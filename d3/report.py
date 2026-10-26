"""
report.py -- cifras del D3 a partir de results_d3/ (no carga el modelo).

    python -m d3.report results_d3

Escribe results_d3/summary.md y summary.json: exactitud por sistema en cada
conjunto y en los 100 estados juntos, tests pareados (McNemar exacto), la
contribucion de cada tecnica (sistema completo vs sin ella) y un diagnostico
por agente (hechos correctos, consultas, rechazos del Verificador, desvios del
Coordinador). La tabla verdadera se usa aqui SOLO para juzgar.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from d2.ground_truth import single_effectiveness
from d2.report import load, paired_test, strategy_table

LABELS = {
    "direct": "B0 Directo (baseline)",
    "notype": "H  Sin modelo (ignora tipos)",
    "decomposed_words": "S2 Solucion D2",
    "agents_full": "D3 Agentes (completo)",
    "agents_no_rag": "D3 sin recuperacion",
    "agents_no_fewshot": "D3 sin few-shot",
    "agents_no_verifier": "D3 sin Verificador",
    "agents_no_decomposition": "D3 sin descomposicion",
    "agents_no_ranking": "D3 sin tabla ordenada",
}
ORDER = list(LABELS)
FULL = "agents_full"
ABLATIONS = [s for s in ORDER if s.startswith("agents_no_")]


def load_all(results_dir) -> Dict[str, Dict]:
    sets = {}
    for d in sorted(Path(results_dir).iterdir()):
        if (d / "decisions.jsonl").exists():
            rows, cases, meta = load(d)
            sets[d.name] = {"rows": rows, "cases": cases, "meta": meta}
    return sets


def pooled(sets: Dict[str, Dict]) -> Dict:
    rows, cases = [], {}
    for name, s in sets.items():
        for r in s["rows"]:
            rows.append({**r, "case_id": f"{name}:{r['case_id']}"})
        cases.update({f"{name}:{k}": v for k, v in s["cases"].items()})
    return {"rows": rows, "cases": cases}


def table(rows: List[Dict]) -> Dict[str, Dict]:
    t = strategy_table(rows)
    out = {}
    for name in [s for s in ORDER if s in t] + [s for s in t if s not in ORDER]:
        out[name] = {**t[name], "label": LABELS.get(name, name)}
    return out


def comparisons(rows: List[Dict]) -> List[Dict]:
    present = {r["strategy"] for r in rows}
    pairs = [(s, "direct") for s in ORDER if s in present and s != "direct"]
    pairs += [(FULL, "decomposed_words"), (FULL, "notype")]
    pairs += [(FULL, a) for a in ABLATIONS if a in present]
    out = []
    for a, b in pairs:
        if a in present and b in present:
            test = paired_test(rows, a, b)
            if test:
                out.append(test)
    return out


# --------------------------------------------------------------- diagnostico --

def agent_diagnostics(rows: List[Dict], cases: Dict) -> Dict[str, Dict]:
    out = {}
    for name in [s for s in ORDER if s.startswith("agents_")]:
        rs = [r for r in rows if r["strategy"] == name]
        if not rs:
            continue
        facts = [f for r in rs for f in r["trace"].get("facts", [])]
        c = Counter()
        for f in facts:
            truth = single_effectiveness(f["attack"], f["defend"])
            c["facts"] += 1
            c["facts_right"] += f["multiplier"] == truth
            c["lookups"] += f["decision"] == "LOOKUP"
            c["right_section"] += f["passage_title"] == f"{f['attack']}-type attacks"
            c["revised"] += f["revisions"] > 0
            c["unverified"] += f["verified"] is False
            c["always_x1_right"] += truth == 1.0
        plan_missed = deviated = 0
        for r in rs:
            case = cases[r["case_id"]]
            usable = {f"MOVE_{i + 1}" for i, m in enumerate(case["moves"]) if m["pp"] > 0}
            analyzed = {row["action"] for row in r["trace"].get("calculator", [])
                        if row["score"] is not None}
            if r["trace"].get("calculator"):
                plan_missed += bool(usable - analyzed)
                deviated += r["interpreted_action"] != r["trace"].get("calculator_best")
        n = len(rs)
        out[name] = {
            "states": n,
            "facts": c["facts"],
            "facts_right_pct": round(100 * c["facts_right"] / c["facts"], 1) if c["facts"] else None,
            "always_x1_right_pct": round(100 * c["always_x1_right"] / c["facts"], 1) if c["facts"] else None,
            "lookup_pct": round(100 * c["lookups"] / c["facts"], 1) if c["facts"] else None,
            "right_section_pct": round(100 * c["right_section"] / c["facts"], 1) if c["facts"] else None,
            "facts_revised": c["revised"],
            "facts_unverified": c["unverified"],
            "states_plan_missed_a_move": plan_missed,
            "states_final_differs_from_calculator": deviated,
            "llm_calls_per_state": round(sum(r["llm_calls"] for r in rs) / n, 2),
        }
    return out


def revision_effect(rows: List[Dict]) -> Optional[Dict]:
    """Que hizo el bucle Verificador -> Analista: hechos corregidos vs danados."""
    rs = [r for r in rows if r["strategy"] == FULL]
    base = {(r["case_id"]): r for r in rows if r["strategy"] == "agents_no_verifier"}
    if not rs or not base:
        return None
    fixed = broken = 0
    for r in rs:
        b = base.get(r["case_id"])
        if not b:
            continue
        for f_full, f_base in zip(r["trace"].get("facts", []), b["trace"].get("facts", [])):
            truth = single_effectiveness(f_full["attack"], f_full["defend"])
            fixed += f_full["multiplier"] == truth and f_base["multiplier"] != truth
            broken += f_full["multiplier"] != truth and f_base["multiplier"] == truth
    return {"facts_fixed_by_loop": fixed, "facts_broken_by_loop": broken}


def failures(rows: List[Dict], cases: Dict, system: str = FULL) -> List[Dict]:
    out = []
    for r in rows:
        if r["strategy"] != system or r["decision_correct"]:
            continue
        wrong = [f"{f['attack']}->{f['defend']}: dijo '{f['answer']}', Gen I x{single_effectiveness(f['attack'], f['defend']):g}"
                 for f in r["trace"].get("facts", [])
                 if f["multiplier"] != single_effectiveness(f["attack"], f["defend"])]
        if wrong:
            cause = "hecho de tipo incorrecto"
        elif r["interpreted_action"] != r["trace"].get("calculator_best"):
            cause = "el Coordinador no eligio el maximo de la calculadora"
        else:
            cause = "plan incompleto"
        out.append({"case_id": r["case_id"], "difficulty": r["difficulty"], "chosen": r["interpreted_action"],
                    "reference": r["reference_action"], "regret": r["regret"], "cause": cause, "wrong_facts": wrong})
    return out


# -------------------------------------------------------------------- salida --

def _ci(row: Dict) -> str:
    lo, hi = row["acc_ci95"]
    return f"{row['acc_pct']}% [{lo:.0f}–{hi:.0f}]"


def build_report(results_dir="results_d3") -> str:
    sets = load_all(results_dir)
    if not sets:
        return f"(sin resultados en {results_dir})"
    allp = pooled(sets)
    groups = {**{k: v for k, v in sets.items()}, "all": allp}
    tables = {k: table(v["rows"]) for k, v in groups.items()}
    summary = {
        "sets": {k: {"n_states": len(v["cases"]), "seed": v["meta"].get("seed")} for k, v in sets.items()},
        "model": next((v["meta"].get("model") for v in sets.values() if v["meta"].get("model")), None),
        "tables": tables,
        "comparisons": {k: comparisons(v["rows"]) for k, v in groups.items()},
        "agents": agent_diagnostics(allp["rows"], allp["cases"]),
        "revision_effect": revision_effect(allp["rows"]),
        "failures_full": failures(allp["rows"], allp["cases"]),
    }
    out = Path(results_dir)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    names = [n for n in ORDER if n in tables["all"]]
    lines = ["# Resultados Deliverable 3", ""]
    if summary["model"]:
        m = summary["model"]
        lines.append(f"- Modelo (todos los agentes): `{m.get('model_id')}` revision `{str(m.get('revision'))[:10]}`, "
                     f"{m.get('device')} {m.get('gpu') or ''} {m.get('dtype')}")
    lines.append("- Conjuntos: " + ", ".join(f"{k} (semilla {v['seed']}, n={v['n_states']})"
                                            for k, v in summary["sets"].items()))
    lines += ["- Correcto = la accion coincide con max(potencia x precision x STAB x efectividad Gen I), igual que D1/D2", "",
              "## 1. Exactitud (mismos estados, mismo criterio)", "",
              "| Sistema | " + " | ".join(groups) + " | llamadas/estado | s/estado |",
              "|---|" + "---:|" * (len(groups) + 2)]
    for n in names:
        cells = [(_ci(tables[g][n]) if n in tables[g] else "–") for g in groups]
        t = tables["all"][n]
        lines.append(f"| {LABELS.get(n, n)} | " + " | ".join(cells) +
                     f" | {t['llm_calls_per_state']} | {t['seconds_per_state']} |")
    lines += ["", "## 2. Tests pareados (McNemar exacto, 100 estados)", ""]
    for c in summary["comparisons"]["all"]:
        lines.append(f"- {LABELS.get(c['a'], c['a'])} vs {LABELS.get(c['b'], c['b'])}: "
                     f"gana {c['a_right_b_wrong']}, pierde {c['b_right_a_wrong']}, p = {c['p_value']:.3g}")
    lines += ["", "## 3. Diagnostico por agente (100 estados)", "",
              "| Sistema | hechos ok | siempre x1 | consulta | seccion ok | revisados | sin verificar | plan incompleto | final != calculadora | llamadas |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for n, a in summary["agents"].items():
        lines.append(f"| {LABELS.get(n, n)} | {a['facts_right_pct']}% | {a['always_x1_right_pct']}% | {a['lookup_pct']}% | "
                     f"{a['right_section_pct']}% | {a['facts_revised']} | {a['facts_unverified']} | "
                     f"{a['states_plan_missed_a_move']} | {a['states_final_differs_from_calculator']} | {a['llm_calls_per_state']} |")
    if summary["revision_effect"]:
        e = summary["revision_effect"]
        lines += ["", f"Bucle Verificador->Analista (completo vs sin Verificador): corrige {e['facts_fixed_by_loop']} hechos, "
                      f"daña {e['facts_broken_by_loop']}."]
    lines += ["", f"## 4. Fallos del sistema completo ({len(summary['failures_full'])})", ""]
    for f in summary["failures_full"]:
        lines.append(f"- {f['case_id']} ({f['difficulty']}): eligio {f['chosen']}, correcto {f['reference']}, "
                     f"regret {f['regret']} — {f['cause']}" + (f": {'; '.join(f['wrong_facts'])}" if f["wrong_facts"] else ""))
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(build_report(sys.argv[1] if len(sys.argv) > 1 else "results_d3"))
