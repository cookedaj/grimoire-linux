# SPDX-License-Identifier: GPL-3.0-or-later
"""Previews for WidgetL's page: each widget's own Face.qml (plain QtQuick, no Plasma) rendered offscreen with sample
data, so the page shows exactly what the widget draws. Rendering runs in a child process (a QML scene can't share
the page's QApplication offscreen), and the PNGs are cached by the face's files and the language, so they're redrawn
only after an update or a language change. The faces' i18n()/i18nc() come from Plasma in the real widget; here a
stand-in reads the same .mo catalogs (plasmai18n.py) in Grimoire's language.

    QT_QPA_PLATFORM=offscreen python3 -m grimoire.spells.widgetl.preview OUTDIR [id ...]
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from grimoire import i18n
from grimoire.paths import CACHE, ROOT
from grimoire.spells.widgetl import plasmai18n, widgets

SCALE = 2                                   # rendered at twice the size, shown at device pixel ratio 2
DIR = CACHE / "widgetl"

_HISTORY = [14, 18, 25, 22, 30, 41, 38, 35, 28, 22, 20, 26, 33, 45, 52, 48, 40, 31, 27, 24, 22, 29, 35, 31, 26, 23]
SAMPLES = {
    "clock": {"showSeconds": False, "use24h": True, "showDate": True},
    "system": {"cpu": 23, "ram": 41, "gpu": 12, "cpuTemp": 54, "gpuTemp": 61, "ramDetail": "12.6 of 31 GB",
               "cpuHistory": _HISTORY},
    "weather": {"hasData": True, "place": "Lisbon, Portugal", "temperature": 18.4, "feelsLike": 16.2, "code": 2,
                "wind": 12, "humidity": 70,
                "days": [{"name": "Thu", "code": 0, "high": 21, "low": 12}, {"name": "Fri", "code": 3, "high": 19,
                         "low": 13}, {"name": "Sat", "code": 61, "high": 17, "low": 12},
                         {"name": "Sun", "code": 95, "high": 16, "low": 11},
                         {"name": "Mon", "code": 2, "high": 18, "low": 11}]},
    "nowplaying": {"hasPlayer": True, "title": "Night Drive", "artist": "Grimoire", "album": "Black & White",
                   "playing": True, "position": 132, "length": 254},
}


def face(wid: str) -> Path:
    return widgets.source_dir(wid) / "contents" / "ui" / "Face.qml"


def language() -> str:
    return i18n.loaded() or i18n.current()


def _digest(wid: str) -> str:
    lang = language()
    h = hashlib.sha256(json.dumps(SAMPLES.get(wid, {}), sort_keys=True).encode() + str(SCALE).encode()
                       + lang.encode())
    ui = face(wid).parent
    for p in sorted(ui.glob("*.qml")):
        h.update(p.name.encode() + p.read_bytes())
    mo = plasmai18n.mo_path(widgets.get(wid).plugin, lang, widgets.source_dir(wid))
    if lang != "en" and mo.is_file():
        h.update(mo.read_bytes())
    return h.hexdigest()[:16]


def cached(wid: str) -> Path | None:
    try:
        path = DIR / f"{wid}-{_digest(wid)}.png"
    except OSError:
        return None
    return path if path.is_file() else None


def ensure(timeout: float = 60) -> tuple[dict, str]:
    """({id: PNG path or None}, error text) — renders the ones missing from the cache in a child process."""
    missing = [w.id for w in widgets.WIDGETS if cached(w.id) is None]
    error = ""
    if missing:
        DIR.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", GRIMOIRE_LANG=language(),
                   PYTHONPATH=str(ROOT) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""))
        try:
            r = subprocess.run([sys.executable, "-P", "-m", "grimoire.spells.widgetl.preview", str(DIR), *missing],
                               capture_output=True, text=True, timeout=timeout, env=env)
            error = r.stderr.strip() if r.returncode else ""
        except (OSError, subprocess.TimeoutExpired) as err:
            error = str(err)
    return {w.id: cached(w.id) for w in widgets.WIDGETS}, error


def _stand_in(plugin: str, lang: str):
    """A QML context object with Plasma's i18n()/i18nc() (up to five %1.. arguments), from the package's catalog."""
    from PySide6.QtCore import QObject, Slot

    tr, trc = plasmai18n.translator(plugin, lang, widgets.source_dir(plugin.removeprefix(widgets.PREFIX)))

    class Translations(QObject):
        @Slot(str, result=str)
        @Slot(str, "QVariant", result=str)
        @Slot(str, "QVariant", "QVariant", result=str)
        @Slot(str, "QVariant", "QVariant", "QVariant", result=str)
        @Slot(str, "QVariant", "QVariant", "QVariant", "QVariant", result=str)
        @Slot(str, "QVariant", "QVariant", "QVariant", "QVariant", "QVariant", result=str)
        def i18n(self, text, *args):
            return tr(text, *args)

        @Slot(str, str, result=str)
        @Slot(str, str, "QVariant", result=str)
        @Slot(str, str, "QVariant", "QVariant", result=str)
        @Slot(str, str, "QVariant", "QVariant", "QVariant", result=str)
        @Slot(str, str, "QVariant", "QVariant", "QVariant", "QVariant", result=str)
        @Slot(str, str, "QVariant", "QVariant", "QVariant", "QVariant", "QVariant", result=str)
        def i18nc(self, context, text, *args):
            return trc(context, text, *args)
    return Translations(), tr, trc


def render(out: Path, ids: list[str]) -> int:
    """The child process: render each face to OUT/<id>-<digest>.png, dropping that widget's older previews."""
    from PySide6.QtCore import QDate, QDateTime, QEventLoop, QLocale, QTime, QTimer, QUrl
    from PySide6.QtGui import QColor, QGuiApplication
    from PySide6.QtQuick import QQuickView

    lang = language()
    QLocale.setDefault(QLocale(i18n.QT_LOCALE.get(lang, lang)))      # Qt.locale(): day names and the date
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    failed, keep = 0, []                 # the context objects outlive their views (deleteLater runs at the end)
    for wid in ids:
        w = widgets.get(wid)
        context, tr, trc = _stand_in(w.plugin, lang)
        keep.append(context)
        props = dict(SAMPLES.get(wid, {}))
        if wid == "clock":
            props["now"] = QDateTime(QDate.currentDate(), QTime(10, 8, 0))
        elif wid == "system":
            props["ramDetail"] = trc("memory used of total", "%1 of %2 GB", "12.6", 31)
        elif wid == "weather":
            thursday = QDate(2026, 10, 15)
            props["days"] = [dict(d, name=QLocale().toString(thursday.addDays(i), "ddd"))
                             for i, d in enumerate(props["days"])]
            props["windUnit"] = trc("wind speed unit", "km/h")
        view = QQuickView()
        view.rootContext().setContextObject(context)
        view.setColor(QColor(0, 0, 0, 0))
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        view.resize(w.size[0] * SCALE, w.size[1] * SCALE)
        view.setInitialProperties(props)
        view.setSource(QUrl.fromLocalFile(str(face(wid))))
        if view.status() != QQuickView.Status.Ready:
            for e in view.errors():
                print(f"{wid}: {e.toString()}", file=sys.stderr)
            failed += 1
            continue
        view.show()
        loop = QEventLoop()
        QTimer.singleShot(400, loop.quit)                 # let Canvas items paint and Behaviors settle
        loop.exec()
        for old in out.glob(f"{wid}-*.png"):
            old.unlink()                                  # our own cache files
        view.grabWindow().save(str(out / f"{wid}-{_digest(wid)}.png"))
        view.close()
        view.deleteLater()
    app.processEvents()
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(render(Path(sys.argv[1]), sys.argv[2:] or [w.id for w in widgets.WIDGETS]))
