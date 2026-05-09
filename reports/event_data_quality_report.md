# Event Data Quality Report

Total event return rows: 840

## Analysis status

| analysis_status   |   rows |
|:------------------|-------:|
| ready             |    669 |
| partial_pending   |     88 |
| data_issue        |     83 |

## Missing reason

| missing_reason        |   rows |
|:----------------------|-------:|
| none                  |    669 |
| pending_future_window |     88 |
| missing_factor_input  |     59 |
| missing_ticker_price  |     20 |
| adr_calendar_gap      |      4 |

## By affected ticker

| affected_ticker   |   rows |
|:------------------|-------:|
| NVDA              |    240 |
| TSM               |    240 |
| AMD               |    240 |
| GOOGL             |    120 |

## By benchmark

| benchmark_ticker   |   rows |
|:-------------------|-------:|
| QQQ                |    210 |
| SOXX               |    210 |
| SMH                |    210 |
| QQQ_SOXX_TNX       |    210 |

## Data Issues

| affected_ticker   | benchmark_ticker   | missing_reason       |   rows |
|:------------------|:-------------------|:---------------------|-------:|
| NVDA              | QQQ_SOXX_TNX       | missing_factor_input |     20 |
| AMD               | QQQ_SOXX_TNX       | missing_factor_input |     19 |
| TSM               | QQQ_SOXX_TNX       | missing_factor_input |     15 |
| GOOGL             | QQQ_SOXX_TNX       | missing_factor_input |      5 |
| GOOGL             | QQQ                | missing_ticker_price |      2 |
| GOOGL             | QQQ_SOXX_TNX       | missing_ticker_price |      2 |
| GOOGL             | SMH                | missing_ticker_price |      2 |
| GOOGL             | SOXX               | missing_ticker_price |      2 |
| NVDA              | QQQ                | missing_ticker_price |      2 |
| NVDA              | QQQ_SOXX_TNX       | missing_ticker_price |      2 |
| NVDA              | SMH                | missing_ticker_price |      2 |
| NVDA              | SOXX               | missing_ticker_price |      2 |
| AMD               | QQQ                | missing_ticker_price |      1 |
| AMD               | QQQ_SOXX_TNX       | missing_ticker_price |      1 |
| AMD               | SMH                | missing_ticker_price |      1 |
| AMD               | SOXX               | missing_ticker_price |      1 |
| TSM               | QQQ                | adr_calendar_gap     |      1 |
| TSM               | QQQ_SOXX_TNX       | adr_calendar_gap     |      1 |
| TSM               | SMH                | adr_calendar_gap     |      1 |
| TSM               | SOXX               | adr_calendar_gap     |      1 |
