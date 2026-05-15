from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class LatestRiskResponse(BaseModel):
    date: str
    vol_20d: float
    vol_60d: float
    var_95_60d: float
    cvar_95_60d: float
    drawdown: float
    skew_60d: float
    regime_label: str
    risk_score: int
    risk_level: str | None


class HistoricalRiskPoint(BaseModel):
    date: str
    vol_20d: float
    vol_60d: float
    var_95_60d: float
    cvar_95_60d: float
    drawdown: float
    skew_60d: float
    regime_label: str
    risk_score: int
    risk_level: str | None


class RunUpdateResponse(BaseModel):
    status: str
    message: str
    stdout: str
    stderr: str
    returncode: int | None
