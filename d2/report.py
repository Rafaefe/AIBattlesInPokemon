"""
report.py -- metricas y analisis a partir de los archivos de results_d2/.
No carga el modelo: cualquiera puede verificar las cifras con los archivos.

    python -m d2.report results_d2

Escribe summary.md y summary.json en la misma carpeta.

Dos cosas que se DERIVAN aqui y no estan en decisions.jsonl:
  * Las acciones de las estrategias generativas (B0, A1, A3) se vuelven a
    interpretar desde la respuesta cruda con los parsers actuales. Asi un cambio
    de parser (p. ej. aceptar 'FINAL: THUNDERBOLT' en A3) no exige volver a
    correr el modelo, y las cifras siempre salen de la respuesta cruda.
  * La referencia sin modelo H: max(potencia x precision x STAB), sin tipos.
    Sirve para saber si el modelo aporta algo por encima de ignorar los tipos.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from d2.calculator import base_power, best_move, expected_damage
from d2.ground_truth import MODERN_VALUES, single_effectiveness
from d2.parsing import final_line_parse, final_line_semantic, semantic_parse, strict_parse
from d2.strategies import LABELS

POSITIONS = ["MOVE_1", "MOVE_2", "MOVE_3", "MOVE_4"]
ORDER = ["direct", "structured", "permutation", "cot", "decomposed", "decomposed_cal",
         "notype", "decomposed_words"]
BASELINE = "direct"
HEURISTIC = "notype"
DECOMPOSED = ["decomposed", "decomposed_cal", "decomposed_words"]

_PARSERS = {
    "direct": (strict_parse, semantic_parse),
    "structured": (strict_parse, semantic_parse),
    "cot": (final_line_parse, final_line_semantic),
}


# ---------------------------------------------------------------- estadistica --

def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (100 * max(0.0, center - half), 100 * min(1.0, center + half))


def mcnemar_exact(b: int, c: int) -> float:
    """p-valor bilateral exacto de McNemar (binomial con p = 0.5 sobre los discordantes)."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def chi2_uniform(counts: List[int]) -> Tuple[float, Optional[float]]:
    total = sum(counts)
    if total == 0:
        return 0.0, None
    expected = total / len(counts)
    stat = sum((o - expected) ** 2 / expected for o in counts)
    try:
        from scipy.stats import chi2
        return stat, float(chi2.sf(stat, len(counts) - 1))
    except ImportError:                                  # pragma: no cover
        return stat, None


# ---------------------------------------------------------------------- carga --

def _score(row: Dict, case: Dict, strict: Optional[str], interp: Optional[str]) -> Dict:
    best = max(case["reference_scores"])
    chosen = case["reference_scores"][int(interp[-1]) - 1] if interp else None
    row.update({
        "strict_action": strict or "", "interpreted_action": interp or "",
        "strict_valid": int(strict is not None), "interpretable": int(interp is not None),
        "decision_correct": int(interp == case["reference_action"]),
        "executable_correct": int(strict == case["reference_action"]),
        "chosen_score": chosen,
        "regret": round((best - chosen) / best, 4) if (chosen is not None and best > 0) else None,
    })
    return row


def heuristic_rows(cases: Dict[int, Dict]) -> List[Dict]:
    """H: la calculadora con TODAS las efectividades en x1 (ignora tipos). Sin modelo."""
    out = []
    for case in cases.values():
        scores = [base_power(m, case["player_types"]) for m in case["moves"]]
        action = f"MOVE_{best_move(scores) + 1}"
        row = {"case_id": case["case_id"], "difficulty": case["difficulty"], "strategy": HEURISTIC,
               "reference_action": case["reference_action"], "raw_response": "",
               "best_score": max(case["reference_scores"]), "llm_calls": 0, "seconds": 0.0, "trace": {}}
        out.append(_score(row, case, action, action))
    return out


def load(results_dir) -> Tuple[List[Dict], Dict[int, Dict], Dict]:
    d = Path(results_dir)
    rows = [json.loads(l) for l in (d / "decisions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = {c["case_id"]: c for c in json.loads((d / "cases.json").read_text(encoding="utf-8"))}
    meta_path = d / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for row in rows:                                     # re-interpretar desde la respuesta cruda
        if row["strategy"] in _PARSERS:
            case = cases[row["case_id"]]
            strict_fn, interp_fn = _PARSERS[row["strategy"]]
            raw = row["raw_response"]
            _score(row, case, strict_fn(raw, case), interp_fn(raw, case))
    rows += heuristic_rows(cases)
    return rows, cases, meta


def solution_name(rows: List[Dict]) -> str:
    present = {r["strategy"] for r in rows}
    return "decomposed_words" if "decomposed_words" in present else "decomposed"


# ------------------------------------------------------------------- analisis --

def strategy_table(rows: List[Dict]) -> Dict[str, Dict]:
    by = defaultdict(list)
    for r in rows:
        by[r["strategy"]].append(r)
    table = {}
    for name in [s for s in ORDER if s in by] + [s for s in by if s not in ORDER]:
        rs = by[name]
        n = len(rs)
        acc_k = sum(r["decision_correct"] for r in rs)
        exe_k = sum(r["executable_correct"] for r in rs)
        regrets = [r["regret"] for r in rs if r["regret"] is not None]
        chosen = Counter(r["interpreted_action"] for r in rs if r["interpreted_action"])
        per_diff = {}
        for diff in ["EASY", "MEDIUM", "HARD"]:
            sub = [r for r in rs if r["difficulty"] == diff]
            per_diff[diff] = f"{sum(r['decision_correct'] for r in sub)}/{len(sub)}"
        stat, p = chi2_uniform([chosen[pos] for pos in POSITIONS])
        table[name] = {
            "label": LABELS.get(name, name),
            "n": n,
            "strict_pct": round(100 * sum(r["strict_valid"] for r in rs) / n, 1),
            "interp_pct": round(100 * sum(r["interpretable"] for r in rs) / n, 1),
            "acc_k": acc_k,
            "acc_pct": round(100 * acc_k / n, 1),
            "acc_ci95": [round(x, 1) for x in wilson(acc_k, n)],
            "exec_k": exe_k,
            "exec_pct": round(100 * exe_k / n, 1),
            "exec_ci95": [round(x, 1) for x in wilson(exe_k, n)],
            "mean_regret": round(sum(regrets) / len(regrets), 3) if regrets else None,
            "llm_calls_per_state": round(sum(r["llm_calls"] for r in rs) / n, 2),
            "seconds_per_state": round(sum(r["seconds"] for r in rs) / n, 2),
            "per_difficulty": per_diff,
            "chosen_positions": {pos: chosen[pos] for pos in POSITIONS},
            "chi2_uniform": round(stat, 1),
            "chi2_p": p,
        }
    return table


def paired_test(rows: List[Dict], a: str, b: str, metric: str = "executable_correct") -> Optional[Dict]:
    ra = {r["case_id"]: r[metric] for r in rows if r["strategy"] == a}
    rb = {r["case_id"]: r[metric] for r in rows if r["strategy"] == b}
    common = sorted(set(ra) & set(rb))
    if not common or a == b:
        return None
    only_a = sum(1 for c in common if ra[c] and not rb[c])
    only_b = sum(1 for c in common if rb[c] and not ra[c])
    return {"a": a, "b": b, "metric": metric, "n": len(common),
            "a_right_b_wrong": only_a, "b_right_a_wrong": only_b,
            "p_value": mcnemar_exact(only_a, only_b)}


def agreement_with_heuristic(rows: List[Dict]) -> Dict[str, int]:
    """En cuantos estados cada variante descompuesta elige LO MISMO que ignorar los tipos."""
    h = {r["case_id"]: r["interpreted_action"] for r in rows if r["strategy"] == HEURISTIC}
    out = {}
    for s in DECOMPOSED:
        rs = [r for r in rows if r["strategy"] == s]
        if rs:
            out[s] = sum(r["interpreted_action"] == h[r["case_id"]] for r in rs)
    return out


def permutation_diagnostics(rows: List[Dict]) -> Optional[Dict]:
    perm = [r for r in rows if r["strategy"] == "permutation"]
    if not perm:
        return None
    same_slot = same_move = complete = 0
    slots = Counter()
    for r in perm:
        rot = r["trace"]["rotations"]
        shown = [x["shown"] for x in rot]
        original = [x["original"] for x in rot]
        for s in shown:
            if s:
                slots[s] += 1
        if all(shown):
            complete += 1
            same_slot += len(set(shown)) == 1
            same_move += len(set(original)) == 1
    stat, p = chi2_uniform([slots[pos] for pos in POSITIONS])
    return {
        "states": len(perm),
        "states_with_4_valid_answers": complete,
        "same_displayed_slot_all_4": same_slot,
        "same_original_move_all_4": same_move,
        "displayed_slot_distribution": {pos: slots[pos] for pos in POSITIONS},
        "chi2_uniform": round(stat, 1),
        "chi2_p": p,
    }


def _fmt(x: float) -> str:
    return {2.0: "2", 1.0: "1", 0.5: "0.5", 0.0: "0"}.get(x, str(x))


def fact_analysis(rows: List[Dict], strategy: str) -> Optional[Dict]:
    sol = [r for r in rows if r["strategy"] == strategy]
    if not sol:
        return None
    queries, unique = 0, {}
    for r in sol:
        for mv in r["trace"]["moves"]:
            for f in mv["facts"]:
                queries += 1
                unique[(f["attack"], f["defend"])] = f
    by_class = defaultdict(lambda: [0, 0])
    predicted = Counter()
    wrong = []
    for (atk, dfn), f in sorted(unique.items()):
        truth = single_effectiveness(atk, dfn)
        ok = f["multiplier"] == truth
        predicted[f["multiplier"]] += 1
        by_class[truth][0] += ok
        by_class[truth][1] += 1
        if not ok:
            modern = MODERN_VALUES.get((atk, dfn))
            wrong.append({"attack": atk, "defend": dfn, "model": f["multiplier"], "truth": truth,
                          "answer": f.get("answer"),
                          "confidence": (f.get("probs") or {}).get(_fmt(f["multiplier"])),
                          "matches_modern_chart": modern is not None and modern == f["multiplier"]})
    right = sum(v[0] for v in by_class.values())
    # Lo que sabe el modelo MAS ALLA de responder "x1": sus respuestas no neutras y
    # cuanto acertaria una respuesta constante "x1" (que es lo que hace H).
    non_neutral = [(k, f) for k, f in unique.items() if f["multiplier"] != 1.0]
    non_neutral_ok = sum(f["multiplier"] == single_effectiveness(*k) for k, f in non_neutral)
    const_one_ok = sum(single_effectiveness(*k) == 1.0 for k in unique)
    same = [(k, f) for k, f in unique.items() if k[0] == k[1]]
    same_super_wrong = sorted(k[0] for k, f in same
                              if f["multiplier"] == 2.0 and single_effectiveness(*k) != 2.0)
    ties = [r for r in sol if r["trace"].get("tie_broken")]
    modal, modal_n = predicted.most_common(1)[0]
    mean_modal_prob = None
    if all("probs" in f for f in unique.values()):
        mean_modal_prob = round(sum(f["probs"][_fmt(modal)] for f in unique.values()) / len(unique), 3)
    return {
        "decisions_by_tie_break": len(ties),
        "decisions_by_tie_break_correct": sum(r["decision_correct"] for r in ties),
        "queries": queries,
        "unique_pairs": len(unique),
        "unique_correct": right,
        "unique_accuracy_pct": round(100 * right / len(unique), 1),
        "by_true_multiplier": {str(k): f"{v[0]}/{v[1]}" for k, v in sorted(by_class.items(), reverse=True)},
        "predicted_distribution": {str(k): v for k, v in sorted(predicted.items(), reverse=True)},
        "modal_answer": modal, "modal_share": f"{modal_n}/{len(unique)}",
        "mean_prob_of_modal_answer": mean_modal_prob,
        "unparsed_answers": sum(1 for f in unique.values() if f.get("parsed") is False),
        "non_neutral_answers": len(non_neutral),
        "non_neutral_correct": non_neutral_ok,
        "constant_x1_correct": const_one_ok,
        "same_type_pairs": len(same),
        "same_type_said_super_wrongly": same_super_wrong,
        "wrong_facts": wrong,
    }


def failure_anatomy(rows: List[Dict], cases: Dict[int, Dict], strategy: str) -> List[Dict]:
    """Por que falla la solucion en cada estado donde falla."""
    out = []
    for r in rows:
        if r["strategy"] != strategy or r["decision_correct"]:
            continue
        case = cases[r["case_id"]]
        wrong_facts = []
        for mv in r["trace"]["moves"]:
            for f in mv["facts"]:
                truth = single_effectiveness(f["attack"], f["defend"])
                if f["multiplier"] != truth:
                    wrong_facts.append({"move": mv["action"], "name": mv["name"],
                                        "attack": f["attack"], "defend": f["defend"],
                                        "model": f["multiplier"], "truth": truth,
                                        "answer": f.get("answer"),
                                        "modern": MODERN_VALUES.get((f["attack"], f["defend"]))})
        # Contrafactual: misma calculadora con los hechos corregidos.
        fixed = [expected_damage(m, case["player_types"],
                                 math.prod(single_effectiveness(m["type"], t) for t in case["enemy_types"]))
                 for m in case["moves"]]
        fixed_action = f"MOVE_{best_move(fixed) + 1}"
        cause = "otro"
        if wrong_facts:
            gen = all(w["modern"] is not None and w["modern"] == w["model"] for w in wrong_facts)
            cause = "tabla de otra generacion" if gen else "hecho de tipo incorrecto"
        out.append({
            "case_id": r["case_id"], "difficulty": r["difficulty"],
            "chosen": r["interpreted_action"], "reference": r["reference_action"],
            "regret": r["regret"], "wrong_facts": wrong_facts,
            "fixed_by_correct_facts": fixed_action == r["reference_action"],
            "cause": cause,
        })
    return out


def content_free_prior(rows: List[Dict]) -> Optional[Dict]:
    for r in rows:
        if r["strategy"] == "decomposed_cal" and r["trace"].get("prior"):
            return r["trace"]["prior"]
    return None


# --------------------------------------------------------------------- salida --

def build_report(results_dir="results_d2") -> str:
    rows, cases, meta = load(results_dir)
    solution = solution_name(rows)
    table = strategy_table(rows)
    vs_baseline = [t for t in (paired_test(rows, s, BASELINE) for s in table if s != BASELINE) if t]
    vs_alternatives = [t for t in (paired_test(rows, solution, s) for s in table
                                   if s not in (solution, BASELINE)) if t]
    perm = permutation_diagnostics(rows)
    facts = {s: fact_analysis(rows, s) for s in DECOMPOSED if any(r["strategy"] == s for r in rows)}
    failures = failure_anatomy(rows, cases, solution)
    agreement = agreement_with_heuristic(rows)
    prior = content_free_prior(rows)

    summary = {"meta": meta, "solution": solution, "strategies": table,
               "paired_tests_vs_baseline": vs_baseline,
               "paired_tests_solution_vs_alternatives": vs_alternatives,
               "permutation_diagnostics": perm, "facts": facts,
               "agreement_with_notype": agreement, "content_free_prior": prior,
               "failures": failures}
    d = Path(results_dir)
    (d / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    L: List[str] = []
    model = meta.get("model", {})
    n = meta.get("n_states", len(cases))
    L.append("# Resultados Deliverable 2\n")
    L.append(f"- Modelo: `{model.get('model_id')}` (revision `{model.get('revision')}`), "
             f"{(model.get('n_params') or 0) / 1e9:.2f}B parametros, {model.get('device')} {model.get('gpu') or ''}")
    L.append(f"- Estados: **{n}** (semilla {meta.get('seed')}, reparto {meta.get('difficulty_split')}), "
             "mismos estados para todas las estrategias")
    L.append("- Correcto = la accion coincide con la politica de referencia del D1 "
             "(power x accuracy x STAB x efectividad)")
    L.append(f"- Solucion evaluada: **{LABELS.get(solution, solution)}**; H es una referencia sin modelo\n")

    L.append("## 1. Estrategias sobre los mismos estados\n")
    L.append("| Estrategia | STRICT | ACC [IC 95%] | EXEC-CORRECT | regret | llamadas/estado | s/estado |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for t in table.values():
        L.append(f"| {t['label']} | {t['strict_pct']}% | {t['acc_pct']}% [{t['acc_ci95'][0]}–{t['acc_ci95'][1]}] | "
                 f"{t['exec_pct']}% | {t['mean_regret']} | {t['llm_calls_per_state']} | {t['seconds_per_state']} |")
    L.append("")
    L.append("| Estrategia | EASY | MEDIUM | HARD | MOVE_1 | MOVE_2 | MOVE_3 | MOVE_4 | chi2 vs uniforme |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for t in table.values():
        pd_, cp = t["per_difficulty"], t["chosen_positions"]
        pv = f"{t['chi2_uniform']} (p={t['chi2_p']:.1e})" if t["chi2_p"] is not None else str(t["chi2_uniform"])
        L.append(f"| {t['label']} | {pd_['EASY']} | {pd_['MEDIUM']} | {pd_['HARD']} | "
                 f"{cp['MOVE_1']} | {cp['MOVE_2']} | {cp['MOVE_3']} | {cp['MOVE_4']} | {pv} |")
    optimal = Counter(c["reference_action"] for c in cases.values())
    L.append(f"| *accion optima* | | | | {optimal['MOVE_1']} | {optimal['MOVE_2']} | "
             f"{optimal['MOVE_3']} | {optimal['MOVE_4']} | |\n")

    L.append("## 2. Tests pareados (McNemar exacto sobre EXEC-CORRECT, mismos estados)\n")
    L.append("Contra el baseline B0:")
    for t in vs_baseline:
        L.append(f"- {LABELS.get(t['a'], t['a'])}: gana en {t['a_right_b_wrong']}, pierde en "
                 f"{t['b_right_a_wrong']}, p = {t['p_value']:.2e} (n = {t['n']})")
    L.append(f"\n{LABELS.get(solution, solution)} contra cada alternativa:")
    for t in vs_alternatives:
        L.append(f"- vs {LABELS.get(t['b'], t['b'])}: gana en {t['a_right_b_wrong']}, pierde en "
                 f"{t['b_right_a_wrong']}, p = {t['p_value']:.2e}")
    L.append("")

    L.append("## 3. Aporta el modelo algo mas que ignorar los tipos?\n")
    L.append(f"- H (sin modelo, sin tipos) acierta {table[HEURISTIC]['acc_pct']}%.")
    for s, k in agreement.items():
        L.append(f"- {LABELS.get(s, s)} elige lo mismo que H en {k} de {n} estados.")
    if prior:
        L.append(f"- Preferencia de S1 ante una pregunta VACIA (sin tipos): {prior}")
    L.append("")

    if perm:
        L.append("## 4. Sesgo de posicion medido directamente (baseline con 4 rotaciones)\n")
        L.append(f"- Estados con 4 respuestas validas: {perm['states_with_4_valid_answers']} de {perm['states']}")
        L.append(f"- Eligio la MISMA casilla mostrada en las 4 rotaciones: {perm['same_displayed_slot_all_4']}")
        L.append(f"- Eligio el MISMO movimiento en las 4 rotaciones: {perm['same_original_move_all_4']}")
        L.append(f"- Casillas elegidas ({4 * perm['states']} respuestas posibles): {perm['displayed_slot_distribution']}, "
                 f"chi2 = {perm['chi2_uniform']}" + (f", p = {perm['chi2_p']:.1e}" if perm["chi2_p"] is not None else ""))
        L.append("")

    L.append("## 5. Hechos de tipo que aporto el modelo\n")
    for s, fa in facts.items():
        L.append(f"**{LABELS.get(s, s)}**")
        L.append(f"- Pares correctos: {fa['unique_correct']}/{fa['unique_pairs']} = {fa['unique_accuracy_pct']}% "
                 f"({fa['queries']} consultas; el resto sale de cache)")
        L.append(f"- Acierto por multiplicador verdadero: {fa['by_true_multiplier']}")
        L.append(f"- Respuestas que dio (por par): {fa['predicted_distribution']}"
                 + (f"; prob. media de su respuesta mas comun: {fa['mean_prob_of_modal_answer']}"
                    if fa["mean_prob_of_modal_answer"] is not None else "")
                 + (f"; respuestas no interpretables: {fa['unparsed_answers']}" if fa["unparsed_answers"] else ""))
        L.append(f"- Cuando NO dijo x1, acerto {fa['non_neutral_correct']}/{fa['non_neutral_answers']}. "
                 f"Responder siempre x1 (lo que hace H) acertaria {fa['constant_x1_correct']}/{fa['unique_pairs']} pares.")
        if fa["same_type_pairs"]:
            L.append(f"- Pares del mismo tipo (p. ej. Agua contra Agua): {fa['same_type_pairs']}; "
                     f"llamo 'super efectivo' sin serlo a: {', '.join(fa['same_type_said_super_wrongly']) or 'ninguno'}")
        L.append(f"- Decisiones resueltas por desempate: {fa['decisions_by_tie_break']} "
                 f"({fa['decisions_by_tie_break_correct']} correctas)\n")
    sol_facts = facts.get(solution)
    if sol_facts and sol_facts["wrong_facts"]:
        L.append(f"Hechos erroneos de la solucion ({LABELS.get(solution, solution)}):\n")
        L.append("| Ataque -> Defensa | Modelo | Gen I | Coincide con tabla moderna | Respuesta |")
        L.append("|---|---:|---:|:---:|---|")
        for w in sol_facts["wrong_facts"]:
            L.append(f"| {w['attack']} -> {w['defend']} | {w['model']} | {w['truth']} | "
                     f"{'si' if w['matches_modern_chart'] else 'no'} | {(w['answer'] or '').strip()[:50]} |")
        L.append("")

    L.append("## 6. Anatomia de los fallos de la solucion\n")
    if not failures:
        L.append("- La solucion no fallo en ningun estado de este conjunto.")
    for f in failures:
        facts_txt = "; ".join(f"{w['name']}: {w['attack']}->{w['defend']} dijo {w['model']}, Gen I es {w['truth']}"
                              for w in f["wrong_facts"]) or "sin hechos incorrectos"
        L.append(f"- Caso {f['case_id']} ({f['difficulty']}): eligio {f['chosen']}, optimo {f['reference']}, "
                 f"regret {f['regret']}. Causa: {f['cause']}. {facts_txt}. "
                 f"Con los hechos corregidos acierta: {'si' if f['fixed_by_correct_facts'] else 'no'}.")
    if failures:
        causes = Counter(f["cause"] for f in failures)
        L.append(f"\nResumen: {dict(causes)}; corregibles con hechos correctos: "
                 f"{sum(f['fixed_by_correct_facts'] for f in failures)}/{len(failures)}")

    text = "\n".join(L) + "\n"
    (d / "summary.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(build_report(sys.argv[1] if len(sys.argv) > 1 else "results_d2"))
