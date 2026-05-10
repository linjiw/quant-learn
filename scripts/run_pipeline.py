import argparse
import subprocess
import sys

from quant_learn.analytics.auditability import (
    UPSTREAM_FRESHNESS_TABLES,
    build_freshness_snapshot,
    generate_run_id,
    record_pipeline_run,
    stale_tables,
)
from quant_learn.config import ensure_directories
from quant_learn.time import utc_now_naive

PIPELINE_STEPS = [
    ("fundamentals", [["scripts.build_fundamentals"]]),
    ("segments", [["scripts.build_segment_features"], ["scripts.build_segment_dashboard"]]),
    ("factor", [["scripts.build_factor_model"]]),
    (
        "events",
        [
            ["scripts.build_event_returns", "--benchmarks", "QQQ", "SOXX", "SMH"],
            ["scripts.build_event_reviews"],
            ["scripts.build_event_data_quality_report"],
        ],
    ),
    ("valuation", [["scripts.build_valuation"]]),
    ("evidence", [["scripts.build_evidence", "--run-id", "{run_id}"]]),
    ("weekly_digest", [["scripts.build_weekly_digest"]]),
]

FINAL_RECORD_STEP = "weekly_digest"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the research pipeline sequentially.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the default full analytics pipeline.",
    )
    parser.add_argument("--from-step", default="fundamentals")
    parser.add_argument("--to-step", default="weekly_digest")
    parser.add_argument("--force-stale", action="store_true")
    parser.add_argument("--max-staleness-days", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ensure_directories()
    run_id = generate_run_id("pipeline")
    started_at = utc_now_naive()
    freshness = build_freshness_snapshot()
    _print_upstream_freshness_warnings(freshness, args.max_staleness_days)

    selected = _selected_steps(args.from_step, args.to_step)
    skipped_upstream = _skipped_upstream_steps(args.from_step)
    if skipped_upstream and not args.force_stale:
        stale = stale_tables(freshness, args.max_staleness_days)
        if stale:
            _record_failure(
                run_id,
                started_at,
                args,
                freshness,
                "stale upstream data; rerun upstream steps or pass --force-stale",
            )
            tables = ", ".join(f"{row['table']}({row['staleness_days']})" for row in stale)
            raise SystemExit(f"Stale upstream data detected: {tables}")

    try:
        recorded_final = False
        for step_name, commands in selected:
            print(f"== {step_name} ==")
            for command in commands:
                resolved_command = [
                    run_id if part == "{run_id}" else part for part in command
                ]
                full_command = [sys.executable, "-m", *resolved_command]
                print(" ".join(full_command))
                if (
                    step_name == FINAL_RECORD_STEP
                    and not args.dry_run
                    and not recorded_final
                ):
                    _record_success(run_id, started_at, args, build_freshness_snapshot())
                    recorded_final = True
                if not args.dry_run:
                    subprocess.run(full_command, check=True)
        if not recorded_final:
            _record_success(run_id, started_at, args, build_freshness_snapshot())
    except Exception as exc:
        _record_failure(run_id, started_at, args, build_freshness_snapshot(), str(exc))
        raise

    print(f"pipeline_run_id: {run_id}")


def _selected_steps(from_step: str, to_step: str):
    names = [name for name, _commands in PIPELINE_STEPS]
    if from_step not in names or to_step not in names:
        raise SystemExit(f"Unknown step. Valid steps: {', '.join(names)}")
    start = names.index(from_step)
    end = names.index(to_step)
    if start > end:
        raise SystemExit("--from-step must be before or equal to --to-step")
    return PIPELINE_STEPS[start : end + 1]


def _skipped_upstream_steps(from_step: str) -> list[str]:
    names = [name for name, _commands in PIPELINE_STEPS]
    return names[: names.index(from_step)]


def _record_failure(run_id: str, started_at, args, freshness, error_message: str) -> None:
    record_pipeline_run(
        run_id=run_id,
        started_at=started_at,
        completed_at=utc_now_naive(),
        mode="full" if args.full else "partial",
        from_step=args.from_step,
        to_step=args.to_step,
        force_stale=args.force_stale,
        status="failed",
        freshness_snapshot=freshness,
        error_message=error_message,
    )


def _record_success(run_id: str, started_at, args, freshness) -> None:
    record_pipeline_run(
        run_id=run_id,
        started_at=started_at,
        completed_at=utc_now_naive(),
        mode="full" if args.full else "partial",
        from_step=args.from_step,
        to_step=args.to_step,
        force_stale=args.force_stale,
        status="dry_run" if args.dry_run else "success",
        freshness_snapshot=freshness,
    )


def _print_upstream_freshness_warnings(
    freshness: list[dict],
    max_staleness_days: int,
) -> None:
    upstream = [
        row
        for row in freshness
        if row.get("table") in UPSTREAM_FRESHNESS_TABLES
        and (
            row.get("row_count") == 0
            or row.get("staleness_days") is None
            or row.get("staleness_days") > max_staleness_days
        )
    ]
    if not upstream:
        return
    tables = ", ".join(
        f"{row['table']}({row.get('staleness_days', 'unknown')})" for row in upstream
    )
    print(f"WARNING: upstream freshness may be stale: {tables}", file=sys.stderr)


if __name__ == "__main__":
    main()
