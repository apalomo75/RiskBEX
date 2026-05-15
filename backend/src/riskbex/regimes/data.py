from src.riskbex.config import REGIME_FEATURES, REGIME_SPLIT_COLUMN, REGIME_TRAIN_LABEL


def get_regime_feature_columns():
    return list(REGIME_FEATURES)


def validate_regime_columns(df):
    required_columns = [*REGIME_FEATURES, REGIME_SPLIT_COLUMN]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required regime columns: {missing_columns}")


def prepare_regime_input(df):
    validate_regime_columns(df)
    keep_columns = []
    if "date" in df.columns:
        keep_columns.append("date")
    keep_columns.extend(REGIME_FEATURES)
    if REGIME_SPLIT_COLUMN in df.columns:
        keep_columns.append(REGIME_SPLIT_COLUMN)

    prepared_df = df[keep_columns].copy()
    prepared_df = prepared_df.dropna(subset=REGIME_FEATURES)
    if "date" in prepared_df.columns:
        prepared_df = prepared_df.sort_values("date")
    return prepared_df.reset_index(drop=True)


def prepare_regime_train_data(df):
    prepared_df = prepare_regime_input(df)
    return prepared_df[
        prepared_df[REGIME_SPLIT_COLUMN] == REGIME_TRAIN_LABEL
    ].reset_index(drop=True)
