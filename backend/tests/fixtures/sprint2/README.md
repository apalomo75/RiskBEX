# Inputs offline de Sprint 2

`manifest.json` conserva la procedencia y SHA-256 del CSV descomprimido.

- `historical_prices.csv.gz`: bytes originales del raw académico desde Git,
  hasta 23/04/2026. No se recalculan ni editan sus retornos guardados.
- `extended_prices.csv.gz`: copia del raw local RISKBEX hasta 15/05/2026,
  posterior a la validación causal-v1. No es una descarga de mercado reciente.
- `causal_main_predictions.csv.gz`: copia exacta del resultado de validación del
  XGBoost MAIN causal-v1, que permanece intacto en su experimento original.

El motor consume únicamente fecha/precio y recalcula retornos. Los demás campos
no se utilizan para generar señales. El contexto inicial de precio está
documentado en el manifiesto del paquete, sin introducir observaciones futuras.
