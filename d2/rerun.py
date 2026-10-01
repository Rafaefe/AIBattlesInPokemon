"""
rerun.py -- lo unico que hay que correr despues de la primera corrida.

    python -m d2.rerun

1. Muestra 8 hechos de tipos clasicos con el formato de S2, para ver de un
   vistazo si el modelo responde con sentido (es solo una vista previa: esos
   mismos hechos vuelven a salir, identicos, dentro de la evaluacion).
2. Corre S2 sobre los MISMOS 50 estados de results_d2/. Lo que ya estaba
   calculado (B0, A1, A2, A3, S1, S1+cal) no se repite.
3. Corre B0 y S2 sobre 50 estados NUEVOS (results_d2_holdout/), para confirmar
   el resultado fuera de los estados donde se diagnostico S1.
4. Escribe los reportes y las cifras del documento tecnico.

En CPU tarda del orden de 15-25 minutos; en una GPU, un par de minutos.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from d2.evaluate import DEFAULT_MODEL, DEFAULT_N, DEFAULT_SEED, HOLDOUT_SEED, HOLDOUT_STRATEGIES, run
from d2.ground_truth import single_effectiveness
from d2.parsing import parse_effect
from d2.report import build_report
from d2.strategies import fact_prompt_words

PREVIEW = [("Water", "Fire"), ("Electric", "Water"), ("Grass", "Water"), ("Fire", "Water"),
           ("Normal", "Rock"), ("Electric", "Ground"), ("Normal", "Ghost"), ("Normal", "Water")]


def preview(llm) -> int:
    print("\n1) Vista previa: 8 hechos de tipos con el formato de S2")
    ok = 0
    for atk, dfn in PREVIEW:
        answer = llm.generate(fact_prompt_words(atk, dfn), max_new_tokens=12)
        got, truth = parse_effect(answer), single_effectiveness(atk, dfn)
        ok += got == truth
        mark = "ok " if got == truth else "MAL"
        print(f"   [{mark}] {atk:>8} -> {dfn:<7} Gen I x{truth:<3g} | modelo: {answer!r:40} -> "
              f"{'no interpretable' if got is None else f'x{got:g}'}")
    print(f"   {ok}/8 correctos")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dtype", default=None)
    args = ap.parse_args()

    if not Path("results_d2/decisions.jsonl").exists():
        sys.exit("No encuentro results_d2/decisions.jsonl: corre este comando dentro de la carpeta del "
                 "repositorio, con la carpeta results_d2 de la primera corrida.")

    from d2.llm import HFModel
    t0 = time.time()
    llm = HFModel(args.model, dtype=args.dtype)
    preview(llm)

    print("\n2) S2 sobre los mismos 50 estados (results_d2/)")
    run(llm, n=DEFAULT_N, seed=DEFAULT_SEED, out="results_d2", strategies=["decomposed_words"])
    build_report("results_d2")

    print("\n3) B0 y S2 sobre 50 estados NUEVOS (results_d2_holdout/)")
    run(llm, n=DEFAULT_N, seed=HOLDOUT_SEED, out="results_d2_holdout", strategies=HOLDOUT_STRATEGIES)
    build_report("results_d2_holdout")

    print("\n4) Cifras del documento tecnico")
    subprocess.run([sys.executable, "report/fill_d2.py", "results_d2", "results_d2_holdout"], check=False)

    print("\n" + "=" * 70)
    for name, folder in [("50 estados originales", "results_d2"), ("50 estados nuevos", "results_d2_holdout")]:
        table = json.loads(Path(folder, "summary.json").read_text(encoding="utf-8"))["strategies"]
        line = " | ".join(f"{k}: {table[k]['acc_pct']}%" for k in
                          ["direct", "notype", "decomposed", "decomposed_words"] if k in table)
        print(f"{name:<22} {line}")
    print("=" * 70)
    print(f"Listo en {(time.time() - t0) / 60:.1f} min. Mandame las carpetas results_d2 y results_d2_holdout.")


if __name__ == "__main__":
    main()
