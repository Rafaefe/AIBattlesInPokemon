# Guion del video (máximo 3:00)

La pauta: *"el video muestra el pipeline corriendo de punta a punta sobre un input que no fue
elegido para favorecerlo, con el baseline visible sobre el mismo input. Edición que oculte la
ejecución, o salidas que no se puedan rastrear al repositorio, reciben cero."*

Por eso: **grabar la ejecución real, sin cortar dentro de un comando que corre.** Se puede cortar
*entre* comandos (la evaluación completa se muestra ya terminada, desde sus archivos).

## Antes de grabar

**Lo más simple:** abrir en Colab `D2_video.ipynb` (trae este repositorio adentro), poner GPU T4 y
`Ejecutar todo` una vez **antes** de grabar. Después, grabando, volver a ejecutar las celdas
marcadas "EN EL VIDEO" una por una.

Si se hace desde el repositorio clonado:

1. Las corridas ya están hechas (`results_d2/` y `results_d2_holdout/`, en el repo).
2. Abrir `results_d2/summary.md`, `results_d2_holdout/summary.md` y el PDF del documento.
3. En Colab (GPU T4): clonar el repo, `pip install -r requirements-d2.txt` y dejar el modelo
   descargado (correr una vez `python -m d2.demo` antes de grabar, para que no se vea la descarga).

## Guion

| Tiempo | Qué se ve | Qué se dice (idea) |
|---|---|---|
| 0:00–0:20 | README, "El fallo que ataca" | "En el D1, Qwen2.5-1.5B acertaba 16,7 %, bajo el azar: respondía por posición. La solución: preguntarle un hecho de tipos a la vez y dejar la aritmética a una calculadora." |
| 0:20–0:30 | Salida de `python -m pytest -q tests` (20 pasan) | "Los tests verifican, entre otras cosas, que la solución no tiene acceso a la tabla de tipos." |
| 0:30–1:30 | **En vivo:** `python -m d2.demo` | Señalar la **semilla impresa** ("sale del reloj; con ella cualquiera reproduce este estado"). Recorrer: respuesta del baseline → las preguntas de S2 con **las palabras que respondió el modelo** → tabla de la calculadora → juez y referencia H. |
| 1:30–2:05 | Tablas de `results_d2/summary.md` y `results_d2_holdout/summary.md` | "Mismos 50 estados para todos: el baseline acierta 28 %, S2 48 % (gana 13, pierde 3, p = 0,02). En 50 estados nuevos, 40 contra 58 %. Y ya no hay sesgo de posición. Pero H, que ignora los tipos, saca 54 y 76 %: el modelo no aporta sobre asumir ×1." |
| 2:05–2:45 | Sección 5 del documento + **en vivo** `python -m d2.demo --replay 32` | "La v1 respondía '0,5' a todo, incluso a una pregunta vacía; por eso S2. Y aquí falla S2: el modelo dijo 'normal damage' para Eléctrico contra Tierra, que en Gen I no hace nada, y eligió Thunderbolt. Dijo 'normal damage' en 87 % de los pares y cuando dijo otra cosa acertó 2 de 16. Con los hechos correctos, la misma calculadora acierta los 26 fallos: ahora el problema es saber, no combinar." |
| 2:45–3:00 | Link del repo | "Todo sale de este repositorio y se reproduce con estos comandos. Próximo paso: enseñarle la tabla al modelo." |

## Consejos

- Grabar con OBS o el grabador de Windows (`Win + Alt + R`). Resolución 1080p.
- En la T4 la demo tarda segundos: se puede mostrar entera sin cortar. En CPU también, pero más lento.
- Si la demo sale "correcta" para los dos, no pasa nada: es un estado al azar. Lo importante es que
  se vea que no se eligió.
- Subir a YouTube como **no listado** o a Drive con "cualquiera con el enlace". Probar el enlace en
  una ventana de incógnito antes de entregar.
