from fastapi import FastAPI

from src.riskbex.api.routes import health, risk, updates


app = FastAPI(title="RISKBEX API")

app.include_router(health.router)
app.include_router(risk.router)
app.include_router(updates.router)
