"""Segment KPI bridge, features, and reports."""

import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

DRIVER_FEATURES = {
    "GOOGL": {
        "cloud_growth_score": ("Google Cloud", "segment_revenue_growth_yoy", "growth"),
        "cloud_margin_score": ("Google Cloud", "segment_margin", "margin"),
        "search_resilience_score": (
            "Google Search & other",
            "segment_revenue_growth_yoy",
            "growth",
        ),
        "services_profitability_score": ("Google Services", "segment_margin", "margin"),
        "youtube_ads_growth_score": ("YouTube ads", "segment_revenue_growth_yoy", "growth"),
    },
    "NVDA": {
        "data_center_momentum_score": ("Data Center", "segment_revenue_growth_yoy", "growth"),
        "gaming_cycle_score": ("Gaming", "segment_revenue_growth_yoy", "growth"),
        "automotive_growth_score": ("Automotive", "segment_revenue_growth_yoy", "growth"),
        "professional_visualization_growth_score": (
            "Professional Visualization",
            "segment_revenue_growth_yoy",
            "growth",
        ),
    },
    "AMD": {
        "data_center_momentum_score": ("Data Center", "segment_revenue_growth_yoy", "growth"),
        "data_center_margin_score": ("Data Center", "segment_margin", "margin"),
        "client_cycle_score": ("Client", "segment_revenue_growth_yoy", "growth"),
        "embedded_margin_score": ("Embedded", "segment_margin", "margin"),
    },
}

REQUIRED_KPIS_BY_TICKER = {
    "GOOGL": {
        "cloud_growth_score": ("Google Cloud:revenue",),
        "cloud_margin_score": ("Google Cloud:revenue", "Google Cloud:operating_income"),
        "search_resilience_score": ("Google Search & other:revenue",),
        "services_profitability_score": (
            "Google Services:revenue",
            "Google Services:operating_income",
        ),
        "youtube_ads_growth_score": ("YouTube ads:revenue",),
    },
    "NVDA": {
        "data_center_momentum_score": ("Data Center:revenue",),
        "gaming_cycle_score": ("Gaming:revenue",),
        "automotive_growth_score": ("Automotive:revenue",),
        "professional_visualization_growth_score": (
            "Professional Visualization:revenue",
        ),
        "ai_end_market_breadth_score": (
            "Data Center:revenue",
            "Gaming:revenue",
            "Automotive:revenue",
        ),
    },
    "AMD": {
        "data_center_momentum_score": ("Data Center:revenue",),
        "data_center_margin_score": ("Data Center:revenue", "Data Center:operating_income"),
        "client_cycle_score": ("Client:revenue",),
        "embedded_margin_score": ("Embedded:revenue", "Embedded:operating_income"),
        "second_source_thesis_score": ("Data Center:revenue", "Data Center:operating_income"),
    },
    "TSM": {
        "monthly_revenue_momentum_score": ("total:monthly_revenue_yoy",),
        "monthly_revenue_sequential_score": ("total:monthly_revenue_twd",),
        "monthly_revenue_yoy_trend_score": ("total:monthly_revenue_yoy",),
        "hpc_mix_score": ("High Performance Computing:revenue_share",),
        "advanced_node_mix_score": ("advanced_technology:revenue_share",),
        "gross_margin_quality_score": ("total:gross_margin",),
        "capex_cycle_score": ("total:quarterly_revenue", "total:capex"),
    },
}


def build_company_segment_kpis(
    tickers: Optional[list[str]] = None,
    quarters: int = 8,
) -> pd.DataFrame:
    """Bridge company-level fundamental drivers into the segment KPI layer."""

    initialize_database()
    ticker_list = tickers or ["GOOGL", "NVDA", "AMD"]
    with connect() as conn:
        fundamentals = _load_company_fundamentals(conn, ticker_list)

    if fundamentals.empty:
        return pd.DataFrame()

    fundamentals["period_end"] = pd.to_datetime(fundamentals["period_end"])
    latest = fundamentals.groupby("ticker", group_keys=False).head(quarters).sort_values(
        ["ticker", "period_end"]
    )
    rows = []
    ingested_at = utc_now_naive()
    for _, row in latest.iterrows():
        base = {
            "period_end": row["period_end"].date(),
            "fiscal_year": row["fiscal_year"],
            "fiscal_quarter": row["fiscal_quarter"],
            "period_type": "quarter",
            "ticker": row["ticker"],
            "kpi_group": "company",
            "segment_name": "total",
            "unit": None,
            "currency": None,
            "source_type": row.get("source_type", "fundamentals_quarterly"),
            "source_url": None,
            "source_accession_number": row.get("source_accession_number"),
            "filed_date": row.get("source_filed_date"),
            "is_reported": False,
            "is_derived": True,
            "derivation_method": row.get("derivation_method", "fundamentals_quarterly_bridge"),
            "confidence": _company_confidence_label(row.get("confidence")),
            "notes": row.get("notes", "Derived from normalized point-in-time fundamentals."),
            "ingested_at": ingested_at,
        }
        metrics = {
            "revenue": (row.get("revenue"), "USD"),
            "gross_margin": (row.get("gross_margin"), "ratio"),
            "operating_margin": (row.get("operating_margin"), "ratio"),
            "operating_cash_flow": (row.get("operating_cash_flow"), "USD"),
            "capex": (row.get("capex"), "USD"),
            "free_cash_flow": (row.get("free_cash_flow"), "USD"),
        }
        revenue = row.get("revenue")
        operating_cash_flow = row.get("operating_cash_flow")
        capex = row.get("capex")
        free_cash_flow = row.get("free_cash_flow")
        if pd.notna(operating_cash_flow) and pd.notna(capex) and operating_cash_flow:
            metrics["capex_to_ocf"] = (float(capex) / float(operating_cash_flow), "ratio")
        if pd.notna(revenue) and pd.notna(free_cash_flow) and revenue:
            metrics["fcf_margin"] = (float(free_cash_flow) / float(revenue), "ratio")

        for kpi_name, (value, unit) in metrics.items():
            if pd.isna(value):
                continue
            item = {
                **base,
                "kpi_name": kpi_name,
                "kpi_value": float(value),
                "unit": unit,
                "currency": "USD" if unit == "USD" else None,
            }
            item["segment_kpi_id"] = _segment_kpi_id(item)
            rows.append(item)
    if not rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(rows).drop_duplicates(subset=["segment_kpi_id"], keep="last")


def _load_company_fundamentals(conn, ticker_list: list[str]) -> pd.DataFrame:
    normalized = conn.execute(
        """
        SELECT
            ticker,
            fiscal_year,
            fiscal_quarter,
            period_end,
            revenue,
            gross_profit,
            gross_margin,
            operating_income,
            operating_margin,
            net_income,
            eps_diluted AS eps,
            operating_cash_flow_quarterly AS operating_cash_flow,
            capex_quarterly AS capex,
            free_cash_flow_quarterly AS free_cash_flow,
            cash,
            debt,
            shares_outstanding,
            source_accession_number,
            filed_date AS source_filed_date,
            source_url,
            confidence,
            data_quality_flag,
            derivation_method,
            'fundamentals_quarterly_normalized' AS source_type,
            'Derived from PIT normalized fundamentals with YTD cash-flow lineage.'
                AS notes
        FROM fundamentals_quarterly_normalized
        WHERE ticker IN (SELECT unnest(?))
          AND period_end IS NOT NULL
        ORDER BY ticker, period_end DESC
        """,
        [ticker_list],
    ).fetchdf()
    if not normalized.empty:
        return normalized

    return conn.execute(
        """
        SELECT
            *,
            'fundamentals_quarterly' AS source_type,
            NULL AS confidence,
            NULL AS data_quality_flag,
            'fundamentals_quarterly_bridge' AS derivation_method,
            'Derived from legacy fundamentals_quarterly.' AS notes
        FROM fundamentals_quarterly
        WHERE ticker IN (SELECT unnest(?))
          AND period_end IS NOT NULL
        ORDER BY ticker, period_end DESC
        """,
        [ticker_list],
    ).fetchdf()


def build_tsmc_monthly_segment_kpis(months: int = 24) -> pd.DataFrame:
    """Bridge official TSMC monthly revenue into the segment KPI layer."""

    initialize_database()
    with connect() as conn:
        monthly = conn.execute(
            """
            SELECT period, year, month, revenue_ntd_million, mom_pct, yoy_pct, source_url
            FROM tsmc_monthly_revenue
            ORDER BY period DESC
            LIMIT ?
            """,
            [months],
        ).fetchdf()

    if monthly.empty:
        return pd.DataFrame()

    rows = []
    ingested_at = utc_now_naive()
    for _, row in monthly.sort_values("period").iterrows():
        period = pd.to_datetime(row["period"]).date()
        base = {
            "period_end": period,
            "fiscal_year": int(row["year"]),
            "fiscal_quarter": _quarter_from_month(int(row["month"])),
            "period_type": "month",
            "ticker": "TSM",
            "kpi_group": "monthly",
            "segment_name": "total",
            "source_type": "monthly_revenue",
            "source_url": row["source_url"],
            "source_accession_number": None,
            "filed_date": None,
            "is_reported": True,
            "is_derived": False,
            "derivation_method": None,
            "confidence": "high",
            "notes": "Official TSMC monthly revenue bridge.",
            "ingested_at": ingested_at,
        }
        for kpi_name, value, unit, currency in (
            ("monthly_revenue_twd", row["revenue_ntd_million"], "TWD_mn", "TWD"),
            ("monthly_revenue_mom", row["mom_pct"], "percent", None),
            ("monthly_revenue_yoy", row["yoy_pct"], "percent", None),
        ):
            item = {
                **base,
                "kpi_name": kpi_name,
                "kpi_value": None if pd.isna(value) else float(value),
                "unit": unit,
                "currency": currency,
            }
            item["segment_kpi_id"] = _segment_kpi_id(item)
            rows.append(item)

    return pd.DataFrame(rows)


def store_segment_kpis(segment_kpis: pd.DataFrame) -> int:
    """Store segment KPI rows."""

    if segment_kpis.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, segment_kpis, "segment_kpis", ["segment_kpi_id"])


def build_segment_features() -> pd.DataFrame:
    """Build lightweight segment driver features from current segment KPIs."""

    initialize_database()
    with connect() as conn:
        segments = conn.execute("SELECT * FROM segments_view").fetchdf()
        kpis = conn.execute("SELECT * FROM segment_kpis").fetchdf()

    rows = []
    ingested_at = utc_now_naive()
    rows.extend(_segment_view_features(segments, ingested_at))
    rows.extend(_driver_features(segments, ingested_at))
    rows.extend(_company_features(kpis, ingested_at))
    rows.extend(_tsm_quarterly_features(kpis, ingested_at))
    rows.extend(_tsm_monthly_features(kpis, ingested_at))
    if not rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(rows).drop_duplicates(
        subset=["date", "ticker", "feature_name"],
        keep="first",
    )


def store_segment_features(segment_features: pd.DataFrame) -> int:
    """Store segment feature rows."""

    if segment_features.empty:
        return 0
    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM segment_features")
        return upsert_dataframe(
            conn,
            segment_features,
            "segment_features",
            ["date", "ticker", "feature_name"],
        )


def build_segment_dashboard(output_path: Path) -> Path:
    """Write a concise segment dashboard markdown report."""

    initialize_database()
    with connect() as conn:
        features = conn.execute(
            """
            SELECT *
            FROM segment_features
            ORDER BY ticker, feature_name
            """
        ).fetchdf()

    lines = ["# Segment Dashboard", ""]
    if features.empty:
        lines.append("No segment features are available yet.")
    else:
        for ticker, group in features.groupby("ticker"):
            lines.extend([f"## {ticker}", ""])
            for _, row in group.iterrows():
                lines.append(
                    "- "
                    f"{row['feature_name']}: value={_fmt_value(row['feature_value'])}, "
                    f"score={_fmt_value(row['feature_score'])}, "
                    f"direction={row['direction']}, confidence={_fmt_value(row['confidence'])}"
                )
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _segment_view_features(segments: pd.DataFrame, ingested_at) -> list[dict]:
    if segments.empty:
        return []

    rows = []
    segments["period_end"] = pd.to_datetime(segments["period_end"])
    if "period_type" in segments.columns and (segments["period_type"] == "quarter").any():
        segments = segments[segments["period_type"] == "quarter"]
    latest = (
        segments.sort_values("period_end")
        .groupby(["ticker", "segment_name"], dropna=False)
        .tail(1)
    )
    for _, row in latest.iterrows():
        date = _feature_date(row)
        segment_slug = _slug(row["segment_name"])
        if pd.notna(row["segment_revenue_growth_yoy"]):
            value = float(row["segment_revenue_growth_yoy"])
            rows.append(
                _feature_row(
                    date,
                    row["ticker"],
                    f"{segment_slug}_revenue_growth_yoy",
                    value,
                    _score_growth(value),
                    _direction(value),
                    _confidence(row["confidence"]),
                    _source_ids_for_feature(row, "segment_revenue_growth_yoy"),
                    ingested_at,
                )
            )
        if pd.notna(row["segment_margin"]):
            value = float(row["segment_margin"])
            rows.append(
                _feature_row(
                    date,
                    row["ticker"],
                    f"{segment_slug}_margin",
                    value,
                    _score_margin(value),
                    _direction(value),
                    _confidence(row["confidence"]),
                    _source_ids_for_feature(row, "segment_margin"),
                    ingested_at,
                )
            )
    return rows


def _driver_features(segments: pd.DataFrame, ingested_at) -> list[dict]:
    """Build ticker-specific driver features only when required KPIs are present."""

    if segments.empty:
        return []

    quarter_segments = _quarter_segments(segments)
    rows: list[dict] = []
    latest = (
        quarter_segments.sort_values("period_end")
        .groupby(["ticker", "segment_name"], dropna=False)
        .tail(1)
    )

    for ticker, feature_specs in DRIVER_FEATURES.items():
        ticker_rows = latest[latest["ticker"] == ticker]
        if ticker_rows.empty:
            continue
        for feature_name, (segment_name, source_column, score_kind) in feature_specs.items():
            if not _has_required_segment_kpis(ticker_rows, ticker, feature_name):
                continue
            segment_rows = ticker_rows[ticker_rows["segment_name"] == segment_name]
            if segment_rows.empty:
                continue
            row = segment_rows.iloc[0]
            value = row.get(source_column)
            if pd.isna(value):
                continue
            score = (
                _score_margin(float(value))
                if score_kind == "margin"
                else _score_growth(float(value))
            )
            rows.append(
                _feature_row(
                    _feature_date(row),
                    ticker,
                    feature_name,
                    float(value),
                    score,
                    _direction(float(value)),
                    _confidence(row["confidence"]),
                    _source_ids_for_feature(row, source_column),
                    ingested_at,
                )
            )

    rows.extend(_combined_driver_features(latest, ingested_at))
    return rows


def _combined_driver_features(latest_segments: pd.DataFrame, ingested_at) -> list[dict]:
    """Build simple thesis features from multiple required source KPIs."""

    rows: list[dict] = []
    amd_data_center = _latest_segment(latest_segments, "AMD", "Data Center")
    amd_rows = latest_segments[latest_segments["ticker"] == "AMD"]
    if amd_data_center is not None and _has_required_segment_kpis(
        amd_rows,
        "AMD",
        "second_source_thesis_score",
    ):
        growth = amd_data_center.get("segment_revenue_growth_yoy")
        margin = amd_data_center.get("segment_margin")
        if pd.notna(growth) and pd.notna(margin):
            score = (_score_growth(float(growth)) + _score_margin(float(margin))) / 2.0
            value = (float(growth) + float(margin)) / 2.0
            source_ids = _join_source_ids(
                _source_ids_for_feature(amd_data_center, "segment_revenue_growth_yoy"),
                _source_ids_for_feature(amd_data_center, "segment_margin"),
            )
            rows.append(
                _feature_row(
                    _feature_date(amd_data_center),
                    "AMD",
                    "second_source_thesis_score",
                    value,
                    score,
                    _direction(value),
                    _confidence(amd_data_center["confidence"]),
                    source_ids,
                    ingested_at,
                )
            )

    nvda_rows = latest_segments[latest_segments["ticker"] == "NVDA"]
    nvda_segments = [
        _latest_segment(latest_segments, "NVDA", segment)
        for segment in ("Data Center", "Gaming", "Automotive")
    ]
    if _has_required_segment_kpis(nvda_rows, "NVDA", "ai_end_market_breadth_score") and all(
        row is not None and pd.notna(row.get("segment_revenue_growth_yoy"))
        for row in nvda_segments
    ):
        values = [
            float(row["segment_revenue_growth_yoy"])
            for row in nvda_segments
            if row is not None
        ]
        score = sum(_score_growth(value) for value in values) / len(values)
        value = sum(values) / len(values)
        source_ids = _join_source_ids(
            *(
                _source_ids_for_feature(row, "segment_revenue_growth_yoy")
                for row in nvda_segments
                if row is not None
            )
        )
        rows.append(
            _feature_row(
                _feature_date(nvda_segments[0]),
                "NVDA",
                "ai_end_market_breadth_score",
                value,
                score,
                _direction(value),
                min(_confidence(row["confidence"]) for row in nvda_segments if row is not None),
                source_ids,
                ingested_at,
            )
        )
    return rows


def _company_features(kpis: pd.DataFrame, ingested_at) -> list[dict]:
    if kpis.empty:
        return []
    company = kpis[(kpis["period_type"] == "quarter") & (kpis["kpi_group"] == "company")].copy()
    if company.empty:
        return []
    company["period_end"] = pd.to_datetime(company["period_end"])

    rows = []
    rows.extend(
        _latest_company_feature(
            company,
            "GOOGL",
            "capex_to_ocf",
            "capex_pressure_score",
            _score_inverse_pressure,
            inverse_direction=True,
        )
    )
    rows.extend(
        _latest_company_feature(
            company,
            "GOOGL",
            "fcf_margin",
            "fcf_quality_score",
            _score_margin,
        )
    )
    for ticker in ("NVDA", "AMD"):
        rows.extend(
            _latest_company_feature(
                company,
                ticker,
                "gross_margin",
                "gross_margin_quality_score",
                _score_margin,
            )
        )
        rows.extend(
            _latest_company_feature(
                company,
                ticker,
                "operating_margin",
                "operating_margin_quality_score",
                _score_margin,
            )
        )

    for row in rows:
        row["ingested_at"] = ingested_at
    return rows


def _latest_company_feature(
    company: pd.DataFrame,
    ticker: str,
    kpi_name: str,
    feature_name: str,
    score_fn,
    inverse_direction: bool = False,
) -> list[dict]:
    item = (
        company[
            (company["ticker"] == ticker)
            & (company["kpi_name"] == kpi_name)
            & company["kpi_value"].notna()
        ]
        .sort_values("period_end")
        .tail(1)
    )
    if item.empty:
        return []
    row = item.iloc[0]
    value = float(row["kpi_value"])
    direction = _direction(value)
    if inverse_direction:
        direction = "negative" if value > 0.5 else "neutral"
    return [
        _feature_row(
            _kpi_feature_date(row),
            ticker,
            feature_name,
            value,
            score_fn(value),
            direction,
            _confidence(row["confidence"]),
            str(row["segment_kpi_id"]),
            None,
        )
    ]


def _tsm_monthly_features(kpis: pd.DataFrame, ingested_at) -> list[dict]:
    if kpis.empty:
        return []
    monthly = kpis[
        (kpis["ticker"] == "TSM")
        & (kpis["period_type"] == "month")
        & (
            kpis["kpi_name"].isin(
                ["monthly_revenue_yoy", "monthly_revenue_mom", "monthly_revenue_twd"]
            )
        )
    ].copy()
    if monthly.empty:
        return []
    monthly["period_end"] = pd.to_datetime(monthly["period_end"])
    rows = []
    for kpi_name, feature_name in (("monthly_revenue_yoy", "monthly_revenue_momentum_score"),):
        if not _has_required_kpi_rows(kpis, "TSM", feature_name):
            continue
        item = (
            monthly[(monthly["kpi_name"] == kpi_name) & monthly["kpi_value"].notna()]
            .sort_values("period_end")
            .tail(1)
        )
        if item.empty:
            continue
        row = item.iloc[0]
        value = float(row["kpi_value"]) / 100.0
        rows.append(
            _feature_row(
                _kpi_feature_date(row),
                "TSM",
                feature_name,
                value,
                _score_growth(value),
                _direction(value),
                _confidence(row["confidence"]),
                row["segment_kpi_id"],
                ingested_at,
            )
        )

    revenue = monthly[
        (monthly["kpi_name"] == "monthly_revenue_twd") & monthly["kpi_value"].notna()
    ].sort_values("period_end")
    if (
        _has_required_kpi_rows(kpis, "TSM", "monthly_revenue_sequential_score")
        and len(revenue) >= 2
    ):
        latest = revenue.iloc[-1]
        previous = revenue.iloc[-2]
        value = float(latest["kpi_value"]) / float(previous["kpi_value"]) - 1.0
        rows.append(
            _feature_row(
                latest["period_end"].date(),
                "TSM",
                "monthly_revenue_sequential_score",
                value,
                _score_growth(value),
                _direction(value),
                min(_confidence(latest["confidence"]), _confidence(previous["confidence"])),
                _source_ids_from_rows([latest, previous]),
                ingested_at,
            )
        )
    yoy = monthly[
        (monthly["kpi_name"] == "monthly_revenue_yoy")
        & monthly["kpi_value"].notna()
    ].sort_values("period_end")
    if (
        _has_required_kpi_rows(kpis, "TSM", "monthly_revenue_yoy_trend_score")
        and len(yoy) >= 4
    ):
        latest = yoy.iloc[-1]
        prior_mean = yoy.iloc[-4:-1]["kpi_value"].mean()
        trend_value = (float(latest["kpi_value"]) - float(prior_mean)) / 100.0
        source_ids = ",".join(yoy.iloc[-4:]["segment_kpi_id"].astype(str).tolist())
        rows.append(
            _feature_row(
                latest["period_end"].date(),
                "TSM",
                "monthly_revenue_yoy_trend_score",
                trend_value,
                _score_growth(trend_value),
                _direction(trend_value),
                min(_confidence(value) for value in yoy.iloc[-4:]["confidence"].tolist()),
                source_ids,
                ingested_at,
            )
        )
    return rows


def _tsm_quarterly_features(kpis: pd.DataFrame, ingested_at) -> list[dict]:
    if kpis.empty:
        return []
    quarterly = kpis[(kpis["ticker"] == "TSM") & (kpis["period_type"] == "quarter")].copy()
    if quarterly.empty:
        return []
    quarterly["period_end"] = pd.to_datetime(quarterly["period_end"])

    rows = []
    for segment_name, kpi_name, feature_name, score_fn in (
        ("High Performance Computing", "revenue_share", "hpc_mix_score", _score_margin),
        ("advanced_technology", "revenue_share", "advanced_node_mix_score", _score_margin),
        ("total", "gross_margin", "gross_margin_quality_score", _score_margin),
    ):
        if not _has_required_kpi_rows(kpis, "TSM", feature_name):
            continue
        row = _latest_kpi(quarterly, segment_name, kpi_name)
        if row is None:
            continue
        value = float(row["kpi_value"])
        rows.append(
            _feature_row(
                _kpi_feature_date(row),
                "TSM",
                feature_name,
                value,
                score_fn(value),
                _direction(value),
                _confidence(row["confidence"]),
                str(row["segment_kpi_id"]),
                ingested_at,
            )
        )

    revenue = _latest_kpi(quarterly, "total", "quarterly_revenue")
    capex = _latest_kpi(quarterly, "total", "capex")
    if (
        _has_required_kpi_rows(kpis, "TSM", "capex_cycle_score")
        and revenue is not None
        and capex is not None
        and revenue["period_end"] == capex["period_end"]
    ):
        value = float(capex["kpi_value"]) / float(revenue["kpi_value"])
        rows.append(
            _feature_row(
                _kpi_feature_date(revenue),
                "TSM",
                "capex_cycle_score",
                value,
                _score_inverse_pressure(value),
                "negative" if value > 0.5 else "neutral",
                min(_confidence(revenue["confidence"]), _confidence(capex["confidence"])),
                _source_ids_from_rows([revenue, capex]),
                ingested_at,
            )
        )
    return rows


def _feature_row(
    date,
    ticker: str,
    feature_name: str,
    feature_value: float,
    feature_score: float,
    direction: str,
    confidence: float,
    source_kpi_ids: str,
    ingested_at,
) -> dict:
    return {
        "date": date,
        "ticker": ticker,
        "feature_name": feature_name,
        "feature_value": feature_value,
        "feature_score": feature_score,
        "direction": direction,
        "confidence": confidence,
        "source_kpi_ids": source_kpi_ids,
        "ingested_at": ingested_at,
    }


def _segment_kpi_id(row: dict) -> str:
    key_columns = (
        "ticker",
        "period_end",
        "period_type",
        "kpi_group",
        "segment_name",
        "kpi_name",
    )
    key = "|".join(
        str(row.get(column, ""))
        for column in key_columns
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"segment_kpi_{digest}"


def _quarter_from_month(month: int) -> str:
    return f"Q{((month - 1) // 3) + 1}"


def _quarter_segments(segments: pd.DataFrame) -> pd.DataFrame:
    result = segments.copy()
    result["period_end"] = pd.to_datetime(result["period_end"])
    if "period_type" in result.columns and (result["period_type"] == "quarter").any():
        return result[result["period_type"] == "quarter"]
    return result


def _latest_segment(
    segments: pd.DataFrame,
    ticker: str,
    segment_name: str,
) -> Optional[pd.Series]:
    rows = segments[(segments["ticker"] == ticker) & (segments["segment_name"] == segment_name)]
    if rows.empty:
        return None
    return rows.sort_values("period_end").iloc[-1]


def _latest_kpi(kpis: pd.DataFrame, segment_name: str, kpi_name: str) -> Optional[pd.Series]:
    rows = kpis[(kpis["segment_name"] == segment_name) & (kpis["kpi_name"] == kpi_name)]
    rows = rows[rows["kpi_value"].notna()]
    if rows.empty:
        return None
    return rows.sort_values("period_end").iloc[-1]


def _has_required_segment_kpis(
    rows: pd.DataFrame,
    ticker: str,
    feature_name: str,
) -> bool:
    required = REQUIRED_KPIS_BY_TICKER.get(ticker, {}).get(feature_name, ())
    if not required:
        return True

    for key in required:
        segment_name, kpi_name = key.split(":", 1)
        segment_rows = rows[rows["segment_name"] == segment_name]
        if segment_rows.empty:
            return False
        if not any(
            _segment_kpi_available(row, kpi_name)
            for _, row in segment_rows.iterrows()
        ):
            return False
    return True


def _segment_kpi_available(row: pd.Series, kpi_name: str) -> bool:
    column_by_kpi = {
        "revenue": "segment_revenue",
        "operating_income": "segment_operating_income",
        "margin": "segment_margin",
    }
    column = column_by_kpi.get(kpi_name)
    if column is None:
        return False
    return column in row and pd.notna(row[column])


def _has_required_kpi_rows(kpis: pd.DataFrame, ticker: str, feature_name: str) -> bool:
    required = REQUIRED_KPIS_BY_TICKER.get(ticker, {}).get(feature_name, ())
    if not required:
        return True

    ticker_rows = kpis[kpis["ticker"] == ticker]
    for key in required:
        segment_name, kpi_name = key.split(":", 1)
        matching = ticker_rows[
            (ticker_rows["segment_name"] == segment_name)
            & (ticker_rows["kpi_name"] == kpi_name)
            & ticker_rows["kpi_value"].notna()
        ]
        if matching.empty:
            return False
    return True


def _feature_date(row: pd.Series):
    available_date = row.get("available_date")
    if pd.notna(available_date):
        return pd.to_datetime(available_date).date()
    return pd.to_datetime(row["period_end"]).date()


def _kpi_feature_date(row: pd.Series):
    filed_date = row.get("filed_date")
    if pd.notna(filed_date):
        return pd.to_datetime(filed_date).date()
    return pd.to_datetime(row["period_end"]).date()


def _slug(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("&", "and").replace("/", "_")


def _score_growth(value: float) -> float:
    if pd.isna(value):
        return float("nan")
    return max(0.0, min(100.0, 50.0 + value * 100.0))


def _score_margin(value: float) -> float:
    if pd.isna(value):
        return float("nan")
    return max(0.0, min(100.0, value * 100.0))


def _score_inverse_pressure(value: float) -> float:
    if pd.isna(value):
        return float("nan")
    return max(0.0, min(100.0, 100.0 - value * 100.0))


def _direction(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _confidence(value: object) -> float:
    if pd.isna(value):
        return 0.6
    normalized = str(value).strip().lower()
    if normalized == "high":
        return 0.9
    if normalized == "medium":
        return 0.7
    if normalized == "low":
        return 0.5
    try:
        return float(normalized)
    except ValueError:
        return 0.6


def _company_confidence_label(value: object) -> str:
    confidence = _confidence(value)
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"


def _source_ids(row: pd.Series) -> str:
    if "source_kpi_ids" in row and pd.notna(row["source_kpi_ids"]):
        return str(row["source_kpi_ids"])
    if "segment_kpi_id" in row and pd.notna(row["segment_kpi_id"]):
        return str(row["segment_kpi_id"])
    parts = [row.get("ticker"), row.get("segment_name"), row.get("period_end")]
    return "|".join(str(part) for part in parts)


def _source_ids_for_feature(row: pd.Series, source_column: str) -> str:
    if source_column == "segment_revenue_growth_yoy":
        return _join_source_ids(
            row.get("segment_revenue_source_kpi_ids"),
            row.get("prior_year_segment_revenue_source_kpi_ids"),
        )
    if source_column == "segment_margin":
        return _join_source_ids(row.get("segment_margin_source_kpi_ids"))
    if source_column == "segment_revenue":
        return _join_source_ids(row.get("segment_revenue_source_kpi_ids"))
    return _source_ids(row)


def _join_source_ids(*values: object) -> str:
    source_ids = []
    for value in values:
        if pd.isna(value):
            continue
        source_ids.extend(item for item in str(value).split(",") if item)
    return ",".join(dict.fromkeys(source_ids))


def _source_ids_from_rows(rows: list[pd.Series]) -> str:
    return _join_source_ids(
        *(
            row.get("segment_kpi_id")
            if "segment_kpi_id" in row and pd.notna(row["segment_kpi_id"])
            else row.get("source_kpi_ids")
            for row in rows
        )
    )


def _fmt_value(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"
