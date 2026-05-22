from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import ai_framework_tracker, ai_strategy_signals
from quant_learn.db import initialize_database
from quant_learn.ingest import ai_framework


def test_indicator_status_infers_directional_thresholds() -> None:
    indicators = pd.DataFrame(
        [
            {
                "control_layer": "capacity",
                "status": "",
                "current_value": 8.0,
                "target_value": 10.0,
                "warning_value": 20.0,
                "direction": "lower_is_bullish",
                "importance_score": 5.0,
                "confidence": 0.5,
            },
            {
                "control_layer": "authority",
                "status": "",
                "current_value": 3.0,
                "target_value": 10.0,
                "warning_value": 5.0,
                "direction": "higher_is_bullish",
                "importance_score": 5.0,
                "confidence": 0.5,
            },
        ]
    )

    scored = ai_framework_tracker.score_indicators(indicators)

    assert list(scored["computed_status"]) == ["green", "red"]
    assert list(scored["indicator_score"]) == [85.0, 20.0]


def test_portfolio_exposure_uses_explicit_overlapping_map() -> None:
    holdings = pd.DataFrame(
        [
            {
                "ticker": "MSFT",
                "target_weight": 18.0,
                "control_layers": "authority;outcome",
                "exposure_map": "authority:18;outcome:10",
            },
            {
                "ticker": "NVDA",
                "target_weight": 7.0,
                "control_layers": "capacity;cost",
                "exposure_map": "capacity:7;cost:5",
            },
        ]
    )

    exposure = ai_framework_tracker.build_portfolio_exposure(holdings).set_index(
        "control_layer"
    )

    assert exposure.loc["authority", "exposure_weight"] == 18.0
    assert exposure.loc["outcome", "exposure_weight"] == 10.0
    assert exposure.loc["capacity", "exposure_weight"] == 7.0
    assert exposure.loc["cost", "exposure_weight"] == 5.0


def test_strategy_signals_flag_red_plateau_and_outcome_research() -> None:
    indicators = pd.DataFrame(
        [
            {
                "indicator_id": "meta_metr_task_horizon_doubling_time",
                "control_layer": "meta",
                "indicator_name": "METR task horizon",
                "status": "",
                "current_value": 220.0,
                "target_value": 60.0,
                "warning_value": 180.0,
                "unit": "days",
                "direction": "lower_is_bullish",
                "importance_score": 5.0,
                "confidence": 0.5,
            },
            {
                "indicator_id": "meta_linji_capability_frontier_assessment",
                "control_layer": "meta",
                "indicator_name": "Linji frontier assessment",
                "status": "unknown",
                "current_value": None,
                "target_value": 70.0,
                "warning_value": 40.0,
                "unit": "score",
                "direction": "higher_is_bullish",
                "importance_score": 5.0,
                "confidence": 0.5,
            },
        ]
    )
    framework = ai_framework_tracker.FrameworkInputs(
        as_of_date=pd.Timestamp("2026-05-21").date(),
        indicators=indicators,
        predictions=pd.DataFrame(),
        scenarios=pd.DataFrame(),
        holdings=pd.DataFrame(),
    )
    control_scores = pd.DataFrame(
        [
            {
                "ticker": "MCO",
                "outcome_score": 85.0,
            }
        ]
    )
    inputs = ai_strategy_signals.StrategyInputs(framework, control_scores)

    signals = ai_strategy_signals.build_strategy_signals(inputs).set_index("signal_id")

    assert signals.loc["capability_plateau", "severity"] == "high"
    assert signals.loc["capability_plateau", "action_bias"] == "framework_review"
    assert "outcome_control_mispricing_research" in signals.index


def test_ai_framework_import_and_decision_scores(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "framework.duckdb"
    initialize_database(db_path)
    _patch_db(monkeypatch, db_path)

    indicators = tmp_path / "indicators.csv"
    indicators.write_text(
        "\n".join(
            [
                "as_of_date,indicator_id,control_layer,indicator_name,direction,"
                "current_value,target_value,warning_value,status,importance_score,confidence",
                "2026-05-21,cap_good,capacity,Capacity signal,higher_is_bullish,"
                "90,70,40,,5,0.8",
                "2026-05-21,auth_bad,authority,Authority bottleneck,higher_is_bullish,"
                "2,20,5,,5,0.8",
            ]
        ),
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.csv"
    predictions.write_text(
        "\n".join(
            [
                "as_of_date,prediction_id,control_layer,prediction_text,falsifier,"
                "status,probability,confidence",
                "2026-05-21,pred_cap,capacity,Capacity thesis,Falsified by weak supply,"
                "on_track,0.7,0.8",
                "2026-05-21,pred_auth,authority,Authority thesis,Falsified by no adoption,"
                "at_risk,0.2,0.8",
            ]
        ),
        encoding="utf-8",
    )
    scenarios = tmp_path / "scenarios.csv"
    scenarios.write_text(
        "\n".join(
            [
                "as_of_date,scenario_id,scenario_name,probability,scenario_type",
                "2026-05-21,tail,Trust plateau,40,risk",
                "2026-05-21,base,Scaling,60,base",
            ]
        ),
        encoding="utf-8",
    )
    holdings = tmp_path / "holdings.csv"
    holdings.write_text(
        "\n".join(
            [
                "as_of_date,ticker,holding_name,bucket,target_weight,current_weight,"
                "min_weight,max_weight,control_layers,thesis,risk_flags,action_bias",
                "2026-05-21,TSM,TSMC,Core Compounders,7,7,5,10,capacity,"
                "Capacity bottleneck,geopolitical risk,hold",
                "2026-05-21,MSFT,Microsoft,Core Compounders,18,18,14,22,authority,"
                "Authority layer,valuation risk,hold",
                "2026-05-21,CASH,Cash,Dry Powder,10,10,5,20,risk_control,"
                "Dry powder,cash drag,hold",
            ]
        ),
        encoding="utf-8",
    )
    control_scores = tmp_path / "control_scores.csv"
    control_scores.write_text(
        "\n".join(
            [
                "as_of_date,ticker,capacity_score,cost_score,authority_score,"
                "outcome_score,physical_ai_score,confidence",
                "2026-05-21,TSM,90,20,5,5,5,0.5",
                "2026-05-21,MSFT,20,10,90,75,5,0.5",
                "2026-05-21,CASH,0,0,0,0,0,1.0",
            ]
        ),
        encoding="utf-8",
    )

    ai_framework.import_ai_framework(
        indicators_path=indicators,
        predictions_path=predictions,
        scenarios_path=scenarios,
        holdings_path=holdings,
        control_scores_path=control_scores,
    )
    inputs = ai_framework_tracker.load_framework_inputs()
    decisions = ai_framework_tracker.build_ai_framework_decisions(inputs)
    stored_count = ai_framework_tracker.store_ai_framework_decisions(decisions)

    by_ticker = decisions.set_index("ticker")
    assert stored_count == 3
    assert by_ticker.loc["TSM", "decision_score"] > by_ticker.loc["MSFT", "decision_score"]
    assert by_ticker.loc["CASH", "suggested_weight"] > by_ticker.loc["CASH", "target_weight"]

    with duckdb.connect(str(db_path)) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM ai_framework_decisions").fetchone()[0]
    assert row_count == 3


def _patch_db(monkeypatch, db_path: Path) -> None:
    monkeypatch.setattr(ai_framework, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(
        ai_framework,
        "initialize_database",
        lambda: initialize_database(db_path),
    )
    monkeypatch.setattr(ai_framework_tracker, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(
        ai_framework_tracker,
        "initialize_database",
        lambda: initialize_database(db_path),
    )
