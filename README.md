# Live PC Health Dashboard

A real-time dashboard that shows CPU, RAM, and Disk usage of your local machine,
streamed from a Python backend to a browser frontend over WebSockets.

> 🏗️ **Status: Step 3 of N** — full dashboard with live Chart.js graphs.
> Possible next steps: Dockerize, deploy, add more metrics (network, GPU, temps).

---

## Tech Stack
- **Backend:** Python + FastAPI + `psutil`
- **Realtime:** WebSockets
- **Frontend:** HTML / CSS / Vanilla JS + Chart.js

---

## Project Structure
```
live-pc-dashboard/
├── backend/
│   ├── stats.py          # Step 1: psutil metrics reader
│   └── main.py           # Step 2+3: FastAPI app + WebSocket + static files
├── frontend/
│   ├── index.html        # Step 3: dashboard page
│   ├── style.css         # Step 3: dark dashboard theme
│   └── app.js            # Step 3: WebSocket client + Chart.js
├── requirements.txt      # Python dependencies
└── README.md
```

---

## Getting Started (Step 1)

### 1. Create and activate a virtual environment
A virtual environment keeps this project's packages isolated from the rest
of your system.

**Windows (cmd):**
```bat
cd live-pc-dashboard
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
cd live-pc-dashboard
python3 -m venv venv
source venv/bin/activate
```

You should now see `(venv)` at the start of your terminal prompt.

### 2. Install the dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the stats reader
```bash
python backend/stats.py
```

You should see a new line printed every 2 seconds, like:
```
CPU:  12.3%  |  RAM:  54.0% (8.64 / 16.0 GB)  |  Disk:  62.1% (313.5 / 502.3 GB)
```

Press **Ctrl+C** to stop.

---

## Step 2 — FastAPI + WebSockets

If you upgraded `requirements.txt` (added `uvicorn[standard]`), reinstall:

```bash
pip install -r requirements.txt
```

**Important:** run the server from the **project root** (the folder that
contains `backend/`), not from inside `backend/`. That way the import
`from backend.stats import ...` resolves correctly.

Start the server (with auto-reload on file changes):

```bash
# from the live-pc-dashboard/ folder
uvicorn backend.main:app --reload
```

You should see something like:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Open **http://127.0.0.1:8000** in your browser. You'll see a tiny test page that
connects to the `/ws` WebSocket and prints each incoming sample. Open the
browser console (**F12 → Console**) to inspect the raw JSON messages, which look
like:

```json
{
  "cpu_percent": 9.4,
  "ram_total_gb": 16.0,
  "ram_used_gb": 8.61,
  "ram_percent": 53.8,
  "disk_total_gb": 502.3,
  "disk_used_gb": 313.5,
  "disk_free_gb": 188.8,
  "disk_percent": 62.1,
  "timestamp": "2026-06-17T14:30:21"
}
```

Press **Ctrl+C** in the terminal to stop the server.

### Useful FastAPI extras
- **Interactive API docs:** visit http://127.0.0.1:8000/docs (auto-generated).
- **ReDoc docs:** http://127.0.0.1:8000/redoc.

---

## Step 3 — Browser dashboard with Chart.js

Nothing new to install — the backend already serves the frontend files and
Chart.js is loaded from a CDN. Just restart the server:

```bash
# from the live-pc-dashboard/ folder
uvicorn backend.main:app --reload
```

Open **http://127.0.0.1:8000**. You should now see:

- A dark dashboard with three cards: **CPU**, **RAM**, **Disk**.
- The big percentage in each card updating every second.
- Three live line charts (blue/pink/amber) that scroll right-to-left like a
  heart-rate monitor, showing the last 30 samples.
- A green **● Connected** badge in the top-right (pulses while live).
- If you stop the server, the badge turns grey and the page auto-reconnects
  after 2 seconds.

### Try it
- Open the dashboard, then run something heavy (a build, a video render,
  lots of browser tabs) and watch the CPU/RAM lines spike.
- Open the page in **two tabs at once** — both get independent live streams
  (each WebSocket connection is its own call to `websocket_endpoint`).

---

## Next Steps
- **Dockerize** the app for portable deployment.
- **Deploy** behind a reverse proxy (nginx/Caddy) for a live portfolio demo.
- **Add metrics**: network throughput, per-core CPU, GPU, temperatures.
- **Polish**: thresholds + color changes (e.g. red when CPU > 90%).
