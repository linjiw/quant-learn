"""Evidence cards, research stance, and decision memo generation."""

import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd

from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.research_views import load_research_views
from quant_learn.time import utc_now_naive
from quant_learn.universe import evidence_weights_by_ticker

EVIDENCE_COLUMNS = [
    "evidence_id",
    "run_id",
    "as_of_date",
    "ticker",
    "evidence_type",
    "source_table",
    "source_id",
    "source_date",
    "available_date",
    "direction",
    "strength",
    "confidence",
    "materiality",
    "summary",
    "metric_name",
    "metric_value",
    "comparison_value",
    "interpretation",
    "thesis_tag",
    "risk_tag",
    "data_quality_flag",
    "created_at",
    "ingested_at",
]

STANCE_COLUMNS = [
    "stance_id",
    "run_id",
    "as_of_date",
    "ticker",
    "stance",
    "stance_modifier",
    "confidence",
    "thesis_summary",
    "positive_evidence_ids",
    "negative_evidence_ids",
    "mixed_evidence_ids",
    "risk_flags",
    "falsifiers",
    "next_catalysts",
    "data_quality_caveats",
    "created_at",
    "ingested_at",
]

STANCE_COMPONENT_COLUMNS = [
    "run_id",
    "as_of_date",
    "ticker",
    "evidence_type",
    "direction",
    "weighted_score",
    "raw_strength",
    "avg_confidence",
    "evidence_count",
    "top_evidence_ids",
    "created_at",
    "ingested_at",
]

STANCE_CAP_COLUMNS = [
    "run_id",
    "as_of_date",
    "ticker",
    "cap_type",
    "cap_value",
    "reason",
    "applied",
    "created_at",
    "ingested_at",
]

STANCE_CONFLICT_COLUMNS = [
    "run_id",
    "as_of_date",
    "ticker",
    "conflict_type",
    "positive_evidence_ids",
    "negative_evidence_ids",
    "severity",
    "summary",
    "created_at",
    "ingested_at",
]

EVIDENCE_TYPE_WEIGHTS = evidence_weights_by_ticker()
_RESEARCH_VIEWS = load_research_views()
STATIC_THESIS = {
    ticker: (
        _RESEARCH_VIEWS[ticker].thesis_text
        if ticker in _RESEARCH_VIEWS
        else f"{ticker} lacks a manually maintained thesis."
    )
    for ticker in CORE_TICKERS
}
FALSIFIERS = {
    ticker: (
        _RESEARCH_VIEWS[ticker].falsifiers
        if ticker in _RESEARCH_VIEWS
        else ["Add a manual falsifier in data/manual/research_views.csv."]
    )
    for ticker in CORE_TICKERS
}
NEXT_CATALYSTS = {
    ticker: (
        _RESEARCH_VIEWS[ticker].next_catalysts
        if ticker in _RESEARCH_VIEWS
        else ["Add next catalysts in data/manual/research_views.csv."]
    )
    for ticker in CORE_TICKERS
}

STRENGTH_VALUES = {"low": 0.25, "medium": 0.50, "high": 0.75, "very_high": 1.00}
STANCE_ORDER = ["high_risk", "cautious", "neutral", "constructive", "strong_constructive"]
FACTOR_DOMINANCE_THRESHOLD = 0.55
FACTOR_LED_MODIFIER_THRESHOLD = 0.50
MIN_NON_FACTOR_POSITIVE_TYPES_FOR_STRONG = 2
MIN_NON_FACTOR_POSITIVE_COUNT_FOR_FACTOR_LED = 3

CONFIDENCE_CAP_VALUES = {
    "limited_evidence": 0.55,
    "missing_segment_evidence": 0.65,
    "missing_cash_flow_evidence": 0.75,
    "missing_factor_evidence": 0.75,
    "missing_valuation_evidence": 0.80,
    "data_quality_issues": 0.70,
    "conflicting_evidence": 0.75,
    "tsm_fx_model_gap": 0.65,
    "missing_non_factor_positive_evidence": 0.70,
    "factor_dominated_positive_evidence": 0.70,
    "insufficient_non_factor_positive_confirmation": 0.70,
    "negative_valuation_evidence": 0.70,
    "factor_led_insufficient_confirmation": 0.60,
    "residual_concentration": 0.70,
}

CONFIDENCE_CAP_REASONS = {
    "limited_evidence": "limited evidence coverage caps confidence",
    "missing_segment_evidence": "missing segment evidence prevents strong constructive stance",
    "missing_cash_flow_evidence": "missing cash-flow evidence caps confidence",
    "missing_factor_evidence": "missing factor residual evidence caps confidence",
    "missing_valuation_evidence": "missing valuation evidence leaves price discipline unresolved",
    "data_quality_issues": "multiple data-quality issues cap confidence",
    "conflicting_evidence": "positive and negative evidence are both material",
    "tsm_fx_model_gap": "TSM factor evidence is capped until USD/TWD is added to the model",
    "missing_non_factor_positive_evidence": (
        "strong constructive stance requires positive non-factor evidence"
    ),
    "factor_dominated_positive_evidence": (
        "positive evidence is factor-led and lacks enough non-factor confirmation"
    ),
    "insufficient_non_factor_positive_confirmation": (
        "strong constructive stance requires at least two non-factor positive evidence types"
    ),
    "negative_valuation_evidence": (
        "negative valuation evidence caps high-confidence positive stance"
    ),
    "factor_led_insufficient_confirmation": (
        "factor-led stance requires at least three non-factor positive evidence rows"
    ),
    "residual_concentration": (
        "positive residual evidence is concentrated in a small number of trading days"
    ),
}


def build_evidence_cards(
    as_of_date: Optional[str] = None,
    run_id: Optional[str] = None,
) -> pd.DataFrame:
    """Build evidence cards from event, segment, cash-flow, and factor layers."""

    initialize_database()
    with connect() as conn:
        event_reviews = conn.execute("SELECT * FROM event_reviews").fetchdf()
        event_returns = conn.execute("SELECT * FROM event_returns").fetchdf()
        segment_features = conn.execute("SELECT * FROM segment_features").fetchdf()
        cash_flow_features = conn.execute("SELECT * FROM cash_flow_features").fetchdf()
        valuation_features = conn.execute("SELECT * FROM valuation_features").fetchdf()
        factor_residuals = conn.execute(
            """
            SELECT
                r.*,
                e.r2,
                e.factor_corr_qqq_soxx,
                e.beta_qqq,
                e.beta_soxx,
                e.beta_tnx_bps
            FROM factor_residuals r
            LEFT JOIN factor_exposures e
              ON r.date = e.date
             AND r.ticker = e.ticker
             AND r.model_name = e.model_name
             AND r.lookback_window = e.lookback_window
            """
        ).fetchdf()
        residual_diagnostics = conn.execute("SELECT * FROM residual_diagnostics").fetchdf()

    cards = []
    effective_as_of = _as_of_date(
        as_of_date,
        event_reviews,
        segment_features,
        cash_flow_features,
        valuation_features,
        factor_residuals,
        residual_diagnostics,
    )
    created_at = utc_now_naive()
    cards.extend(_event_evidence(event_reviews, event_returns, effective_as_of, created_at))
    cards.extend(_segment_evidence(segment_features, effective_as_of, created_at))
    cards.extend(_cash_flow_evidence(cash_flow_features, effective_as_of, created_at))
    cards.extend(_valuation_evidence(valuation_features, effective_as_of, created_at))
    cards.extend(_factor_evidence(factor_residuals, effective_as_of, created_at))
    cards.extend(
        _residual_concentration_evidence(residual_diagnostics, effective_as_of, created_at)
    )

    if not cards:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    evidence = pd.DataFrame(cards)
    if not run_id:
        raise ValueError("run_id required: build_evidence_cards requires explicit run_id")
    evidence["run_id"] = run_id
    return evidence[EVIDENCE_COLUMNS].drop_duplicates(subset=["evidence_id"], keep="last")


def store_evidence_cards(evidence_cards: pd.DataFrame) -> int:
    """Legacy single-table rebuild for tests and fixtures.

    Production code must use `store_research_outputs` so evidence, stance, and
    audit tables are committed atomically.
    """

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM evidence_cards")
        if evidence_cards.empty:
            return 0
        return upsert_dataframe(conn, evidence_cards, "evidence_cards", ["evidence_id"])


def build_research_stance(
    as_of_date: Optional[str] = None,
    run_id: Optional[str] = None,
    evidence_cards: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Build research stance rows.

    If `evidence_cards` is provided, the database is not queried. This supports
    the in-memory production pipeline before the new run is committed.
    """

    initialize_database()
    if evidence_cards is None:
        with connect() as conn:
            evidence = conn.execute("SELECT * FROM evidence_cards").fetchdf()
    else:
        evidence = evidence_cards.copy()

    if evidence.empty:
        return pd.DataFrame(columns=STANCE_COLUMNS)

    evidence["source_date"] = pd.to_datetime(evidence["source_date"], errors="coerce")
    effective_as_of = _as_of_date(as_of_date, evidence)
    output_run_id = _run_id_from_frames(run_id, evidence)
    created_at = utc_now_naive()
    rows = []
    for ticker in CORE_TICKERS:
        ticker_evidence = evidence[evidence["ticker"] == ticker].copy()
        rows.append(
            _stance_row(ticker, ticker_evidence, effective_as_of, output_run_id, created_at)
        )
    return pd.DataFrame(rows)[STANCE_COLUMNS]


def store_research_stance(research_stance: pd.DataFrame) -> int:
    """Legacy single-table rebuild for tests and fixtures.

    Production code must use `store_research_outputs` so evidence, stance, and
    audit tables are committed atomically.
    """

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM research_stance")
        if research_stance.empty:
            return 0
        return upsert_dataframe(conn, research_stance, "research_stance", ["stance_id"])


def build_stance_audit_tables(
    as_of_date: Optional[str] = None,
    run_id: Optional[str] = None,
    evidence_cards: Optional[pd.DataFrame] = None,
    research_stance: Optional[pd.DataFrame] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build stance component, confidence-cap, and conflict audit tables.

    If `evidence_cards` and/or `research_stance` are provided, those frames are
    used instead of querying current DB tables. This supports the in-memory
    production pipeline before the new run is committed.
    """

    initialize_database()
    if evidence_cards is None or research_stance is None:
        with connect() as conn:
            evidence = (
                conn.execute("SELECT * FROM evidence_cards").fetchdf()
                if evidence_cards is None
                else evidence_cards.copy()
            )
            stance = (
                conn.execute("SELECT * FROM research_stance").fetchdf()
                if research_stance is None
                else research_stance.copy()
            )
    else:
        evidence = evidence_cards.copy()
        stance = research_stance.copy()

    if evidence.empty:
        return (
            pd.DataFrame(columns=STANCE_COMPONENT_COLUMNS),
            pd.DataFrame(columns=STANCE_CAP_COLUMNS),
            pd.DataFrame(columns=STANCE_CONFLICT_COLUMNS),
        )

    evidence["source_date"] = pd.to_datetime(evidence["source_date"], errors="coerce")
    effective_as_of = _as_of_date(as_of_date, evidence, stance)
    output_run_id = _run_id_from_frames(run_id, stance, evidence)
    created_at = utc_now_naive()
    component_rows = []
    cap_rows = []
    conflict_rows = []
    stance_by_ticker = stance.set_index("ticker") if not stance.empty else pd.DataFrame()

    for ticker in CORE_TICKERS:
        ticker_evidence = evidence[evidence["ticker"] == ticker].copy()
        if ticker_evidence.empty:
            continue
        scored = _score_evidence_for_ticker(ticker, ticker_evidence, effective_as_of)
        positive_score = scored.loc[scored["direction"] == "positive", "weighted_score"].sum()
        negative_score = -scored.loc[
            scored["direction"] == "negative",
            "weighted_score",
        ].sum()
        caps, _ = _confidence_caps(ticker, scored, positive_score, negative_score)
        stance_value = (
            str(stance_by_ticker.loc[ticker, "stance"])
            if not stance_by_ticker.empty and ticker in stance_by_ticker.index
            else _apply_stance_caps(_stance_from_score(positive_score - negative_score), caps)
        )
        component_rows.extend(
            _component_rows(ticker, scored, effective_as_of, output_run_id, created_at)
        )
        cap_rows.extend(_cap_rows(ticker, caps, effective_as_of, output_run_id, created_at))
        conflict_rows.extend(
            _conflict_rows(
                ticker,
                scored,
                stance_value,
                effective_as_of,
                output_run_id,
                created_at,
            )
        )

    return (
        pd.DataFrame(component_rows, columns=STANCE_COMPONENT_COLUMNS),
        pd.DataFrame(cap_rows, columns=STANCE_CAP_COLUMNS),
        pd.DataFrame(conflict_rows, columns=STANCE_CONFLICT_COLUMNS),
    )


def store_stance_audit_tables(
    components: pd.DataFrame,
    caps: pd.DataFrame,
    conflicts: pd.DataFrame,
) -> tuple[int, int, int]:
    """Legacy single-table rebuild for tests and fixtures.

    Production code must use `store_research_outputs` so evidence, stance, and
    audit tables are committed atomically.
    """

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM stance_components")
        conn.execute("DELETE FROM stance_confidence_caps")
        conn.execute("DELETE FROM stance_conflicts")
        component_count = 0
        cap_count = 0
        conflict_count = 0
        if not components.empty:
            component_count = upsert_dataframe(
                conn,
                components,
                "stance_components",
                ["as_of_date", "ticker", "evidence_type", "direction"],
            )
        if not caps.empty:
            cap_count = upsert_dataframe(
                conn,
                caps,
                "stance_confidence_caps",
                ["as_of_date", "ticker", "cap_type"],
            )
        if not conflicts.empty:
            conflict_count = upsert_dataframe(
                conn,
                conflicts,
                "stance_conflicts",
                ["as_of_date", "ticker", "conflict_type"],
            )
    return component_count, cap_count, conflict_count


def store_research_outputs(
    evidence_cards: pd.DataFrame,
    research_stance: pd.DataFrame,
    components: pd.DataFrame,
    caps: pd.DataFrame,
    conflicts: pd.DataFrame,
) -> tuple[int, int, int, int, int]:
    """Store all current research outputs in one transaction after builds succeed."""

    initialize_database()
    if all(
        frame.empty
        for frame in (evidence_cards, research_stance, components, caps, conflicts)
    ):
        raise ValueError(
            "refusing to wipe current research outputs with all-empty inputs; "
            "build non-empty frames or add an explicit truncation function"
        )
    with connect() as conn:
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DELETE FROM evidence_cards")
            conn.execute("DELETE FROM research_stance")
            conn.execute("DELETE FROM stance_components")
            conn.execute("DELETE FROM stance_confidence_caps")
            conn.execute("DELETE FROM stance_conflicts")
            evidence_count = (
                upsert_dataframe(conn, evidence_cards, "evidence_cards", ["evidence_id"])
                if not evidence_cards.empty
                else 0
            )
            stance_count = (
                upsert_dataframe(conn, research_stance, "research_stance", ["stance_id"])
                if not research_stance.empty
                else 0
            )
            component_count = (
                upsert_dataframe(
                    conn,
                    components,
                    "stance_components",
                    ["as_of_date", "ticker", "evidence_type", "direction"],
                )
                if not components.empty
                else 0
            )
            cap_count = (
                upsert_dataframe(
                    conn,
                    caps,
                    "stance_confidence_caps",
                    ["as_of_date", "ticker", "cap_type"],
                )
                if not caps.empty
                else 0
            )
            conflict_count = (
                upsert_dataframe(
                    conn,
                    conflicts,
                    "stance_conflicts",
                    ["as_of_date", "ticker", "conflict_type"],
                )
                if not conflicts.empty
                else 0
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
    return evidence_count, stance_count, component_count, cap_count, conflict_count


def build_decision_memo(
    output_path: Path,
    run_id: Optional[str] = None,
    data_snapshot_hash: Optional[str] = None,
) -> Path:
    """Write the AI compute four-stock decision memo."""

    initialize_database()
    with connect() as conn:
        stance = conn.execute(
            """
            SELECT *
            FROM research_stance
            ORDER BY ticker
            """
        ).fetchdf()
        evidence = conn.execute("SELECT * FROM evidence_cards").fetchdf()

    lines = ["# AI Compute Four-Stock Decision Memo", ""]
    if stance.empty:
        lines.append("No research stance rows are available yet.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    as_of = pd.to_datetime(stance["as_of_date"]).max().date()
    run_id = run_id or _run_id_from_frames(None, stance)
    lines.append(f"as_of_date: {as_of}")
    if run_id:
        lines.append(f"run_id: {run_id}")
    if data_snapshot_hash:
        lines.append(f"data_snapshot_hash: {data_snapshot_hash}")
    lines.extend(["", "## Executive Summary", ""])
    lines.extend(_summary_table(stance))
    lines.extend(["", "## Cross-Stock Read", ""])
    lines.extend(_cross_stock_read(stance, evidence))

    evidence_by_id = evidence.set_index("evidence_id") if not evidence.empty else pd.DataFrame()
    for ticker in CORE_TICKERS:
        row = stance[stance["ticker"] == ticker]
        if row.empty:
            continue
        lines.extend(_ticker_section(row.iloc[0], evidence_by_id))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def build_stance_audit_report(output_path: Path) -> Path:
    """Write a stance audit report with scoring components, caps, and conflicts."""

    initialize_database()
    with connect() as conn:
        stance = conn.execute("SELECT * FROM research_stance ORDER BY ticker").fetchdf()
        evidence = conn.execute("SELECT * FROM evidence_cards").fetchdf()
        components = conn.execute(
            "SELECT * FROM stance_components ORDER BY ticker, evidence_type, direction"
        ).fetchdf()
        caps = conn.execute(
            "SELECT * FROM stance_confidence_caps ORDER BY ticker, cap_type"
        ).fetchdf()
        conflicts = conn.execute(
            "SELECT * FROM stance_conflicts ORDER BY ticker, severity, conflict_type"
        ).fetchdf()

    lines = ["# Stance Audit Report", ""]
    if stance.empty:
        lines.append("No research stance rows are available yet.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    evidence_by_id = evidence.set_index("evidence_id") if not evidence.empty else pd.DataFrame()
    as_of = pd.to_datetime(stance["as_of_date"]).max().date()
    lines.extend([f"as_of_date: {as_of}", ""])
    lines.extend(
        [
            "This report audits how `research_stance` was produced. It is designed to "
            "find overconfident outputs, missing evidence categories, and conflicts "
            "between operating evidence and factor residual evidence.",
            "",
        ]
    )

    for ticker in CORE_TICKERS:
        row = stance[stance["ticker"] == ticker]
        if row.empty:
            continue
        ticker_components = components[components["ticker"] == ticker]
        ticker_caps = caps[caps["ticker"] == ticker]
        ticker_conflicts = conflicts[conflicts["ticker"] == ticker]
        ticker_evidence = evidence[evidence["ticker"] == ticker]
        lines.extend(
            _audit_ticker_section(
                row.iloc[0],
                ticker_components,
                ticker_caps,
                ticker_conflicts,
                ticker_evidence,
                evidence_by_id,
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _event_evidence(
    event_reviews: pd.DataFrame,
    event_returns: pd.DataFrame,
    as_of_date,
    created_at,
) -> list[dict]:
    if event_reviews.empty:
        return []

    factor = _event_return_lookup(event_returns, prefer_factor=True)
    fallback = _event_return_lookup(event_returns, prefer_factor=False)
    rows = []
    for _, review in event_reviews.iterrows():
        ticker = review["affected_ticker"]
        source_id = f"{review['event_id']}:{ticker}"
        return_row = factor.get(source_id) or fallback.get(source_id)
        metric_value = return_row.get("abnormal_return") if return_row else None
        materiality = abs(float(metric_value)) if pd.notna(metric_value) else 0.0
        direction = _direction_from_signed(metric_value, threshold=0.03)
        strength = _strength_from_materiality(materiality, [0.03, 0.05, 0.10])
        confidence = _bounded_confidence(
            float(review.get("confidence") or 0.55)
            * (1.0 if review.get("data_quality_flag") == "complete" else 0.75)
        )
        model_label = (
            "factor-model"
            if return_row and return_row.get("benchmark_type") == "factor_model"
            else "benchmark"
        )
        summary = (
            f"{ticker} event reaction evidence for {review['event_id']}: "
            f"{review.get('interpretation') or 'no interpretation available'}"
        )
        rows.append(
            _evidence_row(
                as_of_date=as_of_date,
                ticker=ticker,
                evidence_type="event_reaction",
                source_table="event_reviews",
                source_id=source_id,
                source_date=review["reaction_date"],
                available_date=review["reaction_date"],
                direction=direction,
                strength=strength,
                confidence=confidence,
                materiality=materiality,
                summary=summary,
                metric_name=f"{model_label}_abnormal_0_p5",
                metric_value=metric_value,
                comparison_value=return_row.get("benchmark_return") if return_row else None,
                interpretation=review.get("interpretation"),
                thesis_tag=_extract_thesis_tag(review.get("thesis_impact")),
                risk_tag=None,
                data_quality_flag=review.get("data_quality_flag"),
                created_at=created_at,
            )
        )
    return rows


def _segment_evidence(segment_features: pd.DataFrame, as_of_date, created_at) -> list[dict]:
    if segment_features.empty:
        return []
    rows = []
    latest = (
        segment_features.sort_values("date")
        .groupby(["ticker", "feature_name"], dropna=False)
        .tail(1)
    )
    for _, feature in latest.iterrows():
        score = feature.get("feature_score")
        direction = _direction_from_score(score)
        if direction == "neutral":
            continue
        materiality = _score_materiality(score)
        source_id = str(
            feature.get("source_kpi_ids")
            or f"{feature['ticker']}:{feature['feature_name']}"
        )
        rows.append(
            _evidence_row(
                as_of_date=as_of_date,
                ticker=feature["ticker"],
                evidence_type="segment_momentum",
                source_table="segment_features",
                source_id=source_id,
                source_date=feature["date"],
                available_date=feature["date"],
                direction=direction,
                strength=_strength_from_materiality(materiality, [0.20, 0.40, 0.70]),
                confidence=float(feature.get("confidence") or 0.6),
                materiality=materiality,
                summary=_segment_summary(feature, direction),
                metric_name=feature["feature_name"],
                metric_value=feature.get("feature_value"),
                comparison_value=score,
                interpretation=f"Feature score {score:.1f} is {direction}.",
                thesis_tag=_thesis_tag_for_feature(str(feature["feature_name"])),
                risk_tag=_risk_tag_for_feature(str(feature["feature_name"]), direction),
                data_quality_flag="complete",
                created_at=created_at,
            )
        )
    return rows


def _cash_flow_evidence(cash_flow_features: pd.DataFrame, as_of_date, created_at) -> list[dict]:
    if cash_flow_features.empty:
        return []
    rows = []
    latest = (
        cash_flow_features.sort_values("date")
        .groupby(["ticker", "feature_name"], dropna=False)
        .tail(1)
    )
    for _, feature in latest.iterrows():
        direction = str(feature.get("direction") or "neutral")
        score_direction = _direction_from_score(feature.get("feature_score"))
        if direction == "neutral":
            direction = score_direction
        if direction == "neutral":
            continue
        materiality = _score_materiality(feature.get("feature_score"))
        rows.append(
            _evidence_row(
                as_of_date=as_of_date,
                ticker=feature["ticker"],
                evidence_type="cash_flow_quality",
                source_table="cash_flow_features",
                source_id=str(feature.get("source_fundamental_ids") or ""),
                source_date=feature["date"],
                available_date=feature["date"],
                direction=direction,
                strength=_strength_from_materiality(materiality, [0.20, 0.40, 0.70]),
                confidence=float(feature.get("confidence") or 0.6),
                materiality=materiality,
                summary=_cash_flow_summary(feature, direction),
                metric_name=feature["feature_name"],
                metric_value=feature.get("feature_value"),
                comparison_value=feature.get("feature_score"),
                interpretation=f"Cash-flow feature score {feature.get('feature_score'):.1f}.",
                thesis_tag="cash_flow_quality",
                risk_tag="capex_pressure" if direction == "negative" else None,
                data_quality_flag=feature.get("data_quality_flag"),
                created_at=created_at,
            )
        )
    return rows


def _valuation_evidence(valuation_features: pd.DataFrame, as_of_date, created_at) -> list[dict]:
    if valuation_features.empty:
        return []
    rows = []
    latest = (
        valuation_features.sort_values("date")
        .groupby(["ticker", "feature_name"], dropna=False)
        .tail(1)
    )
    for _, feature in latest.iterrows():
        direction = str(feature.get("direction") or "neutral")
        if direction == "neutral":
            continue
        score = feature.get("feature_score")
        materiality = _score_materiality(score)
        rows.append(
            _evidence_row(
                as_of_date=as_of_date,
                ticker=feature["ticker"],
                evidence_type="valuation",
                source_table="valuation_features",
                source_id=str(feature.get("source_metric_ids") or ""),
                source_date=feature["date"],
                available_date=feature["date"],
                direction=direction,
                strength=_strength_from_materiality(materiality, [0.20, 0.40, 0.70]),
                confidence=float(feature.get("confidence") or 0.6),
                materiality=materiality,
                summary=_valuation_summary(feature, direction),
                metric_name=feature["feature_name"],
                metric_value=feature.get("feature_value"),
                comparison_value=score,
                interpretation=f"Valuation feature score {score:.1f}.",
                thesis_tag="valuation_discipline",
                risk_tag="valuation_risk" if direction == "negative" else None,
                data_quality_flag=feature.get("data_quality_flag"),
                created_at=created_at,
            )
        )
    return rows


def _factor_evidence(factor_residuals: pd.DataFrame, as_of_date, created_at) -> list[dict]:
    if factor_residuals.empty:
        return []
    rows = []
    latest = factor_residuals.sort_values("date").groupby("ticker", dropna=False).tail(1)
    for _, row in latest.iterrows():
        residual_20d = row.get("residual_return_20d")
        residual_60d = row.get("residual_return_60d")
        direction = _factor_direction(residual_20d, residual_60d)
        materiality = max(
            abs(float(residual_20d)) if pd.notna(residual_20d) else 0.0,
            abs(float(residual_60d)) if pd.notna(residual_60d) else 0.0,
        )
        confidence = _factor_confidence(row)
        rows.append(
            _evidence_row(
                as_of_date=as_of_date,
                ticker=row["ticker"],
                evidence_type="factor_residual",
                source_table="factor_residuals",
                source_id=f"{row['ticker']}:{row['date']}:{row['model_name']}:{row['lookback_window']}",
                source_date=row["date"],
                available_date=row["date"],
                direction=direction,
                strength=_strength_from_materiality(materiality, [0.03, 0.08, 0.20]),
                confidence=confidence,
                materiality=materiality,
                summary=_factor_summary(row, direction),
                metric_name="residual_return_60d",
                metric_value=residual_60d,
                comparison_value=row.get("r2"),
                interpretation=(
                    f"20d residual {_fmt_pct(residual_20d)} and 60d residual "
                    f"{_fmt_pct(residual_60d)} after QQQ/SOXX/10Y attribution."
                ),
                thesis_tag="factor_residual",
                risk_tag="fx_model_gap" if row["ticker"] == "TSM" else None,
                data_quality_flag=row.get("data_quality_flag"),
                created_at=created_at,
            )
        )
    return rows


def _residual_concentration_evidence(
    residual_diagnostics: pd.DataFrame,
    as_of_date,
    created_at,
) -> list[dict]:
    if residual_diagnostics.empty:
        return []
    rows = []
    diagnostics = residual_diagnostics.copy()
    diagnostics["as_of_date"] = pd.to_datetime(diagnostics["as_of_date"])
    latest = (
        diagnostics[diagnostics["window_days"] == 60]
        .sort_values("as_of_date")
        .groupby("ticker", dropna=False)
        .tail(1)
    )
    for _, row in latest.iterrows():
        concentration = row.get("top_3_days_contribution_pct")
        residual_return = row.get("residual_return")
        if (
            pd.isna(concentration)
            or pd.isna(residual_return)
            or float(concentration) <= 0.60
            or float(residual_return) <= 0.0
        ):
            continue
        rows.append(
            _evidence_row(
                as_of_date=as_of_date,
                ticker=row["ticker"],
                evidence_type="risk",
                source_table="residual_diagnostics",
                source_id=(
                    f"{row['ticker']}:{row['model_name']}:{int(row['window_days'])}"
                ),
                source_date=row["as_of_date"],
                available_date=row["as_of_date"],
                direction="negative",
                strength=_strength_from_materiality(float(concentration), [0.45, 0.60, 0.75]),
                confidence=0.80,
                materiality=float(concentration),
                summary=(
                    f"{row['ticker']} positive residual is concentrated: top 3 days "
                    f"contribute {float(concentration) * 100:.1f}% of 60d absolute "
                    "residual movement."
                ),
                metric_name="top_3_days_contribution_pct",
                metric_value=concentration,
                comparison_value=0.60,
                interpretation="Factor-led evidence needs event attribution review.",
                thesis_tag="factor_quality",
                risk_tag="residual_concentration",
                data_quality_flag=row.get("data_quality_flag"),
                created_at=created_at,
            )
        )
    return rows


def _stance_row(
    ticker: str,
    evidence: pd.DataFrame,
    as_of_date,
    run_id: str,
    created_at,
) -> dict:
    if evidence.empty:
        return _empty_stance_row(ticker, as_of_date, run_id, created_at)

    scored = _score_evidence_for_ticker(ticker, evidence, as_of_date)
    positive_score = scored.loc[scored["direction"] == "positive", "weighted_score"].sum()
    negative_score = -scored.loc[scored["direction"] == "negative", "weighted_score"].sum()
    net_score = positive_score - negative_score
    stance = _stance_from_score(net_score)
    caps, caveats = _confidence_caps(ticker, scored, positive_score, negative_score)
    stance = _apply_stance_caps(stance, caps)
    stance_modifier = _stance_modifier(ticker, stance, scored, caps)
    confidence = _stance_confidence(scored, caps)

    positive_ids = _top_evidence_ids(scored, "positive")
    negative_ids = _top_evidence_ids(scored, "negative")
    mixed_ids = _top_evidence_ids(scored, "mixed") + _top_evidence_ids(scored, "neutral")
    risk_flags = _risk_flags(scored)
    thesis_summary = _thesis_summary(ticker, stance, net_score, scored)

    return {
        "stance_id": _stable_id("stance", ticker, as_of_date),
        "run_id": run_id,
        "as_of_date": as_of_date,
        "ticker": ticker,
        "stance": stance,
        "stance_modifier": stance_modifier,
        "confidence": round(confidence, 3),
        "thesis_summary": thesis_summary,
        "positive_evidence_ids": ",".join(positive_ids),
        "negative_evidence_ids": ",".join(negative_ids),
        "mixed_evidence_ids": ",".join(mixed_ids[:5]),
        "risk_flags": "; ".join(risk_flags),
        "falsifiers": "; ".join(FALSIFIERS[ticker]),
        "next_catalysts": "; ".join(NEXT_CATALYSTS[ticker]),
        "data_quality_caveats": "; ".join(caveats),
        "created_at": created_at,
        "ingested_at": created_at,
    }


def _score_evidence_for_ticker(ticker: str, evidence: pd.DataFrame, as_of_date) -> pd.DataFrame:
    scored = evidence.copy()
    type_counts = scored["evidence_type"].value_counts().to_dict()
    weights = EVIDENCE_TYPE_WEIGHTS.get(ticker, {})
    scored["strength_value"] = scored["strength"].map(STRENGTH_VALUES).fillna(0.25)
    scored["sign"] = scored["direction"].map({"positive": 1.0, "negative": -1.0}).fillna(0.0)
    scored["type_weight"] = scored["evidence_type"].map(weights).fillna(0.05)
    scored["time_decay"] = scored["source_date"].apply(lambda value: _time_decay(value, as_of_date))
    scored["weighted_score"] = (
        scored["sign"]
        * scored["strength_value"]
        * scored["confidence"].fillna(0.5)
        * scored["type_weight"]
        / scored["evidence_type"].map(type_counts).fillna(1.0)
        * scored["time_decay"]
        * 100.0
    )
    scored["abs_weighted_score"] = scored["weighted_score"].abs()
    return scored


def _confidence_caps(
    ticker: str,
    evidence: pd.DataFrame,
    positive_score: float,
    negative_score: float,
) -> tuple[list[str], list[str]]:
    caps = []
    caveats = []
    evidence_types = set(evidence["evidence_type"])
    if len(evidence) < 4 or len(evidence_types) < 3:
        caps.append("limited_evidence")
        caveats.append("limited evidence coverage caps confidence")
    if "segment_momentum" not in evidence_types:
        caps.append("missing_segment_evidence")
        caveats.append("missing segment evidence prevents strong constructive stance")
    if "cash_flow_quality" not in evidence_types:
        caps.append("missing_cash_flow_evidence")
        caveats.append("missing cash-flow evidence caps confidence")
    if "factor_residual" not in evidence_types:
        caps.append("missing_factor_evidence")
        caveats.append("missing factor residual evidence caps confidence")
    if "valuation" not in evidence_types:
        caps.append("missing_valuation_evidence")
        caveats.append("missing valuation evidence leaves price discipline unresolved")
    data_issues = evidence[
        evidence["data_quality_flag"].fillna("complete").isin(
            ["incomplete", "data_issue", "insufficient_observations"]
        )
    ]
    if len(data_issues) >= 2:
        caps.append("data_quality_issues")
        caveats.append("multiple data-quality issues cap confidence")
    if positive_score >= 15 and negative_score >= 15:
        caps.append("conflicting_evidence")
        caveats.append("positive and negative evidence are both material")
    negative_valuation = _material_evidence(evidence, "valuation", "negative")
    if not negative_valuation.empty and positive_score >= 20:
        caps.append("negative_valuation_evidence")
        caveats.append("negative valuation evidence caps high-confidence positive stance")
    non_factor_positive = evidence[
        (evidence["direction"] == "positive")
        & (evidence["evidence_type"] != "factor_residual")
    ]
    positive_factor_score = _positive_factor_score(evidence)
    positive_non_factor_score = float(non_factor_positive["weighted_score"].sum())
    positive_factor_share = _positive_factor_share(evidence, positive_score)
    non_factor_positive_types = _non_factor_positive_type_count(evidence)
    non_factor_positive_count = int(len(non_factor_positive))
    factor_led_insufficient = (
        positive_factor_score >= positive_non_factor_score
        and positive_factor_score > 0
        and non_factor_positive_count < MIN_NON_FACTOR_POSITIVE_COUNT_FOR_FACTOR_LED
    )
    if factor_led_insufficient:
        caps.append("factor_led_insufficient_confirmation")
        caveats.append(
            "factor-led stance requires at least three non-factor positive evidence rows"
        )
    elif positive_factor_score >= 15 and non_factor_positive.empty:
        caps.append("missing_non_factor_positive_evidence")
        caveats.append("strong constructive stance requires positive non-factor evidence")
    if (
        positive_score >= 25
        and non_factor_positive_types < MIN_NON_FACTOR_POSITIVE_TYPES_FOR_STRONG
        and not factor_led_insufficient
    ):
        caps.append("insufficient_non_factor_positive_confirmation")
        caveats.append(
            "strong constructive stance requires at least two non-factor positive evidence types"
        )
    if (
        positive_factor_share >= FACTOR_DOMINANCE_THRESHOLD
        and non_factor_positive_types < MIN_NON_FACTOR_POSITIVE_TYPES_FOR_STRONG
        and not factor_led_insufficient
    ):
        caps.append("factor_dominated_positive_evidence")
        caveats.append("factor-led positive evidence needs non-factor confirmation")
    if (evidence["risk_tag"] == "residual_concentration").any():
        caps.append("residual_concentration")
        caveats.append("positive residual evidence is concentrated in a few trading days")
    if ticker == "TSM":
        caps.append("tsm_fx_model_gap")
        caveats.append("TSM factor evidence is capped until USD/TWD is added to the model")
    return caps, caveats


def _stance_confidence(evidence: pd.DataFrame, caps: list[str]) -> float:
    avg_confidence = float(evidence["confidence"].dropna().mean()) if not evidence.empty else 0.35
    coverage_score = min(1.0, evidence["evidence_type"].nunique() / 5.0)
    issue_rate = float(
        evidence["data_quality_flag"].fillna("complete").isin(["incomplete", "data_issue"]).mean()
    )
    confidence = avg_confidence * 0.70 + coverage_score * 0.25 + (1.0 - issue_rate) * 0.05
    for cap in caps:
        confidence = min(confidence, CONFIDENCE_CAP_VALUES.get(cap, confidence))
    return _bounded_confidence(confidence)


def _stance_from_score(net_score: float) -> str:
    if net_score >= 25:
        return "strong_constructive"
    if net_score >= 10:
        return "constructive"
    if net_score > -10:
        return "neutral"
    if net_score > -25:
        return "cautious"
    return "high_risk"


def _apply_stance_caps(stance: str, caps: list[str]) -> str:
    if (
        "factor_led_insufficient_confirmation" in caps
        and stance in {"strong_constructive", "constructive"}
    ):
        stance = "neutral"
    if "missing_segment_evidence" in caps and stance == "strong_constructive":
        stance = "constructive"
    if "missing_non_factor_positive_evidence" in caps and stance == "strong_constructive":
        stance = "constructive"
    if (
        "insufficient_non_factor_positive_confirmation" in caps
        and stance == "strong_constructive"
    ):
        stance = "constructive"
    if "factor_dominated_positive_evidence" in caps and stance == "strong_constructive":
        stance = "constructive"
    if "negative_valuation_evidence" in caps and stance == "strong_constructive":
        stance = "constructive"
    if "residual_concentration" in caps and stance == "strong_constructive":
        stance = "constructive"
    if "limited_evidence" in caps and stance in {"strong_constructive", "constructive"}:
        stance = "neutral"
    if "conflicting_evidence" in caps and stance == "strong_constructive":
        stance = "constructive"
    return stance


def _stance_modifier(
    ticker: str,
    stance: str,
    scored: pd.DataFrame,
    caps: list[str],
) -> str:
    positive_stance = stance in {"constructive", "strong_constructive"}
    negative_factor = _material_evidence(scored, "factor_residual", "negative")
    positive_valuation = _material_evidence(scored, "valuation", "positive")
    negative_valuation = _material_evidence(scored, "valuation", "negative")
    positive_factor_share = _positive_factor_share(
        scored,
        scored.loc[scored["direction"] == "positive", "weighted_score"].sum(),
    )
    has_positive_cash = not _material_evidence(scored, "cash_flow_quality", "positive").empty
    has_negative_cash = not _material_evidence(scored, "cash_flow_quality", "negative").empty

    modifiers = []
    if positive_stance and not negative_valuation.empty:
        modifiers.append("valuation_capped")
    if positive_stance and positive_factor_share >= FACTOR_LED_MODIFIER_THRESHOLD:
        modifiers.append("factor_led")
    if "residual_concentration" in caps:
        modifiers.append("residual_concentrated")
    if ticker == "TSM" and (
        "tsm_fx_model_gap" in caps
        or "missing_cash_flow_evidence" in caps
        or "data_quality_issues" in caps
    ):
        modifiers.append("data_quality_capped")
    if positive_stance and not negative_factor.empty:
        modifiers.append("factor_conflicted")
    if not positive_stance and not positive_valuation.empty and negative_valuation.empty:
        modifiers.append("valuation_supported")
    if "missing_valuation_evidence" in caps:
        modifiers.append("valuation_unknown")
    if has_positive_cash and has_negative_cash:
        modifiers.append("mixed_cash_flow")
    if "conflicting_evidence" in caps and not modifiers:
        modifiers.append("mixed")
    if caps and not modifiers:
        modifiers.append("capped")
    return "+".join(dict.fromkeys(modifiers)) if modifiers else "clean"


def _empty_stance_row(ticker: str, as_of_date, run_id: str, created_at) -> dict:
    return {
        "stance_id": _stable_id("stance", ticker, as_of_date),
        "run_id": run_id,
        "as_of_date": as_of_date,
        "ticker": ticker,
        "stance": "neutral",
        "stance_modifier": "insufficient_evidence",
        "confidence": 0.25,
        "thesis_summary": f"{STATIC_THESIS[ticker]} Evidence coverage is not yet sufficient.",
        "positive_evidence_ids": "",
        "negative_evidence_ids": "",
        "mixed_evidence_ids": "",
        "risk_flags": "insufficient evidence",
        "falsifiers": "; ".join(FALSIFIERS[ticker]),
        "next_catalysts": "; ".join(NEXT_CATALYSTS[ticker]),
        "data_quality_caveats": "no evidence cards available",
        "created_at": created_at,
        "ingested_at": created_at,
    }


def _top_evidence_ids(scored: pd.DataFrame, direction: str, limit: int = 5) -> list[str]:
    rows = scored[scored["direction"] == direction].sort_values(
        "abs_weighted_score",
        ascending=False,
    )
    return rows["evidence_id"].head(limit).astype(str).tolist()


def _risk_flags(scored: pd.DataFrame) -> list[str]:
    flags = []
    negative = scored[scored["direction"] == "negative"].sort_values(
        "abs_weighted_score",
        ascending=False,
    )
    for _, row in negative.head(4).iterrows():
        risk_tag = _clean_text(row.get("risk_tag"))
        summary = _clean_text(row.get("summary"))
        metric_name = _clean_text(row.get("metric_name"))
        flags.append(risk_tag or summary or metric_name)
    if not flags:
        flags.append("no major negative evidence from current evidence set")
    return list(dict.fromkeys(flags))


def _component_rows(
    ticker: str,
    scored: pd.DataFrame,
    as_of_date,
    run_id: str,
    created_at,
) -> list[dict]:
    rows = []
    grouped = scored.groupby(["evidence_type", "direction"], dropna=False)
    for (evidence_type, direction), group in grouped:
        top_ids = (
            group.sort_values("abs_weighted_score", ascending=False)["evidence_id"]
            .head(5)
            .astype(str)
            .tolist()
        )
        rows.append(
            {
                "run_id": run_id,
                "as_of_date": as_of_date,
                "ticker": ticker,
                "evidence_type": evidence_type,
                "direction": direction,
                "weighted_score": float(group["weighted_score"].sum()),
                "raw_strength": float(group["strength_value"].mean()),
                "avg_confidence": float(group["confidence"].fillna(0.5).mean()),
                "evidence_count": int(len(group)),
                "top_evidence_ids": ",".join(top_ids),
                "created_at": created_at,
                "ingested_at": created_at,
            }
        )
    return rows


def _cap_rows(ticker: str, caps: list[str], as_of_date, run_id: str, created_at) -> list[dict]:
    rows = []
    for cap in caps:
        rows.append(
            {
                "run_id": run_id,
                "as_of_date": as_of_date,
                "ticker": ticker,
                "cap_type": cap,
                "cap_value": CONFIDENCE_CAP_VALUES.get(cap),
                "reason": CONFIDENCE_CAP_REASONS.get(cap, cap),
                "applied": True,
                "created_at": created_at,
                "ingested_at": created_at,
            }
        )
    return rows


def _conflict_rows(
    ticker: str,
    scored: pd.DataFrame,
    stance: str,
    as_of_date,
    run_id: str,
    created_at,
) -> list[dict]:
    rows = []
    positive_segment = _material_evidence(scored, "segment_momentum", "positive")
    negative_segment = _material_evidence(scored, "segment_momentum", "negative")
    positive_factor = _material_evidence(scored, "factor_residual", "positive")
    negative_factor = _material_evidence(scored, "factor_residual", "negative")
    positive_cash = _material_evidence(scored, "cash_flow_quality", "positive")
    negative_cash = _material_evidence(scored, "cash_flow_quality", "negative")
    positive_valuation = _material_evidence(scored, "valuation", "positive")
    negative_valuation = _material_evidence(scored, "valuation", "negative")
    positive_factor_score = _positive_factor_score(scored)
    positive_non_factor_score = float(
        scored[
            (scored["direction"] == "positive")
            & (scored["evidence_type"] != "factor_residual")
        ]["weighted_score"].sum()
    )

    if stance in {"constructive", "strong_constructive"} and not negative_factor.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_stance_negative_factor_residual",
                _top_ids(scored[scored["direction"] == "positive"]),
                _top_ids(negative_factor),
                "high" if _max_strength(negative_factor) >= 0.75 else "medium",
                (
                    f"{ticker} has a positive stance, but factor residual evidence is "
                    "negative. Treat the stance as conflicted until residual pressure "
                    "or operating evidence resolves."
                ),
                created_at,
            )
        )

    if not positive_factor.empty and positive_factor_score >= positive_non_factor_score:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "factor_dominated_positive_stance",
                _top_ids(positive_factor),
                _top_ids(scored[scored["direction"] == "negative"]),
                "medium",
                (
                    f"{ticker} positive stance is materially supported by factor "
                    "residual evidence; audit non-factor confirmation before raising "
                    "confidence."
                ),
                created_at,
            )
        )

    if stance in {"constructive", "strong_constructive"} and not negative_valuation.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_stance_negative_valuation",
                _top_ids(scored[scored["direction"] == "positive"]),
                _top_ids(negative_valuation),
                "high" if _max_strength(negative_valuation) >= 0.75 else "medium",
                (
                    f"{ticker} has a positive stance, but valuation evidence is "
                    "negative. Treat upside as valuation-capped until price or "
                    "fundamentals improve."
                ),
                created_at,
            )
        )

    if not positive_factor.empty and not negative_valuation.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_factor_negative_valuation",
                _top_ids(positive_factor),
                _top_ids(negative_valuation),
                "medium",
                (
                    f"{ticker} has positive factor residual evidence but negative "
                    "valuation evidence."
                ),
                created_at,
            )
        )

    if not positive_valuation.empty and not negative_factor.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_valuation_negative_factor",
                _top_ids(positive_valuation),
                _top_ids(negative_factor),
                "medium",
                (
                    f"{ticker} has positive valuation evidence but negative factor "
                    "residual evidence."
                ),
                created_at,
            )
        )

    if not positive_segment.empty and not negative_factor.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_segment_negative_factor",
                _top_ids(positive_segment),
                _top_ids(negative_factor),
                "high" if _max_strength(negative_factor) >= 0.75 else "medium",
                (
                    f"{ticker} has positive company-driver evidence but negative "
                    "factor residual evidence."
                ),
                created_at,
            )
        )

    if not positive_factor.empty and negative_segment.empty and positive_segment.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_residual_missing_segment_support",
                _top_ids(positive_factor),
                "",
                "medium",
                (
                    f"{ticker} has positive factor residual evidence without positive "
                    "segment support."
                ),
                created_at,
            )
        )

    if not positive_factor.empty and not negative_segment.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_factor_negative_segment",
                _top_ids(positive_factor),
                _top_ids(negative_segment),
                "high" if _max_strength(negative_segment) >= 0.75 else "medium",
                (
                    f"{ticker} has positive residual evidence but negative segment "
                    "driver evidence."
                ),
                created_at,
            )
        )

    if not positive_segment.empty and not negative_cash.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_segment_negative_cash_flow",
                _top_ids(positive_segment),
                _top_ids(negative_cash),
                "medium",
                (
                    f"{ticker} has positive operating-driver evidence but negative "
                    "cash-flow evidence."
                ),
                created_at,
            )
        )

    if not positive_cash.empty and not negative_segment.empty:
        rows.append(
            _conflict_row(
                as_of_date,
                run_id,
                ticker,
                "positive_cash_flow_negative_segment",
                _top_ids(positive_cash),
                _top_ids(negative_segment),
                "medium",
                (
                    f"{ticker} has positive cash-flow evidence but negative segment "
                    "driver evidence."
                ),
                created_at,
            )
        )
    return rows


def _conflict_row(
    as_of_date,
    run_id: str,
    ticker: str,
    conflict_type: str,
    positive_ids: str,
    negative_ids: str,
    severity: str,
    summary: str,
    created_at,
) -> dict:
    return {
        "run_id": run_id,
        "as_of_date": as_of_date,
        "ticker": ticker,
        "conflict_type": conflict_type,
        "positive_evidence_ids": positive_ids,
        "negative_evidence_ids": negative_ids,
        "severity": severity,
        "summary": summary,
        "created_at": created_at,
        "ingested_at": created_at,
    }


def _material_evidence(scored: pd.DataFrame, evidence_type: str, direction: str) -> pd.DataFrame:
    return scored[
        (scored["evidence_type"] == evidence_type)
        & (scored["direction"] == direction)
        & (scored["strength_value"] >= 0.50)
    ]


def _top_ids(frame: pd.DataFrame, limit: int = 5) -> str:
    if frame.empty:
        return ""
    return ",".join(
        frame.sort_values("abs_weighted_score", ascending=False)["evidence_id"]
        .head(limit)
        .astype(str)
        .tolist()
    )


def _max_strength(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    return float(frame["strength_value"].max())


def _positive_factor_score(scored: pd.DataFrame) -> float:
    rows = scored[
        (scored["direction"] == "positive")
        & (scored["evidence_type"] == "factor_residual")
    ]
    return float(rows["weighted_score"].sum()) if not rows.empty else 0.0


def _positive_factor_share(scored: pd.DataFrame, positive_score: float) -> float:
    if positive_score <= 0:
        return 0.0
    return max(0.0, _positive_factor_score(scored) / float(positive_score))


def _non_factor_positive_type_count(scored: pd.DataFrame) -> int:
    rows = scored[
        (scored["direction"] == "positive")
        & (scored["evidence_type"] != "factor_residual")
    ]
    return int(rows["evidence_type"].nunique())


def _thesis_summary(ticker: str, stance: str, net_score: float, scored: pd.DataFrame) -> str:
    top = scored.sort_values("abs_weighted_score", ascending=False).head(2)
    top_bits = "; ".join(top["summary"].astype(str).tolist())
    return (
        f"{STATIC_THESIS[ticker]} Current stance is {stance} with net evidence score "
        f"{net_score:.1f}. {top_bits}"
    )


def _summary_table(stance: pd.DataFrame) -> list[str]:
    lines = [
        "| Ticker | Stance | Modifier | Confidence | Main caveat | One-line thesis |",
        "|---|---|---|---:|---|---|",
    ]
    for _, row in stance.iterrows():
        lines.append(
            f"| {row['ticker']} | {row['stance']} | {row.get('stance_modifier', 'n/a')} | "
            f"{float(row['confidence']):.2f} | {_main_caveat(row)} | "
            f"{_short(row['thesis_summary'], 120)} |"
        )
    return lines


def _cross_stock_read(stance: pd.DataFrame, evidence: pd.DataFrame) -> list[str]:
    constructive = stance[stance["stance"].isin(["constructive", "strong_constructive"])]
    cautious = stance[stance["stance"].isin(["cautious", "high_risk"])]
    factor = (
        evidence[evidence["evidence_type"] == "factor_residual"]
        if not evidence.empty
        else evidence
    )
    positive_factor = (
        factor[factor["direction"] == "positive"]["ticker"].tolist()
        if not factor.empty
        else []
    )
    negative_factor = (
        factor[factor["direction"] == "negative"]["ticker"].tolist()
        if not factor.empty
        else []
    )
    return [
        "- Constructive evidence currently clusters around: "
        f"{_list_or_none(constructive['ticker'].tolist())}.",
        "- Cautious/high-risk evidence currently clusters around: "
        f"{_list_or_none(cautious['ticker'].tolist())}.",
        f"- Positive factor residual leadership: {_list_or_none(positive_factor)}.",
        f"- Negative factor residual pressure: {_list_or_none(negative_factor)}.",
        "- Stance is research output only; it is not an automatic buy/sell instruction.",
    ]


def _ticker_section(row: pd.Series, evidence_by_id: pd.DataFrame) -> list[str]:
    ticker = row["ticker"]
    lines = [
        "",
        f"## {ticker}",
        "",
        "### Stance",
        "",
        (
            f"{row['stance']} / {row.get('stance_modifier', 'n/a')} "
            f"(confidence {float(row['confidence']):.2f})"
        ),
        "",
    ]
    lines.extend(["### Thesis", "", str(row["thesis_summary"]), ""])
    for title, column in (
        ("Positive Evidence", "positive_evidence_ids"),
        ("Negative / Mixed Evidence", "negative_evidence_ids"),
        ("Mixed Evidence", "mixed_evidence_ids"),
    ):
        lines.extend([f"### {title}", ""])
        lines.extend(_evidence_bullets(row.get(column), evidence_by_id))
        lines.append("")
    lines.extend(["### Risk Flags", "", _value_or_none(row.get("risk_flags")), ""])
    lines.extend(["### Falsifiers", ""])
    lines.extend([f"- {item}" for item in str(row["falsifiers"]).split("; ") if item])
    lines.extend(["", "### Next Catalysts", ""])
    lines.extend([f"- {item}" for item in str(row["next_catalysts"]).split("; ") if item])
    lines.extend(
        ["", "### Data Quality Caveats", "", _value_or_none(row.get("data_quality_caveats")), ""]
    )
    return lines


def _audit_ticker_section(
    row: pd.Series,
    components: pd.DataFrame,
    caps: pd.DataFrame,
    conflicts: pd.DataFrame,
    ticker_evidence: pd.DataFrame,
    evidence_by_id: pd.DataFrame,
) -> list[str]:
    ticker = row["ticker"]
    net_score = float(components["weighted_score"].sum()) if not components.empty else 0.0
    lines = [
        f"## {ticker}",
        "",
        f"- Stance: {row['stance']}",
        f"- Modifier: {row.get('stance_modifier', 'n/a')}",
        f"- Confidence: {float(row['confidence']):.2f}",
        f"- Net weighted score: {net_score:.1f}",
        "",
        "### Evidence Count By Type",
        "",
    ]
    lines.extend(_audit_count_table(ticker_evidence))
    lines.extend(["", "### Score Contribution By Type", ""])
    lines.extend(_audit_component_table(components))
    lines.extend(["", "### Confidence Caps Applied", ""])
    lines.extend(_audit_cap_table(caps))
    lines.extend(["", "### Conflicts", ""])
    lines.extend(_audit_conflict_bullets(conflicts))
    lines.extend(["", "### Top Positive Evidence", ""])
    lines.extend(_evidence_bullets(row.get("positive_evidence_ids"), evidence_by_id))
    lines.extend(["", "### Top Negative Evidence", ""])
    lines.extend(_evidence_bullets(row.get("negative_evidence_ids"), evidence_by_id))
    lines.extend(["", "### Final Stance Explanation", "", str(row["thesis_summary"]), ""])
    return lines


def _audit_count_table(ticker_evidence: pd.DataFrame) -> list[str]:
    lines = ["| Evidence type | Direction | Count |", "|---|---|---:|"]
    if ticker_evidence.empty:
        lines.append("| none | none | 0 |")
        return lines
    counts = (
        ticker_evidence.groupby(["evidence_type", "direction"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["evidence_type", "direction"])
    )
    for _, row in counts.iterrows():
        lines.append(f"| {row['evidence_type']} | {row['direction']} | {int(row['count'])} |")
    return lines


def _audit_component_table(components: pd.DataFrame) -> list[str]:
    lines = [
        "| Evidence type | Direction | Weighted score | Avg confidence | Count |",
        "|---|---:|---:|---:|---:|",
    ]
    if components.empty:
        lines.append("| none | none | 0.0 | 0.00 | 0 |")
        return lines
    for _, row in components.sort_values("weighted_score", ascending=False).iterrows():
        lines.append(
            f"| {row['evidence_type']} | {row['direction']} | "
            f"{float(row['weighted_score']):.1f} | "
            f"{float(row['avg_confidence']):.2f} | {int(row['evidence_count'])} |"
        )
    return lines


def _audit_cap_table(caps: pd.DataFrame) -> list[str]:
    lines = ["| Cap type | Cap value | Reason |", "|---|---:|---|"]
    if caps.empty:
        lines.append("| none | n/a | none |")
        return lines
    for _, row in caps.iterrows():
        lines.append(
            f"| {row['cap_type']} | {float(row['cap_value']):.2f} | {row['reason']} |"
        )
    return lines


def _audit_conflict_bullets(conflicts: pd.DataFrame) -> list[str]:
    if conflicts.empty:
        return ["- none"]
    lines = []
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    ranked = conflicts.copy()
    ranked["_rank"] = ranked["severity"].map(severity_rank).fillna(9)
    for _, row in ranked.sort_values(["_rank", "conflict_type"]).iterrows():
        lines.append(f"- {row['severity']}: {row['summary']}")
    return lines


def _evidence_bullets(ids_text: object, evidence_by_id: pd.DataFrame) -> list[str]:
    ids = [item for item in str(ids_text or "").split(",") if item]
    if not ids:
        return ["- none"]
    lines = []
    for evidence_id in ids[:5]:
        if evidence_by_id.empty or evidence_id not in evidence_by_id.index:
            continue
        row = evidence_by_id.loc[evidence_id]
        lines.append(
            f"- {row['summary']} "
            f"(strength {row['strength']}, confidence {float(row['confidence']):.2f})"
        )
    return lines or ["- none"]


def _event_return_lookup(event_returns: pd.DataFrame, prefer_factor: bool) -> dict[str, dict]:
    if event_returns.empty:
        return {}
    rows = event_returns[event_returns["return_window"] == "0_p5"].copy()
    if prefer_factor:
        rows = rows[rows["benchmark_type"] == "factor_model"]
    else:
        rows = rows[rows["benchmark_ticker"].isin(["SOXX", "SMH", "QQQ"])]
    rows["_source_id"] = rows["event_id"].astype(str) + ":" + rows["affected_ticker"].astype(str)
    rows["_quality_rank"] = (
        rows["data_quality_flag"].map({"complete": 0, "mapped_reaction_date": 1}).fillna(2)
    )
    return (
        rows.sort_values(["_source_id", "_quality_rank"])
        .groupby("_source_id", dropna=False)
        .head(1)
        .set_index("_source_id")
        .to_dict("index")
    )


def _evidence_row(**kwargs) -> dict:
    row = dict(kwargs)
    row["evidence_id"] = _stable_id(
        "evidence",
        row["ticker"],
        row["evidence_type"],
        row["source_table"],
        row["source_id"],
        row["metric_name"],
        row["source_date"],
    )
    row["ingested_at"] = row["created_at"]
    for column in ("source_date", "available_date", "as_of_date"):
        row[column] = _to_date(row[column])
    row["confidence"] = _bounded_confidence(row.get("confidence"))
    return row


def _run_id_from_frames(explicit_run_id: Optional[str], *frames: pd.DataFrame) -> str:
    if explicit_run_id:
        return explicit_run_id
    frame_run_ids = []
    for frame in frames:
        if frame.empty or "run_id" not in frame.columns:
            continue
        values = frame["run_id"].dropna().astype(str)
        values = values[values.str.len() > 0]
        frame_run_ids.extend(values.unique().tolist())
    unique_run_ids = list(dict.fromkeys(frame_run_ids))
    if len(unique_run_ids) == 1:
        return unique_run_ids[0]
    if len(unique_run_ids) > 1:
        raise ValueError(
            "run_id is ambiguous: input frames carry multiple run_id values; "
            "pass run_id explicitly"
        )
    raise ValueError(
        "run_id required: no explicit run_id was passed and no input frame carries run_id"
    )


def _stable_id(*parts: object) -> str:
    key = "|".join("" if pd.isna(part) else str(part) for part in parts)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:14]
    return f"{parts[0]}_{digest}"


def _to_date(value: object):
    date_value = pd.to_datetime(value, errors="coerce")
    if pd.isna(date_value):
        return None
    return date_value.date()


def _as_of_date(as_of_date: Optional[str], *frames: pd.DataFrame):
    if as_of_date:
        return pd.to_datetime(as_of_date).date()
    dates = []
    for frame in frames:
        if frame.empty:
            continue
        for column in ("date", "as_of_date", "reaction_date", "source_date"):
            if column in frame.columns:
                values = pd.to_datetime(frame[column], errors="coerce").dropna()
                if not values.empty:
                    dates.append(values.max())
    if not dates:
        return utc_now_naive().date()
    return max(dates).date()


def _direction_from_signed(value: object, threshold: float = 0.0) -> str:
    if pd.isna(value):
        return "mixed"
    numeric = float(value)
    if numeric > threshold:
        return "positive"
    if numeric < -threshold:
        return "negative"
    return "neutral"


def _direction_from_score(score: object) -> str:
    if pd.isna(score):
        return "mixed"
    numeric = float(score)
    if numeric >= 70:
        return "positive"
    if numeric <= 30:
        return "negative"
    return "neutral"


def _factor_direction(residual_20d: object, residual_60d: object) -> str:
    if pd.isna(residual_20d) or pd.isna(residual_60d):
        return "mixed"
    if residual_20d > 0.03 and residual_60d > 0.03:
        return "positive"
    if residual_20d < -0.03 and residual_60d < -0.03:
        return "negative"
    if abs(float(residual_20d)) < 0.03 and abs(float(residual_60d)) < 0.03:
        return "neutral"
    return "mixed"


def _strength_from_materiality(materiality: float, thresholds: list[float]) -> str:
    if materiality >= thresholds[2]:
        return "very_high"
    if materiality >= thresholds[1]:
        return "high"
    if materiality >= thresholds[0]:
        return "medium"
    return "low"


def _score_materiality(score: object) -> float:
    if pd.isna(score):
        return 0.0
    return abs(float(score) - 50.0) / 50.0


def _factor_confidence(row: pd.Series) -> float:
    confidence = 0.80
    if row.get("data_quality_flag") == "high_collinearity":
        confidence -= 0.15
    if pd.notna(row.get("factor_corr_qqq_soxx")) and abs(float(row["factor_corr_qqq_soxx"])) >= 0.9:
        confidence -= 0.10
    if pd.notna(row.get("r2")) and float(row["r2"]) < 0.30:
        confidence -= 0.15
    if row["ticker"] == "TSM":
        confidence = min(confidence, 0.60)
    return _bounded_confidence(confidence)


def _time_decay(source_date: object, as_of_date) -> float:
    if pd.isna(source_date):
        return 0.50
    delta = (pd.to_datetime(as_of_date) - pd.to_datetime(source_date)).days
    if delta <= 90:
        return 1.00
    if delta <= 180:
        return 0.70
    if delta <= 365:
        return 0.40
    return 0.20


def _bounded_confidence(value: object) -> float:
    if pd.isna(value):
        return 0.5
    return max(0.05, min(0.95, float(value)))


def _segment_summary(feature: pd.Series, direction: str) -> str:
    return (
        f"{feature['ticker']} {feature['feature_name']} is {direction} "
        f"with score {float(feature['feature_score']):.1f}."
    )


def _cash_flow_summary(feature: pd.Series, direction: str) -> str:
    return (
        f"{feature['ticker']} cash-flow feature {feature['feature_name']} is {direction} "
        f"with value {_fmt_number(feature.get('feature_value'))}."
    )


def _valuation_summary(feature: pd.Series, direction: str) -> str:
    return (
        f"{feature['ticker']} valuation feature {feature['feature_name']} is {direction} "
        f"with score {float(feature['feature_score']):.1f}."
    )


def _factor_summary(row: pd.Series, direction: str) -> str:
    caveat = (
        " Confidence is capped for missing FX/geopolitical factor."
        if row["ticker"] == "TSM"
        else ""
    )
    return (
        f"{row['ticker']} factor residual evidence is {direction}: 20d "
        f"{_fmt_pct(row.get('residual_return_20d'))}, 60d "
        f"{_fmt_pct(row.get('residual_return_60d'))}.{caveat}"
    )


def _thesis_tag_for_feature(feature_name: str) -> str:
    if "cloud" in feature_name:
        return "cloud_operating_leverage"
    if "data_center" in feature_name:
        return "ai_compute_demand"
    if "capex" in feature_name:
        return "capex_pressure"
    if "monthly_revenue" in feature_name or "hpc" in feature_name:
        return "ai_supply_chain_validation"
    return "company_driver"


def _risk_tag_for_feature(feature_name: str, direction: str) -> Optional[str]:
    if direction != "negative":
        return None
    if "capex" in feature_name:
        return "capex_pressure"
    if "margin" in feature_name:
        return "margin_pressure"
    if "revenue" in feature_name or "growth" in feature_name:
        return "growth_deceleration"
    return "negative_driver"


def _extract_thesis_tag(thesis_impact: object) -> Optional[str]:
    if pd.isna(thesis_impact):
        return None
    text = str(thesis_impact)
    marker = "thesis tag "
    if marker in text:
        return text.split(marker, 1)[1].strip(". ")
    return None


def _fmt_pct(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _fmt_number(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def _short(value: object, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _list_or_none(values: list[str]) -> str:
    values = list(dict.fromkeys(values))
    return ", ".join(values) if values else "none"


def _main_caveat(row: pd.Series) -> str:
    modifier = _clean_text(row.get("stance_modifier"))
    modifiers = modifier.split("+") if modifier else []
    caveats = _clean_text(row.get("data_quality_caveats"))
    risk_flags = _clean_text(row.get("risk_flags"))
    modifier_caveats = {
        "valuation_capped": "valuation evidence caps upside",
        "valuation_supported": "valuation evidence supports setup",
        "valuation_unknown": "valuation evidence missing",
        "residual_concentrated": "factor residual is concentrated",
        "factor_led": "needs non-factor confirmation",
        "factor_conflicted": "negative factor-residual conflict",
        "mixed_cash_flow": "cash-flow evidence is mixed",
        "data_quality_capped": caveats.split("; ", 1)[0] if caveats else "data-quality capped",
        "capped": caveats.split("; ", 1)[0] if caveats else "confidence capped",
        "mixed": caveats.split("; ", 1)[0] if caveats else "mixed evidence",
    }
    for item in modifiers:
        if item in modifier_caveats:
            return _short(modifier_caveats[item], 80)
    if caveats:
        return _short(caveats.split("; ", 1)[0], 80)
    if modifier and modifier != "clean":
        return modifier
    if risk_flags:
        return _short(risk_flags.split("; ", 1)[0], 80)
    return "none"


def _value_or_none(value: object) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "none"
    return str(value)


def _clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text
