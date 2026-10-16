# SPDX-License-Identifier: GPL-3.0-or-later
"""The install queue: tasks wait here and run in batches on a worker thread, so the page never freezes.

When the queue is idle and a task arrives, everything waiting goes out as one batch (apply.run_batch: one helper
call, so one password prompt, then your own Flatpaks); tasks added while a batch runs wait for the next one. A
waiting task can be cancelled; a running one can't (apt and flatpak mustn't be stopped halfway).
"""
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.i18n import tr
from grimoire.spells.storel import apply
from grimoire.spells.storel.apply import CANCELLED, DONE, FAILED, RUNNING, WAITING, Task

QSS = """
QPlainTextEdit#Log { font-family: "IBM Plex Mono"; font-size: 11px; color: #bdbdbd; background: #080808;
                     border: 1px solid #1c1c1c; border-radius: 8px; padding: 6px; }
QProgressBar { background: #121212; border: 1px solid #262626; border-radius: 4px; max-height: 6px; }
QProgressBar::chunk { background: #f2f2f2; border-radius: 3px; }
"""


class Queue(QObject):
    changed = Signal(object)            # a Task (state, progress or message changed), or None for the whole list
    line = Signal(str)
    finished = Signal(object)           # the batch's tasks

    def __init__(self):
        super().__init__()
        self.tasks: list[Task] = []
        self.busy = False
        self.finished.connect(self._after)

    def add(self, task: Task):
        self.tasks.append(task)
        self.changed.emit(None)
        self._kick()

    def pending(self, key: str) -> Task | None:
        """The waiting or running task for this app, if any."""
        return next((t for t in self.tasks if t.key == key and t.state in (WAITING, RUNNING)), None)

    def active(self) -> int:
        return sum(t.state in (WAITING, RUNNING) for t in self.tasks)

    def cancel(self, task: Task):
        if task.state == WAITING and not self._in_batch(task):
            task.state, task.message = CANCELLED, ""
            self.changed.emit(None)

    def clear_finished(self):
        self.tasks = [t for t in self.tasks if t.state in (WAITING, RUNNING)]
        self.changed.emit(None)

    def _in_batch(self, task: Task) -> bool:
        return task in getattr(self, "_batch", [])

    def _kick(self):
        if self.busy:
            return
        batch = [t for t in self.tasks if t.state == WAITING]
        if not batch:
            return
        self.busy = True
        self._batch = batch

        def work():
            try:
                apply.run_batch(batch, self.line.emit, self.changed.emit)
            except Exception as e:                      # shown on the tasks, not a crash
                for t in batch:
                    if t.state in (WAITING, RUNNING):
                        t.state, t.message = FAILED, str(e)
            self.finished.emit(batch)
        threading.Thread(target=work, daemon=True).start()

    def _after(self, batch):
        self.busy = False
        self._batch = []
        self.changed.emit(None)
        self._kick()


def state_text(task: Task) -> str:
    install = task.action == "install"
    return {WAITING: tr("grimoire.spells.storel.queueview", "Waiting"),
            RUNNING: (tr("grimoire.spells.storel.queueview", "Installing…") if install else
                      tr("grimoire.spells.storel.queueview", "Removing…")),
            DONE: (tr("grimoire.spells.storel.queueview", "Installed") if install else
                   tr("grimoire.spells.storel.queueview", "Removed")),
            FAILED: tr("grimoire.spells.storel.queueview", "Failed"),
            CANCELLED: tr("grimoire.spells.storel.queueview", "Cancelled")}[task.state]


class TaskRow(QFrame):
    def __init__(self, queue: Queue, task: Task):
        super().__init__()
        self.setObjectName("Row")
        self.task = task
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.title = QLabel()
        self.title.setObjectName("RowTitle")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        col.addWidget(self.title)
        self.sub = QLabel()
        self.sub.setObjectName("Muted")
        self.sub.setTextFormat(Qt.TextFormat.PlainText)
        self.sub.setWordWrap(True)
        col.addWidget(self.sub)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        col.addWidget(self.bar)
        lay.addLayout(col, 1)
        self.cancel = QPushButton(tr("grimoire.spells.storel.queueview", "Cancel"))
        self.cancel.clicked.connect(lambda: queue.cancel(task))
        lay.addWidget(self.cancel, 0, Qt.AlignmentFlag.AlignTop)
        self.queue = queue
        self.update_()

    def update_(self):
        t = self.task
        verb = (tr("grimoire.spells.storel.queueview", "Install {name}") if t.action == "install" else
                tr("grimoire.spells.storel.queueview", "Remove {name}")).format(name=i18n.isolate(t.title))
        self.title.setText(verb)
        bits = [state_text(t)]
        if t.message:
            bits.append(t.message)
        self.sub.setText("   ·   ".join(bits))
        self.bar.setVisible(t.state == RUNNING)
        if t.progress < 0:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(t.progress))
        self.cancel.setVisible(t.state == WAITING and not self.queue._in_batch(t))


class QueuePanel(QWidget):
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        self.setStyleSheet(QSS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        head = QHBoxLayout()
        self.state = QLabel()
        self.state.setObjectName("Muted")
        self.state.setWordWrap(True)
        head.addWidget(self.state, 1)
        self.clear = QPushButton(tr("grimoire.spells.storel.queueview", "Clear finished"))
        self.clear.clicked.connect(queue.clear_finished)
        head.addWidget(self.clear)
        lay.addLayout(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        self.rows_lay = QVBoxLayout(inner)
        self.rows_lay.setContentsMargins(0, 0, 8, 0)
        self.rows_lay.setSpacing(8)
        self.rows_lay.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 3)
        logh = QHBoxLayout()
        logh.addWidget(QLabel(tr("grimoire.spells.storel.queueview", "Log")), 1)
        copy = QPushButton(tr("grimoire.spells.storel.queueview", "Copy log"))
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.log.toPlainText()))
        logh.addWidget(copy)
        lay.addLayout(logh)
        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        self.log.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        lay.addWidget(self.log, 2)
        self.rows: dict[int, TaskRow] = {}
        queue.changed.connect(self._changed)
        queue.line.connect(self.log.appendPlainText)
        self._rebuild()

    def _changed(self, task):
        if task is not None and id(task) in self.rows:
            self.rows[id(task)].update_()
            self._head()
        else:
            self._rebuild()

    def _rebuild(self):
        for row in self.rows.values():
            row.setParent(None)
            row.deleteLater()
        self.rows = {}
        for t in reversed(self.queue.tasks):              # newest on top
            row = TaskRow(self.queue, t)
            self.rows[id(t)] = row
            self.rows_lay.insertWidget(self.rows_lay.count() - 1, row)
        self._head()

    def _head(self):
        n = self.queue.active()
        done = len(self.queue.tasks) - n
        self.state.setText(tr("grimoire.spells.storel.queueview", "%n app(s) waiting or in progress.", n=n) if n else
                           tr("grimoire.spells.storel.queueview", "Nothing in the queue. Install or remove an app and "
                              "it shows here with its progress.") if not self.queue.tasks else
                           tr("grimoire.spells.storel.queueview", "All done."))
        self.clear.setEnabled(done > 0)
