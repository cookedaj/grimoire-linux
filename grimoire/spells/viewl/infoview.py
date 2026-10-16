# SPDX-License-Identifier: GPL-3.0-or-later
"""The info panel beside the picture: file facts, then what the camera wrote (EXIF), read on a worker thread."""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, QLocale, QSize, Qt
from PySide6.QtGui import QImageIOHandler, QImageReader
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from grimoire.fsutil import human, tilde
from grimoire.i18n import isolate, ltr, tr
from grimoire.spells.viewl import exif


def gather(path: Path) -> dict:
    """Everything the panel shows about one file (worker thread)."""
    info = {"path": path, "exif": exif.read(path)}
    try:
        st = path.stat()
        info["bytes"], info["mtime"] = st.st_size, st.st_mtime
    except OSError:
        pass
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and reader.transformation() & QImageIOHandler.Transformation.TransformationRotate90:
        size = QSize(size.height(), size.width())
    info["size"] = size
    info["fmt"] = bytes(reader.format()).decode().upper()
    info["frames"] = reader.imageCount() if reader.supportsAnimation() else 1
    return info


def _when(ts: float) -> str:
    fmt = tr("grimoire.spells.viewl.infoview", "d MMM yyyy, HH:mm", "QLocale date and time format")
    return QLocale().toString(QDateTime.fromSecsSinceEpoch(int(ts)), fmt)


def _taken(text: str) -> str:
    """EXIF dates look like '2024:05:01 10:00:00'."""
    try:
        return _when(datetime.strptime(str(text)[:19], "%Y:%m:%d %H:%M:%S").timestamp())
    except (ValueError, OverflowError, OSError):
        return str(text)


def _num(x: float, digits: int = 1) -> str:
    return (
        QLocale().toString(float(x), "f", digits).rstrip("0").rstrip(QLocale().decimalPoint())
        if digits
        else QLocale().toString(int(round(x)))
    )


def rows(info: dict) -> list[tuple[str, str]]:
    p: Path = info["path"]
    out = [
        (tr("grimoire.spells.viewl.infoview", "File"), isolate(p.name)),
        (tr("grimoire.spells.viewl.infoview", "Folder"), ltr(tilde(p.parent))),
    ]
    if "bytes" in info:
        out.append((tr("grimoire.spells.viewl.infoview", "Size"), ltr(human(info["bytes"]))))
    size: QSize = info.get("size") or QSize()
    if size.isValid():
        mp = size.width() * size.height() / 1e6
        dims = f"{size.width()} × {size.height()}"
        out.append(
            (
                tr("grimoire.spells.viewl.infoview", "Dimensions"),
                tr("grimoire.spells.viewl.infoview", "{size} ({mp} MP)").format(size=ltr(dims), mp=_num(mp))
                if mp >= 0.1
                else ltr(dims),
            )
        )
    if info.get("fmt"):
        out.append((tr("grimoire.spells.viewl.infoview", "Format"), info["fmt"]))
    if info.get("frames", 1) > 1:
        out.append(
            (
                tr("grimoire.spells.viewl.infoview", "Animation"),
                tr("grimoire.spells.viewl.infoview", "%n frame(s)", n=info["frames"]),
            )
        )
    if "mtime" in info:
        out.append((tr("grimoire.spells.viewl.infoview", "Modified"), _when(info["mtime"])))
    e = info.get("exif") or {}
    if not e:
        return out
    out.append(("", ""))  # a gap before the camera's part
    if e.get("taken") or e.get("datetime"):
        out.append((tr("grimoire.spells.viewl.infoview", "Taken"), _taken(e.get("taken") or e["datetime"])))
    make, model = str(e.get("make", "")), str(e.get("model", ""))
    camera = model if make and model.lower().startswith(make.split()[0].lower()) else f"{make} {model}".strip()
    if camera:
        out.append((tr("grimoire.spells.viewl.infoview", "Camera"), isolate(camera)))
    if e.get("lens"):
        out.append((tr("grimoire.spells.viewl.infoview", "Lens"), isolate(e["lens"])))
    if isinstance(e.get("exposure"), float) and e["exposure"] > 0:
        t = e["exposure"]
        shown = f"1/{round(1 / t)}" if t < 0.5 else _num(t)
        out.append(
            (
                tr("grimoire.spells.viewl.infoview", "Exposure"),
                tr("grimoire.spells.viewl.infoview", "{time} s").format(time=ltr(shown)),
            )
        )
    if isinstance(e.get("fnumber"), float) and e["fnumber"] > 0:
        out.append((tr("grimoire.spells.viewl.infoview", "Aperture"), ltr(f"f/{_num(e['fnumber'])}")))
    iso = e.get("iso")
    if isinstance(iso, tuple):
        iso = iso[0]
    if isinstance(iso, int) and iso > 0:
        out.append(("ISO", ltr(str(iso))))
    if isinstance(e.get("focal"), float) and e["focal"] > 0:
        focal = tr("grimoire.spells.viewl.infoview", "{mm} mm").format(mm=_num(e["focal"]))
        if isinstance(e.get("focal35"), int) and e["focal35"] > 0:
            focal = tr("grimoire.spells.viewl.infoview", "{mm} mm ({full} mm on 35 mm film)").format(
                mm=_num(e["focal"]), full=e["focal35"]
            )
        out.append((tr("grimoire.spells.viewl.infoview", "Focal length"), focal))
    if isinstance(e.get("bias"), float) and e["bias"]:
        out.append((tr("grimoire.spells.viewl.infoview", "Exposure bias"), ltr(f"{e['bias']:+.1f} EV")))
    if isinstance(e.get("flash"), int):
        out.append(
            (
                tr("grimoire.spells.viewl.infoview", "Flash"),
                tr("grimoire.spells.viewl.infoview", "Fired")
                if e["flash"] & 1
                else tr("grimoire.spells.viewl.infoview", "Didn't fire"),
            )
        )
    where = exif.gps(e)
    if where:
        out.append((tr("grimoire.spells.viewl.infoview", "Location"), ltr(f"{where[0]:.5f}, {where[1]:.5f}")))
    for key, label in (
        ("software", tr("grimoire.spells.viewl.infoview", "Software")),
        ("artist", tr("grimoire.spells.viewl.infoview", "Artist")),
        ("copyright", tr("grimoire.spells.viewl.infoview", "Copyright")),
    ):
        if isinstance(e.get(key), str) and e[key]:
            out.append((label, isolate(e[key])))
    return out


class InfoPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.setMinimumWidth(270)
        self.setMaximumWidth(340)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("Panel")
        self.box = QVBoxLayout(body)
        self.box.setContentsMargins(18, 18, 18, 18)
        self.box.setSpacing(12)
        head = QLabel(tr("grimoire.spells.viewl.infoview", "INFO"))
        head.setObjectName("NavSection")
        self.box.addWidget(head)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(9)
        self.grid.setColumnStretch(1, 1)
        self.box.addLayout(self.grid)
        self.box.addStretch(1)
        scroll.setWidget(body)
        lay.addWidget(scroll)

    def clear(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()

    def show_info(self, info: dict | None):
        self.clear()
        if not info:
            return
        for i, (label, value) in enumerate(rows(info)):
            if not label:
                gap = QFrame()
                gap.setObjectName("Rule")
                gap.setFixedHeight(1)
                self.grid.addWidget(gap, i, 0, 1, 2)
                continue
            k = QLabel(label)
            k.setObjectName("Muted")
            k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            v = QLabel(value)
            v.setTextFormat(Qt.TextFormat.PlainText)  # names and EXIF text come from the file
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.grid.addWidget(k, i, 0)
            self.grid.addWidget(v, i, 1)
