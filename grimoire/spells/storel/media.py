# SPDX-License-Identifier: GPL-3.0-or-later
"""Screenshots and remote icons (no Qt): downloaded over https only when shown, kept in CACHE/storel/media.

Only https URLs from the catalog are fetched, each at most MAX bytes, and only files that start like a PNG, JPEG,
WebP or GIF are kept (Qt decodes them; nothing else ever reads them). The cache is trimmed to KEEP bytes, oldest
first. FETCH is the stub point for tests.
"""
import hashlib
import os
import urllib.request
from pathlib import Path

from grimoire.paths import CACHE

DIR = CACHE / "storel" / "media"
MAX = 12 * 1024 * 1024
KEEP = 300 * 1024 * 1024
AGENT = "Grimoire-Linux-StoreL (+https://github.com/cookedaj/grimoire-linux)"
MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")


def _image(head: bytes) -> bool:
    return head.startswith(MAGIC) or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")


def _fetch(url: str, timeout: float = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:          # nosec: https only, checked by get()
        if not r.geturl().startswith("https://"):
            raise OSError("redirected away from https")
        data = r.read(MAX + 1)
    if len(data) > MAX:
        raise OSError("too big")
    return data


FETCH = _fetch


def path_for(url: str) -> Path:
    return DIR / hashlib.sha256(url.encode()).hexdigest()[:40]


def get(url: str) -> Path | None:
    """The image at url as a cached file; None when it can't be fetched or isn't an image."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    dest = path_for(url)
    if dest.is_file():
        try:
            os.utime(dest)
        except OSError:
            pass
        return dest
    try:
        data = FETCH(url)
    except (OSError, ValueError):
        return None
    if not _image(data[:16]):
        return None
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    except OSError:
        return None
    trim()
    return dest


def trim(keep: int = KEEP):
    """Drop the least recently shown images once the cache passes keep bytes (our own cache files only)."""
    try:
        files = [(p.stat().st_mtime, p.stat().st_size, p) for p in DIR.iterdir() if p.is_file()]
    except OSError:
        return
    total = sum(s for _t, s, _p in files)
    for _t, s, p in sorted(files):
        if total <= keep:
            break
        try:
            p.unlink()
            total -= s
        except OSError:
            pass
