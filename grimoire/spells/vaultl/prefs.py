# SPDX-License-Identifier: GPL-3.0-or-later
"""How VaultL's window was left (grid or details, hidden files, preview, sort, icon size) and the folders pinned
to Places, in vaultl-view.json. No Qt. vaultl.json stays Tidy's: its Settings.save writes only its own keys."""
import json
import os

from grimoire.paths import CONFIG

FILE = CONFIG / "vaultl-view.json"
ICON_SIZES = (48, 72, 96, 128)                 # grid zoom steps; 72 is where VaultL started
DEFAULTS = {"view": 0, "hidden": False, "preview": True, "sort_col": 0, "sort_desc": False, "icon": 72,
            "places": []}
MAX_PLACES = 30


def load() -> dict:
    """The saved values over the defaults; anything of the wrong type or out of range is dropped."""
    try:
        data = json.loads(FILE.read_text())
    except (OSError, ValueError):
        data = {}
    out = dict(DEFAULTS)
    if not isinstance(data, dict):
        return out
    for k, v in data.items():
        if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
            out[k] = v
    out["view"] = out["view"] if out["view"] in (0, 1) else 0
    out["sort_col"] = out["sort_col"] if 0 <= out["sort_col"] <= 3 else 0
    out["icon"] = out["icon"] if out["icon"] in ICON_SIZES else 72
    out["places"] = [p for p in out["places"] if isinstance(p, str) and os.path.isabs(p)][:MAX_PLACES]
    return out


def save(prefs: dict):
    """Atomic, so two VaultL windows never leave half a file."""
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_name(f".{FILE.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({k: prefs[k] for k in DEFAULTS if k in prefs}, indent=1))
    os.replace(tmp, FILE)


def update(**changes) -> dict:
    """Read, change, write: another VaultL window's choices made since this one started are kept."""
    prefs = load() | changes
    try:
        save(prefs)
    except OSError:
        pass                                    # a read-only config folder: the choice lasts for this run
    return prefs
