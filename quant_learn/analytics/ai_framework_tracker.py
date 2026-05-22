"""Trusted-execution framework tracker and portfolio decision support."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from quant_learn.config import EXPORT_DIR, PROJECT_ROOT, ensure_directories
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

REPORT_PATH = PROJECT_ROOT / "reports" / "ai_execution_tracker.md"

INDICATOR_STATUS_SCORES = {
    "green": 85.0,
    "yellow": 55.0,
    "red": 20.0,
    "unknown": 45.0,
    "": 45.0,
}

PREDICTION_STATUS_SCORES = {
    "confirmed": 90.0,
    "on_track": 75.0,
    "watch": 55.0,
    "unknown": 45.0,
    "at_risk": 30.0,
    "falsified": 10.0,
    "": 45.0,
}


@dataclass(frozen=True)
class FrameworkInputs:
    as_of_date: date
    indicators: pd.DataFrame
    predictions: pd.DataFrame
    scenarios: pd.DataFrame
    holdings: pd.DataFrame


def run_ai_framework_tracker(
    as_of_date: Optional[date] = None,
    output_path: Path = REPORT_PATH,
) -> tuple[pd.DataFrame, Path]:
    """Build decision rows and write the AI framework tracker report."""

    inputs = load_framework_inputs(as_of_date)
    decisions = build_ai_framework_decisions(inputs)
    store_ai_framework_decisions(decisions)
    report_path = export_ai_framework_report(inputs, decisions, output_path)
    return decisions, report_path


def load_framework_inputs(as_of_date: Optional[date] = None) -> FrameworkInputs:
    """Load latest framework snapshots at or before `as_of_date`."""

    initialize_database()
    with connect() as conn:
        target_date = as_of_date or _latest_available_as_of_date(conn)
        if target_date is None:
            empty = pd.DataFrame()
            return FrameworkInputs(date.today(), empty, empty, empty, empty)
        indicators = _load_latest_snapshot(conn, "ai_framework_indicators", target_date)
        predictions = _load_latest_snapshot(conn, "ai_framework_predictions", target_date)
        scenarios = _load_latest_snapshot(conn, "ai_framework_scenarios", target_date)
        holdings = _load_latest_snapshot(conn, "ai_framework_holdings", target_date)

    for frame in (indicators, predictions, scenarios, holdings):
        if "as_of_date" in frame.columns and not frame.empty:
            frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
    if not predictions.empty and "deadline" in predictions.columns:
        predictions["deadline"] = pd.to_datetime(predictions["deadline"], errors="coerce").dt.date
    latest_dates = [
        frame["as_of_date"].max()
        for frame in (indicators, predictions, scenarios, holdings)
        if not frame.empty
    ]
    decision_date = max(latest_dates) if latest_dates else target_date
    return FrameworkInputs(decision_date, indicators, predictions, scenarios, holdings)


def build_ai_framework_decisions(inputs: FrameworkInputs) -> pd.DataFrame:
    """Score each holding against control-layer evidence and scenario risk."""

    if inputs.holdings.empty:
        return pd.DataFrame()

    indicators = score_indicators(inputs.indicators)
    predictions = score_predictions(inputs.predictions)
    indicator_layer_scores = _layer_scores(indicators, "indicator_score")
    prediction_layer_scores = _layer_scores(predictions, "prediction_score")
    tail_probability = _tail_probability(inputs.scenarios)
    ingested_at = utc_now_naive()
    rows = []

    for _, holding in inputs.holdings.iterrows():
        ticker = str(holding["ticker"])
        layers = _split_tokens(holding.get("control_layers"))
        is_cash = ticker.upper() == "CASH" or "risk_control" in layers
        default_support = 60.0 if is_cash else 50.0
        indicator_support = _support_score(
            layers,
            indicator_layer_scores,
            default=default_support,
        )
        prediction_support = _support_score(
            layers,
            prediction_layer_scores,
            default=default_support,
        )
        thesis_alignment = _thesis_alignment_score(holding)
        risk_control = _risk_control_score(holding, layers, indicators, tail_probability)

        if is_cash:
            decision_score = float(
                np.clip(0.35 * risk_control + 0.35 * thesis_alignment + 30.0, 0, 100)
            )
        else:
            decision_score = (
                0.35 * indicator_support
                + 0.30 * prediction_support
                + 0.20 * thesis_alignment
                + 0.15 * risk_control
            )
        decision_label = _decision_label(decision_score, is_cash, tail_probability)
        suggested_weight = _suggested_weight(holding, decision_score, is_cash, tail_probability)
        rebalance_flag = _rebalance_flag(holding, suggested_weight, decision_score)
        rows.append(
            {
                "as_of_date": inputs.as_of_date,
                "ticker": ticker,
                "holding_name": holding.get("holding_name"),
                "bucket": holding.get("bucket"),
                "target_weight": _safe_float(holding.get("target_weight")),
                "current_weight": _safe_float(holding.get("current_weight")),
                "suggested_weight": suggested_weight,
                "decision_score": round(float(decision_score), 2),
                "thesis_alignment_score": round(float(thesis_alignment), 2),
                "indicator_support_score": round(float(indicator_support), 2),
                "prediction_support_score": round(float(prediction_support), 2),
                "risk_control_score": round(float(risk_control), 2),
                "decision_label": decision_label,
                "rebalance_flag": rebalance_flag,
                "rationale": _decision_rationale(
                    layers,
                    indicator_support,
                    prediction_support,
                    risk_control,
                    tail_probability,
                ),
                "ingested_at": ingested_at,
            }
        )

    return pd.DataFrame(rows)


def score_indicators(indicators: pd.DataFrame) -> pd.DataFrame:
    """Attach computed status and score columns to indicator observations."""

    if indicators.empty:
        return indicators.copy()
    scored = indicators.copy()
    scored["computed_status"] = scored.apply(_indicator_status, axis=1)
    scored["indicator_score"] = scored["computed_status"].map(INDICATOR_STATUS_SCORES).fillna(45.0)
    scored["evidence_weight"] = scored.apply(_evidence_weight, axis=1)
    return scored


def score_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Attach evidence scores to falsifiable predictions."""

    if predictions.empty:
        return predictions.copy()
    scored = predictions.copy()
    scored["normalized_status"] = scored["status"].fillna("").astype(str).str.strip().str.lower()
    status_score = scored["normalized_status"].map(PREDICTION_STATUS_SCORES).fillna(45.0)
    probability_score = scored["probability"].map(lambda value: _safe_float(value, np.nan) * 100.0)
    scored["prediction_score"] = np.where(
        pd.isna(probability_score),
        status_score,
        0.55 * status_score + 0.45 * probability_score,
    )
    scored["evidence_weight"] = scored.apply(_evidence_weight, axis=1)
    return scored


def store_ai_framework_decisions(decisions: pd.DataFrame) -> int:
    """Store current decision-support rows."""

    if decisions.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, decisions, "ai_framework_decisions", ["as_of_date", "ticker"])


def export_ai_framework_report(
    inputs: FrameworkInputs,
    decisions: pd.DataFrame,
    output_path: Path = REPORT_PATH,
) -> Path:
    """Export CSV snapshots and a markdown operating dashboard."""

    ensure_directories()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    score_indicators(inputs.indicators).to_csv(
        EXPORT_DIR / "ai_framework_indicators_scored.csv",
        index=False,
    )
    score_predictions(inputs.predictions).to_csv(
        EXPORT_DIR / "ai_framework_predictions_scored.csv",
        index=False,
    )
    build_portfolio_exposure(inputs.holdings).to_csv(
        EXPORT_DIR / "ai_framework_portfolio_exposure.csv",
        index=False,
    )
    decisions.to_csv(EXPORT_DIR / "ai_framework_decisions.csv", index=False)
    output_path.write_text(_render_report(inputs, decisions), encoding="utf-8")
    return output_path


def build_portfolio_exposure(holdings: pd.DataFrame) -> pd.DataFrame:
    """Aggregate overlapping control-right exposures from holding-level maps."""

    if holdings.empty:
        return pd.DataFrame()
    rows = []
    for _, holding in holdings.iterrows():
        exposure_map = _parse_exposure_map(holding.get("exposure_map"))
        if not exposure_map:
            exposure_map = _fallback_exposure_map(holding)
        for layer, exposure in exposure_map.items():
            rows.append(
                {
                    "control_layer": layer,
                    "ticker": holding["ticker"],
                    "exposure_weight": exposure,
                }
            )
    if not rows:
        return pd.DataFrame()
    exposure_rows = pd.DataFrame(rows)
    grouped = exposure_rows.groupby("control_layer", sort=True)
    return pd.DataFrame(
        [
            {
                "control_layer": layer,
                "exposure_weight": group["exposure_weight"].sum(),
                "top_holdings": _format_exposure_holdings(group),
            }
            for layer, group in grouped
        ]
    ).sort_values("exposure_weight", ascending=False)


def _latest_available_as_of_date(conn) -> Optional[date]:
    dates = []
    for table in (
        "ai_framework_holdings",
        "ai_framework_indicators",
        "ai_framework_predictions",
        "ai_framework_scenarios",
    ):
        value = conn.execute(f"SELECT max(as_of_date) FROM {table}").fetchone()[0]
        if value is not None:
            dates.append(value)
    return max(dates) if dates else None


def _load_latest_snapshot(conn, table: str, as_of_date: date) -> pd.DataFrame:
    snapshot_date = conn.execute(
        f"SELECT max(as_of_date) FROM {table} WHERE as_of_date <= ?",
        [as_of_date],
    ).fetchone()[0]
    if snapshot_date is None:
        return pd.DataFrame()
    return conn.execute(
        f"SELECT * FROM {table} WHERE as_of_date = ? ORDER BY 1, 2",
        [snapshot_date],
    ).fetchdf()


def _indicator_status(row: pd.Series) -> str:
    explicit = str(row.get("status") or "").strip().lower()
    if explicit and explicit not in {"nan", "none"}:
        return explicit
    current = _safe_float(row.get("current_value"), np.nan)
    target = _safe_float(row.get("target_value"), np.nan)
    warning = _safe_float(row.get("warning_value"), np.nan)
    direction = str(row.get("direction") or "").strip().lower()
    if pd.isna(current) or pd.isna(target):
        return "unknown"
    if direction == "higher_is_bullish":
        if current >= target:
            return "green"
        if not pd.isna(warning) and current >= warning:
            return "yellow"
        return "red"
    if direction == "lower_is_bullish":
        if current <= target:
            return "green"
        if not pd.isna(warning) and current <= warning:
            return "yellow"
        return "red"
    if direction == "binary_positive":
        if current >= 1:
            return "green"
        if current > 0:
            return "yellow"
        return "red"
    return "unknown"


def _evidence_weight(row: pd.Series) -> float:
    importance = _safe_float(row.get("importance_score"), 3.0)
    confidence = _safe_float(row.get("confidence"), 0.5)
    if confidence > 1:
        confidence = confidence / 100.0
    return float(max(0.1, importance) * max(0.25, confidence))


def _layer_scores(scored: pd.DataFrame, score_column: str) -> dict[str, float]:
    if scored.empty or score_column not in scored.columns:
        return {}
    layer_scores = {}
    for layer, group in scored.groupby("control_layer"):
        layer_scores[str(layer)] = _weighted_average(group[score_column], group["evidence_weight"])
    return layer_scores


def _support_score(layers: list[str], layer_scores: dict[str, float], default: float) -> float:
    values = [layer_scores[layer] for layer in layers if layer in layer_scores]
    if not values:
        return default
    return float(np.mean(values))


def _thesis_alignment_score(holding: pd.Series) -> float:
    action_bias = str(holding.get("action_bias") or "").strip().lower()
    bucket = str(holding.get("bucket") or "").strip().lower()
    score = {
        "add": 75.0,
        "increase": 75.0,
        "buy": 75.0,
        "hold": 62.0,
        "watch": 55.0,
        "trim": 42.0,
        "avoid": 25.0,
    }.get(action_bias, 60.0)
    if "core" in bucket:
        score += 4.0
    if "dry powder" in bucket:
        score += 8.0
    if "cyclical" in bucket or "optionality" in bucket:
        score -= 2.0
    return float(np.clip(score, 0.0, 100.0))


def _risk_control_score(
    holding: pd.Series,
    layers: list[str],
    indicators: pd.DataFrame,
    tail_probability: float,
) -> float:
    score = 76.0
    risk_flags = _split_tokens(holding.get("risk_flags"))
    score -= min(30.0, 4.0 * len(risk_flags))
    bucket = str(holding.get("bucket") or "").strip().lower()
    if "cyclical" in bucket or "optionality" in bucket:
        score -= 4.0
    if tail_probability >= 0.35 and "core" not in bucket:
        score -= 5.0
    if not indicators.empty and layers:
        relevant = indicators[indicators["control_layer"].isin(layers)]
        red_count = int((relevant.get("computed_status", pd.Series(dtype=str)) == "red").sum())
        score -= min(20.0, 5.0 * red_count)
    if "risk_control" in layers:
        score = max(score, 85.0)
    return float(np.clip(score, 20.0, 92.0))


def _tail_probability(scenarios: pd.DataFrame) -> float:
    if scenarios.empty:
        return 0.0
    scenario_type = scenarios["scenario_type"].fillna("").astype(str).str.lower()
    tail = scenarios[scenario_type.isin(["risk", "tail"])]
    return float(tail["probability"].fillna(0.0).sum())


def _decision_label(decision_score: float, is_cash: bool, tail_probability: float) -> str:
    if is_cash:
        if tail_probability >= 0.35:
            return "Maintain dry powder"
        return "Hold cash reserve"
    if decision_score >= 75:
        return "Increase / evidence improving"
    if decision_score >= 62:
        return "Hold target / monitor"
    if decision_score >= 45:
        return "Watch / require new evidence"
    if decision_score >= 35:
        return "Reduce toward lower band"
    return "De-risk / thesis not confirmed"


def _suggested_weight(
    holding: pd.Series,
    decision_score: float,
    is_cash: bool,
    tail_probability: float,
) -> float:
    target = _safe_float(holding.get("target_weight"), 0.0)
    minimum = _safe_float(holding.get("min_weight"), target)
    maximum = _safe_float(holding.get("max_weight"), target)
    if is_cash:
        add = 2.0 if tail_probability >= 0.35 else 0.0
        return round(float(np.clip(target + add, minimum, maximum)), 2)
    if decision_score >= 75:
        return round(float(np.clip(target + 1.0, minimum, maximum)), 2)
    if decision_score >= 45:
        return round(float(np.clip(target, minimum, maximum)), 2)
    if decision_score >= 35:
        return round(float(np.clip(target - 1.0, minimum, maximum)), 2)
    return round(float(minimum), 2)


def _rebalance_flag(holding: pd.Series, suggested_weight: float, decision_score: float) -> str:
    current = _safe_float(
        holding.get("current_weight"),
        _safe_float(holding.get("target_weight"), 0.0),
    )
    minimum = _safe_float(holding.get("min_weight"), current)
    maximum = _safe_float(holding.get("max_weight"), current)
    if current < minimum:
        return "below target band"
    if current > maximum:
        return "above target band"
    if suggested_weight > current + 0.5:
        return "consider add toward suggested weight"
    if suggested_weight < current - 0.5:
        if decision_score < 50:
            return "evidence weak; trim toward lower band"
        return "consider trim toward suggested weight"
    return "within band"


def _decision_rationale(
    layers: list[str],
    indicator_support: float,
    prediction_support: float,
    risk_control: float,
    tail_probability: float,
) -> str:
    layer_text = ";".join(layers) if layers else "none"
    return (
        f"layers={layer_text}; indicator_support={indicator_support:.1f}; "
        f"prediction_support={prediction_support:.1f}; risk_control={risk_control:.1f}; "
        f"tail_scenario_probability={tail_probability:.1%}"
    )


def _render_report(inputs: FrameworkInputs, decisions: pd.DataFrame) -> str:
    indicators = score_indicators(inputs.indicators)
    predictions = score_predictions(inputs.predictions)
    return f"""# AI Trusted Execution Tracker

As of: {inputs.as_of_date}

This is research decision support, not investment advice. The operating thesis is
that the scarce asset is trusted execution of intelligence: authority, action,
verification, liability, and the human attention needed to supervise them.

## Control-Layer Dashboard

{_format_control_layers(indicators, predictions)}

## Portfolio Control-Rights Exposure

{_format_portfolio_exposure(inputs.holdings)}

## Leading Indicators

{_format_indicators(indicators)}

## Falsifiable Predictions

{_format_predictions(predictions)}

## Scenario Weights

{_format_scenarios(inputs.scenarios)}

## Monitoring Questions

{_format_monitoring_questions(indicators)}

## Watchlist Gaps

{_format_watchlist_gaps(indicators)}

## Portfolio Decision System

{_format_decisions(decisions)}

## Review Queue

{_format_review_queue(indicators, predictions, decisions)}

## Update Loop

1. Update the four CSVs under `data/manual/ai_framework_*.csv`.
2. Run `uv run python -m scripts.import_ai_framework`.
3. Run `uv run python -m scripts.build_ai_framework_tracker`.
4. Review red indicators, at-risk predictions, and any rebalance flags before
   changing weights.
"""


def _format_control_layers(indicators: pd.DataFrame, predictions: pd.DataFrame) -> str:
    layers = sorted(
        set(indicators.get("control_layer", pd.Series(dtype=str)).dropna())
        | set(predictions.get("control_layer", pd.Series(dtype=str)).dropna())
    )
    if not layers:
        return "No control-layer rows available."
    indicator_scores = _layer_scores(indicators, "indicator_score")
    prediction_scores = _layer_scores(predictions, "prediction_score")
    rows = []
    for layer in layers:
        indicator_count = (
            int((indicators["control_layer"] == layer).sum()) if not indicators.empty else 0
        )
        prediction_count = (
            int((predictions["control_layer"] == layer).sum()) if not predictions.empty else 0
        )
        rows.append(
            {
                "control_layer": layer,
                "indicator_score": _fmt_score(indicator_scores.get(layer)),
                "prediction_score": _fmt_score(prediction_scores.get(layer)),
                "indicator_count": indicator_count,
                "prediction_count": prediction_count,
            }
        )
    return pd.DataFrame(rows).to_markdown(index=False)


def _format_portfolio_exposure(holdings: pd.DataFrame) -> str:
    exposure = build_portfolio_exposure(holdings)
    if exposure.empty:
        return "No portfolio exposure rows available."
    display = exposure.copy()
    display["exposure_weight"] = display["exposure_weight"].map(_fmt_weight)
    return (
        "Exposures can overlap by design; this table is a control-rights map, "
        "not a sum-to-100 allocation.\n\n"
        f"{display.to_markdown(index=False)}"
    )


def _format_indicators(indicators: pd.DataFrame) -> str:
    if indicators.empty:
        return "No leading indicators loaded."
    display = indicators[
        [
            "control_layer",
            "indicator_name",
            "current_value",
            "target_value",
            "warning_value",
            "unit",
            "computed_status",
            "indicator_score",
            "confidence",
            "notes",
        ]
    ].copy()
    for column in ("current_value", "target_value", "warning_value"):
        display[column] = display[column].map(_fmt_number)
    for column in ("unit", "notes"):
        display[column] = display[column].fillna("")
    display["indicator_score"] = display["indicator_score"].map(_fmt_score)
    display["confidence"] = display["confidence"].map(_fmt_probability)
    return display.to_markdown(index=False)


def _format_predictions(predictions: pd.DataFrame) -> str:
    if predictions.empty:
        return "No falsifiable predictions loaded."
    display = predictions[
        [
            "control_layer",
            "prediction_text",
            "deadline",
            "target_threshold",
            "current_value",
            "unit",
            "status",
            "probability",
            "falsifier",
        ]
    ].copy()
    display["current_value"] = display["current_value"].map(_fmt_number)
    display["unit"] = display["unit"].fillna("")
    display["probability"] = display["probability"].map(_fmt_probability)
    return display.to_markdown(index=False)


def _format_scenarios(scenarios: pd.DataFrame) -> str:
    if scenarios.empty:
        return "No scenarios loaded."
    display = scenarios[
        [
            "scenario_name",
            "probability",
            "scenario_type",
            "thesis_impact",
            "portfolio_posture",
        ]
    ].copy()
    display["probability"] = display["probability"].map(_fmt_probability)
    return display.to_markdown(index=False)


def _format_monitoring_questions(indicators: pd.DataFrame) -> str:
    if indicators.empty:
        return "No monitoring indicators loaded."
    specs = [
        (
            "Capability regime",
            "Does METR task horizon keep extending?",
            "meta_metr_task_horizon_doubling_time",
            "If doubling time compresses below 60 days, reassess toward authority/outcome.",
        ),
        (
            "Economic regime",
            "Does risk-adjusted cost per verified task keep declining?",
            "cost_risk_adjusted_verified_task_index",
            "If TCAO does not decline, compress pure capacity exposure.",
        ),
        (
            "Trust regime",
            "Do enterprise agents keep gaining write/execute permission?",
            "authority_write_permission_penetration",
            "If Fortune 500 write-permission penetration stalls below 10%, reassess authority.",
        ),
    ]
    rows = []
    indexed = indicators.set_index("indicator_id") if "indicator_id" in indicators.columns else None
    for regime, question, indicator_id, trigger in specs:
        row = None
        if indexed is not None and indicator_id in indexed.index:
            row = indexed.loc[indicator_id]
        rows.append(
            {
                "regime": regime,
                "question": question,
                "current": _fmt_number(row.get("current_value")) if row is not None else "n/a",
                "unit": row.get("unit") if row is not None else "",
                "status": row.get("computed_status") if row is not None else "missing",
                "trigger": trigger,
            }
        )
    return pd.DataFrame(rows).to_markdown(index=False)


def _format_watchlist_gaps(indicators: pd.DataFrame) -> str:
    if indicators.empty:
        return "- none"
    watchlist = indicators[indicators["control_layer"] == "watchlist"]
    if watchlist.empty:
        return "- none"
    lines = []
    for _, row in watchlist.iterrows():
        lines.append(
            f"- {row['indicator_name']}: status={row['computed_status']}, "
            f"target={_fmt_number(row.get('target_value'))}{row.get('unit') or ''}; "
            f"{row.get('notes') or ''}"
        )
    return "\n".join(lines)


def _format_decisions(decisions: pd.DataFrame) -> str:
    if decisions.empty:
        return "No portfolio decision rows available."
    display = decisions[
        [
            "ticker",
            "bucket",
            "target_weight",
            "current_weight",
            "suggested_weight",
            "decision_score",
            "decision_label",
            "rebalance_flag",
        ]
    ].copy()
    for column in ("target_weight", "current_weight", "suggested_weight"):
        display[column] = display[column].map(_fmt_weight)
    display["decision_score"] = display["decision_score"].map(_fmt_score)
    return display.to_markdown(index=False)


def _format_review_queue(
    indicators: pd.DataFrame,
    predictions: pd.DataFrame,
    decisions: pd.DataFrame,
) -> str:
    lines = []
    if not indicators.empty:
        weak = indicators[indicators["computed_status"].isin(["red", "unknown"])]
        for _, row in weak.iterrows():
            lines.append(
                f"- indicator: {row['control_layer']} / "
                f"{row['indicator_name']} is {row['computed_status']}"
            )
    if not predictions.empty:
        risky = predictions[predictions["status"].isin(["at_risk", "falsified", "unknown"])]
        for _, row in risky.iterrows():
            lines.append(
                f"- prediction: {row['prediction_id']} "
                f"status={row['status']} deadline={row['deadline']}"
            )
    if not decisions.empty:
        flagged = decisions[decisions["rebalance_flag"] != "within band"]
        for _, row in flagged.iterrows():
            lines.append(
                f"- holding: {row['ticker']} "
                f"{row['rebalance_flag']} ({row['decision_label']})"
            )
    return "\n".join(lines) if lines else "- none"


def _weighted_average(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return 50.0
    return float(np.average(values[valid], weights=weights[valid]))


def _parse_exposure_map(value) -> dict[str, float]:
    if pd.isna(value):
        return {}
    exposures = {}
    for token in str(value).replace(",", ";").split(";"):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            layer, raw_value = token.split(":", 1)
        elif "=" in token:
            layer, raw_value = token.split("=", 1)
        else:
            continue
        layer = layer.strip().lower()
        exposure = _safe_float(raw_value, np.nan)
        if layer and not pd.isna(exposure):
            exposures[layer] = exposure
    return exposures


def _fallback_exposure_map(holding: pd.Series) -> dict[str, float]:
    layers = _split_tokens(holding.get("control_layers"))
    if not layers:
        return {}
    target = _safe_float(holding.get("target_weight"), 0.0)
    equal_weight = target / len(layers)
    return {layer: equal_weight for layer in layers}


def _format_exposure_holdings(group: pd.DataFrame) -> str:
    sorted_group = group.sort_values("exposure_weight", ascending=False)
    return "; ".join(
        f"{row.ticker} {_fmt_weight(row.exposure_weight)}"
        for row in sorted_group.itertuples()
    )


def _split_tokens(value) -> list[str]:
    if pd.isna(value):
        return []
    return [
        token.strip().lower()
        for token in str(value).replace(",", ";").split(";")
        if token.strip()
    ]


def _safe_float(value, default=np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_score(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.1f}"


def _fmt_number(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):g}"


def _fmt_probability(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.0f}%"


def _fmt_weight(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.1f}%"
