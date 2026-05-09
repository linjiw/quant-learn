"""Build point-in-time quarterly fundamental snapshots from SEC company facts."""

import hashlib
import json
from datetime import timedelta
from typing import Optional

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
    "eps_diluted": [
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

INCOME_METRICS = ["revenue", "gross_profit", "operating_income", "net_income"]
FLOW_METRICS = ["operating_cash_flow", "capex", "buyback", "dividend"]
INSTANT_METRICS = ["cash", "shares_outstanding", "debt_current", "debt_noncurrent"]
QUARTER_ORDER = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

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

NORMALIZED_COLUMNS = [
    "fundamental_id",
    "ticker",
    "fiscal_year",
    "fiscal_quarter",
    "period_start",
    "period_end",
    "available_date",
    "source_accession_number",
    "source_form",
    "filed_date",
    "source_url",
    "revenue",
    "gross_profit",
    "gross_margin",
    "operating_income",
    "operating_margin",
    "net_income",
    "eps_diluted",
    "operating_cash_flow_ytd",
    "capex_ytd",
    "free_cash_flow_ytd",
    "operating_cash_flow_quarterly",
    "capex_quarterly",
    "free_cash_flow_quarterly",
    "cash",
    "debt",
    "shares_outstanding",
    "is_ytd_source",
    "is_quarterly_derived",
    "derivation_method",
    "source_xbrl_tags",
    "source_fact_keys",
    "data_quality_flag",
    "confidence",
    "ingested_at",
]


def legacy_from_normalized(normalized: pd.DataFrame) -> pd.DataFrame:
    """Build the compact legacy fundamentals table from normalized PIT rows."""

    if normalized.empty:
        return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

    legacy = pd.DataFrame(
        {
            "ticker": normalized["ticker"],
            "fiscal_year": normalized["fiscal_year"],
            "fiscal_quarter": normalized["fiscal_quarter"],
            "period_end": normalized["period_end"],
            "revenue": normalized["revenue"],
            "gross_profit": normalized["gross_profit"],
            "gross_margin": normalized["gross_margin"],
            "operating_income": normalized["operating_income"],
            "operating_margin": normalized["operating_margin"],
            "net_income": normalized["net_income"],
            "eps": normalized["eps_diluted"],
            "operating_cash_flow": normalized["operating_cash_flow_quarterly"],
            "capex": normalized["capex_quarterly"],
            "free_cash_flow": normalized["free_cash_flow_quarterly"],
            "cash": normalized["cash"],
            "debt": normalized["debt"],
            "shares_outstanding": normalized["shares_outstanding"],
            "buyback": pd.NA,
            "dividend": pd.NA,
            "source_accession_number": normalized["source_accession_number"],
            "source_filed_date": normalized["filed_date"],
            "ingested_at": normalized["ingested_at"],
        }
    )
    return legacy[FUNDAMENTAL_COLUMNS].sort_values(["ticker", "period_end", "fiscal_quarter"])


def build_fundamentals_quarterly_normalized() -> pd.DataFrame:
    """Build PIT-safe quarterly fundamentals with explicit cash-flow lineage."""

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
            SELECT
                f.ticker,
                f.cik,
                f.taxonomy,
                f.concept,
                f.unit,
                f.fiscal_year,
                f.fiscal_period,
                f.form,
                f.filed_date,
                f.start_date,
                f.end_date,
                f.frame,
                f.accession_number,
                f.value,
                COALESCE(s.source_url, f.source_url) AS source_url,
                s.report_date
            FROM sec_facts f
            LEFT JOIN sec_filings s
                ON f.ticker = s.ticker
               AND f.accession_number = s.accession_number
            WHERE f.ticker IN (SELECT unnest(?))
              AND f.concept IN (SELECT unnest(?))
              AND f.fiscal_year IS NOT NULL
              AND f.fiscal_period IS NOT NULL
              AND f.end_date IS NOT NULL
              AND f.value IS NOT NULL
            """,
            [CORE_TICKERS, concepts],
        ).fetchdf()

    if facts.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)

    prepared = _prepare_facts(facts)
    if prepared.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)

    rows = []
    ingested_at = utc_now_naive()
    for _, filing_facts in prepared.groupby(["ticker", "accession_number"], dropna=False):
        row = _normalized_filing_row(filing_facts, ingested_at)
        if row is not None:
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)

    normalized = pd.DataFrame(rows)
    normalized = _derive_quarterly_income_for_q4(normalized)
    normalized = _derive_quarterly_cash_flow(normalized)
    normalized = _finish_normalized_rows(normalized)
    return normalized[NORMALIZED_COLUMNS].sort_values(["ticker", "period_end", "fiscal_quarter"])


def store_fundamentals_quarterly_normalized(fundamentals: pd.DataFrame) -> int:
    """Store normalized quarterly fundamentals."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM fundamentals_quarterly_normalized")
        if fundamentals.empty:
            return 0
        return upsert_dataframe(
            conn,
            fundamentals,
            "fundamentals_quarterly_normalized",
            ["fundamental_id"],
        )


def build_fundamentals_quarterly() -> pd.DataFrame:
    """Build the legacy compact table from normalized PIT fundamentals."""

    normalized = build_fundamentals_quarterly_normalized()
    return legacy_from_normalized(normalized)


def store_fundamentals_quarterly(fundamentals: pd.DataFrame) -> int:
    """Store legacy normalized fundamental snapshots."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM fundamentals_quarterly")
        if fundamentals.empty:
            return 0
        return upsert_dataframe(
            conn,
            fundamentals,
            "fundamentals_quarterly",
            ["ticker", "fiscal_year", "fiscal_quarter", "period_end"],
        )


def build_cash_flow_features() -> pd.DataFrame:
    """Build cash-flow quality features from normalized fundamentals."""

    initialize_database()
    with connect() as conn:
        fundamentals = conn.execute(
            """
            SELECT *
            FROM fundamentals_quarterly_normalized
            WHERE operating_cash_flow_quarterly IS NOT NULL
               OR capex_quarterly IS NOT NULL
               OR free_cash_flow_quarterly IS NOT NULL
            """
        ).fetchdf()

    if fundamentals.empty:
        return pd.DataFrame()

    fundamentals["period_end"] = pd.to_datetime(fundamentals["period_end"])
    fundamentals["available_date"] = pd.to_datetime(fundamentals["available_date"])
    latest = fundamentals.sort_values("period_end").groupby("ticker", dropna=False).tail(1)
    ingested_at = utc_now_naive()
    rows = []
    for _, row in latest.iterrows():
        rows.extend(_cash_flow_feature_rows(row, ingested_at))
    return pd.DataFrame(rows)


def store_cash_flow_features(features: pd.DataFrame) -> int:
    """Store cash-flow quality features."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM cash_flow_features")
        if features.empty:
            return 0
        return upsert_dataframe(
            conn,
            features,
            "cash_flow_features",
            ["date", "ticker", "feature_name"],
        )


def _prepare_facts(facts: pd.DataFrame) -> pd.DataFrame:
    prepared = facts.copy()
    date_columns = ["filed_date", "start_date", "end_date", "report_date"]
    for column in date_columns:
        prepared[column] = pd.to_datetime(prepared[column], errors="coerce")
    prepared = prepared[prepared["fiscal_period"].isin(["Q1", "Q2", "Q3", "FY"])]
    prepared = prepared[prepared["form"].isin(["10-Q", "10-K", "20-F", "6-K", "40-F"])]
    prepared = prepared[prepared["report_date"].notna()]
    prepared = prepared[prepared["end_date"].dt.date == prepared["report_date"].dt.date]
    prepared["duration_days"] = (prepared["end_date"] - prepared["start_date"]).dt.days
    prepared["concept_pair"] = list(zip(prepared["taxonomy"], prepared["concept"]))
    return prepared


def _normalized_filing_row(filing_facts: pd.DataFrame, ingested_at) -> Optional[dict]:
    filing_facts = filing_facts.sort_values("filed_date")
    first = filing_facts.iloc[-1]
    fiscal_period = str(first["fiscal_period"])
    fiscal_quarter = "Q4" if fiscal_period == "FY" else fiscal_period
    if fiscal_quarter not in QUARTER_ORDER:
        return None

    source_tags: dict[str, str] = {}
    source_keys: dict[str, str] = {}
    row = {
        "ticker": first["ticker"],
        "fiscal_year": int(first["fiscal_year"]),
        "fiscal_quarter": fiscal_quarter,
        "period_start": pd.NaT,
        "period_end": first["end_date"].date(),
        "available_date": first["filed_date"].date(),
        "source_accession_number": first["accession_number"],
        "source_form": first["form"],
        "filed_date": first["filed_date"].date(),
        "source_url": first["source_url"],
        "ingested_at": ingested_at,
    }

    for metric in INCOME_METRICS + ["eps_diluted"]:
        kind = "ytd" if fiscal_period == "FY" else "quarterly"
        fact = _select_metric_fact(filing_facts, metric, kind)
        row[metric] = _fact_value(fact)
        _record_lineage(source_tags, source_keys, metric, fact)
        if metric == "revenue" and fact is not None:
            row["period_start"] = fact["start_date"].date()

    for metric in FLOW_METRICS:
        fact = _select_metric_fact(filing_facts, metric, "ytd")
        value = _fact_value(fact)
        if metric == "capex" and value is not None:
            value = abs(value)
        row[f"{metric}_ytd"] = value
        _record_lineage(source_tags, source_keys, f"{metric}_ytd", fact)
        if pd.isna(row["period_start"]) and fact is not None:
            row["period_start"] = fact["start_date"].date()

    for metric in INSTANT_METRICS:
        fact = _select_metric_fact(filing_facts, metric, "instant")
        row[metric] = _fact_value(fact)
        _record_lineage(source_tags, source_keys, metric, fact)

    row["debt"] = _sum_optional(row.get("debt_current"), row.get("debt_noncurrent"))
    row.pop("debt_current", None)
    row.pop("debt_noncurrent", None)
    row["source_xbrl_tags"] = json.dumps(source_tags, sort_keys=True)
    row["source_fact_keys"] = json.dumps(source_keys, sort_keys=True)
    return row


def _derive_quarterly_income_for_q4(normalized: pd.DataFrame) -> pd.DataFrame:
    result = normalized.copy()
    result["_quarter_order"] = result["fiscal_quarter"].map(QUARTER_ORDER)
    result = result.sort_values(["ticker", "fiscal_year", "_quarter_order", "period_end"])

    for _, group in result.groupby(["ticker", "fiscal_year"], dropna=False):
        q4_index = group[group["fiscal_quarter"] == "Q4"].index
        if q4_index.empty:
            continue
        prior = group[group["fiscal_quarter"].isin(["Q1", "Q2", "Q3"])]
        q4_idx = q4_index[0]
        if len(prior) == 3:
            result.loc[q4_idx, "period_start"] = (
                pd.to_datetime(prior["period_end"]).max() + timedelta(days=1)
            ).date()
        for metric in INCOME_METRICS:
            annual_value = result.loc[q4_idx, metric]
            if pd.isna(annual_value):
                continue
            if prior[metric].isna().any() or len(prior) != 3:
                result.loc[q4_idx, metric] = pd.NA
                result.loc[q4_idx, "derivation_method"] = _append_method(
                    result.loc[q4_idx].get("derivation_method"),
                    f"{metric}_q4_missing_prior_quarters",
                )
                continue
            result.loc[q4_idx, metric] = float(annual_value) - float(prior[metric].sum())
            result.loc[q4_idx, "derivation_method"] = _append_method(
                result.loc[q4_idx].get("derivation_method"),
                f"{metric}_q4_annual_minus_q1_q3",
            )
            result.loc[q4_idx, "source_fact_keys"] = _append_source_keys(
                result.loc[q4_idx].get("source_fact_keys"),
                prior["source_fact_keys"].tolist(),
            )
        result.loc[q4_idx, "eps_diluted"] = pd.NA
    return result.drop(columns=["_quarter_order"])


def _derive_quarterly_cash_flow(normalized: pd.DataFrame) -> pd.DataFrame:
    result = normalized.copy()
    for column in (
        "operating_cash_flow_quarterly",
        "capex_quarterly",
        "buyback_quarterly",
        "dividend_quarterly",
    ):
        if column not in result.columns:
            result[column] = pd.NA
    result["_quarter_order"] = result["fiscal_quarter"].map(QUARTER_ORDER)
    result = result.sort_values(["ticker", "fiscal_year", "_quarter_order", "period_end"])

    for _, group in result.groupby(["ticker", "fiscal_year"], dropna=False):
        previous = None
        for index, row in group.iterrows():
            is_q1 = row["fiscal_quarter"] == "Q1"
            methods = []
            for metric, output in (
                ("operating_cash_flow", "operating_cash_flow_quarterly"),
                ("capex", "capex_quarterly"),
                ("buyback", "buyback_quarterly"),
                ("dividend", "dividend_quarterly"),
            ):
                ytd_column = f"{metric}_ytd"
                if ytd_column not in result.columns or pd.isna(row.get(ytd_column)):
                    continue
                if is_q1:
                    value = row[ytd_column]
                    method = "reported_ytd_equals_quarter"
                elif previous is not None and pd.notna(previous.get(ytd_column)):
                    value = float(row[ytd_column]) - float(previous[ytd_column])
                    if metric == "capex":
                        value = abs(value)
                    method = "ytd_difference"
                else:
                    result.loc[index, "derivation_method"] = _append_method(
                        result.loc[index].get("derivation_method"),
                        f"{metric}_quarterly_missing_prior_ytd",
                    )
                    continue
                result.loc[index, output] = value
                methods.append(method)
            previous = result.loc[index]
            if methods:
                result.loc[index, "is_ytd_source"] = True
                result.loc[index, "is_quarterly_derived"] = any(
                    method == "ytd_difference" for method in methods
                )
                result.loc[index, "derivation_method"] = _append_method(
                    result.loc[index].get("derivation_method"),
                    "+".join(sorted(set(methods))),
                )

    result["free_cash_flow_ytd"] = (
        result["operating_cash_flow_ytd"] - result["capex_ytd"]
    )
    result["free_cash_flow_quarterly"] = (
        result["operating_cash_flow_quarterly"] - result["capex_quarterly"]
    )
    return result.drop(columns=["_quarter_order"])


def _finish_normalized_rows(normalized: pd.DataFrame) -> pd.DataFrame:
    result = normalized.copy()
    result["gross_margin"] = result["gross_profit"] / result["revenue"]
    result["operating_margin"] = result["operating_income"] / result["revenue"]
    result["fundamental_id"] = result.apply(_fundamental_id, axis=1)
    result["data_quality_flag"] = result.apply(_data_quality_flag, axis=1)
    result["confidence"] = result["data_quality_flag"].map(
        {"complete": 0.9, "derived_cash_flow": 0.8, "partial": 0.6}
    ).fillna(0.5)
    for column in NORMALIZED_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
    for column in ("period_start", "period_end", "available_date", "filed_date"):
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.date
    return result


def _select_metric_fact(
    facts: pd.DataFrame,
    metric: str,
    kind: str,
) -> Optional[pd.Series]:
    concept_priority = {
        concept_pair: priority for priority, concept_pair in enumerate(METRIC_CONCEPTS[metric])
    }
    candidates = facts[facts["concept_pair"].isin(concept_priority)].copy()
    if candidates.empty:
        return None
    candidates["priority"] = candidates["concept_pair"].map(concept_priority)
    candidates["filed_date_sort"] = candidates["filed_date"].fillna(pd.Timestamp.min)

    if kind == "instant":
        candidates = candidates.sort_values(
            ["priority", "filed_date_sort"],
            ascending=[True, False],
        )
        return candidates.iloc[0]

    candidates = candidates[candidates["duration_days"].notna()].copy()
    if candidates.empty:
        return None
    if kind == "quarterly":
        quarterly = candidates[
            (candidates["duration_days"] >= 70) & (candidates["duration_days"] <= 110)
        ]
        pool = quarterly if not quarterly.empty else candidates
        pool = pool.assign(duration_sort=(pool["duration_days"] - 90).abs())
        pool = pool.sort_values(
            ["priority", "duration_sort", "filed_date_sort"],
            ascending=[True, True, False],
        )
        return pool.iloc[0]
    if kind == "ytd":
        pool = candidates.sort_values(
            ["priority", "duration_days", "filed_date_sort"],
            ascending=[True, False, False],
        )
        return pool.iloc[0]
    return None


def _cash_flow_feature_rows(row: pd.Series, ingested_at) -> list[dict]:
    rows = []
    date = pd.to_datetime(row["available_date"]).date()
    ticker = row["ticker"]
    fundamental_id = row["fundamental_id"]
    confidence = float(row.get("confidence") or 0.6)
    data_quality_flag = row.get("data_quality_flag")
    metric_specs = [
        (
            "capex_to_ocf",
            _ratio(row.get("capex_quarterly"), row.get("operating_cash_flow_quarterly")),
            True,
        ),
        ("fcf_margin", _ratio(row.get("free_cash_flow_quarterly"), row.get("revenue")), False),
    ]
    for feature_name, value, inverse_pressure in metric_specs:
        if value is None or pd.isna(value):
            continue
        rows.append(
            {
                "date": date,
                "ticker": ticker,
                "feature_name": feature_name,
                "feature_value": value,
                "feature_score": (
                    _score_inverse(value) if inverse_pressure else _score_positive(value)
                ),
                "direction": _direction(value, inverse_pressure=inverse_pressure),
                "source_fundamental_ids": fundamental_id,
                "confidence": confidence,
                "data_quality_flag": data_quality_flag,
                "ingested_at": ingested_at,
            }
        )
    return rows


def _fact_value(fact: Optional[pd.Series]) -> Optional[float]:
    if fact is None or pd.isna(fact["value"]):
        return None
    return float(fact["value"])


def _record_lineage(
    source_tags: dict[str, str],
    source_keys: dict[str, str],
    metric: str,
    fact: Optional[pd.Series],
) -> None:
    if fact is None:
        return
    source_tags[metric] = f"{fact['taxonomy']}:{fact['concept']}"
    source_keys[metric] = _fact_key(fact)


def _fact_key(fact: pd.Series) -> str:
    return "|".join(
        str(fact.get(column, ""))
        for column in ("ticker", "accession_number", "concept", "unit", "start_date", "end_date")
    )


def _fundamental_id(row: pd.Series) -> str:
    key = "|".join(
        str(row.get(column, ""))
        for column in ("ticker", "fiscal_year", "fiscal_quarter", "period_end")
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"fundamental_{digest}"


def _data_quality_flag(row: pd.Series) -> str:
    if pd.notna(row.get("revenue")) and pd.notna(row.get("free_cash_flow_quarterly")):
        if row.get("is_quarterly_derived"):
            return "derived_cash_flow"
        return "complete"
    return "partial"


def _sum_optional(*values: object) -> Optional[float]:
    valid = [float(value) for value in values if pd.notna(value)]
    if not valid:
        return None
    return sum(valid)


def _append_method(existing: object, addition: str) -> str:
    parts = [] if pd.isna(existing) else [part for part in str(existing).split("+") if part]
    parts.append(addition)
    return "+".join(dict.fromkeys(parts))


def _append_source_keys(existing: object, additions: list[object]) -> str:
    try:
        payload = {} if pd.isna(existing) else json.loads(str(existing))
    except json.JSONDecodeError:
        payload = {"existing": str(existing)}
    for index, item in enumerate(additions):
        if pd.isna(item):
            continue
        try:
            payload[f"derived_from_prior_{index}"] = json.loads(str(item))
        except json.JSONDecodeError:
            payload[f"derived_from_prior_{index}"] = str(item)
    return json.dumps(payload, sort_keys=True)


def _ratio(numerator: object, denominator: object) -> Optional[float]:
    if pd.isna(numerator) or pd.isna(denominator) or float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)


def _score_positive(value: float) -> float:
    return max(0.0, min(100.0, value * 100.0))


def _score_inverse(value: float) -> float:
    return max(0.0, min(100.0, 100.0 - value * 100.0))


def _direction(value: float, inverse_pressure: bool = False) -> str:
    if inverse_pressure:
        return "negative" if value > 0.5 else "neutral"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"
