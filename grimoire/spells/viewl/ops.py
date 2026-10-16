# SPDX-License-Identifier: GPL-3.0-or-later
"""ViewL's file changes, all run on worker threads and all asked for by a click first:

- saving a turned/flipped picture: JPEGs losslessly (only the EXIF Orientation tag changes), other formats re-encoded
  (PNG and WebP losslessly). Replacing the original sends the old file to the Trash first; "Save as" never
  overwrites (an existing name becomes "name (2).ext").
- rename (refuses a name that's taken), Trash, copy/move into a folder (VaultL's transfer, so clashes get free names)
- set as wallpaper: into MuraL's library, then MuraL's own apply (every desktop).
"""

import os
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader, QImageWriter, QTransform

from grimoire.fsutil import free_name, trash
from grimoire.i18n import tr
from grimoire.paths import CACHE
from grimoire.spells.viewl import exif

JPEG = {".jpg", ".jpeg", ".jpe", ".jfif"}
QUALITY = {"jpg": 95, "jpeg": 95, "webp": 100, "avif": 90, "jxl": 95, "heif": 90, "heic": 90}


def writable(suffix: str) -> bool:
    fmt = suffix.lower().lstrip(".")
    return fmt in {bytes(f).decode().lower() for f in QImageWriter.supportedImageFormats()} or fmt in ("jpe", "jfif")


def lossless(src: Path, dest: Path) -> bool:
    """A JPEG kept as a JPEG turns without touching its pixels."""
    return src.suffix.lower() in JPEG and dest.suffix.lower() in JPEG


def _turned_bytes(src: Path, orient: int) -> bytes:
    data = src.read_bytes()
    return exif.set_jpeg_orientation(data, exif.then(exif.orientation(src), orient))


def _encode(src: Path, orient: int, dest: Path):
    reader = QImageReader(str(src))
    reader.setAutoTransform(True)
    img = reader.read()
    if img.isNull():
        raise OSError(reader.errorString())
    if orient != 1:
        a, b, c, d = exif.ORIENT[orient]
        img = img.transformed(QTransform(a, c, b, d, 0, 0))
    fmt = dest.suffix.lower().lstrip(".")
    fmt = "jpg" if fmt in ("jpe", "jfif", "jpeg") else fmt
    if fmt == "jpg" and img.hasAlphaChannel():
        img = img.convertToFormat(QImage.Format.Format_RGB32)
    writer = QImageWriter(str(dest), fmt.encode())
    writer.setQuality(QUALITY.get(fmt, -1))
    if not writer.write(img):
        raise OSError(writer.errorString())


def _write(src: Path, orient: int, tmp: Path, dest_suffix_from: Path):
    if lossless(src, dest_suffix_from):
        tmp.write_bytes(_turned_bytes(src, orient))
    else:
        tmp_fmt = tmp.with_suffix(dest_suffix_from.suffix)  # QImageWriter picks the format by name
        try:
            _encode(src, orient, tmp_fmt)
            os.replace(tmp_fmt, tmp)
        finally:
            tmp_fmt.unlink(missing_ok=True)


def _tmp(next_to: Path) -> Path:
    return next_to.with_name(f".{next_to.name}.viewl-{os.getpid()}.tmp")


def save_turned(src: Path, orient: int, dest: Path | None = None) -> Path:
    """Write src turned by orient (an EXIF orientation value). dest None replaces src (the old file goes to the
    Trash first); otherwise dest, or a free name next to it. Returns the file written. Raises OSError."""
    target = src if dest is None else dest
    if not lossless(src, target) and not writable(target.suffix):
        raise OSError(tr("grimoire.spells.viewl.ops", "This format can't be written here; save as PNG or JPEG"))
    tmp = _tmp(target)
    try:
        _write(src, orient, tmp, target)
        if dest is None:
            try:
                os.chmod(tmp, src.stat().st_mode & 0o7777)
            except OSError:
                pass
            trash(src)  # the original stays recoverable
            os.replace(tmp, src)
            return src
        target = free_name(target)
        os.replace(tmp, target)
        return target
    except ValueError as e:  # EXIF we can't safely change
        raise OSError(str(e)) from e
    finally:
        tmp.unlink(missing_ok=True)


def save_copy(src: Path, dest: Path) -> Path:
    """Save as without turns: a plain copy when the format stays, else re-encoded. Never overwrites."""
    if src.suffix.lower() == dest.suffix.lower() or lossless(src, dest):
        import shutil

        target = free_name(dest)
        shutil.copy2(src, target)
        return target
    return save_turned(src, 1, dest)


def rename(path: Path, name: str) -> Path:
    name = name.strip()
    if not name or name in (".", "..") or "/" in name or "\0" in name:
        raise OSError(tr("grimoire.spells.viewl.ops", "That isn't a usable file name"))
    dest = path.with_name(name)
    if dest == path:
        return path
    if dest.exists() or dest.is_symlink():
        raise OSError(tr("grimoire.spells.viewl.ops", "A file called {name} is already there").format(name=name))
    os.rename(path, dest)
    return dest


def to_trash(paths: list[Path]) -> list[str]:
    errors = []
    for p in paths:
        try:
            trash(p)
        except OSError as e:
            errors.append(f"{p.name}: {e}")
    return errors


def transfer(paths: list[Path], folder: Path, move: bool) -> tuple[int, list[str]]:
    from grimoire.spells.vaultl.ops import transfer as vault_transfer

    return vault_transfer(paths, folder, move)


def set_wallpaper(path: Path, orient: int = 1) -> Path:
    """Put the picture (turned, if it is) in MuraL's library and make it every desktop's wallpaper with MuraL's
    apply. Returns the library copy. Raises OSError/RuntimeError with what went wrong."""
    from grimoire.spells.mural import library, plasma

    src = path
    if orient != 1 or path.suffix.lower() not in library.IMAGE_EXT | library.VIDEO_EXT:
        out = CACHE / "viewl" / "wallpaper"  # formats the wallpaper can't show become a PNG first
        out.mkdir(parents=True, exist_ok=True)
        src = out / (path.stem + ".png")
        src.unlink(missing_ok=True)  # our own scratch copy from a previous click
        _encode(path, orient, src)
    added = library.add([src])
    if not added:
        raise OSError(tr("grimoire.spells.viewl.ops", "MuraL's library didn't take this picture"))
    settings = plasma.Settings.load()
    settings.items = [str(added[0])]
    plasma.apply(settings)
    return added[0]
