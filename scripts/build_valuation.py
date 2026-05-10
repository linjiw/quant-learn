import argparse

from quant_learn.analytics.valuation import (
    build_valuation_features,
    build_valuation_metrics,
    store_valuation_features,
    store_valuation_metrics,
)
from quant_learn.config import CORE_TICKERS, EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build PIT trailing valuation metrics and features.",
    )
    parser.add_argument("--tickers", nargs="*", default=CORE_TICKERS)
    args = parser.parse_args()

    ensure_directories()
    metrics = build_valuation_metrics(args.tickers)
    metric_count = store_valuation_metrics(metrics)
    metric_export = EXPORT_DIR / "valuation_metrics.csv"
    metrics.to_csv(metric_export, index=False)

    features = build_valuation_features(args.tickers)
    feature_count = store_valuation_features(features)
    feature_export = EXPORT_DIR / "valuation_features.csv"
    features.to_csv(feature_export, index=False)

    print(f"Upserted {metric_count} valuation_metrics rows.")
    print(f"Upserted {feature_count} valuation_features rows.")
    print(f"Exported {metric_export}.")
    print(f"Exported {feature_export}.")


if __name__ == "__main__":
    main()
