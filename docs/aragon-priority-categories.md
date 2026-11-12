# Aragón: prioridad y clasificación de ayudas agrarias

Este plan organiza la búsqueda y revisión posterior al lote filtrable de Aragón (run 10). Los términos de búsqueda solo recuperan candidatos; no asignan categoría, actividad ni elegibilidad. La categoría se confirma con la ficha oficial y, cuando los metadatos no bastan, las bases o documentos de la convocatoria.

La bandeja de revisión ahora genera una orientación automática determinista a partir del título, finalidad, sectores, objetivos y beneficiarios de los metadatos BDNS. Muestra posibles categorías y actividades, una pista de relevancia y los campos/términos coincidentes. No lee los PDF, no guarda una decisión de revisión y no cambia clasificación, fiabilidad, elegibilidad ni matriz. Todas las sugerencias requieren confirmación humana; la regla prioriza marcar “comprobar beneficiarios” cuando hay señales agrarias pero los metadatos no identifican beneficiarios directos.

Las convocatorias aceptadas para extracción pueden recibir una clasificación confirmada en la ficha de revisión. Las coincidencias sugeridas adjuntan automáticamente los campos y valores BDNS como evidencia; una corrección manual requiere URL, localizador y cita oficial. La revisión se conserva como evento append-only ligado a la huella de la fuente. El informe de cobertura agrega las clasificaciones vigentes por región consultada, actividad, categoría y campaña, sin promoverlas a `verified`.

## Prioridad operativa

| Prioridad | Categorías | Criterio práctico |
|---|---|---|
| P1 · revisar primero | PAC directa, pagos asociados, incorporación de jóvenes, modernización, agroambiental/ecológica, seguro agrario | Ayudas recurrentes o de aplicación directa a explotaciones. Revisar primero nuevas convocatorias y campañas identificables. |
| P2 · revisión sectorial | Sanidad animal, ganadería extensiva, razas autóctonas | Dependen más del tipo de explotación; incluir candidatos ganaderos y revisar actividad y beneficiario. |
| P3 · seguimiento por oportunidad | Inversión general, ayudas de emergencia | Inversión se solapa con modernización y puede dirigirse a transformación u otros destinatarios. Emergencia se activa ante convocatorias o daños concretos; buscar cuando haya un aviso oficial pertinente. |

P3 indica una búsqueda más condicionada, no menor importancia para una explotación afectada. Las prioridades son una decisión operativa para Aragón y no describen la oferta actual de ayudas.

## Términos de descubrimiento

La tabla complementaria [`aragon-priority-category-map.csv`](aragon-priority-category-map.csv) contiene términos iniciales por categoría y señales que deben verificarse. Úsalos en lotes pequeños en `--terms`; los sinónimos pueden generar resultados repetidos y falsos positivos.

- Mantener agricultura, ganadería y explotaciones mixtas como actividades separadas. Solo asignar una actividad cuando la convocatoria delimite beneficiarios, producción o actuaciones.
- Permitir más de una categoría cuando las bases regulen intervenciones distintas que encajen en varias categorías; documentar la razón para cada asignación.
- `inversión` puede coincidir con modernización, pero no implica ayuda a productores: comprobar el beneficiario y si se financia la explotación primaria.
- Un pago PAC o una ayuda de seguro puede tener campaña o periodo específico. Registrar el año/etiqueta solo con evidencia oficial explícita.

## Evidencia mínima para reconciliar la matriz

Para pasar una fila de Aragón de `not_checked` a `indexed`, conservar el run y las convocatorias que respaldan esa categoría, y registrar una nota que cite el campo BDNS o la sección/página de las bases que acredita el objeto de la ayuda. Para `details_extracted`, debe existir una extracción vigente con citas. `verified` requiere además superar las puertas de revisión de la tarea 3.5. Una búsqueda limitada sin candidatos no prueba que la categoría carezca de ayudas.

No marcar filas de actividad que las bases no permitan distinguir. Si una convocatoria está dirigida a universidades, administraciones u organizaciones, solo contarla para explotaciones si las fuentes oficiales muestran un mecanismo de ayuda directo para estas. Mantener el resto como candidato, fuera de alcance o sin clasificar según la revisión registrada.

## Situación del lote

Run 10 contiene 62 convocatorias descubiertas en 11 consultas de Aragón. El usuario confirmó que completó la revisión de relevancia. No se recibieron conteos ni asignaciones categoría/actividad/campaña para actualizar la matriz, por lo que la clasificación estructurada queda pendiente de reconciliación.

Al abrir el run 10 tras reconstruir los servicios, las 62 fichas recibirán las sugerencias en pantalla sin tener que repetir la importación. Conviene comparar las sugerencias con la revisión previa y corregir las que no encajen con las fuentes oficiales.
