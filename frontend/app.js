/* ════════════════════════════════════════════════════════════════════════════
   LIVE PC HEALTH · MISSION CONTROL — frontend logic
   ────────────────────────────────────────────────────────────────────────────
   Responsibilities:
     1. Open a WebSocket to the backend's /ws endpoint.
     2. On each sample: target gauges/sparklines; rAF loop smooths display ~60fps.
     3. Process tables update on full ticks only (max ~1/s), with row diffing.
     4. Handle connection state (status badge + auto-reconnect).
   ════════════════════════════════════════════════════════════════════════════ */

// ── Config ──────────────────────────────────────────────────────────────────
const MAX_POINTS = 30;
const LERP_FACTOR = 0.18; // display lerp per frame toward server target
const PROCESS_TABLE_MIN_MS = 1000;

// ── DOM references ──────────────────────────────────────────────────────────
const statusEl     = document.getElementById("status");
const cpuValueEl   = document.getElementById("cpu-value");
const ramValueEl   = document.getElementById("ram-value");
const ramDetailEl  = document.getElementById("ram-detail");
const diskValueEl  = document.getElementById("disk-value");
const diskDetailEl = document.getElementById("disk-detail");
const lastUpdateEl = document.getElementById("last-update");
const topCpuEl          = document.getElementById("top-cpu-table");
const topMemEl          = document.getElementById("top-memory-table");
const diskSelectEl      = document.getElementById("disk-select");

const DISK_STORAGE_KEY = "selectedDiskMount";
let knownDiskMountsKey = "";
let lastProcessTableRender = 0;
let latestDisks = [];

// ── Gauge elements ──────────────────────────────────────────────────────────
const cpuCard  = document.querySelector('.card[data-metric="cpu"]');
const ramCard  = document.querySelector('.card[data-metric="ram"]');
const diskCard = document.querySelector('.card[data-metric="disk"]');
const cpuGaugeFill  = cpuCard.querySelector(".gauge-fill");
const ramGaugeFill  = ramCard.querySelector(".gauge-fill");
const diskGaugeFill = diskCard.querySelector(".gauge-fill");

const GAUGE_R = 52;
const GAUGE_C = 2 * Math.PI * GAUGE_R;
const GAUGE_ARC = GAUGE_C * 0.75;

[cpuGaugeFill, ramGaugeFill, diskGaugeFill].forEach((el) => {
  el.setAttribute("stroke-dasharray", `${GAUGE_ARC} ${GAUGE_C}`);
  el.setAttribute("stroke-dashoffset", GAUGE_ARC);
});

// Server targets vs smoothly displayed values (updated every rAF).
const metrics = {
  cpu:  { display: 0, target: 0 },
  ram:  { display: 0, target: 0 },
  disk: { display: 0, target: 0 },
};

function setGauge(fillCircleEl, percent) {
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = GAUGE_ARC * (1 - clamped / 100);
  fillCircleEl.setAttribute("stroke-dashoffset", offset);
}

function setPercentText(el, value, suffix = "%") {
  el.textContent = `${value.toFixed(1)}${suffix}`;
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function applyMetricDisplay(metric, valueEl, cardEl, fillEl) {
  setGauge(fillEl, metrics[metric].display);
  setPercentText(valueEl, metrics[metric].display);
}

function startDisplayLoop() {
  function frame() {
    for (const key of ["cpu", "ram", "disk"]) {
      const m = metrics[key];
      const delta = m.target - m.display;
      if (Math.abs(delta) < 0.03) {
        m.display = m.target;
      } else {
        m.display = lerp(m.display, m.target, LERP_FACTOR);
      }
    }
    applyMetricDisplay("cpu", cpuValueEl, cpuCard, cpuGaugeFill);
    applyMetricDisplay("ram", ramValueEl, ramCard, ramGaugeFill);
    applyMetricDisplay("disk", diskValueEl, diskCard, diskGaugeFill);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// ── Sparklines ────────────────────────────────────────────────────────────────
function makeChart(canvasId, color) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  return new Chart(ctx, {
    type: "line",
    data: {
      labels: Array(MAX_POINTS).fill(""),
      datasets: [{
        data: Array(MAX_POINTS).fill(null),
        borderColor: color,
        backgroundColor: color + "22",
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
        y: { min: 0, max: 100, display: false },
        x: { display: false },
      },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}

const cpuChart  = makeChart("cpu-chart",  "#7dd3fc");
const ramChart  = makeChart("ram-chart",  "#a78bfa");
const diskChart = makeChart("disk-chart", "#4ade80");

function pushSample(chart, value) {
  const data = chart.data.datasets[0].data;
  data.push(value);
  if (data.length > MAX_POINTS) data.shift();
  chart.update("none");
}

// ── Process tables — row diff, throttled ────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function updateProcessRow(tr, row, barField) {
  const barWidth = Math.max(2, Math.min(100, row[barField]));
  let cells = tr.children;
  if (!cells.length) {
    tr.innerHTML = `
      <td></td>
      <td class="proc-name-cell">
        <div class="proc-bar"></div>
        <span></span>
      </td>
      <td class="num big-num"></td>
      <td class="num"></td>`;
    cells = tr.children;
  }
  cells[0].textContent = row.pid;
  cells[1].querySelector(".proc-bar").style.width = `${barWidth}%`;
  cells[1].querySelector("span").textContent = row.name;
  cells[2].textContent = row.cpu_percent.toFixed(1);
  cells[3].textContent = `${row.memory_mib.toFixed(0)} MiB (${row.memory_percent.toFixed(1)}%)`;
}

function renderProcessTable(tableBodyEl, rows, barField) {
  const existing = Array.from(tableBodyEl.children);

  rows.forEach((row, i) => {
    let tr = existing[i];
    if (!tr) {
      tr = document.createElement("tr");
      tableBodyEl.appendChild(tr);
    }
    updateProcessRow(tr, row, barField);
  });

  while (tableBodyEl.children.length > rows.length) {
    tableBodyEl.removeChild(tableBodyEl.lastChild);
  }
}

function maybeRenderProcessTables(d) {
  const isFull = d.tick === "full";
  const now = performance.now();
  if (!isFull && now - lastProcessTableRender < PROCESS_TABLE_MIN_MS) {
    return;
  }
  lastProcessTableRender = now;
  renderProcessTable(topCpuEl, d.top_cpu || [], "cpu_percent");
  renderProcessTable(topMemEl, d.top_memory || [], "memory_percent");
}

function escapeAttr(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function defaultDiskMount(disks) {
  const system = disks.find(
    (d) => d.mountpoint === "C:\\" || d.mountpoint === "/"
  );
  return system ? system.mountpoint : disks[0]?.mountpoint;
}

function syncDiskSelect(disks) {
  if (!diskSelectEl || !disks?.length) return;

  const mountsKey = disks.map((d) => d.mountpoint).join("|");
  if (mountsKey !== knownDiskMountsKey) {
    knownDiskMountsKey = mountsKey;
    const saved = localStorage.getItem(DISK_STORAGE_KEY);
    diskSelectEl.innerHTML = disks
      .map(
        (d) =>
          `<option value="${escapeAttr(d.mountpoint)}">${escapeHtml(d.label)}</option>`
      )
      .join("");
    const pick =
      saved && disks.some((d) => d.mountpoint === saved)
        ? saved
        : defaultDiskMount(disks);
    if (pick) diskSelectEl.value = pick;
  }
}

function getSelectedDisk(disks) {
  if (!disks?.length) return null;
  const mount = diskSelectEl?.value || localStorage.getItem(DISK_STORAGE_KEY);
  return disks.find((d) => d.mountpoint === mount) || disks[0];
}

function updateDiskFromPayload(d) {
  if (d.disks?.length) {
    latestDisks = d.disks;
    syncDiskSelect(d.disks);
    const disk = getSelectedDisk(d.disks);
    if (!disk) return;
    metrics.disk.target = disk.percent;
    diskDetailEl.textContent = `${disk.used_gib} / ${disk.total_gib} GiB`;
    pushSample(diskChart, disk.percent);
    return;
  }

  metrics.disk.target = d.disk_percent;
  diskDetailEl.textContent = `${d.disk_used_gib} / ${d.disk_total_gib} GiB`;
  pushSample(diskChart, d.disk_percent);
}

if (diskSelectEl) {
  diskSelectEl.addEventListener("change", () => {
    localStorage.setItem(DISK_STORAGE_KEY, diskSelectEl.value);
    if (latestDisks.length) {
      const disk = getSelectedDisk(latestDisks);
      if (disk) {
        metrics.disk.target = disk.percent;
        diskDetailEl.textContent = `${disk.used_gib} / ${disk.total_gib} GiB`;
        pushSample(diskChart, disk.percent);
      }
    }
  });
}

function clockNow() {
  return new Date().toLocaleTimeString();
}

function handleMetricsMessage(d) {
  metrics.cpu.target = d.cpu_percent;
  metrics.ram.target = d.ram_percent;
  ramDetailEl.textContent = `${d.ram_used_gib} / ${d.ram_total_gib} GiB`;

  pushSample(cpuChart, d.cpu_percent);
  pushSample(ramChart, d.ram_percent);
  updateDiskFromPayload(d);

  maybeRenderProcessTables(d);
  lastUpdateEl.textContent = clockNow();
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    statusEl.textContent = "● LIVE";
    statusEl.className = "status connected";
  };

  ws.onmessage = (event) => {
    handleMetricsMessage(JSON.parse(event.data));
  };

  ws.onclose = () => {
    statusEl.textContent = "● Disconnected";
    statusEl.className = "status disconnected";
    setTimeout(connect, 2000);
  };

  ws.onerror = () => ws.close();
}

startDisplayLoop();
connect();
