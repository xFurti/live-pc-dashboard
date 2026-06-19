"""
Windows Private Working Set via Win32 API.

Task Manager's Memory column shows Private Working Set. psutil's RSS and
even memory_full_info().private do not match exactly; on Win11 22H2+
GetProcessMemoryInfo with PROCESS_MEMORY_COUNTERS_EX2 exposes
PrivateWorkingSetSize for a closer match.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

if not sys.platform.startswith("win"):
    def get_private_working_set_bytes(pid: int) -> int | None:  # noqa: ARG001
        return None
else:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010

    class PROCESS_MEMORY_COUNTERS_EX2(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
            ("PrivateWorkingSetSize", ctypes.c_size_t),
            ("SharedCommitUsage", ctypes.c_size_t),
        ]

    def get_private_working_set_bytes(pid: int) -> int | None:
        access = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            return None
        try:
            counters = PROCESS_MEMORY_COUNTERS_EX2()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX2)
            ok = psapi.GetProcessMemoryInfo(
                handle,
                ctypes.byref(counters),
                counters.cb,
            )
            if not ok:
                return None
            if counters.PrivateWorkingSetSize:
                return int(counters.PrivateWorkingSetSize)
            if counters.PrivateUsage:
                return int(counters.PrivateUsage)
            return None
        finally:
            kernel32.CloseHandle(handle)
