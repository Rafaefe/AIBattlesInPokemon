"""
demo.py -- el sistema de agentes en vivo: cada mensaje entre agentes se imprime
cuando ocurre, y al final se compara con B0 y S2 sobre el MISMO estado.

    python -m d3.demo                        # estado NUEVO, semilla del reloj (se imprime)
    python -m d3.demo --seed 482913          # reproduce exactamente un estado del video
    python -m d3.demo --replay orig:32       # un estado del conjunto de evaluacion
    python -m d3.demo --replay orig:32 --config no_verifier

La traza completa (prompts incluidos) queda en traces/demo_<estado>_<config>.json.
La respuesta correcta se calcula al final con la tabla verdadera, solo para juzgar.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict

from d2.demo import BAD, BOLD, DIM, END, _mark, _move_label
from d2.ground_truth import single_effectiveness
from d2.render import state_text
from d2.states import fresh_case, generate_cases, public_view
from d2.strategies import decomposed_words, direct
from d3.agents import CONFIGS, run_agents
from d3.evaluate import SETS

TRACE_DIR = Path("traces")
COLOR = {"coordinator": "\033[96m", "analyst": "\033[93m", "verifier": "\033[95m",
         "type_lookup": "\033[94m", "calculator": "\033[94m", "environment": "\033[97m"}


def _who(name: str) -> str:
    return f"{COLOR.get(name, '')}{name}{END}"


def print_message(m: Dict) -> None:
    c, head = m["content"], f"  {DIM}#{m['step']:>3}{END} {_who(m['from'])} -> {_who(m['to'])}"
    if m["kind"] == "llm":
        out = str(c["output"]).strip().replace("\n", " ")[:70]
        if c.get("probs") and set(c["probs"]) == {"yes", "no"}:
            out += f" (P(yes)={c['probs']['yes']:.2f})"
        print(f"  {DIM}#{m['step']:>3}   ({m['from']} piensa: {c['template']} -> {out!r}){END}")
    elif m["kind"] == "handoff" and "state" in c:
        print(f"{head}  [estado del combate]")
    elif m["kind"] == "tool_result" and m["from"] == "type_lookup":
        print(f"{head}  [{c['title']}] " + " | ".join(c["text"].splitlines()))
    elif m["kind"] == "tool_result":
        print(f"{head}  " + ", ".join(f"{r['action']}={r['score']}" for r in c))
    elif m["kind"] == "stop":
        print(f"{head}  {BOLD}PARADA: {c['action']}{END}")
    else:
        print(f"{head}  {json.dumps(c, ensure_ascii=False)}")


def show(llm, case: Dict, tag: str, header: str, config: str = "full") -> Dict:
    visible = public_view(case)
    print(f"{BOLD}{'=' * 78}\n{header}\n{'=' * 78}{END}")
    print(state_text(visible))

    print(f"\n{BOLD}[D3] SISTEMA DE AGENTES ({config}) - mensajes en vivo{END}")
    t0 = time.perf_counter()
    agents = run_agents(llm, visible, CONFIGS[config], keep_prompts=True, on_message=print_message)
    print(f"  accion          : {_move_label(visible, agents.strict_action)}   "
          f"{DIM}({agents.llm_calls} llamadas al modelo, {time.perf_counter() - t0:.1f}s){END}")

    print(f"\n{BOLD}[B0] BASELINE y [S2] SOLUCION D2, mismo estado{END}")
    base, sol = direct(llm, visible), decomposed_words(llm, visible)
    print(f"  B0              : {_move_label(visible, base.interpreted_action)}  (respuesta {base.raw!r})")
    print(f"  S2              : {_move_label(visible, sol.strict_action)}")

    reference = case["reference_action"]
    print(f"\n{BOLD}JUEZ (tabla Gen I verdadera, fuera del sistema){END}")
    print(f"  accion optima   : {_move_label(case, reference)}   scores {case['reference_scores']}")
    print(f"  B0 {_mark(base.interpreted_action == reference)}   S2 {_mark(sol.strict_action == reference)}   "
          f"D3 {_mark(agents.strict_action == reference)}")
    for f in agents.trace["facts"]:
        truth = single_effectiveness(f["attack"], f["defend"])
        if f["multiplier"] != truth:
            print(f"  {BAD}hecho erroneo{END}   : {f['move']} {f['attack']} -> {f['defend']}: el Analista dijo "
                  f"'{f['answer']}' (x{f['multiplier']:g}); en Gen I es x{truth:g}")

    TRACE_DIR.mkdir(exist_ok=True)
    path = TRACE_DIR / f"demo_{tag}_{config}.json"
    path.write_text(json.dumps({"state": tag, "config": config, "case": visible,
                                "reference_action": reference, "action": agents.strict_action,
                                "baseline_action": base.interpreted_action, "s2_action": sol.strict_action,
                                "facts": agents.trace["facts"], "prompts": agents.trace["prompts"],
                                "messages": agents.trace["messages"]}, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print(f"\n  {DIM}traza completa: {path}{END}")
    return {"agents": agents, "baseline": base, "solution": sol, "reference": reference}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--replay", default=None, help="conjunto:caso, p. ej. orig:32 o holdout:7")
    parser.add_argument("--config", default="full", choices=sorted(CONFIGS))
    parser.add_argument("--dtype", default=None)
    args = parser.parse_args()

    from d2.llm import HFModel
    llm = HFModel(args.model, dtype=args.dtype, prefix_cache=True)
    if args.replay:
        set_name, case_id = args.replay.split(":")
        case = next(c for c in generate_cases(50, SETS[set_name]) if c["case_id"] == int(case_id))
        show(llm, case, f"{set_name}{case_id}",
             f"CASO {case_id} DEL CONJUNTO {set_name} ({case['difficulty']})", args.config)
    else:
        seed = int(time.time() * 1000) % 1_000_000 if args.seed is None else args.seed
        show(llm, fresh_case(seed), f"seed{seed}",
             f"ESTADO NUEVO  |  semilla {seed}  |  (python -m d3.demo --seed {seed})", args.config)


if __name__ == "__main__":
    main()
