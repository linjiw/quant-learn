"""Time helpers."""

from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Return a timezone-normalized naive UTC datetime for DuckDB timestamps."""

    return datetime.now(timezone.utc).replace(tzinfo=None)
