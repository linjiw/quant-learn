# Event Data Quality Report

Total event return rows: 630

## Analysis status

| analysis_status   |   rows |
|:------------------|-------:|
| ready             |    546 |
| partial_pending   |     66 |
| data_issue        |     18 |

## Missing reason

| missing_reason        |   rows |
|:----------------------|-------:|
| none                  |    546 |
| pending_future_window |     66 |
| missing_ticker_price  |     15 |
| adr_calendar_gap      |      3 |

## By affected ticker

| affected_ticker   |   rows |
|:------------------|-------:|
| NVDA              |    180 |
| TSM               |    180 |
| AMD               |    180 |
| GOOGL             |     90 |

## By benchmark

| benchmark_ticker   |   rows |
|:-------------------|-------:|
| QQQ                |    210 |
| SOXX               |    210 |
| SMH                |    210 |

## Data Issues

| affected_ticker   | benchmark_ticker   | missing_reason       |   rows |
|:------------------|:-------------------|:---------------------|-------:|
| GOOGL             | QQQ                | missing_ticker_price |      2 |
| GOOGL             | SMH                | missing_ticker_price |      2 |
| GOOGL             | SOXX               | missing_ticker_price |      2 |
| NVDA              | QQQ                | missing_ticker_price |      2 |
| NVDA              | SMH                | missing_ticker_price |      2 |
| NVDA              | SOXX               | missing_ticker_price |      2 |
| AMD               | QQQ                | missing_ticker_price |      1 |
| AMD               | SMH                | missing_ticker_price |      1 |
| AMD               | SOXX               | missing_ticker_price |      1 |
| TSM               | QQQ                | adr_calendar_gap     |      1 |
| TSM               | SMH                | adr_calendar_gap     |      1 |
| TSM               | SOXX               | adr_calendar_gap     |      1 |
