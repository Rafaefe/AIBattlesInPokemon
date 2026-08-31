# Modelos de lenguaje pequeños para decidir en combate en Pokémon Blue

Deliverable 1 · Generative Artificial Intelligence (580694), Primavera 2026 · Universidad de Concepción

Equipo: Nombre 1 · Nombre 2 · Nombre 3 · Nombre 4

## Resumen

Este repositorio contiene el benchmark, los resultados crudos y el paper del
Deliverable 1. Evaluamos si un LLM pequeño (≤8B) puede actuar como módulo de
decisión de combate en Pokémon Blue, comparando un prompt directo (`DIRECT`)
contra un prompt estructurado con salida forzada (`STRUCTURED`) sobre 30
estados sintéticos de batalla (10 EASY / 10 MEDIUM / 10 HARD).

El paper completo está en [`paper/main.pdf`](paper/main.pdf).

## Estructura del repositorio

```
.
├── paper/
│   ├── main.tex              # fuente LaTeX del póster (1 página)
│   └── main.pdf              # PDF compilado
├── src/
│   └── pokemon_benchmark_final.py   # benchmark offline (genera casos, corre el LLM, calcula métricas)
├── data/
│   └── benchmark_cases.json  # los 30 estados sintéticos usados (reproducibles)
├── results/
│   ├── benchmark_results.csv # una fila por (caso, modo de prompt): 60 filas
│   ├── benchmark_failures.csv# subconjunto de respuestas incorrectas/no ejecutables
│   └── benchmark_summary.csv # métricas agregadas por modo de prompt y dificultad
└── requirements.txt
```

## Reproducir el benchmark

```bash
pip install -r requirements.txt
python src/pokemon_benchmark_final.py
```

El script es determinista (decodificación greedy, semilla fija) y **no**
requiere PyBoy ni el ROM: los 30 estados de batalla se generan de forma
sintética y reproducible. La demo con el emulador se mantiene en un módulo
aparte para no mezclar errores del emulador con fallos del modelo (ver
Sección 7 del paper).

## Métricas reportadas

| Métrica | Definición |
|---|---|
| `strict_valid` | La respuesta es exactamente `MOVE_N` y es ejecutable |
| `interpretable` | Se puede recuperar la intención aunque no sea estricta |
| `decision_correct` | Coincide con el ground truth determinista |
| `executable_correct` | Es ejecutable **y** coincide con el ground truth |
| `regret` | Score óptimo perdido: `best_score - chosen_score` |

El ground truth se calcula como `score = potencia × precisión × STAB ×
efectividad`, con `score = 0` si `PP = 0` (ver Sección 1 del paper).

## Cómo citamos este repositorio en el paper

El póster referencia este repositorio como evidencia y fuente de los cuatro
archivos de resultados. Para que el enlace sea estable, recomendamos:

1. Congelar los resultados de este entregable con un tag, p. ej. `v1-deliverable1`.
2. Enlazar en el paper a ese tag (o a un commit específico), no a `main`,
   para que lecturas futuras vean exactamente los datos que sustentan las
   cifras reportadas.

## Licencia

Código, datos generados y paper bajo licencia MIT (ver [`LICENSE`](LICENSE)).

Esta licencia **no cubre** el contenido de Pokémon Blue: los nombres de
movimientos, tipos y valores de juego usados para construir los estados de
batalla son propiedad de Nintendo / Creatures Inc. / GAME FREAK inc. y se
usan solo con fines educativos. El ROM no se incluye ni se distribuye en
este repositorio. Los modelos evaluados (Qwen2.5, Llama 3.2, Phi-3.5-mini)
se referencian por nombre bajo sus propias licencias; sus pesos no se
redistribuyen aquí.
