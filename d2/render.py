"""render.py -- como se le muestra el estado al modelo (identico al D1)."""

from __future__ import annotations

from typing import Dict


def state_text(case: Dict) -> str:
    moves = [
        f"MOVE_{i}: {m['name']} | Type={m['type']} | Power={m['power']} | "
        f"Accuracy={m['accuracy']}% | PP={m['pp']}"
        for i, m in enumerate(case["moves"], start=1)
    ]
    return (
        "PLAYER\n"
        f"HP: {case['player_hp_percent']}%\n"
        f"Types: {'/'.join(case['player_types'])}\n"
        f"Speed: {case['player_speed']}\n\n"
        "OPPONENT\n"
        f"HP: {case['enemy_hp_percent']}%\n"
        f"Types: {'/'.join(case['enemy_types'])}\n"
        f"Speed: {case['enemy_speed']}\n\n"
        "AVAILABLE MOVES\n" + "\n".join(moves)
    )


def move_short(move: Dict) -> str:
    return (f"{move['name']};{move['type']};P{move['power']};"
            f"A{move['accuracy']};PP{move['pp']}")
