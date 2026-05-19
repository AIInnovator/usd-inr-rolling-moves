const DATA_PATHS = {
  manifest: "data/manifest.json",
  summary: "data/usd_inr_move_analysis.json",
  rolling: "data/usd_inr_rolling_moves.json",
  daily: "data/usd_inr_daily.json",
};

const state = {
  manifest: null,
  summary: null,
  rolling: [],
  daily: [],
  selectedPeriod: "1Y",
  basis: "return",
};

const $ = (id) => document.getElementById(id);

function formatPercent(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${(value * 100).toFixed(digits)}%`;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function compactDate(value) {
  if (!value) return "--";
  const parsedDate = new Date(`${value}T00:00:00Z`);
  return parsedDate.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  });
}

function valueClass(value) {
  return value >= 0 ? "positive" : "negative";
}

function getSelectedSummary() {
  return state.summary.rolling_return_summary.find((item) => item.label === state.selectedPeriod);
}

function getSelectedSeries() {
  return state.rolling.filter((item) => item.label === state.selectedPeriod);
}

async function loadJson(path) {
  const response = await fetch(`${path}?v=${Date.now()}`);
  if (!response.ok) {
    throw new Error(`Unable to load ${path}: HTTP ${response.status}`);
  }
  return response.json();
}

async function loadData() {
  const [manifest, summary, rolling, daily] = await Promise.all([
    loadJson(DATA_PATHS.manifest),
    loadJson(DATA_PATHS.summary),
    loadJson(DATA_PATHS.rolling),
    loadJson(DATA_PATHS.daily),
  ]);
  state.manifest = manifest;
  state.summary = summary;
  state.rolling = rolling;
  state.daily = daily;
}

function isStale(endDate) {
  const latest = new Date(`${endDate}T00:00:00Z`);
  const today = new Date();
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const ageDays = (todayUtc - latest.getTime()) / 86400000;
  return ageDays > 2;
}

function renderStatus() {
  const statusPanel = document.querySelector(".status-panel");
  const generatedAt = new Date(state.manifest.generated_at);
  const updated = generatedAt.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
  statusPanel.classList.remove("loaded", "stale", "error");
  statusPanel.classList.add(isStale(state.manifest.end_date) ? "stale" : "loaded");
  $("dataStatus").textContent = `Data as of ${compactDate(state.manifest.end_date)} | updated ${updated}`;
}

function renderKpis() {
  const perf = state.summary.performance_summary;
  const latest = state.daily[state.daily.length - 1];

  $("dateRange").textContent = `${compactDate(perf.start_date)} - ${compactDate(perf.end_date)}`;
  $("rowCount").textContent = `${perf.observations.toLocaleString("en-US")} observations`;
  $("latestClose").textContent = formatNumber(latest.close, 3);
  $("cagr").textContent = formatPercent(perf.cagr);
  $("volatility").textContent = formatPercent(perf.annualized_volatility);
  $("spotMeta").textContent = `${formatNumber(state.daily[0].close, 2)} to ${formatNumber(latest.close, 2)}`;
}

function renderControls() {
  const buttonWrap = $("periodButtons");
  buttonWrap.innerHTML = "";

  state.summary.rolling_return_summary.forEach((period) => {
    const button = document.createElement("button");
    button.className = `period-button${period.label === state.selectedPeriod ? " active" : ""}`;
    button.type = "button";
    button.dataset.period = period.label;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", period.label === state.selectedPeriod ? "true" : "false");
    button.innerHTML = `<strong>${period.label}</strong><span>${formatPercent(period.latest?.return)}</span>`;
    button.addEventListener("click", () => {
      state.selectedPeriod = period.label;
      renderDashboard();
    });
    buttonWrap.appendChild(button);
  });

  document.querySelectorAll(".basis-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.basis === state.basis);
    button.onclick = () => {
      state.basis = button.dataset.basis;
      document.querySelectorAll(".basis-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderDashboard();
    };
  });
}

function renderSelectedReadout() {
  const summary = getSelectedSummary();
  const averageKey = state.basis === "return" ? "average_return" : "average_annualized_return";
  const medianKey = state.basis === "return" ? "median_return" : "median_annualized_return";
  const latestValue = summary.latest?.[state.basis];

  $("selectedAverage").textContent = formatPercent(summary[averageKey]);
  $("selectedMedian").textContent = formatPercent(summary[medianKey]);
  $("selectedPositive").textContent = formatPercent(summary.positive_period_pct);
  $("selectedLatest").textContent = formatPercent(latestValue);
  $("lineTitle").textContent = `${summary.label} Rolling ${state.basis === "return" ? "Window" : "Annualized"} Move`;
  $("histTitle").textContent = `${summary.label} Move Histogram`;
  $("lineMeta").textContent = `${summary.observations.toLocaleString("en-US")} windows`;
}

function scaleLinear(domainMin, domainMax, rangeMin, rangeMax) {
  if (domainMin === domainMax) return () => (rangeMin + rangeMax) / 2;
  return (value) => rangeMin + ((value - domainMin) / (domainMax - domainMin)) * (rangeMax - rangeMin);
}

function downsample(values, maxPoints = 850) {
  if (values.length <= maxPoints) return values;
  const step = Math.ceil(values.length / maxPoints);
  return values.filter((_, index) => index % step === 0 || index === values.length - 1);
}

function renderLineChart(target, data, options) {
  const width = 980;
  const height = options.height || 380;
  const pad = { top: 16, right: 28, bottom: 38, left: 58 };
  const values = data.map((item) => item.value);
  const includeZero = options.includeZero !== false;
  const min = includeZero ? Math.min(...values, 0) : Math.min(...values);
  const max = includeZero ? Math.max(...values, 0) : Math.max(...values);
  const x = scaleLinear(0, data.length - 1, pad.left, width - pad.right);
  const y = scaleLinear(min, max, height - pad.bottom, pad.top);
  const visible = downsample(data);
  const stride = Math.ceil(data.length / visible.length);
  const points = visible.map((item, index) => `${x(index * stride)},${y(item.value)}`).join(" ");
  const zeroY = y(0);
  const last = data[data.length - 1];
  const first = data[0];
  const formatValue = options.valueFormatter || formatPercent;

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="${options.gradientId}" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#f4b84a" />
          <stop offset="56%" stop-color="#45d6b5" />
          <stop offset="100%" stop-color="#84d46f" />
        </linearGradient>
      </defs>
      ${[0.25, 0.5, 0.75].map((tick) => `<line class="grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${pad.top + (height - pad.top - pad.bottom) * tick}" y2="${pad.top + (height - pad.top - pad.bottom) * tick}" />`).join("")}
      <line class="zero-line" x1="${pad.left}" x2="${width - pad.right}" y1="${zeroY}" y2="${zeroY}" />
      <polyline points="${points}" fill="none" stroke="url(#${options.gradientId})" stroke-width="3.3" vector-effect="non-scaling-stroke" />
      <circle cx="${x(data.length - 1)}" cy="${y(last.value)}" r="5" fill="#f4ead8" />
      <text class="chart-label" x="${pad.left}" y="${height - 12}">${compactDate(first.date)}</text>
      <text class="chart-label" text-anchor="end" x="${width - pad.right}" y="${height - 12}">${compactDate(last.date)}</text>
      <text class="chart-label" x="${pad.left}" y="${pad.top + 12}">${formatValue(max)}</text>
      <text class="chart-label" x="${pad.left}" y="${height - pad.bottom - 4}">${formatValue(min)}</text>
    </svg>
  `;
}

function renderHistogram(target, values) {
  const width = 620;
  const height = 280;
  const pad = { top: 18, right: 18, bottom: 32, left: 42 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const bucketCount = 24;
  const buckets = Array.from({ length: bucketCount }, () => 0);
  values.forEach((value) => {
    const index = Math.min(bucketCount - 1, Math.floor(((value - min) / (max - min || 1)) * bucketCount));
    buckets[index] += 1;
  });
  const x = scaleLinear(0, bucketCount, pad.left, width - pad.right);
  const y = scaleLinear(0, Math.max(...buckets), height - pad.bottom, pad.top);
  const zeroX = x(((0 - min) / (max - min || 1)) * bucketCount);

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      ${buckets.map((count, index) => {
        const barX = x(index) + 2;
        const barW = Math.max(2, x(index + 1) - x(index) - 4);
        const barY = y(count);
        const barH = height - pad.bottom - barY;
        const bucketValue = min + ((max - min) * index) / bucketCount;
        const color = bucketValue >= 0 ? "#45d6b5" : "#e26457";
        return `<rect x="${barX}" y="${barY}" width="${barW}" height="${barH}" fill="${color}" opacity="0.78" />`;
      }).join("")}
      <line class="zero-line" x1="${zeroX}" x2="${zeroX}" y1="${pad.top}" y2="${height - pad.bottom}" />
      <text class="chart-label" x="${pad.left}" y="${height - 10}">${formatPercent(min)}</text>
      <text class="chart-label" text-anchor="end" x="${width - pad.right}" y="${height - 10}">${formatPercent(max)}</text>
    </svg>
  `;
}

function renderWindowTable() {
  const summary = getSelectedSummary();
  const rows = [
    ["Best", summary.best],
    ["Worst", summary.worst],
    ["Latest", summary.latest],
  ];
  $("windowRows").innerHTML = rows
    .map(([label, row]) => {
      const value = row[state.basis];
      return `
        <tr>
          <td>${label}</td>
          <td>${compactDate(row.start_date)}<br>${compactDate(row.end_date)}</td>
          <td class="${valueClass(value)}">${formatPercent(value)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderPeriodCards() {
  $("periodCards").innerHTML = state.summary.rolling_return_summary
    .map((period) => {
      const latest = period.latest?.return;
      return `
        <article class="period-card">
          <header>
            <h3>${period.label}</h3>
            <span class="pill">${period.observations.toLocaleString("en-US")}</span>
          </header>
          <div class="latest ${valueClass(latest)}">${formatPercent(latest)}</div>
          <div class="mini-stats">
            <span><strong>${formatPercent(period.average_return)}</strong>Average</span>
            <span><strong>${formatPercent(period.median_return)}</strong>Median</span>
            <span><strong>${formatPercent(period.percentile_5)}</strong>5th pct</span>
            <span><strong>${formatPercent(period.percentile_95)}</strong>95th pct</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderCharts() {
  const selectedSeries = getSelectedSeries();
  const lineData = selectedSeries.map((item) => ({ date: item.end_date, value: item[state.basis] }));
  renderLineChart($("lineChart"), lineData, { gradientId: "rollingGradient", height: 420 });
  renderHistogram($("histogram"), selectedSeries.map((item) => item[state.basis]));
  const spotData = state.daily.map((item) => ({ date: item.date, value: item.close }));
  renderLineChart($("spotChart"), spotData, {
    gradientId: "spotGradient",
    height: 330,
    includeZero: false,
    valueFormatter: (value) => formatNumber(value, 2),
  });
}

function renderDashboard() {
  renderStatus();
  renderKpis();
  renderControls();
  renderSelectedReadout();
  renderCharts();
  renderWindowTable();
  renderPeriodCards();
}

async function init() {
  try {
    await loadData();
    renderDashboard();
  } catch (error) {
    document.querySelector(".status-panel").classList.add("error");
    $("dataStatus").textContent = error.message;
    console.error(error);
  }
}

init();
