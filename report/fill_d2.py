"""
fill_d2.py -- escribe report/d2_numbers.tex a partir de los resultados.

Todas las cifras (y las frases que dependen de ellas) del documento tecnico
salen de aqui, asi que cada numero del PDF se rastrea hasta el repositorio.

    python report/fill_d2.py results_d2 results_d2_holdout
    python report/fill_d2.py --placeholder              # plantilla con '??'

Luego:  cd report && pdflatex deliverable2_es.tex  (dos veces)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from d2.calculator import expected_damage  # noqa: E402
from d2.ground_truth import MODERN_VALUES, single_effectiveness  # noqa: E402

KEYS = {"direct": "Base", "structured": "Struct", "permutation": "Perm", "cot": "Cot",
        "decomposed": "Sone", "decomposed_cal": "Scal", "notype": "Heur", "decomposed_words": "Stwo"}
POS = ["MOVE_1", "MOVE_2", "MOVE_3", "MOVE_4"]
Q = "\\ph{??}"


def num(x, d=1) -> str:
    if x is None:
        return "--"
    return f"{x:.{d}f}".replace(".", "{,}")


def mult(x) -> str:
    return {2.0: "2", 1.0: "1", 0.5: "0{,}5", 0.0: "0"}.get(x, num(x, 2))


def pval(p) -> str:
    if p is None:
        return "--"
    if p >= 0.001:
        return num(p, 3)
    exp = math.floor(math.log10(p))
    return f"{num(p / 10 ** exp, 1)}\\times10^{{{exp}}}"


def coords(counts: dict) -> str:
    return "".join(f"(MOVE\\_{i + 1},{counts.get(p, 0)})" for i, p in enumerate(POS))


def esc(s: str) -> str:
    return (s.replace("\\", "").replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")
             .replace("#", "\\#").replace("$", "").replace("{", "").replace("}", "").replace("~", ""))


def paired(summary: dict, a: str, b: str):
    for key in ("paired_tests_vs_baseline", "paired_tests_solution_vs_alternatives"):
        for t in summary.get(key, []):
            if (t["a"], t["b"]) == (a, b):
                return t["a_right_b_wrong"], t["b_right_a_wrong"], t["p_value"]
            if (t["a"], t["b"]) == (b, a):
                return t["b_right_a_wrong"], t["a_right_b_wrong"], t["p_value"]
    return None


def hw_text(h: dict) -> str:
    dev = h.get("gpu") or ("CPU" if h.get("device") == "cpu" else h.get("device") or "??")
    return f"{dev}, {str(h.get('dtype', '')).replace('torch.', '')}"


def hw_note(meta: dict) -> str:
    """Si alguna sesion corrio en otro hardware que la solucion, se declara."""
    sessions = [s for s in meta.get("sessions", []) if s.get("hardware")]
    sol = next((s for s in sessions if "decomposed_words" in s["strategies"]), None)
    if sol is None:
        return ""
    others = [s for s in sessions if s is not sol and hw_text(s["hardware"]) != hw_text(sol["hardware"])]
    if not others:
        return ""
    names = {"direct": "B0", "structured": "A1", "permutation": "A2", "cot": "A3",
             "decomposed": "S1", "decomposed_cal": "S1$^{+}$"}
    parts = []
    for o in others:
        who = ", ".join(names.get(x, x) for x in o["strategies"])
        parts.append(f"{who} (50 originales) corrieron antes en {esc(hw_text(o['hardware']))}")
    return "; ".join(parts) + "."


def verdict_vs_heuristic(dev, hold) -> str:
    """Frase que depende de los datos: aporta el modelo algo sobre ignorar los tipos?"""
    if dev is None:
        return ""
    w, l, p = dev
    txt_h = ""
    if hold is not None:
        wh, lh, ph = hold
        txt_h = f" En los 50 estados nuevos: gana en {wh}, pierde en {lh} ($p={pval(ph)}$)."
    if w > l and p < 0.05:
        head = (f"\\textbf{{El modelo s\\'i aporta:}} frente a H, S2 gana en {w} estados y pierde en {l} "
                f"($p={pval(p)}$).")
    elif w > l:
        head = (f"\\textbf{{El aporte del modelo es incierto:}} frente a H, S2 gana en {w} estados y pierde en "
                f"{l}, pero con $n=50$ no es significativo ($p={pval(p)}$).")
    else:
        head = (f"\\textbf{{El modelo no aporta sobre ignorar los tipos:}} frente a H, S2 gana en {w} estados y "
                f"pierde en {l} ($p={pval(p)}$).")
        if hold is not None and hold[1] > hold[0] and hold[2] < 0.05:
            wh, lh, ph = hold
            return head + (f" En los 50 estados nuevos es \\emph{{peor}}: gana en {wh}, pierde en {lh} "
                           f"($p={pval(ph)}$). Sus hechos de tipos valen menos que asumir $\\times$1.")
        head += " Sus hechos de tipos no son mejores que asumir $\\times$1."
    return head + txt_h


def featured_failure(summary: dict, order: list):
    fails = [f for f in summary["failures"] if f["wrong_facts"]]
    if not fails:
        return None
    pos = {c: i for i, c in enumerate(order)}
    fails.sort(key=lambda f: pos[f["case_id"]])
    gen = [f for f in fails if f["cause"] == "tabla de otra generacion"]
    return (gen or fails)[0]


def failure_macros(f, case, rows) -> dict:
    row = next(r for r in rows if r["strategy"] == "decomposed_words" and r["case_id"] == f["case_id"])
    trace = {m["action"]: m for m in row["trace"]["moves"]}
    lines = []
    for i, m in enumerate(case["moves"], 1):
        t = trace[f"MOVE_{i}"]
        true_eff = math.prod(single_effectiveness(m["type"], d) for d in case["enemy_types"])
        ts = expected_damage(m, case["player_types"], true_eff)
        wrong = t["effectiveness"] is not None and t["effectiveness"] != true_eff
        mark = "\\textcolor{crimson}{\\textbf{%s}}" if wrong else "%s"
        model_eff = "--" if t["effectiveness"] is None else f"$\\times${mult(t['effectiveness'])}"
        true_s = "--" if m["pp"] <= 0 else f"$\\times${mult(true_eff)}"
        ms = "PP 0" if t["score"] is None else num(t["score"], 1)
        tss = "PP 0" if m["pp"] <= 0 else num(ts, 1)
        lines.append(f"MOVE\\_{i} & {esc(m['name'])} & {m['type']} & {mark % model_eff} & {true_s} & "
                     f"{mark % ms} & {tss}\\\\")
    w = f["wrong_facts"][0]
    modern = MODERN_VALUES.get((w["attack"], w["defend"]))
    said = esc((w.get("answer") or "").strip().split("\n")[0][:40])
    ci, ri = int(f["chosen"][-1]) - 1, int(f["reference"][-1]) - 1
    return {
        "fcId": str(f["case_id"]), "fcDiff": f["difficulty"],
        "fcPlayer": "/".join(case["player_types"]), "fcEnemy": "/".join(case["enemy_types"]),
        "fcAtk": w["attack"], "fcDef": w["defend"], "fcModel": mult(w["model"]), "fcTruth": mult(w["truth"]),
        "fcSaid": said or "--",
        "fcIsModern": "1" if (modern is not None and modern == w["model"]) else "0",
        "fcChosen": f"MOVE\\_{ci + 1} ({esc(case['moves'][ci]['name'])})",
        "fcOptimal": f"MOVE\\_{ri + 1} ({esc(case['moves'][ri]['name'])})",
        "fcRegret": num(100 * (f["regret"] or 0), 0),
        "fcFixed": "s\\'i" if f["fixed_by_correct_facts"] else "no",
        "fcTable": "\n".join(lines),
    }


def load(folder: Path):
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    cases = json.loads((folder / "cases.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (folder / "decisions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return summary, cases, rows


def build(dev_dir: Path, hold_dir: Path | None) -> dict:
    summary, cases_list, rows = load(dev_dir)
    cases = {c["case_id"]: c for c in cases_list}
    meta, table = summary["meta"], summary["strategies"]
    model = meta.get("model", {})
    m: dict = {}

    m["modelId"] = esc(model.get("model_id", "??"))
    m["modelRev"] = esc((model.get("revision") or "??")[:10])
    m["nParams"] = num((model.get("n_params") or 0) / 1e9, 2)
    m["hw"] = esc(hw_text(model))
    m["hwNote"] = hw_note(meta)
    m["libs"] = esc(f"torch {model.get('torch', '?')}, transformers {model.get('transformers', '?')}")
    m["nStates"] = str(meta.get("n_states", len(cases)))
    m["seed"] = str(meta.get("seed", "??"))
    split = meta.get("difficulty_split", {})
    m["split"] = f"{split.get('EASY', '?')}/{split.get('MEDIUM', '?')}/{split.get('HARD', '?')}"
    m["runMinutes"] = num(sum(r["seconds"] for r in rows) / 60, 0)

    for name, k in KEYS.items():
        t = table.get(name)
        if not t:
            for f in ["acc", "ci", "strict", "regret", "calls", "secs", "win", "loss", "p", "diff", "chi", "chiP"]:
                m[f"{f}{k}"] = Q
            m[f"pos{k}"] = coords({})
            continue
        m[f"acc{k}"] = num(t["acc_pct"])
        m[f"ci{k}"] = f"{num(t['acc_ci95'][0], 0)}--{num(t['acc_ci95'][1], 0)}"
        m[f"strict{k}"] = num(t["strict_pct"], 0)
        m[f"regret{k}"] = num(t["mean_regret"], 2)
        m[f"calls{k}"] = num(t["llm_calls_per_state"], 1)
        m[f"secs{k}"] = num(t["seconds_per_state"], 1)
        d = t["per_difficulty"]
        m[f"diff{k}"] = f"{d['EASY']} $\\cdot$ {d['MEDIUM']} $\\cdot$ {d['HARD']}"
        m[f"pos{k}"] = coords(t["chosen_positions"])
        m[f"chi{k}"] = num(t["chi2_uniform"], 1)
        m[f"chiP{k}"] = pval(t["chi2_p"])
        pr = paired(summary, name, "direct")
        m[f"win{k}"], m[f"loss{k}"], m[f"p{k}"] = (str(pr[0]), str(pr[1]), pval(pr[2])) if pr else ("--", "--", "--")
    m["posOpt"] = coords(Counter(c["reference_action"] for c in cases_list))

    perm = summary.get("permutation_diagnostics") or {}
    m["permComplete"] = str(perm.get("states_with_4_valid_answers", "--"))
    m["sameSlot"] = str(perm.get("same_displayed_slot_all_4", "--"))
    m["sameMove"] = str(perm.get("same_original_move_all_4", "--"))

    agree = summary.get("agreement_with_notype", {})
    m["agreeSone"] = str(agree.get("decomposed", "--"))
    m["agreeStwo"] = str(agree.get("decomposed_words", Q))
    f1 = (summary.get("facts") or {}).get("decomposed") or {}
    m["sOneModal"] = mult(f1.get("modal_answer")) if f1 else "--"
    m["sOneModalShare"] = f1.get("modal_share", "--")
    m["sOneModalProb"] = num(f1.get("mean_prob_of_modal_answer"), 2)
    prior = summary.get("content_free_prior") or {}
    m["priorHalf"] = num(prior.get("0.5"), 2)

    f2 = (summary.get("facts") or {}).get("decomposed_words") or {}
    m["factPairs"] = str(f2.get("unique_pairs", Q))
    m["factRight"] = str(f2.get("unique_correct", Q))
    m["factAcc"] = num(f2["unique_accuracy_pct"]) if f2 else Q
    byc = f2.get("by_true_multiplier", {})
    for key, nm in [("2.0", "Two"), ("1.0", "One"), ("0.5", "Half"), ("0.0", "Zero")]:
        m[f"recall{nm}"] = byc.get(key, Q)
    wrong = f2.get("wrong_facts", [])
    m["nWrongFacts"] = str(len(wrong))
    m["unparsed"] = str(f2.get("unparsed_answers", 0)) if f2 else Q
    m["ties"] = str(f2.get("decisions_by_tie_break", Q))
    m["neutralShare"] = f2.get("modal_share", Q) if f2.get("modal_answer") == 1.0 else Q
    m["neutralPct"] = (num(100 * f2["predicted_distribution"].get("1.0", 0) / f2["unique_pairs"], 0)
                       if f2 else Q)
    m["nonNeutral"] = f"{f2['non_neutral_correct']}/{f2['non_neutral_answers']}" if "non_neutral_answers" in f2 else Q
    m["constOne"] = f"{f2['constant_x1_correct']}/{f2['unique_pairs']}" if "constant_x1_correct" in f2 else Q
    es = {"Water": "Agua", "Electric": "El\\'ectrico", "Poison": "Veneno", "Psychic": "Ps\\'iquico",
          "Rock": "Roca", "Fire": "Fuego", "Grass": "Planta", "Ice": "Hielo", "Normal": "Normal",
          "Fighting": "Lucha", "Ground": "Tierra", "Flying": "Volador", "Bug": "Bicho", "Ghost": "Fantasma",
          "Dragon": "Drag\\'on"}
    same = f2.get("same_type_said_super_wrongly", [])
    m["sameSuper"] = ", ".join(f"{es.get(t, t)}--{es.get(t, t)}" for t in same) if same else "--"
    m["nSameSuper"] = str(len(same))
    n_modern = sum(w["matches_modern_chart"] for w in wrong)
    fails = summary["failures"]
    n_gen = sum(f["cause"] == "tabla de otra generacion" for f in fails)
    m["nFail"] = str(len(fails))
    m["nFailFixed"] = str(sum(f["fixed_by_correct_facts"] for f in fails))
    m["genBullet"] = Q if not f2 else (
        f"{n_modern} de sus {len(wrong)} hechos err\\'oneos coinciden con la tabla de Gen~II en adelante "
        f"({n_gen} de los {len(fails)} fallos se deben solo a eso)." if n_modern else
        f"Ninguno de sus {len(wrong)} errores es el valor de Gen~II+: no confunde generaciones.")

    # held-out
    from d2.evaluate import DEFAULT_N, HOLDOUT_SEED
    m["holdN"], m["holdSeed"] = str(DEFAULT_N), str(HOLDOUT_SEED)
    for k in ["Base", "Heur", "Stwo"]:
        m[f"acc{k}H"], m[f"ci{k}H"] = Q, Q
    m["winStwoH"] = m["lossStwoH"] = m["pStwoH"] = Q
    m["nonNeutralH"] = m["neutralShareH"] = m["secsBaseH"] = m["secsStwoH"] = m["hwH"] = Q
    hold_sh = None
    if hold_dir is not None and (hold_dir / "summary.json").exists():
        hs, hcases, _ = load(hold_dir)
        m["holdN"] = str(hs["meta"].get("n_states", len(hcases)))
        m["holdSeed"] = str(hs["meta"].get("seed", "??"))
        for name, k in [("direct", "Base"), ("notype", "Heur"), ("decomposed_words", "Stwo")]:
            t = hs["strategies"].get(name)
            if t:
                m[f"acc{k}H"] = num(t["acc_pct"])
                m[f"ci{k}H"] = f"{num(t['acc_ci95'][0], 0)}--{num(t['acc_ci95'][1], 0)}"
        pr = paired(hs, "decomposed_words", "direct")
        if pr:
            m["winStwoH"], m["lossStwoH"], m["pStwoH"] = str(pr[0]), str(pr[1]), pval(pr[2])
        hold_sh = paired(hs, "decomposed_words", "notype")
        fh = (hs.get("facts") or {}).get("decomposed_words") or {}
        if "non_neutral_answers" in fh:
            m["nonNeutralH"] = f"{fh['non_neutral_correct']}/{fh['non_neutral_answers']}"
            m["neutralShareH"] = f"{fh['predicted_distribution'].get('1.0', 0)}/{fh['unique_pairs']}"
        for name, k in [("direct", "Base"), ("decomposed_words", "Stwo")]:
            t = hs["strategies"].get(name)
            if t:
                m[f"secs{k}H"] = num(t["seconds_per_state"], 2)
        m["hwH"] = esc(hw_text(hs["meta"].get("model", {})))

    dev_sh = paired(summary, "decomposed_words", "notype")
    m["verdictSH"] = verdict_vs_heuristic(dev_sh, hold_sh) or Q
    m["winSH"], m["lossSH"], m["pSH"] = (str(dev_sh[0]), str(dev_sh[1]), pval(dev_sh[2])) if dev_sh else (Q,) * 3

    f = featured_failure(summary, [c["case_id"] for c in cases_list]) if "decomposed_words" in table else None
    m["hasFailure"] = "1" if f else "0"
    m["fcIdOrQ"] = str(f["case_id"]) if f else "<id>"
    if f:
        m.update(failure_macros(f, cases[f["case_id"]], rows))
    return m


def placeholders() -> dict:
    m = {k: Q for k in ["modelRev", "nParams", "hw", "libs", "runMinutes", "permComplete", "sameSlot",
                        "sameMove", "agreeSone", "agreeStwo", "sOneModal", "sOneModalShare", "sOneModalProb",
                        "priorHalf", "factPairs", "factRight", "factAcc", "recallTwo", "recallOne",
                        "recallHalf", "recallZero", "nWrongFacts", "unparsed", "ties", "nFail", "nFailFixed",
                        "genBullet", "holdN", "holdSeed", "winStwoH", "lossStwoH", "pStwoH", "verdictSH",
                        "winSH", "lossSH", "pSH", "neutralShare", "neutralPct", "nonNeutral", "constOne",
                        "sameSuper", "nSameSuper", "nonNeutralH", "neutralShareH", "secsBaseH", "secsStwoH",
                        "hwH"]}
    m["hwNote"] = ""
    m.update({"modelId": "Qwen/Qwen2.5-1.5B-Instruct", "nStates": "50", "seed": "20260830", "split": "17/17/16",
              "holdN": "50", "holdSeed": "20260927",
              "hasFailure": "0", "fcIdOrQ": "<id>", "posOpt": coords({})})
    for k in KEYS.values():
        for f in ["acc", "ci", "strict", "regret", "calls", "secs", "win", "loss", "p", "diff", "chi", "chiP"]:
            m[f"{f}{k}"] = Q
        m[f"pos{k}"] = coords({})
    for k in ["Base", "Heur", "Stwo"]:
        m[f"acc{k}H"], m[f"ci{k}H"] = Q, Q
    return m


def write(macros: dict, out: Path) -> None:
    lines = ["% GENERADO por report/fill_d2.py -- no editar a mano."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(macros.items())]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="?", default="results_d2")
    ap.add_argument("holdout", nargs="?", default="results_d2_holdout")
    ap.add_argument("--placeholder", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "report" / "d2_numbers.tex"))
    a = ap.parse_args()
    macros = placeholders() if a.placeholder else build(Path(a.results), Path(a.holdout))
    write(macros, Path(a.out))
    print(f"escrito {a.out} ({len(macros)} cifras)")


if __name__ == "__main__":
    main()
