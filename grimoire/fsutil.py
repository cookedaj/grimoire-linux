# SPDX-License-Identifier: GPL-3.0-or-later
"""File helpers shared by several spells: safe names, the Trash, and friendly sizes/paths."""
import errno
import os
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


_RENAME_NOREPLACE = 1
_libc = None


def rename_noreplace(src: Path, dest: Path):
    """os.rename that raises FileExistsError instead of replacing dest (Linux renameat2 RENAME_NOREPLACE). Where the
    kernel or filesystem can't do that, it falls back to a plain rename after an exists check (the old behavior)."""
    global _libc
    try:
        if _libc is None:
            import ctypes
            import ctypes.util
            _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
            _libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        fn = _libc.renameat2
    except (OSError, AttributeError):
        fn = None
    if fn is not None:
        import ctypes
        AT_FDCWD = -100
        if fn(AT_FDCWD, os.fsencode(src), AT_FDCWD, os.fsencode(dest), _RENAME_NOREPLACE) == 0:
            return
        err = ctypes.get_errno()
        if err not in (errno.EINVAL, errno.ENOSYS):        # EINVAL: this filesystem has no NOREPLACE
            raise OSError(err, os.strerror(err), str(dest))
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(dest))
    os.rename(src, dest)


def move_free(src: Path, dest: Path) -> Path:
    """Move src to dest or the next free 'name (2)' beside it, never over anything, even if a name gets taken
    between the check and the move. Returns where it went."""
    while True:
        target = free_name(dest)
        try:
            rename_noreplace(src, target)
            return target
        except FileExistsError:
            continue


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
