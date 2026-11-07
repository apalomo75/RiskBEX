# RISKBEX — Instrucciones de trabajo

Estas normas se aplican a todas las tareas futuras en este repositorio.

## Contexto consolidado

- Considerar cerrados los Sprints 1A, 1B, 1C, 1D, 2 y 3. No volver a auditar el TFM ni reconstruir modelos salvo petición explícita.
- Utilizar la documentación existente, especialmente `backend/docs/`, como referencia.
- Inspeccionar exclusivamente los archivos relacionados con la tarea. Evitar lecturas completas de notebooks, CSV grandes o scripts que no se vayan a modificar.
- No revisar el historial Git completo sin una razón concreta.

## Pruebas eficientes

- Ejecutar primero únicamente los tests afectados por los cambios.
- Ejecutar una sola vez cada batería, salvo fallos. No repetir las 103 pruebas históricas en cada sprint.
- Reservar la suite completa para cambios transversales o preparación de releases.
- En cambios cuantitativos, ejecutar siempre las pruebas relevantes de integridad y ausencia de look-ahead.
- Nunca eliminar ni debilitar pruebas para acelerar su ejecución.
- Si una prueba falla, corregir la causa y repetir únicamente la prueba afectada.

## Herramientas y recursos

- Preferir búsquedas específicas y evitar comandos redundantes o lecturas de directorios completos.
- No comprobar SHA-256 de centenares de archivos en cada tarea; limitar las comprobaciones a los artefactos relevantes.
- No navegar por internet salvo cuando sea necesario verificar información externa.
- No ejecutar entrenamientos, descargas ni Docker sin una necesidad específica y la autorización aplicable a la tarea. La actualización diaria utiliza modelos congelados, sin reentrenamiento.
- No instalar dependencias sin autorización.
- Evitar tareas paralelas costosas que no contribuyan directamente al objetivo.

## Modificaciones

- Hacer cambios mínimos y localizados; identificar el código reutilizable y el cambio mínimo antes de modificar un componente.
- Conservar FastAPI, sus contratos públicos siempre que sea posible y `backend/dashboard.py` como interfaz principal de Streamlit, con sus seis pestañas y funcionalidades.
- No reconstruir componentes ya desarrollados, realizar rediseños estéticos ni refactorizaciones generales no solicitadas.
- No eliminar funcionalidades existentes sin justificarlo previamente.
- Mantener la fidelidad a la metodología del TFM. MAIN es el único motor operativo; ROBUST permanece como referencia académica.
- No modificar resultados originales del TFM ni sobrescribir artefactos históricos. Mantener separados entrenamiento congelado y datos operativos.
- No hacer commits automáticamente.

## Entregas

Al finalizar cada tarea, entregar únicamente:

1. Qué se ha cambiado.
2. Qué funciona.
3. Tests ejecutados y resultado; indicar expresamente si no se ejecutaron.
4. Qué queda pendiente.

Limitar el informe habitual a 300 palabras. No generar informes extensos adicionales salvo petición expresa.

## Prioridad inmediata

- Priorizar la publicación de RISKBEX v0.1 mediante funcionalidades visibles y verificables: integración del pipeline, FastAPI, Streamlit, actualización automática y despliegue.
- No ampliar el alcance hacia funcionalidades de versiones posteriores ni perfeccionar componentes que ya hayan superado sus criterios de aceptación.
- No activar programación automática ni despliegues sin la autorización correspondiente.
- Si se detecta un problema realmente bloqueante, detenerse e informar. No iniciar una investigación extensa sin justificar su necesidad.
