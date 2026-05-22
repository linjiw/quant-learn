# AI Trusted Execution Framework Website Design

As of: 2026-05-22

This document describes the implementation and design system for the static
research dashboard at `site/ai-framework/`. It is written for expert review of
both the website implementation and the investment-framework writing.

This is a research dashboard only. It is not investment, tax, legal, or
financial advice.

## 1. Objective

The site translates the AI "trusted execution of intelligence" framework into a
reviewable dashboard.

The product goal is not to present an AI-themed stock list. The goal is to make
the framework auditable:

- Map holdings to control-right layers: capacity, cost, authority, outcome,
  physical AI optionality, and dry powder.
- Make thesis writing source-linked and reviewable.
- Separate structural thesis from review signals.
- Track uncertainty explicitly instead of hiding it in conviction language.
- Provide a compact artifact an expert can critique without reading the full
  conversation history.

## 2. Artifact Map

Primary website files:

- `site/ai-framework/index.html`: static page shell and view containers.
- `site/ai-framework/styles.css`: visual design system, layout, responsive rules.
- `site/ai-framework/app.js`: render logic, tab switching, filtering, source cards.
- `site/ai-framework/research-data.js`: all research content and source URLs.
- `site/ai-framework/README.md`: quick local open instructions.

Related QA artifacts:

- `reports/screenshots/ai-framework-desktop.png`
- `reports/screenshots/ai-framework-narrow.png`
- `reports/screenshots/ai-framework-narrow-fulltop.png`

Related framework data and reports:

- `data/manual/ai_framework_holdings.csv`
- `data/manual/ai_framework_indicators.csv`
- `data/manual/ai_framework_predictions.csv`
- `data/manual/ai_framework_scenarios.csv`
- `data/manual/ai_control_right_scores.csv`
- `reports/ai_execution_tracker.md`
- `reports/ai_strategy_system.md`

## 3. Information Architecture

The first screen is the usable dashboard, not a landing page. It starts with:

- Operating thesis summary.
- Total target weight.
- Highest current alert.
- Investable row count.
- Research-only disclaimer.

The navigation has five views:

| View | Purpose |
| --- | --- |
| Portfolio | Holdings, weights, thesis, evidence, risks, watch item, source links |
| Control rights | Overlapping exposure bars and allocation buckets |
| Signals | Systematic-discretionary plateau and watchlist signals |
| Research notes | Compressed stock-by-stock story for written review |
| Sources | Full linked evidence base |

## 4. Data Model

All content is stored in `window.AI_FRAMEWORK_DATA` inside
`site/ai-framework/research-data.js`.

Top-level fields:

```js
{
  asOf: "2026-05-22",
  dataDate: "2026-05-21",
  reviewDate: "2026-05-22",
  title: "...",
  subtitle: "...",
  summary: "...",
  allocation: [...],
  exposures: [...],
  monitoringQuestions: [...],
  signals: [...],
  claims: [...],
  holdings: [...],
  sources: {...}
}
```

Holding schema:

```js
{
  ticker: "MSFT",
  name: "Microsoft",
  weight: 18,
  bucket: "Core compounders",
  conviction: "A",
  layers: ["Authority", "Outcome"],
  thesis: "...",
  evidence: ["...", "..."],
  risks: ["...", "..."],
  falsifier: "...",
  watch: "...",
  confidence: "High",
  last_reviewed_at: "2026-05-22",
  next_review_due: "2026-08-22",
  sources: ["msft-agent365", "msft-security-agent365"]
}
```

Signal and monitoring-question objects can also carry `sources`, which render as
source pills in the Signals view. They also carry `observed_value`,
`confidence`, `last_reviewed_at`, and `next_review_due` so the signal layer is
auditable over time.

Claim provenance schema:

```js
{
  claim_id: "nvda-rubin-platform",
  source_id: "nvidia-rubin",
  entity: "NVDA",
  claim: "...",
  evidence_type: "company_product_page",
  metric: "Rubin GPU, Vera CPU, NVLink, networking, DPU stack",
  quote_or_excerpt: "Rack-scale platform architecture",
  retrieved_at: "2026-05-22",
  confidence: "High"
}
```

Current invariants verified locally:

- Holdings count: 14
- Total weight: 100
- Source count: 31
- Claim count: 15
- Missing source IDs: 0
- Duplicate tickers: 0
- Signals: 4
- Monitoring questions: 3

## 5. Research Methodology

The framework treats intelligence as increasingly abundant and trusted execution
as the scarce economic layer.

The site encodes that thesis through four categories of research objects:

1. Holdings

   Each holding has a role in the control-rights framework. The thesis text is
   intentionally short and tied to evidence, risks, and a watch item.

2. Control-right exposures

   Exposure layers intentionally overlap. A holding can map to several control
   rights. The exposure bars are therefore a qualitative portfolio map, not an
   accounting total.

3. Review signals

   Signals are not automatic trade orders. They are prompts for
   systematic-discretionary review. Current signals focus on capability,
   economics, trust, and missing agent-runtime public-market exposure.

4. Sources

   The dashboard favors official/company sources and primary research where
   available. When secondary sources are used, the thesis labels the uncertainty
   explicitly.

Important writing rule added after review:

- Product existence is not the same as production adoption.
- Architecture strength is not the same as monetization durability.
- Trusted data/workflow is not automatically outcome-verification revenue.

This rule is now reflected in the MSFT, GOOGL, NVDA, and vertical-verifier
language.

## 6. Portfolio Story

The current 100% target allocation is:

| Holding | Weight | Framework role |
| --- | ---: | --- |
| MSFT | 18% | Authority and outcome control |
| GOOGL | 15% | Capacity, cost, authority, outcome |
| AVGO | 10% | Custom silicon and networking |
| 000660.KS | 8% | HBM capacity bottleneck |
| NVDA | 7% | AI factory platform infrastructure |
| TSM | 7% | Foundry and advanced packaging chokepoint |
| TER | 7% | Semiconductor test plus robotics optionality |
| MSCI | 2% | Financial data and analytics control point |
| MCO | 2% | Credit-risk verifier |
| SPGI | 2% | Ratings/data plus Kensho AI retrieval |
| VEEV | 2% | Life-sciences workflow verifier |
| CEG | 5% | Nodal power exposure |
| VRT | 5% | Data-center power and thermal infrastructure |
| CASH | 10% | Dry powder and regime-change option value |

The story is:

- Core compounders express the trusted-execution loop.
- Bottleneck cyclicals express current physical constraints.
- Vertical verifiers express outcome-control optionality.
- TER gives semiconductor-test exposure plus physical-AI optionality.
- Cash is treated as an explicit risk-control asset.

## 7. Design System

### Visual Direction

The dashboard is intentionally work-focused:

- Quiet research-terminal feel.
- Dense but readable information.
- No landing-page hero.
- No decorative gradients, orbs, or marketing illustration.
- Cards are used only for repeated items, metrics, and dashboard panels.

### Color Tokens

Defined in `:root`:

| Token | Use |
| --- | --- |
| `--bg` | Page background |
| `--panel` | Panel/card background |
| `--ink` | Primary text |
| `--muted` | Secondary text |
| `--line` | Borders |
| `--accent` | Accent controls |
| `--accent-dark` | Active tabs, primary labels |
| `--amber` | Warning alert |
| `--red` | High severity |
| `--blue` | Secondary bar endpoint |
| `--green-soft` | Authority/source/chip backgrounds |
| `--amber-soft` | Medium severity background |
| `--red-soft` | High severity background |

The palette is intentionally mixed: green/teal for governance and audit, amber
for trust alerts, red for high review status, blue as a secondary signal in
bars. It avoids a one-hue AI palette.

### Typography

- System sans stack: `Inter`, UI sans, system fonts.
- Fixed font sizes with responsive breakpoints. No viewport-width font scaling.
- Letter spacing is zero for headings and small positive only for uppercase
  section labels.
- Long text uses constrained line-height for review readability.

### Layout

- Page max width: `1440px`.
- Main grid uses CSS Grid.
- Desktop dashboard: thesis panel plus three metric panels.
- Holdings grid: 3 columns desktop, 2 columns tablet, 1 column narrow.
- Tabs wrap under `560px` so audit-critical `Sources` stays visible.
- `overflow-x: hidden` plus min-width-safe grid tracks prevent accidental
  horizontal overflow.

### Components

Current reusable UI components:

- Sticky topbar
- Metric panel
- Tab button
- Holding card
- Layer chip
- Source pill
- Exposure bar row
- Signal card
- Question card
- Research row
- Source card
- Claim card

## 8. Implementation Architecture

The site is dependency-free static HTML/CSS/JS.

Rationale:

- The framework is mostly content and review logic, not a complex app state
  problem.
- No build system keeps it easy for an expert reviewer to inspect.
- All facts and weights live in one data file.
- Rendering functions are small and deterministic.

Render flow:

1. `index.html` loads `research-data.js`.
2. `index.html` loads `app.js`.
3. `app.js` reads `window.AI_FRAMEWORK_DATA`.
4. `init()` renders all views and binds tab/filter events.
5. Portfolio filtering is client-side by control-right layer.

Important functions in `app.js`:

- `escapeHtml(value)`: escapes all dynamic text before insertion into rendered
  markup.
- `safeUrl(value)`: only allows `http` and `https` source URLs in rendered links.
- `sourceLink(id)`: maps a source ID to a rendered source pill.
- `setupTabs()`: view switching with ARIA tab semantics and keyboard navigation.
- `setupFilters()`: layer filter setup.
- `renderPortfolio(layer)`: holding card rendering.
- `renderControlRights()`: exposure bars and allocation cards.
- `renderSignals()`: plateau/watchlist signal rendering with sources.
- `renderResearch()`: compressed stock story view.
- `renderSources()`: complete source registry.
- `renderClaims()`: claim-level evidence provenance rendering.

Security and accessibility posture:

- The page still uses string-template rendering for simplicity, but all dynamic
  text is escaped at render boundaries.
- Source URLs are parsed and restricted to `http`/`https`.
- External links use `rel="noopener noreferrer"`.
- The dashboard navigation uses `role="tablist"`, `role="tab"`,
  `role="tabpanel"`, `aria-controls`, and `aria-selected`.
- Tabs support mouse activation plus `ArrowLeft`, `ArrowRight`, `Home`, and `End`.

## 9. Source Strategy

Primary or high-confidence source categories:

- Company product pages: Microsoft Agent 365, Google Ironwood, NVIDIA Rubin,
  Veeva AI Agents.
- Company investor releases: MSCI, Teradyne, TSMC, Broadcom, SK hynix.
- Research and benchmark sources: METR, arXiv, Epoch AI, OpenAI benchmark notes.
- Infrastructure/process sources: PJM interconnection process.

Current claim-level provenance:

- The site now stores first-pass claim records with `claim_id`, `source_id`,
  `entity`, `claim`, `evidence_type`, `metric`, `quote_or_excerpt`,
  `retrieved_at`, and `confidence`.
- Claim records cover the framework-level capability/cost claims and the main
  thesis claim for each investable holding except cash.

Known weaker areas:

- CEG still uses a Reuters-via-Investing source for the specific Three Mile
  Island / PJM delay claim, plus PJM process documentation as primary context.
- Claim-level provenance is first-pass; it is not yet complete for every bullet
  in every evidence list.
- Some official investor PDF URLs may be brittle over time.

Future audit improvement:

```js
{
  claim_id: "nvda-rubin-system-architecture",
  source_id: "nvidia-rubin",
  evidence_type: "company_product_page",
  retrieved_at: "2026-05-22",
  metric: "72 Rubin GPUs / 36 Vera CPUs",
  confidence: "high"
}
```

## 10. QA Performed

Commands run:

```bash
node --check site/ai-framework/app.js
node --check site/ai-framework/research-data.js
node scripts/validate_ai_framework_site.mjs
node scripts/check_ai_framework_sources.mjs
uv run ruff check .
uv run pytest
```

Latest results:

- JS syntax: pass
- Data integrity: pass
- Claim provenance integrity: pass
- Ruff: pass
- Pytest: 64 passed
- Browser console: no warnings or errors in the checked session
- Source link-health: available as an audit script; 403/timeouts are treated as
  evidence of brittle or bot-blocked sources, not automatically as false claims.
- Desktop screenshot: generated
- Narrow screenshot: generated

Visual QA notes:

- Desktop layout is readable.
- Narrow layout is single-column and tabs wrap so Sources remains visible.
- The `asOf` date no longer wraps.
- Header date semantics are explicit: data date and review date are shown separately.
- A data-URL favicon is used to avoid local favicon 404 noise.

## 11. Known Limitations

Implementation limitations:

- Static data only; no live ingestion from the tracker database yet.
- Link-health is scriptable but not yet enforced in CI.
- Claim-level provenance exists, but it is first-pass and not yet exhaustive.
- No print/export stylesheet.

Research limitations:

- Several key variables are still proxies rather than direct measurements:
  risk-adjusted cost per verified task, human-review minutes, and enterprise
  write-permission penetration.
- The vertical verifier basket is conceptually strong but still needs direct
  evidence that AI products are becoming outcome-verification revenue.
- NVDA platform thesis needs continued monitoring of attach rate, networking,
  software pull-through, gross margin durability, and custom-silicon bypass.
- Capacity names remain cycle-sensitive and should not be evaluated as if they
  were authority/outcome compounders.

## 12. Expert Review Checklist

Please review these questions:

1. Is the control-rights mapping defensible for each holding?
2. Does any thesis overstate adoption, monetization, or moat strength?
3. Are any source links weak, stale, or insufficiently primary?
4. Is the CEG nodal-power framing adequately supported?
5. Does the vertical verifier basket need different names or weights?
6. Are the review signals actionable, or are they still too narrative?
7. Is the UI readable enough for monthly/quarterly review?
8. Are there accessibility or mobile usability issues in the current layout?
9. Which evidence bullets still need claim-level provenance?
10. What would falsify the dashboard's core thesis over the next 12 months?

## 13. Recommended Next Iteration

Highest-value next work:

1. Expand claim-level provenance to every material evidence bullet.
2. Generate the website from the tracker CSV/SQLite data instead of manually
   duplicating content in `research-data.js`.
3. Promote structured signal fields into tracker CSV/SQLite once the schema stabilizes.
4. Add historical snapshots for link-health reports and claim provenance.
5. Add a changelog of thesis updates so changes are auditable over time.
