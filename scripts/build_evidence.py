import argparse
import shutil
from pathlib import Path

from quant_learn.analytics.auditability import (
    archive_research_outputs,
    build_freshness_snapshot,
    generate_run_id,
    record_pipeline_run,
)
from quant_learn.analytics.evidence import (
    build_decision_memo,
    build_evidence_cards,
    build_research_stance,
    build_stance_audit_report,
    build_stance_audit_tables,
    store_evidence_cards,
    store_research_stance,
    store_stance_audit_tables,
)
from quant_learn.config import EXPORT_DIR, ensure_directories
from quant_learn.time import utc_now_naive


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build evidence cards, research stance, and decision memo.",
    )
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--memo", default="reports/decision_memo.md")
    parser.add_argument("--audit-report", default="reports/stance_audit_report.md")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    ensure_directories()
    run_id = args.run_id or generate_run_id("evidence")
    started_at = utc_now_naive()
    try:
        archive_research_outputs(run_id)
        evidence_cards = build_evidence_cards(as_of_date=args.as_of_date, run_id=run_id)
        evidence_count = store_evidence_cards(evidence_cards)
        evidence_export = EXPORT_DIR / "evidence_cards.csv"
        evidence_cards.to_csv(evidence_export, index=False)

        research_stance = build_research_stance(as_of_date=args.as_of_date, run_id=run_id)
        stance_count = store_research_stance(research_stance)
        stance_export = EXPORT_DIR / "research_stance.csv"
        research_stance.to_csv(stance_export, index=False)

        components, caps, conflicts = build_stance_audit_tables(
            as_of_date=args.as_of_date,
            run_id=run_id,
        )
        component_count, cap_count, conflict_count = store_stance_audit_tables(
            components,
            caps,
            conflicts,
        )
        components.to_csv(EXPORT_DIR / "stance_components.csv", index=False)
        caps.to_csv(EXPORT_DIR / "stance_confidence_caps.csv", index=False)
        conflicts.to_csv(EXPORT_DIR / "stance_conflicts.csv", index=False)

        freshness = build_freshness_snapshot()
        snapshot_hash = record_pipeline_run(
            run_id=run_id,
            started_at=started_at,
            completed_at=utc_now_naive(),
            mode="evidence",
            from_step="evidence",
            to_step="evidence",
            force_stale=False,
            status="success",
            freshness_snapshot=freshness,
        )

        memo_path = build_decision_memo(
            Path(args.memo),
            run_id=run_id,
            data_snapshot_hash=snapshot_hash,
        )
        audit_path = build_stance_audit_report(Path(args.audit_report))
        history_dir = Path(args.memo).parent / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_memo = history_dir / f"decision_memo_{run_id}.md"
        shutil.copyfile(memo_path, history_memo)
    except Exception as exc:
        record_pipeline_run(
            run_id=run_id,
            started_at=started_at,
            completed_at=utc_now_naive(),
            mode="evidence",
            from_step="evidence",
            to_step="evidence",
            force_stale=False,
            status="failed",
            freshness_snapshot=build_freshness_snapshot(),
            error_message=str(exc),
        )
        raise

    print(f"run_id: {run_id}")
    print(f"data_snapshot_hash: {snapshot_hash}")
    print(f"Upserted {evidence_count} evidence_cards rows.")
    print(f"Upserted {stance_count} research_stance rows.")
    print(f"Upserted {component_count} stance_components rows.")
    print(f"Upserted {cap_count} stance_confidence_caps rows.")
    print(f"Upserted {conflict_count} stance_conflicts rows.")
    print(f"Exported {evidence_export}.")
    print(f"Exported {stance_export}.")
    print(f"Wrote {memo_path}.")
    print(f"Wrote {history_memo}.")
    print(f"Wrote {audit_path}.")


if __name__ == "__main__":
    main()
