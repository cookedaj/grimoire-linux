# SPDX-License-Identifier: GPL-3.0-or-later
"""LaunchL's page in Grimoire: install or update the widget, swap it in for Kickoff and back."""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.launchl import appedit, panel

NAMES = {"org.kde.plasma.kickoff": "Kickoff",
         "org.kde.plasma.kicker": tr_noop("grimoire.spells.launchl.page", "Application Menu"),
         "org.kde.plasma.kickerdash": tr_noop("grimoire.spells.launchl.page", "Application Dashboard")}


def _name(plugin: str, fallback: str = "") -> str:
    """A launcher's name as Plasma shows it (Kickoff stays Kickoff)."""
    name = NAMES.get(plugin)
    return tr("grimoire.spells.launchl.page", name) if name else (fallback or plugin)


def _label(text="", name="", wrap=True) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def status() -> str:
    return panel.status()


class _Signals(QObject):
    done = Signal(object)          # (what, error text or "", result)


class LaunchLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.sig = _Signals()
        self.sig.done.connect(self._finished)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(56, 48, 56, 40)
        lay.setSpacing(6)
        # aligned by the layout, which mirrors: a full-width label aligns Latin text left even right to left
        lay.addWidget(_label("LaunchL", "PageHeading", wrap=False), 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(_label(tr("grimoire.spells.launchl.page",
                                "Your app launcher in the panel, in black and white: favorites, every app by "
                                "category, places and recent files, search that also finds files, does sums and unit "
                                "conversions and runs Grimoire's spells, and the leave buttons. Meta opens it once "
                                "it's in Kickoff's place."), "Muted"))
        lay.addSpacing(24)

        lay.addWidget(_label(tr("grimoire.spells.launchl.page", "WIDGET"), "Section"))
        self.state = _label("", "")
        lay.addWidget(self.state)
        row = QHBoxLayout()
        self.install_btn = QPushButton()
        self.install_btn.clicked.connect(self._install)
        row.addWidget(self.install_btn)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(24)

        lay.addWidget(_label(tr("grimoire.spells.launchl.page", "PANEL"), "Section"))
        self.where = _label("", "Muted")
        lay.addWidget(self.where)
        row = QHBoxLayout()
        self.replace_btn = QPushButton(tr("grimoire.spells.launchl.page", "Replace launcher"))
        self.replace_btn.setObjectName("Primary")
        self.replace_btn.clicked.connect(self._replace)
        self.restore_btn = QPushButton(tr("grimoire.spells.launchl.page", "Restore Kickoff"))
        self.restore_btn.clicked.connect(self._restore)
        row.addWidget(self.replace_btn)
        row.addWidget(self.restore_btn)
        row.addStretch(1)
        lay.addLayout(row)
        self.note = _label("", "Muted")
        lay.addWidget(self.note)
        lay.addSpacing(24)

        # apps changed with LaunchL's right-click "Edit…" / "Hide from Menu" (hidden ones are only reachable here)
        lay.addWidget(_label(tr("grimoire.spells.launchl.page", "APPS YOU CHANGED"), "Section"))
        self.edits_note = _label(tr("grimoire.spells.launchl.page",
                                    "Right-click an app in LaunchL to edit its name, icon or command, or to hide "
                                    "it. Changes are your own copies; system files are never touched."), "Muted")
        lay.addWidget(self.edits_note)
        self.edits = QVBoxLayout()
        self.edits.setSpacing(4)
        lay.addLayout(self.edits)
        self.edits_status = _label("", "Muted")
        lay.addWidget(self.edits_status)
        lay.addStretch(1)
        self.refresh()

    # ---- state ----------------------------------------------------------------------------------------------------

    def refresh(self):
        self.state.setText(tr("grimoire.spells.launchl.page", "Checking…"))
        self._busy(True)
        POOL.start(Job(self._read, lambda r: self.sig.done.emit(("read", "", r))))

    @staticmethod
    def _read() -> dict:
        info = {"installed": panel.is_installed(), "update": panel.needs_update(), "record": panel.load_state(),
                "edited": appedit.edited()}
        try:
            info["panels"] = panel.scan()
        except (RuntimeError, ValueError) as err:
            info["panels"], info["error"] = [], str(err)
        return info

    def _show(self, info: dict):
        installed, panels = info["installed"], info["panels"]
        here = panel.in_panel(panels) if panels else False
        record = info["record"].get("replaced")
        if not installed:
            bits = [tr("grimoire.spells.launchl.page", "Not installed")]
        else:
            bits = [tr("grimoire.spells.launchl.page", "In your panel") if here
                    else tr("grimoire.spells.launchl.page", "Installed, not in your panel")]
            if info["update"]:
                bits.append(tr("grimoire.spells.launchl.page", "an update is ready"))
        self.state.setText(" · ".join(bits))
        self.install_btn.setText(tr("grimoire.spells.launchl.page", "Install widget") if not installed else
                                 tr("grimoire.spells.launchl.page", "Update widget") if info["update"]
                                 else tr("grimoire.spells.launchl.page", "Reinstall widget"))
        found = panel.find_launcher(panels) if panels else None
        if "error" in info:
            self.where.setText(tr("grimoire.spells.launchl.page", "Plasma isn't answering ({error}), so the panel "
                                  "can't be read right now.").format(error=info["error"]))
        elif record:
            self.where.setText(tr("grimoire.spells.launchl.page",
                                  "LaunchL took the place of {launcher} (panel {panel}, position {position}) on "
                                  "{date}. Restore puts it back exactly there, with its settings.").format(
                launcher=_name(record["type"]), panel=record["panel"], position=record["position"] + 1,
                date=record["recorded"][:10]))
        elif here:
            self.where.setText(tr("grimoire.spells.launchl.page",
                                  "LaunchL is in your panel (added by hand). Restore needs a recorded replacement, "
                                  "so use Edit Mode to swap launchers."))
        elif found:
            p, w, pos = found
            self.where.setText(tr("grimoire.spells.launchl.page",
                                  "{launcher} is in panel {panel} at position {position}. Replace puts LaunchL in "
                                  "that exact spot, with your favorites in their order and its shortcut, and records "
                                  "everything so Restore can undo it.").format(
                launcher=_name(w["type"]), panel=p["id"], position=pos + 1))
        else:
            self.where.setText(tr("grimoire.spells.launchl.page",
                                  "No Kickoff, Application Menu or Dashboard in your panels. Add LaunchL from the "
                                  "panel's Add Widgets (search \"LaunchL\")."))
        self.replace_btn.setEnabled(installed and bool(found) and not here)
        self.restore_btn.setEnabled(bool(record))
        self.restore_btn.setText(tr("grimoire.spells.launchl.page", "Restore {launcher}").format(
            launcher=_name(record["type"], "Kickoff")) if record else tr("grimoire.spells.launchl.page",
                                                                          "Restore Kickoff"))
        self.install_btn.setEnabled(True)
        self._show_edits(info.get("edited", []))

    def _show_edits(self, apps: list):
        while self.edits.count():
            item = self.edits.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not apps:
            self.edits.addWidget(_label(tr("grimoire.spells.launchl.page", "No changed apps."), "Muted"))
            return
        for app in apps:
            line = QWidget()
            row = QHBoxLayout(line)
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(8)
            name = QLabel(isolate(app.name or app.id))
            name.setTextFormat(Qt.TextFormat.PlainText)
            row.addWidget(name)
            state = QLabel(tr("grimoire.spells.launchl.page", "hidden") if app.hidden
                           else tr("grimoire.spells.launchl.page", "edited"))
            state.setObjectName("Muted")
            row.addWidget(state)
            row.addStretch(1)
            if app.hidden:
                show = QPushButton(tr("grimoire.spells.launchl.page", "Show in menu"))
                show.clicked.connect(lambda _=False, a=app.id: self._start("unhide", lambda: self._apply(
                    appedit.hide, a, False)))
                row.addWidget(show)
            edit = QPushButton(tr("grimoire.spells.launchl.page", "Edit…"))
            edit.clicked.connect(lambda _=False, a=app.id: self._edit(a))
            row.addWidget(edit)                       # Edit and Reset line up from row to row
            reset = QPushButton(tr("grimoire.spells.launchl.page", "Reset"))
            reset.setToolTip(tr("grimoire.spells.launchl.page", "Back to the default; your copy goes to the Trash"))
            reset.clicked.connect(lambda _=False, a=app.id: self._start("reset", lambda: self._apply(
                appedit.reset, a)))
            row.addWidget(reset)
            line.setToolTip(ltr(app.id))
            self.edits.addWidget(line)

    @staticmethod
    def _apply(fn, *args):
        fn(*args)
        appedit.rebuild()

    def _edit(self, app_id: str):
        from grimoire.spells.launchl.editor import EditDialog
        dlg = EditDialog(app_id, self)
        dlg.finished.connect(lambda _r: self.refresh())
        dlg.open()

    def _busy(self, on: bool):
        for b in (self.install_btn, self.replace_btn, self.restore_btn):
            b.setEnabled(not on)

    # ---- actions --------------------------------------------------------------------------------------------------

    def _start(self, what: str, fn):
        self._busy(True)
        self._note_for(what).setText(tr("grimoire.spells.launchl.page", "Working…"))

        def guarded():
            try:
                return "", fn()
            except Exception as err:      # anything uncaught would leave the buttons off and "Working…" for good
                return str(err) or type(err).__name__, None
        POOL.start(Job(guarded, lambda r: self.sig.done.emit((what, r[0], r[1]))))

    def _note_for(self, what: str) -> QLabel:
        return self.edits_status if what in ("unhide", "reset") else self.note

    def _install(self):
        self._start("install", panel.install)

    def _replace(self):
        if QMessageBox.question(
                self, tr("grimoire.spells.launchl.page", "Replace launcher"),
                tr("grimoire.spells.launchl.page",
                   "LaunchL takes Kickoff's place in your panel:\n\n"
                   "1. Grimoire records where Kickoff is, its settings and its shortcut.\n"
                   "2. LaunchL is added in the same spot, with your favorites in the same order.\n"
                   "3. Kickoff is removed.\n\nRestore Kickoff puts it back exactly as it was.")) \
                != QMessageBox.StandardButton.Yes:
            return
        self._start("replace", panel.replace)

    def _restore(self):
        if QMessageBox.question(self, tr("grimoire.spells.launchl.page", "Restore Kickoff"),
                                tr("grimoire.spells.launchl.page", "Put the old launcher back where LaunchL is, "
                                   "with its settings, and remove LaunchL from the panel?")) \
                != QMessageBox.StandardButton.Yes:
            return
        self._start("restore", panel.restore)

    def _finished(self, payload):
        what, error, result = payload
        if what == "read":
            self._show(result)
            return
        if error:
            failed = {"install": tr("grimoire.spells.launchl.page", "Couldn't install the widget: {error}"),
                      "unhide": tr("grimoire.spells.launchl.page", "Couldn't show the app again: {error}"),
                      "reset": tr("grimoire.spells.launchl.page", "Couldn't reset the app: {error}"),
                      "replace": tr("grimoire.spells.launchl.page", "Couldn't replace the launcher: {error}"),
                      "restore": tr("grimoire.spells.launchl.page", "Couldn't restore the launcher: {error}")}
            self._note_for(what).setText(failed.get(what, "{error}").format(error=error))
        elif what == "install":
            self.note.setText(tr("grimoire.spells.launchl.page",
                                 "Widget installed. Plasma picks up a new version when it next restarts."))
        elif what == "replace":
            self.note.setText(tr("grimoire.spells.launchl.page", "LaunchL is in your panel. {next}").format(
                next=result.get("check") or tr("grimoire.spells.launchl.page", "Press Meta to open it.")))
        elif what == "unhide":
            self.edits_status.setText(tr("grimoire.spells.launchl.page", "The app is back in the menu."))
        elif what == "reset":
            self.edits_status.setText(tr("grimoire.spells.launchl.page",
                                         "The app is back to its default. Your copy is in the Trash."))
        elif what == "restore":
            self.note.setText(tr("grimoire.spells.launchl.page", "{launcher} is back in your panel.").format(
                launcher=_name(result["type"], "Kickoff")))
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
