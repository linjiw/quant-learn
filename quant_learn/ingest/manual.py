"""Manual CSV importers for curated events and segment KPIs."""

from pathlib import Path

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def import_events(path: Path) -> int:
    """Import manually curated events from CSV."""

    df = pd.read_csv(path)
    required = {"event_id", "event_date", "ticker", "event_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required event columns: {sorted(missing)}")

    for optional in (
        "event_name",
        "event_description",
        "source",
        "source_url",
        "importance_score",
        "expected_value",
        "actual_value",
        "surprise_pct",
        "metadata_json",
    ):
        if optional not in df.columns:
            df[optional] = None

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date
    df["ingested_at"] = utc_now_naive()
    df = df[
        [
            "event_id",
            "event_date",
            "ticker",
            "event_type",
            "event_name",
            "event_description",
            "source",
            "source_url",
            "importance_score",
            "expected_value",
            "actual_value",
            "surprise_pct",
            "metadata_json",
            "ingested_at",
        ]
    ]
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, df, "events", ["event_id"])


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
