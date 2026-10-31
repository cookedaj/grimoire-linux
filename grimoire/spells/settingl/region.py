# SPDX-License-Identifier: GPL-3.0-or-later
"""Language & region (no Qt): Plasma's language and formats, and the system locale.

Plasma keeps them in plasma-localerc ([Translations] LANGUAGE, [Formats] LANG/LC_*), which startplasma exports at
the next login; written with kwriteconfig6 like KDE's Region & Language module. Only locales the system already
has (locale -a) are offered: generating a new one needs root, which KDE's own module does.
"""

import re
from pathlib import Path

from grimoire.spells.settingl import kde

LOCALE = re.compile(r"[a-z]{2,3}(_[A-Z]{2})?(@[a-z]+)?")
FORMAT = re.compile(r"[a-z]{2,3}_[A-Z]{2}\.UTF-8(@[a-z]+)?")
LOCALE_DIRS = [Path("/usr/share/locale"), Path("/usr/local/share/locale")]


def read() -> dict:
    cfg = kde.parse("plasma-localerc")
    tr, fmt = cfg.get(("Translations",), {}), cfg.get(("Formats",), {})
    system = kde.bus_props(
        "org.freedesktop.locale1", "/org/freedesktop/locale1", "org.freedesktop.locale1", system=True
    ).get("Locale", [])
    sys_lang = next((s.split("=", 1)[1] for s in system if s.startswith("LANG=")), "")
    return {
        "language": tr.get("LANGUAGE", ""),
        "formats": fmt.get("LANG", ""),
        "time": fmt.get("LC_TIME", ""),
        "system": sys_lang,
    }


def languages() -> list[str]:
    """Languages Plasma itself is translated into here (it has plasmashell's catalog), plus English."""
    found = {"en_US"}
    for d in LOCALE_DIRS:
        for mo in d.glob("*/LC_MESSAGES/plasmashell.mo") if d.is_dir() else []:
            code = mo.parent.parent.name
            if LOCALE.fullmatch(code):
                found.add(code)
    return sorted(found)


def formats() -> list[str]:
    """The UTF-8 locales this system has generated, as Plasma writes them (en_GB.UTF-8)."""
    r = kde.RUN(["locale", "-a"], 10)
    out = set()
    for name in r.stdout.split() if not r.returncode else []:
        base, _, enc = name.partition(".")
        enc, _, mod = enc.partition("@")
        if enc.lower().replace("-", "") == "utf8" and "_" in base:
            full = f"{base}.UTF-8" + (f"@{mod}" if mod else "")
            if FORMAT.fullmatch(full):
                out.add(full)
    return sorted(out)


def set_language(code: str):
    """Plasma's language from the next login ("" = the system's)."""
    if code and not LOCALE.fullmatch(code):
        raise ValueError(code)
    kde.write("plasma-localerc", "Translations", "LANGUAGE", code or None, notify=False)


def set_formats(name: str):
    """Number, date and currency formats from the next login ("" = like the language)."""
    if name and not FORMAT.fullmatch(name):
        raise ValueError(name)
    kde.write("plasma-localerc", "Formats", "LANG", name or None, notify=False)
