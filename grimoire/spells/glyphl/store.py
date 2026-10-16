# SPDX-License-Identifier: GPL-3.0-or-later
"""GlyphL's settings, recent characters and favorites (glyphl.json in the profile's config folder). No Qt.
CONFIG is read late, so importing this before the sign-in gate binds no profile."""
import json
import os

from grimoire import paths
from grimoire.i18n import tr

RECENT_MAX, FAVORITES_MAX = 48, 400
DEFAULTS = {"recent": [], "favorites": [], "tone": 0, "close": True, "category": "recent"}
HOTKEY_ID = "glyphs"            # hotkeys.COMMANDS id: KDE knows the binding as grimoire-hotkey-glyphs.desktop


def _file():
    return paths.CONFIG / "glyphl.json"


def _texts(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out = [v for v in value if isinstance(v, str) and 0 < len(v) <= 32 and "\x00" not in v]
    return list(dict.fromkeys(out))[:limit]


def load() -> dict:
    try:
        d = json.loads(_file().read_text())
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    tone = d.get("tone")
    category = d.get("category")
    return {"recent": _texts(d.get("recent"), RECENT_MAX), "favorites": _texts(d.get("favorites"), FAVORITES_MAX),
            "tone": tone if isinstance(tone, int) and 0 <= tone <= 5 else 0,
            "close": d.get("close") if isinstance(d.get("close"), bool) else True,
            "category": category if isinstance(category, str) and len(category) < 40 else "recent"}


def save(s: dict):
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f".{f.name}.tmp")
    tmp.write_text(json.dumps({k: s.get(k, v) for k, v in DEFAULTS.items()}, ensure_ascii=False, indent=1))
    os.replace(tmp, f)


def used(s: dict, text: str):
    """text was just copied: to the front of the recent list."""
    s["recent"] = [text] + [t for t in s["recent"] if t != text][:RECENT_MAX - 1]


def toggle_favorite(s: dict, text: str) -> bool:
    """Star or unstar text; True when it is a favorite now."""
    if text in s["favorites"]:
        s["favorites"] = [t for t in s["favorites"] if t != text]
        return False
    s["favorites"] = (s["favorites"] + [text])[-FAVORITES_MAX:]
    return True


def status_line() -> str:
    s = load()
    bits = [tr("grimoire.spells.glyphl.store", "%n favorite(s)", n=len(s["favorites"])),
            tr("grimoire.spells.glyphl.store", "%n used lately", n=len(s["recent"]))]
    return " · ".join(bits)
