# SPDX-License-Identifier: GPL-3.0-or-later
"""GameL's settings and the MangoHud overlay: a black & white MangoHud.conf, and whether games GameL starts get
MANGOHUD=1. Everything is a manual switch: GameL never changes the crosshair, optimizations or anything else when a
game starts. No Qt.

MangoHud reads ~/.config/MangoHud/MangoHud.conf for every game it's loaded into, so the look applies to Steam games
started with `mangohud %command%` too. A MangoHud.conf GameL didn't write is moved aside (never overwritten) first.
"""
import json
import os
import re
import shutil
from pathlib import Path

from grimoire.fsutil import move_free
from grimoire.i18n import tr_noop
from grimoire.paths import CONFIG

MARKER = "# Written by Grimoire Linux GameL"
STEAM_OPTION = "mangohud %command%"
DEFAULTS = {"mangohud": False, "toggle": "Shift_R+F12", "position": "top-left", "compact": False,
            "view": "grid", "sort": "name"}
# shown with tr("grimoire.spells.gamel.overlay", …)
POSITIONS = {"top-left": tr_noop("grimoire.spells.gamel.overlay", "Top left"),
             "top-right": tr_noop("grimoire.spells.gamel.overlay", "Top right"),
             "bottom-left": tr_noop("grimoire.spells.gamel.overlay", "Bottom left"),
             "bottom-right": tr_noop("grimoire.spells.gamel.overlay", "Bottom right"),
             "top-center": tr_noop("grimoire.spells.gamel.overlay", "Top center")}
SORTS = ("name", "last", "size", "playtime")
KEY_RE = re.compile(r"^[A-Za-z0-9_]{1,24}(\+[A-Za-z0-9_]{1,24}){0,3}$")
MONO = Path("/usr/share/fonts/truetype/ibm-plex/IBMPlexMono-Medium.ttf")


def settings_file() -> Path:
    return CONFIG / "gamel.json"


def load() -> dict:
    try:
        d = json.loads(settings_file().read_text())
    except (OSError, ValueError):
        d = {}
    out = dict(DEFAULTS)
    if isinstance(d, dict):
        for k, v in d.items():
            if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
                out[k] = v
    if out["position"] not in POSITIONS:
        out["position"] = DEFAULTS["position"]
    if not KEY_RE.match(out["toggle"]):
        out["toggle"] = DEFAULTS["toggle"]
    if out["sort"] not in SORTS:
        out["sort"] = DEFAULTS["sort"]
    return out


def save(d: dict):
    f = settings_file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: d[k] for k in DEFAULTS if k in d}, indent=1))
    tmp.replace(f)


# ---------------------------------------------------------------- MangoHud
def installed() -> bool:
    return bool(shutil.which("mangohud"))


def conf_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "MangoHud/MangoHud.conf"


def ours(path: Path | None = None) -> bool:
    try:
        with open(path or conf_path(), encoding="utf-8", errors="replace") as f:
            return f.readline().startswith(MARKER)
    except OSError:
        return False


def conf_text(s: dict) -> str:
    """The black & white MangoHud style: FPS, frame times, CPU and GPU load and temperature, RAM and VRAM."""
    white = "FFFFFF"
    lines = [MARKER + " (black & white style). GameL rewrites this file when you change its overlay settings;",
             "# To keep your own edits, delete this file's first line: GameL then moves the file aside instead.",
             "legacy_layout=false",
             "fps", "frametime", "frame_timing=1",
             "cpu_stats", "cpu_temp", "gpu_stats", "gpu_temp",
             "ram", "vram",
             f"position={s['position']}",
             f"toggle_hud={s['toggle']}",
             "font_size=20", "round_corners=6", "background_alpha=0.55", "background_color=000000",
             f"text_color={white}", f"gpu_color={white}", f"cpu_color={white}", f"vram_color={white}",
             f"ram_color={white}", f"engine_color={white}", f"io_color={white}", f"frametime_color={white}",
             f"media_player_color={white}", f"wine_color={white}", f"battery_color={white}",
             f"network_color={white}", f"horizontal_separator_color={white}",
             "fps_color_change=0", "cpu_load_change=0", "gpu_load_change=0"]
    if s.get("compact"):
        lines += ["horizontal", "hud_compact", "table_columns=14"]
    else:
        lines += ["table_columns=3"]
    if MONO.is_file():
        lines.append(f"font_file={MONO}")
    return "\n".join(lines) + "\n"


def write_conf(s: dict) -> Path | None:
    """Write GameL's MangoHud.conf. A file someone else wrote is moved to "MangoHud.conf.before-gamel" first
    (free_name: never over an older copy); returns where it went, else None."""
    path = conf_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    moved = None
    if (path.exists() or path.is_symlink()) and not ours(path):
        moved = move_free(path, path.with_name(path.name + ".before-gamel"))
    tmp = path.with_name(path.name + ".gamel-tmp")
    tmp.unlink(missing_ok=True)                # a leftover (or a symlink) there must not be written through
    tmp.write_text(conf_text(s), encoding="utf-8")
    tmp.replace(path)
    return moved


def set_overlay(on: bool) -> Path | None:
    """The manual on/off: on writes the style and makes GameL start Heroic and Lutris games with MANGOHUD=1. Off
    only stops that; the style file stays, so Steam's `mangohud %command%` keeps the look."""
    s = load() | {"mangohud": on}
    moved = write_conf(s) if on else None
    save(s)
    return moved


def env(s: dict | None = None) -> dict:
    """Extra environment for a game GameL starts (empty when the overlay is off or MangoHud isn't installed)."""
    s = s or load()
    return {"MANGOHUD": "1"} if s["mangohud"] and installed() else {}
