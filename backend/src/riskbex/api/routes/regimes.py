from typing import Optional

from fastapi import APIRouter, HTTPException

from src.riskbex.api.schemas import (
    DurationSummaryRow,
    ModelSelectionRow,
    RegimeHistoryPoint,
    RegimeLatestResponse,
    RegimeSummaryRow,
    TransitionMatrixRow,
)
from src.riskbex.data.loaders import (
    load_duration_summary,
    load_model_selection,
    load_regime_dataset,
    load_regime_summary,
    load_transition_matrix,
)


router = APIRouter()

VALID_SPLITS = {"MAIN", "ROBUST"}
SPLIT_COLUMNS = {
    "MAIN": {
        "regime": "main_regime",
        "probabilities": [
            "main_p_regime_0",
            "main_p_regime_1",
            "main_p_regime_2",
        ],
    },
    "ROBUST": {
        "regime": "robust_regime",
        "probabilities": [
            "robust_p_regime_0",
            "robust_p_regime_1",
            "robust_p_regime_2",
        ],
    },
}


def _normalize_split(split):
    normalized_split = split.upper()
    if normalized_split not in VALID_SPLITS:
        raise HTTPException(status_code=400, detail="split must be MAIN or ROBUST")
    return normalized_split


def _format_date(value):
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)


def _build_label_mapping(regime_summary_df, split):
    split_summary = regime_summary_df[regime_summary_df["split"] == split]
    return {
        int(row["regime"]): {
            "economic_label": str(row["economic_label"]),
            "risk_order": int(row["risk_order"]),
        }
        for _, row in split_summary.iterrows()
    }


def _label_for_regime(label_mapping, regime):
    if regime not in label_mapping:
        raise HTTPException(
            status_code=500,
            detail=f"Missing economic label mapping for regime {regime}",
        )
    return label_mapping[regime]


def _build_regime_point(row, split, label_mapping, include_dominant_probability=False):
    split_config = SPLIT_COLUMNS[split]
    regime = int(row[split_config["regime"]])
    labels = _label_for_regime(label_mapping, regime)
    probabilities = [float(row[column]) for column in split_config["probabilities"]]
    point = {
        "date": _format_date(row["date"]),
        "split": split,
        "regime": regime,
        "economic_label": labels["economic_label"],
        "risk_order": labels["risk_order"],
        "p_regime_0": probabilities[0],
        "p_regime_1": probabilities[1],
        "p_regime_2": probabilities[2],
    }
    if include_dominant_probability:
        point["dominant_probability"] = max(probabilities)
    return point


def _parse_limit(limit):
    if limit is None:
        return 250
    if limit.lower() == "all":
        return None
    try:
        parsed_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="limit must be all or a positive integer") from exc
    if parsed_limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be all or a positive integer")
    return parsed_limit


def _records(df):
    return df.to_dict(orient="records")


@router.get("/regimes/latest", response_model=RegimeLatestResponse)
def regimes_latest(split: str = "MAIN"):
    normalized_split = _normalize_split(split)
    regime_df = load_regime_dataset()
    regime_summary_df = load_regime_summary()
    label_mapping = _build_label_mapping(regime_summary_df, normalized_split)

    latest = regime_df.iloc[-1]
    return _build_regime_point(
        latest,
        normalized_split,
        label_mapping,
        include_dominant_probability=True,
    )


@router.get("/regimes/history", response_model=list[RegimeHistoryPoint])
def regimes_history(split: str = "MAIN", limit: Optional[str] = "250"):
    normalized_split = _normalize_split(split)
    records_limit = _parse_limit(limit)
    regime_df = load_regime_dataset()
    regime_summary_df = load_regime_summary()
    label_mapping = _build_label_mapping(regime_summary_df, normalized_split)

    output_df = regime_df if records_limit is None else regime_df.tail(records_limit)
    return [
        _build_regime_point(row, normalized_split, label_mapping)
        for _, row in output_df.iterrows()
    ]


@router.get("/regimes/summary", response_model=list[RegimeSummaryRow])
def regimes_summary(split: Optional[str] = None):
    summary_df = load_regime_summary()
    if split is not None:
        summary_df = summary_df[summary_df["split"] == _normalize_split(split)]
    return _records(summary_df)


@router.get("/regimes/model-selection", response_model=list[ModelSelectionRow])
def regimes_model_selection():
    return _records(load_model_selection())


@router.get("/regimes/transitions", response_model=list[TransitionMatrixRow])
def regimes_transitions(split: Optional[str] = None):
    transition_df = load_transition_matrix()
    if split is not None:
        transition_df = transition_df[transition_df["split"] == _normalize_split(split)]
    return _records(transition_df)


@router.get("/regimes/durations", response_model=list[DurationSummaryRow])
def regimes_durations(split: Optional[str] = None, scope: Optional[str] = None):
    duration_df = load_duration_summary()
    if split is not None:
        duration_df = duration_df[duration_df["split"] == _normalize_split(split)]
    if scope is not None:
        duration_df = duration_df[duration_df["scope"] == scope.upper()]
    return _records(duration_df)
