# SPDX-License-Identifier: GPL-3.0-or-later
"""Every installed KDE settings module (KCM), so nothing System Settings can do is out of reach.

Read from the modules' own metadata: QPluginLoader reads the JSON embedded in each plugin without loading it, and
.desktop entries cover modules that ship only those. Names, descriptions, keywords and System Settings' category
names come in the language KDE has for ours (else English). Opening one runs kcmshell6 (kde.OPEN). QtCore only.
"""

import os
import re
from pathlib import Path

from grimoire import i18n
from grimoire.spells.settingl import kde

PLUGIN_GROUPS = ("systemsettings", "systemsettings_qwidgets", "kinfocenter", "desktop")
CATEGORIES = [
    Path(d) / "systemsettings/categories"
    for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    if d
]
# KDE's locale names for ours (KDE has no Bengali or Urdu names for most modules: those fall back to English)
KDE_LANG = {"pt": "pt_BR"}
SKIP = {"kcm_landingpage"}  # System Settings' own start page: ours is SettingL


def _lang() -> str:
    code = i18n.loaded() or i18n.current()
    return KDE_LANG.get(code, code)


def _local(data: dict, key: str, lang: str) -> str:
    for k in (f"{key}[{lang}]", f"{key}[{lang.split('_')[0]}]", key):
        if data.get(k):
            return str(data[k])
    return ""


def _plugin_dirs() -> list[Path]:
    from PySide6.QtCore import QLibraryInfo

    roots = [p for p in os.environ.get("QT_PLUGIN_PATH", "").split(":") if p]
    roots.append(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    return [Path(r) / "plasma/kcms" / g for r in dict.fromkeys(roots) for g in PLUGIN_GROUPS]


def _desktop(path: Path) -> dict:
    """A .desktop file's [Desktop Entry] keys."""
    out, inside = {}, False
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            inside = line == "[Desktop Entry]"
            continue
        if inside and "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def categories(lang: str | None = None) -> dict[str, dict]:
    """System Settings' categories: id → {name, parent, weight}."""
    lang = lang or _lang()
    out: dict[str, dict] = {}
    for folder in reversed(CATEGORIES):
        for f in sorted(folder.glob("*.desktop")) if folder.is_dir() else []:
            d = _desktop(f)
            cid = d.get("X-KDE-System-Settings-Category")
            if cid:
                out[cid] = {
                    "name": _local(d, "Name", lang),
                    "parent": d.get("X-KDE-System-Settings-Parent-Category", ""),
                    "weight": kde.as_int(d.get("X-KDE-Weight", ""), 100),
                }
    return out


def _keywords(text: str) -> list[str]:
    return [k.strip() for k in re.split(r"[,;]", text or "") if k.strip()]


def _from_plugin(path: Path, lang: str) -> dict | None:
    from PySide6.QtCore import QPluginLoader

    meta = QPluginLoader(str(path)).metaData().get("MetaData", {})
    kp = meta.get("KPlugin", {})
    if not kp:
        return None
    forms = kp.get("FormFactors")
    if forms and "desktop" not in forms:
        return None  # phone/tablet modules (Plasma Mobile)
    return {
        "id": path.stem,
        "name": _local(kp, "Name", lang) or path.stem,
        "name_en": kp.get("Name", path.stem),
        "description": _local(kp, "Description", lang),
        "description_en": kp.get("Description", ""),
        "icon": kp.get("Icon", ""),
        "keywords": _keywords(_local(meta, "X-KDE-Keywords", lang)) + _keywords(meta.get("X-KDE-Keywords", "")),
        "category": meta.get("X-KDE-System-Settings-Parent-Category", "") or "",
        "weight": kde.as_int(str(meta.get("X-KDE-Weight", "")), 100),
        "group": path.parent.name,
        "exec": None,
    }


def _applications() -> list[Path]:
    dirs = [Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")] + [
        Path(d) for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d
    ]
    return [d / "applications" for d in dirs]


def _exec_args(exec_line: str) -> list[str]:
    import shlex

    try:
        return [a for a in shlex.split(exec_line) if not re.fullmatch(r"%[a-zA-Z]", a)]
    except ValueError:
        return []


def scan() -> list[dict]:
    """All the modules, sorted by name (in the language shown). Slow-ish (≈100 files): call it off the UI thread."""
    lang = _lang()
    found: dict[str, dict] = {}
    skipped = set(SKIP)
    for folder in _plugin_dirs():
        for f in sorted(folder.glob("*.so")) if folder.is_dir() else []:
            if f.stem in found or f.stem in skipped:
                continue
            try:
                m = _from_plugin(f, lang)
            except Exception:  # one broken plugin mustn't hide the others
                m = None
            if m:
                found[f.stem] = m
            else:
                skipped.add(f.stem)
    for folder in _applications():
        for f in sorted(folder.glob("*.desktop")) if folder.is_dir() else []:
            d = _desktop(f)
            args = _exec_args(d.get("Exec", ""))
            if len(args) != 2 or Path(args[0]).name not in ("systemsettings", "kcmshell6", "kinfocenter"):
                continue  # a module with arguments is an action (import a VPN…)
            mid = args[1]
            if mid in found:  # fill in what a plugin left out
                found[mid]["icon"] = found[mid]["icon"] or d.get("Icon", "")
                continue
            if mid in skipped or d.get("Hidden") == "true" or not re.fullmatch(r"[\w.-]+", mid):
                continue
            found[mid] = {
                "id": mid,
                "name": _local(d, "Name", lang) or mid,
                "name_en": d.get("Name", mid),
                "description": _local(d, "Comment", lang) or _local(d, "GenericName", lang),
                "description_en": d.get("Comment", ""),
                "icon": d.get("Icon", ""),
                "keywords": _keywords(_local(d, "X-KDE-Keywords", lang))
                + _keywords(_local(d, "Keywords", lang))
                + _keywords(d.get("X-KDE-Keywords", "")),
                "category": "",
                "weight": 100,
                "group": "desktop-file",
                "exec": args,
            }
    cats = categories(lang)
    for m in found.values():
        c = cats.get(m["category"])
        m["category_name"] = c["name"] if c else ""
        m["keywords"] = list(dict.fromkeys(m["keywords"]))
    return sorted(found.values(), key=lambda m: m["name"].casefold())


def open_module(m: dict | str):
    """Open a module from scan() (or by id) in KDE's own window."""
    if isinstance(m, dict) and m.get("exec"):
        kde.LAUNCH(m["exec"])
    else:
        kde.OPEN(m["id"] if isinstance(m, dict) else m)


def score(m: dict, words: list[str]) -> int:
    """How well a module matches every search word (0 = not at all): names first, then keywords, then the rest."""
    total = 0
    names = (m["name"].casefold(), m["name_en"].casefold(), m["id"].casefold())
    keys = [k.casefold() for k in m["keywords"]]
    rest = " ".join((m["description"], m["description_en"], m.get("category_name", ""))).casefold()
    for w in words:
        if any(n.startswith(w) for n in names):
            total += 30
        elif any(w in n for n in names):
            total += 20
        elif any(k.startswith(w) for k in keys):
            total += 12
        elif any(w in k for k in keys):
            total += 8
        elif w in rest:
            total += 4
        else:
            return 0
    return total


def search(mods: list[dict], text: str) -> list[dict]:
    words = [w for w in text.casefold().split() if w]
    if not words:
        return list(mods)
    hits = [(score(m, words), m) for m in mods]
    return [m for s, m in sorted(hits, key=lambda h: (-h[0], h[1]["name"].casefold())) if s]
