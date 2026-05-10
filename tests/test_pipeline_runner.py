import sys

import pandas as pd

from quant_learn.analytics.weekly_digest import _pipeline_section
from scripts import run_pipeline


def test_pipeline_run_id_is_passed_to_evidence_and_recorded_before_digest(
    monkeypatch,
) -> None:
    calls = []
    run_rows = []
    freshness = [
        {
            "table": "prices",
            "row_count": 1,
            "max_date": "2026-05-01",
            "max_available_date": None,
            "max_ingested_at": "2026-05-01",
            "staleness_days": 0,
        },
        {
            "table": "market_factor_inputs",
            "row_count": 1,
            "max_date": "2026-05-01",
            "max_available_date": None,
            "max_ingested_at": "2026-05-01",
            "staleness_days": 0,
        },
    ]

    def fake_record_pipeline_run(**kwargs):
        calls.append(("record", kwargs["run_id"], kwargs["status"]))
        run_rows.append(kwargs)
        return "snapshot_fixture"

    def fake_subprocess_run(command, check):
        del check
        module = command[command.index("-m") + 1]
        if module == "scripts.build_evidence":
            assert "--run-id" in command
            assert command[command.index("--run-id") + 1] == "pipeline_fixture"
        if module == "scripts.build_weekly_digest":
            assert calls and calls[-1] == ("record", "pipeline_fixture", "success")
        calls.append(("subprocess", module))

    monkeypatch.setattr(run_pipeline, "generate_run_id", lambda prefix: f"{prefix}_fixture")
    monkeypatch.setattr(run_pipeline, "build_freshness_snapshot", lambda: freshness)
    monkeypatch.setattr(run_pipeline, "record_pipeline_run", fake_record_pipeline_run)
    monkeypatch.setattr(run_pipeline.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(run_pipeline, "ensure_directories", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline",
            "--from-step",
            "evidence",
            "--to-step",
            "weekly_digest",
            "--force-stale",
        ],
    )

    run_pipeline.main()

    assert run_rows[0]["run_id"] == "pipeline_fixture"
    assert run_rows[0]["from_step"] == "evidence"
    assert run_rows[0]["to_step"] == "weekly_digest"
    assert calls == [
        ("subprocess", "scripts.build_evidence"),
        ("record", "pipeline_fixture", "success"),
        ("subprocess", "scripts.build_weekly_digest"),
    ]


def test_stale_partial_pipeline_blocks_without_force(monkeypatch) -> None:
    run_rows = []
    freshness = [
        {
            "table": "prices",
            "row_count": 1,
            "max_date": "2026-05-01",
            "max_available_date": None,
            "max_ingested_at": "2026-05-01",
            "staleness_days": 10,
        }
    ]

    def fake_record_pipeline_run(**kwargs):
        run_rows.append(kwargs)
        return "snapshot_fixture"

    monkeypatch.setattr(run_pipeline, "generate_run_id", lambda prefix: f"{prefix}_fixture")
    monkeypatch.setattr(run_pipeline, "build_freshness_snapshot", lambda: freshness)
    monkeypatch.setattr(run_pipeline, "record_pipeline_run", fake_record_pipeline_run)
    monkeypatch.setattr(run_pipeline, "ensure_directories", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline",
            "--from-step",
            "evidence",
            "--to-step",
            "weekly_digest",
            "--max-staleness-days",
            "3",
        ],
    )

    try:
        run_pipeline.main()
    except SystemExit as exc:
        assert "Stale upstream data detected" in str(exc)
    else:
        raise AssertionError("stale partial pipeline should have exited")

    assert run_rows[0]["run_id"] == "pipeline_fixture"
    assert run_rows[0]["status"] == "failed"
    assert "stale upstream data" in run_rows[0]["error_message"]


def test_weekly_digest_pipeline_section_marks_force_stale_runs() -> None:
    rows = pd.DataFrame(
        [
            {
                "run_id": "pipeline_fixture",
                "status": "success",
                "from_step": "evidence",
                "to_step": "weekly_digest",
                "data_snapshot_hash": "snapshot_fixture",
                "force_stale": True,
            }
        ]
    )

    section = "\n".join(_pipeline_section(rows))

    assert "pipeline_fixture" in section
    assert "force-stale" in section
