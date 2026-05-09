"""Rule-based event review generation."""

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def build_event_reviews() -> pd.DataFrame:
    """Build one readable review row per event impact."""

    initialize_database()
    with connect() as conn:
        events = conn.execute(
            """
            SELECT
                e.event_id,
                COALESCE(i.affected_ticker, e.primary_ticker, e.ticker) AS affected_ticker,
                COALESCE(e.reaction_date, e.event_date) AS reaction_date,
                e.event_type,
                e.event_name,
                e.thesis_tag AS event_thesis_tag,
                i.expected_direction,
                i.driver_tag,
                COALESCE(i.thesis_tag, e.thesis_tag) AS thesis_tag,
                i.impact_confidence
            FROM events e
            LEFT JOIN event_impacts i
                ON e.event_id = i.event_id
            ORDER BY e.event_date, e.event_id, affected_ticker
            """
        ).fetchdf()
        returns = conn.execute("SELECT * FROM event_returns").fetchdf()
        metrics = conn.execute("SELECT * FROM event_metrics").fetchdf()
        segment_features = conn.execute("SELECT * FROM segment_features").fetchdf()

    if events.empty:
        return pd.DataFrame()

    ingested_at = utc_now_naive()
    reviews = []
    for _, event in events.iterrows():
        event_returns = returns[
            (returns["event_id"] == event["event_id"])
            & (returns["affected_ticker"] == event["affected_ticker"])
        ]
        event_metrics = metrics[metrics["event_id"] == event["event_id"]]
        event_segment_features = _event_segment_features(event, segment_features)
        data_quality_flag = _review_quality(event_returns)
        confidence = _review_confidence(event, event_returns, event_metrics, data_quality_flag)

        reviews.append(
            {
                "event_id": event["event_id"],
                "affected_ticker": event["affected_ticker"],
                "reaction_date": pd.to_datetime(event["reaction_date"]).date(),
                "event_type": event["event_type"],
                "summary": _summary(event),
                "raw_reaction_summary": _raw_reaction_summary(event_returns),
                "benchmark_attribution_summary": _benchmark_attribution_summary(event_returns),
                "metric_surprise_summary": _metric_surprise_summary(event_metrics),
                "linked_segment_features": _linked_segment_features(event_segment_features),
                "linked_kpi_ids": _linked_kpi_ids(event_segment_features),
                "fundamental_context_summary": _fundamental_context_summary(
                    event,
                    event_segment_features,
                ),
                "interpretation": _interpretation(event_returns, data_quality_flag),
                "thesis_impact": _thesis_impact(event),
                "confidence": confidence,
                "data_quality_flag": data_quality_flag,
                "analysis_status": _review_status(event_returns),
                "created_at": ingested_at,
                "ingested_at": ingested_at,
            }
        )

    return pd.DataFrame(reviews)


def store_event_reviews(event_reviews: pd.DataFrame) -> int:
    """Store generated event reviews."""

    if event_reviews.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(
            conn,
            event_reviews,
            "event_reviews",
            ["event_id", "affected_ticker"],
        )


def _summary(event: pd.Series) -> str:
    event_name = event.get("event_name") or event["event_id"]
    return (
        f"{event['affected_ticker']} review for {event_name} "
        f"on {pd.to_datetime(event['reaction_date']).date()}."
    )


def _raw_reaction_summary(event_returns: pd.DataFrame) -> str:
    raw_0_p1 = _first_raw_return(event_returns, "0_p1")
    raw_0_p5 = _first_raw_return(event_returns, "0_p5")
    return f"Raw return was {_fmt_pct(raw_0_p1)} over 0_p1 and {_fmt_pct(raw_0_p5)} over 0_p5."


def _benchmark_attribution_summary(event_returns: pd.DataFrame) -> str:
    rows = event_returns[event_returns["return_window"] == "0_p5"]
    if rows.empty:
        return "No 0_p5 benchmark attribution is available."

    parts = []
    for _, row in rows.sort_values("benchmark_ticker").iterrows():
        benchmark_label = (
            f"{row['benchmark_ticker']}:{row['model_name']}"
            if row["benchmark_type"] == "factor_model"
            else row["benchmark_ticker"]
        )
        parts.append(
            f"{benchmark_label} abnormal {_fmt_pct(row['abnormal_return'])}"
            f" ({row['data_quality_flag']})"
        )
    return "0_p5 benchmark attribution: " + "; ".join(parts) + "."


def _metric_surprise_summary(event_metrics: pd.DataFrame) -> str:
    if event_metrics.empty:
        return "No event metric evidence is attached yet."

    parts = []
    for _, metric in event_metrics.sort_values("metric_name").iterrows():
        parts.append(
            f"{metric['metric_name']} {metric['surprise_direction']} "
            f"surprise {_fmt_pct(metric['surprise_pct'])}"
        )
    return "Metric evidence: " + "; ".join(parts) + "."


def _event_segment_features(event: pd.Series, segment_features: pd.DataFrame) -> pd.DataFrame:
    if segment_features.empty:
        return pd.DataFrame()
    reaction_date = pd.to_datetime(event["reaction_date"], errors="coerce")
    if pd.isna(reaction_date):
        return pd.DataFrame()
    ticker_features = segment_features[
        segment_features["ticker"] == event["affected_ticker"]
    ].copy()
    if ticker_features.empty:
        return pd.DataFrame()
    ticker_features["date"] = pd.to_datetime(ticker_features["date"], errors="coerce")
    ticker_features = ticker_features[ticker_features["date"] <= reaction_date]
    if ticker_features.empty:
        return pd.DataFrame()
    return (
        ticker_features.sort_values(["feature_name", "date"])
        .groupby("feature_name", group_keys=False)
        .tail(1)
        .sort_values(["date", "feature_score", "feature_name"], ascending=[False, False, True])
    )


def _linked_segment_features(event_segment_features: pd.DataFrame) -> str:
    if event_segment_features.empty:
        return ""
    return ",".join(event_segment_features["feature_name"].astype(str).tolist())


def _linked_kpi_ids(event_segment_features: pd.DataFrame) -> str:
    if event_segment_features.empty:
        return ""
    values = []
    for source_ids in event_segment_features["source_kpi_ids"].dropna().astype(str):
        values.extend(item for item in source_ids.split(",") if item)
    return ",".join(dict.fromkeys(values))


def _fundamental_context_summary(event: pd.Series, event_segment_features: pd.DataFrame) -> str:
    if event_segment_features.empty:
        return "No point-in-time segment feature context is available for this event yet."

    parts = []
    for _, row in event_segment_features.iterrows():
        parts.append(
            f"{row['feature_name']} {row['direction']} "
            f"(score {_fmt_score(row['feature_score'])})"
        )
    return (
        f"Latest available {event['affected_ticker']} segment context before the event: "
        + "; ".join(parts)
        + "."
    )


def _interpretation(event_returns: pd.DataFrame, data_quality_flag: str) -> str:
    if data_quality_flag == "incomplete":
        return "Price attribution is incomplete; defer interpretation until enough prices exist."

    rows = event_returns[
        (event_returns["return_window"] == "0_p5")
        & (
            event_returns["benchmark_ticker"].isin(["SOXX", "SMH", "QQQ"])
            | (event_returns["benchmark_type"] == "factor_model")
        )
    ]
    if rows.empty:
        return "No benchmark attribution is available for interpretation."

    preferred = _preferred_abnormal_return(rows)
    if pd.isna(preferred):
        return "Benchmark attribution is present but abnormal return is unavailable."
    if _has_complete_factor_model(rows):
        if preferred >= 0.03:
            return "The reaction looks positive versus the pre-event factor model."
        if preferred <= -0.03:
            return "The reaction looks negative versus the pre-event factor model."
        return "The reaction was broadly in line with the pre-event factor model."
    if preferred >= 0.03:
        return "The reaction looks company- or chain-specific positive, not just beta."
    if preferred <= -0.03:
        return "The reaction looks company- or chain-specific negative versus benchmarks."
    return "The reaction was broadly in line with market or sector beta."


def _thesis_impact(event: pd.Series) -> str:
    direction = event.get("expected_direction") or "unknown"
    driver = event.get("driver_tag") or "unclassified_driver"
    thesis = event.get("thesis_tag") or event.get("event_thesis_tag") or "unclassified_thesis"
    return f"Driver {driver}; expected direction {direction}; thesis tag {thesis}."


def _review_quality(event_returns: pd.DataFrame) -> str:
    key_rows = event_returns[event_returns["return_window"].isin(["0_p1", "0_p5"])]
    if key_rows.empty:
        return "incomplete"
    if (key_rows["data_quality_flag"] == "incomplete").any():
        return "incomplete"
    if (key_rows["data_quality_flag"] == "mapped_reaction_date").any():
        return "mapped_reaction_date"
    return "complete"


def _review_status(event_returns: pd.DataFrame) -> str:
    key_rows = event_returns[event_returns["return_window"].isin(["0_p1", "0_p5"])]
    if key_rows.empty:
        return "excluded"
    statuses = set(key_rows["analysis_status"].dropna())
    if statuses and statuses.issubset({"ready"}):
        return "ready"
    if statuses and statuses.issubset({"ready", "partial_pending"}):
        return "partial_pending"
    if "data_issue" in statuses:
        return "data_issue"
    return "excluded"


def _review_confidence(
    event: pd.Series,
    event_returns: pd.DataFrame,
    event_metrics: pd.DataFrame,
    data_quality_flag: str,
) -> float:
    impact_confidence = event.get("impact_confidence")
    if pd.isna(impact_confidence):
        impact_confidence = 0.65
    metric_confidence = event_metrics["confidence"].dropna().mean()
    if pd.isna(metric_confidence):
        metric_confidence = 0.55
    quality_multiplier = 0.65 if data_quality_flag == "incomplete" else 1.0
    return float(min(0.95, ((impact_confidence + metric_confidence) / 2.0) * quality_multiplier))


def _preferred_abnormal_return(rows: pd.DataFrame) -> float:
    factor_rows = rows[
        (rows["benchmark_type"] == "factor_model")
        & (rows["data_quality_flag"].isin(["complete", "mapped_reaction_date"]))
    ]
    if not factor_rows.empty:
        value = factor_rows.iloc[0]["abnormal_return"]
        if pd.notna(value):
            return float(value)
    for benchmark in ("SOXX", "SMH", "QQQ"):
        benchmark_rows = rows[rows["benchmark_ticker"] == benchmark]
        if not benchmark_rows.empty:
            value = benchmark_rows.iloc[0]["abnormal_return"]
            if pd.notna(value):
                return float(value)
    return float("nan")


def _has_complete_factor_model(rows: pd.DataFrame) -> bool:
    factor_rows = rows[
        (rows["benchmark_type"] == "factor_model")
        & (rows["data_quality_flag"].isin(["complete", "mapped_reaction_date"]))
        & rows["abnormal_return"].notna()
    ]
    return not factor_rows.empty


def _first_raw_return(event_returns: pd.DataFrame, return_window: str) -> float:
    rows = event_returns[event_returns["return_window"] == return_window]
    if rows.empty:
        return float("nan")
    value = rows.iloc[0]["raw_return"]
    return float(value) if pd.notna(value) else float("nan")


def _fmt_pct(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _fmt_score(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.0f}"
