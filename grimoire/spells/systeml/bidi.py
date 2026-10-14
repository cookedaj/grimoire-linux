# SPDX-License-Identifier: GPL-3.0-or-later
"""Right-to-left helpers for SystemL's and NetL's data: numbers with units, addresses and commands are
left-to-right text that Qt would otherwise reorder ("1.9 GB" as "GB 1.9", "-20" as "20-") or align away from
where an Arabic or Urdu reader starts."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel


def ltr(s: str) -> str:
    """Left-to-right data kept whole inside right-to-left text (a no-op in left-to-right languages)."""
    return f"\u202a{s}\u202c" if s and QApplication.isRightToLeft() else s


def lead(label: QLabel) -> QLabel:
    """A label that starts where reading starts even when its own text runs left to right (Qt aligns a label by
    its text's direction): data lines, Latin titles such as "Wi-Fi"."""
    if QApplication.isRightToLeft():
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute
                           | (label.alignment() & Qt.AlignmentFlag.AlignVertical_Mask))
    return label
