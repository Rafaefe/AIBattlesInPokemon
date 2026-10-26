"""
Tests del sistema de agentes del D3 con modelos FALSOS (sin GPU ni descargas).
Verifican la logica y las reglas de honestidad; los resultados salen solo de
d3.evaluate con el modelo real.

    python -m pytest -q tests
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from d2.ground_truth import single_effectiveness
from d2.states import TYPES, generate_cases, public_view
from d3 import agents, evaluate, report
from d3.prompting import PROMPT_DIR, load_prompt
from d3.tools import TypeLookup, calculator, calculator_best, load_kb

ROOT = Path(__file__).resolve().parents[1]
QUESTION = re.compile(r"how effective is a (\S+)-type attack against a (\S+)-type")
PHRASE = {2.0: "super effective", 1.0: "normal damage", 0.5: "not very effective", 0.0: "no effect"}


class FakeAgentLLM:
    """
    Un modelo falso que sigue los contratos de cada plantilla:
    consulta siempre, escribe como query el tipo atacante, lee cada linea de la nota
    buscando el tipo defensor, el Verificador relee igual (o, en sus primeras `reject`
    revisiones, invierte su lectura y por lo tanto rechaza) y el Coordinador elige la
    PRIMERA fila de la tabla que se le muestra.
    """

    def __init__(self, facts=None, reject: int = 0, decide: str = "LOOKUP"):
        self.facts = facts or single_effectiveness
        self.reject, self.decide = reject, decide
        self.calls = {"generate": 0, "choose": 0}

    def generate(self, prompt, max_new_tokens=32, system=None):
        self.calls["generate"] += 1
        if "PLAN:" in prompt:
            return "PLAN: MOVE_1, MOVE_2, MOVE_3, MOVE_4"
        if "QUERY:" in prompt:
            return QUESTION.search(prompt).group(1)
        q = QUESTION.search(prompt)            # S2 del D2
        return PHRASE[self.facts(*q.groups())] if q else "MOVE_1"

    def choose(self, prompt, options, system=None):
        self.calls["choose"] += 1
        if "do you need to check the type chart notes" in prompt:
            pick = "yes" if self.decide == "LOOKUP" else "no"
        elif "listed in this line?" in prompt:          # Analista: lectura por linea
            dfn = re.search(r"Is (\S+)-type listed in this line", prompt).group(1)
            line = re.search(r'Line from the type chart notes:\n"(.*)"', prompt).group(1)
            p_yes = 0.4 if line.startswith("D.") else float(f"{dfn}-type" in line)
            return ("yes" if p_yes > 0.5 else "no"), {"yes": p_yes, "no": 1 - p_yes}
        elif "Does the list contain" in prompt:         # Verificador: la ultima lista del prompt
            dfn = re.findall(r"Does the list contain (\S+)-type", prompt)[-1]
            items = re.findall(r"^List: (.*)$", prompt, re.M)[-1]
            inside = f"{dfn}-type" in items
            if self.reject > 0:                          # invertir siempre contradice al Analista
                inside = not inside
                if inside or items == "none.":           # la revision termina en esta lista o en D
                    self.reject -= 1
            pick = "yes" if inside else "no"
        elif set(options) <= set(PHRASE.values()):
            pick = PHRASE[self.facts(*QUESTION.findall(prompt)[-1])]
        else:                                   # Coordinador: primera etiqueta que aparece en la tabla
            labels = re.findall(r"^(MOVE_[1-4]) ", prompt.split("produced this table.")[-1].split("Rows are")[0], re.M)
            pick = next((l for l in labels if l in options), options[0])
        return pick, {o: float(o == pick) for o in options}


# ---------------------------------------------------------------- honestidad --

def _imports(path: Path) -> set:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
    return found


def test_agents_never_see_the_type_chart():
    """Ni d3/agents.py ni nada de lo que importa (transitivamente) toca d2.ground_truth."""
    seen, stack = set(), ["d3.agents"]
    while stack:
        mod = stack.pop()
        if mod in seen or not mod.startswith(("d2", "d3")):
            continue
        seen.add(mod)
        stack.extend(_imports((ROOT / Path(*mod.split("."))).with_suffix(".py")))
    assert "d2.ground_truth" not in seen, seen
    assert "d2.states" not in seen, seen


def test_knowledge_base_text_agrees_with_the_judge():
    """El texto que consulta el Analista dice lo mismo que la tabla del juez, par por par."""
    values = {"A": 2.0, "B": 0.5, "C": 0.0}
    kb = {p.attack_type: p for p in load_kb()}
    assert set(kb) == set(TYPES)
    for atk in TYPES:
        assert kb[atk].line("D") == "D. Normal damage against every other type."
        listed = {}
        for label, value in values.items():
            for d in re.findall(r"(\w+)-type", kb[atk].line(label)):
                assert d not in listed, (atk, d)          # cada tipo en una sola linea
                listed[d] = value
        for dfn in TYPES:
            assert listed.get(dfn, 1.0) == single_effectiveness(atk, dfn), (atk, dfn)


def test_every_agent_prompt_is_a_versioned_file():
    for agent, version in agents.PROMPT_VERSIONS.items():
        p = load_prompt(agent, version)
        assert p.path.parent == PROMPT_DIR and p.path.name == f"{agent}.{version}.md"
        assert "system" in p.sections and p.version == version and len(p.sha256) == 64
        assert p.render("system")                       # todas las plantillas son de este archivo
    assert not re.search(r"Answer: |You are the", Path(agents.__file__).read_text(encoding="utf-8"))


# --------------------------------------------------------------- herramientas --

def test_type_lookup_returns_the_first_mentioned_attacking_type():
    lookup = TypeLookup()
    assert lookup("Electric").attack_type == "Electric"
    assert lookup("Electric-type attacks vs Ground").attack_type == "Electric"
    assert lookup("ground electric").attack_type == "Ground"     # consulta mal escrita -> seccion equivocada
    assert lookup("dragon") is None


def test_calculator_ignores_moves_without_pp_or_not_analyzed():
    case = public_view(generate_cases(3, 1)[0])
    rows = calculator(case["moves"], case["player_types"], {0: 1.0})
    assert rows[0]["score"] is not None and all(r["score"] is None for r in rows[1:])
    assert calculator_best(rows) == "MOVE_1"


# ---------------------------------------------------------------- el sistema --

def test_full_system_with_perfect_agents_is_always_right():
    for case in generate_cases(50, 20260830) + generate_cases(50, 20260927):
        d = agents.run_agents(FakeAgentLLM(), public_view(case))
        assert d.strict_action == case["reference_action"], case["case_id"]


def test_trace_contains_every_handoff_and_stops_once():
    case = generate_cases(5, 20260830)[0]
    d = agents.run_agents(FakeAgentLLM(), public_view(case))
    msgs = d.trace["messages"]
    kinds = {(m["from"], m["to"], m["kind"]) for m in msgs}
    for edge in [("environment", "coordinator", "handoff"), ("coordinator", "analyst", "handoff"),
                 ("analyst", "type_lookup", "tool_call"), ("type_lookup", "analyst", "tool_result"),
                 ("analyst", "verifier", "handoff"), ("analyst", "coordinator", "handoff"),
                 ("coordinator", "calculator", "tool_call"), ("coordinator", "environment", "stop")]:
        assert edge in kinds, edge
    assert [m["kind"] for m in msgs].count("stop") == 1 and msgs[-1]["kind"] == "stop"
    assert d.llm_calls == sum(m["kind"] == "llm" for m in msgs)


def test_verifier_rejects_without_evidence_and_cites_the_line():
    case = public_view(generate_cases(5, 20260830)[0])
    v = agents.Verifier(FakeAgentLLM(), agents.Trace(), agents.CONFIGS["full"])
    fact = {"attack": "Electric", "defend": "Ground", "answer": "normal damage", "passage": None,
            "passage_title": None}
    assert not v.review(fact)["accepted"]                                  # sin nota: rechaza
    p = TypeLookup()("Electric")
    fact.update(passage=p.text, passage_title=p.title)
    r = v.review(fact)
    assert not r["accepted"] and r["line"] == "C" and "no effect" in r["reason"]
    assert v.review({**fact, "answer": "no effect"})["accepted"]
    g = TypeLookup()("Ground")
    assert "not Electric" in v.review({**fact, "passage": g.text, "passage_title": g.title})["reason"]


def test_verifier_rejection_sends_the_fact_back_and_the_loop_is_bounded():
    case = public_view(generate_cases(5, 20260830)[0])
    d = agents.run_agents(FakeAgentLLM(reject=1), case)
    assert d.trace["facts"][0]["revisions"] == 1 and d.trace["facts"][0]["verified"] is True
    d = agents.run_agents(FakeAgentLLM(reject=10 ** 6), case)
    assert all(f["revisions"] == agents.MAX_REVISIONS and f["verified"] is False for f in d.trace["facts"])


def test_ablations_switch_off_exactly_one_technique():
    case = public_view(generate_cases(5, 20260830)[0])
    no_rag = agents.run_agents(FakeAgentLLM(), case, agents.CONFIGS["no_rag"])
    assert not any(m["kind"] == "tool_call" and m["to"] == "type_lookup" for m in no_rag.trace["messages"])
    no_ver = agents.run_agents(FakeAgentLLM(), case, agents.CONFIGS["no_verifier"])
    assert not any("verifier" in (m["from"], m["to"]) for m in no_ver.trace["messages"])
    single = agents.run_agents(FakeAgentLLM(), case, agents.CONFIGS["no_decomposition"])
    assert not any(m["to"] == "analyst" for m in single.trace["messages"]) and single.llm_calls == 1
    for name, cfg in agents.CONFIGS.items():
        off = [k for k in ("rag", "fewshot", "verifier", "decomposition", "ranking") if not getattr(cfg, k)]
        assert len(off) == (0 if name == "full" else 1), name


def test_without_ranking_a_position_biased_coordinator_falls_back_to_move_1():
    """El falso Coordinador elige la primera fila: con la tabla en orden original eso es MOVE_1."""
    cases = generate_cases(50, 20260830)
    acts = [agents.run_agents(FakeAgentLLM(), public_view(c), agents.CONFIGS["no_ranking"]).strict_action
            for c in cases]
    first_usable = [next(f"MOVE_{i + 1}" for i, m in enumerate(c["moves"]) if m["pp"] > 0) for c in cases]
    assert acts == first_usable


def test_evaluate_writes_one_trace_per_state_and_a_report(tmp_path):
    llm = FakeAgentLLM()
    systems = ["direct", "decomposed_words", "agents_full", "agents_no_verifier"]
    for s in ("orig", "holdout"):
        evaluate.run(llm, s, n=6, systems=systems, out=tmp_path, progress=False)
    for s in ("orig", "holdout"):
        for name in ("agents_full", "agents_no_verifier"):
            lines = (tmp_path / s / "traces" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
            assert len(lines) == 6 and all(json.loads(l)["messages"] for l in lines)
    text = report.build_report(tmp_path)
    assert "D3 Agentes (completo)" in text and (tmp_path / "summary.json").exists()
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["tables"]["all"]["agents_full"]["acc_pct"] == 100.0
    assert summary["agents"]["agents_full"]["facts_right_pct"] == 100.0
    # se reanuda sin repetir trabajo
    evaluate.run(llm, "orig", n=6, systems=systems, out=tmp_path, progress=False)
    assert len((tmp_path / "orig" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()) == 24
