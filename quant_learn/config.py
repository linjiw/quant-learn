"""Project configuration and ticker universe."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DUCKDB_DIR = DATA_DIR / "duckdb"
EXPORT_DIR = DATA_DIR / "exports"
MANUAL_DIR = DATA_DIR / "manual"
DEFAULT_DB_PATH = DUCKDB_DIR / "quant_learn.duckdb"

CORE_TICKERS: list[str] = ["GOOGL", "NVDA", "AMD", "TSM"]
BENCHMARK_TICKERS: list[str] = ["QQQ", "SOXX", "SMH", "SPY", "^TNX", "TWD=X"]
DEFAULT_PRICE_TICKERS: list[str] = CORE_TICKERS + BENCHMARK_TICKERS

SEC_CIKS: dict[str, str] = {
    "GOOGL": "0001652044",
    "NVDA": "0001045810",
    "AMD": "0000002488",
    "TSM": "0001046179",
}

HYPERSCALER_TICKERS: list[str] = ["GOOGL", "MSFT", "AMZN", "META"]

TSMC_MONTHLY_REVENUE_URL = "https://investor.tsmc.com/english/monthly-revenue/{year}"

SELECTED_SEC_CONCEPTS = {
    "us-gaap": {
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "GrossProfit",
        "OperatingIncomeLoss",
        "NetIncomeLoss",
        "EarningsPerShareDiluted",
        "NetCashProvidedByUsedInOperatingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "Assets",
        "Liabilities",
        "StockholdersEquity",
        "CashAndCashEquivalentsAtCarryingValue",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
        "CommonStocksIncludingAdditionalPaidInCapital",
        "PaymentsForRepurchaseOfCommonStock",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    },
    "ifrs-full": {
        "Revenue",
        "CostOfSales",
        "GrossProfit",
        "ProfitLoss",
        "ProfitLossFromOperatingActivities",
        "BasicEarningsLossPerShare",
        "DilutedEarningsLossPerShare",
        "CashFlowsFromUsedInOperatingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "Assets",
        "Liabilities",
        "Equity",
        "CashAndCashEquivalents",
    },
}


def ensure_directories() -> None:
    """Create project data directories."""

    for path in (DATA_DIR, DUCKDB_DIR, EXPORT_DIR, MANUAL_DIR):
        path.mkdir(parents=True, exist_ok=True)
