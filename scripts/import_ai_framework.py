import argparse
from pathlib import Path

from quant_learn.config import MANUAL_DIR
from quant_learn.ingest.ai_framework import import_ai_framework


def main() -> None:
    parser = argparse.ArgumentParser(description="Import AI framework tracker CSVs.")
    parser.add_argument(
        "--indicators",
        type=Path,
        default=MANUAL_DIR / "ai_framework_indicators.csv",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=MANUAL_DIR / "ai_framework_predictions.csv",
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=MANUAL_DIR / "ai_framework_scenarios.csv",
    )
    parser.add_argument(
        "--holdings",
        type=Path,
        default=MANUAL_DIR / "ai_framework_holdings.csv",
    )
    parser.add_argument(
        "--control-scores",
        type=Path,
        default=MANUAL_DIR / "ai_control_right_scores.csv",
    )
    args = parser.parse_args()

    counts = import_ai_framework(
        indicators_path=args.indicators,
        predictions_path=args.predictions,
        scenarios_path=args.scenarios,
        holdings_path=args.holdings,
        control_scores_path=args.control_scores,
    )
    for name, count in counts.items():
        print(f"Upserted {count} AI framework {name} rows.")


if __name__ == "__main__":
    main()
