"""Manual importers for the AI trusted-execution framework tracker."""

from pathlib import Path

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def import_ai_framework_indicators(path: Path) -> int:
    """Import dated leading-indicator observations."""

    df = pd.read_csv(path)
    required = {
        "as_of_date",
        "indicator_id",
        "control_layer",
        "indicator_name",
        "direction",
    }
    _require_columns(df, required, "indicator")
    for optional in (
        "indicator_group",
        "metric_name",
        "current_value",
        "target_value",
        "warning_value",
        "unit",
        "status",
        "importance_score",
        "confidence",
        "source",
        "source_url",
        "notes",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["as_of_date"] = _date_column(df["as_of_date"])
    numeric_columns = (
        "current_value",
        "target_value",
        "warning_value",
        "importance_score",
        "confidence",
    )
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["control_layer"] = _normalized_text_column(df["control_layer"])
    df["direction"] = _normalized_text_column(df["direction"])
    df["status"] = _normalized_text_column(df["status"])
    df["ingested_at"] = utc_now_naive()

    columns = [
        "as_of_date",
        "indicator_id",
        "control_layer",
        "indicator_name",
        "indicator_group",
        "metric_name",
        "current_value",
        "target_value",
        "warning_value",
        "unit",
        "direction",
        "status",
        "importance_score",
        "confidence",
        "source",
        "source_url",
        "notes",
        "ingested_at",
    ]
    return _upsert(df[columns], "ai_framework_indicators", ["as_of_date", "indicator_id"])


def import_ai_framework_predictions(path: Path) -> int:
    """Import dated falsifiable predictions."""

    df = pd.read_csv(path)
    required = {
        "as_of_date",
        "prediction_id",
        "control_layer",
        "prediction_text",
        "falsifier",
    }
    _require_columns(df, required, "prediction")
    for optional in (
        "deadline",
        "target_metric",
        "target_threshold",
        "current_value",
        "unit",
        "status",
        "probability",
        "confidence",
        "source",
        "source_url",
        "notes",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["as_of_date"] = _date_column(df["as_of_date"])
    df["deadline"] = _date_column(df["deadline"])
    for column in ("current_value", "probability", "confidence"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["probability"] = df["probability"].map(_normalize_probability)
    df["confidence"] = df["confidence"].map(_normalize_probability)
    df["control_layer"] = _normalized_text_column(df["control_layer"])
    df["status"] = _normalized_text_column(df["status"])
    df["ingested_at"] = utc_now_naive()

    columns = [
        "as_of_date",
        "prediction_id",
        "control_layer",
        "prediction_text",
        "deadline",
        "target_metric",
        "target_threshold",
        "current_value",
        "unit",
        "status",
        "probability",
        "confidence",
        "falsifier",
        "source",
        "source_url",
        "notes",
        "ingested_at",
    ]
    return _upsert(df[columns], "ai_framework_predictions", ["as_of_date", "prediction_id"])


def import_ai_framework_scenarios(path: Path) -> int:
    """Import dated scenario probabilities."""

    df = pd.read_csv(path)
    required = {"as_of_date", "scenario_id", "scenario_name", "probability"}
    _require_columns(df, required, "scenario")
    for optional in (
        "scenario_type",
        "thesis_impact",
        "portfolio_posture",
        "trigger_indicators",
        "notes",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["as_of_date"] = _date_column(df["as_of_date"])
    df["probability"] = (
        pd.to_numeric(df["probability"], errors="coerce").map(_normalize_probability)
    )
    df["ingested_at"] = utc_now_naive()

    columns = [
        "as_of_date",
        "scenario_id",
        "scenario_name",
        "probability",
        "scenario_type",
        "thesis_impact",
        "portfolio_posture",
        "trigger_indicators",
        "notes",
        "ingested_at",
    ]
    return _upsert(df[columns], "ai_framework_scenarios", ["as_of_date", "scenario_id"])


def import_ai_framework_holdings(path: Path) -> int:
    """Import dated research-portfolio holdings and target weights."""

    df = pd.read_csv(path)
    required = {"as_of_date", "ticker", "target_weight", "control_layers", "thesis"}
    _require_columns(df, required, "holding")
    for optional in (
        "holding_name",
        "bucket",
        "current_weight",
        "min_weight",
        "max_weight",
        "risk_flags",
        "exposure_map",
        "action_bias",
        "notes",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["as_of_date"] = _date_column(df["as_of_date"])
    for column in ("target_weight", "current_weight", "min_weight", "max_weight"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["current_weight"] = df["current_weight"].where(
        df["current_weight"].notna(),
        df["target_weight"],
    )
    df["min_weight"] = df["min_weight"].where(df["min_weight"].notna(), df["target_weight"] * 0.75)
    df["max_weight"] = df["max_weight"].where(df["max_weight"].notna(), df["target_weight"] * 1.25)
    df["action_bias"] = _normalized_text_column(df["action_bias"])
    df["ingested_at"] = utc_now_naive()

    columns = [
        "as_of_date",
        "ticker",
        "holding_name",
        "bucket",
        "target_weight",
        "current_weight",
        "min_weight",
        "max_weight",
        "control_layers",
        "exposure_map",
        "thesis",
        "risk_flags",
        "action_bias",
        "notes",
        "ingested_at",
    ]
    return _upsert(df[columns], "ai_framework_holdings", ["as_of_date", "ticker"])


def import_ai_control_right_scores(path: Path) -> int:
    """Import dated company-to-control-right score mappings."""

    df = pd.read_csv(path)
    required = {
        "as_of_date",
        "ticker",
        "capacity_score",
        "cost_score",
        "authority_score",
        "outcome_score",
        "physical_ai_score",
    }
    _require_columns(df, required, "control-right score")
    for optional in (
        "holding_name",
        "confidence",
        "scoring_method",
        "source",
        "notes",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["as_of_date"] = _date_column(df["as_of_date"])
    numeric_columns = (
        "capacity_score",
        "cost_score",
        "authority_score",
        "outcome_score",
        "physical_ai_score",
        "confidence",
    )
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["confidence"] = df["confidence"].map(_normalize_probability)
    df["ingested_at"] = utc_now_naive()

    columns = [
        "as_of_date",
        "ticker",
        "holding_name",
        "capacity_score",
        "cost_score",
        "authority_score",
        "outcome_score",
        "physical_ai_score",
        "confidence",
        "scoring_method",
        "source",
        "notes",
        "ingested_at",
    ]
    return _upsert(df[columns], "ai_control_right_scores", ["as_of_date", "ticker"])


def import_ai_framework(
    *,
    indicators_path: Path,
    predictions_path: Path,
    scenarios_path: Path,
    holdings_path: Path,
    control_scores_path: Path,
) -> dict[str, int]:
    """Import the complete AI framework tracker seed/update set."""

    return {
        "indicators": import_ai_framework_indicators(indicators_path),
        "predictions": import_ai_framework_predictions(predictions_path),
        "scenarios": import_ai_framework_scenarios(scenarios_path),
        "holdings": import_ai_framework_holdings(holdings_path),
        "control_scores": import_ai_control_right_scores(control_scores_path),
    }


def _require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required {label} columns: {sorted(missing)}")


def _date_column(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date


def _normalized_text_column(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def _normalize_probability(value) -> float:
    if pd.isna(value):
        return value
    value = float(value)
    if value > 1:
        return value / 100.0
    return value


def _upsert(df: pd.DataFrame, table: str, key_columns: list[str]) -> int:
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, df, table, key_columns)
