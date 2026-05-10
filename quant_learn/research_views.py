"""Manual research thesis views loaded outside code configuration."""

from dataclasses import dataclass

import pandas as pd

from quant_learn.config import CORE_TICKERS, MANUAL_DIR


@dataclass(frozen=True)
class ResearchView:
    ticker: str
    thesis_text: str
    falsifiers: list[str]
    next_catalysts: list[str]
    updated_at: str
    reviewer_notes: str


def load_research_views(path=None) -> dict[str, ResearchView]:
    """Load manual thesis/falsifier/catalyst views from CSV."""

    csv_path = path or MANUAL_DIR / "research_views.csv"
    if not csv_path.exists():
        return {}

    frame = pd.read_csv(csv_path)
    views = {}
    for _, row in frame.iterrows():
        ticker = str(row["ticker"])
        views[ticker] = ResearchView(
            ticker=ticker,
            thesis_text=str(row["thesis_text"]),
            falsifiers=_split_list(row.get("falsifiers")),
            next_catalysts=_split_list(row.get("next_catalysts")),
            updated_at=str(row.get("updated_at") or ""),
            reviewer_notes=str(row.get("reviewer_notes") or ""),
        )
    return views


def validate_research_views(path=None) -> None:
    """Validate that every core ticker has a manual research view."""

    views = load_research_views(path)
    missing = set(CORE_TICKERS) - set(views)
    if missing:
        raise ValueError(f"Missing research views for: {sorted(missing)}")


def _split_list(value) -> list[str]:
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]
