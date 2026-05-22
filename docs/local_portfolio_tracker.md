# Local Portfolio Tracker

This tracker turns the framework allocation into a private $1,000 paper
portfolio. It is local-only by design.

## Privacy Boundary

The following paths are gitignored:

- `data/local/`
- `reports/local/`
- `site/ai-framework/local-portfolio-data.json`
- `site/ai-framework/local-portfolio/`
- `logs/`

The GitHub Pages builder explicitly excludes the local portfolio files, even if
they exist in the source site directory.

## Daily Update

Initialize or update the local portfolio:

```bash
uv run python -m scripts.update_local_portfolio
```

The first run uses the latest available Yahoo Finance prices as the initial cost
basis for a $1,000 allocation matching `data/manual/ai_framework_holdings.csv`.
The `CASH` row stays as cash. `000660.KS` is priced in KRW and converted to USD
through `KRW=X`.

Outputs:

```text
data/local/ai_portfolio_lots.json
data/local/ai_portfolio_snapshots.csv
data/local/ai_portfolio_summary.csv
site/ai-framework/local-portfolio-data.json
site/ai-framework/local-portfolio/portfolio-value.png
site/ai-framework/local-portfolio/portfolio-allocation.png
reports/local/ai_portfolio_value.png
reports/local/ai_portfolio_allocation.png
```

## Local Dashboard

Start the local site:

```bash
cd site/ai-framework
python3 -m http.server 8765
```

Open:

```text
http://127.0.0.1:8765/
```

The `Portfolio` tab shows the private performance panel only when
`local-portfolio-data.json` exists locally.

## Local Daily Schedule

Install the macOS `launchd` job:

```bash
uv run python -m scripts.install_local_portfolio_launchd --load
```

Default schedule: every day at `06:45` local time.

The job runs:

```bash
uv run python -m scripts.update_local_portfolio
```

Logs:

```text
logs/local_portfolio_refresh.log
```

To change the time:

```bash
uv run python -m scripts.install_local_portfolio_launchd --hour 7 --minute 15 --load
```

## Reinitialization

Only use this when you intentionally want to reset the cost basis:

```bash
uv run python -m scripts.update_local_portfolio --force-reinitialize
```
