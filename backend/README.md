# RISKBEX Backend

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
