# SPDX-License-Identifier: GPL-3.0-or-later
"""Notifications (no Qt): Do Not Disturb and each app's basics, in Plasma's own plasmanotifyrc.

Plasma's notification server watches that file: kwriteconfig6 --notify makes a change apply at once, like the
switches in Plasma's own notification settings. Do Not Disturb is [DoNotDisturb] Until (a local date and time);
"until you turn it off" is a year ahead, as Plasma's applet does it.
"""

from datetime import datetime, timedelta

from grimoire.spells.settingl import kde

FILE = "plasmanotifyrc"


def _until(v: str) -> datetime | None:
    """KConfig's QDateTime: "2026,10,15,18,30,0" (older files: ISO)."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        if "," in v:
            parts = [int(float(x)) for x in v.split(",")]
            return datetime(*parts[:6]) if len(parts) >= 6 else datetime(*parts[:3])
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):
        return None


def read() -> dict:
    cfg = kde.parse(FILE)
    until = _until(cfg.get(("DoNotDisturb",), {}).get("Until", ""))
    inhibited = kde.bus_props(
        "org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications"
    ).get("Inhibited", False)
    apps = []
    for groups, keys in cfg.items():
        if len(groups) == 2 and groups[0] == "Applications":
            apps.append(
                {
                    "id": groups[1],
                    "popups": kde.as_bool(keys.get("ShowPopups", ""), True),
                    "history": kde.as_bool(keys.get("ShowInHistory", ""), True),
                    "badges": kde.as_bool(keys.get("ShowBadges", ""), True),
                }
            )
    now = datetime.now()
    return {
        "dnd": bool(until and until > now),
        "until": until if until and until > now else None,
        "inhibited": bool(inhibited),
        "apps": apps,
    }


def set_dnd(minutes: int | None):
    """minutes: None = off, 0 = until you turn it off, else that many minutes from now."""
    if minutes is None:
        kde.write(FILE, "DoNotDisturb", "Until", None)
        return
    end = datetime.now() + (timedelta(days=365) if minutes == 0 else timedelta(minutes=int(minutes)))
    kde.write(FILE, "DoNotDisturb", "Until", f"{end.year},{end.month},{end.day},{end.hour},{end.minute},{end.second}")


def until_morning() -> int:
    """Minutes until 8:00 tomorrow."""
    now = datetime.now()
    morning = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return max(1, int((morning - now).total_seconds() // 60))


def set_app(app: str, key: str, on: bool):
    if key not in ("ShowPopups", "ShowInHistory", "ShowBadges") or not app or "]" in app or "[" in app:
        raise ValueError(key)
    kde.write(FILE, ("Applications", app), key, bool(on))
