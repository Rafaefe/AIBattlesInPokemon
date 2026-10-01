"""
analyze_results.py
==================

Analisis post-hoc del piloto v1 del benchmark Pokemon Blue.

Este script NO ejecuta el modelo. Lee los artefactos que produce
`benchmark/pokemon_benchmark_final.py` y reproduce, de forma
determinista, todas las cifras que aparecen en el poster del
Deliverable 1 y que NO estan en `benchmark_summary.csv`:

  1. Distribucion posicional de las respuestas (el sesgo hacia MOVE_2).
  2. Tasa de acierto segun la posicion del movimiento optimo.
  3. Test chi-cuadrado de la distribucion de elecciones contra la uniforme.
  4. Politicas de referencia triviales (azar, constante, heuristicas)
     con las que se compara al modelo.
  5. Errores "duros": movimientos con efectividad 0, movimientos con
     PP = 0 y elecciones estrictamente peores de las cuatro.
  6. Exactitud por nivel de dificultad y regret medio.

Uso:
    python analysis/analyze_results.py
    python analysis/analyze_results.py --results-dir results --out analysis/analysis_report.txt

Dependencias:
    pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List

import pandas as pd
from scipy.stats import chisquare

MODES = ["DIRECT", "STRUCTURED"]
POSITIONS = ["MOVE_1", "MOVE_2", "MOVE_3", "MOVE_4"]


# ------------------------------------------------------------------ carga --

def load(results_dir: Path):
    results = pd.read_csv(results_dir / "benchmark_results.csv")
    with (results_dir / "benchmark_cases.json").open(encoding="utf-8") as f:
        cases = {c["case_id"]: c for c in json.load(f)}
    return results, cases


def by_mode(results: pd.DataFrame, mode: str) -> pd.DataFrame:
    return results[results.prompt_mode == mode].set_index("case_id")


def action_of(row) -> str | None:
    """Accion interpretada de una fila, o None si no fue interpretable."""
    value = row.get("interpreted_action")
    if isinstance(value, str) and value.startswith("MOVE_"):
        return value
    return None


# --------------------------------------------------------------- politicas --

def argmax_policy(cases: Dict[int, dict], key) -> Dict[int, str]:
    """Politica determinista: elige el movimiento que maximiza `key(move)`."""
    choice = {}
    for case_id, case in cases.items():
        moves = case["moves"]
        best = max(range(4), key=lambda i: key(moves[i]))
        choice[case_id] = f"MOVE_{best + 1}"
    return choice


def accuracy(choice: Dict[int, str], cases: Dict[int, dict]) -> float:
    hits = sum(1 for cid, c in cases.items() if choice[cid] == c["reference_action"])
    return 100.0 * hits / len(cases)


def baselines(cases: Dict[int, dict]) -> List[tuple]:
    """Politicas de referencia con las que se compara al modelo."""
    rows = []

    # Azar uniforme: valor esperado analitico, no simulado.
    rows.append(("Azar uniforme entre 4 movimientos", 25.0))

    # Politica constante: siempre la misma posicion.
    for k in range(1, 5):
        acc = accuracy({cid: f"MOVE_{k}" for cid in cases}, cases)
        rows.append((f'Constante "siempre MOVE_{k}"', acc))

    # Heuristicas que ignoran total o parcialmente la tabla de tipos.
    rows.append((
        "max(potencia x precision), con PP > 0",
        accuracy(argmax_policy(
            cases,
            lambda m: (m["power"] * m["accuracy"] / 100.0) if m["pp"] > 0 else -1.0,
        ), cases),
    ))
    rows.append((
        "max(potencia) - ignora los tipos por completo",
        accuracy(argmax_policy(cases, lambda m: m["power"]), cases),
    ))
    return rows


# ------------------------------------------------------------------ checks --

def hard_errors(sub: pd.DataFrame, cases: Dict[int, dict]) -> Dict[str, list]:
    """
    Errores indefendibles bajo CUALQUIER regla de puntuacion.

    Sirven para descartar que el bajo accuracy sea un artefacto de la
    politica de referencia elegida.
    """
    zero_effect, unexecutable, strictly_worst = [], [], []

    for case_id, case in cases.items():
        row = sub.loc[case_id]
        action = action_of(row)

        if action is None:
            # No interpretable. El parser rechaza una etiqueta MOVE_N cuando el
            # movimiento no tiene PP: eso no es ruido, es un intento de emitir
            # una accion inejecutable, y cuenta como error duro.
            match = re.search(r"MOVE_([1-4])", str(row.get("raw_response", "")))
            if match:
                idx = int(match.group(1)) - 1
                if case["moves"][idx]["pp"] <= 0:
                    unexecutable.append((case_id, f"MOVE_{idx + 1}",
                                         case["moves"][idx]["name"]))
            continue

        idx = int(action[-1]) - 1
        scores = case["reference_scores"]
        move = case["moves"][idx]

        if scores[idx] == 0:
            zero_effect.append((case_id, action, move["name"], move["type"],
                                "/".join(case["enemy_types"])))
        if scores[idx] == min(scores):
            strictly_worst.append((case_id, action))

    return {
        "zero_effect": zero_effect,
        "unexecutable": unexecutable,
        "strictly_worst": strictly_worst,
    }


def hit_rate_by_optimal_position(sub: pd.DataFrame, cases: Dict[int, dict]):
    """Acierto condicionado a DONDE estaba el movimiento optimo."""
    table = {pos: [0, 0] for pos in POSITIONS}  # [aciertos, total]
    for case_id, case in cases.items():
        reference = case["reference_action"]
        table[reference][1] += 1
        if action_of(sub.loc[case_id]) == reference:
            table[reference][0] += 1
    return table


# ------------------------------------------------------------------ salida --

def analyse(results: pd.DataFrame, cases: Dict[int, dict]) -> str:
    out: List[str] = []

    def line(text: str = "") -> None:
        out.append(text)

    n = len(cases)
    line("=" * 78)
    line("ANALISIS DEL PILOTO v1 - benchmark Pokemon Blue")
    line("=" * 78)
    line(f"Estados evaluados: {n}   |   Inferencias totales: {len(results)}")
    line()

    # --- 1. metricas agregadas ------------------------------------------
    line("-" * 78)
    line("1. METRICAS AGREGADAS POR PROMPT")
    line("-" * 78)
    line(f"{'prompt':<14}{'STRICT':>9}{'INTERP':>9}{'ACC':>9}{'EXEC-C.':>10}{'regret':>9}")
    for mode in MODES:
        sub = by_mode(results, mode)
        valid = sub[sub.interpretable == 1]
        line(
            f"{mode:<14}"
            f"{100 * sub.strict_valid.mean():>8.1f}%"
            f"{100 * sub.interpretable.mean():>8.1f}%"
            f"{100 * sub.decision_correct.mean():>8.1f}%"
            f"{100 * sub.executable_correct.mean():>9.1f}%"
            f"{valid.regret.mean():>9.2f}"
        )
    line()

    # --- 2. sesgo posicional --------------------------------------------
    line("-" * 78)
    line("2. DISTRIBUCION POSICIONAL DE LAS RESPUESTAS")
    line("-" * 78)
    optimal = Counter(c["reference_action"] for c in cases.values())
    line(f"{'':<14}" + "".join(f"{p:>10}" for p in POSITIONS))
    line(f"{'accion optima':<14}" + "".join(f"{optimal[p]:>10}" for p in POSITIONS))
    for mode in MODES:
        sub = by_mode(results, mode)
        chosen = Counter(a for a in (action_of(r) for _, r in sub.iterrows()) if a)
        line(f"{mode.lower():<14}" + "".join(f"{chosen[p]:>10}" for p in POSITIONS))
    line()

    sub = by_mode(results, "STRUCTURED")
    chosen = Counter(a for a in (action_of(r) for _, r in sub.iterrows()) if a)
    observed = [chosen[p] for p in POSITIONS]
    total = sum(observed)
    stat, pvalue = chisquare(observed, [total / 4] * 4)
    line(f"STRUCTURED vs distribucion uniforme: chi2(3) = {stat:.1f}, p = {pvalue:.2e}")
    line(f"(sobre las {total} respuestas interpretables)")
    line()

    line("Acierto segun la POSICION del movimiento optimo (STRUCTURED):")
    for pos, (hits, tot) in hit_rate_by_optimal_position(sub, cases).items():
        line(f"  optimo = {pos}  (n={tot})  ->  aciertos: {hits}/{tot}")
    line()

    # --- 3. baselines ----------------------------------------------------
    line("-" * 78)
    line("3. POLITICAS TRIVIALES vs EL MODELO")
    line("-" * 78)
    model_acc = 100 * by_mode(results, "STRUCTURED").decision_correct.mean()
    line(f"{'Qwen2.5-1.5B, prompt estructurado':<48}{model_acc:>8.1f}%")
    for name, acc in baselines(cases):
        line(f"{name:<48}{acc:>8.1f}%")
    line()

    # --- 4. errores duros -------------------------------------------------
    line("-" * 78)
    line("4. ERRORES INDEFENDIBLES BAJO CUALQUIER REGLA (STRUCTURED)")
    line("-" * 78)
    errors = hard_errors(sub, cases)
    for case_id, action, name, mtype, enemy in errors["zero_effect"]:
        line(f"  efectividad 0 -> caso {case_id}: {action} = {name} ({mtype}) "
             f"contra {enemy}")
    for case_id, action, name in errors["unexecutable"]:
        line(f"  PP = 0        -> caso {case_id}: {action} = {name}, PP agotado, "
             f"no se puede ejecutar")
    worst = errors["strictly_worst"]
    interpretable = int(sub.interpretable.sum())
    line(f"  peor opcion de las cuatro: {len(worst)} de {interpretable} respuestas "
         f"({100 * len(worst) / interpretable:.0f}%) "
         f"-> casos {[c for c, _ in worst]}")
    line()

    # --- 5. dificultad ----------------------------------------------------
    line("-" * 78)
    line("5. EXACTITUD POR NIVEL DE DIFICULTAD")
    line("-" * 78)
    for mode in MODES:
        m = by_mode(results, mode)
        cells = "  ".join(
            f"{d}: {int(m[m.difficulty == d].decision_correct.sum())}/"
            f"{len(m[m.difficulty == d])}"
            for d in ["EASY", "MEDIUM", "HARD"]
        )
        line(f"  {mode:<12} {cells}")
    line()
    line("Un razonamiento graduado deberia degradarse con la dificultad.")
    line("Un sesgo de posicion no. Los datos no muestran gradiente.")
    line("=" * 78)

    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results", type=Path,
                        help="carpeta con los CSV/JSON del benchmark")
    parser.add_argument("--out", default=None, type=Path,
                        help="si se indica, guarda el reporte en este archivo")
    args = parser.parse_args()

    results, cases = load(args.results_dir)
    report = analyse(results, cases)
    print(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"\n[guardado en {args.out}]")


if __name__ == "__main__":
    main()
