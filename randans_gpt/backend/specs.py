"""
backend/specs.py
----------------
Detects the PC's hardware (RAM, CPU, GPU, free disk) so the setup wizard can
recommend AI models that will actually run well. Everything is best-effort and
wrapped in try/except: a failed probe just leaves that field empty.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd: list, timeout: int = 8) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)
        return out.stdout if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def _ram_gb() -> float | None:
    try:
        import psutil
        return round(psutil.virtual_memory().total / 1024 ** 3, 1)
    except Exception:  # noqa: BLE001
        pass
    try:
        if sys.platform == "win32":
            import ctypes

            class MEM(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("pt", ctypes.c_ulonglong), ("pa", ctypes.c_ulonglong),
                            ("vt", ctypes.c_ulonglong), ("va", ctypes.c_ulonglong), ("ve", ctypes.c_ulonglong)]
            m = MEM()
            m.l = ctypes.sizeof(MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.total / 1024 ** 3, 1)
        with open("/proc/meminfo") as fh:
            return round(int(fh.readline().split()[1]) / 1024 ** 2, 1)
    except Exception:  # noqa: BLE001
        return None


def _cpu_name() -> str:
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return " ".join(winreg.QueryValueEx(key, "ProcessorNameString")[0].split())
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return " ".join(line.split(":", 1)[1].split())
    except Exception:  # noqa: BLE001
        pass
    return platform.processor() or "Unknown CPU"


def _cores() -> tuple:
    try:
        import psutil
        return psutil.cpu_count(logical=False) or None, psutil.cpu_count(logical=True) or None
    except Exception:  # noqa: BLE001
        return None, os.cpu_count()


def _gpus() -> list:
    """[{'name', 'vram_gb', 'nvidia'}] - NVIDIA VRAM from nvidia-smi, names from Windows/Linux probes."""
    gpus: list = []
    smi = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    for line in smi.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and parts[1].replace(".", "").isdigit():
            gpus.append({"name": parts[0], "vram_gb": round(float(parts[1]) / 1024, 1), "nvidia": True})
    if gpus:
        return gpus
    names: list = []
    if sys.platform == "win32":
        out = _run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"])
        names = [n.strip() for n in out.splitlines() if n.strip()]
    elif sys.platform.startswith("linux"):
        names = [re.sub(r"^.*?: ", "", l) for l in _run(["lspci"]).splitlines() if re.search(r"VGA|3D|Display", l)]
    for n in names:
        gpus.append({"name": n, "vram_gb": None, "nvidia": bool(re.search(r"nvidia|geforce|rtx|gtx", n, re.I))})
    return gpus


def ollama_models_dir() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")


def _disk_free_gb() -> float | None:
    path = ollama_models_dir()
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        return round(shutil.disk_usage(path).free / 1024 ** 3, 1)
    except Exception:  # noqa: BLE001
        return None


def detect_specs() -> dict:
    """Snapshot of this PC. Safe to call from a worker thread (can take a few seconds on Windows)."""
    physical, logical = _cores()
    gpus = _gpus()
    nvidia = [g for g in gpus if g["nvidia"] and g.get("vram_gb")]
    best = max(nvidia, key=lambda g: g["vram_gb"]) if nvidia else None
    return {
        "os": f"{platform.system()} {platform.release()}", "ram_gb": _ram_gb(), "cpu": _cpu_name(),
        "cores": physical, "threads": logical, "gpus": [g["name"] for g in gpus],
        "gpu_accel": bool(best), "vram_gb": best["vram_gb"] if best else None,
        "gpu_name": best["name"] if best else (gpus[0]["name"] if gpus else None),
        "disk_free_gb": _disk_free_gb(),
    }
