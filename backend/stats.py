"""
Live PC Health Dashboard — Step 1
=================================
This module is the heart of our dashboard: it reads real system metrics
(CPU, RAM, Disk) using the `psutil` library.

In Step 1 we just PRINT the values to the terminal so we can confirm
psutil works on your machine. In Step 2 we will reuse the EXACT same
get_*() functions and send their results to the browser over WebSockets.

Run me with:  python backend/stats.py
"""

import os
import sys
import time
from collections import defaultdict

# psutil (python system and process utilities) gives us a single consistent
# API to read hardware stats on Windows, macOS and Linux.
import psutil

from backend.win_memory import get_private_working_set_bytes

_BYTES_PER_GIB = 1024 ** 3
_BYTES_PER_MIB = 1024 ** 2

_SKIP_FSTYPES = frozenset({
    "squashfs", "tmpfs", "devtmpfs", "proc", "sysfs", "cgroup", "cgroup2",
    "autofs", "fusectl", "debugfs", "tracefs", "securityfs", "pstore", "bpf",
    "mqueue", "hugetlbfs", "devpts", "binfmt_misc", "configfs", "nsfs",
})


# -----------------------------------------------------------------------------
# 1) CPU
# -----------------------------------------------------------------------------
def get_cpu_usage():
    """
    Returns the current CPU utilization as a percentage (0–100).

    psutil.cpu_percent(interval=...) works like this:
      - With interval=None  -> returns the % since the LAST time it was called.
      - With interval=1.0   -> blocks for 1 second and returns a true
                               "right now" measurement.

    GOTCHA: the very first call to cpu_percent() always returns 0.0 because
    psutil has no previous sample to compare against. We "prime" it once at
    the bottom of this file (see _prime_cpu()) so the first real reading is
    meaningful instead of zero.
    """
    cpu_percent = psutil.cpu_percent(interval=None)
    return {"cpu_percent": cpu_percent}


# -----------------------------------------------------------------------------
# 2) RAM (main memory)
# -----------------------------------------------------------------------------
def get_memory_usage():
    """
    Returns info about system RAM.

    psutil.virtual_memory() returns an object with several attributes:
      .total     -> total physical RAM in bytes
      .available -> RAM that can be given to apps without swapping
      .used      -> RAM currently in use
      .percent   -> percentage of RAM in use (what we'll plot on the chart)

    We convert bytes -> gibibytes (÷ 1024³) so the numbers are human-readable.
    """
    mem = psutil.virtual_memory()

    return {
        "ram_total_gib": round(mem.total / _BYTES_PER_GIB, 2),
        "ram_used_gib": round(mem.used / _BYTES_PER_GIB, 2),
        "ram_percent": mem.percent,
    }


# -----------------------------------------------------------------------------
# 3) DISK (storage on the system drive)
# -----------------------------------------------------------------------------
def get_disk_usage():
    """
    Returns info about the storage drive.

    psutil.disk_usage(path) takes a path to ANY mounted filesystem and returns
    its usage. We use the root of the system drive:
      - Windows : 'C:\\'
      - macOS/Linux : '/'

    The returned object has:
      .total  -> total size of the disk in bytes
      .used   -> bytes currently used
      .free   -> bytes still available
      .percent-> percentage of the disk that is used
    """
    # Pick the right root path depending on the operating system.
    # On Windows the drive is 'C:\\', on Unix-like systems it is '/'.
    path = "C:\\" if sys.platform.startswith("win") else "/"

    disk = psutil.disk_usage(path)

    return {
        "disk_total_gib": round(disk.total / _BYTES_PER_GIB, 2),
        "disk_used_gib": round(disk.used / _BYTES_PER_GIB, 2),
        "disk_free_gib": round(disk.free / _BYTES_PER_GIB, 2),
        "disk_percent": disk.percent,
    }


def _should_skip_partition(part):
    """Skip virtual / pseudo filesystems that are not user storage volumes."""
    fstype = (part.fstype or "").lower()
    if fstype in _SKIP_FSTYPES:
        return True
    if sys.platform.startswith("win"):
        opts = (part.opts or "").lower()
        if "cdrom" in opts:
            return True
    return False


def _disk_label(part):
    """Human-readable volume label for the disk dropdown."""
    mount = part.mountpoint
    if sys.platform.startswith("win") and len(mount) >= 2 and mount[1] == ":":
        return mount[:2]
    return mount


def get_all_disks():
    """
    Enumerate mounted storage volumes (all local disks).

    Returns {"disks": [{device, mountpoint, fstype, label, total_gib, ...}, ...]}.
    Unreadable or virtual partitions are skipped.
    """
    disks = []
    seen = set()

    for part in psutil.disk_partitions(all=False):
        mount = part.mountpoint
        if mount in seen:
            continue
        if _should_skip_partition(part):
            continue
        try:
            usage = psutil.disk_usage(mount)
        except (PermissionError, OSError):
            continue
        seen.add(mount)
        disks.append({
            "device": part.device,
            "mountpoint": mount,
            "fstype": part.fstype,
            "label": _disk_label(part),
            "total_gib": round(usage.total / _BYTES_PER_GIB, 2),
            "used_gib": round(usage.used / _BYTES_PER_GIB, 2),
            "free_gib": round(usage.free / _BYTES_PER_GIB, 2),
            "percent": usage.percent,
        })

    disks.sort(key=lambda d: d["mountpoint"])
    return {"disks": disks}


def _process_memory_bytes(proc) -> int:
    """
    OS-specific process memory for the process table.

    Windows: Private Working Set (Task Manager Memory column) when available.
    Linux/macOS: RSS (same as top/htop RES).
    """
    if sys.platform.startswith("win"):
        pws = get_private_working_set_bytes(proc.pid)
        if pws is not None:
            return pws
        full = proc.memory_full_info()
        return full.private if hasattr(full, "private") else full.rss
    return proc.memory_info().rss


# Tiered collection caches — fast ticks reuse stale process/disk lists between full scans.
_ram_total_bytes: int | None = None
_cached_disks: dict = {"disks": []}
_cached_processes: dict = {"top_cpu": [], "top_memory": []}

FAST_TICK_SEC = 0.4
FULL_SCAN_EVERY_N = 5  # ~2s between full scans at 400ms fast ticks


def refresh_ram_total() -> int:
    """Refresh cached total RAM (used for process memory % between full scans)."""
    global _ram_total_bytes
    _ram_total_bytes = psutil.virtual_memory().total
    return _ram_total_bytes


def _get_ram_total() -> int:
    if _ram_total_bytes is None:
        return refresh_ram_total()
    return _ram_total_bytes


def collect_fast_snapshot():
    """
    Lightweight tick (~few ms): interval=None CPU, RAM, system disk.
    Reuses cached process list and disk enumeration from the last full scan.
    """
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    path = "C:\\" if sys.platform.startswith("win") else "/"
    disk = psutil.disk_usage(path)

    # Refresh percent on cached disk entries without re-enumerating partitions.
    disks = _cached_disks.get("disks", [])
    if disks:
        refreshed = []
        for d in disks:
            try:
                usage = psutil.disk_usage(d["mountpoint"])
                refreshed.append({
                    **d,
                    "total_gib": round(usage.total / _BYTES_PER_GIB, 2),
                    "used_gib": round(usage.used / _BYTES_PER_GIB, 2),
                    "free_gib": round(usage.free / _BYTES_PER_GIB, 2),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                refreshed.append(d)
        disks = refreshed

    return {
        "cpu_percent": cpu_percent,
        "ram_total_gib": round(mem.total / _BYTES_PER_GIB, 2),
        "ram_used_gib": round(mem.used / _BYTES_PER_GIB, 2),
        "ram_percent": mem.percent,
        "disk_total_gib": round(disk.total / _BYTES_PER_GIB, 2),
        "disk_used_gib": round(disk.used / _BYTES_PER_GIB, 2),
        "disk_free_gib": round(disk.free / _BYTES_PER_GIB, 2),
        "disk_percent": disk.percent,
        "disks": disks,
        "top_cpu": _cached_processes.get("top_cpu", []),
        "top_memory": _cached_processes.get("top_memory", []),
        "tick": "fast",
    }


def collect_full_snapshot(limit=5):
    """
    Heavy tick (~1s+): blocking CPU sample, process scan, disk enumeration.
    Updates module caches consumed by collect_fast_snapshot().
    """
    global _cached_disks, _cached_processes

    cpu_percent = psutil.cpu_percent(interval=1.0)
    refresh_ram_total()
    _cached_disks = get_all_disks()
    _cached_processes = get_top_processes(limit)

    return {
        "cpu_percent": cpu_percent,
        **get_memory_usage(),
        **get_disk_usage(),
        **_cached_disks,
        **_cached_processes,
        "tick": "full",
    }


def collect_metrics_snapshot(limit=5):
    """
    Full synchronized snapshot (backward compatible with verify_metrics / CLI).
    Blocks ~1s for CPU baseline, then reads all gauges and top processes.
    """
    return collect_full_snapshot(limit)


# -----------------------------------------------------------------------------
# 4) The monitor loop — runs forever, printing the stats
# -----------------------------------------------------------------------------
def monitor_loop(interval_seconds=2):
    """
    Infinite loop that reads all three stats and prints them to the terminal
    every `interval_seconds` seconds.

    In Step 2 this loop will be replaced by an async task that sends the same
    data to every connected browser via WebSocket.
    """
    print("🖥️  Live PC Health Dashboard — Step 1 (terminal mode)")
    print("    Press Ctrl+C to stop.\n")

    try:
        while True:
            cpu = get_cpu_usage()
            ram = get_memory_usage()
            disk = get_disk_usage()

            # Format a single readable line per sample.
            print(
                f"CPU: {cpu['cpu_percent']:5.1f}%  |  "
                f"RAM: {ram['ram_percent']:5.1f}% "
                f"({ram['ram_used_gib']} / {ram['ram_total_gib']} GiB)  |  "
                f"Disk: {disk['disk_percent']:5.1f}% "
                f"({disk['disk_used_gib']} / {disk['disk_total_gib']} GiB)"
            )

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        # Graceful exit when the user presses Ctrl+C.
        print("\n👋 Stopped. See you in Step 2 (WebSockets)!")


def _prime_cpu():
    """
    Call cpu_percent() once and discard the result so the first real
    reading in the loop is accurate instead of 0.0.
    """
    psutil.cpu_percent(interval=None)


# Module-level cache: keeps psutil.Process objects alive between ticks.
#
# WHY WE NEED THIS (the per-process CPU gotcha):
#   process.cpu_percent(interval=None) works exactly like the global one — it
#   returns the % change SINCE THE LAST TIME IT WAS CALLED ON THAT SAME OBJECT.
#   If we create a fresh Process object each tick and immediately read its
#   cpu_percent(), we ALWAYS get 0.0 (no previous sample to compare against).
#
#   By storing the Process object in _process_cache (keyed by pid) and reusing
#   it next tick, the second call onwards gives a real delta. Pids that have
#   died are pruned so the cache doesn't grow forever.
_process_cache = {}  # { pid: psutil.Process }


def _is_non_meaningful_process(pid, name):
    """
    Return True for OS pseudo-processes that should not appear in top lists.

    Windows "System Idle Process" (pid 0) reports *idle* CPU time — the inverse
    of real utilization — so it always dominates the CPU ranking. "System"
    (pid 4) is kernel overhead, not an app. Linux kernel threads ([kthreadd],
    etc.) are not user workloads.
    """
    normalized_name = (name or "").strip().lower()

    if sys.platform.startswith("win"):
        if pid == 0:
            return True
        if normalized_name in ("system idle process", "idle"):
            return True
        if pid == 4 and normalized_name == "system":
            return True
        return False

    if pid == 0:
        return True
    return normalized_name.startswith("[") and normalized_name.endswith("]")


def _normalize_app_group_key(name):
    """
    Grouping key: exact executable base name (lowercase, no .exe on Windows).

    Processes are grouped only when their normalized names match exactly —
    e.g. all chrome.exe PIDs together, but not chrome vs chromedriver.
    """
    base = os.path.basename(name or "unknown")
    if sys.platform.startswith("win") and base.lower().endswith(".exe"):
        base = base[:-4]
    return base.lower()


def _friendly_display_name(name):
    """Human-readable app label: basename without path or .exe extension."""
    base = os.path.basename(name or "unknown")
    if sys.platform.startswith("win") and base.lower().endswith(".exe"):
        base = base[:-4]
    if not base:
        return "unknown"
    # Preserve mixed-case names (Cursor, Discord); title-case plain lowercase (chrome).
    if base.islower():
        return base.title()
    return base


def _aggregate_process_rows(rows, vm_total):
    """
    Sum CPU and memory for processes that share the same executable name.

    cpu_percent may exceed 100% for multi-process apps (total app usage).
    memory_percent is recalculated from summed bytes / total RAM.
    """
    groups = defaultdict(list)
    for row in rows:
        groups[_normalize_app_group_key(row["name"])].append(row)

    aggregated = []
    for members in groups.values():
        total_cpu = sum(m["cpu_percent"] for m in members)
        total_memory_bytes = sum(m["memory_bytes"] for m in members)
        memory_mib = round(total_memory_bytes / _BYTES_PER_MIB)
        memory_percent = (
            (total_memory_bytes / vm_total) * 100 if vm_total else 0.0
        )

        rep = max(members, key=lambda m: (m["memory_bytes"], m["cpu_percent"]))

        aggregated.append({
            "pid": rep["pid"],
            "name": _friendly_display_name(rep["name"]),
            "cpu_percent": round(total_cpu, 1),
            "memory_percent": round(memory_percent, 1),
            "memory_mib": memory_mib,
            "process_count": len(members),
        })

    return aggregated


def _prime_process_cpu():
    """
    Prime per-process cpu_percent() baselines so the first real tick
    returns meaningful values instead of 0.0 for every process.
    """
    for proc in psutil.process_iter(["pid"]):
        try:
            pid = proc.info["pid"]
            cached = _process_cache.get(pid)
            if cached is None:
                _process_cache[pid] = proc
                cached = proc
            cached.cpu_percent(interval=None)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue


# -----------------------------------------------------------------------------
# 5) PROCESSES — top consumers of CPU and RAM
# -----------------------------------------------------------------------------
def get_top_processes(limit=5):
    """
    Returns the top `limit` processes by CPU usage and by RAM usage.

    Walks every running process via psutil.process_iter(), reads its name,
    CPU% and memory%, sorts, and returns the top N of each.

    Returns a dict (matches our flat-dict convention, just nested by list):
        {
          "top_cpu": [
              {
                  "pid": 1234,
                  "name": "Chrome",
                  "cpu_percent": 23.1,
                  "memory_percent": 4.5,
                  "memory_mib": 512,
                  "process_count": 12,
              },
              ...
          ],
          "top_memory": [ ... same shape, sorted by memory_mib ... ],
        }

    Notes:
      - Pseudo-processes (Idle, System on Windows; kernel threads on Linux)
        are excluded via _is_non_meaningful_process().
      - Multiple PIDs with the same executable (chrome.exe, Cursor.exe, …) are
        aggregated into one row per application; cpu_percent is summed.
      - Windows system processes may raise AccessDenied — also skipped.
      - Zombie/exited processes raise NoSuchProcess — also skipped.
      - Per-process CPU is normalized by logical core count (0–100% of the
        whole machine), matching the system gauge and Windows Task Manager.
    """
    cpu_count = psutil.cpu_count() or 1
    vm_total = _get_ram_total()
    live_pids = set()
    rows = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = proc.info["pid"]
            name = proc.info["name"] or "unknown"
            live_pids.add(pid)

            if _is_non_meaningful_process(pid, name):
                continue

            cached = _process_cache.get(pid)
            if cached is None:
                _process_cache[pid] = proc
                cached = proc

            with cached.oneshot():
                raw_cpu = cached.cpu_percent(interval=None)
                memory_bytes = _process_memory_bytes(cached)

            cpu_percent = max(0.0, min(100.0, raw_cpu / cpu_count))

            rows.append({
                "pid": pid,
                "name": name,
                "cpu_percent": cpu_percent,
                "memory_bytes": memory_bytes,
            })

        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

    # Prune dead processes from the cache so it doesn't grow unbounded.
    for dead_pid in [p for p in _process_cache if p not in live_pids]:
        del _process_cache[dead_pid]

    grouped = _aggregate_process_rows(rows, vm_total)

    top_cpu = sorted(grouped, key=lambda r: r["cpu_percent"], reverse=True)[:limit]
    top_memory = sorted(
        grouped,
        key=lambda r: (r["memory_mib"], r["memory_percent"]),
        reverse=True,
    )[:limit]

    return {"top_cpu": top_cpu, "top_memory": top_memory}


# -----------------------------------------------------------------------------
# Entry point — this runs only when we execute the file directly:
#   python backend/stats.py
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    _prime_cpu()
    _prime_process_cpu()
    monitor_loop(interval_seconds=2)
