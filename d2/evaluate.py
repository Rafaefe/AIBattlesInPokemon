"""
evaluate.py -- corre todas las estrategias sobre el MISMO conjunto de estados.

    python -m d2.evaluate                      # Qwen2.5-1.5B, 50 estados, todas las estrategias
    python -m d2.evaluate --n 50 --seed 20260830 --out results_d2
    python -m d2.evaluate --model microsoft/Phi-3.5-mini-instruct --dtype float16 --strategies direct,decomposed --out results_d2_phi

Escribe en --out:
    cases.json          los estados con su ground truth
    decisions.jsonl     una fila por (estrategia, estado); se reanuda si se corta
    run_meta.json       modelo, revision, GPU, versiones, tiempos
y al final llama a d2.report para escribir summary.md / summary.json.

El criterio de correccion es el del D1: la accion interpretada coincide con
reference_action (politica power x accuracy x STAB x efectividad).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from d2.calculator import best_move, expected_damage
from d2.ground_truth import type_effectiveness
from d2.states import generate_cases, public_view
from d2.strategies import LABELS, STRATEGIES, Decision

DEFAULT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
DEFAULT_N = 50
DEFAULT_SEED = 20260830            # misma semilla que el D1
ALL_STRATEGIES = ["direct", "structured", "permutation", "cot", "decomposed", "decomposed_cal",
                  "decomposed_words"]
# Conjunto NUEVO para confirmar la solucion final sin reutilizar los 50 estados donde se
# diagnostico S1. Semilla fijada el 27-09-2026, despues de disenar S2 y antes de correrlo.
HOLDOUT_SEED = 20260927
HOLDOUT_STRATEGIES = ["direct", "decomposed_words"]


def oracle_action(case: Dict) -> str:
    """La calculadora de la solucion alimentada con la tabla VERDADERA (chequeo, no resultado)."""
    scores = [expected_damage(m, case["player_types"],
                              type_effectiveness(m["type"], case["enemy_types"]))
              for m in case["moves"]]
    return f"MOVE_{best_move(scores) + 1}"


def score_row(case: Dict, d: Decision) -> Dict:
    reference = case["reference_action"]
    best = max(case["reference_scores"])
    chosen_score = regret = None
    if d.interpreted_action:
        chosen_score = case["reference_scores"][int(d.interpreted_action[-1]) - 1]
        regret = round((best - chosen_score) / best, 4) if best > 0 else None
    return {
        "case_id": case["case_id"],
        "difficulty": case["difficulty"],
        "strategy": d.strategy,
        "reference_action": reference,
        "raw_response": d.raw,
        "strict_action": d.strict_action or "",
        "interpreted_action": d.interpreted_action or "",
        "strict_valid": int(d.strict_action is not None),
        "interpretable": int(d.interpreted_action is not None),
        "decision_correct": int(d.interpreted_action == reference),
        "executable_correct": int(d.strict_action == reference),
        "chosen_score": chosen_score,
        "best_score": best,
        "regret": regret,
        "llm_calls": d.llm_calls,
        "seconds": round(d.seconds, 3),
        "trace": d.trace,
    }


def _load_done(path: Path) -> Dict:
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[(row["strategy"], row["case_id"])] = row
    return done


def run(llm, n: int = DEFAULT_N, seed: int = DEFAULT_SEED, out: str = "results_d2",
        strategies: Optional[Iterable[str]] = None, progress: bool = True) -> List[Dict]:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    strategies = list(strategies or ALL_STRATEGIES)

    cases = generate_cases(n, seed)
    for case in cases:                                   # chequeo de la herramienta
        assert oracle_action(case) == case["reference_action"], case["case_id"]
    (out_dir / "cases.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False),
                                        encoding="utf-8")

    decisions_path = out_dir / "decisions.jsonl"
    done = _load_done(decisions_path)
    started = time.time()

    try:
        from tqdm.auto import tqdm
    except ImportError:                                  # pragma: no cover
        tqdm = None

    with decisions_path.open("a", encoding="utf-8") as sink:
        for name in strategies:
            fn = STRATEGIES[name]
            todo = [c for c in cases if (name, c["case_id"]) not in done]
            iterator = todo
            if progress and tqdm is not None:
                iterator = tqdm(todo, desc=LABELS[name], unit="estado")
            elif progress:
                print(f"{LABELS[name]}: {len(todo)} estados")
            for case in iterator:
                decision = fn(llm, public_view(case))
                row = score_row(case, decision)
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()
                done[(name, case["case_id"])] = row

    meta_path = out_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    sessions = meta.get("sessions") or ([{k: meta[k] for k in ("strategies", "wall_clock_seconds_this_session",
                                                                  "finished_at") if k in meta}] if meta else [])
    described = llm.describe() if hasattr(llm, "describe") else {}
    sessions.append({"strategies": strategies,
                     "wall_clock_seconds": round(time.time() - started, 1),
                     "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "hardware": {k: described.get(k) for k in ("device", "gpu", "dtype", "torch")},
                     "llm_calls": dict(getattr(llm, "calls", {}))})
    meta.pop("wall_clock_seconds_this_session", None)     # formato antiguo: ya queda en sessions[0]
    meta.pop("finished_at", None)
    meta.update({
        "n_states": n,
        "seed": seed,
        "difficulty_split": {d: sum(c["difficulty"] == d for c in cases)
                             for d in ["EASY", "MEDIUM", "HARD"]},
        "strategies": sorted({row["strategy"] for row in done.values()},
                             key=lambda s: ALL_STRATEGIES.index(s) if s in ALL_STRATEGIES else 99),
        "sessions": sessions,
        "oracle_check": "calculator + true type chart reproduces the reference action on all states",
    })
    if described:
        described = {k: v for k, v in described.items() if k != "calls"}
        meta["model"] = {**meta.get("model", {}), **described}   # hardware de la ULTIMA sesion
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return [done[(s, c["case_id"])] for s in strategies for c in cases]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default="results_d2")
    parser.add_argument("--strategies", default=",".join(ALL_STRATEGIES))
    parser.add_argument("--dtype", default=None, help="float32 / float16 / bfloat16 (por defecto: automatico)")
    parser.add_argument("--holdout", action="store_true",
                        help="conjunto nuevo (semilla HOLDOUT_SEED) con B0 y la solucion -> results_d2_holdout")
    args = parser.parse_args()

    from d2.llm import HFModel
    from d2.report import build_report

    llm = HFModel(args.model, dtype=args.dtype)
    if args.holdout:
        run(llm, n=args.n, seed=HOLDOUT_SEED, out="results_d2_holdout", strategies=HOLDOUT_STRATEGIES)
        print(build_report("results_d2_holdout"))
        return
    run(llm, n=args.n, seed=args.seed, out=args.out,
        strategies=[s.strip() for s in args.strategies.split(",") if s.strip()])
    print(build_report(args.out))


if __name__ == "__main__":
    main()
