import argparse
from pathlib import Path

from quant_learn.analytics.evidence import (
    build_decision_memo,
    build_evidence_cards,
    build_research_stance,
    store_evidence_cards,
    store_research_stance,
)
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build V1.0 evidence cards, research stance, and decision memo.",
    )
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--memo", default="reports/decision_memo.md")
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

    memo_path = build_decision_memo(Path(args.memo))

    print(f"Upserted {evidence_count} evidence_cards rows.")
    print(f"Upserted {stance_count} research_stance rows.")
    print(f"Exported {evidence_export}.")
    print(f"Exported {stance_export}.")
    print(f"Wrote {memo_path}.")


if __name__ == "__main__":
    main()
