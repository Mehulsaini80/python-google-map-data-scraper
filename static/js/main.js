// ── State ────────────────────────────────────────────────────────
let currentResults = [];
let currentLabel   = "";

// ── DOM refs ─────────────────────────────────────────────────────
const form         = document.getElementById("search-form");
const searchBtn    = document.getElementById("search-btn");
const statusBar    = document.getElementById("status-bar");
const statusText   = document.getElementById("status-text");
const statusDetail = document.getElementById("status-detail");
const errorToast   = document.getElementById("error-toast");
const errorMsg     = document.getElementById("error-msg");
const resultsArea  = document.getElementById("results-area");
const emptyState   = document.getElementById("empty-state");
const tableBody    = document.getElementById("table-body");
const countEl      = document.getElementById("result-count");
const maxInput     = document.getElementById("max-results");
const maxLabel     = document.getElementById("max-value");
const dedupStats   = document.getElementById("dedup-stats");
const dbCountEl    = document.getElementById("db-count");

// ── Load DB stats on page load ────────────────────────────────────
async function loadDBStats() {
  try {
    const res  = await fetch("/api/db/stats");
    const data = await res.json();
    dbCountEl.textContent = data.total_in_db.toLocaleString();
  } catch { dbCountEl.textContent = "?"; }
}
loadDBStats();

// ── Slider ───────────────────────────────────────────────────────
maxInput.addEventListener("input", () => {
  maxLabel.textContent = maxInput.value + " results";
  const pct = ((maxInput.value - maxInput.min) / (maxInput.max - maxInput.min)) * 100;
  maxInput.style.setProperty("--pct", pct + "%");
});

// ── Add / remove keyword rows ─────────────────────────────────────
function addKeyword() {
  const list = document.getElementById("keyword-list");
  const row  = document.createElement("div");
  row.className = "keyword-row fade-in";
  row.innerHTML = `
    <input class="kw-input" type="text" placeholder="e.g. CA in Mansarovar Jaipur"/>
    <button type="button" class="btn-remove-kw" onclick="removeKeyword(this)" title="Remove">✕</button>
  `;
  list.appendChild(row);
}

function removeKeyword(btn) {
  const rows = document.querySelectorAll(".keyword-row");
  if (rows.length <= 1) {
    // Clear the last one instead of removing
    btn.closest(".keyword-row").querySelector(".kw-input").value = "";
    return;
  }
  btn.closest(".keyword-row").remove();
}

// ── Get all keyword values ────────────────────────────────────────
function getKeywords() {
  return Array.from(document.querySelectorAll(".kw-input"))
    .map(i => i.value.trim())
    .filter(Boolean);
}

// ── Search ────────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const keywords    = getKeywords();
  const max_results = parseInt(maxInput.value);

  if (!keywords.length) {
    showError("Please enter at least one search keyword.");
    return;
  }

  currentLabel = keywords.join(", ");
  setLoading(true, keywords.length);
  hideError();
  hideDedupStats();
  emptyState.style.display   = "none";
  resultsArea.style.display  = "none";

  // Rotating status messages
  const msgs = [
    "Opening browser…",
    "Loading Google Maps…",
    "Scrolling results list…",
    "Collecting listing URLs…",
    "Visiting each place page…",
    "Extracting phone & address…",
    "Checking for duplicates…",
    "Saving to database…",
    "Almost done…",
  ];
  let mi = 0;
  const ticker = setInterval(() => {
    if (mi < msgs.length) {
      statusText.textContent  = msgs[mi++];
      statusDetail.textContent = `Processing ${keywords.length} keyword(s) — ${max_results} results each`;
    }
  }, 12000);

  try {
    const res  = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords, max_results }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Search failed");

    currentResults = data.results;

    // Show dedup stats
    showDedupStats(data);

    // Render table
    if (currentResults.length > 0) {
      renderTable(currentResults);
    } else {
      emptyState.style.display = "block";
    }

    // Refresh DB count
    dbCountEl.textContent = data.total_in_db
      ? data.total_in_db.toLocaleString()
      : (parseInt(dbCountEl.textContent || "0") + data.count).toLocaleString();
    loadDBStats();

  } catch (err) {
    showError(err.message);
  } finally {
    clearInterval(ticker);
    setLoading(false);
  }
});

// ── Show dedup stats ──────────────────────────────────────────────
function showDedupStats(data) {
  document.getElementById("stat-scraped").textContent = data.total_scraped || 0;
  document.getElementById("stat-new").textContent     = data.count || 0;
  document.getElementById("stat-dupes").textContent   = data.duplicates_skipped || 0;
  document.getElementById("stat-db").textContent      = data.total_in_db || 0;

  // Per-query breakdown
  const breakdown = document.getElementById("query-breakdown");
  breakdown.innerHTML = "";
  if (data.query_stats && data.query_stats.length > 0) {
    data.query_stats.forEach(q => {
      const row = document.createElement("div");
      row.className = "query-row fade-in";
      row.innerHTML = `
        <span class="query-name">🔍 ${esc(q.query)}</span>
        <div class="query-pills">
          <span class="qpill">${q.scraped} scraped</span>
          <span class="qpill green">${q.new} new</span>
          <span class="qpill amber">${q.skipped} skipped</span>
        </div>
      `;
      breakdown.appendChild(row);
    });
  }

  dedupStats.style.display = "block";
}

function hideDedupStats() {
  dedupStats.style.display = "none";
}

// ── Render results table ──────────────────────────────────────────
function renderTable(data) {
  tableBody.innerHTML = "";
  resultsArea.style.display = "block";
  countEl.textContent = data.length;

  data.forEach((r, i) => {
    const tr = document.createElement("tr");
    tr.className = "fade-in";
    tr.style.animationDelay = Math.min(i * 0.02, 1) + "s";
    tr.innerHTML = `
      <td class="row-num">${i + 1}</td>
      <td><strong>${esc(r.name)}</strong></td>
      <td><span class="pill">${esc(r.category)}</span></td>
      <td>
        <div style="font-weight:600;font-size:13px">${r.rating !== "N/A" ? r.rating : "—"}</div>
        <div class="stars">${stars(r.rating)}</div>
      </td>
      <td style="font-size:12px">${r.reviews && r.reviews !== "N/A" ? Number(r.reviews).toLocaleString() : "—"}</td>
      <td>${r.phone !== "N/A" ? `<a class="phone-link" href="tel:${r.phone}">${esc(r.phone)}</a>` : '<span class="no-data">N/A</span>'}</td>
      <td class="address-cell">${esc(r.address)}</td>
      <td>${r.website !== "N/A" ? `<a class="website-link" href="${r.website}" target="_blank">&#8599; Visit</a>` : '<span class="no-data">—</span>'}</td>
    `;
    tableBody.appendChild(tr);
  });
}

// ── Clear DB ──────────────────────────────────────────────────────
async function clearDB() {
  if (!confirm("Clear ALL data from the database? This cannot be undone.")) return;
  try {
    await fetch("/api/db/clear", { method: "POST" });
    dbCountEl.textContent = "0";
    alert("Database cleared successfully.");
  } catch { alert("Failed to clear database."); }
}

// ── Export current results ────────────────────────────────────────
async function exportData(format) {
  if (!currentResults.length) return;
  const endpoint = format === "excel" ? "/api/export/excel" : "/api/export/pdf";
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results: currentResults, keyword: currentLabel }),
    });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url;
    a.download = `${currentLabel.replace(/\s+/g,"_").slice(0,40)}_results.${format==="excel"?"xlsx":"pdf"}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showError("Export failed: " + err.message);
  }
}

// ── Helpers ───────────────────────────────────────────────────────
function esc(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}

function stars(rating) {
  if (!rating || rating === "N/A") return "";
  const full = Math.round(parseFloat(rating));
  return "★".repeat(Math.min(full,5)) + "☆".repeat(Math.max(0,5-full));
}

function setLoading(on, kwCount = 1) {
  searchBtn.disabled = on;
  statusBar.style.display = on ? "flex" : "none";
  if (on) {
    statusText.textContent   = "Opening browser…";
    statusDetail.textContent = `Processing ${kwCount} keyword(s)`;
  }
  searchBtn.innerHTML = on
    ? `<div class="spinner" style="width:16px;height:16px;border-width:2px"></div> Scraping ${kwCount} keyword(s)…`
    : `<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg> Scrape Google Maps`;
}

function showError(msg) { errorToast.style.display="flex"; errorMsg.textContent=msg; }
function hideError()    { errorToast.style.display="none"; } 