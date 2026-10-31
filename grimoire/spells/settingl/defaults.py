# SPDX-License-Identifier: GPL-3.0-or-later
"""Default apps (no Qt): which program opens links, mail, folders, text, pictures, music, video and PDFs, and which
terminal KDE starts.

Read with xdg-mime (the freedesktop lookup Plasma follows). Changed only when you pick one and press Set on the page:
xdg-mime default writes your mimeapps.list, and for the browser and terminal the keys KDE's Default Applications
module writes in kdeglobals are set too. SettingL never makes itself (or any Grimoire app) a default on its own.
"""

import os
import re
from pathlib import Path

from grimoire.i18n import tr_noop
from grimoire.spells.settingl import kde

CTX = "grimoire.spells.settingl.defaults"
# id, label, the types it answers for (the first one is read to show the current choice)
KINDS = [
    (
        "browser",
        tr_noop("grimoire.spells.settingl.defaults", "Web browser"),
        ["x-scheme-handler/https", "x-scheme-handler/http", "text/html", "application/xhtml+xml"],
    ),
    ("mail", tr_noop("grimoire.spells.settingl.defaults", "Email"), ["x-scheme-handler/mailto"]),
    ("files", tr_noop("grimoire.spells.settingl.defaults", "File manager"), ["inode/directory"]),
    ("terminal", tr_noop("grimoire.spells.settingl.defaults", "Terminal"), []),
    ("text", tr_noop("grimoire.spells.settingl.defaults", "Text editor"), ["text/plain"]),
    (
        "image",
        tr_noop("grimoire.spells.settingl.defaults", "Pictures"),
        ["image/png", "image/jpeg", "image/gif", "image/webp"],
    ),
    (
        "music",
        tr_noop("grimoire.spells.settingl.defaults", "Music"),
        ["audio/mpeg", "audio/flac", "audio/ogg", "audio/x-wav"],
    ),
    ("video", tr_noop("grimoire.spells.settingl.defaults", "Videos"), ["video/mp4", "video/x-matroska", "video/webm"]),
    ("pdf", tr_noop("grimoire.spells.settingl.defaults", "PDF documents"), ["application/pdf"]),
]
DESKTOP_ID = re.compile(r"[A-Za-z0-9_.+\-]+\.desktop")


def _app_dirs() -> list[Path]:
    dirs = [Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")] + [
        Path(d) for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d
    ]
    return [d / "applications" for d in dirs]


def _entry(path: Path) -> dict:
    out, inside = {}, False
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            inside = s == "[Desktop Entry]"
        elif inside and "=" in s and not s.startswith("#"):
            k, _, v = s.partition("=")
            out[k.strip()] = v.strip()
    return out


def apps(lang: str = "") -> dict[str, dict]:
    """Every application entry: desktop id → {name, icon, mimes, categories, exec, hidden}. The first folder wins."""
    out: dict[str, dict] = {}
    for d in _app_dirs():
        for f in sorted(d.rglob("*.desktop")) if d.is_dir() else []:
            did = str(f.relative_to(d)).replace("/", "-")
            if did in out:
                continue
            e = _entry(f)
            if e.get("Type", "Application") != "Application":
                continue
            name = (
                (e.get(f"Name[{lang}]") or e.get(f"Name[{lang.split('_')[0]}]") or e.get("Name", did))
                if lang
                else e.get("Name", did)
            )
            out[did] = {
                "id": did,
                "name": name,
                "icon": e.get("Icon", ""),
                "mimes": [m for m in e.get("MimeType", "").split(";") if m],
                "categories": [c for c in e.get("Categories", "").split(";") if c],
                "exec": e.get("Exec", ""),
                "hidden": e.get("Hidden") == "true",
                "nodisplay": e.get("NoDisplay") == "true",
            }
    return out


def query(mime: str) -> str:
    r = kde.RUN(["xdg-mime", "query", "default", mime], 10)
    return r.stdout.strip() if not r.returncode else ""


def candidates(kind: str, everything: dict[str, dict]) -> list[dict]:
    """Apps that can be the default for kind, by name."""
    if kind == "terminal":
        hits = [a for a in everything.values() if "TerminalEmulator" in a["categories"]]
    else:
        mimes = next(k[2] for k in KINDS if k[0] == kind)
        hits = [a for a in everything.values() if mimes[0] in a["mimes"]]
    return sorted((a for a in hits if not a["hidden"]), key=lambda a: a["name"].casefold())


def terminal() -> str:
    g = kde.parse("kdeglobals").get(("General",), {})
    service = g.get("TerminalService", "")
    if service:
        return service
    app = g.get("TerminalApplication", "")
    if app:
        return app if app.endswith(".desktop") else f"{Path(app.split()[0]).name}.desktop"
    return "org.kde.konsole.desktop"


def read(lang: str = "") -> dict:
    """{"current": {kind: desktop id}, "apps": {...}, "choices": {kind: [app ids]}}"""
    everything = apps(lang)
    current = {kind: (terminal() if kind == "terminal" else query(mimes[0])) for kind, _, mimes in KINDS}
    choices = {kind: [a["id"] for a in candidates(kind, everything)] for kind, _, _ in KINDS}
    return {"current": current, "apps": everything, "choices": choices}


def set_default(kind: str, app_id: str, everything: dict[str, dict]):
    """Make app_id the default for kind (only called from the page's Set button)."""
    if not DESKTOP_ID.fullmatch(app_id or "") or app_id not in everything:
        raise ValueError(app_id)
    if app_id not in [a["id"] for a in candidates(kind, everything)]:
        raise ValueError(app_id)
    if kind == "terminal":
        args = [a for a in everything[app_id]["exec"].split() if not a.startswith("%")]
        kde.write("kdeglobals", "General", "TerminalApplication", args[0] if args else app_id.removesuffix(".desktop"))
        kde.write("kdeglobals", "General", "TerminalService", app_id)
        return
    mimes = next(k[2] for k in KINDS if k[0] == kind)
    mine = [m for m in mimes if m in everything[app_id]["mimes"] or m.startswith("x-scheme-handler/http")]
    kde.check(["xdg-mime", "default", app_id, *mine])
    if kind == "browser":
        kde.write("kdeglobals", "General", "BrowserApplication", app_id)
