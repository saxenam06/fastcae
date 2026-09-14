"""What this process holds of the machine's memory, and what the machine has - so work that takes a
lot of it can wait for room instead of taking the machine down."""

from __future__ import annotations

import os


def committed_gb() -> float:
    """Memory this process has committed, in GB: on Windows its private bytes, the figure the
    system runs out of; elsewhere its resident set."""
    if os.name == "nt":
        import ctypes
        import ctypes.wintypes as wt

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wt.DWORD),
                ("PageFaultCount", wt.DWORD),
                *[
                    (name, ctypes.c_size_t)
                    for name in (
                        "PeakWorkingSetSize",
                        "WorkingSetSize",
                        "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage",
                        "QuotaNonPagedPoolUsage",
                        "PagefileUsage",
                        "PeakPagefileUsage",
                        "PrivateUsage",
                    )
                ],
            ]

        kernel32 = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = wt.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(Counters), wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return 0.0
        return counters.PrivateUsage / 2**30
    try:
        with open("/proc/self/status", encoding="ascii") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 2**20
    except OSError:
        pass
    return 0.0


def physical_gb() -> float:
    """The machine's physical memory, in GB."""
    if os.name == "nt":
        import ctypes
        import ctypes.wintypes as wt

        class Status(ctypes.Structure):
            _fields_ = [
                ("dwLength", wt.DWORD),
                ("dwMemoryLoad", wt.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = Status()
        status.dwLength = ctypes.sizeof(status)
        ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(status))
        return status.ullTotalPhys / 2**30
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
