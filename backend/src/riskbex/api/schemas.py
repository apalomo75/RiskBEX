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


class RegimeLatestResponse(BaseModel):
    date: str
    split: str
    regime: int
    economic_label: str
    risk_order: int
    p_regime_0: float
    p_regime_1: float
    p_regime_2: float
    dominant_probability: float


class RegimeHistoryPoint(BaseModel):
    date: str
    split: str
    regime: int
    economic_label: str
    risk_order: int
    p_regime_0: float
    p_regime_1: float
    p_regime_2: float


class RegimeSummaryRow(BaseModel):
    split: str
    regime: int
    n_obs: int
    frequency_pct: float
    mean_ret_1d: float
    mean_ewma_vol: float
    mean_cvar_95_60d: float
    median_ewma_vol: float
    median_cvar_95_60d: float
    economic_label: str
    risk_order: int
    risk_severity: float


class ModelSelectionRow(BaseModel):
    split: str
    split_column: str
    train_start: str
    train_end: str
    n_obs_train: int
    k_regimes: int
    aic: float
    bic: float
    log_likelihood: float
    converged: bool
    selected: bool


class TransitionMatrixRow(BaseModel):
    split: str
    from_regime: int
    from_label: str
    from_risk_order: int
    to_regime: int
    to_label: str
    to_risk_order: int
    transition_probability: float


class DurationSummaryRow(BaseModel):
    split: str
    scope: str
    regime: int
    economic_label: str
    risk_order: int
    n_blocks: int
    mean_duration_trading_days: float
    median_duration_trading_days: float
    max_duration_trading_days: int
    min_duration_trading_days: int
    total_obs: int
    frequency_pct: float
