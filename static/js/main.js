let currentResults = [];
let currentKeyword = "";

const form       = document.getElementById("search-form");
const searchBtn  = document.getElementById("search-btn");
const statusBar  = document.getElementById("status-bar");
const statusText = document.getElementById("status-text");
const errorToast = document.getElementById("error-toast");
const errorMsg   = document.getElementById("error-msg");
const resultsArea= document.getElementById("results-area");
const emptyState = document.getElementById("empty-state");
const tableBody  = document.getElementById("table-body");
const countEl    = document.getElementById("result-count");
const maxInput   = document.getElementById("max-results");
const maxLabel   = document.getElementById("max-value");

maxInput.addEventListener("input", () => {
  maxLabel.textContent = maxInput.value + " results";
  const pct = ((maxInput.value - maxInput.min) / (maxInput.max - maxInput.min)) * 100;
  maxInput.style.setProperty("--pct", pct + "%");
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const keyword     = document.getElementById("keyword").value.trim();
  const location    = document.getElementById("location").value.trim();
  const max_results = parseInt(maxInput.value);

  if (!keyword) return;
  currentKeyword = keyword + (location ? " " + location : "");

  setLoading(true);
  hideError();

  const msgs = [
    "Opening browser…",
    "Loading Google Maps…",
    "Scrolling results list…",
    "Visiting each listing…",
    "Extracting data fields…",
    "Almost done…",
  ];
  let mi = 0;
  const ticker = setInterval(() => {
    if (mi < msgs.length) statusText.textContent = msgs[mi++];
  }, 9000);

  try {
    const res  = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword, location, max_results }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Search failed");
    currentResults = data.results;
    renderTable(currentResults);
  } catch (err) {
    showError(err.message);
  } finally {
    clearInterval(ticker);
    setLoading(false);
  }
});

function renderTable(data) {
  tableBody.innerHTML = "";
  if (!data || !data.length) {
    emptyState.style.display = "block";
    resultsArea.style.display = "none";
    return;
  }
  emptyState.style.display = "none";
  resultsArea.style.display = "block";
  countEl.textContent = data.length;

  data.forEach((r, i) => {
    const tr = document.createElement("tr");
    tr.className = "fade-in";
    tr.style.animationDelay = (i * 0.03) + "s";
    tr.innerHTML = `
      <td><strong>${esc(r.name)}</strong></td>
      <td><span class="pill">${esc(r.category)}</span></td>
      <td>
        <div style="font-weight:600">${r.rating !== "N/A" ? r.rating : "—"}</div>
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

function setLoading(on) {
  searchBtn.disabled = on;
  statusBar.style.display = on ? "flex" : "none";
  if (on) statusText.textContent = "Opening browser…";
  searchBtn.innerHTML = on
    ? "Scraping… (30–90s)"
    : '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg> Scrape Google Maps';
}

function showError(msg) { errorToast.style.display = "flex"; errorMsg.textContent = msg; }
function hideError()    { errorToast.style.display = "none"; }

async function exportData(format) {
  if (!currentResults.length) return;
  const endpoint = format === "excel" ? "/api/export/excel" : "/api/export/pdf";
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results: currentResults, keyword: currentKeyword }),
    });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url;
    a.download = `${currentKeyword.replace(/\s+/g,"_")}_results.${format==="excel"?"xlsx":"pdf"}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showError("Export failed: " + err.message);
  }
}
