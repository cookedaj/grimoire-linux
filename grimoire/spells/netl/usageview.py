# SPDX-License-Identifier: GPL-3.0-or-later
"""NetL's Usage history panel: bytes per day or per month as black & white bars and a table, per interface or all
of them, the apps NetL measured in the picked day or month, and the switch for background recording (the timer
in usage.py).
"""
from PySide6.QtCore import QDateTime, QLocale, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QHeaderView, QPushButton, QVBoxLayout, QWidget

from grimoire.fsutil import human
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.netl import probe, usage
from grimoire.spells.systeml.alertview import _row
from grimoire.spells.systeml.graph import BG, DIM, EDGE, GRID, INK, SOFT, _font, draw_text
from grimoire.spells.systeml.bidi import ltr
from grimoire.spells.systeml.page import NumItem, _label, _tree
from grimoire.widgets import Switch

SHOWN = {"days": 31, "months": 12}


def when_text(t: float) -> str:
    """A short date and time in the app's language (month names from QLocale, not the C locale)."""
    return QLocale().toString(QDateTime.fromSecsSinceEpoch(int(t)), "MMM dd HH:mm")


class UsageBars(QWidget):
    """Download as a solid white bar, upload as a gray one beside it, one pair per day or month."""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)   # a chart/canvas: never mirrored in RTL
        self.rows: list[tuple[str, int, int]] = []
        self.setMinimumHeight(170)

    def set_rows(self, rows):
        self.rows = rows
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(EDGE)
        p.setBrush(BG)
        p.drawRoundedRect(r, 10, 10)
        area = r.adjusted(16, 30, -16, -26)
        p.setFont(_font(11))
        p.setPen(DIM)
        draw_text(p, r.adjusted(16, 10, -16, 0), Qt.AlignmentFlag.AlignLeft,
                   tr("grimoire.spells.netl.usageview", "↓ DOWNLOAD   ↑ UPLOAD"))
        if not self.rows:
            p.setPen(SOFT)
            draw_text(p, area, Qt.AlignmentFlag.AlignCenter, tr("grimoire.spells.netl.usageview", "Nothing recorded yet"))
            p.end()
            return
        top = max(max(max(rx, tx) for _, rx, tx in self.rows), 1)
        draw_text(p, r.adjusted(16, 10, -16, 0), Qt.AlignmentFlag.AlignRight,
                   tr("grimoire.spells.netl.usageview", "max {value}").format(value=human(top)))
        p.setPen(GRID)
        for i in range(4):
            y = area.top() + area.height() * i / 3
            p.drawLine(int(area.left()), int(y), int(area.right()), int(y))
        slot = area.width() / len(self.rows)
        bw = max(1.5, min(14.0, slot * 0.36))
        p.setPen(Qt.PenStyle.NoPen)
        every = max(1, len(self.rows) // 8)
        for i, (label, rx, tx) in enumerate(self.rows):
            x = area.left() + slot * i + slot / 2
            for j, (v, color) in enumerate(((rx, INK), (tx, SOFT))):
                h = area.height() * v / top
                p.setBrush(color)
                p.drawRoundedRect(QRectF(x - bw - 1 + j * (bw + 2), area.bottom() - h, bw, h), 2, 2)
            if i % every == 0 or i == len(self.rows) - 1:
                p.setPen(DIM)
                p.setFont(_font(10, mono=True))
                draw_text(p, QRectF(x - 30, area.bottom() + 6, 60, 14), Qt.AlignmentFlag.AlignHCenter, label)
                p.setPen(Qt.PenStyle.NoPen)
        p.end()


class UsagePanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.data = usage.load()
        self.period = "days"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.timer_sw = Switch()
        self.timer_sub = _label("", "Muted", wrap=True)
        self.timer_sw.toggled.connect(self._toggle)
        lay.addWidget(_row(tr("grimoire.spells.netl.usageview", "Record in the background"), self.timer_sub,
                           self.timer_sw))

        bar = QHBoxLayout()
        bar.setSpacing(0)
        self.segs = []
        for i, (name, key) in enumerate(((tr("grimoire.spells.netl.usageview", "Days"), "days"),
                                         (tr("grimoire.spells.netl.usageview", "Months"), "months"))):
            b = QPushButton(name)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setProperty("pos", "first" if i == 0 else "last")
            b.clicked.connect(lambda _=False, k=key: self.set_period(k))
            bar.addWidget(b)
            self.segs.append((b, key))
        bar.addSpacing(12)
        self.iface = QComboBox()
        self.iface.setMinimumWidth(200)
        self.iface.currentIndexChanged.connect(lambda _: self.fill())
        bar.addWidget(self.iface)
        bar.addStretch(1)
        self.sum = _label("", "Muted")
        bar.addWidget(self.sum)
        lay.addLayout(bar)

        self.bars = UsageBars()
        lay.addWidget(self.bars)
        tables = QHBoxLayout()
        tables.setSpacing(12)
        self.table = _tree([""] * 4)
        self.apps = _tree([tr("grimoire.spells.netl.usageview", "App (measured while NetL was open)"),
                           tr("grimoire.spells.netl.usageview", "Download"), tr("grimoire.spells.netl.usageview", "Upload")])
        for t in (self.table, self.apps):
            h = t.header()
            h.setStretchLastSection(False)
            h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for c in range(1, t.columnCount()):
                h.resizeSection(c, 100)
        self.table.itemSelectionChanged.connect(self._fill_apps)
        tables.addWidget(self.table, 1)
        tables.addWidget(self.apps, 1)
        lay.addLayout(tables, 1)
        page.sig.timer.connect(self._show_timer)
        self.set_period("days")

    def load(self):
        self.page.load_usage()
        POOL.start(Job(usage.enabled, self.page.sig.timer.emit))

    def _show_timer(self, on: bool):
        self.timer_sw.blockSignals(True)
        self.timer_sw.setChecked(on)
        self.timer_sw.blockSignals(False)
        last = self.data.get("t")
        state = tr("grimoire.spells.netl.usageview", "A user timer adds up every interface's counters every 5 "
                   "minutes, even while NetL is closed.") if on else \
            tr("grimoire.spells.netl.usageview", "Off: usage only adds up while NetL is open (once a minute). Turn on "
               "to count everything, every 5 minutes, with a cheap user timer.")
        when = tr("grimoire.spells.netl.usageview", "Last reading: {when}.").format(when=when_text(last)) if last else \
            tr("grimoire.spells.netl.usageview", "No reading yet.")
        self.timer_sub.setText(f"{state} {when}")

    def _toggle(self, on: bool):
        self.page.act(tr("grimoire.spells.netl.usageview", "Background recording"),
                      lambda: usage.set_enabled(on) or (tr("grimoire.spells.netl.usageview", "on") if on else
                                                        tr("grimoire.spells.netl.usageview", "off")),
                      then=self.load)

    def set_data(self, data: dict):
        """The interface picker holds "All interfaces" (no data) and each interface (its name as data)."""
        self.data = data
        names = [None] + usage.interfaces(data)
        if names != [self.iface.itemData(i) for i in range(self.iface.count())]:
            cur = self.iface.currentData()
            self.iface.blockSignals(True)
            self.iface.clear()
            for n in names:
                self.iface.addItem(tr("grimoire.spells.netl.usageview", "All interfaces") if n is None else n, n)
            if cur in names:
                self.iface.setCurrentIndex(names.index(cur))
            self.iface.blockSignals(False)
        self.fill()

    def set_period(self, key: str):
        self.period = key
        for b, k in self.segs:
            b.setChecked(k == key)
        self.table.setHeaderLabels([tr("grimoire.spells.netl.usageview", "Day") if key == "days" else
                                    tr("grimoire.spells.netl.usageview", "Month"),
                                    tr("grimoire.spells.netl.usageview", "Download"),
                                    tr("grimoire.spells.netl.usageview", "Upload"),
                                    tr("grimoire.spells.netl.usageview", "Total")])
        self.fill()

    def _ifaces(self) -> set[str] | None:
        i = self.iface.currentIndex()
        return usage.physical_set(self.data) if i <= 0 else {self.iface.currentData()}

    def fill(self):
        ifaces, period = self._ifaces(), self.period
        keys = sorted(self.data.get(period, {}))
        rows = [(k, *usage.totals(self.data, period, k, ifaces)) for k in keys]
        sel = self.table.currentItem().text(0) if self.table.currentItem() else None
        self.table.setSortingEnabled(False)
        self.table.clear()
        for k, rx, tx in rows:
            it = NumItem([k, ltr(human(rx)), ltr(human(tx)), ltr(human(rx + tx))])
            for c, v in enumerate([k, rx, tx, rx + tx]):
                it.setData(c, Qt.ItemDataRole.UserRole, v)
                if c:
                    it.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.addTopLevelItem(it)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.SortOrder.DescendingOrder)
        hit = self.table.findItems(sel, Qt.MatchFlag.MatchExactly, 0) if sel else []
        if hit:
            self.table.setCurrentItem(hit[0])
        elif self.table.topLevelItemCount():
            self.table.setCurrentItem(self.table.topLevelItem(0))
        recent = rows[-SHOWN[period]:]
        fmt = (lambda k: k[8:]) if period == "days" else \
            (lambda k: QLocale().monthName(int(k[5:7]), QLocale.FormatType.ShortFormat))
        self.bars.set_rows([(fmt(k), rx, tx) for k, rx, tx in recent])
        rx, tx = sum(r[1] for r in recent), sum(r[2] for r in recent)
        span = tr("grimoire.spells.netl.usageview", "last %n day(s): ↓ {down}  ↑ {up}", n=len(recent)) \
            if period == "days" else tr("grimoire.spells.netl.usageview", "last %n month(s): ↓ {down}  ↑ {up}",
                                        n=len(recent))
        self.sum.setText(span.format(down=ltr(human(rx)), up=ltr(human(tx))) if recent else "")
        self._fill_apps()

    def _fill_apps(self):
        it = self.table.currentItem()
        self.apps.setSortingEnabled(False)
        self.apps.clear()
        bucket = "app_days" if self.period == "days" else "app_months"
        for app, (rx, tx) in (self.data.get(bucket, {}).get(it.text(0), {}) if it else {}).items():
            row = NumItem([probe.app_text(app), ltr(human(rx)), ltr(human(tx))])
            for c, v in enumerate([probe.app_text(app).lower(), rx, tx]):
                row.setData(c, Qt.ItemDataRole.UserRole, v)
                if c:
                    row.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.apps.addTopLevelItem(row)
        self.apps.setSortingEnabled(True)
        self.apps.sortItems(1, Qt.SortOrder.DescendingOrder)
