import math
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.riskbex.api.schemas import (
    TailRiskEventRow,
    TailRiskLatestResponse,
    TailRiskMetricRow,
    TailRiskThresholdRow,
)
from src.riskbex.data.loaders import (
    load_tail_analysis,
    load_tail_metrics,
    load_tail_thresholds,
)


router = APIRouter()

VALID_SAMPLES = {"main", "robust"}
METHODOLOGY = (
    "Tail events are defined as the worst 5% of OOS market returns. Strategy "
    "performance is evaluated on the same stress days for Buy & Hold and "
    "Regime Strategy."
)


def _normalize_sample(sample: str) -> str:
    normalized_sample = str(sample).lower()
    if normalized_sample not in VALID_SAMPLES:
        raise HTTPException(status_code=400, detail="sample must be main or robust")
    return normalized_sample


def _format_date(value):
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)


def _nullable_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed_value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed_value):
        return None
    return parsed_value


def _load_analysis_or_raise(sample: str):
    try:
        return load_tail_analysis(sample)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Tail risk outputs not found. Run scripts/run_tail_analysis.py first.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _load_metrics_or_raise():
    try:
        return load_tail_metrics()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Tail risk outputs not found. Run scripts/run_tail_analysis.py first.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _load_thresholds_or_raise():
    try:
        return load_tail_thresholds()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Tail risk outputs not found. Run scripts/run_tail_analysis.py first.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _event_records(df):
    output_df = df.copy()
    output_df["date"] = output_df["date"].map(_format_date)
    output_df["benchmark_tail_cum"] = output_df["benchmark_tail_cum"].map(_nullable_float)
    output_df["strategy_tail_cum"] = output_df["strategy_tail_cum"].map(_nullable_float)
    return output_df.to_dict(orient="records")


def _latest_response(row):
    return {
        "date": _format_date(row["date"]),
        "sample": str(row["sample"]),
        "regime": int(row["regime"]),
        "regime_label": str(row["regime_label"]),
        "risk_order": int(row["risk_order"]),
        "ret_1d": float(row["ret_1d"]),
        "stress_tail_event": bool(row["stress_tail_event"]),
        "tail_threshold": float(row["tail_threshold"]),
        "strategy_exposure": float(row["strategy_exposure"]),
        "benchmark_return": float(row["benchmark_return"]),
        "strategy_return": float(row["strategy_return"]),
        "benchmark_drawdown": float(row["benchmark_drawdown"]),
        "strategy_drawdown": float(row["strategy_drawdown"]),
        "benchmark_tail_cum": _nullable_float(row["benchmark_tail_cum"]),
        "strategy_tail_cum": _nullable_float(row["strategy_tail_cum"]),
        "methodology": METHODOLOGY,
    }


@router.get("/tail-risk/events", response_model=list[TailRiskEventRow])
def tail_risk_events(sample: str = "main"):
    normalized_sample = _normalize_sample(sample)
    analysis_df = _load_analysis_or_raise(normalized_sample)
    return _event_records(analysis_df)


@router.get("/tail-risk/metrics", response_model=list[TailRiskMetricRow])
def tail_risk_metrics():
    metrics_df = _load_metrics_or_raise()
    return metrics_df.to_dict(orient="records")


@router.get("/tail-risk/thresholds", response_model=list[TailRiskThresholdRow])
def tail_risk_thresholds():
    thresholds_df = _load_thresholds_or_raise()
    return thresholds_df.to_dict(orient="records")


@router.get("/tail-risk/latest", response_model=TailRiskLatestResponse)
def tail_risk_latest(sample: str = "main"):
    normalized_sample = _normalize_sample(sample)
    analysis_df = _load_analysis_or_raise(normalized_sample)
    if analysis_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No tail risk rows found for sample {normalized_sample}.",
        )
    return _latest_response(analysis_df.iloc[-1])
