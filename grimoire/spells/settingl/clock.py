# SPDX-License-Identifier: GPL-3.0-or-later
"""Date & time (no Qt): read from systemd-timedated, changed through its D-Bus methods with interactive polkit
authorization, which is what KDE's Date & Time module does (Plasma's agent asks for the password when needed)."""

import re
from datetime import datetime

from grimoire.spells.settingl import kde

DEST, PATH, IFACE = "org.freedesktop.timedate1", "/org/freedesktop/timedate1", "org.freedesktop.timedate1"
ZONE = re.compile(r"[A-Za-z0-9_+\-]+(/[A-Za-z0-9_+\-]+)*")


def read() -> dict:
    p = kde.bus_props(DEST, PATH, IFACE, system=True)
    return {
        "ok": bool(p),
        "timezone": p.get("Timezone", ""),
        "ntp": bool(p.get("NTP")),
        "can_ntp": bool(p.get("CanNTP", True)),
        "synced": bool(p.get("NTPSynchronized")),
        "local_rtc": bool(p.get("LocalRTC")),
    }


def zones() -> list[str]:
    r = kde.RUN(["timedatectl", "list-timezones"], 10)
    return [z for z in r.stdout.split() if ZONE.fullmatch(z)] if not r.returncode else []


def set_timezone(zone: str):
    if not ZONE.fullmatch(zone or "") or ".." in zone:
        raise ValueError(zone)
    kde.bus_call(DEST, PATH, IFACE, "SetTimezone", "sb", zone, "true", system=True, interactive=True, timeout=120)


def set_ntp(on: bool):
    kde.bus_call(
        DEST, PATH, IFACE, "SetNTP", "bb", "true" if on else "false", "true", system=True, interactive=True, timeout=120
    )


def set_time(when: datetime):
    """Set the clock (only works with automatic time off)."""
    usec = int(when.timestamp() * 1_000_000)
    kde.bus_call(DEST, PATH, IFACE, "SetTime", "xbb", usec, "false", "true", system=True, interactive=True, timeout=120)
