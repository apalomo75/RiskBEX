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


class AdaptiveBacktestResultRow(BaseModel):
    date: str
    ret_1d: float
    regime: int
    regime_label: str
    risk_order: int
    p_regime_0: float
    p_regime_1: float
    p_regime_2: float
    target_exposure: float
    strategy_exposure: float
    benchmark_return: float
    strategy_return: float
    benchmark_cum: float
    strategy_cum: float
    benchmark_drawdown: float
    strategy_drawdown: float


class AdaptiveBacktestMetricsRow(BaseModel):
    sample: str
    strategy: str
    total_return: float
    mean_daily_return: float
    daily_volatility: float
    annualized_volatility: float
    VaR_95: float
    CVaR_95: float
    max_drawdown: float
    n_observations: int
    start_date: str
    end_date: str


class AdaptiveBacktestLatestResponse(BaseModel):
    date: str
    sample: str
    regime: int
    regime_label: str
    risk_order: int
    p_regime_0: float
    p_regime_1: float
    p_regime_2: float
    target_exposure: float
    strategy_exposure: float
    benchmark_cum: float
    strategy_cum: float
    benchmark_drawdown: float
    strategy_drawdown: float
    benchmark_return: float
    strategy_return: float
    methodology: str


class TailRiskEventRow(BaseModel):
    date: str
    sample: str
    ret_1d: float
    stress_tail_event: bool
    tail_threshold: float
    regime: int
    regime_label: str
    risk_order: int
    p_regime_0: float
    p_regime_1: float
    p_regime_2: float
    target_exposure: float
    strategy_exposure: float
    benchmark_return: float
    strategy_return: float
    benchmark_cum: float
    strategy_cum: float
    benchmark_drawdown: float
    strategy_drawdown: float
    benchmark_tail_cum: float | None
    strategy_tail_cum: float | None


class TailRiskMetricRow(BaseModel):
    sample: str
    strategy: str
    n_tail_events: int
    tail_threshold: float
    tail_share: float
    mean_tail_return: float
    median_tail_return: float
    min_tail_return: float
    tail_volatility: float
    tail_total_return: float
    tail_VaR_95: float
    tail_CVaR_95: float
    max_backtest_drawdown_on_tail_days: float
    hit_ratio_negative: float


class TailRiskThresholdRow(BaseModel):
    sample: str
    threshold_quantile: float
    tail_threshold: float
    n_observations: int
    n_tail_events: int
    tail_share: float
    start_date: str
    end_date: str
    worst_market_return: float


class TailRiskLatestResponse(BaseModel):
    date: str
    sample: str
    regime: int
    regime_label: str
    risk_order: int
    ret_1d: float
    stress_tail_event: bool
    tail_threshold: float
    strategy_exposure: float
    benchmark_return: float
    strategy_return: float
    benchmark_drawdown: float
    strategy_drawdown: float
    benchmark_tail_cum: float | None
    strategy_tail_cum: float | None
    methodology: str
