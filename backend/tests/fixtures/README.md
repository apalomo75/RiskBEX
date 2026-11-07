# Referencia candidata TFM: exposición CVaR

`tfm_cvar_reference.json` conserva los valores sin redondear de las tablas
locales del TFM inspeccionadas en Sprint 0 y sus hashes SHA-256. La referencia
es candidata: no declara aprobado el snapshot completo ni reconstruido el
dataset maestro histórico. El HEAD registrado no incluye todos los cambios
locales que produjeron estos resultados.

Las cuatro tablas pequeñas provienen de `tables/chapter4/` del TFM. Se usa
`regime_interpretation_table.csv`, no `regime_summary.csv`: este último fue
reutilizado por el notebook para una presentación académica redondeada.

Los tests portables verifican la extracción de la fórmula contra estas tablas.
El test local adicional comprueba los hashes de los datasets completos de
regímenes MAIN/ROBUST y reconstruye sus estadísticas train y mappings. No
entrena Markov ni XGBoost y no modifica el TFM. Si no existe el repositorio
académico local, solo ese test se omite; si existe pero cambió, falla y exige
revisar la referencia. Puede indicarse su ubicación con `TFM_REFERENCE_DIR`.

No actualizar automáticamente las expectativas para hacer pasar un fallo.
Esta fixture no acredita equivalencia de precios, entrenamiento o predicciones
ML, ni resuelve las decisiones metodológicas pendientes del Sprint 0.
