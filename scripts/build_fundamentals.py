from quant_learn.analytics.fundamentals import (
    build_cash_flow_features,
    build_fundamentals_quarterly,
    build_fundamentals_quarterly_normalized,
    legacy_from_normalized,
    store_cash_flow_features,
    store_fundamentals_quarterly,
    store_fundamentals_quarterly_normalized,
)
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    ensure_directories()
    normalized = build_fundamentals_quarterly_normalized()
    normalized_count = store_fundamentals_quarterly_normalized(normalized)
    normalized_export_path = EXPORT_DIR / "fundamentals_quarterly_normalized.csv"
    normalized.to_csv(normalized_export_path, index=False)

    fundamentals = legacy_from_normalized(normalized)
    if fundamentals.empty:
        fundamentals = build_fundamentals_quarterly()
    legacy_count = store_fundamentals_quarterly(fundamentals)
    legacy_export_path = EXPORT_DIR / "fundamentals_quarterly.csv"
    fundamentals.to_csv(legacy_export_path, index=False)

    cash_flow_features = build_cash_flow_features()
    cash_flow_count = store_cash_flow_features(cash_flow_features)
    cash_flow_export_path = EXPORT_DIR / "cash_flow_features.csv"
    cash_flow_features.to_csv(cash_flow_export_path, index=False)

    print(f"Upserted {normalized_count} fundamentals_quarterly_normalized rows.")
    print(f"Upserted {legacy_count} fundamentals_quarterly rows.")
    print(f"Upserted {cash_flow_count} cash_flow_features rows.")
    print(f"Exported {normalized_export_path}.")
    print(f"Exported {legacy_export_path}.")
    print(f"Exported {cash_flow_export_path}.")


if __name__ == "__main__":
    main()
