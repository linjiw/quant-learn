import sys
from pathlib import Path

import pytest

from scripts import build_evidence


def test_build_evidence_failure_records_failed_pipeline_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_rows = []

    def raise_build_error(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("fixture build failure")

    def fake_record_pipeline_run(**kwargs):
        run_rows.append(kwargs)
        return "snapshot_fixture"

    monkeypatch.setattr(build_evidence, "ensure_directories", lambda: None)
    monkeypatch.setattr(build_evidence, "archive_research_outputs", lambda run_id: None)
    monkeypatch.setattr(build_evidence, "build_evidence_cards", raise_build_error)
    monkeypatch.setattr(build_evidence, "build_freshness_snapshot", lambda: [])
    monkeypatch.setattr(build_evidence, "record_pipeline_run", fake_record_pipeline_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_evidence",
            "--run-id",
            "failure_run",
            "--memo",
            str(tmp_path / "decision_memo.md"),
            "--audit-report",
            str(tmp_path / "stance_audit_report.md"),
        ],
    )

    with pytest.raises(RuntimeError, match="fixture build failure"):
        build_evidence.main()

    assert len(run_rows) == 1
    assert run_rows[0]["run_id"] == "failure_run"
    assert run_rows[0]["status"] == "failed"
    assert run_rows[0]["error_message"] == "fixture build failure"
    assert not (tmp_path / "decision_memo.md").exists()
