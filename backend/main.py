"""
Live PC Health Dashboard — Step 3
=================================
The backend now serves a real browser dashboard (HTML/CSS/JS + Chart.js)
from the `frontend/` folder, while still streaming live stats over the
/ws WebSocket from Step 2.

Architecture overview
---------------------
                          ┌──────────────────────────┐
   Browser (Chart.js)  ◄──┤  FastAPI WebSocket (/ws) │◄── stats.py get_*()
   loads /                └──────────────────────────┘
        ▲                          ▲
        │ static files             │ JSON stream
        │ (index.html, css, js)    │
   ┌────┴──────────────────────────┴────┐
   │           FastAPI app               │
   └─────────────────────────────────────┘

Run the server with:
    uvicorn backend.main:app --reload
Then open http://127.0.0.1:8000
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Reuse the exact same functions we wrote in Step 1. No duplication.
from backend.stats import (
    FAST_TICK_SEC,
    FULL_SCAN_EVERY_N,
    collect_fast_snapshot,
    collect_full_snapshot,
    _prime_cpu,
    _prime_process_cpu,
)

# Prime CPU baselines once at import time (see stats.py for why).
_prime_cpu()
_prime_process_cpu()

# Create the FastAPI application instance.
app = FastAPI(title="Live PC Health Dashboard")

# Where our static frontend files live (../frontend relative to this file).
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# -----------------------------------------------------------------------------
# Serve the dashboard page at "/"
# -----------------------------------------------------------------------------
@app.get("/")
async def home():
    """
    Returns the main dashboard HTML page.
    (We read the file ourselves so we don't have to mount a full static
    router just for one page — though we do mount one below for CSS/JS.)
    """
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


# -----------------------------------------------------------------------------
# The WebSocket endpoint.
#
# IMPORTANT (route ordering): specific routes like "/" and "/ws" MUST be
# registered BEFORE the catch-all `app.mount("/", StaticFiles(...))` further
# below. Starlette matches routes in registration order, so a Mount at "/"
# would otherwise swallow the /ws WebSocket handshake and hand it to
# StaticFiles (which can't handle WebSockets) -> dashboard never updates.
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Runs once PER connected client. Each browser tab gets its own invocation
    of this function.

    Flow:
      1. `await websocket.accept()` completes the WebSocket handshake.
      2. Tiered loop (asyncio.to_thread keeps the event loop free):
           - fast ticks (~400ms): RAM, disks, interval=None CPU + cached processes
           - full ticks (~every 2s): blocking 1s CPU + process scan + disk enum
         JSON shape is unchanged; optional `tick` field is "fast" | "full".
      3. If the client disconnects, WebSocketDisconnect is raised and we
         break out cleanly.
    """
    await websocket.accept()
    try:
        # Prime caches so the first fast ticks already have process/disk data.
        payload = await asyncio.to_thread(collect_full_snapshot, 5)
        payload["timestamp"] = time_iso()
        await websocket.send_text(json.dumps(payload))

        tick = 0
        while True:
            tick += 1
            if tick % FULL_SCAN_EVERY_N == 0:
                payload = await asyncio.to_thread(collect_full_snapshot, 5)
            else:
                payload = await asyncio.to_thread(collect_fast_snapshot)
            payload["timestamp"] = time_iso()
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(FAST_TICK_SEC)
    except WebSocketDisconnect:
        pass


# -----------------------------------------------------------------------------
# Static files — MUST be the last route registered.
# Serves everything in frontend/ (style.css, app.js) as static files, so
# e.g. /style.css -> frontend/style.css. Because it is registered AFTER the
# specific "/" and "/ws" routes above, those take priority and this mount
# only handles the leftover static asset requests.
# -----------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")


# -----------------------------------------------------------------------------
# Helper: ISO-formatted timestamp for each sample.
# -----------------------------------------------------------------------------
def time_iso():
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# -----------------------------------------------------------------------------
# Quick local-run convenience: `python backend/main.py`
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
