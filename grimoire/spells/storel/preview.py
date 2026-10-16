# SPDX-License-Identifier: GPL-3.0-or-later
"""The dialog before anything is installed or removed: for APT, everything `apt-get -s` says would be installed,
upgraded and removed (removals beyond what you picked need a tick; the desktop, its fonts and required system
packages are refused outright); for Flatpak and Snap, the size, the runtime it brings and where it goes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from grimoire import i18n
from grimoire.fsutil import human
from grimoire.i18n import tr
from grimoire.spells.storel.apply import Task

QSS = """
QDialog#Plan { background: #0b0b0b; }
QLabel#Risk { color: #e8e8e8; font-size: 12px; border-left: 2px solid #f2f2f2; padding-left: 8px; }
QLabel#Risk[rtl="true"] { border-left: none; padding-left: 0; border-right: 2px solid #f2f2f2; padding-right: 8px; }
QPlainTextEdit#Log { font-family: "IBM Plex Mono"; font-size: 11px; color: #bdbdbd; background: #080808;
                     border: 1px solid #1c1c1c; border-radius: 8px; padding: 6px; }
"""


def _label(text="", name="", wrap=True) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)        # package names and app names: never rich text
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    lab.setProperty("rtl", i18n.rtl())
    return lab


def _box(lines: list[str]) -> QPlainTextEdit:
    t = QPlainTextEdit("\n".join(lines))
    t.setObjectName("Log")
    t.setReadOnly(True)
    t.setLayoutDirection(Qt.LayoutDirection.LeftToRight)         # package lists read left to right
    t.setMaximumHeight(min(180, 30 + 18 * len(lines)))
    return t


def where(task: Task) -> str:
    """Where a task installs to or removes from, in a sentence."""
    if task.source == "flatpak":
        return (tr("grimoire.spells.storel.preview", "Flatpak, just for you: no password needed.")
                if task.scope == "user" else
                tr("grimoire.spells.storel.preview", "Flatpak, for everyone on this PC: asks for your password."))
    if task.source == "snap":
        return tr("grimoire.spells.storel.preview", "Snap: asks for your password.")
    return tr("grimoire.spells.storel.preview", "System package (APT): asks for your password.")


class PreviewDialog(QDialog):
    def __init__(self, parent, task: Task, plan: dict):
        super().__init__(parent)
        self.task = task
        self.setObjectName("Plan")
        self.setStyleSheet(QSS)
        install = task.action == "install"
        self.setWindowTitle(tr("grimoire.spells.storel.preview", "Install", "dialog title") if install else
                            tr("grimoire.spells.storel.preview", "Remove", "dialog title"))
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)
        title = (tr("grimoire.spells.storel.preview", "Install {name}?") if install else
                 tr("grimoire.spells.storel.preview", "Remove {name}?")).format(name=i18n.isolate(task.title))
        lay.addWidget(_label(title, "SectionTitle"))
        lay.addWidget(_label(where(task), "Muted"))
        self.allow: QCheckBox | None = None
        self.removals: list[str] = []
        blocked = False
        if task.source == "apt":
            blocked = self._apt(lay, plan)
        elif task.source == "flatpak":
            self._flatpak(lay, plan)
        else:
            self._snap(lay, plan)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("grimoire.spells.storel.preview", "Cancel"))
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self.ok = QPushButton(tr("grimoire.spells.storel.preview", "Install", "button") if install else
                              tr("grimoire.spells.storel.preview", "Remove", "button"))
        self.ok.setObjectName("Primary")
        self.ok.clicked.connect(self.accept)
        self.ok.setEnabled(not blocked and self.allow is None)
        if self.allow is not None:
            self.allow.toggled.connect(lambda on: self.ok.setEnabled(on and not blocked))
        btns.addWidget(self.ok)
        lay.addLayout(btns)
        (cancel if blocked else self.ok).setDefault(True)

    def _sizes(self, lay, download, disk):
        bits = []
        if download:
            bits.append(tr("grimoire.spells.storel.preview", "{size} to download").format(
                size=i18n.ltr(human(download))))
        if disk and disk > 0:
            bits.append(tr("grimoire.spells.storel.preview", "{size} more disk space").format(
                size=i18n.ltr(human(disk))))
        elif disk and disk < 0:
            bits.append(tr("grimoire.spells.storel.preview", "{size} freed").format(size=i18n.ltr(human(-disk))))
        if bits:
            lay.addWidget(_label("   ·   ".join(bits), "RowTitle"))

    def _apt(self, lay, sim: dict) -> bool:
        up, new, rm = sim["upgrade"], sim["install"], sim["remove"]
        lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Simulated with apt-get -s: {new} to install, "
                                "{up} to upgrade, {rm} to remove.").format(new=len(new), up=len(up), rm=len(rm)),
                             "Muted"))
        if new:
            lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Will be installed:"), "Muted"))
            lay.addWidget(_box([f"{n}   {v}" for n, v in new]))
        if up:
            lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Will be upgraded:"), "Muted"))
            lay.addWidget(_box([f"{n}   {old} → {v}" for n, old, v in up]))
        self._sizes(lay, sim.get("download"), sim.get("disk"))
        if sim.get("blocked"):
            names = ", ".join(n for n, _why in sim["blocked"])
            lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Refused: this would remove {names}, which the "
                                    "desktop or the system needs. StoreL never lets those go.").format(
                                        names=i18n.isolate(names)), "Risk"))
            if rm:
                lay.addWidget(_box(rm))
            return True
        if rm:
            self.removals = list(rm)
            extra = [n for n in rm if n.split(":")[0] not in self.task.names and n not in self.task.names]
            lay.addWidget(_label(tr("grimoire.spells.storel.preview", "These packages will be REMOVED:"), "Risk"))
            lay.addWidget(_box(rm))
            if self.task.action == "remove":
                lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Your settings and files stay; apt "
                                        "doesn't purge."), "Muted"))
            if extra or self.task.action == "install":
                self.allow = QCheckBox(tr("grimoire.spells.storel.preview", "Yes, remove these packages"))
                lay.addWidget(self.allow)
        lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Asks for your password once. Progress shows "
                                "under Queue."), "Muted"))
        return False

    def _flatpak(self, lay, info: dict):
        if self.task.action == "install":
            if info.get("version"):
                lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Version {version}").format(
                    version=i18n.ltr(info["version"])), "Muted"))
            self._sizes(lay, info.get("download"), info.get("installed"))
            if info.get("runtime") and not info.get("runtime_installed"):
                lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Also installs the runtime it needs: "
                                        "{runtime}").format(runtime=i18n.ltr(info["runtime"])), "Muted"))
            if info.get("error"):
                lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Couldn't ask the remote for details "
                                        "({err}); it will still try.").format(err=i18n.isolate(info["error"])),
                                     "Muted"))
        else:
            lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Its data in ~/.var/app stays, so a reinstall "
                                    "picks up where you left off. Runtimes other apps share stay too."), "Muted"))
        lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Progress shows under Queue."), "Muted"))

    def _snap(self, lay, info: dict):
        if self.task.classic:
            lay.addWidget(_label(tr("grimoire.spells.storel.preview", "This snap runs without the snap sandbox "
                                    "(classic confinement): it can reach your whole system."), "Risk"))
        if self.task.action == "remove":
            lay.addWidget(_label(tr("grimoire.spells.storel.preview", "snapd keeps a snapshot of its data for a "
                                    "while."), "Muted"))
        lay.addWidget(_label(tr("grimoire.spells.storel.preview", "Progress shows under Queue."), "Muted"))

    def confirmed_removals(self) -> list[str]:
        """Exactly the simulated removals, which the helper holds the step to (none unless you agreed)."""
        if not self.removals:
            return []
        if self.allow is None or self.allow.isChecked():
            return list(self.removals)
        return []
