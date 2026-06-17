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

import time

# psutil (python system and process utilities) gives us a single consistent
# API to read hardware stats on Windows, macOS and Linux.
import psutil


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

    We convert bytes -> gigabytes (÷ 1024³) so the numbers are human-readable.
    """
    mem = psutil.virtual_memory()
    bytes_per_gb = 1024 ** 3  # 1 GB = 1024 * 1024 * 1024 bytes

    return {
        "ram_total_gb": round(mem.total / bytes_per_gb, 2),
        "ram_used_gb": round(mem.used / bytes_per_gb, 2),
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
    import sys
    path = "C:\\" if sys.platform.startswith("win") else "/"

    disk = psutil.disk_usage(path)
    bytes_per_gb = 1024 ** 3

    return {
        "disk_total_gb": round(disk.total / bytes_per_gb, 2),
        "disk_used_gb": round(disk.used / bytes_per_gb, 2),
        "disk_free_gb": round(disk.free / bytes_per_gb, 2),
        "disk_percent": disk.percent,
    }


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
                f"({ram['ram_used_gb']} / {ram['ram_total_gb']} GB)  |  "
                f"Disk: {disk['disk_percent']:5.1f}% "
                f"({disk['disk_used_gb']} / {disk['disk_total_gb']} GB)"
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


# -----------------------------------------------------------------------------
# Entry point — this runs only when we execute the file directly:
#   python backend/stats.py
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    _prime_cpu()
    monitor_loop(interval_seconds=2)
