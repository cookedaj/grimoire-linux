# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings → Printers: your CUPS printers and print queue (printers.py does the work, off the UI thread).

Adding a printer and picking drivers is KDE's printer settings' job (print-manager); this panel opens it. Names from
CUPS and job titles go into plain-text labels only. The list refreshes every few seconds while it's on screen and
is only rebuilt when something changed, so keyboard focus stays put.
"""
import shutil

from PySide6.QtCore import QDateTime, QLocale, QProcess, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget

from grimoire import NAME, i18n, printers
from grimoire.fsutil import human
from grimoire.i18n import tr
from grimoire.settingsview import Row, _button, _label, run

POLL_MS = 4000
LAUNCH = QProcess.startDetached          # tests swap this; never opens KDE's settings there
KDE_SETTINGS = (["kcmshell6", "kcm_printer_manager"], ["systemsettings", "kcm_printer_manager"],
                ["system-config-printer"])


def open_kde(cmds=KDE_SETTINGS) -> bool:
    """The first of KDE's printer settings (or system-config-printer) that exists, detached."""
    for cmd in cmds:
        if shutil.which(cmd[0]) and _start(cmd):
            return True
    return False


def _start(cmd) -> bool:
    ok = LAUNCH(cmd[0], cmd[1:])
    return bool(ok[0] if isinstance(ok, tuple) else ok)


def _state(p: printers.Printer) -> str:
    if p.paused:
        bits = [tr("grimoire.printersview", "Paused")]
    elif p.state == printers.PRINTING:
        bits = [tr("grimoire.printersview", "Printing")]
    else:
        bits = [tr("grimoire.printersview", "Ready")]
    bits += [tr("grimoire.printers", r) for r in printers.reasons(p)]
    return " · ".join(bits)


def _badge(text, solid=False):
    b = QLabel(text)
    b.setObjectName("BadgeSolid" if solid else "Badge")
    return b


class PrinterRow(Row):
    def __init__(self, panel, p: printers.Printer):
        self.panel, self.p = panel, p
        sub = [i18n.isolate(p.model)] if p.model else []
        if p.location:
            sub.append(i18n.isolate(p.location))
        state = _state(p)
        sub.append(state)
        if p.message and p.message.lower() not in ("none", "ready to print.", "paused", state.lower()):
            sub.append(i18n.isolate(p.message))
        self.default = _button(tr("grimoire.printersview", "Set as default"), self._default,
                               tip=tr("grimoire.printersview", "Apps pick this printer first"))
        self.default.setVisible(not p.default)
        self.pause = _button(tr("grimoire.printersview", "Resume") if p.paused
                             else tr("grimoire.printersview", "Pause"), self._pause,
                             tip=tr("grimoire.printersview", "A paused printer keeps its jobs waiting"))
        self.test = _button(tr("grimoire.printersview", "Test page"), self._test)
        self.test.setEnabled(not p.paused)
        self.more = QPushButton(tr("grimoire.printersview", "More"))
        self.more.setCursor(Qt.CursorShape.PointingHandCursor)
        menu = QMenu(self.more)
        menu.addAction(tr("grimoire.printersview", "Options in KDE…"), self._options)
        menu.addSeparator()
        menu.addAction(tr("grimoire.printersview", "Remove printer…"), self._remove)
        self.more.setMenu(menu)
        super().__init__(p.label, " · ".join(sub), [self.default, self.pause, self.test, self.more])
        self.title.setToolTip(p.name)
        if p.default:                              # the badge sits right after the name
            head = QHBoxLayout()
            head.setSpacing(8)
            text = self.layout().itemAt(0).layout()
            text.removeWidget(self.title)
            head.addWidget(self.title)
            head.addWidget(_badge(tr("grimoire.printersview", "DEFAULT"), True))
            head.addStretch(1)
            text.insertLayout(0, head)
        self.buttons = [self.default, self.pause, self.test, self.more]

    def _busy(self, on=True):
        for b in self.buttons:
            b.setEnabled(not on and (b is not self.test or not self.p.paused))

    def _do(self, fn, done_text):
        self._busy()
        name = self.p.label

        def finish(ok, value):
            if ok:
                self.panel.say(done_text(value).format(name=i18n.isolate(name)) if callable(done_text)
                               else done_text.format(name=i18n.isolate(name)))
            else:
                self.panel.say(value)
            try:
                self._busy(False)
            except RuntimeError:               # a refresh rebuilt the list meanwhile
                pass
            self.panel.reload()
        run(fn, finish)

    def _default(self):
        name = self.p.name
        self._do(lambda: printers.set_default(name), lambda where: (
            tr("grimoire.printersview", "{name} is now the default printer.") if where == "system" else
            tr("grimoire.printersview", "{name} is now your default printer (just for you: CUPS keeps another "
               "one for everyone).")))

    def _pause(self):
        name = self.p.name
        if self.p.paused:
            self._do(lambda: printers.resume(name), tr("grimoire.printersview", "{name} is printing again."))
        else:
            self._do(lambda: printers.pause(name), tr("grimoire.printersview", "{name} is paused."))

    def _test(self):
        name = self.p.name
        self._do(lambda: printers.test_page(name), tr("grimoire.printersview", "Test page sent to {name}."))

    def _options(self):
        if not (shutil.which("configure-printer") and _start(["configure-printer", self.p.name])) and not open_kde():
            self.panel.say(tr("grimoire.printersview", "KDE's printer settings aren't installed (package "
                              "print-manager)."))

    def _remove(self):
        name = self.p.label
        text = tr("grimoire.printersview", "Remove {name}? Its waiting jobs are cancelled.").format(
            name=i18n.isolate(name))
        if self.p.network:
            text += "\n\n" + tr("grimoire.printersview", "It was found on the network, so it may come back by itself "
                                "while it's switched on.")
        box = QMessageBox(QMessageBox.Icon.NoIcon, NAME, text, parent=self)     # no colored icon: B&W
        box.setTextFormat(Qt.TextFormat.PlainText)                                # printer names are CUPS's
        yes = box.addButton(tr("grimoire.printersview", "Remove"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is yes:
            pname = self.p.name
            self._do(lambda: printers.remove(pname), tr("grimoire.printersview", "{name} removed."))


class JobRow(Row):
    def __init__(self, panel, job: printers.Job, names: dict):
        self.panel, self.job = panel, job
        bits = [i18n.isolate(names.get(job.printer, job.printer))]
        if job.size:
            bits.append(i18n.ltr(human(job.size)))
        if job.created:
            bits.append(QLocale().toString(QDateTime.fromSecsSinceEpoch(job.created), QLocale.FormatType.ShortFormat))
        bits.append(tr("grimoire.printers", printers.JOB_STATES.get(job.state, printers.JOB_STATES[3])))
        self.cancel = _button(tr("grimoire.printersview", "Cancel"), self._cancel,
                              tip=tr("grimoire.printersview", "Stop this job and drop it from the queue"))
        super().__init__(job.name or tr("grimoire.printersview", "Untitled job"), " · ".join(bits), [self.cancel])

    def _cancel(self):
        self.cancel.setEnabled(False)
        jid = self.job.id

        def done(ok, value):
            self.panel.say(tr("grimoire.printersview", "Job cancelled.") if ok else value)
            self.panel.reload()
        run(lambda: printers.cancel(jid), done)


class PrintersPanel(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.printersview", "Printers on this PC and what's waiting to print. Adding a "
                                "printer opens KDE's printer settings, which find drivers for you."), "Muted"))
        top = QHBoxLayout()
        top.setSpacing(8)
        self.add = _button(tr("grimoire.printersview", "Add printer…"), self._add, "Primary")
        top.addWidget(self.add)
        top.addWidget(_button(tr("grimoire.printersview", "Refresh"), self.reload))
        top.addStretch(1)
        lay.addLayout(top)
        self.status = _label("", "Status")
        self.status.hide()
        lay.addWidget(self.status)
        self.missing = _label(tr("grimoire.printersview", "Printing needs python3-cups. Install it with:"), "Muted")
        self.cmd = _label(printers.INSTALL, "Mono", wrap=False)
        self.cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.missing)
        lay.addWidget(self.cmd)
        lay.addSpacing(6)
        lay.addWidget(_label(tr("grimoire.printersview", "PRINTERS"), "Section"))
        self.note = _label(tr("grimoire.printersview", "Reading printers…"), "Muted")
        lay.addWidget(self.note)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(8)
        lay.addLayout(self.rows)
        lay.addSpacing(10)
        lay.addWidget(_label(tr("grimoire.printersview", "QUEUE"), "Section"))
        self.empty = _label(tr("grimoire.printersview", "Nothing waiting to print."), "Muted")
        lay.addWidget(self.empty)
        self.jobs = QVBoxLayout()
        self.jobs.setSpacing(8)
        lay.addLayout(self.jobs)
        lay.addStretch(1)
        self.sig = None
        self.loading = False
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.reload)
        ok = printers.available()
        self.missing.setVisible(not ok)
        self.cmd.setVisible(not ok)

    def showEvent(self, e):
        super().showEvent(e)
        if printers.available():
            self.reload()
            self.timer.start()
        else:
            self.note.setText(tr("grimoire.printersview", "No printing support yet."))

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def say(self, text):
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _add(self):
        if not open_kde():
            self.say(tr("grimoire.printersview", "KDE's printer settings aren't installed (package print-manager)."))

    def reload(self):
        if self.loading or not printers.available():
            return
        self.loading = True
        run(printers.listing, self._show)

    @staticmethod
    def _clear(lay):
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _show(self, ok, value):
        self.loading = False
        if not ok:
            self.sig = None
            self._clear(self.rows)
            self._clear(self.jobs)
            self.note.setText(value)
            self.note.show()
            self.empty.hide()
            return
        ps, jobs = value
        sig = (repr(ps), repr(jobs))
        if sig == self.sig:
            return
        self.sig = sig
        self._clear(self.rows)
        self._clear(self.jobs)
        self.note.setText(tr("grimoire.printersview", "No printers yet. Add one, or switch on a network printer: "
                             "most show up by themselves."))
        self.note.setVisible(not ps)
        for p in ps:
            self.rows.addWidget(PrinterRow(self, p))
        names = {p.name: p.label for p in ps}
        self.empty.setVisible(not jobs)
        for j in jobs:
            self.jobs.addWidget(JobRow(self, j, names))
