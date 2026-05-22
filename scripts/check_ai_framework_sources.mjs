import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const repoRoot = process.cwd();
const siteDirArgIndex = process.argv.indexOf("--site-dir");
const siteDir =
  siteDirArgIndex >= 0 && process.argv[siteDirArgIndex + 1]
    ? process.argv[siteDirArgIndex + 1]
    : path.join("site", "ai-framework");
const dataPath = path.resolve(repoRoot, siteDir, "research-data.js");
const code = fs.readFileSync(dataPath, "utf8");
const sandbox = { window: {} };

vm.runInNewContext(code, sandbox, { filename: dataPath });

const sources = sandbox.window.AI_FRAMEWORK_DATA?.sources || {};
const timeoutMs = 8000;
const failOnError = process.argv.includes("--fail-on-error");
const failOnDegraded = process.argv.includes("--fail-on-degraded");

async function fetchWithTimeout(url, method) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      method,
      redirect: "follow",
      signal: controller.signal,
      headers:
        method === "GET"
          ? {
              Range: "bytes=0-2048",
              "User-Agent": "quant-learn-source-audit/1.0"
            }
          : {
              "User-Agent": "quant-learn-source-audit/1.0"
            }
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function checkSource([sourceId, source]) {
  const started = Date.now();

  try {
    let response;
    let method = "HEAD";
    let firstError;
    try {
      response = await fetchWithTimeout(source.url, "HEAD");
    } catch (error) {
      firstError = error;
    }
    if (!response || !response.ok) {
      try {
        response = await fetchWithTimeout(source.url, "GET");
        method = "GET";
      } catch (error) {
        if (!response) throw firstError || error;
        // Keep the original HEAD response if GET fallback also fails after a response.
      }
    }
    return {
      source_id: sourceId,
      label: source.label,
      status: response.status,
      ok: response.ok,
      method,
      elapsed_ms: Date.now() - started,
      url: source.url,
      final_url: response.url,
      note: response.status === 403 ? "bot_or_permission_block_possible" : ""
    };
  } catch (error) {
    return {
      source_id: sourceId,
      label: source.label,
      status: null,
      ok: false,
      elapsed_ms: Date.now() - started,
      url: source.url,
      final_url: null,
      error: error.name === "AbortError" ? "timeout" : error.message
    };
  }
}

const results = await Promise.all(Object.entries(sources).map(checkSource));
const summary = {
  checked_at: new Date().toISOString(),
  source_count: results.length,
  ok_count: results.filter((result) => result.ok).length,
  blocked_or_forbidden_count: results.filter((result) => result.status === 403).length,
  error_count: results.filter((result) => !result.ok && result.status !== 403).length,
  results
};

console.log(JSON.stringify(summary, null, 2));

if (failOnError && summary.error_count > 0) {
  process.exitCode = 1;
}

if (failOnDegraded && summary.error_count + summary.blocked_or_forbidden_count > 0) {
  process.exitCode = 1;
}
