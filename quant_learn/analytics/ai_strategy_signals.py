"""Phase 1 systematic-discretionary strategy signals for the AI framework."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from quant_learn.analytics.ai_framework_tracker import (
    FrameworkInputs,
    load_framework_inputs,
    score_indicators,
)
from quant_learn.config import EXPORT_DIR, PROJECT_ROOT, ensure_directories
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

REPORT_PATH = PROJECT_ROOT / "reports" / "ai_strategy_system.md"


@dataclass(frozen=True)
class StrategyInputs:
    framework: FrameworkInputs
    control_scores: pd.DataFrame


def run_ai_strategy_signals(
    as_of_date: Optional[date] = None,
    output_path: Path = REPORT_PATH,
) -> tuple[pd.DataFrame, Path]:
    """Build Phase 1 strategy signals and export a report."""

    inputs = load_strategy_inputs(as_of_date)
    signals = build_strategy_signals(inputs)
    store_strategy_signals(signals)
    report_path = export_strategy_report(inputs, signals, output_path)
    return signals, report_path


def load_strategy_inputs(as_of_date: Optional[date] = None) -> StrategyInputs:
    """Load framework tracker inputs and latest control-right score matrix."""

    framework = load_framework_inputs(as_of_date)
    initialize_database()
    with connect() as conn:
        target_date = as_of_date or framework.as_of_date
        score_date = conn.execute(
            "SELECT max(as_of_date) FROM ai_control_right_scores WHERE as_of_date <= ?",
            [target_date],
        ).fetchone()[0]
        if score_date is None:
            control_scores = pd.DataFrame()
        else:
            control_scores = conn.execute(
                """
                SELECT *
                FROM ai_control_right_scores
                WHERE as_of_date = ?
                ORDER BY ticker
                """,
                [score_date],
            ).fetchdf()
    if not control_scores.empty:
        control_scores["as_of_date"] = pd.to_datetime(control_scores["as_of_date"]).dt.date
    return StrategyInputs(framework=framework, control_scores=control_scores)


def build_strategy_signals(inputs: StrategyInputs) -> pd.DataFrame:
    """Convert framework indicators into non-automatic strategy review signals."""

    indicators = score_indicators(inputs.framework.indicators)
    as_of_date = inputs.framework.as_of_date
    created_at = utc_now_naive()
    rows = []
    rows.extend(_plateau_signals(as_of_date, indicators, created_at))
    rows.extend(_watchlist_signals(as_of_date, indicators, created_at))
    rows.extend(_outcome_mispricing_research_signals(as_of_date, inputs, created_at))
    if not rows:
        rows.append(
            _signal_row(
                as_of_date=as_of_date,
                signal_id="no_action",
                signal_type="status",
                severity="info",
                action_bias="hold_framework",
                target_layer="portfolio",
                target_tickers="",
                source_indicator_ids="",
                summary="No Phase 1 strategy alerts generated.",
                rationale="Indicator state did not cross a plateau or review threshold.",
                suggested_review="Continue monthly indicator updates.",
                created_at=created_at,
            )
        )
    return pd.DataFrame(rows)


def store_strategy_signals(signals: pd.DataFrame) -> int:
    """Store latest strategy review signals."""

    if signals.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, signals, "ai_strategy_signals", ["as_of_date", "signal_id"])


def export_strategy_report(
    inputs: StrategyInputs,
    signals: pd.DataFrame,
    output_path: Path = REPORT_PATH,
) -> Path:
    """Export strategy CSVs and a markdown report."""

    ensure_directories()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    signals.to_csv(EXPORT_DIR / "ai_strategy_signals.csv", index=False)
    inputs.control_scores.to_csv(EXPORT_DIR / "ai_control_right_scores_latest.csv", index=False)
    output_path.write_text(_render_report(inputs, signals), encoding="utf-8")
    return output_path


def _plateau_signals(as_of_date: date, indicators: pd.DataFrame, created_at) -> list[dict]:
    specs = [
        (
            "capability_plateau",
            "Capability plateau watch",
            "meta_metr_task_horizon_doubling_time",
            "meta_linji_capability_frontier_assessment",
            "capability",
            "Capability scaling is the first framework gate.",
        ),
        (
            "economic_plateau",
            "Economic plateau watch",
            "cost_risk_adjusted_verified_task_index",
            "",
            "cost",
            "TCAO must fall for enterprise AI spend to compound economically.",
        ),
        (
            "trust_plateau",
            "Trust plateau watch",
            "authority_write_permission_penetration",
            "authority_expert_review_minutes",
            "authority",
            "Trusted execution requires write permission and lower expert review minutes.",
        ),
    ]
    rows = []
    for signal_id, summary, primary_id, secondary_id, layer, rationale in specs:
        relevant_ids = [primary_id] + ([secondary_id] if secondary_id else [])
        relevant = _indicator_rows(indicators, relevant_ids)
        severity = _plateau_severity(relevant)
        action_bias = {
            "high": "framework_review",
            "medium": "monitor_monthly",
            "info": "collect_data",
        }[severity]
        rows.append(
            _signal_row(
                as_of_date=as_of_date,
                signal_id=signal_id,
                signal_type="plateau_detection",
                severity=severity,
                action_bias=action_bias,
                target_layer=layer,
                target_tickers="",
                source_indicator_ids=";".join(relevant_ids),
                summary=summary,
                rationale=_indicator_rationale(relevant, rationale),
                suggested_review=_plateau_review(layer, severity),
                created_at=created_at,
            )
        )
    return rows


def _watchlist_signals(as_of_date: date, indicators: pd.DataFrame, created_at) -> list[dict]:
    rows = []
    watchlist = indicators[indicators["control_layer"] == "watchlist"]
    for _, row in watchlist.iterrows():
        rows.append(
            _signal_row(
                as_of_date=as_of_date,
                signal_id=f"watchlist_{row['indicator_id']}",
                signal_type="watchlist_gap",
                severity="info",
                action_bias="no_position_until_clean_proxy",
                target_layer="watchlist",
                target_tickers="DDOG;CRWD;PANW;OKTA;private_agent_infra",
                source_indicator_ids=row["indicator_id"],
                summary=row["indicator_name"],
                rationale=row.get("notes") or "",
                suggested_review=(
                    "Track agent-specific revenue, IPOs, or disclosed product traction."
                ),
                created_at=created_at,
            )
        )
    return rows


def _outcome_mispricing_research_signals(
    as_of_date: date,
    inputs: StrategyInputs,
    created_at,
) -> list[dict]:
    if inputs.control_scores.empty:
        return []
    outcome_candidates = inputs.control_scores[inputs.control_scores["outcome_score"] >= 75]
    if outcome_candidates.empty:
        return []
    target_tickers = ";".join(outcome_candidates["ticker"].astype(str).tolist())
    return [
        _signal_row(
            as_of_date=as_of_date,
            signal_id="outcome_control_mispricing_research",
            signal_type="mispricing_research",
            severity="medium",
            action_bias="run_valuation_overlay",
            target_layer="outcome",
            target_tickers=target_tickers,
            source_indicator_ids="outcome_vertical_verifier_rerating_count",
            summary="Outcome-control candidates need valuation-implied-score research.",
            rationale=(
                "High outcome-control scores are not enough for a trade signal. "
                "The next required input is a market-implied score from valuation, "
                "growth, retention, and AI-specific revenue contribution."
            ),
            suggested_review="Build a valuation overlay before sizing outcome mispricing trades.",
            created_at=created_at,
        )
    ]


def _indicator_rows(indicators: pd.DataFrame, indicator_ids: list[str]) -> pd.DataFrame:
    if indicators.empty:
        return pd.DataFrame()
    return indicators[indicators["indicator_id"].isin(indicator_ids)].copy()


def _plateau_severity(rows: pd.DataFrame) -> str:
    if rows.empty:
        return "info"
    statuses = set(rows["computed_status"].fillna("unknown").astype(str))
    if "red" in statuses:
        return "high"
    if "yellow" in statuses:
        return "medium"
    if statuses <= {"unknown"}:
        return "info"
    return "info"


def _indicator_rationale(rows: pd.DataFrame, base: str) -> str:
    if rows.empty:
        return f"{base} No indicator rows loaded."
    parts = []
    for row in rows.itertuples():
        value = "n/a" if pd.isna(row.current_value) else f"{row.current_value:g}"
        parts.append(f"{row.indicator_id}={value} {row.unit} ({row.computed_status})")
    return f"{base} " + "; ".join(parts)


def _plateau_review(layer: str, severity: str) -> str:
    if severity == "high":
        return f"Pause automatic shifts and run manual {layer} framework review."
    if severity == "medium":
        return f"Increase {layer} review cadence; no automatic rebalance."
    return f"Collect better {layer} evidence before changing weights."


def _signal_row(
    *,
    as_of_date: date,
    signal_id: str,
    signal_type: str,
    severity: str,
    action_bias: str,
    target_layer: str,
    target_tickers: str,
    source_indicator_ids: str,
    summary: str,
    rationale: str,
    suggested_review: str,
    created_at,
) -> dict:
    return {
        "as_of_date": as_of_date,
        "signal_id": signal_id,
        "signal_type": signal_type,
        "severity": severity,
        "action_bias": action_bias,
        "target_layer": target_layer,
        "target_tickers": target_tickers,
        "source_indicator_ids": source_indicator_ids,
        "summary": summary,
        "rationale": rationale,
        "suggested_review": suggested_review,
        "created_at": created_at,
        "ingested_at": created_at,
    }


def _render_report(inputs: StrategyInputs, signals: pd.DataFrame) -> str:
    return f"""# AI Strategy System Phase 1

As of: {inputs.framework.as_of_date}

This is a systematic-discretionary research system, not an automated trading
system. It converts the control-rights framework into review signals, not broker
orders.

## System Boundary

- Position sizing can become algorithmic after the indicator set has a live
  history.
- Plateau detection is an alert, not an automatic trade.
- Regime change decisions require manual review.
- Execution APIs, tax-lot logic, and broker routing are intentionally out of
  scope for Phase 1.

## Strategy Signals

{_format_signals(signals)}

## Control-Right Score Matrix

{_format_control_scores(inputs.control_scores)}

## Build Sequence

1. Keep running the tracker from `reports/ai_execution_tracker.md`.
2. Update control-right scores quarterly from filings, calls, and source memos.
3. Use this report to decide which research queue deserves attention.
4. Build valuation-implied scores before treating mispricing research as trades.
"""


def _format_signals(signals: pd.DataFrame) -> str:
    if signals.empty:
        return "No strategy signals available."
    columns = [
        "signal_type",
        "severity",
        "action_bias",
        "target_layer",
        "target_tickers",
        "summary",
        "suggested_review",
    ]
    return signals[columns].to_markdown(index=False)


def _format_control_scores(scores: pd.DataFrame) -> str:
    if scores.empty:
        return "No control-right scores loaded."
    columns = [
        "ticker",
        "holding_name",
        "capacity_score",
        "cost_score",
        "authority_score",
        "outcome_score",
        "physical_ai_score",
        "confidence",
    ]
    display = scores[columns].copy()
    display["confidence"] = display["confidence"].map(lambda value: f"{float(value) * 100:.0f}%")
    return display.to_markdown(index=False)
