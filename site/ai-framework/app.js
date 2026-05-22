const data = window.AI_FRAMEWORK_DATA;

const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]
  );

const safeUrl = (value) => {
  try {
    const url = new URL(String(value ?? ""), window.location.href);
    if (["http:", "https:"].includes(url.protocol)) {
      return url.href;
    }
  } catch {
    return "about:blank";
  }
  return "about:blank";
};

const sourceLink = (id) => {
  const source = data.sources[id];
  if (!source) return "";
  return `<a class="source-pill" href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a>`;
};

const severityClass = (value) =>
  String(value ?? "")
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9_-]/g, "");

const formatUsd = (value) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(Number(value ?? 0));

const formatPct = (value) => `${Number(value ?? 0).toFixed(2)}%`;

const signedClass = (value) => (Number(value ?? 0) >= 0 ? "positive" : "negative");

function init() {
  document.getElementById("asOf").textContent = `Data ${data.dataDate} | Reviewed ${data.reviewDate}`;
  document.getElementById("summaryText").textContent = data.summary;
  document.getElementById("holdingCount").textContent = data.holdings.length;
  setupTabs();
  setupFilters();
  renderPortfolio("All");
  renderControlRights();
  renderSignals();
  renderResearch();
  renderSources();
  renderClaims();
  loadPortfolioPerformance();
}

function setupTabs() {
  const tabs = Array.from(document.querySelectorAll(".tab"));
  tabs.forEach((button, index) => {
    button.addEventListener("click", () => activateTab(button));
    button.addEventListener("keydown", (event) => {
      const keyToIndex = {
        ArrowLeft: index === 0 ? tabs.length - 1 : index - 1,
        ArrowRight: index === tabs.length - 1 ? 0 : index + 1,
        Home: 0,
        End: tabs.length - 1
      };
      if (!(event.key in keyToIndex)) return;
      event.preventDefault();
      const nextTab = tabs[keyToIndex[event.key]];
      nextTab.focus();
      activateTab(nextTab);
    });
  });
}

function activateTab(activeButton) {
  document.querySelectorAll(".tab").forEach((tab) => {
    const isActive = tab === activeButton;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
    tab.tabIndex = isActive ? 0 : -1;
  });
  document.querySelectorAll(".view").forEach((view) => {
    const isActive = view.id === `view-${activeButton.dataset.view}`;
    view.classList.toggle("active", isActive);
    view.hidden = !isActive;
  });
}

function setupFilters() {
  const select = document.getElementById("layerFilter");
  const layers = Array.from(new Set(data.holdings.flatMap((holding) => holding.layers))).sort();
  layers.forEach((layer) => {
    const option = document.createElement("option");
    option.value = layer;
    option.textContent = layer;
    select.appendChild(option);
  });
  select.addEventListener("change", () => renderPortfolio(select.value));
}

function renderPortfolio(layer) {
  const grid = document.getElementById("holdingsGrid");
  const holdings = data.holdings.filter(
    (holding) => layer === "All" || holding.layers.includes(layer)
  );
  grid.innerHTML = holdings.map(renderHoldingCard).join("");
}

function renderHoldingCard(holding) {
  const evidence = holding.evidence.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const risks = holding.risks.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const chips = holding.layers
    .map((layer) => `<span class="chip">${escapeHtml(layer)}</span>`)
    .join("");
  const sources = holding.sources.map(sourceLink).join("");
  return `
    <article class="holding-card">
      <div class="card-head">
        <div>
          <div class="ticker">${escapeHtml(holding.ticker)}</div>
          <div class="name">${escapeHtml(holding.name)}</div>
        </div>
        <div class="weight">${escapeHtml(holding.weight)}%</div>
      </div>
      <div class="bucket">${escapeHtml(holding.bucket)} | Conviction ${escapeHtml(holding.conviction)}</div>
      <div class="chips">${chips}</div>
      <div class="meta-row">
        <span>Confidence: ${escapeHtml(holding.confidence)}</span>
        <span>Reviewed: ${escapeHtml(holding.last_reviewed_at)}</span>
        <span>Next: ${escapeHtml(holding.next_review_due)}</span>
      </div>
      <p class="thesis">${escapeHtml(holding.thesis)}</p>
      <div>
        <div class="card-section-title">Evidence</div>
        <ul>${evidence}</ul>
      </div>
      <div>
        <div class="card-section-title">Risks</div>
        <ul class="risk-list">${risks}</ul>
      </div>
      <div>
        <div class="card-section-title">Watch</div>
        <p class="muted">${escapeHtml(holding.watch)}</p>
      </div>
      <div>
        <div class="card-section-title">Falsifier</div>
        <p class="muted">${escapeHtml(holding.falsifier)}</p>
      </div>
      <div class="source-links">${sources}</div>
    </article>
  `;
}

function renderControlRights() {
  const bars = document.getElementById("exposureBars");
  const maxValue = Math.max(...data.exposures.map((item) => item.value));
  bars.innerHTML = data.exposures
    .map((item) => {
      const width = Math.max(0, Math.min(100, Math.round((item.value / maxValue) * 100)));
      return `
        <div class="bar-row">
          <div class="bar-label">${escapeHtml(item.layer)}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <div class="bar-value">${escapeHtml(item.value)}%</div>
          <div class="bar-note">${escapeHtml(item.holdings)}</div>
        </div>
      `;
    })
    .join("");

  document.getElementById("allocationGrid").innerHTML = data.allocation
    .map(
      (item) => `
        <div class="mini-card">
          <p class="section-label">${escapeHtml(item.label)}</p>
          <strong>${escapeHtml(item.value)}%</strong>
        </div>
      `
    )
    .join("");
}

function renderSignals() {
  document.getElementById("signalGrid").innerHTML = data.signals
    .map((signal) => {
      const sources = (signal.sources || []).map(sourceLink).join("");
      return `
        <article class="signal-card">
          <span class="severity ${severityClass(signal.severity)}">${escapeHtml(signal.severity)}</span>
          <h3>${escapeHtml(signal.target)}</h3>
          <p><strong>${escapeHtml(signal.type)}</strong></p>
          <p>${escapeHtml(signal.text)}</p>
          <div class="meta-row">
            <span>Observed: ${escapeHtml(signal.observed_value)}</span>
            <span>Value: ${escapeHtml(signal.current_value)} ${escapeHtml(signal.unit)}</span>
            <span>Threshold: ${escapeHtml(signal.threshold)}</span>
            <span>Confidence: ${escapeHtml(signal.confidence)}</span>
            <span>Next: ${escapeHtml(signal.next_review_due)}</span>
          </div>
          <p>Status rule: ${escapeHtml(signal.status_rule)}</p>
          <p>Action: ${escapeHtml(signal.action)}</p>
          <div class="source-links">${sources}</div>
        </article>
      `;
    })
    .join("");

  document.getElementById("questionGrid").innerHTML = data.monitoringQuestions
    .map((question) => {
      const sources = (question.sources || []).map(sourceLink).join("");
      return `
        <article class="question-card">
          <span class="severity ${severityClass(question.status)}">${escapeHtml(question.status)}</span>
          <h3>${escapeHtml(question.label)}</h3>
          <p>${escapeHtml(question.question)}</p>
          <div class="meta-row">
            <span>Observed: ${escapeHtml(question.observed_value)}</span>
            <span>Value: ${escapeHtml(question.current_value)} ${escapeHtml(question.unit)}</span>
            <span>Threshold: ${escapeHtml(question.threshold)}</span>
            <span>Confidence: ${escapeHtml(question.confidence)}</span>
            <span>Next: ${escapeHtml(question.next_review_due)}</span>
          </div>
          <p>Status rule: ${escapeHtml(question.status_rule)}</p>
          <p>${escapeHtml(question.trigger)}</p>
          <div class="source-links">${sources}</div>
        </article>
      `;
    })
    .join("");
}

function renderResearch() {
  document.getElementById("researchList").innerHTML = data.holdings
    .map(
      (holding) => `
        <section class="research-row">
          <div>
            <div class="ticker">${escapeHtml(holding.ticker)}</div>
            <div class="name">${escapeHtml(holding.name)}</div>
            <div class="weight">${escapeHtml(holding.weight)}%</div>
          </div>
          <div>
            <h3>${escapeHtml(holding.bucket)}</h3>
            <p>${escapeHtml(holding.thesis)}</p>
            <p class="muted">Watch: ${escapeHtml(holding.watch)}</p>
            <p class="muted">Falsifier: ${escapeHtml(holding.falsifier)}</p>
          </div>
        </section>
      `
    )
    .join("");
}

function renderSources() {
  document.getElementById("sourceList").innerHTML = Object.entries(data.sources)
    .map(
      ([id, source]) => `
        <article class="source-card">
          <p class="section-label">${escapeHtml(id)}</p>
          <h3><a href="${safeUrl(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a></h3>
          <p>${escapeHtml(source.url)}</p>
        </article>
      `
    )
    .join("");
}

function renderClaims() {
  document.getElementById("claimList").innerHTML = (data.claims || [])
    .map((claim) => {
      const source = data.sources[claim.source_id];
      const sourceLabel = source ? source.label : claim.source_id;
      const sourceUrl = source ? source.url : "";
      return `
        <article class="claim-card">
          <p class="section-label">${escapeHtml(claim.entity)} | ${escapeHtml(claim.claim_id)}</p>
          <h3>${escapeHtml(claim.claim)}</h3>
          <div class="meta-row">
            <span>Type: ${escapeHtml(claim.evidence_type)}</span>
            <span>Metric: ${escapeHtml(claim.metric)}</span>
            <span>Confidence: ${escapeHtml(claim.confidence)}</span>
            <span>Retrieved: ${escapeHtml(claim.retrieved_at)}</span>
          </div>
          <p>${escapeHtml(claim.quote_or_excerpt)}</p>
          <a class="source-pill" href="${safeUrl(sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceLabel)}</a>
        </article>
      `;
    })
    .join("");
}

async function loadPortfolioPerformance() {
  try {
    const response = await fetch("./portfolio-data.json", { cache: "no-store" });
    if (!response.ok) {
      renderPortfolioPerformanceMissing();
      return;
    }
    const portfolio = await response.json();
    renderPortfolioPerformance(portfolio);
  } catch {
    renderPortfolioPerformanceMissing();
  }
}

function renderPortfolioPerformanceMissing() {
  const status = document.getElementById("portfolioPerformanceStatus");
  status.className = "portfolio-status muted";
  status.textContent =
    "No portfolio ledger found yet. The daily GitHub workflow generates this $1,000 tracker from the versioned lot seed.";
}

function renderPortfolioPerformance(portfolio) {
  const summary = portfolio.summary || {};
  const status = document.getElementById("portfolioPerformanceStatus");
  status.className = "portfolio-status ready";
  status.textContent = `Updated ${escapeHtml(portfolio.asOfDate)} from the daily portfolio workflow.`;

  const kpis = document.getElementById("portfolioPerformanceKpis");
  kpis.hidden = false;
  kpis.innerHTML = [
    ["Total value", formatUsd(summary.total_value_usd), ""],
    ["Total P/L", formatUsd(summary.pnl_usd), signedClass(summary.pnl_usd)],
    ["Return", formatPct(summary.return_pct), signedClass(summary.return_pct)],
    ["Daily P/L", formatUsd(summary.daily_pnl_usd), signedClass(summary.daily_pnl_usd)],
    ["Daily return", formatPct(summary.daily_return_pct), signedClass(summary.daily_return_pct)],
    ["Annualized", formatPct(summary.annualized_return_pct), signedClass(summary.annualized_return_pct)]
  ]
    .map(
      ([label, value, tone]) => `
        <div class="portfolio-kpi">
          <span>${escapeHtml(label)}</span>
          <strong class="${tone}">${escapeHtml(value)}</strong>
        </div>
      `
    )
    .join("");

  renderPortfolioPerformancePlots(portfolio);
  renderPortfolioPerformanceTable(portfolio);
}

function renderPortfolioPerformancePlots(portfolio) {
  const plots = document.getElementById("portfolioPerformancePlots");
  plots.hidden = false;
  const version = encodeURIComponent(portfolio.updatedAtUtc || Date.now());
  const valuePlot = portfolio.plots?.value;
  const allocationPlot = portfolio.plots?.allocation;
  plots.innerHTML = `
    <figure>
      <figcaption>Value history</figcaption>
      ${
        valuePlot
          ? `<img src="${escapeHtml(valuePlot)}?v=${version}" alt="Portfolio value history plot" />`
          : renderInlineValueChart(portfolio.history || [])
      }
    </figure>
    <figure>
      <figcaption>Current holding values</figcaption>
      ${
        allocationPlot
          ? `<img src="${escapeHtml(allocationPlot)}?v=${version}" alt="Current market value by holding plot" />`
          : renderInlineAllocationChart(portfolio.holdings || [])
      }
    </figure>
  `;
}

function renderPortfolioPerformanceTable(portfolio) {
  document.getElementById("portfolioPerformanceTableWrap").hidden = false;
  document.getElementById("portfolioPerformanceRows").innerHTML = (portfolio.holdings || [])
    .map((holding) => {
      const pnl = Number(holding.pnl_usd || 0);
      return `
        <tr>
          <td>
            <strong>${escapeHtml(holding.ticker)}</strong>
            <span>${escapeHtml(holding.holding_name)}</span>
          </td>
          <td>${escapeHtml(holding.target_weight)}%</td>
          <td>
            ${formatUsd(holding.price_usd)}
            <span>${escapeHtml(holding.currency)} ${Number(holding.price_native || 0).toFixed(2)}</span>
          </td>
          <td>${formatUsd(holding.market_value_usd)}</td>
          <td class="${signedClass(pnl)}">${formatUsd(pnl)}</td>
          <td class="${signedClass(holding.return_pct)}">${formatPct(holding.return_pct)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderInlineValueChart(history) {
  if (!history.length) return `<div class="empty-chart">No history yet</div>`;
  const width = 720;
  const height = 260;
  const padding = 34;
  const values = history.map((row) => Number(row.total_value_usd || 0));
  const min = Math.min(...values, 1000);
  const max = Math.max(...values, 1000);
  const span = Math.max(max - min, 1);
  const points = values
    .map((value, index) => {
      const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / span) * (height - padding * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return `
    <svg class="inline-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Portfolio value chart">
      <polyline points="${points}" fill="none" stroke="#0f766e" stroke-width="4" />
    </svg>
  `;
}

function renderInlineAllocationChart(holdings) {
  if (!holdings.length) return `<div class="empty-chart">No holdings yet</div>`;
  const max = Math.max(...holdings.map((holding) => Number(holding.market_value_usd || 0)), 1);
  return `
    <div class="inline-bars">
      ${holdings
        .map((holding) => {
          const width = Math.max(2, (Number(holding.market_value_usd || 0) / max) * 100);
          return `
            <div>
              <span>${escapeHtml(holding.ticker)}</span>
              <div><i style="width:${width}%"></i></div>
              <b>${formatUsd(holding.market_value_usd)}</b>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

init();
