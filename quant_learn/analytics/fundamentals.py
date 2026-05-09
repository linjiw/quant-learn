"""Build normalized quarterly fundamental snapshots from SEC company facts."""

import pandas as pd

from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

METRIC_CONCEPTS = {
    "revenue": [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("ifrs-full", "Revenue"),
    ],
    "gross_profit": [
        ("us-gaap", "GrossProfit"),
        ("ifrs-full", "GrossProfit"),
    ],
    "operating_income": [
        ("us-gaap", "OperatingIncomeLoss"),
        ("ifrs-full", "ProfitLossFromOperatingActivities"),
    ],
    "net_income": [
        ("us-gaap", "NetIncomeLoss"),
        ("ifrs-full", "ProfitLoss"),
    ],
    "eps": [
        ("us-gaap", "EarningsPerShareDiluted"),
        ("ifrs-full", "DilutedEarningsLossPerShare"),
        ("ifrs-full", "BasicEarningsLossPerShare"),
    ],
    "operating_cash_flow": [
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"),
    ],
    "capex": [
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
        ("us-gaap", "PaymentsToAcquireProductiveAssets"),
        ("ifrs-full", "PaymentsToAcquirePropertyPlantAndEquipment"),
    ],
    "cash": [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("ifrs-full", "CashAndCashEquivalents"),
    ],
    "shares_outstanding": [
        ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),
        ("us-gaap", "EntityCommonStockSharesOutstanding"),
    ],
    "buyback": [
        ("us-gaap", "PaymentsForRepurchaseOfCommonStock"),
    ],
    "dividend": [
        ("us-gaap", "PaymentsOfDividendsCommonStock"),
        ("us-gaap", "PaymentsOfDividends"),
        ("ifrs-full", "DividendsPaid"),
    ],
    "debt_current": [
        ("us-gaap", "LongTermDebtCurrent"),
        ("us-gaap", "DebtCurrent"),
    ],
    "debt_noncurrent": [
        ("us-gaap", "LongTermDebtNoncurrent"),
        ("us-gaap", "LongTermDebt"),
    ],
}

FUNDAMENTAL_COLUMNS = [
    "ticker",
    "fiscal_year",
    "fiscal_quarter",
    "period_end",
    "revenue",
    "gross_profit",
    "gross_margin",
    "operating_income",
    "operating_margin",
    "net_income",
    "eps",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "cash",
    "debt",
    "shares_outstanding",
    "buyback",
    "dividend",
    "source_accession_number",
    "source_filed_date",
    "ingested_at",
]


def build_fundamentals_quarterly() -> pd.DataFrame:
    """Build a compact fundamental table from selected SEC facts."""

    initialize_database()
    concept_pairs = [
        concept_pair
        for concept_pairs_for_metric in METRIC_CONCEPTS.values()
        for concept_pair in concept_pairs_for_metric
    ]
    concepts = sorted({concept for _, concept in concept_pairs})

    with connect() as conn:
        facts = conn.execute(
            """
            SELECT ticker, taxonomy, concept, unit, fiscal_year, fiscal_period,
                   form, filed_date, end_date, accession_number, value
            FROM sec_facts
            WHERE ticker IN (SELECT unnest(?))
              AND concept IN (SELECT unnest(?))
              AND fiscal_year IS NOT NULL
              AND fiscal_period IS NOT NULL
              AND end_date IS NOT NULL
              AND value IS NOT NULL
            """,
            [CORE_TICKERS, concepts],
        ).fetchdf()

    if facts.empty:
        return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

    facts["filed_date"] = pd.to_datetime(facts["filed_date"])
    facts["end_date"] = pd.to_datetime(facts["end_date"])
    facts["fiscal_year"] = facts["fiscal_year"].astype(int)
    facts = facts[facts["fiscal_period"].isin(["Q1", "Q2", "Q3", "Q4", "FY"])]
    facts = facts[facts["form"].isin(["10-Q", "10-K", "20-F", "6-K", "40-F"])]

    metric_frames = []
    for metric, concepts_for_metric in METRIC_CONCEPTS.items():
        metric_frame = _metric_frame(facts, metric, concepts_for_metric)
        if not metric_frame.empty:
            metric_frames.append(metric_frame)

    if not metric_frames:
        return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

    fundamentals = metric_frames[0]
    for metric_frame in metric_frames[1:]:
        fundamentals = fundamentals.merge(
            metric_frame,
            on=["ticker", "fiscal_year", "fiscal_quarter", "period_end"],
            how="outer",
        )

    for column in (
        "revenue",
        "gross_profit",
        "operating_income",
        "operating_cash_flow",
        "capex",
        "debt_current",
        "debt_noncurrent",
    ):
        if column not in fundamentals.columns:
            fundamentals[column] = pd.NA

    fundamentals["debt"] = fundamentals.get("debt_current", 0).fillna(0) + fundamentals.get(
        "debt_noncurrent", 0
    ).fillna(0)
    fundamentals = fundamentals.drop(columns=["debt_current", "debt_noncurrent"], errors="ignore")
    fundamentals["gross_margin"] = fundamentals["gross_profit"] / fundamentals["revenue"]
    fundamentals["operating_margin"] = fundamentals["operating_income"] / fundamentals["revenue"]
    fundamentals["free_cash_flow"] = fundamentals["operating_cash_flow"] - fundamentals["capex"]
    fundamentals["source_accession_number"] = None
    fundamentals["source_filed_date"] = pd.NaT
    fundamentals["ingested_at"] = utc_now_naive()

    for column in FUNDAMENTAL_COLUMNS:
        if column not in fundamentals.columns:
            fundamentals[column] = pd.NA

    fundamentals = fundamentals[FUNDAMENTAL_COLUMNS]
    fundamentals["period_end"] = pd.to_datetime(fundamentals["period_end"]).dt.date
    fundamentals["source_filed_date"] = pd.to_datetime(
        fundamentals["source_filed_date"], errors="coerce"
    ).dt.date
    return fundamentals.sort_values(["ticker", "period_end", "fiscal_quarter"])


def store_fundamentals_quarterly(fundamentals: pd.DataFrame) -> int:
    """Store normalized fundamental snapshots."""

    if fundamentals.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(
            conn,
            fundamentals,
            "fundamentals_quarterly",
            ["ticker", "fiscal_year", "fiscal_quarter", "period_end"],
        )


def _metric_frame(
    facts: pd.DataFrame,
    metric: str,
    concepts_for_metric: list[tuple[str, str]],
) -> pd.DataFrame:
    concept_priority = {
        concept_pair: priority for priority, concept_pair in enumerate(concepts_for_metric)
    }
    metric_facts = facts.copy()
    metric_facts["concept_pair"] = list(zip(metric_facts["taxonomy"], metric_facts["concept"]))
    metric_facts = metric_facts[metric_facts["concept_pair"].isin(concept_priority)]
    if metric_facts.empty:
        return pd.DataFrame()

    metric_facts["priority"] = metric_facts["concept_pair"].map(concept_priority)
    metric_facts["fiscal_quarter"] = metric_facts["fiscal_period"]
    metric_facts["period_end"] = metric_facts["end_date"]
    metric_facts["filed_date_sort"] = metric_facts["filed_date"].fillna(pd.Timestamp.min)
    metric_facts = metric_facts.sort_values(
        [
            "ticker",
            "fiscal_year",
            "fiscal_quarter",
            "period_end",
            "priority",
            "filed_date_sort",
        ],
        ascending=[True, True, True, True, True, False],
    )
    latest = metric_facts.groupby(
        ["ticker", "fiscal_year", "fiscal_quarter", "period_end"],
        dropna=False,
        as_index=False,
    ).head(1)
    return latest[
        ["ticker", "fiscal_year", "fiscal_quarter", "period_end", "value"]
    ].rename(columns={"value": metric})
