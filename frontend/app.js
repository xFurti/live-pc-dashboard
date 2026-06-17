/* ── Live PC Health Dashboard — frontend logic ───────────────────────────────
 *
 * Responsibilities:
 *   1. Open a WebSocket to the backend's /ws endpoint.
 *   2. On each incoming JSON sample, update the big % numbers AND push the
 *      new value into the corresponding Chart.js line chart.
 *   3. Handle connection state (status badge + auto-reconnect).
 *
 * We keep a rolling window of the last MAX_POINTS samples so the chart
 * scrolls like a heart-rate monitor instead of growing forever.
 */

// ── Config ──────────────────────────────────────────────────────────────────
const MAX_POINTS = 30; // how many recent samples to show on each chart

// ── DOM references ──────────────────────────────────────────────────────────
const statusEl    = document.getElementById("status");
const cpuValueEl  = document.getElementById("cpu-value");
const ramValueEl  = document.getElementById("ram-value");
const ramDetailEl = document.getElementById("ram-detail");
const diskValueEl = document.getElementById("disk-value");
const diskDetailEl= document.getElementById("disk-detail");
const lastUpdateEl= document.getElementById("last-update");

// ── Chart factory ───────────────────────────────────────────────────────────
// All three charts share the same shape: a line that grows from left to right.
// We pre-fill the labels with empty slots so the chart is a fixed width.
function makeChart(canvasId, color) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  return new Chart(ctx, {
    type: "line",
    data: {
      labels: Array(MAX_POINTS).fill(""),          // empty x-axis labels
      datasets: [{
        data: Array(MAX_POINTS).fill(null),         // start with no data
        borderColor: color,
        backgroundColor: color + "33",              // 33 = ~20% opacity hex
        fill: true,
        tension: 0.3,                                // smooth curves
        pointRadius: 0,                              // hide dots
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      animation: false,                              // real-time = no animation
      scales: {
        y: { min: 0, max: 100, ticks: { color: "#8a8f98" }, grid: { color: "#2a2e37" } },
        x: { display: false },                       // hide x-axis labels
      },
      plugins: { legend: { display: false } },
    },
  });
}

const cpuChart  = makeChart("cpu-chart",  "#38bdf8");
const ramChart  = makeChart("ram-chart",  "#f472b6");
const diskChart = makeChart("disk-chart", "#fbbf24");

// ── Helper: push a new sample into a chart, dropping the oldest ──────────────
function pushSample(chart, value) {
  const data = chart.data.datasets[0].data;
  data.push(value);
  if (data.length > MAX_POINTS) data.shift();       // keep the window fixed
  chart.update("none");                              // "none" = skip animation
}

// ── Helper: format "now" as a short HH:MM:SS timestamp ───────────────────────
function clockNow() {
  return new Date().toLocaleTimeString();
}

// ── WebSocket connection ─────────────────────────────────────────────────────
function connect() {
  // Build the ws:// URL from the current page so it works on any host/port.
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    statusEl.textContent = "● Connected";
    statusEl.className = "status connected";
  };

  ws.onmessage = (event) => {
    // Every message is a JSON object with cpu_percent, ram_*, disk_*, timestamp.
    const d = JSON.parse(event.data);

    // Update the big number displays.
    cpuValueEl.textContent  = `${d.cpu_percent.toFixed(1)}%`;
    ramValueEl.textContent  = `${d.ram_percent.toFixed(1)}%`;
    ramDetailEl.textContent = `${d.ram_used_gb} / ${d.ram_total_gb} GB`;
    diskValueEl.textContent = `${d.disk_percent.toFixed(1)}%`;
    diskDetailEl.textContent= `${d.disk_used_gb} / ${d.disk_total_gb} GB`;

    // Push the new sample into each chart.
    pushSample(cpuChart,  d.cpu_percent);
    pushSample(ramChart,  d.ram_percent);
    pushSample(diskChart, d.disk_percent);

    lastUpdateEl.textContent = `updated ${clockNow()}`;
  };

  ws.onclose = () => {
    statusEl.textContent = "● Disconnected";
    statusEl.className = "status disconnected";
    // Auto-reconnect after 2 seconds so the dashboard recovers if you restart the server.
    setTimeout(connect, 2000);
  };

  ws.onerror = () => ws.close();   // onclose will handle the reconnect
}

// Kick things off.
connect();
