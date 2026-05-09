"""Segment KPI bridge, features, and reports."""

import hashlib
from pathlib import Path

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def build_tsmc_monthly_segment_kpis(months: int = 24) -> pd.DataFrame:
    """Bridge official TSMC monthly revenue into the segment KPI layer."""

    initialize_database()
    with connect() as conn:
        monthly = conn.execute(
            """
            SELECT period, year, month, revenue_ntd_million, mom_pct, yoy_pct, source_url
            FROM tsmc_monthly_revenue
            ORDER BY period DESC
            LIMIT ?
            """,
            [months],
        ).fetchdf()

    if monthly.empty:
        return pd.DataFrame()

    rows = []
    ingested_at = utc_now_naive()
    for _, row in monthly.sort_values("period").iterrows():
        period = pd.to_datetime(row["period"]).date()
        base = {
            "period_end": period,
            "fiscal_year": int(row["year"]),
            "fiscal_quarter": _quarter_from_month(int(row["month"])),
            "period_type": "month",
            "ticker": "TSM",
            "kpi_group": "monthly",
            "segment_name": "total",
            "source_type": "monthly_revenue",
            "source_url": row["source_url"],
            "source_accession_number": None,
            "filed_date": None,
            "is_reported": True,
            "is_derived": False,
            "derivation_method": None,
            "confidence": "high",
            "notes": "Official TSMC monthly revenue bridge.",
            "ingested_at": ingested_at,
        }
        for kpi_name, value, unit, currency in (
            ("monthly_revenue_twd", row["revenue_ntd_million"], "TWD_mn", "TWD"),
            ("monthly_revenue_mom", row["mom_pct"], "percent", None),
            ("monthly_revenue_yoy", row["yoy_pct"], "percent", None),
        ):
            item = {
                **base,
                "kpi_name": kpi_name,
                "kpi_value": None if pd.isna(value) else float(value),
                "unit": unit,
                "currency": currency,
            }
            item["segment_kpi_id"] = _segment_kpi_id(item)
            rows.append(item)

    return pd.DataFrame(rows)


def store_segment_kpis(segment_kpis: pd.DataFrame) -> int:
    """Store segment KPI rows."""

    if segment_kpis.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, segment_kpis, "segment_kpis", ["segment_kpi_id"])


def build_segment_features() -> pd.DataFrame:
    """Build lightweight segment driver features from current segment KPIs."""

    initialize_database()
    with connect() as conn:
        segments = conn.execute("SELECT * FROM segments_view").fetchdf()
        kpis = conn.execute("SELECT * FROM segment_kpis").fetchdf()

    rows = []
    ingested_at = utc_now_naive()
    rows.extend(_segment_view_features(segments, ingested_at))
    rows.extend(_tsm_monthly_features(kpis, ingested_at))
    return pd.DataFrame(rows)


def store_segment_features(segment_features: pd.DataFrame) -> int:
    """Store segment feature rows."""

    if segment_features.empty:
        return 0
    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM segment_features")
        return upsert_dataframe(
            conn,
            segment_features,
            "segment_features",
            ["date", "ticker", "feature_name"],
        )


def build_segment_dashboard(output_path: Path) -> Path:
    """Write a concise segment dashboard markdown report."""

    initialize_database()
    with connect() as conn:
        features = conn.execute(
            """
            SELECT *
            FROM segment_features
            ORDER BY ticker, feature_name
            """
        ).fetchdf()

    lines = ["# Segment Dashboard", ""]
    if features.empty:
        lines.append("No segment features are available yet.")
    else:
        for ticker, group in features.groupby("ticker"):
            lines.extend([f"## {ticker}", ""])
            for _, row in group.iterrows():
                lines.append(
                    "- "
                    f"{row['feature_name']}: value={_fmt_value(row['feature_value'])}, "
                    f"score={_fmt_value(row['feature_score'])}, "
                    f"direction={row['direction']}, confidence={_fmt_value(row['confidence'])}"
                )
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _segment_view_features(segments: pd.DataFrame, ingested_at) -> list[dict]:
    if segments.empty:
        return []

    rows = []
    segments["period_end"] = pd.to_datetime(segments["period_end"])
    if "period_type" in segments.columns and (segments["period_type"] == "quarter").any():
        segments = segments[segments["period_type"] == "quarter"]
    latest = (
        segments.sort_values("period_end")
        .groupby(["ticker", "segment_name"], dropna=False)
        .tail(1)
    )
    for _, row in latest.iterrows():
        date = row["period_end"].date()
        segment_slug = _slug(row["segment_name"])
        source_id = _source_ids(row)
        if pd.notna(row["segment_revenue_growth_yoy"]):
            value = float(row["segment_revenue_growth_yoy"])
            rows.append(
                _feature_row(
                    date,
                    row["ticker"],
                    f"{segment_slug}_revenue_growth_yoy",
                    value,
                    _score_growth(value),
                    _direction(value),
                    _confidence(row["confidence"]),
                    source_id,
                    ingested_at,
                )
            )
        if pd.notna(row["segment_margin"]):
            value = float(row["segment_margin"])
            rows.append(
                _feature_row(
                    date,
                    row["ticker"],
                    f"{segment_slug}_margin",
                    value,
                    _score_margin(value),
                    _direction(value),
                    _confidence(row["confidence"]),
                    source_id,
                    ingested_at,
                )
            )
    return rows


def _tsm_monthly_features(kpis: pd.DataFrame, ingested_at) -> list[dict]:
    if kpis.empty:
        return []
    monthly = kpis[
        (kpis["ticker"] == "TSM")
        & (kpis["period_type"] == "month")
        & (kpis["kpi_name"].isin(["monthly_revenue_yoy", "monthly_revenue_mom"]))
    ].copy()
    if monthly.empty:
        return []
    monthly["period_end"] = pd.to_datetime(monthly["period_end"])
    rows = []
    for kpi_name, feature_name in (
        ("monthly_revenue_yoy", "monthly_revenue_momentum_score"),
        ("monthly_revenue_mom", "monthly_revenue_sequential_score"),
    ):
        item = monthly[monthly["kpi_name"] == kpi_name].sort_values("period_end").tail(1)
        if item.empty:
            continue
        row = item.iloc[0]
        if pd.isna(row["kpi_value"]):
            continue
        value = float(row["kpi_value"]) / 100.0
        rows.append(
            _feature_row(
                row["period_end"].date(),
                "TSM",
                feature_name,
                value,
                _score_growth(value),
                _direction(value),
                _confidence(row["confidence"]),
                row["segment_kpi_id"],
                ingested_at,
            )
        )
    return rows


def _feature_row(
    date,
    ticker: str,
    feature_name: str,
    feature_value: float,
    feature_score: float,
    direction: str,
    confidence: float,
    source_kpi_ids: str,
    ingested_at,
) -> dict:
    return {
        "date": date,
        "ticker": ticker,
        "feature_name": feature_name,
        "feature_value": feature_value,
        "feature_score": feature_score,
        "direction": direction,
        "confidence": confidence,
        "source_kpi_ids": source_kpi_ids,
        "ingested_at": ingested_at,
    }


def _segment_kpi_id(row: dict) -> str:
    key_columns = (
        "ticker",
        "period_end",
        "period_type",
        "kpi_group",
        "segment_name",
        "kpi_name",
    )
    key = "|".join(
        str(row.get(column, ""))
        for column in key_columns
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"segment_kpi_{digest}"


def _quarter_from_month(month: int) -> str:
    return f"Q{((month - 1) // 3) + 1}"


def _slug(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("&", "and").replace("/", "_")


def _score_growth(value: float) -> float:
    if pd.isna(value):
        return float("nan")
    return max(0.0, min(100.0, 50.0 + value * 100.0))


def _score_margin(value: float) -> float:
    if pd.isna(value):
        return float("nan")
    return max(0.0, min(100.0, value * 100.0))


def _direction(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _confidence(value: object) -> float:
    if pd.isna(value):
        return 0.6
    normalized = str(value).strip().lower()
    if normalized == "high":
        return 0.9
    if normalized == "medium":
        return 0.7
    if normalized == "low":
        return 0.5
    try:
        return float(normalized)
    except ValueError:
        return 0.6


def _source_ids(row: pd.Series) -> str:
    if "segment_kpi_id" in row and pd.notna(row["segment_kpi_id"]):
        return str(row["segment_kpi_id"])
    parts = [row.get("ticker"), row.get("segment_name"), row.get("period_end")]
    return "|".join(str(part) for part in parts)


def _fmt_value(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"
