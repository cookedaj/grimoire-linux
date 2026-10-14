# SPDX-License-Identifier: GPL-3.0-or-later
"""The dialog before an update runs: what APT would upgrade, install and remove (from apt-get -s), the Flatpaks,
snaps and firmware in the batch. Removals need a tick; removing the desktop or its fonts is refused outright."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from grimoire import i18n
from grimoire.i18n import tr
from grimoire.spells.updatel.apply import Plan
from grimoire.spells.updatel.sources import isolate


def _label(text="", name="", wrap=True) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)        # package names from apt-get -s: never rich text
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    lab.setProperty("rtl", i18n.rtl())               # the Risk mark sits on the reading side
    return lab


def _box(lines: list[str]) -> QPlainTextEdit:
    t = QPlainTextEdit("\n".join(lines))
    t.setObjectName("Log")
    t.setReadOnly(True)
    t.setMaximumHeight(min(200, 30 + 18 * len(lines)))
    return t


class PreviewDialog(QDialog):
    def __init__(self, parent, plan: Plan, sim: dict | None, counts: dict[str, int]):
        super().__init__(parent)
        self.setObjectName("Plan")
        self.setWindowTitle(tr("grimoire.spells.updatel.preview", "Update", "dialog title"))
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.spells.updatel.preview", "Before anything changes"), "SectionTitle"))
        self.allow = None
        blocked = False
        if sim is not None:
            up, new, rm, kept = sim["upgrade"], sim["install"], sim["remove"], sim["kept"]
            lay.addWidget(_label(tr("grimoire.spells.updatel.preview",
                                    "APT (simulated with apt-get -s): {up} to upgrade, {new} newly "
                                    "installed, {rm} to remove, {kept} kept back.").format(
                                        up=len(up), new=len(new), rm=len(rm), kept=len(kept)), "RowTitle"))
            if up:
                lay.addWidget(_box([f"{n}   {old} → {v}" for n, old, v in up]))
            if new:
                lay.addWidget(_label(tr("grimoire.spells.updatel.preview",
                                        "Newly installed (new dependencies):"), "Muted"))
                lay.addWidget(_box([f"{n}   {v}" for n, v in new]))
            if kept:
                lay.addWidget(_label(tr("grimoire.spells.updatel.preview",
                                        "Kept back (phased rollout or would need removals): {names}")
                                     .format(names=isolate(" ".join(kept))), "Muted"))
            if sim["protected"]:
                blocked = True
                lay.addWidget(_label(tr("grimoire.spells.updatel.preview",
                                        "Refused: this upgrade would remove {names}. UpdateL never lets the "
                                        "desktop or its fonts go. Update those packages on their own or wait for "
                                        "a fixed update.").format(names=isolate(", ".join(sim["protected"]))), "Risk"))
            elif rm:
                lay.addWidget(_label(tr("grimoire.spells.updatel.preview", "These packages would be REMOVED:"), "Risk"))
                lay.addWidget(_box(rm))
                self.allow = QCheckBox(tr("grimoire.spells.updatel.preview", "Yes, remove these packages"))
                lay.addWidget(self.allow)
        other = []
        if plan.flatpak_user is None or plan.flatpak_user or plan.flatpak_system is None or plan.flatpak_system:
            other.append(tr("grimoire.spells.updatel.preview", "Flatpak: %n update(s)", n=counts.get("flatpak", 0)))
        if plan.snap is None or plan.snap:
            other.append(tr("grimoire.spells.updatel.preview", "Snap: %n update(s)", n=counts.get("snap", 0)))
        if plan.fwupd:
            other.append(tr("grimoire.spells.updatel.preview", "Firmware: %n device(s)", n=len(plan.fwupd)))
        if other:
            lay.addWidget(_label("   ·   ".join(other), "RowTitle"))
        if plan.fwupd:
            lay.addWidget(_label(tr("grimoire.spells.updatel.preview",
                                    "Keep the PC plugged in and don't turn it off. Some firmware installs "
                                    "during the next restart."), "Risk"))
        root = plan.refresh or plan.fwupd or any(x is None or x for x in (plan.apt, plan.flatpak_system, plan.snap))
        if root and not blocked:
            lay.addWidget(_label(tr("grimoire.spells.updatel.preview",
                                    "Asks for your password once. Progress shows under Activity."),
                                 "Muted"))
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("grimoire.spells.updatel.preview", "Cancel"))
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self.ok = QPushButton(tr("grimoire.spells.updatel.preview", "Update", "button"))
        self.ok.setObjectName("Primary")
        self.ok.clicked.connect(self.accept)
        self.ok.setEnabled(not blocked and self.allow is None)
        if self.allow is not None:
            self.allow.toggled.connect(self.ok.setEnabled)
        btns.addWidget(self.ok)
        lay.addLayout(btns)

    def removals_allowed(self) -> bool:
        return bool(self.allow and self.allow.isChecked())
