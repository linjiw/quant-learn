from quant_learn.analytics.fundamentals import (
    build_fundamentals_quarterly,
    store_fundamentals_quarterly,
)
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    ensure_directories()
    fundamentals = build_fundamentals_quarterly()
    count = store_fundamentals_quarterly(fundamentals)
    export_path = EXPORT_DIR / "fundamentals_quarterly.csv"
    fundamentals.to_csv(export_path, index=False)
    print(f"Upserted {count} fundamentals_quarterly rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
