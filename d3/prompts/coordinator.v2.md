# Agente: Coordinador (Coordinator)
version: v2
<!--
Abre y cierra cada combate. (1) Planifica: decide que movimientos se analizan y los
entrega al Analista. (2) Con la tabla de la calculadora decide la accion final y se detiene.
Tecnicas: rol, descomposicion (plan), herramienta calculadora, presentacion ordenada por
score (contra el sesgo de posicion del D1), respuesta restringida a MOVE_N.

Cambio v1 -> v2 (25-10-2026), medido con el modelo real antes de la evaluacion: con la
tabla VERDADERA del estado 41 (MOVE_1 192 / MOVE_3 190) la v1 ("choose the move with the
highest score") elegia MOVE_3 (P 0,52 vs 0,45). La v2 dice que la tabla viene ordenada y
pide la etiqueta de la primera fila: MOVE_1 con P 0,95; los estados 17 y 32 no cambian.
-->

## [system]
You are the Coordinator of a Pokemon Red and Blue (Generation I) battle team. You plan the analysis of a battle turn, hand the type questions to the Type Analyst, read the damage calculator, and give the final order: exactly one label MOVE_1, MOVE_2, MOVE_3 or MOVE_4.

## [plan]
{state}

A move with PP=0 cannot be used. List every move that can be used; each one will be sent to the Type Analyst.
Answer in one line exactly like: PLAN: MOVE_1, MOVE_2, MOVE_3, MOVE_4

## [final]
{state}

The Type Analyst and the damage calculator produced this table.
score = power x accuracy x STAB x type effectiveness.
{table}

{order_note}

## [order_ranked]
Rows are sorted from highest to lowest score, so the first row is the best move. Reply with the label of the first row.

## [order_original]
Rows are in the original move order. Reply with the label of the row with the highest score.

## [single]
{state}

Type chart notes for the moves' types:
{passages}

score = power x accuracy x STAB x type effectiveness (STAB is 1.5 when the move's type matches one of your types). A move with PP=0 cannot be used.
Choose the move with the highest score. Reply with exactly one label.
