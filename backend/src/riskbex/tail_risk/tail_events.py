import pandas as pd


REQUIRED_TAIL_EVENT_COLUMNS = ["date", "ret_1d"]


def _validate_required_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required tail event columns: {missing_columns}")


def compute_tail_threshold(df: pd.DataFrame, quantile: float = 0.05) -> float:
    _validate_required_columns(df, REQUIRED_TAIL_EVENT_COLUMNS)
    if df.empty:
        raise ValueError("Cannot compute tail threshold from an empty dataset.")
    if df["ret_1d"].isna().any():
        raise ValueError("ret_1d contains null values.")

    threshold = float(df["ret_1d"].quantile(quantile))
    if pd.isna(threshold):
        raise ValueError("Tail threshold is NaN.")
    return threshold


def add_tail_event_flag(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if pd.isna(threshold):
        raise ValueError("Tail threshold is NaN.")
    output_df = df.copy()
    output_df["stress_tail_event"] = output_df["ret_1d"] <= threshold
    validate_tail_events(output_df)
    return output_df


def validate_tail_events(df: pd.DataFrame) -> None:
    _validate_required_columns(df, REQUIRED_TAIL_EVENT_COLUMNS)
    if "stress_tail_event" not in df.columns:
        raise ValueError("stress_tail_event column is required.")
    if df["date"].isna().any():
        raise ValueError("date contains null or non-parseable values.")
    if df["date"].duplicated().any():
        raise ValueError("date contains duplicated values.")
    if not df["date"].is_monotonic_increasing:
        raise ValueError("date must be sorted increasingly.")
    if df["ret_1d"].isna().any():
        raise ValueError("ret_1d contains null values.")
    if df["stress_tail_event"].dtype != bool:
        raise ValueError("stress_tail_event must be boolean.")
    if not df["stress_tail_event"].any():
        raise ValueError("At least one stress_tail_event is required.")

