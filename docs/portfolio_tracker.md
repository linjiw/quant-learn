# Portfolio Tracker

This tracker turns the framework allocation into a public $1,000 paper portfolio
on GitHub Pages.

## Persistence Model

The initial lots are versioned so the cost basis does not reset on every GitHub
Actions run:

```text
data/manual/ai_portfolio_lots.json
```

Daily history is also versioned:

```text
data/portfolio/ai_portfolio_summary.csv
data/portfolio/ai_portfolio_snapshots.csv
```

The workflow commits changed history rows back to `main` after a successful
refresh/test pass. The generated site JSON and plot images are rebuilt each run
and published through the GitHub Pages artifact.

## Daily Update

The daily website workflow runs:

```bash
uv run python -m scripts.daily_ai_framework_refresh --include-sec
```

That workflow now includes:

```bash
uv run python -m scripts.update_portfolio
```

Portfolio pricing uses Yahoo Finance through the existing price ingestion layer.
`000660.KS` is priced in KRW and converted to USD with `KRW=X`. The `CASH` row
stays fixed at USD cash.

## Generated Site Files

These files are generated and gitignored locally, then included in the Pages
artifact:

```text
site/ai-framework/portfolio-data.json
site/ai-framework/portfolio/portfolio-value.png
site/ai-framework/portfolio/portfolio-allocation.png
```

The public dashboard reads:

```text
https://linjiw.github.io/quant-learn/portfolio-data.json
```

## Manual Commands

Update the portfolio locally:

```bash
uv run python -m scripts.update_portfolio
```

Reset the initial cost basis only when intentionally starting a new paper
portfolio:

```bash
uv run python -m scripts.update_portfolio --force-reinitialize
```

After reinitializing, commit the updated `data/manual/ai_portfolio_lots.json`.
