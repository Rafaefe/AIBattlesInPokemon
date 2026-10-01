"""
parsing.py -- parsers de salida.

strict_parse y semantic_parse son los mismos del Deliverable 1, para que el
criterio de "respuesta valida" no cambie entre entregas.
"""

from __future__ import annotations

import re
from typing import Dict, Optional


def strict_parse(raw: str, case: Dict) -> Optional[str]:
    """Exactamente MOVE_1..MOVE_4 (con puntuacion final opcional) y con PP > 0."""
    match = re.fullmatch(r"\s*MOVE_([1-4])\s*[.!]?\s*", raw.upper())
    if not match:
        return None
    idx = int(match.group(1)) - 1
    return f"MOVE_{idx + 1}" if case["moves"][idx]["pp"] > 0 else None


def _normalize(text: str) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", text.upper())
    return " ".join(text.split())


def semantic_parse(raw: str, case: Dict) -> Optional[str]:
    """Intencion recuperable: 'move 2' o un nombre de movimiento inequivoco."""
    strict = strict_parse(raw, case)
    if strict:
        return strict
    normalized = _normalize(raw)
    relaxed = re.search(r"\bMOVE\s*([1-4])\b", normalized)
    if relaxed:
        idx = int(relaxed.group(1)) - 1
        if case["moves"][idx]["pp"] > 0:
            return f"MOVE_{idx + 1}"
    found = []
    for i, move in enumerate(case["moves"], start=1):
        if move["pp"] <= 0:
            continue
        name = _normalize(move["name"])
        if name and re.search(rf"\b{re.escape(name)}\b", normalized):
            found.append(f"MOVE_{i}")
    found = list(dict.fromkeys(found))
    return found[0] if len(found) == 1 else None


def final_line_parse(raw: str, case: Dict) -> Optional[str]:
    """Para chain-of-thought: la ultima linea 'FINAL: MOVE_N', con PP > 0."""
    matches = re.findall(r"FINAL\s*[:\-]?\s*\**\s*MOVE[_ ]?([1-4])", raw.upper())
    if not matches:
        return None
    idx = int(matches[-1]) - 1
    return f"MOVE_{idx + 1}" if case["moves"][idx]["pp"] > 0 else None


def final_line_semantic(raw: str, case: Dict) -> Optional[str]:
    """
    Para chain-of-thought, version interpretable: el texto despues del ultimo
    'FINAL' puede traer la etiqueta o el NOMBRE del movimiento ('FINAL: THUNDERBOLT').
    Mismo criterio que semantic_parse del D1, aplicado solo a la linea final.
    """
    strict = final_line_parse(raw, case)
    if strict:
        return strict
    upper = raw.upper()
    pos = upper.rfind("FINAL")
    if pos < 0:
        return None
    tail = raw[pos + len("FINAL"):].split("\n")[0] if raw[pos + len("FINAL"):].strip() else ""
    return semantic_parse(tail, case) if tail.strip(" :*-") else None


# Respuesta en palabras de la solucion S2 -> multiplicador. Se usa la PRIMERA
# expresion reconocible del texto (el modelo a veces agrega una explicacion).
_EFFECT_PATTERNS = [
    (r"super[\s-]*effective|\bdouble\b|\b2\s*x\b|\bx\s*2\b", 2.0),
    (r"not\s+very\s+effective|not\s+effective|\bresist|\bhalf\b|\b0\.5\b", 0.5),
    (r"\bno\s+effect|doesn'?t\s+affect|does\s+not\s+affect|\bimmune|\bno\s+damage|\b0\s*x\b|\bzero\b", 0.0),
    # "normal" solo como grado de dano, no como el TIPO Normal ("Normal-type").
    (r"\bnormal\b(?!\s*-?\s*type)|\bneutral\b|\bregular\b|\bstandard\b|\b1\s*x\b", 1.0),
]


def parse_effect(text: str) -> Optional[float]:
    """'super effective' -> 2, 'not very effective' -> 0.5, 'no effect' -> 0, 'normal damage' -> 1."""
    lowered = text.lower()
    best = None
    for pattern, value in _EFFECT_PATTERNS:
        m = re.search(pattern, lowered)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), value)
    return None if best is None else best[1]
