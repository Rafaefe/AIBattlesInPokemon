"""
calculator.py -- la HERRAMIENTA de la solucion.

Hace solo aritmetica sobre datos visibles en el estado (potencia, precision,
PP, tipos del jugador) y sobre la efectividad que le entrega el modelo. No
conoce la tabla de tipos: si la efectividad viene mal, el resultado viene mal.
"""

from __future__ import annotations

from typing import Dict, List, Optional


def stab(move: Dict, player_types: List[str]) -> float:
    return 1.5 if move["type"] in player_types else 1.0


def expected_damage(move: Dict, player_types: List[str], effectiveness: Optional[float]) -> float:
    """power x (accuracy/100) x STAB x effectiveness; un movimiento sin PP no se puede usar."""
    if move["pp"] <= 0 or effectiveness is None:
        return float("-inf")
    return move["power"] * (move["accuracy"] / 100.0) * stab(move, player_types) * effectiveness


def best_move(scores: List[float], tie_break: Optional[List[float]] = None) -> int:
    """
    Indice del maximo. Si hay empate exacto y se entrega `tie_break`, desempata
    con ese valor; si no, gana el primero (misma regla que la politica de referencia).
    """
    keys = tie_break or [0.0] * len(scores)
    return max(range(len(scores)), key=lambda i: (scores[i], keys[i], -i))


def base_power(move: Dict, player_types: List[str]) -> float:
    """power x (accuracy/100) x STAB: todo lo que se sabe de un movimiento SIN mirar tipos."""
    return expected_damage(move, player_types, 1.0)
