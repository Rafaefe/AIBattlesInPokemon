# Pokémon Blue con un modelo de lenguaje pequeño

**Generative Artificial Intelligence (580694), Primavera 2026 — Universidad de Concepción**

Equipo: `Pedro Dañobeytia · Rafael Fernández · Cristian González · Daniel González`

Un modelo de lenguaje pequeño y de pesos abiertos actúa como **módulo de decisión de combate**
de un agente de Pokémon Blue. Recibe el estado del combate (tipos, % de HP y velocidad de ambos
Pokémon, más cuatro movimientos con tipo, potencia, precisión y PP) y debe devolver una etiqueta
ejecutable: `MOVE_1`, `MOVE_2`, `MOVE_3` o `MOVE_4`.

**Respuesta correcta** (la misma en ambas entregas): el movimiento que maximiza

```
score = potencia × (precisión/100) × STAB × efectividad de tipo      (score = 0 si PP = 0)
```

con la tabla de tipos de la **Generación I**.

---

## Deliverable 2 — la solución

### El fallo que ataca

En el D1, Qwen2.5-1.5B con prompt estructurado acertaba 16,7 % — por debajo del azar — porque
**respondía por posición y no por estado**: elegía `MOVE_2` en 20 de 29 respuestas y nunca `MOVE_1`.
El paso que fallaba era *combinar cinco atributos sobre cuatro candidatos a la vez*.

### La intervención: descomposición + herramienta

```
estado ──► por cada movimiento usable y cada tipo del rival:
             "how effective is a X-type attack against a Y-type Pokemon?"
             └─► Qwen2.5-1.5B responde "super effective" / "normal damage" / ...
             └─► parser fijo ──► ×2 / ×1 / ×0,5 / ×0
        ──► calculadora: potencia × precisión × STAB × efectividad
        ──► máximo ──► MOVE_N
```

- El modelo **nunca ve los cuatro movimientos juntos**: no hay posición a la que sesgarse.
- Cada pregunta es **un solo hecho** de la tabla de tipos; la combinación la hace la calculadora.
- **El modelo es la única fuente de tipos**: la tabla vive en `d2/ground_truth.py`, que solo usa el
  evaluador; un test verifica que `d2/strategies.py` no la importa ni directa ni indirectamente.
- Para medir si el modelo **aporta de verdad**, todo se compara también contra **H**: la misma
  calculadora con todas las efectividades en ×1 (ignora los tipos; no usa el modelo).

### Qué pasó con la primera versión (S1) y por qué existe S2

La primera versión (S1) pedía el multiplicador en números (`2 / 1 / 0.5 / 0`, decodificación
restringida). En la corrida real **el modelo respondió "0.5" en los 122 pares** (probabilidad media
0,97), incluso Agua contra Fuego, y "0.5" con probabilidad 0,90 ante una pregunta **vacía**: la
respuesta la decidía el formato, no los tipos. Con todas las efectividades iguales, S1 se reduce a H
y **elige lo mismo que H en 48 de 50 estados**: su 58 % no es mérito del modelo. S2 hace la misma
pregunta con las palabras del propio juego. Ambas versiones se reportan.

### Qué se compara (mismos 50 estados, mismo criterio)

| Id | Estrategia | Qué cambia |
|---|---|---|
| B0 | **Directo (baseline)** | prompt directo del D1 + pedir la etiqueta `MOVE_N` |
| A1 | Estructurado | prompt estructurado del D1, sin cambios |
| A2 | Votación ×4 | B0 con los movimientos rotados 4 veces + voto (ataca solo la posición) |
| A3 | Chain-of-thought | la fórmula completa en el prompt; el modelo razona y combina solo |
| S1 | Descomposición numérica (v1) | hechos de tipos como número 2/1/0.5/0 |
| S1+cal | S1 calibrada | S1 descontando la preferencia a priori del modelo por cada número |
| H | **Sin modelo** | la calculadora ignorando los tipos: referencia para saber si el modelo aporta |
| **S2** | **Descomposición en palabras** | **la solución** |

Además, B0, H y S2 se evalúan en **50 estados nuevos** (semilla `20260927`, fijada después de
diseñar S2 y antes de correrla) para confirmar el resultado fuera de los estados donde se
diagnosticó S1. Resultados: `results_d2/summary.md` y `results_d2_holdout/summary.md`.

### Resultados

| | 50 originales (semilla 20260830) | 50 nuevos (semilla 20260927) |
|---|---:|---:|
| B0 baseline | 28 % [18–42] | 40 % [28–54] |
| H sin modelo (ignora tipos) | 54 % [40–67] | 76 % [63–86] |
| **S2 solución** | **48 % [35–62]** | **58 % [44–71]** |
| S2 vs B0 (gana/pierde, McNemar exacto) | 13/3, p = 0,021 | 14/5, p = 0,064 |
| S2 vs H (gana/pierde) | 2/5, p = 0,45 | 0/9, p = 0,004 |

**Lo que funciona.** S2 elimina el sesgo de posición del D1 (χ² contra uniforme: B0 p = 0,001,
S2 p = 0,79) y supera al baseline en ambos conjuntos (significativo en los originales, al borde en
los nuevos).

**Lo que no, y por qué.** La descomposición deja el resultado en manos de un solo tipo de hecho —
la tabla de tipos— y **Qwen2.5-1.5B no la sabe**:

- respondió "normal damage" en 106 de 122 pares (87 %);
- cuando dijo otra cosa acertó 2 de 16 (en los estados nuevos, 1 de 12);
- llamó "super effective" a pares del mismo tipo (Agua–Agua, Eléctrico–Eléctrico, Psíquico–Psíquico,
  Veneno–Veneno, Roca–Roca), que en Gen I no lo son;
- por efectividad real: ×2 2/18, ×1 72/80, ×0,5 0/21, ×0 0/3;
- ninguno de sus 48 errores es el valor de Gen II en adelante: no confunde generaciones, no sabe.

Responder siempre ×1 acierta 80/122 pares; el modelo, 74/122. Por eso H, que ignora los tipos,
decide igual o mejor que S2. Los 26 fallos de S2 en los 50 originales se deben a un hecho de tipo
incorrecto y **los 26 se corrigen con los hechos verdaderos** (misma calculadora): el cuello de
botella pasó de *combinar* (D1) a *saber* (D2). Camino para el D3: enseñarle la tabla al modelo
(ajuste fino); darla por recuperación resolvería el paso pero haría innecesario al modelo en él.

### Cómo reproducir lo que muestra el video

```bash
pip install -r requirements-d2.txt          # torch se usa el que ya tengas

python -m pytest -q tests                   # lógica, con modelo falso (sin GPU, <2 s)
python -m d2.evaluate                        # 50 estados × 7 estrategias -> results_d2/ (se reanuda)
python -m d2.evaluate --holdout              # B0 y S2 en 50 estados nuevos -> results_d2_holdout/
python -m d2.report results_d2               # recalcula todas las cifras desde los archivos
python -m d2.demo                            # estado NUEVO (semilla del reloj, se imprime)
python -m d2.demo --seed 482913              # reproduce exactamente un estado del video
python -m d2.demo --replay 17                # repite el estado 17 del conjunto de evaluación
```

Si ya existe `results_d2/` de una corrida anterior, **`python -m d2.rerun`** hace solo lo que falta
(S2 y los 50 estados nuevos) y actualiza las cifras del documento.

También se puede todo desde Colab con `notebooks/D2_colab.ipynb` (GPU T4).

`d2.demo` muestra, sobre el mismo estado, la respuesta cruda del baseline, cada pregunta que la
solución le hace al modelo con **las palabras que respondió**, la tabla de la calculadora y, al final,
el juez (tabla verdadera) y la referencia H.

**Configuración:** `Qwen/Qwen2.5-1.5B-Instruct` (revisión `989aa7980e…`, queda en
`results_d2/run_meta.json`), decodificación greedy, float32, `n = 50`, semilla `20260830` (la del D1),
reparto 17 EASY / 17 MEDIUM / 16 HARD. **Hardware:** S2 y los 50 estados nuevos (B0, H y S2 en la
misma sesión) corrieron en **Colab, Tesla T4**; B0, A1–A3, S1 y S1+cal de los 50 originales
corrieron antes en **CPU**. Mismos pesos y decodificación; cada sesión deja su hardware en
`run_meta.json → sessions`. En la T4, S2 tarda 0,10 s por estado y B0 0,33 s.

### Documento técnico y video

Las cifras del documento se generan desde los archivos, no a mano:

```bash
python report/fill_d2.py results_d2 results_d2_holdout    # escribe report/d2_numbers.tex
cd report && pdflatex deliverable2_es.tex && pdflatex deliverable2_es.tex
```

Las frases que dependen del resultado (por ejemplo, si S2 supera a H) también se escriben desde
los datos. El caso de fallo lo elige una regla fija (el primer fallo en el orden de evaluación
causado por un hecho de otra generación; si no hay, el primer fallo): es el **estado 32**, donde el
modelo dijo "normal damage" para Eléctrico contra Tierra (en Gen I, ×0) y eligió Thunderbolt, que
no hace daño. Guion del video: `docs/guion_video.md`.

### Garantías verificables

| Test | Qué garantiza |
|---|---|
| `test_generator_reproduces_d1_cases_exactly` | con `n=30` el generador produce **exactamente** los 30 estados del D1 |
| `test_solution_never_sees_the_type_chart` | la solución no importa la tabla de tipos (ni transitivamente) |
| `test_strategies_only_receive_public_fields` | ninguna estrategia ve la respuesta ni la dificultad |
| `test_solution_with_perfect_facts_is_always_right` | con hechos correctos la calculadora acierta 50/50: todo error de S viene de un hecho que dio el modelo |
| `test_calibration_removes_a_constant_label_preference` | la calibración corrige un sesgo constante hacia una respuesta |
| `test_words_solution_with_perfect_facts_is_always_right` | S2 con hechos correctos acierta 50/50 |
| `test_constant_answer_collapses_to_the_no_type_heuristic` | si el modelo responde siempre lo mismo, el reporte muestra que S2 = H (lo que le pasó a S1) |

### Archivos que produce la evaluación (`results_d2/`)

| Archivo | Contenido |
|---|---|
| `cases.json` | los 50 estados con su respuesta correcta |
| `decisions.jsonl` | una fila por (estrategia, estado): respuesta cruda, acción, acierto, llamadas, tiempo y la traza completa |
| `run_meta.json` | modelo, revisión, GPU, versiones de librerías y tiempos |
| `summary.md` / `summary.json` | métricas, intervalos de confianza, tests pareados, sesgo de posición, hechos erróneos y anatomía de cada fallo |

### Estructura

```
d2/
  ground_truth.py   tabla de tipos Gen I + política de referencia    (solo evaluación)
  states.py         generador de estados (idéntico al D1)             (solo evaluación)
  render.py         cómo se le muestra el estado al modelo (igual al D1)
  parsing.py        parsers de salida del D1 + línea FINAL para CoT
  llm.py            modelo local: generate() greedy y choose() restringido
  calculator.py     la herramienta: aritmética, sin tabla de tipos
  strategies.py     B0, A1, A2, A3, S1, S1+cal, S2
  evaluate.py       corre todo sobre los mismos estados (reanudable)
  report.py         métricas y análisis desde los archivos, sin modelo
  demo.py           demo para el video y replay de casos
  rerun.py          completa una corrida anterior (S2 + 50 estados nuevos)
tests/              tests de lógica con modelos falsos
notebooks/          D2_colab.ipynb
report/             pósters del D1 y documento técnico del D2 (LaTeX)
```

---

## Deliverable 1 — el diagnóstico

Piloto sobre 30 estados con Qwen2.5-1.5B-Instruct, prompts DIRECT y STRUCTURED.

| Prompt | STRICT | INTERP | ACC | EXEC-CORRECT |
|---|---:|---:|---:|---:|
| DIRECT | 0,0 % | 36,7 % | 3,3 % | 0,0 % |
| STRUCTURED | 96,7 % | 96,7 % | 16,7 % | 16,7 % |

El prompt estructurado arregló el formato, no la decisión: el modelo respondía por posición
(χ²(3) = 31,8; p < 10⁻⁶) y una heurística que ignora los tipos acertaba 63,3 %.

```bash
python benchmark/pokemon_benchmark_final.py          # corrida del D1 (requiere el modelo)
python analysis/analyze_results.py                   # reproduce las cifras del póster del D1
```

Archivos del D1: `benchmark/`, `analysis/`, `results/`, `report/deliverable1*.{tex,pdf}`.

### Modelos candidatos (D1) y fuentes de sus benchmarks

| Modelo | Parámetros | MMLU | IFEval | GSM8K |
|---|---:|---:|---:|---:|
| **Qwen2.5-1.5B-Instruct** (elegido en D2) | 1,5 B | 50,7 | 42,5 | 73,2 |
| Llama-3.2-3B-Instruct | 3,2 B | 63,4 | 77,4 | 77,7 |
| Phi-3.5-mini-instruct | 3,8 B | 69,0 | n.r. | 86,2 |

- Qwen2.5 — <https://qwenlm.github.io/blog/qwen2.5-llm/>
- Llama 3.2 — <https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/MODEL_CARD.md>
- Phi-3.5-mini — <https://huggingface.co/microsoft/Phi-3.5-mini-instruct>
