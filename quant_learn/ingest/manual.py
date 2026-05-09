"""Manual CSV importers for curated events and segment KPIs."""

from pathlib import Path
from typing import Optional

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def import_events(path: Path) -> int:
    """Import manually curated events from CSV."""

    df = pd.read_csv(path)
    if "primary_ticker" not in df.columns and "ticker" in df.columns:
        df["primary_ticker"] = df["ticker"]
    if "ticker" not in df.columns and "primary_ticker" in df.columns:
        df["ticker"] = df["primary_ticker"]

    required = {"event_id", "event_date", "ticker", "primary_ticker", "event_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required event columns: {sorted(missing)}")

    for optional in (
        "reaction_date",
        "event_name",
        "event_description",
        "source",
        "source_url",
        "after_market",
        "importance_score",
        "thesis_tag",
        "expected_value",
        "actual_value",
        "surprise_pct",
        "metadata_json",
        "created_at",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date
    df["reaction_date"] = pd.to_datetime(df["reaction_date"], errors="coerce").dt.date
    df["reaction_date"] = df["reaction_date"].where(df["reaction_date"].notna(), df["event_date"])
    df["after_market"] = df["after_market"].map(_parse_optional_bool)
    df["importance_score"] = pd.to_numeric(df["importance_score"], errors="coerce")
    df["expected_value"] = pd.to_numeric(df["expected_value"], errors="coerce")
    df["actual_value"] = pd.to_numeric(df["actual_value"], errors="coerce")
    df["surprise_pct"] = pd.to_numeric(df["surprise_pct"], errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["created_at"] = df["created_at"].where(df["created_at"].notna(), utc_now_naive())
    df["ingested_at"] = utc_now_naive()
    df = df[
        [
            "event_id",
            "event_date",
            "reaction_date",
            "ticker",
            "primary_ticker",
            "event_type",
            "event_name",
            "event_description",
            "source",
            "source_url",
            "after_market",
            "importance_score",
            "thesis_tag",
            "expected_value",
            "actual_value",
            "surprise_pct",
            "metadata_json",
            "created_at",
            "ingested_at",
        ]
    ]
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, df, "events", ["event_id"])


def import_event_impacts(path: Path) -> int:
    """Import manually curated cross-ticker event impacts from CSV."""

    df = pd.read_csv(path)
    required = {"event_id", "affected_ticker"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required event impact columns: {sorted(missing)}")

    for optional in (
        "expected_direction",
        "driver_tag",
        "thesis_tag",
        "impact_confidence",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["impact_confidence"] = pd.to_numeric(df["impact_confidence"], errors="coerce")
    df["ingested_at"] = utc_now_naive()
    df = df[
        [
            "event_id",
            "affected_ticker",
            "expected_direction",
            "driver_tag",
            "thesis_tag",
            "impact_confidence",
            "ingested_at",
        ]
    ]
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, df, "event_impacts", ["event_id", "affected_ticker"])


def import_event_metrics(path: Path) -> int:
    """Import manually curated event surprise metrics from CSV."""

    df = pd.read_csv(path)
    required = {"event_id", "metric_name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required event metric columns: {sorted(missing)}")

    for optional in (
        "actual_value",
        "expected_value",
        "prior_value",
        "surprise_value",
        "surprise_pct",
        "unit",
        "source",
        "confidence",
        "metric_category",
        "metric_polarity",
        "surprise_direction",
    ):
        if optional not in df.columns:
            df[optional] = None

    numeric_columns = [
        "actual_value",
        "expected_value",
        "prior_value",
        "surprise_value",
        "surprise_pct",
        "confidence",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    missing_surprise = (
        df["surprise_value"].isna()
        & df["actual_value"].notna()
        & df["expected_value"].notna()
    )
    df.loc[missing_surprise, "surprise_value"] = (
        df.loc[missing_surprise, "actual_value"] - df.loc[missing_surprise, "expected_value"]
    )

    missing_surprise_pct = (
        df["surprise_pct"].isna()
        & df["surprise_value"].notna()
        & df["expected_value"].notna()
        & (df["expected_value"] != 0)
    )
    df.loc[missing_surprise_pct, "surprise_pct"] = (
        df.loc[missing_surprise_pct, "surprise_value"]
        / df.loc[missing_surprise_pct, "expected_value"].abs()
    )

    df["metric_category"] = df.apply(
        lambda row: _coalesce_text(
            row["metric_category"],
            _infer_metric_category(row["metric_name"]),
        ),
        axis=1,
    )
    df["metric_polarity"] = df.apply(
        lambda row: _coalesce_text(
            row["metric_polarity"],
            _infer_metric_polarity(row["metric_name"]),
        ),
        axis=1,
    )
    df["surprise_direction"] = df.apply(
        lambda row: _coalesce_text(
            row["surprise_direction"],
            _infer_surprise_direction(row["surprise_value"], row["surprise_pct"]),
        ),
        axis=1,
    )

    df["ingested_at"] = utc_now_naive()
    df = df[
        [
            "event_id",
            "metric_name",
            "actual_value",
            "expected_value",
            "prior_value",
            "surprise_value",
            "surprise_pct",
            "unit",
            "source",
            "confidence",
            "metric_category",
            "metric_polarity",
            "surprise_direction",
            "ingested_at",
        ]
    ]
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, df, "event_metrics", ["event_id", "metric_name"])


def import_segment_kpis(path: Path) -> int:
    """Import manually verified segment KPI observations from CSV."""

    df = pd.read_csv(path)
    required = {"ticker", "fiscal_period", "segment_name", "metric_name", "value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required segment KPI columns: {sorted(missing)}")

    for optional in ("fiscal_year", "period_end", "unit", "source_url"):
        if optional not in df.columns:
            df[optional] = None

    df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce").dt.date
    df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["ingested_at"] = utc_now_naive()
    df = df[
        [
            "ticker",
            "fiscal_period",
            "fiscal_year",
            "period_end",
            "segment_name",
            "metric_name",
            "value",
            "unit",
            "source_url",
            "ingested_at",
        ]
    ]
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(
            conn,
            df,
            "segment_kpis",
            ["ticker", "fiscal_period", "segment_name", "metric_name"],
        )


def _parse_optional_bool(value: object) -> Optional[bool]:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def _coalesce_text(value: object, default: str) -> str:
    if pd.isna(value):
        return default
    text = str(value).strip()
    return text or default


def _infer_metric_category(metric_name: object) -> str:
    metric = str(metric_name).strip().lower()
    if "capex" in metric or "capital" in metric:
        return "capital_intensity"
    if "revenue" in metric:
        return "demand"
    if "margin" in metric:
        return "profitability"
    if "eps" in metric or "earnings" in metric:
        return "earnings"
    if "inventory" in metric:
        return "supply_chain"
    return "other"


def _infer_metric_polarity(metric_name: object) -> str:
    metric = str(metric_name).strip().lower()
    if "capex" in metric or "capital" in metric:
        return "context_dependent"
    if any(token in metric for token in ("revenue", "margin", "eps", "earnings")):
        return "higher_is_better"
    if "inventory" in metric:
        return "context_dependent"
    return "context_dependent"


def _infer_surprise_direction(surprise_value: object, surprise_pct: object) -> str:
    value = surprise_pct
    if pd.isna(value):
        value = surprise_value
    if pd.isna(value):
        return "unknown"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"
