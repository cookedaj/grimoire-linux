# SPDX-License-Identifier: GPL-3.0-or-later
"""About this PC: the hardware and software facts behind the home page's card (no Qt).

Everything is read from /proc, /sys, os-release and a few quick commands (nvidia-smi, lspci, lsblk, dpkg-query),
each with a short timeout and a quiet fallback, so a missing tool only leaves its line empty. gather() is slow-ish
(~0.3 s): call it off the UI thread; info() caches it for the life of the process. Host and user names are kept
apart (personal) and only shown when the user asks for them.
"""
import getpass
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from grimoire import __version__

ROOT = Path(os.environ.get("GRIMOIRE_SYSINFO_ROOT", "/"))    # tests point this at a fake /proc, /sys and /etc
JUNK = re.compile(r"to be filled|default string|system product name|system manufacturer|not applicable|"
                  r"^o\.?e\.?m\.?$|^none$|^unknown$|^\s*$", re.I)

_cache: dict | None = None
_lock = threading.Lock()


def _read(rel: str) -> str:
    try:
        return (ROOT / rel).read_text(errors="replace").strip()
    except OSError:
        return ""


def _run(cmd: list[str], timeout=3.0) -> str:
    if not shutil.which(cmd[0]):
        return ""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _tidy(name: str) -> str:
    """'Intel(R) Core(TM) i5-14400F CPU @ 2.50GHz' -> 'Intel Core i5-14400F'."""
    name = re.sub(r"\((R|TM|C)\)|®|™", "", name, flags=re.I)
    name = re.sub(r"\s+(CPU\s+)?@.*$", "", name)
    name = re.sub(r"\s+(\d+-Core|Processor|CPU)\b.*$", "", name, flags=re.I) if "Ryzen" in name else name
    return re.sub(r"\s+", " ", name).strip()


def cpu() -> tuple[str, int]:
    """Model name and logical CPU count."""
    text = _read("proc/cpuinfo")
    model = next((ln.split(":", 1)[1] for ln in text.splitlines()
                  if ln.split(":")[0].strip() in ("model name", "Model", "Hardware")), "")
    threads = sum(1 for ln in text.splitlines() if ln.startswith("processor")) or os.cpu_count() or 0
    return _tidy(model), threads


def gpus() -> list[str]:
    """Every display controller: NVIDIA ones by nvidia-smi's full name and memory, others from lspci."""
    nvidia = []
    for ln in _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]).splitlines():
        name, _, mem = ln.partition(",")
        mem = mem.strip()
        nvidia.append(f"{name.strip()} ({round(int(mem) / 1024)} GB)" if mem.isdigit() else name.strip())
    out = []
    for ln in _run(["lspci", "-mm"]).splitlines():
        fields = re.findall(r'"([^"]*)"', ln)
        if len(fields) < 3 or not re.search(r"VGA|3D|Display", fields[0]):
            continue
        vendor, device = fields[1], fields[2]
        if "NVIDIA" in vendor.upper() and nvidia:
            out.append(nvidia.pop(0))
            continue
        short = vendor.split()[0].replace("Advanced", "AMD") if vendor else ""
        bracket = re.search(r"\[([^\]]+)\]", device)
        out.append(f"{short} {bracket.group(1) if bracket else device}".strip())
    return out + nvidia


def memory() -> int:
    m = re.search(r"MemTotal:\s+(\d+)", _read("proc/meminfo"))
    return int(m.group(1)) * 1024 if m else 0


def disk() -> dict:
    """The disk holding /: model (from lsblk, through partitions, LUKS and LVM) and the root filesystem's size."""
    d = {"model": "", "total": 0, "free": 0}
    try:
        use = shutil.disk_usage(ROOT)
        d["total"], d["free"] = use.total, use.free
    except OSError:
        pass
    source = _run(["findmnt", "-no", "SOURCE", "/"])
    if source.startswith("/dev/"):
        try:
            tree = json.loads(_run(["lsblk", "-J", "-s", "-o", "NAME,MODEL,TYPE", source]) or "{}")
        except ValueError:
            tree = {}
        stack = list(tree.get("blockdevices", []))
        while stack:
            dev = stack.pop()
            if dev.get("type") == "disk" and (dev.get("model") or "").strip():
                d["model"] = dev["model"].strip()
                break
            stack.extend(dev.get("children", []))
    return d


def system() -> str:
    """'Kubuntu 26.04.1 LTS': os-release's name, called Kubuntu when it's Ubuntu with Kubuntu's desktop."""
    rel = dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', _read("etc/os-release"), re.M))
    name = rel.get("PRETTY_NAME") or rel.get("NAME", "Linux")
    if rel.get("ID") == "ubuntu" and any((ROOT / "var/lib/dpkg/info" / f).exists()
                                         for f in ("kubuntu-desktop.list", "kubuntu-settings-desktop.list")):
        name = name.replace("Ubuntu", "Kubuntu", 1)
    return name


def machine() -> str:
    """Maker and model from DMI, skipping the placeholder text cheap boards ship with."""
    bits = []
    for vendor, product in (("sys_vendor", "product_name"), ("board_vendor", "board_name")):
        v, p = _read(f"sys/class/dmi/id/{vendor}"), _read(f"sys/class/dmi/id/{product}")
        if p and not JUNK.search(p):
            bits.append(p if not v or JUNK.search(v) or p.startswith(v.split()[0]) else f"{v} {p}")
    return " · ".join(dict.fromkeys(bits))


def plasma() -> str:
    """Plasma's version from the package manager. Never `plasmashell --version`: it starts Qt and crashes
    (with a KDE crash report) when there's no usable display, e.g. offscreen."""
    out = _run(["dpkg-query", "-W", "-f=${Version}", "plasma-workspace"]) or \
        _run(["pacman", "-Q", "plasma-workspace"]) or _run(["rpm", "-q", "--qf", "%{VERSION}", "plasma-workspace"])
    m = re.search(r"(?:^|[:\s])(\d+\.\d+(?:\.\d+)?)", out)
    return m.group(1) if m else ""


def boot_time() -> float:
    try:
        return time.time() - float(_read("proc/uptime").split()[0])
    except (IndexError, ValueError):
        return 0.0


def gather() -> dict:
    model, threads = cpu()
    return {"machine": machine(), "cpu": model, "threads": threads, "gpus": gpus(), "memory": memory(),
            "disk": disk(), "system": system(), "kernel": os.uname().release, "plasma": plasma(),
            "session": (os.environ.get("XDG_SESSION_TYPE") or "").capitalize(), "boot": boot_time(),
            "version": __version__,
            "host": socket.gethostname(), "user": getpass.getuser()}


def info(refresh: bool = False) -> dict:
    """gather(), once per process (thread safe)."""
    global _cache
    with _lock:
        if _cache is None or refresh:
            _cache = gather()
        return _cache


def cached() -> dict | None:
    return _cache
