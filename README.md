<div align="center">

![Live PC Health Dashboard](docs/images/hero-banner.png)

<p>
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.111.0-009688.svg" alt="FastAPI" />
  <img src="https://img.shields.io/badge/WebSockets-Realtime-orange.svg" alt="WebSockets" />
  <img src="https://img.shields.io/badge/Frontend-Vanilla_JS-f7df1e.svg" alt="Vanilla JS" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
</p>

<strong>A real-time telemetry dashboard that streams CPU, RAM, Disk, and Process stats from a Python backend to a glassmorphic browser UI over WebSockets.</strong><br/>


</div>

---

## 🖥️ Preview

<div align="center">

![Dashboard Preview](docs/images/dashboard-preview.png)

</div>

---

## ✨ Why Live PC Health

| Feature | Description |
|---------|-------------|
| ⚡ **Real-Time Streaming** | 1-second interval updates powered by FastAPI WebSockets. |
| 🎛️ **SVG Radial Gauges** | Custom-built speedometer arcs for CPU, Memory, and Disk utilization. |
| 📈 **Live Sparklines** | Rolling-window line charts via `Chart.js` for historical trend visualization. |
| 🔥 **Top Processes** | Dynamic tables of the top CPU and RAM consumers, with inline neon progress bars. |
| 🔄 **Auto-Reconnect** | Seamless frontend reconnection logic if the backend server restarts. |
| 🌐 **Cross-Platform** | Built on `psutil`, supporting Windows, macOS, and Linux out of the box. |

The interface adopts a premium **"Mission Control"** aesthetic: an animated gradient mesh background, glassmorphism panels, and neon threshold colors that shift from **green** to **amber** to **red** as utilization climbs.

---

## 🏗️ Architecture

The project is split into a Python data-gathering backend and a static HTML/JS frontend, connected by a live WebSocket stream.


### How the data flows

1. The **browser** loads the dashboard via HTTP (`GET /`).
2. `app.js` opens a **WebSocket** connection to `/ws`.
3. Every second, `stats.py` reads live metrics from the **operating system** through `psutil`.
4. The **FastAPI** server merges the data into a single payload and pushes it over the socket.
5. The **UI** parses the JSON, animating the gauges, updating the sparklines, and re-rendering the process tables.

---

## 📂 Project Structure

```text
live-pc-dashboard/
├── backend/
│   ├── stats.py          # psutil metrics reader (CPU, RAM, Disk, Processes)
│   └── main.py           # FastAPI app + WebSocket endpoint + static file server
├── frontend/
│   ├── index.html        # Dashboard layout and SVG gauges
│   ├── style.css         # Dark theme, glassmorphism, and animations
│   └── app.js            # WebSocket client, Chart.js logic, and DOM updates
├── docs/                 # Documentation assets
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## 🚀 Getting Started

### 1. Prerequisites

Ensure you have **Python 3.10+** installed on your system.

### 2. Set up a virtual environment

It is recommended to run the project inside an isolated virtual environment.

**Windows (cmd / PowerShell):**
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

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the server

Start the backend from the **project root** so module imports and static files resolve correctly.

```bash
uvicorn backend.main:app --reload
```

You should see:
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 5. Launch 

Open your browser and navigate to 👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🛠️ Tech Stack

- **Backend:** [Python](https://www.python.org/), [FastAPI](https://fastapi.tiangolo.com/), [psutil](https://psutil.readthedocs.io/en/latest/)
- **Server:** [Uvicorn](https://www.uvicorn.org/) (ASGI)
- **Frontend:** HTML5, CSS3 (CSS variables, Flexbox/Grid), Vanilla JavaScript
- **Charting:** [Chart.js](https://www.chartjs.org/)
---

## 📄 License

This project is open-source and available under the **MIT License**.

## 🌱 A Note from the Author

This is one of my **first projects**. I'm still learning, so the code
may not always follow best practices.

If you spot a bug, a mistake, or something that could be done better, please
**open an issue** or leave a comment — any feedback is genuinely appreciated
and helps me grow as a developer. Thank you for checking it out! 🙏
