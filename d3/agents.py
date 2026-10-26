"""
agents.py -- el sistema de agentes del Deliverable 3.

Tres agentes, el MISMO modelo (Qwen2.5-1.5B-Instruct), cada uno con su rol, su
prompt versionado (d3/prompts/) y su entrada/salida:

  Coordinador   entrada: estado publico             salida: PLAN (movimientos a analizar)
                entrada: tabla de la calculadora     salida: MOVE_N  -> PARADA
                herramienta: calculator
  Analista      entrada: (tipo atacante, tipo defensor[, rechazo])
                decide si consulta; si consulta, escribe la query y lee la nota linea a linea
                herramienta: type_lookup             salida: frase del juego -> multiplicador
  Verificador   entrada: hecho del Analista + la nota que consulto
                relee la nota a su manera; acepta (sigue) o rechaza (devuelve al Analista
                citando la linea)
                bucle Analista <-> Verificador: maximo MAX_REVISIONS revisiones

Cada mensaje entre agentes y herramientas queda en la traza (Trace). REGLA: este
modulo nunca importa d2.ground_truth (lo verifica un test).
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

from d2.parsing import semantic_parse, strict_parse
from d2.render import state_text
from d2.strategies import Decision
from d3.prompting import load_prompt
from d3.tools import Passage, TypeLookup, calculator, calculator_best

PHRASES = ["super effective", "normal damage", "not very effective", "no effect"]
MULTIPLIER = {"super effective": 2.0, "normal damage": 1.0, "not very effective": 0.5, "no effect": 0.0}
MAX_REVISIONS = 2
# Version de prompt que usa cada agente (d3/prompts/<agente>.<version>.md).
PROMPT_VERSIONS = {"coordinator": "v2", "analyst": "v2", "verifier": "v2"}
# Opciones de la decision del Analista: la primera significa "consultar".
DECIDE_OPTIONS = {"v1": ["LOOKUP", "ANSWER"], "v2": ["yes", "no"]}


@dataclass(frozen=True)
class Config:
    """Que tecnicas estan activas. FULL = todas; cada ablacion apaga UNA."""
    name: str = "full"
    rag: bool = True            # Analista: herramienta type_lookup
    fewshot: bool = True        # Verificador: ejemplos resueltos de como revisar una lista
    verifier: bool = True       # Verificador + bucle de revision
    decomposition: bool = True  # Coordinador -> Analista por par (False: todo en una llamada)
    ranking: bool = True        # Coordinador ve la tabla ordenada por score (False: orden original)


CONFIGS = {
    "full": Config("full"),
    "no_rag": Config("no_rag", rag=False),
    "no_fewshot": Config("no_fewshot", fewshot=False),
    "no_verifier": Config("no_verifier", verifier=False),
    "no_decomposition": Config("no_decomposition", decomposition=False),
    "no_ranking": Config("no_ranking", ranking=False),
}


# ------------------------------------------------------------------- traza --

@dataclass
class Trace:
    messages: List[Dict] = field(default_factory=list)
    keep_prompts: bool = False
    on_message: Optional[Callable[[Dict], None]] = None     # la demo imprime cada mensaje en vivo

    def log(self, sender: str, receiver: str, kind: str, content) -> None:
        message = {"step": len(self.messages) + 1, "from": sender, "to": receiver,
                   "kind": kind, "content": content}
        self.messages.append(message)
        if self.on_message:
            self.on_message(message)

    def llm_calls(self) -> int:
        return sum(1 for m in self.messages if m["kind"] == "llm")


class Agent:
    """Una llamada al modelo con rol propio: su system prompt y sus plantillas salen del archivo."""

    name = "agent"

    def __init__(self, llm, prompt_name: str, trace: Trace):
        self.llm, self.trace = llm, trace
        self.prompt = load_prompt(prompt_name, PROMPT_VERSIONS[prompt_name])
        self.system = self.prompt.sections["system"]

    def _log_llm(self, section: str, prompt: str, output, extra: Optional[Dict] = None) -> None:
        content = {"template": section, "output": output, **(extra or {})}
        if self.trace.keep_prompts:
            content["prompt"] = prompt
        self.trace.log(self.name, self.name, "llm", content)

    def generate(self, section: str, max_new_tokens: int, **values) -> str:
        prompt = self.prompt.render(section, **values)
        out = self.llm.generate(prompt, max_new_tokens=max_new_tokens, system=self.system)
        self._log_llm(section, prompt, out)
        return out

    def choose(self, section: str, options: List[str], **values) -> str:
        prompt = self.prompt.render(section, **values)
        answer, probs = self.llm.choose(prompt, options, system=self.system)
        self._log_llm(section, prompt, answer, {"probs": probs})
        return answer

    def choose_probs(self, section: str, options: List[str], **values) -> Dict[str, float]:
        """Como choose(), pero devuelve las probabilidades (para comparar varias preguntas)."""
        prompt = self.prompt.render(section, **values)
        answer, probs = self.llm.choose(prompt, options, system=self.system)
        self._log_llm(section, prompt, answer, {"probs": probs})
        return probs


# --------------------------------------------------------------- Analista --

LINE_PHRASE = {"A": "super effective", "B": "not very effective", "C": "no effect", "D": "normal damage"}


class TypeAnalyst(Agent):
    """
    Decide si consulta la tabla y que consulta. Con la nota en la mano la lee por partes:
    una pregunta yes/no por linea ("esta {defend}-type en esta linea?") y gana la linea
    con mayor P(yes). Sin nota (no consulto, o ablacion sin recuperacion) responde de memoria.
    """

    name = "analyst"

    def __init__(self, llm, trace: Trace, lookup: TypeLookup, cfg: Config):
        super().__init__(llm, "analyst", trace)
        self.lookup, self.cfg = lookup, cfg

    def analyze(self, attack: str, defend: str, rejection: Optional[Dict] = None) -> Dict:
        feedback = self.prompt.render("feedback", **rejection) if rejection else ""
        passage: Optional[Passage] = None
        decision, query, line, line_probs = "ANSWER", None, None, None
        if self.cfg.rag:
            options = DECIDE_OPTIONS[self.prompt.version]
            said = self.choose("decide", options, attack=attack, defend=defend, feedback=feedback)
            decision = "LOOKUP" if said == options[0] else "ANSWER"
        if decision == "LOOKUP":
            raw = self.generate("query", 12, attack=attack, defend=defend)
            query = raw.strip().splitlines()[0] if raw.strip() else ""
            query = re.sub(r"^\s*QUERY\s*:\s*", "", query, flags=re.I)
            self.trace.log(self.name, self.lookup.name, "tool_call", {"query": query})
            passage = self.lookup(query)
            self.trace.log(self.lookup.name, self.name, "tool_result",
                           {"title": passage.title, "text": passage.text} if passage
                           else {"title": None, "text": "(no section matches the query)"})
        if passage is not None:
            line_probs = {label: self.choose_probs("line", ["yes", "no"], line=passage.line(label),
                                                   defend=defend, feedback=feedback)["yes"]
                          for label in LINE_PHRASE}
            line = max(line_probs, key=line_probs.get)
            answer = LINE_PHRASE[line]
        else:
            answer = self.choose("answer_memory", PHRASES, attack=attack, defend=defend, feedback=feedback)
        return {"attack": attack, "defend": defend, "decision": decision, "query": query,
                "passage_title": passage.title if passage else None,
                "passage": passage.text if passage else None,
                "line": line, "line_probs": line_probs,
                "answer": answer, "multiplier": MULTIPLIER[answer]}


# ------------------------------------------------------------- Verificador --

class Verifier(Agent):
    """
    Relee la nota con OTRA lectura: la lista de tipos de cada linea A, B y C, con ejemplos
    resueltos; su linea es la primera con P(yes) > 0,5 (si ninguna, D). Acepta si coincide
    con la del Analista. Sin nota, o con la seccion de otro tipo atacante, rechaza sin
    llamar al modelo: no hay evidencia contra la cual verificar.
    """

    name = "verifier"

    def __init__(self, llm, trace: Trace, cfg: Config):
        super().__init__(llm, "verifier", trace)
        self.cfg = cfg

    def review(self, fact: Dict) -> Dict:
        attack, defend = fact["attack"], fact["defend"]
        if fact["passage"] is None:
            return {"accepted": False, "line": None,
                    "reason": self.prompt.render("reason_no_notes", attack=attack)}
        if fact["passage_title"] != f"{attack}-type attacks":
            return {"accepted": False, "line": None,
                    "reason": self.prompt.render("reason_wrong_section", attack=attack,
                                                 title=fact["passage_title"])}
        lines = {l.split(".", 1)[0]: l for l in fact["passage"].splitlines()}
        fewshot = self.prompt.sections["fewshot"] if self.cfg.fewshot else ""
        label = "D"
        for candidate in "ABC":
            items = lines[candidate].split(":", 1)[1].strip()
            if self.choose_probs("check", ["yes", "no"], fewshot=fewshot, items=items,
                                 defend=defend)["yes"] > 0.5:
                label = candidate
                break
        expected = LINE_PHRASE[label]
        if expected == fact["answer"]:
            return {"accepted": True, "line": label, "reason": None}
        return {"accepted": False, "line": label,
                "reason": self.prompt.render("reason_line", defend=defend, label=label,
                                             line=lines[label], expected=expected)}


# ------------------------------------------------------------- Coordinador --

_LABEL = re.compile(r"MOVE[_ ]?([1-4])", re.I)


class Coordinator(Agent):
    name = "coordinator"

    def __init__(self, llm, trace: Trace, cfg: Config):
        super().__init__(llm, "coordinator", trace)
        self.cfg = cfg

    def plan(self, case: Dict) -> List[int]:
        raw = self.generate("plan", 32, state=state_text(case))
        picked = sorted({int(m) - 1 for m in _LABEL.findall(raw)})
        if not picked:                                    # sin plan legible: se analiza todo (se registra)
            self.trace.log(self.name, self.name, "note", "plan unreadable -> analyze all moves")
            picked = list(range(len(case["moves"])))
        return picked

    def _table(self, rows: List[Dict]) -> str:
        shown = rows
        if self.cfg.ranking:
            shown = sorted(rows, key=lambda r: (r["score"] is not None, r["score"] or 0, r["tie"]),
                           reverse=True)
        lines = []
        for r in shown:
            head = f"{r['action']} {r['name']} ({r['type']})"
            if r["pp"] <= 0:
                lines.append(f"{head}: cannot be used (PP=0)")
            elif r["score"] is None:
                lines.append(f"{head}: not analyzed")
            else:
                lines.append(f"{head}: power {r['power']}, accuracy {r['accuracy']}%, STAB {r['stab']}, "
                             f"effectiveness x{r['effectiveness']:g} -> score {r['score']:g}")
        return "\n".join(lines)

    def final(self, case: Dict, rows: List[Dict]) -> str:
        options = [r["action"] for r in rows if r["score"] is not None]
        if not options:
            options = [r["action"] for r in rows if r["pp"] > 0] or [r["action"] for r in rows]
        note = self.prompt.render("order_ranked" if self.cfg.ranking else "order_original")
        return self.choose("final", options, state=state_text(case), order_note=note,
                           table=self._table(rows))

    def single(self, case: Dict, lookup: TypeLookup) -> str:
        """Ablacion sin descomposicion: las mismas notas recuperadas, pero todo en UNA llamada."""
        notes = []
        for mtype in dict.fromkeys(m["type"] for m in case["moves"]):
            self.trace.log(self.name, lookup.name, "tool_call", {"query": mtype})
            p = lookup(mtype)
            self.trace.log(lookup.name, self.name, "tool_result", {"title": p.title, "text": p.text})
            notes.append(f"{p.title}: {p.text}")
        return self.choose("single", [f"MOVE_{i}" for i in range(1, 5)], state=state_text(case),
                           passages="\n".join(notes))


# ------------------------------------------------------------------ sistema --

def run_agents(llm, case: Dict, cfg: Config = CONFIGS["full"], keep_prompts: bool = False,
               on_message: Optional[Callable[[Dict], None]] = None) -> Decision:
    """Un combate completo. `case` es public_view(case): sin respuesta ni dificultad."""
    t0 = time.perf_counter()
    trace = Trace(keep_prompts=keep_prompts, on_message=on_message)
    lookup = TypeLookup()
    coordinator = Coordinator(llm, trace, cfg)
    trace.log("environment", "coordinator", "handoff", {"state": state_text(case)})

    facts: List[Dict] = []
    if not cfg.decomposition:
        action = coordinator.single(case, lookup)
        rows = []
    else:
        analyst, verifier = TypeAnalyst(llm, trace, lookup, cfg), Verifier(llm, trace, cfg)
        plan = coordinator.plan(case)
        effectiveness: Dict[int, Optional[float]] = {}
        for i in plan:
            move = case["moves"][i]
            eff = 1.0
            for defend in case["enemy_types"]:
                trace.log("coordinator", "analyst", "handoff",
                          {"move": f"MOVE_{i + 1}", "attack": move["type"], "defend": defend})
                fact = analyst.analyze(move["type"], defend)
                fact.update({"move": f"MOVE_{i + 1}", "revisions": 0, "verified": None})
                if cfg.verifier:
                    for revision in range(MAX_REVISIONS + 1):
                        trace.log("analyst", "verifier", "handoff",
                                  {k: fact[k] for k in ("attack", "defend", "answer", "passage_title")})
                        review = verifier.review(fact)
                        if review["accepted"]:
                            trace.log("verifier", "analyst", "verdict", {"accepted": True, "line": review["line"]})
                            fact["verified"] = True
                            break
                        if revision == MAX_REVISIONS:         # se agota el bucle: queda sin verificar
                            fact["verified"] = False
                            break
                        trace.log("verifier", "analyst", "handoff",
                                  {"rejected": fact["answer"], "line": review["line"], "reason": review["reason"]})
                        rejection = {"previous": fact["answer"], "reason": review["reason"]}
                        revised = analyst.analyze(move["type"], defend, rejection)
                        fact.update({**revised, "revisions": revision + 1})
                trace.log("analyst", "coordinator", "handoff",
                          {k: fact[k] for k in ("move", "attack", "defend", "answer", "multiplier",
                                                "verified", "revisions")})
                facts.append(fact)
                eff *= fact["multiplier"]
            effectiveness[i] = eff
        trace.log("coordinator", "calculator", "tool_call", {"effectiveness": {
            f"MOVE_{i + 1}": e for i, e in effectiveness.items()}})
        rows = calculator(case["moves"], case["player_types"], effectiveness)
        trace.log("calculator", "coordinator", "tool_result",
                  [{k: r[k] for k in ("action", "name", "score")} for r in rows])
        action = coordinator.final(case, rows)

    trace.log("coordinator", "environment", "stop", {"action": action})
    detail = {"config": asdict(cfg), "facts": facts, "calculator": rows,
              "calculator_best": calculator_best(rows) if rows else None,
              "prompts": {a: load_prompt(a, v).describe() for a, v in PROMPT_VERSIONS.items()},
              "messages": trace.messages}
    return Decision(f"agents_{cfg.name}", action, strict_parse(action, case), semantic_parse(action, case),
                    trace.llm_calls(), time.perf_counter() - t0, detail)
