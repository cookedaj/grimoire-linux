# SPDX-License-Identifier: GPL-3.0-or-later
"""MuraL → Looks tab: saved snapshots of the whole desktop look, restored in one click.
The work is in looks.py; this is the list on the left and the details + buttons on the right.
"""
from datetime import datetime

from PySide6.QtCore import QDateTime, QLocale, QObject, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.mural import looks
from grimoire.spells.mural.screens import THUMB, placeholder

ID_ROLE = Qt.ItemDataRole.UserRole


class _Signals(QObject):
    saved = Signal(object)        # the new look, or an error message
    progress = Signal(str)        # part being applied
    restored = Signal(object)     # [(key, ok, message)] or an error message


def when(iso: str) -> str:
    """The save time in the user's language."""
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return QLocale().toString(QDateTime(t.date(), t.time()), QLocale.FormatType.ShortFormat)


def part(key: str) -> str:
    """A part of a look (Desktop, Lock screen…) in the user's language."""
    return tr("grimoire.spells.mural.looks", looks.LABELS[key])


class LooksTab(QWidget):
    restored = Signal()           # the page rebuilds the other tabs so they show what's in use now

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self._sig = _Signals()
        self._working = False         # a save/restore is running: the buttons stay off until it's done
        self._include: set[str] = set()   # the password parts the running restore includes
        self._sig.saved.connect(self._on_saved)
        self._sig.progress.connect(
            lambda key: self.status.setText(tr("grimoire.spells.mural.lookstab", "Applying {part}…")
                                            .format(part=part(key).lower())))
        self._sig.restored.connect(self._on_restored)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(36, 8, 24, 24)
        lv.setSpacing(14)
        head = QHBoxLayout()
        sub = QLabel(tr("grimoire.spells.mural.lookstab", "Save everything MuraL has applied (wallpaper, taskbar, "
                        "colors, icons, fonts…) as a look, and put it all back in one click."))
        sub.setObjectName("Subtitle")
        sub.setWordWrap(True)
        head.addWidget(sub, 1)
        self.save_btn = QPushButton(tr("grimoire.spells.mural.lookstab", "Save current look"))
        self.save_btn.clicked.connect(self._save)
        head.addWidget(self.save_btn)
        lv.addLayout(head)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 24, THUMB.height() + 58))
        self.list.setSpacing(8)
        self.list.currentItemChanged.connect(lambda *_: self._show_details())
        self.list.itemDoubleClicked.connect(lambda _: self._rename())
        lv.addWidget(self.list, 1)
        self.empty = QLabel(tr("grimoire.spells.mural.lookstab", "No looks saved yet. Set things up in the other tabs, "
                                                           "then click “Save current look”."))
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        lv.addWidget(self.empty)
        root.addWidget(left, 1)

        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(300)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(24, 24, 24, 24)
        pl.setSpacing(10)
        self.name = QLabel()
        self.name.setObjectName("Section")
        self.contents = QLabel()
        self.contents.setObjectName("Muted")
        self.contents.setWordWrap(True)
        pl.addWidget(self.name)
        pl.addWidget(self.contents)
        pl.addSpacing(6)
        self.root_boxes: dict[str, QCheckBox] = {}
        for key in sorted(looks.ROOT, key=looks.ORDER.index):
            box = QCheckBox(tr("grimoire.spells.mural.lookstab", "Also restore {part}\n(asks for your password)")
                            .format(part=part(key).lower()))
            self.root_boxes[key] = box
            pl.addWidget(box)
        pl.addStretch(1)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        pl.addWidget(self.status)
        row = QHBoxLayout()
        self.rename_btn = QPushButton(tr("grimoire.spells.mural.lookstab", "Rename"))
        self.rename_btn.clicked.connect(self._rename)
        self.delete_btn = QPushButton(tr("grimoire.spells.mural.lookstab", "Delete"))
        self.delete_btn.clicked.connect(self._delete)
        row.addWidget(self.rename_btn)
        row.addWidget(self.delete_btn)
        pl.addLayout(row)
        self.restore_btn = QPushButton(tr("grimoire.spells.mural.lookstab", "Restore look"))
        self.restore_btn.setObjectName("Primary")
        self.restore_btn.setMinimumHeight(40)
        self.restore_btn.clicked.connect(self._restore)
        pl.addWidget(self.restore_btn)
        root.addWidget(panel)

        self.reload()

    # ---- list
    def reload(self, select: str | None = None):
        keep = select or self.current_id()
        self.list.blockSignals(True)
        self.list.clear()
        active = (looks.active() or {}).get("id")
        for look in looks.all_looks():
            img = QImage(str(looks.thumb_path(look["id"])))
            pm = placeholder() if img.isNull() else QPixmap.fromImage(
                img.scaled(THUMB, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation))
            icon = QIcon(pm)
            icon.addPixmap(pm, QIcon.Mode.Selected)          # no selection tint on the thumbnail
            name = (tr("grimoire.spells.mural.screens", "{name}  ·  in use").format(name=look["name"])
                    if look["id"] == active else look["name"])
            item = QListWidgetItem(icon, f"{name}\n{when(look.get('created', ''))}")
            item.setData(ID_ROLE, look["id"])
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.list.addItem(item)
            if look["id"] == keep:
                self.list.setCurrentItem(item)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.empty.setVisible(self.list.count() == 0)
        self.list.setVisible(self.list.count() > 0)
        self._show_details()

    def current_id(self) -> str | None:
        item = self.list.currentItem()
        return item.data(ID_ROLE) if item else None

    def _show_details(self):
        look = looks.get(self.current_id()) if self.current_id() else None
        for w in (self.rename_btn, self.delete_btn, self.restore_btn):
            w.setEnabled(look is not None and not self._working)
        if look is None:
            self.name.setText(tr("grimoire.spells.mural.lookstab", "NO LOOK SELECTED"))
            self.contents.setText("")
            for box in self.root_boxes.values():
                box.setVisible(False)
            return
        self.name.setText(look["name"].upper())
        lines = []
        for key in looks.parts(look):
            if key == "desktop":
                n = len(look["desktop"]["items"])
                lines.append(tr("grimoire.spells.mural.lookstab", "Desktop · %n wallpaper(s)", n=n))
            else:
                lines.append(f"{part(key)} · {look['tabs'][key].get('label', '')}")
        nothing = tr("grimoire.spells.mural.lookstab", "Nothing was applied with MuraL when this was saved.")
        self.contents.setText("\n".join(lines) or nothing)
        for key, box in self.root_boxes.items():
            box.setVisible(key in look.get("tabs", {}))

    # ---- actions
    def _busy(self, busy: bool, text: str = ""):
        self._working = busy
        for w in (self.save_btn, self.rename_btn, self.delete_btn, self.restore_btn):
            w.setEnabled(not busy)
        if not busy:
            self._show_details()                 # Rename/Delete/Restore only with a look selected
        if text:
            self.status.setText(text)

    def _save(self):
        name, ok = QInputDialog.getText(self, tr("grimoire.spells.mural.lookstab", "Save current look"),
                                        tr("grimoire.spells.mural.lookstab", "Name"),
                                        text=looks.default_name())
        if not ok:
            return
        sig = self._sig
        self._busy(True, tr("grimoire.spells.mural.lookstab", "Saving…"))

        def work():
            try:
                return looks.save_current(name)
            except Exception as e:
                return tr("grimoire.spells.mural.lookstab", "Couldn't save: {error}").format(error=e)

        POOL.start(Job(work, lambda r: sig.saved.emit(r)))

    def _on_saved(self, result):
        self._busy(False)
        if isinstance(result, str):
            self.status.setText(result)
            return
        n = len(looks.parts(result))
        self.status.setText(tr("grimoire.spells.mural.lookstab", "Saved ✓  %n part(s) of your look.", n=n) if n else
                            tr("grimoire.spells.mural.lookstab", "Saved, but nothing is applied with MuraL yet, "
                               "so there's nothing to restore."))
        self.reload(result["id"])

    def _rename(self):
        look = looks.get(self.current_id() or "")
        if look is None:
            return
        name, ok = QInputDialog.getText(self, tr("grimoire.spells.mural.lookstab", "Rename look"),
                                        tr("grimoire.spells.mural.lookstab", "Name"), text=look["name"])
        if ok and name.strip():
            looks.rename(look["id"], name)
            self.reload()

    def _delete(self):
        look = looks.get(self.current_id() or "")
        if look is None:
            return
        question = tr("grimoire.spells.mural.lookstab", "Forget the look “{name}”?\n\nThis only removes the saved "
                      "snapshot; your wallpapers and themes stay.").format(name=look["name"])
        title = tr("grimoire.spells.mural.lookstab", "Delete look?")
        if QMessageBox.question(self, title, question) != QMessageBox.StandardButton.Yes:
            return
        looks.delete(look["id"])
        self.status.setText(tr("grimoire.spells.mural.lookstab", "Deleted “{name}”.").format(name=look["name"]))
        self.reload()

    def _restore(self):
        look_id = self.current_id()
        if not look_id:
            return
        include = {k for k, box in self.root_boxes.items() if box.isVisible() and box.isChecked()}
        sig = self._sig
        self._include = include
        busy = (tr("grimoire.spells.mural.lookstab", "Restoring…  Enter your password when asked.") if include
                else tr("grimoire.spells.mural.lookstab", "Restoring…"))
        self._busy(True, busy)

        def work():
            try:
                return looks.restore(look_id, include, progress=sig.progress.emit)
            except Exception as e:
                return tr("grimoire.spells.mural.lookstab", "Couldn't restore: {error}").format(error=e)

        POOL.start(Job(work, lambda r: sig.restored.emit(r)))

    def _on_restored(self, results):
        self._busy(False)
        if isinstance(results, str):
            self.status.setText(results)
            return
        failed = [r for r in results if not r[1]]
        skipped = {k for k in looks.ROOT if k not in self._include}    # reported, not failed
        lines = [("·  " if ok else "✗  ") + f"{part(key)}: {msg}" for key, ok, msg in results
                 if not ok or key in skipped]
        head = (tr("grimoire.spells.mural.lookstab", "Look restored ✓") if not failed else
                tr("grimoire.spells.mural.lookstab", "Restored, but %n part(s) didn't apply:", n=len(failed)))
        self.status.setText("\n".join([head, *lines]))
        self.reload()
        self.restored.emit()
