
"""
pokemon_benchmark_final.py
==========================

BENCHMARK OFFLINE PARA EL PROYECTO DE GENERATIVE AI.

NO abre Pokemon Blue.
NO usa PyBoy.
NO necesitas jugar 20, 30 o 50 batallas manualmente.

El programa:
1) genera estados sinteticos de batalla reproducibles;
2) calcula una accion de referencia con una politica determinista;
3) prueba LOS MISMOS estados con dos prompts:
      DIRECT     = prompting directo/natural
      STRUCTURED = prompt estructurado con salida MOVE_N
4) guarda todas las respuestas;
5) calcula:
      - Strict valid rate
      - Interpretable rate
      - Decision accuracy
      - Executable-correct rate
6) crea CSV/JSON con los resultados.

La demo en PyBoy queda separada. Este archivo es para producir
la evidencia cuantitativa del Deliverable 1.

Dependencias:
    pip install "torch>=2.1.0" "transformers>=4.46.0" \
                "accelerate>=0.34.0" "huggingface_hub>=0.24.0"

Ejecucion:
    python pokemon_benchmark_final.py
"""

from __future__ import annotations

import csv
import gc
import json
import math
import random
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


# ============================================================
# 1. CONFIGURACION
# ============================================================

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"

# 30 estados = 60 inferencias, porque cada estado se prueba
# con DIRECT y STRUCTURED.
# Puedes cambiarlo a 20, 30 o 50 sin tocar nada mas.
TOTAL_CASES = 30

SEED = 20260830

PROMPT_MODES = ["DIRECT", "STRUCTURED"]

# Si tienes GPU, float16 reduce memoria.
MAX_NEW_TOKENS = 48

OUTPUT_DIR = Path("pokemon_benchmark_output")
CASES_JSON = OUTPUT_DIR / "benchmark_cases.json"
RESULTS_CSV = OUTPUT_DIR / "benchmark_results.csv"
SUMMARY_CSV = OUTPUT_DIR / "benchmark_summary.csv"
FAILURES_CSV = OUTPUT_DIR / "benchmark_failures.csv"


# ============================================================
# 2. DATOS DE MOVIMIENTOS GEN I
#    Solo movimientos ofensivos faciles de puntuar.
# ============================================================

MOVE_DB = [
    {"name": "Scratch",       "type": "Normal",   "power": 40,  "accuracy": 100},
    {"name": "Tackle",        "type": "Normal",   "power": 35,  "accuracy": 95},
    {"name": "Quick Attack",  "type": "Normal",   "power": 40,  "accuracy": 100},
    {"name": "Body Slam",     "type": "Normal",   "power": 85,  "accuracy": 100},
    {"name": "Take Down",     "type": "Normal",   "power": 90,  "accuracy": 85},
    {"name": "Mega Punch",    "type": "Normal",   "power": 80,  "accuracy": 85},
    {"name": "Strength",      "type": "Normal",   "power": 80,  "accuracy": 100},
    {"name": "Slash",         "type": "Normal",   "power": 70,  "accuracy": 100},

    {"name": "Ember",         "type": "Fire",     "power": 40,  "accuracy": 100},
    {"name": "Flamethrower",  "type": "Fire",     "power": 95,  "accuracy": 100},
    {"name": "Fire Blast",    "type": "Fire",     "power": 120, "accuracy": 85},

    {"name": "Water Gun",     "type": "Water",    "power": 40,  "accuracy": 100},
    {"name": "BubbleBeam",    "type": "Water",    "power": 65,  "accuracy": 100},
    {"name": "Surf",          "type": "Water",    "power": 95,  "accuracy": 100},
    {"name": "Hydro Pump",    "type": "Water",    "power": 120, "accuracy": 80},

    {"name": "Vine Whip",     "type": "Grass",    "power": 35,  "accuracy": 100},
    {"name": "Razor Leaf",    "type": "Grass",    "power": 55,  "accuracy": 95},

    {"name": "ThunderShock",  "type": "Electric", "power": 40,  "accuracy": 100},
    {"name": "Thunderbolt",   "type": "Electric", "power": 95,  "accuracy": 100},
    {"name": "Thunder",       "type": "Electric", "power": 120, "accuracy": 70},

    {"name": "Ice Beam",      "type": "Ice",      "power": 95,  "accuracy": 100},
    {"name": "Blizzard",      "type": "Ice",      "power": 120, "accuracy": 90},

    {"name": "Low Kick",      "type": "Fighting", "power": 50,  "accuracy": 90},
    {"name": "Submission",    "type": "Fighting", "power": 80,  "accuracy": 80},

    {"name": "Peck",          "type": "Flying",   "power": 35,  "accuracy": 100},
    {"name": "Drill Peck",    "type": "Flying",   "power": 80,  "accuracy": 100},

    {"name": "Sludge",        "type": "Poison",   "power": 65,  "accuracy": 100},

    {"name": "Earthquake",    "type": "Ground",   "power": 100, "accuracy": 100},

    {"name": "Confusion",     "type": "Psychic",  "power": 50,  "accuracy": 100},
    {"name": "Psybeam",       "type": "Psychic",  "power": 65,  "accuracy": 100},
    {"name": "Psychic",       "type": "Psychic",  "power": 90,  "accuracy": 100},

    {"name": "Leech Life",    "type": "Bug",      "power": 20,  "accuracy": 100},

    {"name": "Rock Throw",    "type": "Rock",     "power": 50,  "accuracy": 65},
    {"name": "Rock Slide",    "type": "Rock",     "power": 75,  "accuracy": 90},

    {"name": "Lick",          "type": "Ghost",    "power": 20,  "accuracy": 100},
]

TYPES = [
    "Normal", "Fire", "Water", "Grass", "Electric", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic",
    "Bug", "Rock", "Ghost",
]


# ============================================================
# 3. TABLA DE EFECTIVIDAD GEN I
#    Lo no especificado se considera 1x.
# ============================================================

TYPE_CHART = {
    "Normal": {
        "Rock": 0.5, "Ghost": 0.0,
    },
    "Fighting": {
        "Normal": 2.0, "Ice": 2.0, "Rock": 2.0,
        "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5,
        "Bug": 0.5, "Ghost": 0.0,
    },
    "Flying": {
        "Fighting": 2.0, "Bug": 2.0, "Grass": 2.0,
        "Rock": 0.5, "Electric": 0.5,
    },
    "Poison": {
        "Grass": 2.0, "Bug": 2.0,
        "Poison": 0.5, "Ground": 0.5,
        "Rock": 0.5, "Ghost": 0.5,
    },
    "Ground": {
        "Poison": 2.0, "Rock": 2.0, "Fire": 2.0,
        "Electric": 2.0, "Bug": 0.5, "Grass": 0.5,
        "Flying": 0.0,
    },
    "Rock": {
        "Flying": 2.0, "Bug": 2.0, "Fire": 2.0, "Ice": 2.0,
        "Fighting": 0.5, "Ground": 0.5,
    },
    "Bug": {
        "Grass": 2.0, "Psychic": 2.0, "Poison": 2.0,
        "Fighting": 0.5, "Flying": 0.5, "Ghost": 0.5,
        "Fire": 0.5,
    },
    # En Gen I Ghost no afecta Psychic por la mecanica/bug original.
    "Ghost": {
        "Normal": 0.0, "Psychic": 0.0, "Ghost": 2.0,
    },
    "Fire": {
        "Bug": 2.0, "Grass": 2.0, "Ice": 2.0,
        "Fire": 0.5, "Water": 0.5, "Rock": 0.5,
    },
    "Water": {
        "Fire": 2.0, "Ground": 2.0, "Rock": 2.0,
        "Water": 0.5, "Grass": 0.5,
    },
    "Grass": {
        "Water": 2.0, "Ground": 2.0, "Rock": 2.0,
        "Fire": 0.5, "Grass": 0.5, "Poison": 0.5,
        "Flying": 0.5, "Bug": 0.5,
    },
    "Electric": {
        "Water": 2.0, "Flying": 2.0,
        "Electric": 0.5, "Grass": 0.5,
        "Ground": 0.0,
    },
    "Psychic": {
        "Fighting": 2.0, "Poison": 2.0,
        "Psychic": 0.5,
    },
    "Ice": {
        "Grass": 2.0, "Ground": 2.0,
        "Flying": 2.0,
        "Water": 0.5, "Ice": 0.5,
    },
}


# ============================================================
# 4. POLITICA DE REFERENCIA (GROUND TRUTH)
# ============================================================

def type_effectiveness(move_type: str, defender_types: List[str]) -> float:
    result = 1.0
    chart = TYPE_CHART.get(move_type, {})

    for defender_type in defender_types:
        result *= chart.get(defender_type, 1.0)

    return result


def reference_score(
    move: Dict,
    player_types: List[str],
    enemy_types: List[str],
) -> float:
    """
    Proxy determinista de utilidad ofensiva:

        power
        x accuracy
        x STAB
        x type effectiveness

    No pretende reproducir todo el motor competitivo de Pokemon.
    Sirve para que cada escenario tenga una respuesta de referencia
    OBJETIVA Y REPRODUCIBLE.
    """
    if move["pp"] <= 0:
        return 0.0

    stab = 1.5 if move["type"] in player_types else 1.0
    eff = type_effectiveness(move["type"], enemy_types)
    accuracy = move["accuracy"] / 100.0

    return move["power"] * accuracy * stab * eff


def add_reference(case: Dict) -> Dict:
    scores = []

    for move in case["moves"]:
        score = reference_score(
            move,
            case["player_types"],
            case["enemy_types"],
        )
        scores.append(score)

    best_idx = max(range(4), key=lambda i: scores[i])

    case["reference_action"] = f"MOVE_{best_idx + 1}"
    case["reference_scores"] = [round(x, 3) for x in scores]

    sorted_scores = sorted(scores, reverse=True)
    second = sorted_scores[1]

    if second <= 0:
        ratio = 999.0
    else:
        ratio = sorted_scores[0] / second

    case["best_vs_second_ratio"] = round(ratio, 3)

    return case


# ============================================================
# 5. GENERAR ESTADOS SINTETICOS
# ============================================================

def random_types(rng: random.Random, dual: bool) -> List[str]:
    if dual:
        return rng.sample(TYPES, 2)
    return [rng.choice(TYPES)]


def candidate_case(
    rng: random.Random,
    difficulty: str,
    case_id: int,
) -> Dict:

    dual_player = difficulty == "HARD" and rng.random() < 0.50
    dual_enemy = difficulty == "HARD"

    player_types = random_types(rng, dual_player)
    enemy_types = random_types(rng, dual_enemy)

    moves = [dict(m) for m in rng.sample(MOVE_DB, 4)]
    rng.shuffle(moves)

    for move in moves:
        move["pp"] = rng.randint(5, 35)

    # En hard, a veces uno de los movimientos no tiene PP.
    if difficulty == "HARD" and rng.random() < 0.30:
        rng.choice(moves)["pp"] = 0

    case = {
        "case_id": case_id,
        "difficulty": difficulty,

        # HP/speed aparecen en el estado para que el problema se parezca
        # al estado real del juego. Esta politica ofensiva concreta no
        # los usa para elegir el ground truth.
        "player_hp_percent": rng.randint(15, 100),
        "player_speed": rng.randint(20, 120),
        "player_types": player_types,

        "enemy_hp_percent": rng.randint(15, 100),
        "enemy_speed": rng.randint(20, 120),
        "enemy_types": enemy_types,

        "moves": moves,
    }

    return add_reference(case)


def difficulty_ok(case: Dict, difficulty: str) -> bool:
    scores = sorted(case["reference_scores"], reverse=True)

    # Evitar empates o casos sin ningun ataque util.
    if scores[0] <= 0:
        return False

    if abs(scores[0] - scores[1]) < 1e-6:
        return False

    ratio = case["best_vs_second_ratio"]

    if difficulty == "EASY":
        # Una alternativa domina claramente.
        return ratio >= 1.80

    if difficulty == "MEDIUM":
        return 1.25 <= ratio < 1.80

    if difficulty == "HARD":
        # Las dos mejores opciones son cercanas y hay doble tipo.
        return 1.01 <= ratio < 1.25

    return False


def split_counts(total: int) -> Dict[str, int]:
    base = total // 3
    remainder = total % 3

    counts = {
        "EASY": base,
        "MEDIUM": base,
        "HARD": base,
    }

    order = ["EASY", "MEDIUM", "HARD"]

    for i in range(remainder):
        counts[order[i]] += 1

    return counts


def generate_cases(total: int, seed: int) -> List[Dict]:
    rng = random.Random(seed)
    counts = split_counts(total)

    cases = []
    next_id = 1

    for difficulty in ["EASY", "MEDIUM", "HARD"]:
        wanted = counts[difficulty]
        made = 0
        attempts = 0

        while made < wanted:
            attempts += 1

            if attempts > 50000:
                raise RuntimeError(
                    f"No pude generar suficientes casos {difficulty}. "
                    "Prueba otro SEED."
                )

            case = candidate_case(
                rng=rng,
                difficulty=difficulty,
                case_id=next_id,
            )

            if not difficulty_ok(case, difficulty):
                continue

            cases.append(case)
            next_id += 1
            made += 1

    # Mezclamos el orden de evaluacion, pero la dificultad queda guardada.
    rng.shuffle(cases)

    return cases


# ============================================================
# 6. PROMPTS
#    MISMA INFORMACION FACTUAL; cambia la forma de instruir.
# ============================================================

def state_text(case: Dict) -> str:
    moves = []

    for i, move in enumerate(case["moves"], start=1):
        moves.append(
            f"MOVE_{i}: {move['name']} | "
            f"Type={move['type']} | "
            f"Power={move['power']} | "
            f"Accuracy={move['accuracy']}% | "
            f"PP={move['pp']}"
        )

    return f"""
PLAYER
HP: {case["player_hp_percent"]}%
Types: {"/".join(case["player_types"])}
Speed: {case["player_speed"]}

OPPONENT
HP: {case["enemy_hp_percent"]}%
Types: {"/".join(case["enemy_types"])}
Speed: {case["enemy_speed"]}

AVAILABLE MOVES
{chr(10).join(moves)}
""".strip()


def build_prompt(case: Dict, mode: str) -> str:
    state = state_text(case)

    if mode == "DIRECT":
        return f"""
You are playing Pokemon Blue.
Your goal is to win the battle.

Here is the current battle state:

{state}

What move would you use next?
""".strip()

    if mode == "STRUCTURED":
        return f"""
You are the battle decision module for Pokemon Blue.

Given the battle state below, select the best available move.

When deciding, consider:
- type effectiveness,
- STAB,
- move power,
- accuracy,
- and remaining PP.

{state}

Return EXACTLY one of:
MOVE_1
MOVE_2
MOVE_3
MOVE_4

Do not explain.
Do not write the move name.
Return only the MOVE_N label.
""".strip()

    raise ValueError(f"Prompt mode desconocido: {mode}")


# ============================================================
# 7. CARGAR MODELO
# ============================================================

class LocalLLM:
    def __init__(self, model_id: str):
        print("\n" + "=" * 72)
        print(f"CARGANDO MODELO: {model_id}")
        print("=" * 72)

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        kwargs = {
            "low_cpu_mem_usage": True,
        }

        if torch.cuda.is_available():
            kwargs["device_map"] = "auto"
            kwargs["torch_dtype"] = torch.float16

        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            **kwargs,
        )

        if not torch.cuda.is_available():
            self.model.to("cpu")

        self.model.eval()

        print(
            "Device:",
            "CUDA" if torch.cuda.is_available() else "CPU"
        )

    @torch.inference_mode()
    def generate(self, prompt: str) -> str:
        # Mismo system prompt para DIRECT y STRUCTURED:
        # no escondemos instrucciones extra en una condicion.
        messages = [
            {
                "role": "system",
                "content": "You are an AI playing Pokemon Blue.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
        )

        device = next(self.model.parameters()).device

        inputs = {
            key: value.to(device)
            for key, value in inputs.items()
        }

        output = self.model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=(
                self.tokenizer.eos_token_id
                if self.tokenizer.eos_token_id is not None
                else 0
            ),
        )

        generated = output[0][inputs["input_ids"].shape[1]:]

        return self.tokenizer.decode(
            generated,
            skip_special_tokens=True,
        ).strip()


# ============================================================
# 8. PARSEO
# ============================================================

def strict_parse(raw: str, case: Dict) -> Optional[str]:
    """
    Formato ejecutable por el agente:
        MOVE_1
        MOVE_2
        MOVE_3
        MOVE_4
    """
    match = re.fullmatch(
        r"\s*MOVE_([1-4])\s*[.!]?\s*",
        raw.upper(),
    )

    if not match:
        return None

    action = f"MOVE_{match.group(1)}"
    idx = int(match.group(1)) - 1

    if case["moves"][idx]["pp"] <= 0:
        return None

    return action


def normalize_for_match(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def semantic_parse(raw: str, case: Dict) -> Optional[str]:
    """
    Para analizar si el modelo ENTENDIO la accion aunque no respetara
    el formato.

    Ejemplo:
        raw = "TAIL WHIP"
        strict_parse    -> None
        semantic_parse  -> MOVE_2

    Asi podemos separar:
      - failure de formato/control
      - failure de decision
    """
    strict = strict_parse(raw, case)

    if strict:
        return strict

    normalized = normalize_for_match(raw)

    # Formas relajadas como "move 2".
    relaxed = re.search(r"\bMOVE\s*([1-4])\b", normalized)

    if relaxed:
        idx = int(relaxed.group(1)) - 1
        if case["moves"][idx]["pp"] > 0:
            return f"MOVE_{idx + 1}"

    found = []

    for i, move in enumerate(case["moves"], start=1):
        if move["pp"] <= 0:
            continue

        move_name = normalize_for_match(move["name"])

        if move_name and re.search(
            rf"\b{re.escape(move_name)}\b",
            normalized,
        ):
            found.append(f"MOVE_{i}")

    # Solo aceptamos un nombre si la respuesta es inequivoca.
    found = list(dict.fromkeys(found))

    if len(found) == 1:
        return found[0]

    return None


# ============================================================
# 9. UNA EVALUACION
# ============================================================

def evaluate_one(
    llm: LocalLLM,
    case: Dict,
    mode: str,
) -> Dict:

    prompt = build_prompt(case, mode)

    start = time.perf_counter()
    raw = llm.generate(prompt)
    seconds = time.perf_counter() - start

    strict_action = strict_parse(raw, case)
    interpreted_action = semantic_parse(raw, case)

    reference = case["reference_action"]

    strict_valid = strict_action is not None
    interpretable = interpreted_action is not None

    decision_correct = interpreted_action == reference
    executable_correct = strict_action == reference

    chosen_score = None
    regret = None

    if interpreted_action is not None:
        idx = int(interpreted_action.split("_")[1]) - 1
        chosen_score = case["reference_scores"][idx]
        best_score = max(case["reference_scores"])

        if best_score > 0:
            regret = (best_score - chosen_score) / best_score

    return {
        "case_id": case["case_id"],
        "difficulty": case["difficulty"],
        "prompt_mode": mode,
        "reference_action": reference,

        "raw_response": raw.replace("\n", "\\n"),
        "strict_action": strict_action or "",
        "interpreted_action": interpreted_action or "",

        "strict_valid": int(strict_valid),
        "interpretable": int(interpretable),
        "decision_correct": int(decision_correct),
        "executable_correct": int(executable_correct),

        "chosen_score": (
            "" if chosen_score is None else round(chosen_score, 3)
        ),
        "best_score": round(max(case["reference_scores"]), 3),
        "regret": (
            "" if regret is None else round(regret, 4)
        ),
        "seconds": round(seconds, 3),

        # Estado resumido para inspeccionar errores en Excel.
        "player_types": "/".join(case["player_types"]),
        "enemy_types": "/".join(case["enemy_types"]),
        "move_1": move_to_short(case["moves"][0]),
        "move_2": move_to_short(case["moves"][1]),
        "move_3": move_to_short(case["moves"][2]),
        "move_4": move_to_short(case["moves"][3]),
        "reference_scores": "|".join(
            str(x) for x in case["reference_scores"]
        ),
    }


def move_to_short(move: Dict) -> str:
    return (
        f'{move["name"]};{move["type"]};'
        f'P{move["power"]};A{move["accuracy"]};PP{move["pp"]}'
    )


# ============================================================
# 10. GUARDAR CSV
# ============================================================

def write_csv(path: Path, rows: List[Dict]) -> None:
    if not rows:
        return

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)


def save_cases(cases: List[Dict]) -> None:
    with CASES_JSON.open("w", encoding="utf-8") as f:
        json.dump(
            cases,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# 11. RESUMEN
# ============================================================

def percent(n: int, d: int) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


def summarize(results: List[Dict]) -> List[Dict]:
    groups = defaultdict(list)

    for row in results:
        groups[(row["prompt_mode"], "ALL")].append(row)
        groups[
            (row["prompt_mode"], row["difficulty"])
        ].append(row)

    summary = []

    for mode in PROMPT_MODES:
        for difficulty in ["ALL", "EASY", "MEDIUM", "HARD"]:
            rows = groups.get((mode, difficulty), [])

            if not rows:
                continue

            n = len(rows)

            strict_valid_n = sum(
                int(r["strict_valid"]) for r in rows
            )
            interpretable_n = sum(
                int(r["interpretable"]) for r in rows
            )
            correct_n = sum(
                int(r["decision_correct"]) for r in rows
            )
            executable_correct_n = sum(
                int(r["executable_correct"]) for r in rows
            )

            valid_regrets = [
                float(r["regret"])
                for r in rows
                if r["regret"] != ""
            ]

            avg_regret = (
                sum(valid_regrets) / len(valid_regrets)
                if valid_regrets
                else None
            )

            summary.append({
                "prompt_mode": mode,
                "difficulty": difficulty,
                "n": n,

                "strict_valid_n": strict_valid_n,
                "strict_valid_rate_pct": percent(
                    strict_valid_n, n
                ),

                "interpretable_n": interpretable_n,
                "interpretable_rate_pct": percent(
                    interpretable_n, n
                ),

                "decision_correct_n": correct_n,
                "decision_accuracy_pct": percent(
                    correct_n, n
                ),

                "executable_correct_n": executable_correct_n,
                "executable_correct_rate_pct": percent(
                    executable_correct_n, n
                ),

                "avg_regret": (
                    ""
                    if avg_regret is None
                    else round(avg_regret, 4)
                ),
            })

    return summary


def print_summary(summary: List[Dict]) -> None:
    print("\n" + "=" * 92)
    print("RESULTADOS FINALES")
    print("=" * 92)

    headers = (
        "PROMPT",
        "LEVEL",
        "N",
        "STRICT%",
        "INTERP%",
        "ACC%",
        "EXEC-CORRECT%",
    )

    print(
        f"{headers[0]:<12}"
        f"{headers[1]:<10}"
        f"{headers[2]:>5}"
        f"{headers[3]:>11}"
        f"{headers[4]:>11}"
        f"{headers[5]:>10}"
        f"{headers[6]:>16}"
    )

    print("-" * 92)

    for row in summary:
        print(
            f'{row["prompt_mode"]:<12}'
            f'{row["difficulty"]:<10}'
            f'{row["n"]:>5}'
            f'{row["strict_valid_rate_pct"]:>10.2f}%'
            f'{row["interpretable_rate_pct"]:>10.2f}%'
            f'{row["decision_accuracy_pct"]:>9.2f}%'
            f'{row["executable_correct_rate_pct"]:>15.2f}%'
        )

    print("=" * 92)

    print(
        "\nCOMO LEER ESTAS METRICAS:\n"
        "- STRICT%: respondio EXACTAMENTE MOVE_N y era ejecutable.\n"
        "- INTERP%: aunque el formato fuera malo, se pudo entender "
        "que movimiento quiso usar.\n"
        "- ACC%: la decision interpretada coincide con el ground truth.\n"
        "- EXEC-CORRECT%: simultaneamente formato correcto + "
        "decision correcta.\n"
    )


# ============================================================
# 12. MAIN
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\nPOKEMON BLUE - OFFLINE PROMPT BENCHMARK")
    print("---------------------------------------")
    print(f"Modelo: {MODEL_ID}")
    print(f"Estados: {TOTAL_CASES}")
    print(
        f"Inferencias totales: "
        f"{TOTAL_CASES * len(PROMPT_MODES)}"
    )
    print(f"Seed: {SEED}")
    print(
        "\nNo se abrira PyBoy y no necesitas jugar ninguna batalla."
    )

    # 1. Los estados se generan UNA sola vez y son los mismos
    # para ambos prompts.
    cases = generate_cases(
        total=TOTAL_CASES,
        seed=SEED,
    )

    save_cases(cases)

    counts = defaultdict(int)
    for c in cases:
        counts[c["difficulty"]] += 1

    print(
        "\nCasos generados:",
        dict(counts),
    )

    # 2. Cargar modelo una sola vez.
    llm = LocalLLM(MODEL_ID)

    results = []
    total_runs = TOTAL_CASES * len(PROMPT_MODES)
    run_number = 0

    # 3. Mismo caso con DIRECT y STRUCTURED.
    for case in cases:
        for mode in PROMPT_MODES:
            run_number += 1

            print(
                f"\n[{run_number}/{total_runs}] "
                f'Case {case["case_id"]} | '
                f'{case["difficulty"]} | {mode}'
            )

            row = evaluate_one(
                llm=llm,
                case=case,
                mode=mode,
            )

            results.append(row)

            print(
                "  RAW:",
                repr(row["raw_response"][:150])
            )
            print(
                f'  reference={row["reference_action"]} | '
                f'strict={row["strict_action"] or "INVALID"} | '
                f'interpreted={row["interpreted_action"] or "INVALID"} | '
                f'correct={bool(row["decision_correct"])}'
            )

    # 4. Guardar resultados completos.
    write_csv(RESULTS_CSV, results)

    # 5. Guardar solo failures para revisarlos mas rapido.
    failures = [
        r for r in results
        if not int(r["executable_correct"])
    ]
    write_csv(FAILURES_CSV, failures)

    # 6. Resumen.
    summary = summarize(results)
    write_csv(SUMMARY_CSV, summary)
    print_summary(summary)

    print("\nARCHIVOS GENERADOS:")
    print(f"  Casos:      {CASES_JSON}")
    print(f"  Resultados: {RESULTS_CSV}")
    print(f"  Resumen:    {SUMMARY_CSV}")
    print(f"  Failures:   {FAILURES_CSV}")

    print(
        "\nIMPORTANTE:\n"
        "El ground truth de este benchmark es una politica ofensiva "
        "explicita: power x accuracy x STAB x type effectiveness.\n"
        "No representa toda la estrategia competitiva de Pokemon; "
        "esa limitacion debe declararse en el informe."
    )

    # Liberar memoria por limpieza.
    del llm
    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
