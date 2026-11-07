from fastapi import APIRouter, HTTPException

from src.riskbex.api.schemas import (
    AdaptiveBacktestLatestResponse,
    AdaptiveBacktestMetricsRow,
    AdaptiveBacktestResultRow,
)
from src.riskbex.data.loaders import (
    load_adaptive_backtest_metrics,
    load_adaptive_backtest_results,
)


router = APIRouter()

VALID_SAMPLES = {"main", "robust"}
SPLIT_COLUMNS = {
    "main": "sample_split_main",
    "robust": "sample_split_robust",
}
METHODOLOGY = (
    "Regime-based adaptive exposure using OOS filtered regimes and one-day "
    "shifted exposure to avoid look-ahead bias."
)


def _normalize_sample(sample: str) -> str:
    normalized_sample = str(sample).lower()
    if normalized_sample not in VALID_SAMPLES:
        raise HTTPException(status_code=400, detail="sample must be main or robust")
    return normalized_sample


def _format_date(value):
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)


def _load_results_or_raise(sample: str):
    try:
        return load_adaptive_backtest_results(sample)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                "Adaptive backtest outputs not found. "
                "Run scripts/run_adaptive_backtest.py first."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _load_metrics_or_raise():
    try:
        return load_adaptive_backtest_metrics()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                "Adaptive backtest outputs not found. "
                "Run scripts/run_adaptive_backtest.py first."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _result_records(df):
    output_df = df.copy()
    output_df["date"] = output_df["date"].map(_format_date)
    return output_df.to_dict(orient="records")


def _latest_response(row, sample: str):
    return {
        "date": _format_date(row["date"]),
        "sample": sample.upper(),
        "regime": int(row["regime"]),
        "regime_label": str(row["regime_label"]),
        "risk_order": int(row["risk_order"]),
        "p_regime_0": float(row["p_regime_0"]),
        "p_regime_1": float(row["p_regime_1"]),
        "p_regime_2": float(row["p_regime_2"]),
        "target_exposure": float(row["target_exposure"]),
        "strategy_exposure": float(row["strategy_exposure"]),
        "benchmark_cum": float(row["benchmark_cum"]),
        "strategy_cum": float(row["strategy_cum"]),
        "benchmark_drawdown": float(row["benchmark_drawdown"]),
        "strategy_drawdown": float(row["strategy_drawdown"]),
        "benchmark_return": float(row["benchmark_return"]),
        "strategy_return": float(row["strategy_return"]),
        "methodology": METHODOLOGY,
    }


@router.get("/backtesting/results", response_model=list[AdaptiveBacktestResultRow])
def backtesting_results(sample: str = "main", strategy: str = "regime_based"):
    normalized_sample = _normalize_sample(sample)
    if normalized_sample == "main":
        from src.riskbex.api.operational import snapshot, backtest_points
        points = backtest_points(snapshot(), strategy)
        if not points.empty:
            return points.to_dict(orient='records')
        raise HTTPException(status_code=503, detail='No realised MAIN backtest rows available.')
    if strategy != 'regime_based':
        raise HTTPException(status_code=400, detail='ML strategies are available only for operational MAIN.')
    results_df = _load_results_or_raise(normalized_sample)
    return _result_records(results_df)


@router.get("/backtesting/metrics", response_model=list[AdaptiveBacktestMetricsRow])
def backtesting_metrics():
    from src.riskbex.api.operational import snapshot
    data = snapshot()
    records = data['metrics'].to_dict(orient='records')
    return [dict(row, publication=data['publication']) for row in records]


@router.get("/backtesting/latest", response_model=AdaptiveBacktestLatestResponse)
def backtesting_latest(sample: str = "main", strategy: str = "regime_based"):
    normalized_sample = _normalize_sample(sample)
    if normalized_sample == "main":
        from src.riskbex.api.operational import snapshot, backtest_points
        data = snapshot()
        points = backtest_points(data, strategy)
        if not points.empty:
            return dict(points.iloc[-1].to_dict(), sample='MAIN',
                        methodology=METHODOLOGY if strategy == 'regime_based' else
                        'XGBoost next-session prediction with training CVaR exposure; prior-close target applied once.',
                        signal=data['latest'])
        raise HTTPException(status_code=503, detail='No realised MAIN backtest rows available.')
    if strategy != 'regime_based':
        raise HTTPException(status_code=400, detail='ML strategies are available only for operational MAIN.')
    results_df = _load_results_or_raise(normalized_sample)
    if results_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No adaptive backtest rows found for sample {normalized_sample}.",
        )
    return _latest_response(results_df.iloc[-1], normalized_sample)
