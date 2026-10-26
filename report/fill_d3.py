"""
fill_d3.py -- escribe report/d3_numbers.tex a partir de results_d3/summary.json.

Todas las cifras del documento tecnico del D3 salen de aqui: cada numero del PDF
se rastrea hasta los archivos del repositorio.

    python -m d3.report results_d3            # (re)genera summary.json
    python report/fill_d3.py results_d3
    python report/fill_d3.py --placeholder    # plantilla con '??' (antes de correr)

Luego:  cd report && pdflatex deliverable3_es.tex  (dos veces)
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"direct": "Base", "notype": "Heur", "decomposed_words": "Stwo", "agents_full": "Full",
        "agents_no_rag": "NoRag", "agents_no_fewshot": "NoFew", "agents_no_verifier": "NoVer",
        "agents_no_decomposition": "NoDec", "agents_no_ranking": "NoRank"}
GROUPS = {"orig": "O", "holdout": "H", "all": "A"}
Q = "\\ph{??}"


def num(x, d=1) -> str:
    return "--" if x is None else f"{x:.{d}f}".replace(".", "{,}")


def pval(p) -> str:
    if p is None:
        return "--"
    if p >= 0.001:
        return num(p, 3)
    exp = math.floor(math.log10(p))
    return f"{num(p / 10 ** exp, 1)}\\times10^{{{exp}}}"


def esc(s: str) -> str:
    return (str(s).replace("\\", "").replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")
            .replace("#", "\\#").replace("$", "").replace("{", "").replace("}", "").replace("~", ""))


def macros(summary: dict) -> dict:
    m = {}
    for g, gk in GROUPS.items():
        table = summary["tables"].get(g, {})
        for s, sk in KEYS.items():
            t = table.get(s)
            m[f"acc{sk}{gk}"] = num(t["acc_pct"]) if t else "--"
            m[f"ci{sk}{gk}"] = f"{t['acc_ci95'][0]:.0f}--{t['acc_ci95'][1]:.0f}" if t else "--"
    for s, sk in KEYS.items():
        t = summary["tables"]["all"].get(s)
        m[f"calls{sk}"] = num(t["llm_calls_per_state"]) if t else "--"
        m[f"chiP{sk}"] = pval(t["chi2_p"]) if t else "--"
    comps = summary["comparisons"]["all"]

    def find(a, b):
        return next((c for c in comps if c["a"] == a and c["b"] == b), None)

    for s, sk in KEYS.items():
        c = find(s, "direct")
        m[f"win{sk}"], m[f"loss{sk}"], m[f"p{sk}"] = ((str(c["a_right_b_wrong"]), str(c["b_right_a_wrong"]),
                                                     pval(c["p_value"])) if c else ("--", "--", "--"))
        c = find("agents_full", s)                          # contribucion: completo vs sin la tecnica
        m[f"gain{sk}"], m[f"drop{sk}"], m[f"pFull{sk}"] = ((str(c["a_right_b_wrong"]), str(c["b_right_a_wrong"]),
                                                           pval(c["p_value"])) if c else ("--", "--", "--"))
    a = summary["agents"].get("agents_full", {})
    for k, mk in [("facts_right_pct", "factsRight"), ("always_x1_right_pct", "alwaysOne"),
                  ("lookup_pct", "lookupPct"), ("right_section_pct", "rightSection")]:
        m[mk] = num(a.get(k))
    for k, mk in [("facts", "nFacts"), ("facts_revised", "nRevised"), ("facts_unverified", "nUnverified"),
                  ("states_plan_missed_a_move", "nPlanMissed"),
                  ("states_final_differs_from_calculator", "nDeviated")]:
        m[mk] = str(a.get(k, "--"))
    for s in ("agents_no_rag", "agents_no_fewshot"):
        m[f"factsRight{KEYS[s]}"] = num(summary["agents"].get(s, {}).get("facts_right_pct"))
    eff = summary.get("revision_effect") or {}
    m["loopFixed"], m["loopBroken"] = str(eff.get("facts_fixed_by_loop", "--")), str(eff.get("facts_broken_by_loop", "--"))
    wbd = summary.get("wrong_by_defender", {}).get("agents_full", {})
    m["nWrongFull"] = str(sum(wbd.values()))
    m["nWrongWater"] = str(wbd.get("Water", 0))
    m["nWrongNoFew"] = str(sum(summary.get("wrong_by_defender", {}).get("agents_no_fewshot", {}).values()))
    fails = summary.get("failures_full", [])
    m["nFail"] = str(len(fails))
    causes = {}
    for f in fails:
        causes[f["cause"]] = causes.get(f["cause"], 0) + 1
    m["failCauses"] = esc("; ".join(f"{v} {k}" for k, v in sorted(causes.items(), key=lambda x: -x[1]))) or "--"
    if fails:
        f = fails[0]
        m.update({"fcId": esc(f["case_id"]), "fcDiff": f["difficulty"], "fcChosen": esc(f["chosen"]),
                  "fcRef": esc(f["reference"]), "fcRegret": num(100 * (f["regret"] or 0), 0),
                  "fcCause": esc(f["cause"]), "fcFacts": esc("; ".join(f["wrong_facts"])) or "--"})
    else:
        m.update({k: "--" for k in ("fcId", "fcDiff", "fcChosen", "fcRef", "fcRegret", "fcCause", "fcFacts")})
    model = summary.get("model") or {}
    m["modelId"] = esc(model.get("model_id", "Qwen/Qwen2.5-1.5B-Instruct"))
    # transformers >= 5.20 ya no expone el commit del snapshot (revision = None en run_meta)
    m["modelRev"] = esc(str(model["revision"])[:10]) if model.get("revision") else "n/d"
    m["nParams"] = num((model.get("n_params") or 1.54e9) / 1e9, 2)
    m["hw"] = esc(f"{model.get('gpu') or model.get('device', '')}, {str(model.get('dtype', '')).replace('torch.', '')}")
    m["libs"] = esc(f"torch {model.get('torch', '?')}, transformers {model.get('transformers', '?')}")
    m["nAll"] = str(sum(v["n_states"] for v in summary["sets"].values()))
    return m


def write(m: dict, path: Path) -> None:
    lines = ["% GENERADO por report/fill_d3.py -- no editar a mano."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(m.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?", default="results_d3")
    ap.add_argument("--placeholder", action="store_true")
    args = ap.parse_args()
    out = ROOT / "report" / "d3_numbers.tex"
    if args.placeholder:
        empty = {"tables": {"all": {}}, "comparisons": {"all": []}, "agents": {}, "sets": {}}
        write({k: Q for k in macros(empty)}, out)
    else:
        write(macros(json.loads((ROOT / args.results / "summary.json").read_text(encoding="utf-8"))), out)
    print(f"escrito {out}")


if __name__ == "__main__":
    main()
