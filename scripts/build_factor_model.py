import argparse
from pathlib import Path

from quant_learn.analytics.factor_model import (
    build_factor_exposures,
    build_factor_residual_report,
    build_factor_residuals,
    build_market_factor_inputs,
    build_residual_diagnostics,
    store_factor_exposures,
    store_factor_residuals,
    store_market_factor_inputs,
    store_residual_diagnostics,
)
from quant_learn.config import CORE_TICKERS, EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PIT three-factor residual model.")
    parser.add_argument("--tickers", nargs="*", default=CORE_TICKERS)
    parser.add_argument("--window", type=int, default=60)
    parser.add_argument("--min-obs", type=int, default=40)
    parser.add_argument("--tnx-source", default="YAHOO_TNX")
    parser.add_argument("--report", default="reports/factor_residual_report.md")
    args = parser.parse_args()

    ensure_directories()
    factor_inputs = build_market_factor_inputs(tnx_source=args.tnx_source)
    input_count = store_market_factor_inputs(factor_inputs)
    input_export = EXPORT_DIR / "market_factor_inputs.csv"
    factor_inputs.to_csv(input_export, index=False)

    exposures = build_factor_exposures(
        tickers=args.tickers,
        window=args.window,
        min_obs=args.min_obs,
    )
    exposure_count = store_factor_exposures(exposures)
    exposure_export = EXPORT_DIR / "factor_exposures.csv"
    exposures.to_csv(exposure_export, index=False)

    residuals = build_factor_residuals(tickers=args.tickers, window=args.window)
    residual_count = store_factor_residuals(residuals)
    residual_export = EXPORT_DIR / "factor_residuals.csv"
    residuals.to_csv(residual_export, index=False)

    diagnostics = build_residual_diagnostics(tickers=args.tickers, lookback_window=args.window)
    diagnostic_count = store_residual_diagnostics(diagnostics, lookback_window=args.window)
    diagnostic_export = EXPORT_DIR / "residual_diagnostics.csv"
    diagnostics.to_csv(diagnostic_export, index=False)

    report_path = build_factor_residual_report(Path(args.report))

    print(f"Upserted {input_count} market_factor_inputs rows.")
    print(f"Upserted {exposure_count} factor_exposures rows.")
    print(f"Upserted {residual_count} factor_residuals rows.")
    print(f"Upserted {diagnostic_count} residual_diagnostics rows.")
    print(f"Exported {input_export}.")
    print(f"Exported {exposure_export}.")
    print(f"Exported {residual_export}.")
    print(f"Exported {diagnostic_export}.")
    print(f"Wrote {report_path}.")


if __name__ == "__main__":
    main()
