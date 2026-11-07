# RISKBEX

Monitor de riesgo del IBEX 35 basado en regímenes Markov Switching, XGBoost y
exposición adaptativa calculada a partir del CVaR de entrenamiento del TFM.

El producto reutiliza la API FastAPI y el dashboard Streamlit existentes con
sus seis pestañas. El motor principal es MAIN; ROBUST se conserva como referencia
académica y no participa en el futuro proceso diario.

Estado actual: motor MAIN offline reproducible y modelos persistidos. Todavía
no hay actualización automática ni entrega pública activada por este sprint.
La primera entrega prevista es **v0.1 — Market Risk Monitor**.

- [Backend y ejecución actual](backend/README.md)
- [Motor MAIN offline, ejemplos y plan mínimo de v0.1](backend/docs/sprint-2.md)
- [Manifiesto del paquete MAIN](backend/model_packages/main-v1/manifest.json)
- [Changelog](CHANGELOG.md)

La publicación incremental continuará con simulador (v0.2), cartera ficticia
(v0.3), explicabilidad/diagnósticos (v0.4) e integración completa (v1.0).
Las referencias académicas y los candidatos de inferencia permanecen separados.
