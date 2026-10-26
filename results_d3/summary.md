# Resultados Deliverable 3

- Modelo (todos los agentes): `Qwen/Qwen2.5-1.5B-Instruct` revision `None`, cuda Tesla T4 torch.float32
- Conjuntos: holdout (semilla 20260927, n=50), orig (semilla 20260830, n=50)
- Correcto = la accion coincide con max(potencia x precision x STAB x efectividad Gen I), igual que D1/D2

## 1. Exactitud (mismos estados, mismo criterio)

| Sistema | holdout | orig | all | llamadas/estado | s/estado |
|---|---:|---:|---:|---:|---:|
| B0 Directo (baseline) | 40.0% [28–54] | 28.0% [18–42] | 34.0% [26–44] | 1.0 | 0.35 |
| H  Sin modelo (ignora tipos) | 76.0% [63–86] | 54.0% [40–67] | 65.0% [55–74] | 0.0 | 0.0 |
| S2 Solucion D2 | 58.0% [44–71] | 48.0% [35–62] | 53.0% [43–62] | 5.14 | 0.23 |
| D3 Agentes (completo) | 80.0% [67–89] | 74.0% [60–84] | 77.0% [68–84] | 52.82 | 4.91 |
| D3 sin recuperacion | 48.0% [35–62] | 34.0% [22–48] | 41.0% [32–51] | 16.94 | 2.01 |
| D3 sin few-shot | 88.0% [76–94] | 86.0% [74–93] | 87.0% [79–92] | 49.4 | 0.94 |
| D3 sin Verificador | 84.0% [72–92] | 86.0% [74–93] | 85.0% [77–91] | 31.64 | 0.28 |
| D3 sin descomposicion | 38.0% [26–52] | 18.0% [10–31] | 28.0% [20–38] | 1.0 | 0.74 |
| D3 sin tabla ordenada | 70.0% [56–81] | 54.0% [40–67] | 62.0% [52–71] | 52.82 | 0.74 |

## 2. Tests pareados (McNemar exacto, 100 estados)

- H  Sin modelo (ignora tipos) vs B0 Directo (baseline): gana 36, pierde 5, p = 7.84e-07
- S2 Solucion D2 vs B0 Directo (baseline): gana 27, pierde 8, p = 0.00188
- D3 Agentes (completo) vs B0 Directo (baseline): gana 47, pierde 4, p = 2.42e-10
- D3 sin recuperacion vs B0 Directo (baseline): gana 14, pierde 7, p = 0.189
- D3 sin few-shot vs B0 Directo (baseline): gana 55, pierde 2, p = 2.3e-14
- D3 sin Verificador vs B0 Directo (baseline): gana 54, pierde 3, p = 4.29e-13
- D3 sin descomposicion vs B0 Directo (baseline): gana 9, pierde 15, p = 0.307
- D3 sin tabla ordenada vs B0 Directo (baseline): gana 35, pierde 7, p = 1.51e-05
- D3 Agentes (completo) vs S2 Solucion D2: gana 35, pierde 11, p = 0.000536
- D3 Agentes (completo) vs H  Sin modelo (ignora tipos): gana 25, pierde 13, p = 0.073
- D3 Agentes (completo) vs D3 sin recuperacion: gana 41, pierde 5, p = 4.41e-08
- D3 Agentes (completo) vs D3 sin few-shot: gana 0, pierde 10, p = 0.00195
- D3 Agentes (completo) vs D3 sin Verificador: gana 3, pierde 11, p = 0.0574
- D3 Agentes (completo) vs D3 sin descomposicion: gana 51, pierde 2, p = 3.18e-13
- D3 Agentes (completo) vs D3 sin tabla ordenada: gana 19, pierde 4, p = 0.0026

## 3. Diagnostico por agente (100 estados)

| Sistema | hechos ok | siempre x1 | consulta | seccion ok | revisados | sin verificar | plan incompleto | final != calculadora | llamadas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D3 Agentes (completo) | 90.6% | 66.1% | 100.0% | 100.0% | 99 | 0 | 17 | 10 | 52.82 |
| D3 sin recuperacion | 31.9% | 66.1% | 0.0% | 0.0% | 498 | 498 | 17 | 19 | 16.94 |
| D3 sin few-shot | 100.0% | 66.1% | 100.0% | 100.0% | 59 | 0 | 17 | 7 | 49.4 |
| D3 sin Verificador | 89.4% | 66.1% | 98.8% | 98.8% | 0 | 0 | 17 | 7 | 31.64 |
| D3 sin descomposicion | None% | None% | None% | None% | 0 | 0 | 0 | 0 | 1.0 |
| D3 sin tabla ordenada | 90.6% | 66.1% | 100.0% | 100.0% | 99 | 0 | 17 | 27 | 52.82 |

Bucle Verificador->Analista (completo vs sin Verificador): corrige 52 hechos, daña 46.

Hechos erroneos por tipo defensor: D3 Agentes (completo): {'Water': 22, 'Ghost': 8, 'Ground': 7, 'Psychic': 5, 'Bug': 2, 'Fire': 2, 'Fighting': 1}; D3 sin recuperacion: {'Psychic': 50, 'Poison': 47, 'Fighting': 35, 'Rock': 32, 'Water': 31, 'Ghost': 26, 'Grass': 20, 'Ice': 20, 'Bug': 18, 'Electric': 18, 'Ground': 17, 'Flying': 13, 'Fire': 12}; D3 sin few-shot: ninguno; D3 sin Verificador: {'Water': 10, 'Poison': 9, 'Electric': 6, 'Flying': 5, 'Rock': 5, 'Ground': 4, 'Ice': 4, 'Bug': 3, 'Ghost': 3, 'Fighting': 2, 'Fire': 2}; D3 sin descomposicion: ninguno; D3 sin tabla ordenada: {'Water': 22, 'Ghost': 8, 'Ground': 7, 'Psychic': 5, 'Bug': 2, 'Fire': 2, 'Fighting': 1}

## 4. Fallos del sistema completo (23)

- holdout:48 (HARD): eligio MOVE_3, correcto MOVE_1, regret 0.1667 — hecho de tipo incorrecto: Psychic->Psychic: dijo 'normal damage', Gen I x0.5
- holdout:14 (EASY): eligio MOVE_2, correcto MOVE_3, regret 0.5833 — el Coordinador no eligió el máximo de la calculadora
- holdout:27 (MEDIUM): eligio MOVE_3, correcto MOVE_2, regret 0.311 — plan incompleto
- holdout:37 (HARD): eligio MOVE_1, correcto MOVE_4, regret 0.1467 — hecho de tipo incorrecto: Bug->Water: dijo 'no effect', Gen I x1; Ghost->Water: dijo 'not very effective', Gen I x1; Psychic->Water: dijo 'no effect', Gen I x1
- holdout:35 (HARD): eligio MOVE_2, correcto MOVE_1, regret 0.0104 — hecho de tipo incorrecto: Water->Ground: dijo 'normal damage', Gen I x2
- holdout:39 (HARD): eligio MOVE_4, correcto MOVE_2, regret 0.1667 — el Coordinador no eligió el máximo de la calculadora
- holdout:41 (HARD): eligio MOVE_3, correcto MOVE_1, regret 0.6111 — hecho de tipo incorrecto: Normal->Water: dijo 'super effective', Gen I x1; Normal->Water: dijo 'super effective', Gen I x1; Flying->Water: dijo 'no effect', Gen I x1
- holdout:22 (MEDIUM): eligio MOVE_3, correcto MOVE_1, regret 0.2308 — hecho de tipo incorrecto: Water->Ground: dijo 'normal damage', Gen I x2
- holdout:21 (MEDIUM): eligio MOVE_3, correcto MOVE_1, regret 0.6875 — el Coordinador no eligió el máximo de la calculadora
- holdout:44 (HARD): eligio MOVE_1, correcto MOVE_4, regret 0.4902 — hecho de tipo incorrecto: Psychic->Psychic: dijo 'normal damage', Gen I x0.5
- orig:41 (HARD): eligio MOVE_3, correcto MOVE_1, regret 0.0104 — hecho de tipo incorrecto: Normal->Ghost: dijo 'normal damage', Gen I x0; Normal->Ghost: dijo 'normal damage', Gen I x0
- orig:27 (MEDIUM): eligio MOVE_1, correcto MOVE_3, regret 0.2344 — hecho de tipo incorrecto: Normal->Water: dijo 'super effective', Gen I x1; Normal->Water: dijo 'super effective', Gen I x1
- orig:31 (MEDIUM): eligio MOVE_2, correcto MOVE_1, regret 0.2099 — hecho de tipo incorrecto: Rock->Water: dijo 'no effect', Gen I x1; Bug->Water: dijo 'no effect', Gen I x1
- orig:50 (HARD): eligio MOVE_2, correcto MOVE_1, regret 0.5625 — hecho de tipo incorrecto: Water->Fire: dijo 'normal damage', Gen I x2
- orig:8 (EASY): eligio MOVE_3, correcto MOVE_1, regret 0.5833 — hecho de tipo incorrecto: Normal->Water: dijo 'super effective', Gen I x1
- orig:29 (MEDIUM): eligio MOVE_4, correcto MOVE_1, regret 0.35 — el Coordinador no eligió el máximo de la calculadora
- orig:47 (HARD): eligio MOVE_4, correcto MOVE_3, regret 1.0 — hecho de tipo incorrecto: Normal->Ghost: dijo 'normal damage', Gen I x0; Fighting->Ghost: dijo 'normal damage', Gen I x0
- orig:43 (HARD): eligio MOVE_3, correcto MOVE_4, regret 0.537 — hecho de tipo incorrecto: Psychic->Psychic: dijo 'normal damage', Gen I x0.5
- orig:48 (HARD): eligio MOVE_3, correcto MOVE_4, regret 0.0519 — hecho de tipo incorrecto: Ghost->Water: dijo 'not very effective', Gen I x1; Psychic->Water: dijo 'no effect', Gen I x1; Rock->Water: dijo 'no effect', Gen I x1
- orig:18 (MEDIUM): eligio MOVE_4, correcto MOVE_1, regret 0.2 — hecho de tipo incorrecto: Normal->Water: dijo 'super effective', Gen I x1
- orig:36 (HARD): eligio MOVE_2, correcto MOVE_1, regret 0.15 — plan incompleto
- orig:11 (EASY): eligio MOVE_2, correcto MOVE_3, regret 1.0 — hecho de tipo incorrecto: Normal->Ghost: dijo 'normal damage', Gen I x0; Normal->Ghost: dijo 'normal damage', Gen I x0
- orig:10 (EASY): eligio MOVE_1, correcto MOVE_2, regret 0.7173 — el Coordinador no eligió el máximo de la calculadora
