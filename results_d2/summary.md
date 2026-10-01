# Resultados Deliverable 2

- Modelo: `Qwen/Qwen2.5-1.5B-Instruct` (revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`), 1.54B parametros, cuda Tesla T4
- Estados: **50** (semilla 20260830, reparto {'EASY': 17, 'MEDIUM': 17, 'HARD': 16}), mismos estados para todas las estrategias
- Correcto = la accion coincide con la politica de referencia del D1 (power x accuracy x STAB x efectividad)
- Solucion evaluada: **S2 Descomposicion en palabras**; H es una referencia sin modelo

## 1. Estrategias sobre los mismos estados

| Estrategia | STRICT | ACC [IC 95%] | EXEC-CORRECT | regret | llamadas/estado | s/estado |
|---|---:|---:|---:|---:|---:|---:|
| B0 Directo (baseline) | 100.0% | 28.0% [17.5–41.7] | 28.0% | 0.333 | 1.0 | 5.29 |
| A1 Estructurado (D1) | 100.0% | 20.0% [11.2–33.0] | 20.0% | 0.42 | 1.0 | 5.81 |
| A2 Votacion x4 permutaciones | 100.0% | 30.0% [19.1–43.8] | 30.0% | 0.323 | 4.0 | 15.12 |
| A3 Chain-of-thought + formula | 56.0% | 28.0% [17.5–41.7] | 14.0% | 0.364 | 1.0 | 96.91 |
| S1 Descomposicion numerica (v1) | 100.0% | 58.0% [44.2–70.6] | 58.0% | 0.192 | 5.16 | 12.56 |
| S1+cal numerica calibrada (v1) | 100.0% | 42.0% [29.4–55.8] | 42.0% | 0.305 | 5.16 | 0.0 |
| H  Heuristica sin tipos (sin modelo) | 100.0% | 54.0% [40.4–67.0] | 54.0% | 0.222 | 0.0 | 0.0 |
| S2 Descomposicion en palabras | 100.0% | 48.0% [34.8–61.5] | 48.0% | 0.254 | 5.16 | 0.34 |

| Estrategia | EASY | MEDIUM | HARD | MOVE_1 | MOVE_2 | MOVE_3 | MOVE_4 | chi2 vs uniforme |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 Directo (baseline) | 6/17 | 6/17 | 2/16 | 14 | 23 | 9 | 4 | 15.8 (p=1.3e-03) |
| A1 Estructurado (D1) | 3/17 | 4/17 | 3/16 | 1 | 37 | 4 | 8 | 66.0 (p=3.1e-14) |
| A2 Votacion x4 permutaciones | 6/17 | 6/17 | 3/16 | 14 | 20 | 7 | 9 | 8.1 (p=4.4e-02) |
| A3 Chain-of-thought + formula | 4/17 | 5/17 | 5/16 | 11 | 17 | 7 | 13 | 4.3 (p=2.3e-01) |
| S1 Descomposicion numerica (v1) | 9/17 | 7/17 | 13/16 | 16 | 12 | 9 | 13 | 2.0 (p=5.7e-01) |
| S1+cal numerica calibrada (v1) | 5/17 | 6/17 | 10/16 | 14 | 13 | 11 | 12 | 0.4 (p=9.4e-01) |
| H  Heuristica sin tipos (sin modelo) | 7/17 | 7/17 | 13/16 | 18 | 12 | 7 | 13 | 4.9 (p=1.8e-01) |
| S2 Descomposicion en palabras | 8/17 | 7/17 | 9/16 | 13 | 15 | 10 | 12 | 1.0 (p=7.9e-01) |
| *accion optima* | | | | 18 | 8 | 14 | 10 | |

## 2. Tests pareados (McNemar exacto sobre EXEC-CORRECT, mismos estados)

Contra el baseline B0:
- A1 Estructurado (D1): gana en 3, pierde en 7, p = 3.44e-01 (n = 50)
- A2 Votacion x4 permutaciones: gana en 2, pierde en 1, p = 1.00e+00 (n = 50)
- A3 Chain-of-thought + formula: gana en 3, pierde en 10, p = 9.23e-02 (n = 50)
- S1 Descomposicion numerica (v1): gana en 17, pierde en 2, p = 7.29e-04 (n = 50)
- S1+cal numerica calibrada (v1): gana en 11, pierde en 4, p = 1.18e-01 (n = 50)
- H  Heuristica sin tipos (sin modelo): gana en 16, pierde en 3, p = 4.43e-03 (n = 50)
- S2 Descomposicion en palabras: gana en 13, pierde en 3, p = 2.13e-02 (n = 50)

S2 Descomposicion en palabras contra cada alternativa:
- vs A1 Estructurado (D1): gana en 16, pierde en 2, p = 1.31e-03
- vs A2 Votacion x4 permutaciones: gana en 12, pierde en 3, p = 3.52e-02
- vs A3 Chain-of-thought + formula: gana en 18, pierde en 1, p = 7.63e-05
- vs S1 Descomposicion numerica (v1): gana en 2, pierde en 7, p = 1.80e-01
- vs S1+cal numerica calibrada (v1): gana en 7, pierde en 4, p = 5.49e-01
- vs H  Heuristica sin tipos (sin modelo): gana en 2, pierde en 5, p = 4.53e-01

## 3. Aporta el modelo algo mas que ignorar los tipos?

- H (sin modelo, sin tipos) acierta 54.0%.
- S1 Descomposicion numerica (v1) elige lo mismo que H en 48 de 50 estados.
- S1+cal numerica calibrada (v1) elige lo mismo que H en 40 de 50 estados.
- S2 Descomposicion en palabras elige lo mismo que H en 42 de 50 estados.
- Preferencia de S1 ante una pregunta VACIA (sin tipos): {'2': 0.0011, '1': 0.01365, '0.5': 0.9039, '0': 0.0813}

## 4. Sesgo de posicion medido directamente (baseline con 4 rotaciones)

- Estados con 4 respuestas validas: 49 de 50
- Eligio la MISMA casilla mostrada en las 4 rotaciones: 0
- Eligio el MISMO movimiento en las 4 rotaciones: 8
- Casillas elegidas (200 respuestas posibles): {'MOVE_1': 39, 'MOVE_2': 76, 'MOVE_3': 71, 'MOVE_4': 13}, chi2 = 52.4, p = 2.5e-11

## 5. Hechos de tipo que aporto el modelo

**S1 Descomposicion numerica (v1)**
- Pares correctos: 21/122 = 17.2% (258 consultas; el resto sale de cache)
- Acierto por multiplicador verdadero: {'2.0': '0/18', '1.0': '0/80', '0.5': '21/21', '0.0': '0/3'}
- Respuestas que dio (por par): {'0.5': 122}; prob. media de su respuesta mas comun: 0.972
- Cuando NO dijo x1, acerto 21/122. Responder siempre x1 (lo que hace H) acertaria 80/122 pares.
- Pares del mismo tipo (p. ej. Agua contra Agua): 9; llamo 'super efectivo' sin serlo a: ninguno
- Decisiones resueltas por desempate: 3 (2 correctas)

**S1+cal numerica calibrada (v1)**
- Pares correctos: 22/122 = 18.0% (258 consultas; el resto sale de cache)
- Acierto por multiplicador verdadero: {'2.0': '0/18', '1.0': '5/80', '0.5': '17/21', '0.0': '0/3'}
- Respuestas que dio (por par): {'2.0': 1, '1.0': 8, '0.5': 113}; prob. media de su respuesta mas comun: 0.484
- Cuando NO dijo x1, acerto 17/114. Responder siempre x1 (lo que hace H) acertaria 80/122 pares.
- Pares del mismo tipo (p. ej. Agua contra Agua): 9; llamo 'super efectivo' sin serlo a: Electric
- Decisiones resueltas por desempate: 3 (1 correctas)

**S2 Descomposicion en palabras**
- Pares correctos: 74/122 = 60.7% (258 consultas; el resto sale de cache)
- Acierto por multiplicador verdadero: {'2.0': '2/18', '1.0': '72/80', '0.5': '0/21', '0.0': '0/3'}
- Respuestas que dio (por par): {'2.0': 13, '1.0': 106, '0.5': 3}
- Cuando NO dijo x1, acerto 2/16. Responder siempre x1 (lo que hace H) acertaria 80/122 pares.
- Pares del mismo tipo (p. ej. Agua contra Agua): 9; llamo 'super efectivo' sin serlo a: Electric, Poison, Psychic, Rock, Water
- Decisiones resueltas por desempate: 3 (0 correctas)

Hechos erroneos de la solucion (S2 Descomposicion en palabras):

| Ataque -> Defensa | Modelo | Gen I | Coincide con tabla moderna | Respuesta |
|---|---:|---:|:---:|---|
| Bug -> Poison | 1.0 | 2.0 | no | normal damage |
| Electric -> Electric | 2.0 | 0.5 | no | super effective |
| Electric -> Fire | 2.0 | 1.0 | no | super effective |
| Electric -> Flying | 1.0 | 2.0 | no | normal damage |
| Electric -> Grass | 1.0 | 0.5 | no | normal damage |
| Electric -> Ground | 1.0 | 0.0 | no | normal damage |
| Electric -> Ice | 2.0 | 1.0 | no | super effective |
| Electric -> Normal | 2.0 | 1.0 | no | super effective |
| Fighting -> Flying | 1.0 | 0.5 | no | normal damage |
| Fighting -> Ghost | 1.0 | 0.0 | no | normal damage |
| Fighting -> Ice | 1.0 | 2.0 | no | normal damage |
| Fighting -> Poison | 1.0 | 0.5 | no | normal damage |
| Fire -> Bug | 1.0 | 2.0 | no | normal damage |
| Fire -> Ice | 1.0 | 2.0 | no | normal damage |
| Fire -> Rock | 1.0 | 0.5 | no | normal damage |
| Fire -> Water | 1.0 | 0.5 | no | normal damage |
| Flying -> Electric | 1.0 | 0.5 | no | normal damage |
| Flying -> Rock | 1.0 | 0.5 | no | normal damage |
| Grass -> Fire | 2.0 | 0.5 | no | super effective |
| Grass -> Flying | 1.0 | 0.5 | no | normal damage |
| Grass -> Ground | 1.0 | 2.0 | no | normal damage |
| Grass -> Poison | 1.0 | 0.5 | no | normal damage |
| Grass -> Psychic | 0.5 | 1.0 | no | not very effective |
| Grass -> Water | 1.0 | 2.0 | no | normal damage |
| Ice -> Fire | 2.0 | 1.0 | no | super effective |
| Ice -> Flying | 1.0 | 2.0 | no | normal damage |
| Ice -> Grass | 1.0 | 2.0 | no | normal damage |
| Ice -> Ground | 1.0 | 2.0 | no | normal damage |
| Ice -> Psychic | 0.5 | 1.0 | no | not very effective |
| Ice -> Water | 2.0 | 0.5 | no | super effective |
| Normal -> Ghost | 1.0 | 0.0 | no | normal damage |
| Normal -> Rock | 1.0 | 0.5 | no | normal damage |
| Poison -> Ghost | 1.0 | 0.5 | no | normal damage |
| Poison -> Grass | 1.0 | 2.0 | no | normal damage |
| Poison -> Poison | 2.0 | 0.5 | no | super effective |
| Poison -> Psychic | 0.5 | 1.0 | no | not very effective |
| Poison -> Rock | 1.0 | 0.5 | no | normal damage |
| Psychic -> Fighting | 1.0 | 2.0 | no | normal damage |
| Psychic -> Poison | 1.0 | 2.0 | no | normal damage |
| Psychic -> Psychic | 2.0 | 0.5 | no | super effective |
| Rock -> Fighting | 1.0 | 0.5 | no | normal damage |
| Rock -> Ground | 1.0 | 0.5 | no | normal damage |
| Rock -> Ice | 1.0 | 2.0 | no | normal damage |
| Rock -> Rock | 2.0 | 1.0 | no | super effective |
| Water -> Grass | 1.0 | 0.5 | no | normal damage |
| Water -> Ground | 1.0 | 2.0 | no | normal damage |
| Water -> Rock | 1.0 | 2.0 | no | normal damage |
| Water -> Water | 2.0 | 0.5 | no | super effective |

## 6. Anatomia de los fallos de la solucion

- Caso 32 (MEDIUM): eligio MOVE_1, optimo MOVE_3, regret 1.0. Causa: hecho de tipo incorrecto. Thunderbolt: Electric->Ground dijo 1.0, Gen I es 0.0; Razor Leaf: Grass->Ground dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 46 (HARD): eligio MOVE_2, optimo MOVE_1, regret 0.2895. Causa: hecho de tipo incorrecto. Flamethrower: Fire->Rock dijo 1.0, Gen I es 0.5; Rock Slide: Rock->Ground dijo 1.0, Gen I es 0.5; Rock Slide: Rock->Rock dijo 2.0, Gen I es 1.0; Strength: Normal->Rock dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 33 (MEDIUM): eligio MOVE_2, optimo MOVE_1, regret 0.2154. Causa: hecho de tipo incorrecto. Psybeam: Psychic->Poison dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 15 (EASY): eligio MOVE_2, optimo MOVE_3, regret 0.7404. Causa: hecho de tipo incorrecto. Rock Slide: Rock->Fighting dijo 1.0, Gen I es 0.5; Psybeam: Psychic->Fighting dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 24 (MEDIUM): eligio MOVE_4, optimo MOVE_1, regret 0.35. Causa: hecho de tipo incorrecto. Confusion: Psychic->Fighting dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 3 (EASY): eligio MOVE_4, optimo MOVE_1, regret 0.7143. Causa: hecho de tipo incorrecto. Hydro Pump: Water->Water dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 27 (MEDIUM): eligio MOVE_1, optimo MOVE_3, regret 0.2344. Causa: hecho de tipo incorrecto. Razor Leaf: Grass->Water dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 31 (MEDIUM): eligio MOVE_3, optimo MOVE_1, regret 0.4667. Causa: hecho de tipo incorrecto. Blizzard: Ice->Water dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 8 (EASY): eligio MOVE_2, optimo MOVE_1, regret 0.7143. Causa: hecho de tipo incorrecto. Hydro Pump: Water->Water dijo 2.0, Gen I es 0.5; Water Gun: Water->Water dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 29 (MEDIUM): eligio MOVE_4, optimo MOVE_1, regret 0.35. Causa: hecho de tipo incorrecto. Confusion: Psychic->Poison dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 4 (EASY): eligio MOVE_1, optimo MOVE_3, regret 0.5. Causa: hecho de tipo incorrecto. Thunderbolt: Electric->Flying dijo 1.0, Gen I es 2.0; Vine Whip: Grass->Flying dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 5 (EASY): eligio MOVE_3, optimo MOVE_4, regret 0.6579. Causa: hecho de tipo incorrecto. Psybeam: Psychic->Psychic dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 37 (HARD): eligio MOVE_4, optimo MOVE_1, regret 0.1204. Causa: hecho de tipo incorrecto. Blizzard: Ice->Psychic dijo 0.5, Gen I es 1.0; Scratch: Normal->Ghost dijo 1.0, Gen I es 0.0. Con los hechos corregidos acierta: si.
- Caso 47 (HARD): eligio MOVE_2, optimo MOVE_3, regret 0.0714. Causa: hecho de tipo incorrecto. Quick Attack: Normal->Ghost dijo 1.0, Gen I es 0.0; Sludge: Poison->Ghost dijo 1.0, Gen I es 0.5; Submission: Fighting->Ghost dijo 1.0, Gen I es 0.0. Con los hechos corregidos acierta: si.
- Caso 38 (HARD): eligio MOVE_2, optimo MOVE_1, regret 0.4062. Causa: hecho de tipo incorrecto. ThunderShock: Electric->Normal dijo 2.0, Gen I es 1.0; Surf: Water->Water dijo 2.0, Gen I es 0.5; Vine Whip: Grass->Water dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 34 (MEDIUM): eligio MOVE_4, optimo MOVE_1, regret 0.3077. Causa: hecho de tipo incorrecto. Sludge: Poison->Grass dijo 1.0, Gen I es 2.0; ThunderShock: Electric->Grass dijo 1.0, Gen I es 0.5; Water Gun: Water->Grass dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 17 (EASY): eligio MOVE_2, optimo MOVE_1, regret 0.4947. Causa: hecho de tipo incorrecto. Flamethrower: Fire->Bug dijo 1.0, Gen I es 2.0; Ember: Fire->Bug dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 12 (EASY): eligio MOVE_1, optimo MOVE_2, regret 0.75. Causa: hecho de tipo incorrecto. Thunderbolt: Electric->Grass dijo 1.0, Gen I es 0.5; Ice Beam: Ice->Grass dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 35 (HARD): eligio MOVE_1, optimo MOVE_3, regret 0.05. Causa: hecho de tipo incorrecto. Thunderbolt: Electric->Grass dijo 1.0, Gen I es 0.5; Slash: Normal->Rock dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 20 (MEDIUM): eligio MOVE_1, optimo MOVE_3, regret 0.3538. Causa: hecho de tipo incorrecto. Thunder: Electric->Fire dijo 2.0, Gen I es 1.0. Con los hechos corregidos acierta: si.
- Caso 44 (HARD): eligio MOVE_2, optimo MOVE_4, regret 0.7059. Causa: hecho de tipo incorrecto. Psychic: Psychic->Fighting dijo 1.0, Gen I es 2.0; ThunderShock: Electric->Ice dijo 2.0, Gen I es 1.0; Fire Blast: Fire->Ice dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 43 (HARD): eligio MOVE_3, optimo MOVE_4, regret 0.537. Causa: hecho de tipo incorrecto. Razor Leaf: Grass->Psychic dijo 0.5, Gen I es 1.0; Razor Leaf: Grass->Poison dijo 1.0, Gen I es 0.5; Ice Beam: Ice->Psychic dijo 0.5, Gen I es 1.0; Confusion: Psychic->Psychic dijo 2.0, Gen I es 0.5; Confusion: Psychic->Poison dijo 1.0, Gen I es 2.0; Blizzard: Ice->Psychic dijo 0.5, Gen I es 1.0. Con los hechos corregidos acierta: si.
- Caso 18 (MEDIUM): eligio MOVE_4, optimo MOVE_1, regret 0.2. Causa: hecho de tipo incorrecto. Ice Beam: Ice->Water dijo 2.0, Gen I es 0.5; Hydro Pump: Water->Water dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 6 (EASY): eligio MOVE_2, optimo MOVE_4, regret 0.7308. Causa: hecho de tipo incorrecto. Sludge: Poison->Rock dijo 1.0, Gen I es 0.5; Slash: Normal->Rock dijo 1.0, Gen I es 0.5; Rock Throw: Rock->Rock dijo 2.0, Gen I es 1.0; BubbleBeam: Water->Rock dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 21 (MEDIUM): eligio MOVE_3, optimo MOVE_2, regret 0.75. Causa: hecho de tipo incorrecto. Psybeam: Psychic->Poison dijo 1.0, Gen I es 2.0; Sludge: Poison->Poison dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 11 (EASY): eligio MOVE_1, optimo MOVE_3, regret 1.0. Causa: hecho de tipo incorrecto. Strength: Normal->Ghost dijo 1.0, Gen I es 0.0; Take Down: Normal->Ghost dijo 1.0, Gen I es 0.0; Sludge: Poison->Ghost dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.

Resumen: {'hecho de tipo incorrecto': 26}; corregibles con hechos correctos: 26/26
