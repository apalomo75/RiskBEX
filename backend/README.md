# RISKBEX Backend

Sprint 1A: [interpretación de entrenamiento, mapping CVaR y pruebas de equivalencia](docs/sprint-1a.md).
La interfaz principal sigue siendo `dashboard.py`, con las seis pestañas existentes.

Sprint 1B: [ML, estrategias históricas y estado de recuperación de modelos](docs/sprint-1b.md).
Verificación offline, sin entrenar ni regenerar CSV operativos:

```bash
python -B -m unittest discover -s tests -v
python -B scripts/check_ml_equivalence.py
```

Sprint 1C: [modelos XGBoost purgados, procedencia y validación](docs/sprint-1c.md).
Los modelos están en `experiments/sprint-1c-causal-v1/`; no se han activado en
el pipeline diario ni en los endpoints públicos.

Sprint 1D: [reconstrucción Markov y bloqueo de compatibilidad ROBUST](docs/sprint-1d.md).
La pareja permanece bloqueada para revisión; los parámetros de diagnóstico están
separados en `experiments/sprint-1d-markov-v2/` y no se usan operativamente.

Sprint 2: [motor MAIN offline y plan de publicación incremental v0.1](docs/sprint-2.md).
Por decisión de producto, MAIN 500 + XGBoost MAIN causal-v1 es el paquete principal;
ROBUST permanece como validación académica y no requiere promoción diaria.
El paquete `model_packages/main-v1/` aún no se conecta a la API ni al pipeline.

Ejecución offline con el runtime registrado en el manifiesto:

```bash
python -B scripts/run_main_offline.py --package model_packages/main-v1 \
  --prices tests/fixtures/sprint2/extended_prices.csv.gz --as-of 2026-05-15
```

## Pipeline de ejecucion RISKBEX

Para generar los outputs derivados del sistema analitico:

```bash
cd backend
PYTHONPATH=src python scripts/run_full_pipeline.py
```

El comando anterior ejecuta, en orden:

```bash
python scripts/prepare_regime_datasets.py
PYTHONPATH=src python scripts/run_adaptive_backtest.py
PYTHONPATH=src python scripts/run_tail_analysis.py
```

Para levantar la API:

```bash
uvicorn main:app --reload
```

Para levantar el dashboard:

```bash
streamlit run dashboard.py
```

Nota metodologica: el pipeline no recalcula Markov Switching. Consume los outputs de regimenes ya generados, prepara datasets limpios MAIN/ROBUST, ejecuta backtesting adaptativo y calcula Tail Risk sobre los outputs de backtesting.

Los CSV generados en `backend/data/processed/` son derivados, pueden estar ignorados por Git y son regenerables mediante `scripts/run_full_pipeline.py`.

Este script sera la base para automatizar la generacion de outputs dentro de Docker/AWS antes de servir API/dashboard.

## Sprint 3: pipeline MAIN versionado

[Arquitectura, validación y comandos](docs/sprint-3.md). `run_daily_update.py` y `run_full_pipeline.py` requieren argumentos explícitos, un recibo de regresión vigente y un directorio separado. Sin argumentos no descargan ni sobrescriben CSV. Los scripts `run_legacy_*` conservan las herramientas anteriores para uso manual, fuera del pipeline MAIN. Las rutas y Streamlit aún no consumen las nuevas publicaciones.
