# Resultados Deliverable 2

- Modelo: `Qwen/Qwen2.5-1.5B-Instruct` (revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`), 1.54B parametros, cuda Tesla T4
- Estados: **50** (semilla 20260927, reparto {'EASY': 17, 'MEDIUM': 17, 'HARD': 16}), mismos estados para todas las estrategias
- Correcto = la accion coincide con la politica de referencia del D1 (power x accuracy x STAB x efectividad)
- Solucion evaluada: **S2 Descomposicion en palabras**; H es una referencia sin modelo

## 1. Estrategias sobre los mismos estados

| Estrategia | STRICT | ACC [IC 95%] | EXEC-CORRECT | regret | llamadas/estado | s/estado |
|---|---:|---:|---:|---:|---:|---:|
| B0 Directo (baseline) | 100.0% | 40.0% [27.6–53.8] | 40.0% | 0.258 | 1.0 | 0.33 |
| H  Heuristica sin tipos (sin modelo) | 100.0% | 76.0% [62.6–85.7] | 76.0% | 0.114 | 0.0 | 0.0 |
| S2 Descomposicion en palabras | 100.0% | 58.0% [44.2–70.6] | 58.0% | 0.19 | 5.12 | 0.1 |

| Estrategia | EASY | MEDIUM | HARD | MOVE_1 | MOVE_2 | MOVE_3 | MOVE_4 | chi2 vs uniforme |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 Directo (baseline) | 7/17 | 7/17 | 6/16 | 12 | 15 | 21 | 2 | 15.1 (p=1.7e-03) |
| H  Heuristica sin tipos (sin modelo) | 14/17 | 10/17 | 14/16 | 12 | 15 | 9 | 14 | 1.7 (p=6.4e-01) |
| S2 Descomposicion en palabras | 13/17 | 5/17 | 11/16 | 13 | 10 | 12 | 15 | 1.0 (p=7.9e-01) |
| *accion optima* | | | | 14 | 20 | 6 | 10 | |

## 2. Tests pareados (McNemar exacto sobre EXEC-CORRECT, mismos estados)

Contra el baseline B0:
- H  Heuristica sin tipos (sin modelo): gana en 20, pierde en 2, p = 1.21e-04 (n = 50)
- S2 Descomposicion en palabras: gana en 14, pierde en 5, p = 6.36e-02 (n = 50)

S2 Descomposicion en palabras contra cada alternativa:
- vs H  Heuristica sin tipos (sin modelo): gana en 0, pierde en 9, p = 3.91e-03

## 3. Aporta el modelo algo mas que ignorar los tipos?

- H (sin modelo, sin tipos) acierta 76.0%.
- S2 Descomposicion en palabras elige lo mismo que H en 41 de 50 estados.

## 5. Hechos de tipo que aporto el modelo

**S2 Descomposicion en palabras**
- Pares correctos: 68/117 = 58.1% (256 consultas; el resto sale de cache)
- Acierto por multiplicador verdadero: {'2.0': '1/18', '1.0': '67/74', '0.5': '0/22', '0.0': '0/3'}
- Respuestas que dio (por par): {'2.0': 7, '1.0': 105, '0.5': 5}
- Cuando NO dijo x1, acerto 1/12. Responder siempre x1 (lo que hace H) acertaria 74/117 pares.
- Pares del mismo tipo (p. ej. Agua contra Agua): 6; llamo 'super efectivo' sin serlo a: Electric, Psychic, Water
- Decisiones resueltas por desempate: 0 (0 correctas)

Hechos erroneos de la solucion (S2 Descomposicion en palabras):

| Ataque -> Defensa | Modelo | Gen I | Coincide con tabla moderna | Respuesta |
|---|---:|---:|:---:|---|
| Bug -> Fighting | 1.0 | 0.5 | no | normal damage |
| Bug -> Fire | 1.0 | 0.5 | no | normal damage |
| Bug -> Grass | 1.0 | 2.0 | no | normal damage |
| Bug -> Poison | 1.0 | 2.0 | no | normal damage |
| Electric -> Electric | 2.0 | 0.5 | no | super effective |
| Electric -> Flying | 1.0 | 2.0 | no | normal damage |
| Electric -> Grass | 1.0 | 0.5 | no | normal damage |
| Fighting -> Bug | 1.0 | 0.5 | no | normal damage |
| Fighting -> Poison | 1.0 | 0.5 | no | normal damage |
| Fighting -> Psychic | 1.0 | 0.5 | no | normal damage |
| Fighting -> Rock | 1.0 | 2.0 | no | normal damage |
| Fire -> Bug | 1.0 | 2.0 | no | normal damage |
| Fire -> Ice | 1.0 | 2.0 | no | normal damage |
| Fire -> Psychic | 0.5 | 1.0 | no | not very effective |
| Fire -> Rock | 1.0 | 0.5 | no | normal damage |
| Fire -> Water | 1.0 | 0.5 | no | normal damage |
| Flying -> Bug | 1.0 | 2.0 | no | normal damage |
| Flying -> Electric | 1.0 | 0.5 | no | normal damage |
| Flying -> Fighting | 1.0 | 2.0 | no | normal damage |
| Flying -> Rock | 1.0 | 0.5 | no | normal damage |
| Ghost -> Psychic | 1.0 | 0.0 | no | normal damage |
| Grass -> Flying | 1.0 | 0.5 | no | normal damage |
| Grass -> Grass | 1.0 | 0.5 | no | normal damage |
| Grass -> Poison | 1.0 | 0.5 | no | normal damage |
| Grass -> Psychic | 0.5 | 1.0 | no | not very effective |
| Grass -> Rock | 1.0 | 2.0 | no | normal damage |
| Grass -> Water | 1.0 | 2.0 | no | normal damage |
| Ground -> Bug | 1.0 | 0.5 | no | normal damage |
| Ground -> Flying | 1.0 | 0.0 | no | normal damage |
| Ground -> Poison | 1.0 | 2.0 | no | normal damage |
| Ground -> Rock | 1.0 | 2.0 | no | normal damage |
| Ice -> Fire | 2.0 | 1.0 | no | super effective |
| Ice -> Grass | 1.0 | 2.0 | no | normal damage |
| Ice -> Psychic | 0.5 | 1.0 | no | not very effective |
| Ice -> Water | 2.0 | 0.5 | no | super effective |
| Normal -> Ghost | 1.0 | 0.0 | no | normal damage |
| Normal -> Rock | 1.0 | 0.5 | no | normal damage |
| Poison -> Psychic | 0.5 | 1.0 | no | not very effective |
| Poison -> Rock | 1.0 | 0.5 | no | normal damage |
| Psychic -> Fighting | 1.0 | 2.0 | no | normal damage |
| Psychic -> Poison | 1.0 | 2.0 | no | normal damage |
| Psychic -> Psychic | 2.0 | 0.5 | no | super effective |
| Rock -> Ground | 1.0 | 0.5 | no | normal damage |
| Rock -> Ice | 1.0 | 2.0 | no | normal damage |
| Rock -> Psychic | 0.5 | 1.0 | no | not very effective |
| Water -> Grass | 1.0 | 0.5 | no | normal damage |
| Water -> Ground | 1.0 | 2.0 | no | normal damage |
| Water -> Ice | 2.0 | 1.0 | no | super effective |
| Water -> Water | 2.0 | 0.5 | no | super effective |

## 6. Anatomia de los fallos de la solucion

- Caso 10 (EASY): eligio MOVE_4, optimo MOVE_1, regret 0.4769. Causa: hecho de tipo incorrecto. Psybeam: Psychic->Fighting dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 48 (HARD): eligio MOVE_3, optimo MOVE_1, regret 0.1667. Causa: hecho de tipo incorrecto. Blizzard: Ice->Psychic dijo 0.5, Gen I es 1.0; Psychic: Psychic->Poison dijo 1.0, Gen I es 2.0; Psychic: Psychic->Psychic dijo 2.0, Gen I es 0.5; Low Kick: Fighting->Poison dijo 1.0, Gen I es 0.5; Low Kick: Fighting->Psychic dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 46 (HARD): eligio MOVE_3, optimo MOVE_2, regret 0.6875. Causa: hecho de tipo incorrecto. Drill Peck: Flying->Bug dijo 1.0, Gen I es 2.0; Earthquake: Ground->Bug dijo 1.0, Gen I es 0.5; BubbleBeam: Water->Ground dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 29 (MEDIUM): eligio MOVE_1, optimo MOVE_2, regret 0.2842. Causa: hecho de tipo incorrecto. Ice Beam: Ice->Psychic dijo 0.5, Gen I es 1.0; Razor Leaf: Grass->Psychic dijo 0.5, Gen I es 1.0. Con los hechos corregidos acierta: si.
- Caso 36 (HARD): eligio MOVE_4, optimo MOVE_2, regret 1.0. Causa: hecho de tipo incorrecto. ThunderShock: Electric->Flying dijo 1.0, Gen I es 2.0; Earthquake: Ground->Flying dijo 1.0, Gen I es 0.0; Earthquake: Ground->Poison dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 7 (EASY): eligio MOVE_4, optimo MOVE_1, regret 0.7474. Causa: hecho de tipo incorrecto. Ice Beam: Ice->Grass dijo 1.0, Gen I es 2.0; Razor Leaf: Grass->Grass dijo 1.0, Gen I es 0.5; Thunderbolt: Electric->Grass dijo 1.0, Gen I es 0.5; Hydro Pump: Water->Grass dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 27 (MEDIUM): eligio MOVE_3, optimo MOVE_2, regret 0.311. Causa: hecho de tipo incorrecto. Razor Leaf: Grass->Water dijo 1.0, Gen I es 2.0; Hydro Pump: Water->Water dijo 2.0, Gen I es 0.5; Flamethrower: Fire->Water dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 5 (EASY): eligio MOVE_3, optimo MOVE_1, regret 0.6275. Causa: hecho de tipo incorrecto. Thunderbolt: Electric->Electric dijo 2.0, Gen I es 0.5; Peck: Flying->Electric dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 43 (HARD): eligio MOVE_1, optimo MOVE_2, regret 0.5714. Causa: hecho de tipo incorrecto. Psychic: Psychic->Psychic dijo 2.0, Gen I es 0.5; Ice Beam: Ice->Psychic dijo 0.5, Gen I es 1.0. Con los hechos corregidos acierta: si.
- Caso 23 (MEDIUM): eligio MOVE_1, optimo MOVE_2, regret 0.235. Causa: hecho de tipo incorrecto. Confusion: Psychic->Poison dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 32 (MEDIUM): eligio MOVE_4, optimo MOVE_1, regret 0.4062. Causa: hecho de tipo incorrecto. Drill Peck: Flying->Fighting dijo 1.0, Gen I es 2.0; Peck: Flying->Fighting dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 11 (EASY): eligio MOVE_1, optimo MOVE_2, regret 0.6786. Causa: hecho de tipo incorrecto. Blizzard: Ice->Water dijo 2.0, Gen I es 0.5; BubbleBeam: Water->Water dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 34 (MEDIUM): eligio MOVE_4, optimo MOVE_2, regret 0.4136. Causa: hecho de tipo incorrecto. Blizzard: Ice->Psychic dijo 0.5, Gen I es 1.0; Flamethrower: Fire->Psychic dijo 0.5, Gen I es 1.0. Con los hechos corregidos acierta: si.
- Caso 22 (MEDIUM): eligio MOVE_3, optimo MOVE_1, regret 0.2308. Causa: hecho de tipo incorrecto. BubbleBeam: Water->Ground dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 33 (MEDIUM): eligio MOVE_1, optimo MOVE_2, regret 0.25. Causa: hecho de tipo incorrecto. Fire Blast: Fire->Psychic dijo 0.5, Gen I es 1.0; Low Kick: Fighting->Psychic dijo 1.0, Gen I es 0.5; Rock Slide: Rock->Psychic dijo 0.5, Gen I es 1.0. Con los hechos corregidos acierta: si.
- Caso 30 (MEDIUM): eligio MOVE_4, optimo MOVE_3, regret 0.2857. Causa: hecho de tipo incorrecto. Scratch: Normal->Rock dijo 1.0, Gen I es 0.5; Vine Whip: Grass->Rock dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 44 (HARD): eligio MOVE_1, optimo MOVE_4, regret 0.4902. Causa: hecho de tipo incorrecto. Psybeam: Psychic->Psychic dijo 2.0, Gen I es 0.5; Strength: Normal->Rock dijo 1.0, Gen I es 0.5; Sludge: Poison->Rock dijo 1.0, Gen I es 0.5; Sludge: Poison->Psychic dijo 0.5, Gen I es 1.0; Body Slam: Normal->Rock dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 28 (MEDIUM): eligio MOVE_2, optimo MOVE_4, regret 0.3333. Causa: hecho de tipo incorrecto. Rock Slide: Rock->Ice dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 24 (MEDIUM): eligio MOVE_3, optimo MOVE_2, regret 0.25. Causa: hecho de tipo incorrecto. Fire Blast: Fire->Psychic dijo 0.5, Gen I es 1.0; Low Kick: Fighting->Psychic dijo 1.0, Gen I es 0.5. Con los hechos corregidos acierta: si.
- Caso 19 (MEDIUM): eligio MOVE_3, optimo MOVE_2, regret 0.3289. Causa: hecho de tipo incorrecto. Flamethrower: Fire->Bug dijo 1.0, Gen I es 2.0. Con los hechos corregidos acierta: si.
- Caso 25 (MEDIUM): eligio MOVE_4, optimo MOVE_1, regret 0.7059. Causa: hecho de tipo incorrecto. ThunderShock: Electric->Electric dijo 2.0, Gen I es 0.5. Con los hechos corregidos acierta: si.

Resumen: {'hecho de tipo incorrecto': 21}; corregibles con hechos correctos: 21/21
