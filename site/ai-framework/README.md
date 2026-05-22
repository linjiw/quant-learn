# AI Framework Website

Static dashboard for the trusted-execution framework.

Open:

```bash
site/ai-framework/index.html
```

The site has no build step. Research content lives in `research-data.js`; layout
and interaction live in `styles.css` and `app.js`.

The personal performance panel reads generated `portfolio-data.json`. Generate
it from the repo root:

```bash
uv run python -m scripts.update_portfolio
```

The daily GitHub workflow publishes the generated portfolio JSON and plot images
to GitHub Pages.

Validate the data contract:

```bash
node scripts/validate_ai_framework_site.mjs
```

Optional source link-health audit:

```bash
node scripts/check_ai_framework_sources.mjs
```

Implementation and design-system notes for review:

```bash
docs/ai_framework_website_design.md
```
