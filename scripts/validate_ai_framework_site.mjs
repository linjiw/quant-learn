import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const repoRoot = process.cwd();
const siteDirArgIndex = process.argv.indexOf("--site-dir");
const siteDir =
  siteDirArgIndex >= 0 && process.argv[siteDirArgIndex + 1]
    ? process.argv[siteDirArgIndex + 1]
    : path.join("site", "ai-framework");
const requirePortfolio = process.argv.includes("--require-portfolio");
const dataPath = path.resolve(repoRoot, siteDir, "research-data.js");
const portfolioDataPath = path.resolve(repoRoot, siteDir, "portfolio-data.json");
const code = fs.readFileSync(dataPath, "utf8");
const sandbox = { window: {} };

vm.runInNewContext(code, sandbox, { filename: dataPath });

const data = sandbox.window.AI_FRAMEWORK_DATA;
const errors = [];
const warnings = [];

const isObject = (value) => value && typeof value === "object" && !Array.isArray(value);
const sourceIds = new Set(Object.keys(data?.sources || {}));
const knownClaimIds = new Set((data?.claims || []).map((claim) => claim.claim_id));
const usedSourceIds = [];
const allowedConfidence = new Set(["High", "Medium-high", "Medium", "Low", "Policy"]);
const allowedSeverity = new Set(["High", "Medium", "Info"]);
const allowedStatus = new Set(["Watch", "Data gap", "High review"]);
const allowedDirection = new Set([
  "above_threshold_bad",
  "below_threshold_bad",
  "no_improvement_bad",
  "watchlist_trigger"
]);

function validateDate(value, context, field) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) {
    errors.push(`${context} ${field} must be YYYY-MM-DD, got: ${value}`);
    return;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    errors.push(`${context} ${field} is not a valid date: ${value}`);
  }
}

function validateReviewDates(object, context) {
  validateDate(object.last_reviewed_at, context, "last_reviewed_at");
  validateDate(object.next_review_due, context, "next_review_due");
  if (
    /^\d{4}-\d{2}-\d{2}$/.test(object.last_reviewed_at || "") &&
    /^\d{4}-\d{2}-\d{2}$/.test(object.next_review_due || "") &&
    object.next_review_due < object.last_reviewed_at
  ) {
    errors.push(`${context} next_review_due must be >= last_reviewed_at`);
  }
}

function requireField(object, field, context) {
  if (object[field] === undefined || object[field] === null || object[field] === "") {
    errors.push(`${context} missing required field: ${field}`);
  }
}

function collectSourceIds(items, context) {
  for (const item of items || []) {
    for (const sourceId of item.sources || []) {
      usedSourceIds.push({ context, sourceId });
      if (!sourceIds.has(sourceId)) {
        errors.push(`${context} references missing source id: ${sourceId}`);
      }
    }
  }
}

if (!isObject(data)) {
  errors.push("window.AI_FRAMEWORK_DATA was not defined as an object");
} else {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(data.asOf || "")) {
    errors.push(`asOf must be YYYY-MM-DD, got: ${data.asOf}`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(data.dataDate || "")) {
    errors.push(`dataDate must be YYYY-MM-DD, got: ${data.dataDate}`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(data.reviewDate || "")) {
    errors.push(`reviewDate must be YYYY-MM-DD, got: ${data.reviewDate}`);
  }

  if (!Array.isArray(data.holdings)) errors.push("holdings must be an array");
  if (!Array.isArray(data.signals)) errors.push("signals must be an array");
  if (!Array.isArray(data.monitoringQuestions)) errors.push("monitoringQuestions must be an array");
  if (!Array.isArray(data.claims)) errors.push("claims must be an array");
  if (!Array.isArray(data.exposures)) errors.push("exposures must be an array");
  if (!Array.isArray(data.allocation)) errors.push("allocation must be an array");
  if (!isObject(data.sources)) errors.push("sources must be an object");

  const tickers = new Set();
  let totalWeight = 0;

  for (const holding of data.holdings || []) {
    const context = `holding ${holding.ticker || "(unknown)"}`;
    for (const field of [
      "ticker",
      "name",
      "weight",
      "bucket",
      "conviction",
      "confidence",
      "last_reviewed_at",
      "next_review_due",
      "layers",
      "thesis",
      "evidence",
      "risks",
      "falsifier",
      "watch"
    ]) {
      requireField(holding, field, context);
    }
    if (tickers.has(holding.ticker)) errors.push(`duplicate ticker: ${holding.ticker}`);
    tickers.add(holding.ticker);
    if (!Number.isFinite(holding.weight)) {
      errors.push(`${context} weight is not numeric`);
    } else {
      totalWeight += holding.weight;
    }
    if (!allowedConfidence.has(holding.confidence)) {
      errors.push(`${context} confidence is outside controlled vocabulary: ${holding.confidence}`);
    }
    validateReviewDates(holding, context);
    if (!Array.isArray(holding.layers) || holding.layers.length === 0) {
      errors.push(`${context} must have at least one layer`);
    }
    if (holding.ticker !== "CASH" && (!Array.isArray(holding.sources) || holding.sources.length === 0)) {
      errors.push(`${context} should have at least one source`);
    }
  }

  if (Math.abs(totalWeight - 100) > 0.0001) {
    errors.push(`holding weights must sum to 100, got ${totalWeight}`);
  }

  const allocationTotal = (data.allocation || []).reduce((sum, item) => sum + (item.value || 0), 0);
  if (Math.abs(allocationTotal - 100) > 0.0001) {
    errors.push(`allocation buckets must sum to 100, got ${allocationTotal}`);
  }

  for (const source of Object.values(data.sources || {})) {
    requireField(source, "label", `source ${source.label || "(unknown)"}`);
    requireField(source, "url", `source ${source.label || "(unknown)"}`);
    try {
      const url = new URL(source.url);
      if (!["http:", "https:"].includes(url.protocol)) {
        errors.push(`source URL must be http/https: ${source.url}`);
      }
    } catch {
      errors.push(`source URL is invalid: ${source.url}`);
    }
  }

  collectSourceIds(data.holdings, "holding");
  collectSourceIds(data.signals, "signal");
  collectSourceIds(data.monitoringQuestions, "monitoring question");

  const seenClaimIds = new Set();
  for (const claim of data.claims || []) {
    const context = `claim ${claim.claim_id || "(unknown)"}`;
    for (const field of [
      "claim_id",
      "source_id",
      "entity",
      "claim",
      "evidence_type",
      "metric",
      "quote_or_excerpt",
      "retrieved_at",
      "confidence"
    ]) {
      requireField(claim, field, context);
    }
    if (seenClaimIds.has(claim.claim_id)) errors.push(`duplicate claim_id: ${claim.claim_id}`);
    seenClaimIds.add(claim.claim_id);
    if (!sourceIds.has(claim.source_id)) {
      errors.push(`${context} references missing source id: ${claim.source_id}`);
    }
    if (!allowedConfidence.has(claim.confidence)) {
      errors.push(`${context} confidence is outside controlled vocabulary: ${claim.confidence}`);
    }
    validateDate(claim.retrieved_at, context, "retrieved_at");
  }

  for (const signal of data.signals || []) {
    const context = `signal ${signal.target || "(unknown)"}`;
    for (const field of [
      "type",
      "severity",
      "target",
      "action",
      "observed_value",
      "confidence",
      "last_reviewed_at",
      "next_review_due",
      "current_value",
      "unit",
      "threshold",
      "direction",
      "status_rule",
      "source_claim_id",
      "text"
    ]) {
      requireField(signal, field, context);
    }
    if (!allowedSeverity.has(signal.severity)) {
      errors.push(`${context} severity is outside controlled vocabulary: ${signal.severity}`);
    }
    if (!allowedConfidence.has(signal.confidence)) {
      errors.push(`${context} confidence is outside controlled vocabulary: ${signal.confidence}`);
    }
    if (!allowedDirection.has(signal.direction)) {
      errors.push(`${context} direction is outside controlled vocabulary: ${signal.direction}`);
    }
    if (!knownClaimIds.has(signal.source_claim_id)) {
      errors.push(`${context} references missing source_claim_id: ${signal.source_claim_id}`);
    }
    validateReviewDates(signal, context);
    if (!Array.isArray(signal.sources) || signal.sources.length === 0) {
      warnings.push(`signal ${signal.target || "(unknown)"} has no sources`);
    }
  }
  for (const question of data.monitoringQuestions || []) {
    const context = `monitoring question ${question.label || "(unknown)"}`;
    for (const field of [
      "label",
      "question",
      "status",
      "observed_value",
      "confidence",
      "last_reviewed_at",
      "next_review_due",
      "current_value",
      "unit",
      "threshold",
      "direction",
      "status_rule",
      "source_claim_id",
      "trigger"
    ]) {
      requireField(question, field, context);
    }
    if (!allowedStatus.has(question.status)) {
      errors.push(`${context} status is outside controlled vocabulary: ${question.status}`);
    }
    if (!allowedConfidence.has(question.confidence)) {
      errors.push(`${context} confidence is outside controlled vocabulary: ${question.confidence}`);
    }
    if (!allowedDirection.has(question.direction)) {
      errors.push(`${context} direction is outside controlled vocabulary: ${question.direction}`);
    }
    if (!knownClaimIds.has(question.source_claim_id)) {
      errors.push(`${context} references missing source_claim_id: ${question.source_claim_id}`);
    }
    validateReviewDates(question, context);
    if (!Array.isArray(question.sources) || question.sources.length === 0) {
      warnings.push(`monitoring question ${question.label || "(unknown)"} has no sources`);
    }
  }
}

if (fs.existsSync(portfolioDataPath) || requirePortfolio) {
  validatePortfolioData(portfolioDataPath);
}

function validatePortfolioData(filePath) {
  if (!fs.existsSync(filePath)) {
    errors.push(`portfolio-data.json is required but missing in ${siteDir}`);
    return;
  }
  let portfolio;
  try {
    portfolio = JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    errors.push(`portfolio-data.json is not valid JSON: ${error.message}`);
    return;
  }
  if (!isObject(portfolio)) {
    errors.push("portfolio-data.json must contain an object");
    return;
  }
  for (const field of ["asOfDate", "baseCurrency", "initialCapitalUsd", "summary", "holdings", "history"]) {
    requireField(portfolio, field, "portfolio");
  }
  validateDate(portfolio.asOfDate, "portfolio", "asOfDate");
  if (portfolio.baseCurrency !== "USD") {
    errors.push(`portfolio baseCurrency must be USD, got ${portfolio.baseCurrency}`);
  }
  if (Number(portfolio.initialCapitalUsd) !== 1000) {
    errors.push(`portfolio initialCapitalUsd must be 1000, got ${portfolio.initialCapitalUsd}`);
  }
  if (!isObject(portfolio.summary)) {
    errors.push("portfolio summary must be an object");
  } else {
    for (const field of ["total_value_usd", "pnl_usd", "return_pct", "daily_pnl_usd", "daily_return_pct"]) {
      if (!Number.isFinite(Number(portfolio.summary[field]))) {
        errors.push(`portfolio summary ${field} must be numeric`);
      }
    }
  }
  if (!Array.isArray(portfolio.holdings) || portfolio.holdings.length !== 14) {
    errors.push(`portfolio holdings must have 14 rows, got ${portfolio.holdings?.length}`);
  } else {
    const tickers = new Set();
    const weightTotal = portfolio.holdings.reduce((sum, holding) => {
      for (const field of ["ticker", "holding_name", "target_weight", "market_value_usd", "price_usd", "pnl_usd"]) {
        requireField(holding, field, `portfolio holding ${holding.ticker || "(unknown)"}`);
      }
      tickers.add(holding.ticker);
      return sum + Number(holding.target_weight || 0);
    }, 0);
    if (!tickers.has("CASH")) errors.push("portfolio holdings must include CASH");
    if (Math.abs(weightTotal - 100) > 0.0001) {
      errors.push(`portfolio target weights must sum to 100, got ${weightTotal}`);
    }
  }
  if (!Array.isArray(portfolio.history) || portfolio.history.length === 0) {
    errors.push("portfolio history must have at least one row");
  }
  for (const [label, plotPath] of Object.entries(portfolio.plots || {})) {
    const cleanPath = String(plotPath).replace(/^\.\//, "");
    if (!fs.existsSync(path.resolve(repoRoot, siteDir, cleanPath))) {
      errors.push(`portfolio plot ${label} is missing: ${plotPath}`);
    }
  }
}

const summary = {
  holdings: data?.holdings?.length || 0,
  totalWeight: (data?.holdings || []).reduce((sum, holding) => sum + (holding.weight || 0), 0),
  allocationTotal: (data?.allocation || []).reduce((sum, item) => sum + (item.value || 0), 0),
  sources: sourceIds.size,
  usedSources: usedSourceIds.length,
  claims: data?.claims?.length || 0,
  signals: data?.signals?.length || 0,
  monitoringQuestions: data?.monitoringQuestions?.length || 0,
  portfolio: fs.existsSync(portfolioDataPath) ? "present" : "missing",
  warnings,
  errors
};

console.log(JSON.stringify(summary, null, 2));

if (errors.length > 0) {
  process.exitCode = 1;
}
