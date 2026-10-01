"""
demo.py -- baseline y solucion sobre el MISMO estado, lado a lado.

    python -m d2.demo                         # estado nuevo, semilla sacada del reloj (se imprime)
    python -m d2.demo --seed 482913           # reproduce un estado concreto
    python -m d2.demo --replay 17             # repite el estado 17 de results_d2/cases.json

El estado nuevo no se elige: la semilla sale del reloj y se muestra en pantalla,
asi cualquiera puede reproducir exactamente lo que se vio en el video.
La respuesta correcta se calcula al final, con la tabla verdadera, solo para juzgar.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Optional

from d2.ground_truth import add_reference, single_effectiveness
from d2.render import state_text
from d2.states import fresh_case, public_view
from d2.calculator import base_power, best_move
from d2.strategies import decomposed_words, direct

OK, BAD, BOLD, DIM, END = "\033[92m", "\033[91m", "\033[1m", "\033[2m", "\033[0m"


def _mark(good: bool) -> str:
    return f"{OK}CORRECTO{END}" if good else f"{BAD}INCORRECTO{END}"


def _move_label(case: Dict, action: Optional[str]) -> str:
    if not action:
        return "(sin accion valida)"
    m = case["moves"][int(action[-1]) - 1]
    return f"{action} = {m['name']} ({m['type']})"


def show(llm, case: Dict, header: str) -> Dict:
    visible = public_view(case)
    print(f"{BOLD}{'=' * 74}\n{header}\n{'=' * 74}{END}")
    print(state_text(visible))

    # ---------------- baseline
    print(f"\n{BOLD}[B0] BASELINE - prompt directo, una llamada{END}")
    t0 = time.perf_counter()
    base = direct(llm, visible)
    print(f"  respuesta cruda : {base.raw!r}")
    print(f"  accion          : {_move_label(visible, base.strict_action or base.interpreted_action)}"
          f"   {DIM}({time.perf_counter() - t0:.1f}s){END}")

    # ---------------- solucion
    print(f"\n{BOLD}[S2] SOLUCION - una pregunta de tipos a la vez + calculadora{END}")
    t0 = time.perf_counter()
    sol = decomposed_words(llm, visible)
    for row in sol.trace["moves"]:
        if row["pp"] <= 0:
            print(f"  {row['action']} {row['name']:<13} PP = 0 -> no se puede usar")
            continue
        for f in row["facts"]:
            said = f["answer"].strip().replace("\n", " ")[:38]
            print(f"  {row['action']} {row['name']:<13} {f['attack']:>8} vs {f['defend']:<8} "
                  f"modelo: {said!r:40} -> x{f['multiplier']:g}")
    print(f"\n  {'mov':<7}{'nombre':<14}{'pot.':>5}{'prec.':>6}{'STAB':>6}{'efect.':>8}{'score':>8}")
    for row in sol.trace["moves"]:
        eff = "-" if row["effectiveness"] is None else f"x{row['effectiveness']:g}"
        score = "-" if row["score"] is None else f"{row['score']:.1f}"
        print(f"  {row['action']:<7}{row['name']:<14}{row['power']:>5}{row['accuracy']:>5}%"
              f"{row['stab']:>6g}{eff:>8}{score:>8}")
    print(f"  accion          : {_move_label(visible, sol.strict_action)}   "
          f"{DIM}({sol.llm_calls} preguntas al modelo, {time.perf_counter() - t0:.1f}s){END}")

    # ---------------- juez
    reference = case["reference_action"]
    print(f"\n{BOLD}JUEZ (tabla Gen I verdadera, fuera del sistema){END}")
    print(f"  accion optima   : {_move_label(case, reference)}   scores {case['reference_scores']}")
    print(f"  baseline        : {_mark(base.interpreted_action == reference)}")
    print(f"  solucion        : {_mark(sol.strict_action == reference)}")
    notype = f"MOVE_{best_move([base_power(m, case['player_types']) for m in case['moves']]) + 1}"
    print(f"  {DIM}(referencia sin modelo, ignorando tipos: {_move_label(case, notype)} -> "
          f"{'correcto' if notype == reference else 'incorrecto'}){END}")
    wrong = [(f, row) for row in sol.trace["moves"] for f in row["facts"]
             if f["multiplier"] != single_effectiveness(f["attack"], f["defend"])]
    for f, row in wrong:
        print(f"  {BAD}hecho erroneo{END}   : {row['name']}: {f['attack']} -> {f['defend']} "
              f"el modelo dijo x{f['multiplier']:g}, en Gen I es "
              f"x{single_effectiveness(f['attack'], f['defend']):g}")
    return {"baseline": base, "solution": sol, "reference": reference}


def run_demo(llm, seed: Optional[int] = None) -> Dict:
    seed = int(time.time() * 1000) % 1_000_000 if seed is None else seed
    case = fresh_case(seed)
    return show(llm, case, f"ESTADO NUEVO  |  semilla {seed}  |  (python -m d2.demo --seed {seed})")


def replay(llm, case_id: int, results_dir: str = "results_d2") -> Dict:
    cases = json.loads((Path(results_dir) / "cases.json").read_text(encoding="utf-8"))
    case = next(c for c in cases if c["case_id"] == case_id)
    return show(llm, add_reference(dict(case)), f"CASO {case_id} DEL CONJUNTO DE EVALUACION ({case['difficulty']})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--replay", type=int, default=None)
    parser.add_argument("--results", default="results_d2")
    parser.add_argument("--dtype", default=None)
    args = parser.parse_args()

    from d2.llm import HFModel
    llm = HFModel(args.model, dtype=args.dtype)
    if args.replay is not None:
        replay(llm, args.replay, args.results)
    else:
        run_demo(llm, args.seed)


if __name__ == "__main__":
    main()
