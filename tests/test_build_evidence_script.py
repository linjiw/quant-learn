import sys
from pathlib import Path

import pandas as pd
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


def test_build_evidence_failure_after_card_build_does_not_store_or_update_memo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_rows = []
    store_called = False
    memo_path = tmp_path / "decision_memo.md"
    memo_path.write_text("previous good memo", encoding="utf-8")

    def raise_stance_error(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("fixture stance failure")

    def fail_if_store_called(*args, **kwargs):
        nonlocal store_called
        del args, kwargs
        store_called = True
        raise AssertionError("store_research_outputs should not be called")

    def fake_record_pipeline_run(**kwargs):
        run_rows.append(kwargs)
        return "snapshot_fixture"

    monkeypatch.setattr(build_evidence, "ensure_directories", lambda: None)
    monkeypatch.setattr(build_evidence, "archive_research_outputs", lambda run_id: None)
    monkeypatch.setattr(
        build_evidence,
        "build_evidence_cards",
        lambda **kwargs: pd.DataFrame({"run_id": [kwargs["run_id"]]}),
    )
    monkeypatch.setattr(build_evidence, "build_research_stance", raise_stance_error)
    monkeypatch.setattr(build_evidence, "store_research_outputs", fail_if_store_called)
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
            str(memo_path),
            "--audit-report",
            str(tmp_path / "stance_audit_report.md"),
        ],
    )

    with pytest.raises(RuntimeError, match="fixture stance failure"):
        build_evidence.main()

    assert store_called is False
    assert memo_path.read_text(encoding="utf-8") == "previous good memo"
    assert run_rows[0]["status"] == "failed"
