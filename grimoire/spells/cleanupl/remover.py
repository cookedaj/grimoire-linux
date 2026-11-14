# SPDX-License-Identifier: GPL-3.0-or-later
"""Removing apps, shared by CleanupL and UninstallerL, in three steps:

1. plan: `apt-get -s` for the packages (off the UI thread), the Flatpak refs, the files that go to the Trash;
2. confirm: a dialog lists exactly that (every package apt would remove, refusals for anything the desktop or the
   system needs, a tick for removals beyond what you picked) and nothing happens before you press Remove;
3. run: StoreL's engine (one password for all system packages, your own Flatpaks without one), then a leftover
   scan in the style of Revo Uninstaller: settings, caches, autostart entries, menu entries, user services and
   Flatpak data, grouped with sizes; only what you tick goes, and only to the Trash.

Removed packages land on a restore list (engine.remember) so Reinstall can bring them back.
"""

import re
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from grimoire import i18n
from grimoire.fsutil import human, tilde
from grimoire.i18n import tr
from grimoire.spells.cleanupl import engine
from grimoire.spells.cleanupl.engine import Found
from grimoire.spells.storel import apply, sources
from grimoire.spells.storel.apply import Task
from grimoire.spells.storel.preview import QSS, _box, _label


# ---------------------------------------------------------------- planning (worker thread)
def plan(found: list[Found]) -> dict:
    """{"tasks": [Task], "apt": simulation or None, "files": [Path], "error": str}"""
    apt_pkgs = [n for f in found if f.source == "apt" for n in f.names]
    out = {"tasks": [], "apt": None, "files": [], "error": ""}
    if apt_pkgs:
        try:
            out["apt"] = sources.simulate("remove", apt_pkgs)
        except RuntimeError as e:
            out["error"] = str(e)
            return out
        out["tasks"].append(
            Task("remove", "apt", ", ".join(f.title for f in found if f.source == "apt"), "cleanupl", apt_pkgs)
        )
    for f in found:
        if f.source == "flatpak":
            out["tasks"].append(Task("remove", "flatpak", f.title, f.key, list(f.names), scope=f.scope))
        elif f.source == "snap":
            out["tasks"].append(Task("remove", "snap", f.title, f.key, list(f.names)))
        elif f.source in ("appimage", "user"):
            out["files"] += [Path(n) for n in f.names]
    return out


# ---------------------------------------------------------------- the confirm dialog
class ConfirmDialog(QDialog):
    """Everything that will change, before anything does."""

    def __init__(self, parent, found: list[Found], p: dict):
        super().__init__(parent)
        self.setObjectName("Plan")
        self.setStyleSheet(QSS)
        self.setWindowTitle(tr("grimoire.spells.cleanupl.remover", "Uninstall"))
        self.setMinimumWidth(600)
        self.removals: list[str] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)
        lay.addWidget(
            _label(tr("grimoire.spells.cleanupl.remover", "Uninstall %n app(s)?", n=len(found)), "SectionTitle")
        )
        lay.addWidget(_box([f"{f.title}   ({engine.describe_source(f)})" for f in found]))
        blocked, self.allow = False, None
        sim = p.get("apt")
        if sim is not None:
            if sim.get("blocked"):
                blocked = True
                names = ", ".join(n for n, _why in sim["blocked"])
                lay.addWidget(
                    _label(
                        tr(
                            "grimoire.spells.cleanupl.remover",
                            "Refused: this would also remove {names}, which the desktop or the "
                            "system needs. Nothing will be removed.",
                        ).format(names=i18n.isolate(names)),
                        "Risk",
                    )
                )
            elif sim["remove"]:
                self.removals = list(sim["remove"])
                picked = {n for t in p["tasks"] if t.source == "apt" for n in t.names}
                extra = [n for n in sim["remove"] if n.split(":")[0] not in picked and n not in picked]
                lay.addWidget(
                    _label(
                        tr(
                            "grimoire.spells.cleanupl.remover",
                            "Simulated with apt-get -s. These system packages will be removed:",
                        ),
                        "Risk" if extra else "Muted",
                    )
                )
                lay.addWidget(_box(sim["remove"]))
                if extra:
                    self.allow = QCheckBox(
                        tr(
                            "grimoire.spells.cleanupl.remover",
                            "Yes, also remove the %n other package(s) apt listed",
                            n=len(extra),
                        )
                    )
                    lay.addWidget(self.allow)
                if sim.get("install"):
                    blocked = True
                    lay.addWidget(
                        _label(
                            tr("grimoire.spells.cleanupl.remover", "Refused: apt would install packages to do this."),
                            "Risk",
                        )
                    )
        flat = [n for t in p["tasks"] if t.source != "apt" for n in t.names]
        if flat:
            lay.addWidget(_label(tr("grimoire.spells.cleanupl.remover", "Flatpaks and snaps:"), "Muted"))
            lay.addWidget(_box(flat))
        if p["files"]:
            lay.addWidget(
                _label(
                    tr("grimoire.spells.cleanupl.remover", "Moved to the Trash (you can restore them from there):"),
                    "Muted",
                )
            )
            lay.addWidget(_box([tilde(f) for f in p["files"]]))
        freed = engine.total(found, with_leftovers=False)
        if freed:
            lay.addWidget(
                _label(
                    tr(
                        "grimoire.spells.cleanupl.remover",
                        "About {size} freed. Settings and caches are offered next, after the uninstall.",
                    ).format(size=i18n.ltr(human(freed))),
                    "RowTitle",
                )
            )
        if any(t.root() for t in p["tasks"]):
            lay.addWidget(
                _label(tr("grimoire.spells.cleanupl.remover", "System packages ask for your password once."), "Muted")
            )
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("grimoire.spells.cleanupl.remover", "Cancel"))
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton(tr("grimoire.spells.cleanupl.remover", "Uninstall"))
        self.ok.setObjectName("Primary")
        self.ok.clicked.connect(self.accept)
        self.ok.setEnabled(not blocked and self.allow is None)
        if self.allow is not None:
            self.allow.toggled.connect(lambda on: self.ok.setEnabled(on and not blocked))
        btns.addWidget(cancel)
        btns.addWidget(self.ok)
        lay.addLayout(btns)
        (cancel if blocked else self.ok).setDefault(True)


# ---------------------------------------------------------------- the leftover scan
class LeftoverDialog(QDialog):
    """What the apps left in your home, grouped (Settings, Cache, Starts at login…), each with its size and a tick.
    Settings, caches, state and launchers start ticked; data folders and Flatpak data don't (they can hold your
    own files). Ticked ones go to the Trash."""

    START_TICKED = {"config", "cache", "state", "autostart", "menu", "units"}

    def __init__(self, parent, items: list[tuple[str, Path, int]]):
        super().__init__(parent)
        self.setObjectName("Plan")
        self.setStyleSheet(QSS)
        self.setWindowTitle(tr("grimoire.spells.cleanupl.remover", "Leftovers"))
        self.setMinimumSize(640, 460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.spells.cleanupl.remover", "Leftovers found"), "SectionTitle"))
        lay.addWidget(
            _label(
                tr(
                    "grimoire.spells.cleanupl.remover",
                    "Files these apps left in your home. Ticked ones move to the Trash; anything "
                    "you're not sure about, leave unticked.",
                ),
                "Muted",
            )
        )
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            [tr("grimoire.spells.cleanupl.remover", "Where"), tr("grimoire.spells.cleanupl.remover", "Size")]
        )
        self.tree.setRootIsDecorated(True)
        self.tree.setColumnWidth(0, 440)
        groups: dict[str, QTreeWidgetItem] = {}
        for app, path, size in items:
            g = engine.group_of(path)
            head = groups.get(g)
            if head is None:
                head = groups[g] = QTreeWidgetItem([tr("grimoire.spells.cleanupl.engine", engine.GROUPS[g]), ""])
                head.setFlags(head.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
                self.tree.addTopLevelItem(head)
            it = QTreeWidgetItem([i18n.ltr(tilde(path)), i18n.ltr(human(size))])
            it.setToolTip(0, app)
            it.setData(0, Qt.ItemDataRole.UserRole, str(path))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked if g in self.START_TICKED else Qt.CheckState.Unchecked)
            head.addChild(it)
        self.tree.expandAll()
        lay.addWidget(self.tree, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        keep = QPushButton(tr("grimoire.spells.cleanupl.remover", "Keep them"))
        keep.clicked.connect(self.reject)
        go = QPushButton(tr("grimoire.spells.cleanupl.remover", "Move ticked to the Trash"))
        go.setObjectName("Primary")
        go.clicked.connect(self.accept)
        btns.addWidget(keep)
        btns.addWidget(go)
        lay.addLayout(btns)

    def ticked(self) -> list[Path]:
        out = []
        for i in range(self.tree.topLevelItemCount()):
            head = self.tree.topLevelItem(i)
            for j in range(head.childCount()):
                it = head.child(j)
                if it.checkState(0) == Qt.CheckState.Checked:
                    out.append(Path(it.data(0, Qt.ItemDataRole.UserRole)))
        return out


# ---------------------------------------------------------------- running it
class Remover(QObject):
    """One uninstall at a time: plan → confirm → run → leftovers. Signals reach the UI thread."""

    line = Signal(str)  # helper/flatpak output, for a log
    status = Signal(str)  # one-line progress for the page
    finished = Signal(bool)  # True when something changed (the page re-reads what's installed)
    _planned = Signal(object, object)
    _ran = Signal(object, object, object)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.page = parent
        self.busy = False
        self._planned.connect(self._confirm)
        self._ran.connect(self._after)

    def start(self, found: list[Found]):
        found = [f for f in found if not f.why_not]
        if self.busy or not found:
            return
        self.busy = True
        self.status.emit(tr("grimoire.spells.cleanupl.remover", "Working out what changes…"))
        threading.Thread(target=lambda: self._planned.emit(found, plan(found)), daemon=True).start()

    def leftovers_only(self, found: list[Found]):
        """For apps already gone, or broken half-installs: skip straight to the leftover scan."""
        if self.busy:
            return
        self._scan(found)

    def _confirm(self, found: list[Found], p: dict):
        if p["error"]:
            self.busy = False
            self.status.emit(
                tr("grimoire.spells.cleanupl.remover", "Couldn't plan this: {err}").format(err=i18n.isolate(p["error"]))
            )
            return
        dlg = ConfirmDialog(self.page, found, p)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.busy = False
            self.status.emit(tr("grimoire.spells.cleanupl.remover", "Nothing was changed."))
            return
        for t in p["tasks"]:
            if t.source == "apt":
                t.removals = list(dlg.removals) or list(t.names)
        self.status.emit(tr("grimoire.spells.cleanupl.remover", "Uninstalling…"))

        def work():
            if p["tasks"]:
                apply.run_batch(p["tasks"], self.line.emit, lambda _t: None)
            errors = engine.trash_files(p["files"])
            self._ran.emit(found, p, errors)

        threading.Thread(target=work, daemon=True).start()

    def _after(self, found: list[Found], p: dict, errors: list):
        failed = [t for t in p["tasks"] if t.state != apply.DONE]
        gone = []
        for f in found:
            if f.source in ("apt", "flatpak", "snap"):
                mine = [t for t in p["tasks"] if t.state == apply.DONE and set(f.names) <= set(t.names)]
                if mine:
                    engine.remember(f)
                    gone.append(f)
            elif f.source in ("appimage", "user"):
                gone.append(f)
        msg = tr("grimoire.spells.cleanupl.remover", "Uninstalled %n app(s).", n=len(gone))
        if failed:
            msg += "  " + tr("grimoire.spells.cleanupl.remover", "Problems: {list}").format(
                list="; ".join(f"{t.title}: {t.message}" for t in failed[:2])
            )
        if errors:
            msg += "  " + tr("grimoire.spells.cleanupl.remover", "Problems: {list}").format(list="; ".join(errors[:2]))
        self.status.emit(msg)
        self._scan(gone, changed=bool(gone))

    def _scan(self, found: list[Found], changed: bool = False):
        own = {Path(n) for f in found for n in f.names if isinstance(n, Path)}
        items, seen = [], set()
        for f in found:
            for path, size in engine.guess_leftovers(f) + list(f.leftovers):
                if path not in seen and path not in own:
                    seen.add(path)
                    items.append((f.title, path, size))
        if items:
            dlg = LeftoverDialog(self.page, items)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                picked = dlg.ticked()
                errors = engine.trash_files(picked)
                total = sum(s for _a, p, s in items if p in picked)
                self.status.emit(
                    tr(
                        "grimoire.spells.cleanupl.remover",
                        "Moved %n leftover(s) to the Trash ({size}).",
                        n=len(picked) - len(errors),
                    ).format(size=i18n.ltr(human(total)))
                    + (
                        "  "
                        + tr("grimoire.spells.cleanupl.remover", "Problems: {list}").format(list="; ".join(errors[:2]))
                        if errors
                        else ""
                    )
                )
                changed = changed or bool(picked)
        elif not changed:
            self.status.emit(tr("grimoire.spells.cleanupl.remover", "No leftovers found."))
        self.busy = False
        self.finished.emit(changed)

    def reinstall(self, entry: dict):
        """Put a removed app back (StoreL's install, with its own preview for APT)."""
        if self.busy:
            return
        self.busy = True
        task = Task(
            "install",
            entry["source"],
            entry["title"],
            "cleanupl",
            list(entry["names"]),
            scope=entry.get("scope", "system"),
            remote="flathub",
        )
        if task.source == "flatpak":  # names are refs: app/ID/ARCH/BRANCH
            task.names = [n for n in task.names if n.startswith("app/")]
        self.status.emit(
            tr("grimoire.spells.cleanupl.remover", "Reinstalling {name}…").format(name=i18n.isolate(entry["title"]))
        )

        def work():
            apply.run_batch([task], self.line.emit, lambda _t: None)
            ok = task.state == apply.DONE
            if ok:
                engine.forget(entry)
            self._reinstalled(entry, ok, task.message)

        threading.Thread(target=work, daemon=True).start()

    def _reinstalled(self, entry, ok, message):
        self.status.emit(
            tr("grimoire.spells.cleanupl.remover", "{name} is back.").format(name=i18n.isolate(entry["title"]))
            if ok
            else tr("grimoire.spells.cleanupl.remover", "Couldn't reinstall {name}: {why}").format(
                name=i18n.isolate(entry["title"]), why=message
            )
        )
        self.busy = False
        self.finished.emit(ok)


def hunt() -> str:
    """Click a window to find its app: KWin's own window picker (the pointer becomes a cross). Its desktop file
    name, or "" when cancelled. Blocks: call it off the UI thread."""
    try:
        r = subprocess.run(
            ["qdbus6", "--literal", "org.kde.KWin", "/KWin", "org.kde.KWin.queryWindowInfo"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r'"desktopFile"\s*=\s*\[Variant(?:\(QString\))?:\s*"([^"]*)"', r.stdout)
    if not m:
        m = re.search(r'"resourceClass"\s*=\s*\[Variant(?:\(QString\))?:\s*"([^"]*)"', r.stdout)
    return m.group(1) if m else ""
