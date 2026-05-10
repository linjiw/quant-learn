import argparse
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build V1.0 evidence cards, research stance, and decision memo.",
    )
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--memo", default="reports/decision_memo.md")
    parser.add_argument("--audit-report", default="reports/stance_audit_report.md")
    args = parser.parse_args()

    ensure_directories()
    evidence_cards = build_evidence_cards(as_of_date=args.as_of_date)
    evidence_count = store_evidence_cards(evidence_cards)
    evidence_export = EXPORT_DIR / "evidence_cards.csv"
    evidence_cards.to_csv(evidence_export, index=False)

    research_stance = build_research_stance(as_of_date=args.as_of_date)
    stance_count = store_research_stance(research_stance)
    stance_export = EXPORT_DIR / "research_stance.csv"
    research_stance.to_csv(stance_export, index=False)

    components, caps, conflicts = build_stance_audit_tables(as_of_date=args.as_of_date)
    component_count, cap_count, conflict_count = store_stance_audit_tables(
        components,
        caps,
        conflicts,
    )
    components.to_csv(EXPORT_DIR / "stance_components.csv", index=False)
    caps.to_csv(EXPORT_DIR / "stance_confidence_caps.csv", index=False)
    conflicts.to_csv(EXPORT_DIR / "stance_conflicts.csv", index=False)

    memo_path = build_decision_memo(Path(args.memo))
    audit_path = build_stance_audit_report(Path(args.audit_report))

    print(f"Upserted {evidence_count} evidence_cards rows.")
    print(f"Upserted {stance_count} research_stance rows.")
    print(f"Upserted {component_count} stance_components rows.")
    print(f"Upserted {cap_count} stance_confidence_caps rows.")
    print(f"Upserted {conflict_count} stance_conflicts rows.")
    print(f"Exported {evidence_export}.")
    print(f"Exported {stance_export}.")
    print(f"Wrote {memo_path}.")
    print(f"Wrote {audit_path}.")


if __name__ == "__main__":
    main()
