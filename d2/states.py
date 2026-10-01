"""
states.py -- generador de estados de combate (identico al del Deliverable 1).

Usa la politica de referencia para etiquetar cada estado y para asignar su
dificultad, por eso importa ground_truth. Es parte del BENCHMARK, no de la
solucion: las estrategias reciben solo `public_view(case)`, sin las etiquetas.
"""

from __future__ import annotations

import random
from typing import Dict, List

from d2.ground_truth import add_reference

MOVE_DB = [
    {"name": "Scratch",       "type": "Normal",   "power": 40,  "accuracy": 100},
    {"name": "Tackle",        "type": "Normal",   "power": 35,  "accuracy": 95},
    {"name": "Quick Attack",  "type": "Normal",   "power": 40,  "accuracy": 100},
    {"name": "Body Slam",     "type": "Normal",   "power": 85,  "accuracy": 100},
    {"name": "Take Down",     "type": "Normal",   "power": 90,  "accuracy": 85},
    {"name": "Mega Punch",    "type": "Normal",   "power": 80,  "accuracy": 85},
    {"name": "Strength",      "type": "Normal",   "power": 80,  "accuracy": 100},
    {"name": "Slash",         "type": "Normal",   "power": 70,  "accuracy": 100},
    {"name": "Ember",         "type": "Fire",     "power": 40,  "accuracy": 100},
    {"name": "Flamethrower",  "type": "Fire",     "power": 95,  "accuracy": 100},
    {"name": "Fire Blast",    "type": "Fire",     "power": 120, "accuracy": 85},
    {"name": "Water Gun",     "type": "Water",    "power": 40,  "accuracy": 100},
    {"name": "BubbleBeam",    "type": "Water",    "power": 65,  "accuracy": 100},
    {"name": "Surf",          "type": "Water",    "power": 95,  "accuracy": 100},
    {"name": "Hydro Pump",    "type": "Water",    "power": 120, "accuracy": 80},
    {"name": "Vine Whip",     "type": "Grass",    "power": 35,  "accuracy": 100},
    {"name": "Razor Leaf",    "type": "Grass",    "power": 55,  "accuracy": 95},
    {"name": "ThunderShock",  "type": "Electric", "power": 40,  "accuracy": 100},
    {"name": "Thunderbolt",   "type": "Electric", "power": 95,  "accuracy": 100},
    {"name": "Thunder",       "type": "Electric", "power": 120, "accuracy": 70},
    {"name": "Ice Beam",      "type": "Ice",      "power": 95,  "accuracy": 100},
    {"name": "Blizzard",      "type": "Ice",      "power": 120, "accuracy": 90},
    {"name": "Low Kick",      "type": "Fighting", "power": 50,  "accuracy": 90},
    {"name": "Submission",    "type": "Fighting", "power": 80,  "accuracy": 80},
    {"name": "Peck",          "type": "Flying",   "power": 35,  "accuracy": 100},
    {"name": "Drill Peck",    "type": "Flying",   "power": 80,  "accuracy": 100},
    {"name": "Sludge",        "type": "Poison",   "power": 65,  "accuracy": 100},
    {"name": "Earthquake",    "type": "Ground",   "power": 100, "accuracy": 100},
    {"name": "Confusion",     "type": "Psychic",  "power": 50,  "accuracy": 100},
    {"name": "Psybeam",       "type": "Psychic",  "power": 65,  "accuracy": 100},
    {"name": "Psychic",       "type": "Psychic",  "power": 90,  "accuracy": 100},
    {"name": "Leech Life",    "type": "Bug",      "power": 20,  "accuracy": 100},
    {"name": "Rock Throw",    "type": "Rock",     "power": 50,  "accuracy": 65},
    {"name": "Rock Slide",    "type": "Rock",     "power": 75,  "accuracy": 90},
    {"name": "Lick",          "type": "Ghost",    "power": 20,  "accuracy": 100},
]

TYPES = ["Normal", "Fire", "Water", "Grass", "Electric", "Ice", "Fighting",
         "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost"]

DIFFICULTIES = ["EASY", "MEDIUM", "HARD"]

# Campos que SOLO puede ver el evaluador.
_PRIVATE_KEYS = {"reference_action", "reference_scores", "best_vs_second_ratio", "difficulty"}


def _random_types(rng: random.Random, dual: bool) -> List[str]:
    return rng.sample(TYPES, 2) if dual else [rng.choice(TYPES)]


def candidate_case(rng: random.Random, difficulty: str, case_id: int) -> Dict:
    dual_player = difficulty == "HARD" and rng.random() < 0.50
    dual_enemy = difficulty == "HARD"
    player_types = _random_types(rng, dual_player)
    enemy_types = _random_types(rng, dual_enemy)

    moves = [dict(m) for m in rng.sample(MOVE_DB, 4)]
    rng.shuffle(moves)
    for move in moves:
        move["pp"] = rng.randint(5, 35)
    if difficulty == "HARD" and rng.random() < 0.30:
        rng.choice(moves)["pp"] = 0

    case = {
        "case_id": case_id,
        "difficulty": difficulty,
        "player_hp_percent": rng.randint(15, 100),
        "player_speed": rng.randint(20, 120),
        "player_types": player_types,
        "enemy_hp_percent": rng.randint(15, 100),
        "enemy_speed": rng.randint(20, 120),
        "enemy_types": enemy_types,
        "moves": moves,
    }
    return add_reference(case)


def difficulty_ok(case: Dict, difficulty: str) -> bool:
    scores = sorted(case["reference_scores"], reverse=True)
    if scores[0] <= 0 or abs(scores[0] - scores[1]) < 1e-6:
        return False
    ratio = case["best_vs_second_ratio"]
    if difficulty == "EASY":
        return ratio >= 1.80
    if difficulty == "MEDIUM":
        return 1.25 <= ratio < 1.80
    if difficulty == "HARD":
        return 1.01 <= ratio < 1.25
    return False


def split_counts(total: int) -> Dict[str, int]:
    base, rem = divmod(total, 3)
    counts = {d: base for d in DIFFICULTIES}
    for i in range(rem):
        counts[DIFFICULTIES[i]] += 1
    return counts


def generate_cases(total: int, seed: int) -> List[Dict]:
    """Misma logica que generate_cases() del D1."""
    rng = random.Random(seed)
    counts = split_counts(total)
    cases, next_id = [], 1
    for difficulty in DIFFICULTIES:
        made = attempts = 0
        while made < counts[difficulty]:
            attempts += 1
            if attempts > 50000:
                raise RuntimeError(f"No pude generar suficientes casos {difficulty}.")
            case = candidate_case(rng, difficulty, next_id)
            if not difficulty_ok(case, difficulty):
                continue
            cases.append(case)
            next_id += 1
            made += 1
    rng.shuffle(cases)
    return cases


def fresh_case(seed: int) -> Dict:
    """Un estado NUEVO para la demo, con dificultad al azar. Reproducible por semilla."""
    rng = random.Random(seed)
    difficulty = rng.choice(DIFFICULTIES)
    while True:
        case = candidate_case(rng, difficulty, case_id=0)
        if difficulty_ok(case, difficulty):
            return case


def public_view(case: Dict) -> Dict:
    """Lo que ve una estrategia: el estado de combate, sin respuesta ni dificultad."""
    return {k: v for k, v in case.items() if k not in _PRIVATE_KEYS}
