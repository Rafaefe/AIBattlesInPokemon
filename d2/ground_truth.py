"""
ground_truth.py -- SOLO PARA EVALUACION.

Contiene la tabla de efectividad de tipos de la Generacion I y la politica
de referencia del Deliverable 1:

    score = power x (accuracy / 100) x STAB x type_effectiveness
    score = 0 si PP = 0

La solucion (d2/strategies.py) NO puede importar este modulo: si lo hiciera,
el sistema resolveria la tarea con la tabla en vez de con el modelo. La regla
se verifica en tests/test_pipeline.py::test_solution_never_sees_the_type_chart.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# Copia exacta de la tabla usada en el Deliverable 1 (lo no listado es 1x).
TYPE_CHART: Dict[str, Dict[str, float]] = {
    "Normal":   {"Rock": 0.5, "Ghost": 0.0},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Rock": 2.0, "Poison": 0.5,
                 "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Ghost": 0.0},
    "Flying":   {"Fighting": 2.0, "Bug": 2.0, "Grass": 2.0, "Rock": 0.5,
                 "Electric": 0.5},
    "Poison":   {"Grass": 2.0, "Bug": 2.0, "Poison": 0.5, "Ground": 0.5,
                 "Rock": 0.5, "Ghost": 0.5},
    "Ground":   {"Poison": 2.0, "Rock": 2.0, "Fire": 2.0, "Electric": 2.0,
                 "Bug": 0.5, "Grass": 0.5, "Flying": 0.0},
    "Rock":     {"Flying": 2.0, "Bug": 2.0, "Fire": 2.0, "Ice": 2.0,
                 "Fighting": 0.5, "Ground": 0.5},
    "Bug":      {"Grass": 2.0, "Psychic": 2.0, "Poison": 2.0, "Fighting": 0.5,
                 "Flying": 0.5, "Ghost": 0.5, "Fire": 0.5},
    # En Gen I, Ghost no afecta a Psychic (bug original del juego).
    "Ghost":    {"Normal": 0.0, "Psychic": 0.0, "Ghost": 2.0},
    "Fire":     {"Bug": 2.0, "Grass": 2.0, "Ice": 2.0, "Fire": 0.5,
                 "Water": 0.5, "Rock": 0.5},
    "Water":    {"Fire": 2.0, "Ground": 2.0, "Rock": 2.0, "Water": 0.5,
                 "Grass": 0.5},
    "Grass":    {"Water": 2.0, "Ground": 2.0, "Rock": 2.0, "Fire": 0.5,
                 "Grass": 0.5, "Poison": 0.5, "Flying": 0.5, "Bug": 0.5},
    "Electric": {"Water": 2.0, "Flying": 2.0, "Electric": 0.5, "Grass": 0.5,
                 "Ground": 0.0},
    "Psychic":  {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5},
    "Ice":      {"Grass": 2.0, "Ground": 2.0, "Flying": 2.0, "Water": 0.5,
                 "Ice": 0.5},
}

# Hechos de la tabla que CAMBIARON a partir de la Generacion II. Un modelo
# entrenado mayormente con informacion de juegos modernos tiende a responder
# el valor moderno. Se usa solo para clasificar errores en el analisis.
MODERN_VALUES: Dict[Tuple[str, str], float] = {
    ("Ghost", "Psychic"): 2.0,   # Gen I: 0   (bug)
    ("Bug", "Poison"): 0.5,      # Gen I: 2
    ("Poison", "Bug"): 1.0,      # Gen I: 2
    ("Ice", "Fire"): 0.5,        # Gen I: 1
}


def single_effectiveness(attack_type: str, defend_type: str) -> float:
    """Multiplicador de UN tipo atacante contra UN tipo defensor."""
    return TYPE_CHART.get(attack_type, {}).get(defend_type, 1.0)


def type_effectiveness(attack_type: str, defender_types: List[str]) -> float:
    result = 1.0
    for defend_type in defender_types:
        result *= single_effectiveness(attack_type, defend_type)
    return result


def reference_score(move: Dict, player_types: List[str], enemy_types: List[str]) -> float:
    if move["pp"] <= 0:
        return 0.0
    stab = 1.5 if move["type"] in player_types else 1.0
    eff = type_effectiveness(move["type"], enemy_types)
    return move["power"] * (move["accuracy"] / 100.0) * stab * eff


def add_reference(case: Dict) -> Dict:
    """Agrega reference_action, reference_scores y best_vs_second_ratio (igual que D1)."""
    scores = [reference_score(m, case["player_types"], case["enemy_types"])
              for m in case["moves"]]
    best_idx = max(range(4), key=lambda i: scores[i])
    case["reference_action"] = f"MOVE_{best_idx + 1}"
    case["reference_scores"] = [round(x, 3) for x in scores]
    ordered = sorted(scores, reverse=True)
    case["best_vs_second_ratio"] = round(ordered[0] / ordered[1], 3) if ordered[1] > 0 else 999.0
    return case
