"""
tools.py -- las dos HERRAMIENTAS del sistema de agentes.

  type_lookup(query)   recuperacion sobre d3/kb/gen1_type_chart.md: devuelve la
                       seccion (un tipo ATACANTE) que mejor coincide con la consulta.
                       La consulta la escribe el Analista; si pide la seccion
                       equivocada, recibe la seccion equivocada.
  calculator(...)      la calculadora del D2 (d2/calculator.py), sin cambios.

La base de conocimiento es un TEXTO en lenguaje natural, separado del juez
(d2/ground_truth.py), que d3 nunca importa. Que el texto dice lo mismo que la
tabla del juez se comprueba en un test, no en ejecucion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from d2.calculator import base_power, best_move, expected_damage, stab

KB_PATH = Path(__file__).resolve().parent / "kb" / "gen1_type_chart.md"
_WORD = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class Passage:
    title: str          # "Electric-type attacks"
    attack_type: str    # "Electric"
    text: str           # cuatro lineas: A super effective / B not very effective / C no effect / D normal

    def line(self, label: str) -> str:
        return next((l for l in self.text.splitlines() if l.startswith(f"{label}.")), "")


def load_kb(path: Path = KB_PATH) -> List[Passage]:
    passages = []
    for block in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)[1:]:
        title, _, text = block.partition("\n")
        title = title.strip()
        lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
        passages.append(Passage(title, title.split("-")[0], "\n".join(lines)))
    return passages


class TypeLookup:
    """
    Recuperacion lexica sobre los TITULOS de seccion. Entre las secciones cuyo
    tipo aparece en la consulta gana la que aparece PRIMERO en ella
    ("Electric vs Ground" -> seccion Electric). Sin coincidencia: None.
    """

    name = "type_lookup"

    def __init__(self, passages: Optional[List[Passage]] = None):
        self.passages = passages or load_kb()
        self.calls = 0

    def __call__(self, query: str) -> Optional[Passage]:
        self.calls += 1
        words = _WORD.findall(query.lower())
        hits = [(words.index(p.attack_type.lower()), p) for p in self.passages
                if p.attack_type.lower() in words]
        return min(hits, key=lambda h: h[0])[1] if hits else None


def calculator(moves: List[Dict], player_types: List[str],
               effectiveness: Dict[int, Optional[float]]) -> List[Dict]:
    """
    Una fila por movimiento con su score. `effectiveness[i]` es el producto de los
    multiplicadores del Analista para el movimiento i (None = no se analizo).
    Un movimiento sin PP o sin analizar queda con score None (no elegible).
    """
    rows = []
    for i, move in enumerate(moves):
        eff = effectiveness.get(i)
        score = expected_damage(move, player_types, eff)
        rows.append({"action": f"MOVE_{i + 1}", "name": move["name"], "type": move["type"],
                     "power": move["power"], "accuracy": move["accuracy"], "pp": move["pp"],
                     "stab": stab(move, player_types), "effectiveness": eff,
                     "score": None if score == float("-inf") else round(score, 3),
                     "tie": base_power(move, player_types) if move["pp"] > 0 else float("-inf")})
    return rows


def calculator_best(rows: List[Dict]) -> Optional[str]:
    """La accion de mayor score segun la calculadora (empate: mayor potencia x precision x STAB)."""
    scores = [float("-inf") if r["score"] is None else r["score"] for r in rows]
    if max(scores) == float("-inf"):
        return None
    return rows[best_move(scores, tie_break=[r["tie"] for r in rows])]["action"]
