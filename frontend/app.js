/* ════════════════════════════════════════════════════════════════════════════
   LIVE PC HEALTH · MISSION CONTROL — frontend logic
   ────────────────────────────────────────────────────────────────────────────
   Responsibilities:
     1. Open a WebSocket to the backend's /ws endpoint.
     2. On each sample: animate the gauge arcs, the % numbers, the sparklines,
        and the two live process tables (with neon bars).
     3. Handle connection state (status badge + auto-reconnect).

   New concepts vs. the old version:
     - SVG radial gauges via stroke-dasharray / stroke-dashoffset (setGauge)
     - Smooth count-up number animation (animateNumber)
     - Threshold color classes (.low / .mid / .high) applied to gauges + numbers
     - Neon inline bars in the process table (renderProcessTable)
   ════════════════════════════════════════════════════════════════════════════ */

// ── Config ──────────────────────────────────────────────────────────────────
const MAX_POINTS = 30; // sparkline rolling-window size

// ── DOM references (all 11 load-bearing IDs preserved) ──────────────────────
const statusEl     = document.getElementById("status");
const cpuValueEl   = document.getElementById("cpu-value");
const ramValueEl   = document.getElementById("ram-value");
const ramDetailEl  = document.getElementById("ram-detail");
const diskValueEl  = document.getElementById("disk-value");
const diskDetailEl = document.getElementById("disk-detail");
const lastUpdateEl = document.getElementById("last-update");
const topCpuEl     = document.getElementById("top-cpu-table");
const topMemEl     = document.getElementById("top-memory-table");

// ── Gauge elements: one .gauge-fill circle per card, found via data-metric ──
const cpuCard  = document.querySelector('.card[data-metric="cpu"]');
const ramCard  = document.querySelector('.card[data-metric="ram"]');
const diskCard = document.querySelector('.card[data-metric="disk"]');
const cpuGaugeFill  = cpuCard.querySelector(".gauge-fill");
const ramGaugeFill  = ramCard.querySelector(".gauge-fill");
const diskGaugeFill = diskCard.querySelector(".gauge-fill");

// ════════════════════════════════════════════════════════════════════════════
// SVG RADIAL GAUGE — the core "Mission Control" trick
// ════════════════════════════════════════════════════════════════════════════
//
// A circle's stroke is drawn along its perimeter. We can render only PART of
// that perimeter using two SVG attributes:
//
//   stroke-dasharray  = "dashLength gapLength"  → pattern of visible/invisible
//   stroke-dashoffset = N                       → where to start the pattern
//
// Our gauge is a 270° arc (speedometer), i.e. 75% of a full circle.
//   circle r = 52  →  full circumference C = 2 * π * 52 ≈ 326.726
//   arc length L = C * 0.75 ≈ 245.04
//
// We set dasharray = "L C" so only the first 270° is ever visible, then use
// dashoffset to "reveal" a fraction of that arc proportional to the % value:
//   0%   → offset = L   (the whole arc is pushed into the gap = nothing shown)
//   100% → offset = 0   (the whole arc is shown)
//   in between → offset = L * (1 - percent/100)
//
// The <svg> is rotated 135° in CSS so the missing 90° wedge sits at the bottom,
// giving the classic gauge look. The CSS `transition: stroke-dashoffset` makes
// the needle sweep smoothly between ticks.
const GAUGE_R = 52;
const GAUGE_C = 2 * Math.PI * GAUGE_R;     // full circumference ≈ 326.726
const GAUGE_ARC = GAUGE_C * 0.75;          // 270° arc length  ≈ 245.04

// Initialise every gauge to an empty 270° track.
[cpuGaugeFill, ramGaugeFill, diskGaugeFill].forEach((el) => {
  el.setAttribute("stroke-dasharray", `${GAUGE_ARC} ${GAUGE_C}`);
  el.setAttribute("stroke-dashoffset", GAUGE_ARC); // start empty
});

/**
 * Set a gauge's fill arc to the given percentage (0–100) and apply the
 * threshold color class (.low / .mid / .high) to both the arc and its card.
 */
function setGauge(cardEl, fillCircleEl, percent) {
  const clamped = Math.max(0, Math.min(100, percent));
  // Reveal a fraction of the 270° arc.
  const offset = GAUGE_ARC * (1 - clamped / 100);
  fillCircleEl.setAttribute("stroke-dashoffset", offset);

  // Threshold colors on both the arc (via the circle) and the number (via the card).
  fillCircleEl.classList.remove("low", "mid", "high");
  cardEl.classList.remove("low", "mid", "high");
  const tier = clamped > 85 ? "high" : clamped >= 60 ? "mid" : "low";
  fillCircleEl.classList.add(tier);
  cardEl.classList.add(tier);
}

// ════════════════════════════════════════════════════════════════════════════
// SMOOTH NUMBER ANIMATION
// ════════════════════════════════════════════════════════════════════════════
//
// Instead of snapping the % to the new value each tick, we interpolate from
// the previously displayed value to the new one over ~400ms using
// requestAnimationFrame. Each element remembers its current value on a
// private property so successive ticks chain smoothly.
function animateNumber(el, target, suffix = "%") {
  const start = el._currentValue ?? 0;
  if (Math.abs(target - start) < 0.05) {
    // No meaningful change — just write the value and bail out.
    el._currentValue = target;
    el.textContent = `${target.toFixed(1)}${suffix}`;
    return;
  }
  const duration = 400;
  const startTime = performance.now();

  function step(now) {
    const t = Math.min(1, (now - startTime) / duration);
    // easeOutCubic — decelerates nicely.
    const eased = 1 - Math.pow(1 - t, 3);
    const value = start + (target - start) * eased;
    el.textContent = `${value.toFixed(1)}${suffix}`;
    if (t < 1) {
      requestAnimationFrame(step);
    } else {
      el._currentValue = target; // remember for the next tick
    }
  }
  requestAnimationFrame(step);
}

// ════════════════════════════════════════════════════════════════════════════
// SPARKLINES (Chart.js, restyled thin + subtle)
// ════════════════════════════════════════════════════════════════════════════
function makeChart(canvasId, color) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  return new Chart(ctx, {
    type: "line",
    data: {
      labels: Array(MAX_POINTS).fill(""),
      datasets: [{
        data: Array(MAX_POINTS).fill(null),
        borderColor: color,
        backgroundColor: color + "22",   // very faint fill under the line
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 1.5,
      }],
    },
    options: {
      responsive: true,
      animation: false,
      scales: {
        y: { min: 0, max: 100, display: false },  // hide axis for a clean sparkline
        x: { display: false },
      },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}

// New palette matches the CSS per-metric variables.
const cpuChart  = makeChart("cpu-chart",  "#38bdf8"); // cyan
const ramChart  = makeChart("ram-chart",  "#a78bfa"); // violet
const diskChart = makeChart("disk-chart", "#34d399"); // emerald

// Push a sample, drop the oldest — unchanged rolling-window logic.
function pushSample(chart, value) {
  const data = chart.data.datasets[0].data;
  data.push(value);
  if (data.length > MAX_POINTS) data.shift();
  chart.update("none");
}

// ════════════════════════════════════════════════════════════════════════════
// PROCESS TABLES — live rebuild with neon inline bars
// ════════════════════════════════════════════════════════════════════════════
//
// `barField` tells us which value drives the bar width:
//   "cpu_percent"    for the Top-by-CPU table
//   "memory_percent" for the Top-by-RAM  table
// The bar is an absolutely-positioned div behind the name text (see CSS).
function renderProcessTable(tableBodyEl, rows, barField) {
  const html = rows.map((r) => {
    const barWidth = Math.max(2, Math.min(100, r[barField])); // clamp 2–100%
    return `
      <tr>
        <td>${r.pid}</td>
        <td class="proc-name-cell">
          <div class="proc-bar" style="width:${barWidth}%"></div>
          <span>${escapeHtml(r.name)}</span>
        </td>
        <td class="num big-num">${r.cpu_percent.toFixed(1)}</td>
        <td class="num">${r.memory_percent.toFixed(1)}</td>
      </tr>`;
  }).join("");
  tableBodyEl.innerHTML = html;
}

// Guard against odd characters in process names (e.g. <, >, &).
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Helper: short HH:MM:SS timestamp ────────────────────────────────────────
function clockNow() {
  return new Date().toLocaleTimeString();
}

// ════════════════════════════════════════════════════════════════════════════
// WEBSOCKET CONNECTION (unchanged reconnect logic, new render calls)
// ════════════════════════════════════════════════════════════════════════════
function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    statusEl.textContent = "● LIVE";
    statusEl.className = "status connected";
  };

  ws.onmessage = (event) => {
    const d = JSON.parse(event.data);

    // Gauges + animated numbers.
    setGauge(cpuCard,  cpuGaugeFill,  d.cpu_percent);
    setGauge(ramCard,  ramGaugeFill,  d.ram_percent);
    setGauge(diskCard, diskGaugeFill, d.disk_percent);
    animateNumber(cpuValueEl,   d.cpu_percent);
    animateNumber(ramValueEl,   d.ram_percent);
    animateNumber(diskValueEl,  d.disk_percent);

    // Sub-readouts (used / total).
    ramDetailEl.textContent  = `${d.ram_used_gb} / ${d.ram_total_gb} GB`;
    diskDetailEl.textContent = `${d.disk_used_gb} / ${d.disk_total_gb} GB`;

    // Sparklines.
    pushSample(cpuChart,  d.cpu_percent);
    pushSample(ramChart,  d.ram_percent);
    pushSample(diskChart, d.disk_percent);

    // Process tables — each table's bar is driven by its own sort field.
    renderProcessTable(topCpuEl, d.top_cpu || [],    "cpu_percent");
    renderProcessTable(topMemEl, d.top_memory || [], "memory_percent");

    lastUpdateEl.textContent = clockNow();
  };

  ws.onclose = () => {
    statusEl.textContent = "● Disconnected";
    statusEl.className = "status disconnected";
    setTimeout(connect, 2000); // auto-reconnect
  };

  ws.onerror = () => ws.close(); // onclose handles the reconnect
}

// Kick things off.
connect();
