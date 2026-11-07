# Predicciones históricas TFM: referencia candidata de Sprint 1B

Los `.csv.gz` son copias comprimidas sin alterar los bytes CSV originales.
La compresión fija `mtime=0`. `manifest.json` registra SHA-256 del contenido
descomprimido, ruta de procedencia, filas y fechas. El verificador exige esos
hashes antes de leer las series. No sustituir una referencia ante un fallo.

- MAIN: 1.376 predicciones; 1.375 observaciones de backtest ML.
- ROBUST: 1.633 predicciones; 1.632 observaciones de backtest ML.
- Los backtests Regime-based tienen una sesión adicional, 22/05/2026. Se excluye
  explícitamente para la comparación conjunta, sin modificar el original.
- Las tablas pequeñas contienen mappings CVaR, métricas brutas/netas, turnover,
  resultados de clasificación redondeados y resultados conjuntos originales.
- Las métricas exactas de clasificación provienen de la salida guardada de la
  celda 20 del notebook 05; se contrastan con los CSV de predicciones.

`historical_master.csv.gz` se recuperó con `git show` del commit TFM
`8dd66a93c06dc3cbfaac29f086ad2625d32d9756`, no del maestro local sobrescrito.
Contiene las once variables: 6.631 filas, 28/03/2000–23/04/2026. Cubre las
5.274/5.017 filas de entrenamiento MAIN/ROBUST, pero NO acredita ser el maestro
exacto de la ejecución de mayo ni cubre todo su periodo OOS. No se mezcla
silenciosamente con el maestro actual iniciado en 2002.

Estos archivos son predicciones, resultados e inputs históricos, NO modelos
XGBoost entrenados. No permiten inferencia de sesiones nuevas. La referencia
completa sigue siendo candidata, con las decisiones del Sprint 0 pendientes.
Procedencia y licencia: repositorio académico TFM, que incluye licencia MIT.
