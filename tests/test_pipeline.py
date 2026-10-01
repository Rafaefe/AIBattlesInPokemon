"""
Tests del pipeline del D2 con modelos FALSOS (no requieren GPU ni descargas).

Sirven para verificar la logica, nunca como resultado: los resultados reportados
salen solo de d2.evaluate con el modelo real.

    python -m pytest -q tests
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from d2 import report, strategies
from d2.evaluate import oracle_action, run
from d2.ground_truth import MODERN_VALUES, single_effectiveness
from d2.parsing import final_line_parse
from d2.states import generate_cases, public_view

ROOT = Path(__file__).resolve().parents[1]
FACT_RE = re.compile(r"a (\S+)-type move hits a (\S+)-type")
WORDS_RE = re.compile(r"how effective is a (\S+)-type attack against a (\S+)-type")
PHRASE = {2.0: "Super effective!", 1.0: "Normal damage.", 0.5: "Not very effective.", 0.0: "No effect."}


class FakeLLM:
    """generate() devuelve siempre la misma etiqueta; choose() responde la tabla verdadera."""

    def __init__(self, label="MOVE_2", facts=None):
        self.label = label
        self.facts = facts or (lambda atk, dfn: single_effectiveness(atk, dfn))

    def generate(self, prompt, max_new_tokens=32):
        if "FINAL: MOVE_N" in prompt:
            return f"Some reasoning...\nFINAL: {self.label}"
        words = WORDS_RE.search(prompt)
        if words:
            return PHRASE[self.facts(*words.groups())]
        return self.label

    def choose(self, prompt, options):
        atk, dfn = FACT_RE.search(prompt).groups()
        value = self.facts(atk, dfn)
        answer = {2.0: "2", 1.0: "1", 0.5: "0.5", 0.0: "0"}[value]
        return answer, {o: (1.0 if o == answer else 0.0) for o in options}


# ------------------------------------------------------------- continuidad --

def test_generator_reproduces_d1_cases_exactly():
    """Con n=30 y la semilla del D1 salen EXACTAMENTE los 30 estados del D1."""
    d1 = json.loads((ROOT / "results" / "benchmark_cases.json").read_text(encoding="utf-8"))
    assert generate_cases(30, 20260830) == d1


def test_oracle_matches_reference_on_eval_set():
    for case in generate_cases(50, 20260830):
        assert oracle_action(case) == case["reference_action"]


# ------------------------------------------------------------- honestidad --

def _d2_imports(module: str) -> set:
    tree = ast.parse((ROOT / "d2" / f"{module}.py").read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("d2"):
            found.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            found |= {a.name.split(".")[1] for a in node.names if a.name.startswith("d2.")}
    return found


def test_solution_never_sees_the_type_chart():
    """Ni strategies.py ni nada de lo que importa (transitivamente) toca la tabla de tipos."""
    seen, stack = set(), ["strategies"]
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        seen.add(mod)
        stack.extend(_d2_imports(mod))
    assert "ground_truth" not in seen, seen
    assert "states" not in seen, seen          # states importa ground_truth


def test_strategies_only_receive_public_fields():
    case = generate_cases(3, 1)[0]
    view = public_view(case)
    assert not {"reference_action", "reference_scores", "difficulty"} & set(view)
    for fn in strategies.STRATEGIES.values():
        fn(FakeLLM(), view)                    # no debe lanzar KeyError


# ----------------------------------------------------------------- logica --

def test_solution_with_perfect_facts_is_always_right():
    llm = FakeLLM()
    for case in generate_cases(50, 20260830):
        d = strategies.decomposed(llm, public_view(case))
        assert d.strict_action == case["reference_action"], case["case_id"]


def test_solution_never_picks_a_move_without_pp():
    llm = FakeLLM()
    for case in generate_cases(60, 7):
        d = strategies.decomposed(llm, public_view(case))
        assert case["moves"][int(d.strict_action[-1]) - 1]["pp"] > 0


def test_permutation_vote_maps_rotations_back_to_original_moves():
    """Un modelo que siempre nombra el mismo MOVIMIENTO debe ganar la votacion por ese movimiento."""
    case = public_view(generate_cases(5, 3)[0])
    target = next(m for m in case["moves"] if m["pp"] > 0)["name"]

    class NameLLM(FakeLLM):
        def generate(self, prompt, max_new_tokens=32):
            return f"I would use {target}."

    d = strategies.permutation_vote(NameLLM(), case)
    assert case["moves"][int(d.strict_action[-1]) - 1]["name"] == target
    assert len(set(r["shown"] for r in d.trace["rotations"])) > 1   # la casilla cambio


def test_position_biased_model_scores_like_the_constant_policy():
    cases = generate_cases(50, 20260830)
    expected = sum(c["reference_action"] == "MOVE_2" for c in cases)
    got = sum(strategies.direct(FakeLLM("MOVE_2"), public_view(c)).strict_action == c["reference_action"]
              for c in cases)
    assert got == expected


def test_final_line_parse():
    case = generate_cases(3, 1)[0]
    usable = next(i for i, m in enumerate(case["moves"], 1) if m["pp"] > 0)
    assert final_line_parse(f"... blah\nFINAL: MOVE_{usable}", case) == f"MOVE_{usable}"
    assert final_line_parse("no final line", case) is None


# ------------------------------------------------------ evaluacion completa --

def test_full_run_and_report(tmp_path):
    """Corre el evaluador completo con un modelo falso que usa la tabla MODERNA."""
    def modern(atk, dfn):
        return MODERN_VALUES.get((atk, dfn), single_effectiveness(atk, dfn))

    run(FakeLLM("MOVE_2", facts=modern), n=50, seed=20260830, out=str(tmp_path), progress=False)
    text = report.build_report(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert "Estrategias sobre los mismos estados" in text
    table = summary["strategies"]
    assert set(table) == {"direct", "structured", "permutation", "cot", "decomposed", "decomposed_cal",
                          "decomposed_words", "notype"}
    assert summary["solution"] == "decomposed_words"
    assert all(t["n"] == 50 for t in table.values())
    # Todo error de la solucion viene de un hecho moderno y se corrige con la tabla Gen I.
    for f in summary["failures"]:
        assert f["cause"] == "tabla de otra generacion"
        assert f["fixed_by_correct_facts"]


def test_run_resumes_without_repeating_work(tmp_path):
    class Counting(FakeLLM):
        n = 0

        def generate(self, prompt, max_new_tokens=32):
            Counting.n += 1
            return super().generate(prompt, max_new_tokens)

    run(Counting(), n=6, seed=1, out=str(tmp_path), strategies=["direct"], progress=False)
    first = Counting.n
    run(Counting(), n=6, seed=1, out=str(tmp_path), strategies=["direct"], progress=False)
    assert Counting.n == first                  # la segunda corrida no pregunta nada


@pytest.mark.parametrize("b,c,expected", [(0, 0, 1.0), (10, 0, 0.001953125), (3, 3, 1.0)])
def test_mcnemar_exact(b, c, expected):
    assert report.mcnemar_exact(b, c) == pytest.approx(expected)


def test_ties_are_broken_by_model_confidence_not_by_position():
    from d2.calculator import best_move
    assert best_move([5.0, 5.0, 3.0]) == 0                       # regla de referencia
    assert best_move([5.0, 5.0, 3.0], tie_break=[1.0, 2.0, 9.0]) == 1
    assert best_move([5.0, 7.0, 3.0], tie_break=[9.0, 0.0, 9.0]) == 1   # no altera un maximo claro


def test_calibration_removes_a_constant_label_preference():
    """Un modelo que prefiere '2' por defecto: la calibracion debe devolver la respuesta con contenido."""
    class Biased(FakeLLM):
        def choose(self, prompt, options):
            atk, dfn = FACT_RE.search(prompt).groups()
            probs = {"2": 0.55, "1": 0.15, "0.5": 0.15, "0": 0.15}      # sesgo hacia "2"
            if atk not in ("N/A", "unknown"):
                truth = {2.0: "2", 1.0: "1", 0.5: "0.5", 0.0: "0"}[single_effectiveness(atk, dfn)]
                probs = {o: (p * 3 if o == truth else p) for o, p in probs.items()}
            z = sum(probs.values())
            probs = {o: p / z for o, p in probs.items()}
            return max(probs, key=probs.get), probs

    cases = [public_view(c) for c in generate_cases(30, 20260830)]
    truth = {c["case_id"]: c["reference_action"] for c in generate_cases(30, 20260830)}
    raw = sum(strategies.decomposed(Biased(), c).strict_action == truth[c["case_id"]] for c in cases)
    cal = sum(strategies.decomposed_calibrated(Biased(), c).strict_action == truth[c["case_id"]] for c in cases)
    assert cal == 30 and cal > raw



# ----------------------------------------------------------- S2 (palabras) --

def test_words_solution_with_perfect_facts_is_always_right():
    llm = FakeLLM()
    for case in generate_cases(50, 20260830):
        d = strategies.decomposed_words(llm, public_view(case))
        assert d.strict_action == case["reference_action"], case["case_id"]


def test_constant_answer_collapses_to_the_no_type_heuristic():
    """Lo que paso con S1 en la corrida real: si el modelo responde siempre lo mismo,
    la solucion se reduce a ignorar los tipos, y el reporte lo tiene que decir."""
    from d2.report import agreement_with_heuristic, heuristic_rows
    from d2.evaluate import score_row
    cases = generate_cases(50, 20260830)
    const = FakeLLM(facts=lambda a, d: 0.5)
    rows = [score_row(c, strategies.decomposed_words(const, public_view(c))) for c in cases]
    rows += heuristic_rows({c["case_id"]: c for c in cases})
    assert agreement_with_heuristic(rows)["decomposed_words"] == 50


def test_parse_effect_reads_the_game_phrases():
    from d2.parsing import parse_effect
    assert parse_effect("It's super effective!") == 2.0
    assert parse_effect("not very effective") == 0.5
    assert parse_effect("Normal-type moves have no effect on Ghost-type Pokemon.") == 0.0
    assert parse_effect("normal damage") == 1.0
    assert parse_effect("I am not sure") is None


def test_cot_accepts_move_name_in_final_line():
    from d2.parsing import final_line_parse, final_line_semantic
    case = {"moves": [{"name": "Thunderbolt", "pp": 5}, {"name": "Strength", "pp": 5},
                      {"name": "Surf", "pp": 5}, {"name": "Lick", "pp": 0}]}
    raw = "...\n**FINAL: THUNDERBOLT**"
    assert final_line_parse(raw, case) is None           # no es MOVE_N: no cuenta como STRICT
    assert final_line_semantic(raw, case) == "MOVE_1"    # pero la intencion es inequivoca
