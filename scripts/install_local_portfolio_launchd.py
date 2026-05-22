"""Install a macOS launchd job for the local portfolio refresh."""

import argparse
import plistlib
import shutil
import subprocess
from pathlib import Path

from quant_learn.config import PROJECT_ROOT

LABEL = "com.linji.quant-learn.portfolio"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = PROJECT_ROOT / "logs" / "local_portfolio_refresh.log"


def main() -> None:
    parser = argparse.ArgumentParser(description="Install daily local portfolio launchd refresh.")
    parser.add_argument("--hour", type=int, default=6)
    parser.add_argument("--minute", type=int, default=45)
    parser.add_argument("--load", action="store_true", help="Load/reload the launchd job now.")
    parser.add_argument("--run-at-load", action="store_true")
    args = parser.parse_args()

    if not (0 <= args.hour <= 23 and 0 <= args.minute <= 59):
        raise ValueError("Hour must be 0-23 and minute must be 0-59.")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    uv_path = shutil.which("uv")
    if not uv_path:
        raise SystemExit("uv was not found on PATH; install uv before scheduling the refresh.")
    command = (
        f"cd {shell_quote(PROJECT_ROOT)} && "
        f"{shell_quote(Path(uv_path))} run python -m scripts.update_local_portfolio "
        f">> {shell_quote(LOG_PATH)} 2>&1"
    )
    payload = {
        "Label": LABEL,
        "ProgramArguments": ["/bin/zsh", "-lc", command],
        "StartCalendarInterval": {"Hour": args.hour, "Minute": args.minute},
        "RunAtLoad": bool(args.run_at_load),
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
        "WorkingDirectory": str(PROJECT_ROOT),
    }
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=True)
    print(f"Wrote {PLIST_PATH}")

    if args.load:
        uid = subprocess.check_output(["id", "-u"], text=True).strip()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)], check=False)
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)], check=True)
        subprocess.run(["launchctl", "enable", f"gui/{uid}/{LABEL}"], check=False)
        print(f"Loaded {LABEL} for daily {args.hour:02d}:{args.minute:02d} local time")


def shell_quote(path: Path) -> str:
    return "'" + str(path).replace("'", "'\\''") + "'"


if __name__ == "__main__":
    main()
