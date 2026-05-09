import argparse

from quant_learn.analytics.event_reviews import build_event_reviews, store_event_reviews
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Build rule-based event review summaries.")
    parser.add_argument("--export", default="event_reviews.csv")
    args = parser.parse_args()

    ensure_directories()
    event_reviews = build_event_reviews()
    count = store_event_reviews(event_reviews)
    export_path = EXPORT_DIR / args.export
    event_reviews.to_csv(export_path, index=False)
    print(f"Upserted {count} event review rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
