# Guion del video — Deliverable 3 (máximo 3:00)

Requisito: grabar la pantalla con el sistema de agentes corriendo sobre inputs reales, de modo que
se vean los **mensajes intermedios entre agentes** y la **salida final**. Todo sale de
`notebooks/D3_colab.ipynb` (T4) o de `python -m d3.demo` en la terminal.

| Tiempo | Qué se ve en pantalla | Qué se dice |
|---|---|---|
| 0:00–0:20 | README, sección D3: el grafo de agentes | Misma tarea y mismo criterio que D1/D2. El D2 dejó un diagnóstico: el modelo no sabe la tabla de tipos. Ahora hay tres agentes con el mismo Qwen2.5-1.5B; el Analista consulta la tabla y el Verificador revisa cada hecho. |
| 0:20–0:35 | `d3/prompts/` abiertos: los tres archivos `.v1.md` | Cada agente tiene su prompt versionado, fuera del código: rol, plantillas y técnicas (few-shot, verificación, salida restringida). |
| 0:35–1:35 | Celda 5 del notebook: `show(...)` con **semilla del reloj** | El estado no está elegido: la semilla sale del reloj y se imprime. Seguir los mensajes: el Coordinador planifica, el Analista decide LOOKUP, escribe la query y recibe la sección, responde, y el Verificador acepta o lo devuelve con un motivo. Después vienen la calculadora y la PARADA con `MOVE_N`. Al final, B0 y S2 sobre el **mismo** estado y el juez. |
| 1:35–2:15 | Celda 6: caso de fallo (`--replay` del primer fallo de `summary.json`) | Dónde falla y **por qué**: qué agente se equivocó y en qué mensaje de la traza se ve. Mostrar el archivo de traza en `traces/`. |
| 2:15–2:50 | `results_d3/summary.md`: tabla de exactitud y ablaciones | Mismos 100 estados y mismo criterio: B0, H, S2, el sistema completo y una ablación por técnica. Leer cuánto cae al quitar cada técnica. |
| 2:50–3:00 | README: comandos para reproducir | Todo se reproduce desde el repositorio; las trazas del video están en `traces/`. |

Después de grabar: subir `traces/` y `results_d3/` al repo y pegar el link del video en
`report/deliverable3_es.tex` (`\VIDEO`) y en el README.
