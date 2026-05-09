import argparse

from quant_learn.analytics.segments import build_segment_features, store_segment_features
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Build segment driver features.")
    parser.add_argument("--export", default="segment_features.csv")
    args = parser.parse_args()

    ensure_directories()
    segment_features = build_segment_features()
    count = store_segment_features(segment_features)
    export_path = EXPORT_DIR / args.export
    segment_features.to_csv(export_path, index=False)
    print(f"Upserted {count} segment feature rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
