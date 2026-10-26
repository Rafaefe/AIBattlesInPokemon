"""
evaluate.py -- baseline, solucion del D2, sistema de agentes y sus ablaciones,
sobre los MISMOS estados y con el MISMO criterio de correccion del D1/D2.

    python -m d3.evaluate                     # 100 estados (50 originales + 50 nuevos del D2)
    python -m d3.evaluate --sets orig --systems direct,agents_full --n 5     # prueba corta

Conjuntos (los dos del D2, sin cambios):
    orig      semilla 20260830 (los 50 del D1/D2)
    holdout   semilla 20260927 (los 50 nuevos del D2)

Sistemas:
    direct              B0  prompt directo (baseline)
    decomposed_words    S2  solucion del D2
    agents_full         D3  sistema de agentes completo
    agents_no_*         D3  sin una tecnica (ver d3/agents.py: CONFIGS)
    (H, la calculadora que ignora los tipos, la agrega d2.report sin modelo)

Escribe en results_d3/<conjunto>/:
    cases.json, decisions.jsonl (una fila por sistema y estado; se reanuda),
    traces/<sistema>.jsonl (TODOS los mensajes entre agentes, uno por estado),
    run_meta.json; y al final summary.md / summary.json (d3.report).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Iterable, List

from d2.evaluate import DEFAULT_MODEL, HOLDOUT_SEED, oracle_action, score_row
from d2.states import generate_cases, public_view
from d2.strategies import STRATEGIES
from d3.agents import CONFIGS, run_agents

SETS = {"orig": 20260830, "holdout": HOLDOUT_SEED}
ALL_SYSTEMS = ["direct", "decomposed_words"] + [f"agents_{c}" for c in CONFIGS]
OUT = Path("results_d3")


def decide(llm, name: str, case: Dict, keep_prompts: bool = False):
    if name.startswith("agents_"):
        return run_agents(llm, case, CONFIGS[name[len("agents_"):]], keep_prompts=keep_prompts)
    return STRATEGIES[name](llm, case)


def _done(path: Path) -> set:
    if not path.exists():
        return set()
    return {(r["strategy"], r["case_id"]) for r in
            (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip())}


def run(llm, set_name: str, n: int = 50, systems: Iterable[str] = ALL_SYSTEMS,
        out: Path = OUT, progress: bool = True) -> Path:
    out_dir = Path(out) / set_name
    (out_dir / "traces").mkdir(parents=True, exist_ok=True)
    cases = generate_cases(n, SETS[set_name])
    for case in cases:
        assert oracle_action(case) == case["reference_action"], case["case_id"]
    (out_dir / "cases.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")

    decisions = out_dir / "decisions.jsonl"
    done = _done(decisions)
    started = time.time()
    try:
        from tqdm.auto import tqdm
    except ImportError:                                   # pragma: no cover
        tqdm = None
    with decisions.open("a", encoding="utf-8") as sink:
        for name in systems:
            todo = [c for c in cases if (name, c["case_id"]) not in done]
            it = tqdm(todo, desc=f"{set_name}:{name}", unit="estado") if (progress and tqdm) else todo
            with (out_dir / "traces" / f"{name}.jsonl").open("a", encoding="utf-8") as traces:
                for case in it:
                    d = decide(llm, name, public_view(case))
                    row = score_row(case, d)
                    messages = row["trace"].pop("messages", None)
                    if messages is not None:
                        traces.write(json.dumps({"case_id": case["case_id"], "system": name,
                                                 "action": d.interpreted_action,
                                                 "reference_action": case["reference_action"],
                                                 "messages": messages}, ensure_ascii=False) + "\n")
                    sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                    sink.flush()

    meta_path = out_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"sessions": []}
    described = llm.describe() if hasattr(llm, "describe") else {}
    meta["sessions"].append({"systems": list(systems), "wall_clock_seconds": round(time.time() - started, 1),
                             "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "llm_calls": dict(getattr(llm, "calls", {}))})
    meta.update({"set": set_name, "seed": SETS[set_name], "n_states": n,
                 "model": {k: v for k, v in described.items() if k != "calls"} or meta.get("model")})
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dtype", default=None)
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--sets", default="orig,holdout")
    parser.add_argument("--systems", default=",".join(ALL_SYSTEMS))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    from d2.llm import HFModel
    from d3.report import build_report

    llm = HFModel(args.model, dtype=args.dtype, prefix_cache=True)
    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    for set_name in [s.strip() for s in args.sets.split(",") if s.strip()]:
        run(llm, set_name, n=args.n, systems=systems, out=Path(args.out))
    print(build_report(args.out))


if __name__ == "__main__":
    main()
