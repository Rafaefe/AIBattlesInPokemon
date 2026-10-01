"""
strategies.py -- baseline, alternativas y la solucion.

REGLA: este modulo nunca importa d2.ground_truth. Cada estrategia recibe
`public_view(case)` (sin respuesta ni dificultad) y un objeto `llm` con
generate() y choose(). Todo lo que "sabe" sobre tipos lo aporta el modelo.

  B0  direct        prompt directo del D1 + pedir la etiqueta MOVE_N   (BASELINE)
  A1  structured    prompt estructurado del D1, sin cambios            (alternativa)
  A2  permutation   B0 sobre 4 rotaciones del orden + votacion          (alternativa)
  A3  cot           chain-of-thought con la formula, en una llamada     (alternativa)
  S1  decomposed        hechos de tipo en NUMEROS (2/1/0.5/0) + calculadora   (v1)
  S1+ decomposed_cal    S1 con calibracion contextual                          (v1)
  S2  decomposed_words  hechos de tipo en PALABRAS + calculadora               (SOLUCION)

S1 fue la primera version. En la corrida real el modelo respondio "0.5" en los
122 pares (y 0.5 con 90 % ante una pregunta VACIA): la respuesta dependia del
formato numerico, no de los tipos. S2 pregunta con las palabras del propio juego.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from d2.calculator import base_power, best_move, expected_damage, stab
from d2.parsing import (final_line_parse, final_line_semantic, parse_effect,
                        semantic_parse, strict_parse)
from d2.render import state_text


@dataclass
class Decision:
    strategy: str
    raw: str
    strict_action: Optional[str]
    interpreted_action: Optional[str]
    llm_calls: int
    seconds: float
    trace: Dict = field(default_factory=dict)


# ------------------------------------------------------------------ prompts --

def direct_prompt(case: Dict) -> str:
    """D1 DIRECT + una linea que pide la etiqueta (corrige la amenaza T1 del D1)."""
    return (
        "You are playing Pokemon Blue.\n"
        "Your goal is to win the battle.\n\n"
        "Here is the current battle state:\n\n"
        f"{state_text(case)}\n\n"
        "What move would you use next?\n"
        "Answer with exactly one label: MOVE_1, MOVE_2, MOVE_3 or MOVE_4."
    )


def structured_prompt(case: Dict) -> str:
    """D1 STRUCTURED, sin cambios."""
    return (
        "You are the battle decision module for Pokemon Blue.\n\n"
        "Given the battle state below, select the best available move.\n\n"
        "When deciding, consider:\n"
        "- type effectiveness,\n- STAB,\n- move power,\n- accuracy,\n"
        "- and remaining PP.\n\n"
        f"{state_text(case)}\n\n"
        "Return EXACTLY one of:\nMOVE_1\nMOVE_2\nMOVE_3\nMOVE_4\n\n"
        "Do not explain.\nDo not write the move name.\nReturn only the MOVE_N label."
    )


def cot_prompt(case: Dict) -> str:
    """Misma informacion que usa la solucion (la formula), pero el modelo hace todo."""
    return (
        "You are the battle decision module for Pokemon Blue (Generation I).\n\n"
        f"{state_text(case)}\n\n"
        "Each move's expected damage is:\n"
        "score = power x (accuracy / 100) x STAB x type effectiveness\n"
        "- STAB is 1.5 if the move's type matches one of your types, otherwise 1.\n"
        "- Type effectiveness is the product of the multipliers (2, 1, 0.5 or 0) "
        "against each of the opponent's types.\n"
        "- A move with PP = 0 cannot be used.\n\n"
        "Think step by step: for each move, write its type effectiveness, its STAB "
        "and its score. Then choose the move with the highest score and finish "
        "with one final line exactly like:\nFINAL: MOVE_N"
    )


FACT_OPTIONS = ["2", "1", "0.5", "0"]


def fact_prompt(attack_type: str, defend_type: str) -> str:
    """Una sola pregunta de la tabla de tipos. Nunca hay cuatro movimientos a la vista."""
    return (
        f"In Pokemon Blue (Generation I), a {attack_type}-type move hits a "
        f"{defend_type}-type Pokemon.\n"
        "What is the type-effectiveness damage multiplier?\n"
        "Answer with only one of: 2, 1, 0.5, 0"
    )


# --------------------------------------------------------------- estrategias --

def direct(llm, case: Dict, max_new_tokens: int = 48) -> Decision:
    t0 = time.perf_counter()
    raw = llm.generate(direct_prompt(case), max_new_tokens=max_new_tokens)
    return Decision("direct", raw, strict_parse(raw, case), semantic_parse(raw, case),
                    1, time.perf_counter() - t0)


def structured(llm, case: Dict, max_new_tokens: int = 48) -> Decision:
    t0 = time.perf_counter()
    raw = llm.generate(structured_prompt(case), max_new_tokens=max_new_tokens)
    return Decision("structured", raw, strict_parse(raw, case), semantic_parse(raw, case),
                    1, time.perf_counter() - t0)


def rotate(case: Dict, r: int) -> Dict:
    moves = case["moves"]
    return {**case, "moves": moves[r:] + moves[:r]}


def permutation_vote(llm, case: Dict, max_new_tokens: int = 48) -> Decision:
    """
    Pregunta B0 con el orden de los movimientos rotado 0..3 veces y vota por el
    movimiento ORIGINAL mas elegido. Empate: gana la respuesta sin rotar si esta
    entre las empatadas; si no, el indice original menor.
    """
    t0 = time.perf_counter()
    rotations, votes = [], Counter()
    for r in range(4):
        rotated = rotate(case, r)
        raw = llm.generate(direct_prompt(rotated), max_new_tokens=max_new_tokens)
        shown = semantic_parse(raw, rotated)          # posicion MOSTRADA elegida
        original = None
        if shown is not None:
            original_idx = (int(shown[-1]) - 1 + r) % 4
            original = f"MOVE_{original_idx + 1}"
            votes[original] += 1
        rotations.append({"rotation": r, "raw": raw, "shown": shown, "original": original})

    action = None
    if votes:
        top = max(votes.values())
        tied = sorted(a for a, v in votes.items() if v == top)
        unrotated = rotations[0]["original"]
        action = unrotated if unrotated in tied else tied[0]
    raw = " | ".join(f"r{x['rotation']}:{x['raw']}" for x in rotations)
    return Decision("permutation", raw, action, action, 4, time.perf_counter() - t0,
                    {"rotations": rotations, "votes": dict(votes)})


def cot(llm, case: Dict, max_new_tokens: int = 320) -> Decision:
    t0 = time.perf_counter()
    raw = llm.generate(cot_prompt(case), max_new_tokens=max_new_tokens)
    return Decision("cot", raw, final_line_parse(raw, case), final_line_semantic(raw, case),
                    1, time.perf_counter() - t0)


def content_free_prior(llm) -> Dict[str, float]:
    """
    Preferencia del modelo por cada respuesta cuando la pregunta no tiene contenido
    (calibracion contextual, Zhao et al. 2021). Promedio de dos entradas vacias.
    """
    priors = [llm.choose(fact_prompt(a, d), FACT_OPTIONS)[1]
              for a, d in [("N/A", "N/A"), ("unknown", "unknown")]]
    return {o: max(1e-6, sum(p[o] for p in priors) / len(priors)) for o in FACT_OPTIONS}


def _ask_fact(llm, attack: str, defend: str, prior: Optional[Dict[str, float]]):
    answer, probs = llm.choose(fact_prompt(attack, defend), FACT_OPTIONS)
    if prior is not None:                         # descontar la preferencia a priori
        raw = {o: probs[o] / prior[o] for o in FACT_OPTIONS}
        total = sum(raw.values()) or 1.0
        probs = {o: round(v / total, 4) for o, v in raw.items()}
        answer = max(FACT_OPTIONS, key=lambda o: probs[o])
    return answer, probs


def _decompose(llm, case: Dict, name: str, prior: Optional[Dict[str, float]] = None) -> Decision:
    t0 = time.perf_counter()
    rows, scores, soft, calls = [], [], [], 0
    for i, move in enumerate(case["moves"], start=1):
        facts, effectiveness, soft_eff = [], None, None
        if move["pp"] > 0:
            effectiveness, soft_eff = 1.0, 1.0
            for defend_type in case["enemy_types"]:
                answer, probs = _ask_fact(llm, move["type"], defend_type, prior)
                calls += 1
                multiplier = float(answer)
                effectiveness *= multiplier
                soft_eff *= sum(float(o) * p for o, p in probs.items())
                facts.append({"attack": move["type"], "defend": defend_type,
                              "multiplier": multiplier, "probs": probs})
        scores.append(expected_damage(move, case["player_types"], effectiveness))
        # Solo para desempatar: el mismo calculo con el multiplicador ESPERADO segun
        # las probabilidades del modelo. Evita que un empate caiga por defecto en
        # MOVE_1, que seria reintroducir un sesgo de posicion.
        soft.append(expected_damage(move, case["player_types"], soft_eff))
        rows.append({"action": f"MOVE_{i}", "name": move["name"], "type": move["type"],
                     "power": move["power"], "accuracy": move["accuracy"], "pp": move["pp"],
                     "stab": stab(move, case["player_types"]), "facts": facts,
                     "effectiveness": effectiveness,
                     "score": None if scores[-1] == float("-inf") else round(scores[-1], 3)})

    action = f"MOVE_{best_move(scores, tie_break=soft) + 1}"
    top = max(scores)
    tie_broken = sum(1 for x in scores if x == top) > 1      # se reporta: transparencia
    raw = "; ".join(f"{r['action']}={r['score']}" for r in rows)
    return Decision(name, raw, action, action, calls, time.perf_counter() - t0,
                    {"moves": rows, "tie_broken": tie_broken, "prior": prior})


def decomposed(llm, case: Dict) -> Decision:
    """
    SOLUCION: descomposicion + herramienta.

    1. Por cada movimiento usable y cada tipo del rival, UNA pregunta al modelo:
       el multiplicador de ese tipo contra ese tipo (respuesta restringida a
       2 / 1 / 0.5 / 0). El modelo nunca ve los cuatro movimientos juntos, asi
       que no hay posicion a la cual sesgarse.
    2. Para rivales de doble tipo se multiplican los dos hechos (regla de Gen I).
    3. La calculadora aplica potencia x precision x STAB x efectividad y elige
       el maximo. La combinacion -el paso que fallaba en el D1- ya no la hace
       el modelo.
    """
    return _decompose(llm, case, "decomposed")


def decomposed_calibrated(llm, case: Dict) -> Decision:
    """La misma solucion, descontando la preferencia a priori del modelo por cada respuesta."""
    return _decompose(llm, case, "decomposed_cal", prior=content_free_prior(llm))


# ------------------------------------------------------ S2: hechos en palabras --

FACT_PHRASES = "super effective, normal damage, not very effective, no effect"


def fact_prompt_words(attack_type: str, defend_type: str) -> str:
    """La misma pregunta de un solo hecho, con las palabras que usa el juego."""
    return (
        f"In Pokemon Red and Blue (Generation I), how effective is a {attack_type}-type "
        f"attack against a {defend_type}-type Pokemon?\n"
        f"Answer with exactly one of these phrases: {FACT_PHRASES}."
    )


def decomposed_words(llm, case: Dict, max_new_tokens: int = 12) -> Decision:
    """
    SOLUCION (S2): descomposicion + herramienta, con la respuesta en palabras.

    Igual que S1 -una pregunta por movimiento y tipo rival, el modelo nunca ve
    las cuatro opciones juntas, la calculadora combina-, pero el modelo responde
    en lenguaje natural ("super effective", "not very effective", ...) y un
    parser fijo lo traduce a 2 / 0.5 / 0 / 1. Si la respuesta no se entiende se
    usa x1 y se marca como no interpretada (se reporta).
    Empates exactos: gana el de mayor potencia x precision x STAB.
    """
    t0 = time.perf_counter()
    rows, scores, ties, calls = [], [], [], 0
    for i, move in enumerate(case["moves"], start=1):
        facts, effectiveness = [], None
        if move["pp"] > 0:
            effectiveness = 1.0
            for defend_type in case["enemy_types"]:
                answer = llm.generate(fact_prompt_words(move["type"], defend_type),
                                      max_new_tokens=max_new_tokens)
                calls += 1
                parsed = parse_effect(answer)
                multiplier = 1.0 if parsed is None else parsed
                effectiveness *= multiplier
                facts.append({"attack": move["type"], "defend": defend_type, "answer": answer,
                              "multiplier": multiplier, "parsed": parsed is not None})
        scores.append(expected_damage(move, case["player_types"], effectiveness))
        ties.append(base_power(move, case["player_types"]) if move["pp"] > 0 else float("-inf"))
        rows.append({"action": f"MOVE_{i}", "name": move["name"], "type": move["type"],
                     "power": move["power"], "accuracy": move["accuracy"], "pp": move["pp"],
                     "stab": stab(move, case["player_types"]), "facts": facts,
                     "effectiveness": effectiveness,
                     "score": None if scores[-1] == float("-inf") else round(scores[-1], 3)})

    action = f"MOVE_{best_move(scores, tie_break=ties) + 1}"
    top = max(scores)
    raw = "; ".join(f"{r['action']}={r['score']}" for r in rows)
    return Decision("decomposed_words", raw, action, action, calls, time.perf_counter() - t0,
                    {"moves": rows, "tie_broken": sum(1 for x in scores if x == top) > 1})


STRATEGIES = {
    "direct": direct,            # B0  baseline
    "structured": structured,    # A1
    "permutation": permutation_vote,  # A2
    "cot": cot,                  # A3
    "decomposed": decomposed,    # S   solucion
    "decomposed_cal": decomposed_calibrated,  # S1+cal
    "decomposed_words": decomposed_words,      # S2  solucion
}

LABELS = {
    "direct": "B0 Directo (baseline)",
    "structured": "A1 Estructurado (D1)",
    "permutation": "A2 Votacion x4 permutaciones",
    "cot": "A3 Chain-of-thought + formula",
    "decomposed": "S1 Descomposicion numerica (v1)",
    "decomposed_cal": "S1+cal numerica calibrada (v1)",
    "decomposed_words": "S2 Descomposicion en palabras",
    "notype": "H  Heuristica sin tipos (sin modelo)",
}
