# SPDX-License-Identifier: GPL-3.0-or-later
"""Power (no Qt): power profiles, the screen-dim/screen-off/sleep timers, batteries.

Profiles go through power-profiles-daemon's own powerprofilesctl. The timers are PowerDevil's (Plasma's power
manager): its powerdevilrc, written with kwriteconfig6 --notify, then PowerDevil is told to reload over D-Bus, as
KDE's Power Management module does. A key that isn't in the file means Plasma's default, which DEFAULTS mirrors.
"""

from pathlib import Path

from grimoire.spells.settingl import kde

SUPPLY = Path("/sys/class/power_supply")
PROFILES = ("AC", "Battery", "LowBattery")
# Plasma 6's defaults for a desktop/laptop (PowerDevil's profile defaults), in seconds; suspend 1 = sleep
DEFAULTS = {
    "AC": {"dim": (True, 300), "off": (True, 600), "sleep": (1, 900)},
    "Battery": {"dim": (True, 120), "off": (True, 300), "sleep": (1, 600)},
    "LowBattery": {"dim": (True, 60), "off": (True, 120), "sleep": (1, 300)},
}
SLEEP, NOTHING = 1, 0


def profiles() -> dict:
    """{"available": [...], "active": str, "degraded": str, "ok": bool}"""
    r = kde.RUN(["powerprofilesctl", "list"], 10)
    if r.returncode:
        return {"available": [], "active": "", "degraded": "", "ok": False}
    avail, active, degraded, cur = [], "", "", None
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.endswith(":") and not line.startswith(" " * 4):
            cur = s.lstrip("* ").rstrip(":")
            avail.append(cur)
            if s.startswith("*"):
                active = cur
        elif s.startswith("Degraded:") and cur == active:
            degraded = s.split(":", 1)[1].strip()
    order = {"power-saver": 0, "balanced": 1, "performance": 2}
    avail.sort(key=lambda p: order.get(p, 9))
    return {"available": avail, "active": active, "degraded": "" if degraded in ("", "no") else degraded, "ok": True}


def set_profile(name: str):
    if name not in ("power-saver", "balanced", "performance"):
        raise ValueError(name)
    kde.check(["powerprofilesctl", "set", name])


def timers(profile: str = "AC") -> dict:
    """{"dim": seconds or 0, "off": seconds or 0, "sleep": seconds or 0} — 0 means never."""
    cfg = kde.parse("powerdevilrc")
    disp = cfg.get((profile, "Display"), {})
    susp = cfg.get((profile, "SuspendAndShutdown"), {})
    d = DEFAULTS[profile]
    dim_on = kde.as_bool(disp.get("DimDisplayWhenIdle", ""), d["dim"][0])
    off_on = kde.as_bool(disp.get("TurnOffDisplayWhenIdle", ""), d["off"][0])
    action = kde.as_int(susp.get("AutoSuspendAction", ""), d["sleep"][0])
    return {
        "dim": kde.as_int(disp.get("DimDisplayIdleTimeoutSec", ""), d["dim"][1]) if dim_on else 0,
        "off": kde.as_int(disp.get("TurnOffDisplayIdleTimeoutSec", ""), d["off"][1]) if off_on else 0,
        "sleep": kde.as_int(susp.get("AutoSuspendIdleTimeoutSec", ""), d["sleep"][1]) if action else 0,
        "action": action,
    }


def set_timer(profile: str, which: str, seconds: int):
    """Set one timer (0 = never) and have PowerDevil reload."""
    if profile not in PROFILES or which not in ("dim", "off", "sleep") or seconds < 0:
        raise ValueError(which)
    if which == "dim":
        kde.write("powerdevilrc", (profile, "Display"), "DimDisplayWhenIdle", bool(seconds))
        if seconds:
            kde.write("powerdevilrc", (profile, "Display"), "DimDisplayIdleTimeoutSec", int(seconds))
    elif which == "off":
        kde.write("powerdevilrc", (profile, "Display"), "TurnOffDisplayWhenIdle", bool(seconds))
        if seconds:
            kde.write("powerdevilrc", (profile, "Display"), "TurnOffDisplayIdleTimeoutSec", int(seconds))
    else:
        kde.write("powerdevilrc", (profile, "SuspendAndShutdown"), "AutoSuspendAction", SLEEP if seconds else NOTHING)
        if seconds:
            kde.write("powerdevilrc", (profile, "SuspendAndShutdown"), "AutoSuspendIdleTimeoutSec", int(seconds))
    reload()


def reload():
    for method in ("reparseConfiguration", "refreshStatus"):
        kde.bus_call(
            "org.kde.Solid.PowerManagement",
            "/org/kde/Solid/PowerManagement",
            "org.kde.Solid.PowerManagement",
            method,
            quiet=True,
        )


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def batteries() -> list[dict]:
    """The PC's batteries and those of connected devices (mice, headsets), from the kernel."""
    out = []
    for d in sorted(SUPPLY.glob("*")) if SUPPLY.is_dir() else []:
        if _read(d / "type") != "Battery":
            continue
        cap = _read(d / "capacity")
        out.append(
            {
                "name": d.name,
                "model": _read(d / "model_name") or _read(d / "manufacturer"),
                "percent": int(cap) if cap.isdigit() else None,
                "status": _read(d / "status"),
                "system": _read(d / "scope") != "Device",
            }
        )
    return out


def has_battery() -> bool:
    return any(b["system"] for b in batteries())
