# SPDX-License-Identifier: GPL-3.0-or-later
"""About this PC (no Qt, read only): the system, Plasma and the hardware, from the files the kernel and the
distribution publish, library versions and lspci."""

import os
import re
import shutil
import socket
from pathlib import Path

from grimoire.spells.settingl import kde

DMI = Path("/sys/class/dmi/id")
LIBS = [Path("/usr/lib/x86_64-linux-gnu"), Path("/usr/lib64"), Path("/usr/lib"), Path("/usr/lib/aarch64-linux-gnu")]
JUNK = re.compile(
    r"to be filled|system product name|system manufacturer|default string|^o\.?e\.?m\.?$|not specified", re.I
)


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def _os_release() -> dict:
    out = {}
    for f in (Path("/etc/os-release"), Path("/usr/lib/os-release")):
        for line in _read(f).splitlines():
            k, _, v = line.partition("=")
            out.setdefault(k, v.strip().strip('"'))
    return out


def _lib_version(stem: str) -> str:
    """The version in a shared library's file name (libKF6CoreAddons.so.6.24.0 → 6.24.0)."""
    for d in LIBS:
        for f in sorted(d.glob(f"{stem}.so.*.*")) if d.is_dir() else []:
            m = re.search(r"\.so\.(\d+\.\d+\.\d+)$", f.name)
            if m:
                return m.group(1)
    return ""


def _cpu() -> tuple[str, int]:
    names = [
        line.split(":", 1)[1].strip()
        for line in _read(Path("/proc/cpuinfo")).splitlines()
        if line.startswith("model name")
    ]
    name = (
        re.sub(r"\s+", " ", re.sub(r"\((R|TM)\)|CPU @.*$|\d+(th|rd|nd|st) Gen ", "", names[0])).strip() if names else ""
    )
    return name, len(names) or (os.cpu_count() or 0)


def _memory() -> int:
    m = re.search(r"MemTotal:\s+(\d+)", _read(Path("/proc/meminfo")))
    return int(m.group(1)) * 1024 if m else 0


def _gpus() -> list[str]:
    r = kde.RUN(["lspci", "-mm"], 10)
    out = []
    for line in r.stdout.splitlines() if not r.returncode else []:
        parts = re.findall(r'"([^"]*)"', line)
        if len(parts) >= 3 and re.search(r"VGA|3D|Display", parts[0]):
            vendor = re.sub(r"\s*(Corporation|Corp\.|Inc\.|\[AMD/ATI\]|Technologies).*$", "", parts[1]).strip()
            model = re.search(r"\[([^\]]+)\]", parts[2])
            out.append(f"{vendor} {model.group(1) if model else parts[2]}".strip())
    return out


def _plasma() -> str:
    """plasma-workspace's library carries Plasma's version (no need to start plasmashell)."""
    return _lib_version("libkworkspace6")


def read() -> dict:
    osr = _os_release()
    cpu, threads = _cpu()
    vendor, product = _read(DMI / "sys_vendor"), _read(DMI / "product_name")
    if JUNK.search(product or "x") or not product:
        vendor, product = _read(DMI / "board_vendor"), _read(DMI / "board_name")
    try:
        disk = shutil.disk_usage("/").total
    except OSError:
        disk = 0
    return {
        "os": osr.get("PRETTY_NAME") or osr.get("NAME", "Linux"),
        "logo": osr.get("LOGO", ""),
        "plasma": _plasma(),
        "frameworks": _lib_version("libKF6CoreAddons"),
        "qt": _lib_version("libQt6Core"),
        "kernel": os.uname().release,
        "arch": os.uname().machine,
        "session": os.environ.get("XDG_SESSION_TYPE", ""),
        "host": socket.gethostname(),
        "vendor": "" if JUNK.search(vendor or "x") else vendor,
        "product": "" if JUNK.search(product or "x") else product,
        "cpu": cpu,
        "threads": threads,
        "memory": _memory(),
        "gpus": _gpus(),
        "disk": disk,
    }
