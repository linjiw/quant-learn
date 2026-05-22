# AI Framework Daily Website Automation

This document describes the daily refresh and GitHub Pages deployment workflow for
the AI trusted-execution dashboard.

## Goal

Every morning, the workflow should:

1. Pull core market data where practical.
2. Import the AI framework manual snapshots.
3. Rebuild AI framework tracker outputs.
4. Rebuild AI strategy review signals.
5. Validate the website data contract.
6. Build a static `public/` artifact.
7. Publish that artifact to GitHub Pages.

The workflow publishes the generated site artifact. It does not commit daily generated
files back into the repository.

## Local Command

Run the same workflow locally:

```bash
uv run python -m scripts.daily_ai_framework_refresh
```

For a fast local smoke test that avoids network data pulls:

```bash
uv run python -m scripts.daily_ai_framework_refresh --skip-market-data --skip-link-audit
```

The generated site artifact is written to:

```text
public/
```

You can preview it locally:

```bash
cd public
python3 -m http.server 8766
```

Then open:

```text
http://127.0.0.1:8766/
```

## GitHub Actions Workflow

Workflow file:

```text
.github/workflows/daily-ai-framework-pages.yml
```

Schedule:

```yaml
cron: "0 14 * * *"
```

GitHub cron uses UTC. `14:00 UTC` maps to morning Pacific time:

- 06:00 PST during standard time.
- 07:00 PDT during daylight time.

It can also be run manually through `workflow_dispatch`.

## GitHub Pages Setup

After pushing this workflow to GitHub:

1. Open the GitHub repository settings.
2. Go to `Pages`.
3. Set `Build and deployment` source to `GitHub Actions`.
4. Optional: add a custom domain if needed.

The workflow uses official GitHub Pages actions:

- `actions/configure-pages`
- `actions/upload-pages-artifact`
- `actions/deploy-pages`

## SEC User Agent

SEC ingestion is optional. The workflow passes:

```yaml
SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}
```

If the secret is not set, the refresh script skips SEC ingestion instead of failing.

Recommended secret format:

```text
Your Name your.email@example.com
```

## Scripts

### `scripts/daily_ai_framework_refresh.py`

Orchestrates the daily refresh:

- Initializes DuckDB.
- Optionally ingests prices and TSMC monthly revenue.
- Optionally ingests SEC data if `--include-sec` and `SEC_USER_AGENT` are set.
- Imports AI framework manual CSVs.
- Builds tracker and strategy reports.
- Validates source site data.
- Builds the GitHub Pages artifact.
- Validates the generated Pages artifact.
- Optionally runs source link-health audit.

### `scripts/build_ai_framework_pages.py`

Builds the deployable static site:

- Copies `site/ai-framework/` into `public/`.
- Stamps the generated `public/research-data.js` with:
  - latest manual data date,
  - current Los Angeles review date.
- Copies selected reports into `public/reports/`.
- Writes `public/refresh.json`.
- Writes `public/.nojekyll`.

### `scripts/validate_ai_framework_site.mjs`

Validates the data contract:

- Holdings sum to 100.
- Allocation buckets sum to 100.
- Source IDs resolve.
- Claim source IDs resolve.
- Review dates are valid and ordered.
- Controlled vocabularies are respected.

### `scripts/check_ai_framework_sources.mjs`

Audits source link health:

- Uses `HEAD` first.
- Falls back to lightweight ranged `GET`.
- Reports `403` as potential bot/permission blocking.
- Supports optional failing modes:

```bash
node scripts/check_ai_framework_sources.mjs --fail-on-error
node scripts/check_ai_framework_sources.mjs --fail-on-degraded
```

## Design Choice

The workflow publishes through GitHub Pages artifacts, not by committing generated
HTML back into the repo. That keeps source history clean while still refreshing the
public site daily.

## Known Limits

- `research-data.js` is still a curated source file. The next improvement is to
  generate it from tracker CSV/SQLite.
- SEC ingestion depends on the optional `SEC_USER_AGENT` secret.
- Some source links may return `403` to automation while still opening in a browser.
- GitHub cron is UTC, not Pacific-time-aware.

