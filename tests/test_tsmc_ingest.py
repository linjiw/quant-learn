import pandas as pd

from quant_learn.ingest.tsmc import _parse_revenue_table


def test_parse_tsmc_revenue_filters_future_blank_months() -> None:
    table = pd.DataFrame(
        [
            ["Jan.", 401255.0, "36.8%"],
            ["May", None, None],
            ["Sept.", None, None],
            ["Total", 401255.0, "36.8%"],
        ],
        columns=pd.MultiIndex.from_tuples(
            [
                ("Month", "Month"),
                ("Consolidated", "Net Revenue"),
                ("Consolidated", "YoY Change"),
            ]
        ),
    )

    parsed = _parse_revenue_table(table, 2026, "https://example.com")

    assert list(parsed["period"]) == [pd.Timestamp("2026-01-01").date()]
    assert parsed.iloc[0]["revenue_ntd_million"] == 401255.0
    assert parsed.iloc[0]["yoy_pct"] == 36.8
