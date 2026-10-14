# SPDX-License-Identifier: GPL-3.0-or-later
"""File helpers shared by several spells: safe names, the Trash, and friendly sizes/paths."""
import subprocess
import sys
from pathlib import Path

from grimoire.i18n import tr, tr_noop
from grimoire.paths import HOME

UNITS = {"B": tr_noop("grimoire.fsutil", "{n} B"), "KB": tr_noop("grimoire.fsutil", "{n} KB"),
         "MB": tr_noop("grimoire.fsutil", "{n} MB"), "GB": tr_noop("grimoire.fsutil", "{n} GB"),
         "TB": tr_noop("grimoire.fsutil", "{n} TB")}


def free_name(dest: Path) -> Path:
    """dest, or 'name (2).ext', 'name (3).ext'… if taken. Never overwrites (broken symlinks count as taken)."""
    if not dest.exists() and not dest.is_symlink():
        return dest
    stem, suffix = (dest.name, "") if dest.is_dir() else (dest.stem, dest.suffix)
    n = 2
    while True:
        cand = dest.with_name(f"{stem} ({n}){suffix}")
        if not cand.exists() and not cand.is_symlink():
            return cand
        n += 1


def trash(path: Path):
    """Move one file or folder to the freedesktop Trash (the one Dolphin uses). Raises OSError on failure."""
    r = subprocess.run(["gio", "trash", str(path)], capture_output=True, text=True)
    if r.returncode:
        raise OSError(r.stderr.strip() or f"couldn't trash {path}")


def human(n: float) -> str:
    """1536 -> '1.5 KB'. In a process that loaded a language (i18n.install / install_catalogs) the number and unit
    follow it ('1,5 Ko'); otherwise, and always in English, exactly as above, with no Qt import (CLI use)."""
    for unit in UNITS:
        if n < 1024 or unit == "TB":
            break
        n /= 1024
    digits = 0 if unit == "B" else 1
    from grimoire import i18n
    if i18n.loaded() in ("", "en") or "PySide6.QtCore" not in sys.modules:
        return f"{n:.{digits}f} {unit}"
    from PySide6.QtCore import QLocale
    loc = QLocale()                                # i18n set the default to the language in use
    loc.setNumberOptions(QLocale.NumberOption.OmitGroupSeparator)
    return tr("grimoire.fsutil", UNITS[unit]).format(n=loc.toString(float(n), "f", digits))


def tilde(p: Path | str) -> str:
    """Show paths under home as ~/…"""
    s, home = str(p), str(HOME)
    return "~" + s[len(home):] if s == home or s.startswith(home + "/") else s
