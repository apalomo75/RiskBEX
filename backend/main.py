from fastapi import FastAPI

from src.riskbex.api.routes import backtesting, health, regimes, risk, tail_risk, updates


app = FastAPI(title="RISKBEX API")

app.include_router(health.router)
app.include_router(backtesting.router)
app.include_router(regimes.router)
app.include_router(risk.router)
app.include_router(tail_risk.router)
app.include_router(updates.router)
