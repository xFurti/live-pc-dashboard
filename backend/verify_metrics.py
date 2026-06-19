"""
Quick sanity check for cross-platform metrics (Task Manager alignment).

Run from the project root:

    python -m backend.verify_metrics

Exercises both tiered collectors:
  - collect_full_snapshot() — synchronized 1s CPU + process scan + disks
  - collect_fast_snapshot() — lightweight tick with cached process/disk data

Compare output with your OS monitor:
  - Windows: Task Manager → Details → Memory column (Private Working Set)
  - Linux:   top / htop (RSS), df -h for disks
  - macOS:   Activity Monitor

Manual checklist (Windows, side-by-side with Task Manager):
  1. Details view → right-click columns → confirm Memory = Private Working Set
  2. Top apps: CPU% and Memory (MiB) are summed across all PIDs of the same
     executable (e.g. all chrome.exe rows → one "Chrome" row)
  3. Change disk in the dashboard dropdown → % matches Explorer / disk properties

RAM total is reported in GiB (binary). Marketing "16 GB" stickers often differ
slightly from OS-reported GiB due to hardware reserved memory.
"""

import time

from backend.stats import (
    _prime_cpu,
    _prime_process_cpu,
    collect_fast_snapshot,
    collect_full_snapshot,
    collect_metrics_snapshot,
)

_prime_cpu()
_prime_process_cpu()

print("=== Full snapshot (1s CPU + process scan) ===")
snapshot = collect_full_snapshot(limit=5)

print("=== System ===")
print(f"CPU:  {snapshot['cpu_percent']:.1f}%")
print(
    f"RAM:  {snapshot['ram_percent']:.1f}% "
    f"({snapshot['ram_used_gib']} / {snapshot['ram_total_gib']} GiB)"
)
print(
    f"Disk (system drive): {snapshot['disk_percent']:.1f}% "
    f"({snapshot['disk_used_gib']} / {snapshot['disk_total_gib']} GiB)"
)

print("\n=== All disks ===")
for d in snapshot.get("disks", []):
    print(
        f"  {d['label']:<8} {d['mountpoint']:<12} "
        f"{d['percent']:5.1f}%  "
        f"({d['used_gib']} / {d['total_gib']} GiB)  "
        f"[{d['fstype']}]"
    )

def _format_process_row(p):
    procs = p.get("process_count", 1)
    procs_note = f"  ({procs} PIDs)" if procs > 1 else ""
    return (
        f"  {p['name']:<24} pid={p['pid']:<6} "
        f"cpu={p['cpu_percent']:5.1f}%  "
        f"ram={p['memory_mib']:7d} MiB ({p['memory_percent']:.1f}%){procs_note}"
    )


print("\n=== Top 5 apps by CPU (grouped by executable, normalized 0–100%) ===")
for p in snapshot["top_cpu"]:
    print(_format_process_row(p))

print("\n=== Top 5 apps by RAM (grouped by executable) ===")
for p in snapshot["top_memory"]:
    print(_format_process_row(p))

print("\n=== Fast snapshot (interval=None CPU, cached processes) ===")
time.sleep(0.4)
fast = collect_fast_snapshot()
print(f"tick={fast['tick']}  CPU={fast['cpu_percent']:.1f}%  RAM={fast['ram_percent']:.1f}%")
print(f"cached top_cpu rows: {len(fast.get('top_cpu', []))}  disks: {len(fast.get('disks', []))}")

# Backward-compat alias
assert collect_metrics_snapshot(limit=1)["tick"] == "full"
print("\nOK — tiered collectors and collect_metrics_snapshot() alias verified.")
