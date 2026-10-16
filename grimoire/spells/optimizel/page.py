# SPDX-License-Identifier: GPL-3.0-or-later
"""OptimizeL page: a scan of this PC as grouped on/off switches (with search and tier filters), one-click profiles,
and a Benchmark tab to measure before and after. Flipping switches only stages changes; the bar at the bottom
applies them in one go (one password prompt for all the system ones). A profile shows its plan first."""
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.optimizel import profiles, tweaks
from grimoire.spells.optimizel.benchview import BenchView
from grimoire.widgets import Switch, segments

# only OptimizeL's own looks (the shared theme stays untouched)
QSS = """
QLabel#BadgeStrong { font-size: 9px; font-weight: 700; letter-spacing: 1px; color: #ffffff; border: 1px solid #f2f2f2;
                     border-radius: 4px; padding: 1px 6px; }
QLabel#Gain { color: #bdbdbd; font-size: 12px; }
QLabel#Risk { color: #e8e8e8; font-size: 12px; border-left: 2px solid #f2f2f2; padding-left: 8px; }
QLabel#Value[strong="true"] { color: #ffffff; font-weight: 600; }
QPushButton#Profile { background: #0f0f0f; border: 1px solid #1f1f1f; border-radius: 10px; padding: 0; text-align: left; }
QPushButton#Profile:hover { border-color: #8a8a8a; }
QPushButton#Profile:disabled { background: transparent; border-color: #161616; }
QLabel#ProfileName { font-size: 14px; font-weight: 600; color: #ffffff; }
QLabel#ProfileName:disabled { color: #555555; }
QLabel#ProfileCount { font-family: "IBM Plex Mono"; font-size: 11px; color: #8c8c8c; }
QLineEdit#Search { padding: 8px 10px; }
QDialog#Plan { background: #0b0b0b; }
"""
# Arabic/Urdu words drawn through IBM Plex Mono's fallback are measured narrower than they paint, so a wrapped
# "now … → …" line overflows its label; in a right-to-left language the readings use the sans font instead
RTL_QSS = 'QLabel#Value { font-family: "IBM Plex Sans"; }'
FILTERS = {"All": tr_noop("grimoire.spells.optimizel.page", "All"),                   # id → label (shown through tr)
           "Safe": tr_noop("grimoire.spells.optimizel.page", "Safe"),
           "Aggressive": tr_noop("grimoire.spells.optimizel.page", "Aggressive"),
           "On": tr_noop("grimoire.spells.optimizel.page", "On"),
           "Off": tr_noop("grimoire.spells.optimizel.page", "Off")}


class _Signals(QObject):
    scanned = Signal(object)
    applied = Signal(object)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _badge(text: str, kind="") -> QLabel:
    return _label(text.upper(), {"solid": "BadgeSolid", "strong": "BadgeStrong"}.get(kind, "Badge"))


def _repolish(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)


class Row(QFrame):
    """One tweak: title, badges, what it does, the gain (and risk), live value → target, and its switch."""
    flipped = Signal(str, bool)

    def __init__(self, t: tweaks.Tweak):
        super().__init__()
        self.t = t
        self.state = "off"
        self.setObjectName("Row")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 16, 18, 16)
        lay.setSpacing(18)
        text = QVBoxLayout()
        text.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = _label(t.text("title"), "RowTitle")
        top.addWidget(self.title)
        holder = QWidget()                 # in a narrow window badges get clipped, never the switch
        holder.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.badges = QHBoxLayout(holder)
        self.badges.setContentsMargins(0, 0, 0, 0)
        self.badges.setSpacing(6)
        self.badges.addStretch(1)
        top.addWidget(holder, 1)
        text.addLayout(top)
        text.addWidget(_label(t.text("why"), "Muted", wrap=True))
        if t.gain:
            text.addWidget(_label(tr("grimoire.spells.optimizel.page",
                                     "Gain: {text}").format(text=t.text("gain")), "Gain", wrap=True))
        if t.risk:
            text.addWidget(_label(tr("grimoire.spells.optimizel.page",
                                     "Can go wrong: {text}").format(text=t.text("risk")), "Risk", wrap=True))
        self.value = _label("", "Value", wrap=True)
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(self.value)
        lay.addLayout(text, 1)

        self.switch = Switch()
        self.switch.toggled.connect(lambda on: self.flipped.emit(t.id, on))
        self.done = QLabel()
        self.done.setObjectName("Done")
        lay.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.done, 0, Qt.AlignmentFlag.AlignVCenter)
        fields = ("group", "title", "why", "gain", "risk", "target", "tier")     # English and translated both match
        self.haystack = " ".join([t.id] + [getattr(t, f) for f in fields] + [t.text(f) for f in fields]).lower()

    def show_state(self, info: dict, pending: bool | None):
        """info is one scan result; pending is the staged on/off, or None when nothing is staged."""
        self.state = info["state"]
        on = self.state == "on"
        while self.badges.count() > 1:      # keep the trailing stretch
            self.badges.takeAt(0).widget().deleteLater()
        badges = [_badge(self.t.text("tier"), "strong" if self.t.tier == "Aggressive" else "")]
        if info["note"]:
            badges.insert(0, _badge(info["note"], "solid"))
        if self.state in ("on", "off"):
            if self.t.when != "now":
                badges.append(_badge(tr("grimoire.spells.optimizel.kinds", tweaks.WHEN[self.t.when])))
            if self.t.root:
                badges.append(_badge(tr("grimoire.spells.optimizel.page", "Password")))
            if self.t.installs and self.state == "off":
                b = _badge(tr("grimoire.spells.optimizel.page", "Installs a package"))
                b.setToolTip(tr("grimoire.spells.optimizel.page",
                                "Turning this on installs {package} from Ubuntu's archive").format(
                    package=self.t.installs))
                badges.append(b)
            if self.t.recommended and self.t.tier == "Safe" and self.state == "off":
                badges.append(_badge(tr("grimoire.spells.optimizel.page", "Recommended")))
        for i, b in enumerate(badges):
            self.badges.insertWidget(i, b)

        live = info["current"]
        # a catalog text, or a reading (which tr() leaves as it is)
        goal = tr("grimoire.spells.optimizel.tweaks", info.get("goal") or self.t.target)
        if self.state == "na":
            self.value.setText(info["reason"])
        elif self.state == "native":
            self.value.setText(_now_line(live) if live else "")
        elif pending is not None:
            self.value.setText(_change_line(live, goal if pending else None))
        else:
            self.value.setText(_now_line(live) if on else _change_line(live, goal))
        self.haystack_live = (live or "").lower()

        switchable = self.state in ("on", "off")
        self.switch.setVisible(switchable)
        self.done.setVisible(not switchable)
        if self.state == "native":
            self.done.setText(tr("grimoire.spells.optimizel.page", "Already set"))
        elif self.state == "na":
            self.done.setText(tr("grimoire.spells.optimizel.page", "Not needed"))
        self.switch.blockSignals(True)
        self.switch.setChecked(on if pending is None else pending)
        self.switch.blockSignals(False)
        self.setProperty("pending", pending is not None)
        self.setProperty("muted", self.state in ("na", "native"))
        for w in (self, self.title):
            _repolish(w)

    def matches(self, words: list[str], tier_filter: str) -> bool:
        if tier_filter in ("Safe", "Aggressive") and self.t.tier != tier_filter:
            return False
        if tier_filter == "On" and self.state != "on":
            return False
        if tier_filter == "Off" and self.state != "off":
            return False
        hay = self.haystack + " " + getattr(self, "haystack_live", "")
        return all(w in hay for w in words)


class NavItem(QPushButton):
    """Group name on the left, "2/4" on the right."""

    def __init__(self, name: str):
        super().__init__()
        self.setObjectName("SubNavItem")
        self.setCheckable(True)
        self.setMinimumHeight(34)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        self.name = _label(tr("grimoire.spells.optimizel.tweaks", name), "NavName")
        self.count = _label("", "NavCount")
        for w in (self.name, self.count):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self.name)
        lay.addStretch(1)
        lay.addWidget(self.count)

    def setChecked(self, on):
        super().setChecked(on)
        self.name.setProperty("on", on)
        _repolish(self.name)


class ProfileButton(QPushButton):
    def __init__(self, p: profiles.Profile):
        super().__init__()
        self.p = p
        self.setObjectName("Profile")
        self.setMinimumHeight(84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(3)
        top = QHBoxLayout()
        self.name = _label(tr("grimoire.spells.optimizel.profiles", p.name), "ProfileName")
        self.count = _label("", "ProfileCount")
        top.addWidget(self.name)
        top.addStretch(1)
        top.addWidget(self.count)
        lay.addLayout(top)
        lay.addWidget(_label(tr("grimoire.spells.optimizel.profiles", p.blurb), "Muted", wrap=True))
        for w in self.findChildren(QLabel):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class PlanDialog(QDialog):
    """Exactly which switches a profile flips, before anything happens."""

    def __init__(self, parent, p: profiles.Profile, changes: dict, info: dict):
        super().__init__(parent)
        self.setObjectName("Plan")
        self.setWindowTitle(tr("grimoire.spells.optimizel.profiles", p.name))
        self.setMinimumWidth(640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.spells.optimizel.profiles", p.name), "SectionTitle"))
        lay.addWidget(_label(tr("grimoire.spells.optimizel.profiles", p.blurb), "Muted", wrap=True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 6, 8, 6)
        col.setSpacing(6)
        for tid, on in changes.items():
            t = tweaks.BY_ID[tid]
            row = QFrame()
            row.setObjectName("Row")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            rl.setSpacing(3)
            top = QHBoxLayout()
            top.setSpacing(8)
            head = tr("grimoire.spells.optimizel.page", "Turn on  ·  {tweak}") if on \
                else tr("grimoire.spells.optimizel.page", "Turn off  ·  {tweak}")
            top.addWidget(_label(head.format(tweak=t.text("title")), "RowTitle"))
            top.addStretch(1)
            top.addWidget(_badge(t.text("tier"), "strong" if t.tier == "Aggressive" else ""))
            if t.when != "now":
                top.addWidget(_badge(tr("grimoire.spells.optimizel.kinds", tweaks.WHEN[t.when])))
            rl.addLayout(top)
            goal = tr("grimoire.spells.optimizel.tweaks", info[tid].get("goal") or t.target)
            rl.addWidget(_label(_change_line(info[tid]["current"], goal if on else None), "Value", wrap=True))
            if on and t.risk:
                rl.addWidget(_label(tr("grimoire.spells.optimizel.page",
                                       "Can go wrong: {text}").format(text=t.text("risk")), "Risk", wrap=True))
            col.addWidget(row)
        col.addStretch(1)
        scroll.setWidget(inner)
        scroll.setMinimumHeight(min(520, 90 + 74 * len(changes)))
        lay.addWidget(scroll, 1)
        notes = [tr("grimoire.spells.optimizel.page", "%n switch(es).", n=len(changes))]
        aggressive = sum(tweaks.BY_ID[t].tier == "Aggressive" and on for t, on in changes.items())
        if aggressive:
            notes.append(tr("grimoire.spells.optimizel.page", "%n of them Aggressive.", n=aggressive))
        notes += _later_notes(changes)
        lay.addWidget(_label(" ".join(notes), "Muted", wrap=True))
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("grimoire.spells.optimizel.page", "Cancel"))
        cancel.clicked.connect(self.reject)
        ok = QPushButton(tr("grimoire.spells.optimizel.page", "Apply %n change(s)", n=len(changes)))
        ok.setObjectName("Primary")
        ok.setMinimumWidth(160)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)


class OptimizeLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.setStyleSheet(i18n.qss(QSS) + (RTL_QSS if i18n.rtl() else ""))
        self.info: dict[str, dict] = {}
        self.pending: dict[str, bool] = {}
        self.busy = False
        self.filter = "All"
        self._sig = _Signals()
        self._sig.scanned.connect(self._on_scanned)
        self._sig.applied.connect(self._on_applied)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 22)
        root.setSpacing(16)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(_label("OptimizeL", "Title"))
        titles.addWidget(_label(tr("grimoire.spells.optimizel.page",
                                   "Tunes this PC for speed. Every switch shows what it changes and what you gain, "
                                   "stays put through restarts, and turning it off puts back exactly what was there."),
                                "Subtitle", wrap=True))
        head.addLayout(titles, 1)
        self.rescan_btn = QPushButton(tr("grimoire.spells.optimizel.page", "Rescan"))
        self.rescan_btn.clicked.connect(self.scan)
        head.addWidget(self.rescan_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        tabs = QHBoxLayout()
        tabs.setSpacing(4)
        self.tabs = []
        for i, name in enumerate((tr("grimoire.spells.optimizel.page", "Tweaks"),
                                  tr("grimoire.spells.optimizel.page", "Benchmark"))):
            b = QPushButton(name)
            b.setObjectName("Tab")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, i=i: self._tab(i))
            tabs.addWidget(b)
            self.tabs.append(b)
        tabs.addStretch(1)
        root.addLayout(tabs)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.stack.addWidget(self._tweaks_view())
        self.bench = BenchView()
        self.stack.addWidget(self.bench)
        self._tab(0)

        self.bar = QFrame()
        self.bar.setObjectName("Pending")
        bl = QHBoxLayout(self.bar)
        bl.setContentsMargins(22, 12, 14, 12)
        bl.setSpacing(10)
        self.bar_text = _label("", "PendingText")
        self.bar_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bl.addWidget(self.bar_text, 1)
        self.discard_btn = QPushButton(tr("grimoire.spells.optimizel.page", "Discard"))
        self.discard_btn.clicked.connect(self._discard)
        self.apply_btn = QPushButton(tr("grimoire.spells.optimizel.page", "Apply changes"))
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.setMinimumWidth(150)
        self.apply_btn.clicked.connect(self._apply)
        bl.addWidget(self.discard_btn)
        bl.addWidget(self.apply_btn)
        root.addWidget(self.bar)

        self.toast = _label("", "Toast", wrap=True)
        self.toast.hide()
        root.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=12000, timeout=self.toast.hide)

        self.nav[tweaks.GROUPS[0]].setChecked(True)
        self._refresh_bar()
        self.scan()
        self.bench.reload()

    def _tweaks_view(self) -> QWidget:
        view = QWidget()
        view.setObjectName("Page")
        col0 = QVBoxLayout(view)
        col0.setContentsMargins(0, 0, 0, 0)
        col0.setSpacing(14)

        prow = QHBoxLayout()
        prow.setSpacing(12)
        self.profile_btns: dict[str, ProfileButton] = {}
        for p in profiles.available():
            b = ProfileButton(p)
            b.clicked.connect(lambda _=False, pid=p.id: self._profile(pid))
            prow.addWidget(b, 1)
            self.profile_btns[p.id] = b
        col0.addLayout(prow)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stats = {}
        for key, label in (("on", tr("grimoire.spells.optimizel.page", "On")),
                           ("left", tr("grimoire.spells.optimizel.page", "Recommended left")),
                           ("native", tr("grimoire.spells.optimizel.page", "Already optimal")),
                           ("finish", tr("grimoire.spells.optimizel.page", "Waiting on restart"))):
            tile = QFrame()
            tile.setObjectName("Stat")
            tl = QVBoxLayout(tile)
            tl.setContentsMargins(18, 10, 18, 10)
            tl.setSpacing(0)
            num = _label("–", "StatNum")
            tl.addWidget(num)
            tl.addWidget(_label(label.upper(), "StatLabel"))
            stats.addWidget(tile, 1)
            self.stats[key] = num
        col0.addLayout(stats)

        frow = QHBoxLayout()
        frow.setSpacing(0)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText(tr("grimoire.spells.optimizel.page",
                                          "Search tweaks: gpu, boot, swap, latency…"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph("search", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._apply_filter)
        frow.addWidget(self.search, 1)
        frow.addSpacing(14)
        self.seg = {}
        for name, label in FILTERS.items():
            b = QPushButton(tr("grimoire.spells.optimizel.page", label))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, n=name: self._set_filter(n))
            frow.addWidget(b)
            self.seg[name] = b
        segments(list(self.seg.values()))
        self.seg["All"].setChecked(True)
        col0.addLayout(frow)

        body = QHBoxLayout()
        body.setSpacing(28)
        nav = QVBoxLayout()
        nav.setSpacing(2)
        nav.addWidget(_label(tr("grimoire.spells.optimizel.page", "GROUPS"), "NavSection"))
        self.nav: dict[str, NavItem] = {}
        for g in tweaks.GROUPS:
            item = NavItem(g)
            item.clicked.connect(lambda _=False, g=g: self._jump(g))
            nav.addWidget(item)
            self.nav[g] = item
        nav.addStretch(1)
        navw = QWidget()
        navw.setFixedWidth(200)
        navw.setLayout(nav)
        body.addWidget(navw)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 14, 24)
        col.setSpacing(10)
        self.rows: dict[str, Row] = {}
        self.sections: dict[str, QWidget] = {}
        self.section_counts: dict[str, QLabel] = {}
        self.good_boxes: dict[str, QWidget] = {}
        for g in tweaks.GROUPS:
            head_row = QWidget()
            hl = QHBoxLayout(head_row)
            hl.setContentsMargins(2, 18 if self.sections else 0, 2, 4)
            hl.addWidget(_label(tr("grimoire.spells.optimizel.tweaks", g), "SectionTitle"))
            hl.addStretch(1)
            cnt = _label("", "Muted")
            hl.addWidget(cnt)
            col.addWidget(head_row)
            self.sections[g] = head_row
            self.section_counts[g] = cnt
            for t in (t for t in tweaks.TWEAKS if t.group == g):
                row = Row(t)
                row.flipped.connect(self._flip)
                col.addWidget(row)
                self.rows[t.id] = row
            good = QWidget()
            gl = QVBoxLayout(good)
            gl.setContentsMargins(4, 2, 0, 0)
            gl.setSpacing(2)
            col.addWidget(good)
            self.good_boxes[g] = good
        self.empty = _label(tr("grimoire.spells.optimizel.page", "No tweak matches."), "Muted")
        self.empty.hide()
        col.addWidget(self.empty)
        col.addStretch(1)
        self.scroll.setWidget(inner)
        self.scroll.verticalScrollBar().valueChanged.connect(self._spy)
        body.addWidget(self.scroll, 1)
        col0.addLayout(body, 1)
        return view

    def _tab(self, i):
        self.stack.setCurrentIndex(i)
        for j, b in enumerate(self.tabs):
            b.setChecked(i == j)

    # ------------------------------------------------------------------ scanning
    def scan(self):
        if self.busy:
            return
        self.rescan_btn.setText(tr("grimoire.spells.optimizel.page", "Scanning…"))
        sig = self._sig
        POOL.start(Job(_scan, sig.scanned.emit))

    def _on_scanned(self, result):
        self.rescan_btn.setText(tr("grimoire.spells.optimizel.page", "Rescan"))
        self.info = result["tweaks"]
        # drop staged flips that the system already matches (e.g. changed elsewhere)
        self.pending = {k: v for k, v in self.pending.items() if (self.info[k]["state"] == "on") != v}
        for tid, row in self.rows.items():
            row.show_state(self.info[tid], self.pending.get(tid))
        for g, box in self.good_boxes.items():
            lay = box.layout()
            while lay.count():
                lay.takeAt(0).widget().deleteLater()
            for text in result["checks"].get(g, []):
                lay.addWidget(_good_line(text))
            box.setProperty("n", len(result["checks"].get(g, [])))
        self._refresh_counts()
        self._refresh_bar()
        self._apply_filter()

    def _states(self) -> dict[str, str]:
        return {tid: i["state"] for tid, i in self.info.items()}

    def _refresh_counts(self):
        states = self._states()
        self.stats["on"].setText(str(sum(s == "on" for s in states.values())))
        self.stats["left"].setText(str(len(profiles.plan("recommended", states))))
        checks = sum(self.good_boxes[g].property("n") or 0 for g in tweaks.GROUPS)
        self.stats["native"].setText(str(sum(s == "native" for s in states.values()) + checks))
        self.stats["finish"].setText(str(sum(bool(i["note"]) for i in self.info.values())))
        for g in tweaks.GROUPS:
            ids = [t.id for t in tweaks.TWEAKS if t.group == g]
            live = [i for i in ids if states.get(i) in ("on", "off")]
            on = sum(states.get(i) == "on" for i in live)
            self.nav[g].count.setText(f"{on}/{len(live)}" if live else "✓")
            self.section_counts[g].setText(tr("grimoire.spells.optimizel.page",
                                              "{on} of {total} on").format(on=on, total=len(live)) if live
                                           else tr("grimoire.spells.optimizel.page", "Nothing to change"))
        for pid, b in self.profile_btns.items():
            n = len(profiles.plan(pid, states))
            b.count.setText(tr("grimoire.spells.optimizel.page", "%n change(s)", n=n) if n
                            else tr("grimoire.spells.optimizel.page", "nothing to do"))
            b.setEnabled(bool(n) and not self.busy)
            _repolish(b.name)

    # ------------------------------------------------------------------ search and filters
    def _set_filter(self, name):
        self.filter = name
        for n, b in self.seg.items():
            b.setChecked(n == name)
        self._apply_filter()

    def _apply_filter(self):
        words = self.search.text().lower().split()
        filtering = bool(words) or self.filter != "All"
        any_shown = False
        for g in tweaks.GROUPS:
            shown = 0
            for t in (t for t in tweaks.TWEAKS if t.group == g):
                ok = self.rows[t.id].matches(words, self.filter)
                self.rows[t.id].setVisible(ok)
                shown += ok
            self.sections[g].setVisible(bool(shown) or not filtering)
            self.good_boxes[g].setVisible(not filtering)
            self.nav[g].setVisible(bool(shown) or not filtering)
            any_shown |= bool(shown)
        self.empty.setVisible(filtering and not any_shown)

    # ------------------------------------------------------------------ staging
    def _flip(self, tid, on):
        if (self.info.get(tid, {}).get("state") == "on") == on:
            self.pending.pop(tid, None)
        else:
            self.pending[tid] = on
        self.rows[tid].show_state(self.info[tid], self.pending.get(tid))
        self._refresh_bar()

    def _discard(self):
        self.pending.clear()
        for tid, row in self.rows.items():
            row.show_state(self.info[tid], None)
        self._refresh_bar()

    def _refresh_bar(self):
        n = len(self.pending)
        self.bar.setVisible(bool(n) or self.busy)
        if self.busy:
            self.bar_text.setText(tr("grimoire.spells.optimizel.page",
                                     "Applying… if a password prompt opens, it's for the system changes."))
            return
        ons = sum(self.pending.values())
        offs = n - ons
        if ons and offs:
            text = tr("grimoire.spells.optimizel.page",
                      "{on} to turn on and {off} to turn off.").format(on=ons, off=offs)
        elif ons:
            text = tr("grimoire.spells.optimizel.page", "%n to turn on.", n=ons)
        else:
            text = tr("grimoire.spells.optimizel.page", "%n to turn off.", n=offs)
        self.bar_text.setText("   ".join([text] + _later_notes(self.pending)) if n else "")

    def _jump(self, g):
        self.scroll.verticalScrollBar().setValue(self.sections[g].y())
        for name, item in self.nav.items():
            item.setChecked(name == g)

    def _spy(self, value):
        current = tweaks.GROUPS[0]
        for g, w in self.sections.items():
            if w.isVisible() and w.y() <= value + 40:
                current = g
        for name, item in self.nav.items():
            item.setChecked(name == current)

    # ------------------------------------------------------------------ profiles
    def _profile(self, pid):
        if self.busy or not self.info:
            return
        changes = profiles.plan(pid, self._states())
        if not changes:
            return
        dlg = PlanDialog(self, profiles.BY_ID[pid], changes, self.info)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.pending = dict(changes)
            self._apply()

    # ------------------------------------------------------------------ applying
    def _apply(self):
        if not self.pending or self.busy:
            return
        self.busy = True
        changes = dict(self.pending)
        for tid, row in self.rows.items():
            row.show_state(self.info[tid], changes.get(tid))
            row.switch.setEnabled(False)
        for w in (self.apply_btn, self.discard_btn, *self.profile_btns.values()):
            w.setEnabled(False)
        self._refresh_bar()
        sig = self._sig
        POOL.start(Job(lambda: (changes, _apply_safely(changes)), sig.applied.emit))

    def _on_applied(self, result):
        changes, problems = result
        self.busy = False
        for w in (self.apply_btn, self.discard_btn):
            w.setEnabled(True)
        for row in self.rows.values():
            row.switch.setEnabled(True)
        self.pending.clear()
        cancelled = getattr(problems, "cancelled", "")             # tweaks.Problems says what went wrong as data
        root_failed = getattr(problems, "root_failed", False)
        done = {t: on for t, on in changes.items() if not (root_failed and tweaks.BY_ID[t].root)}
        ons = sum(done.values())
        offs = len(done) - ons
        if ons and offs:
            text = tr("grimoire.spells.optimizel.page", "Turned on {on} and turned off {off}.").format(on=ons, off=offs)
        elif ons:
            text = tr("grimoire.spells.optimizel.page", "Turned on %n.", n=ons)
        elif offs:
            text = tr("grimoire.spells.optimizel.page", "Turned off %n.", n=offs)
        else:
            text = tr("grimoire.spells.optimizel.page", "Nothing changed.")
        if any(tweaks.BY_ID[t].when == "restart" for t in done):
            text += " " + tr("grimoire.spells.optimizel.page", "Restart to finish the ones marked so.")
        if cancelled:
            text += " " + tr("grimoire.spells.optimizel.page",
                             "System changes were skipped because the password prompt was cancelled.")
        others = [p for p in problems if p != cancelled]
        if others:
            text += " " + tr("grimoire.spells.optimizel.page", "Problems: {list}").format(list="; ".join(others))
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()
        self.scan()


def _apply_safely(changes: dict) -> list[str]:
    """tweaks.apply(), but any error comes back as a problem so _on_applied always runs (no stuck "Applying…")."""
    try:
        return tweaks.apply(changes)
    except Exception as e:
        return [tr("grimoire.spells.optimizel.page", "Couldn't apply: {error}").format(error=e)]


def _iso(text: str) -> str:
    """A reading or target kept in one piece inside a right-to-left line (a first-strong isolate: "swappiness 60"
    stays left to right, a translated phrase keeps its own direction)."""
    return f"\u2068{text}\u2069" if i18n.rtl() and text else text


def _now_line(live: str) -> str:
    return tr("grimoire.spells.optimizel.page", "now  {value}").format(value=_iso(live))


def _change_line(live: str, goal: str | None) -> str:
    """"now <value> → <target>"; goal None means turning it off."""
    if goal is None:
        return tr("grimoire.spells.optimizel.page", "now  {value}   →   back to how it was").format(value=_iso(live))
    return tr("grimoire.spells.optimizel.page", "now  {value}   →   {target}").format(value=_iso(live),
                                                                                       target=_iso(goal))


def _later_notes(changes) -> list[str]:
    """Sentences about a batch of switches: the password prompt, and when they finish."""
    notes = []
    if any(tweaks.BY_ID[t].root for t in changes):
        notes.append(tr("grimoire.spells.optimizel.page", "Asks for your password once."))
    whens = {tweaks.BY_ID[t].when for t in changes}
    if "restart" in whens:
        notes.append(tr("grimoire.spells.optimizel.page", "Some finish after a restart."))
    elif "logout" in whens:
        notes.append(tr("grimoire.spells.optimizel.page", "Some finish after you log out."))
    return notes


def _good_line(text: str) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(8)
    icon = QLabel()
    icon.setPixmap(glyph("check", 14).pixmap(14, 14, QIcon.Mode.Normal))
    lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    lay.addWidget(_label(text, "GoodLine", wrap=True), 1)
    return w


def _scan() -> dict:
    """Runs on a worker thread: every tweak's state and live value, plus the already-good checks."""
    saved = tweaks.load_saved()
    out = {}
    for t in tweaks.TWEAKS:
        try:
            state = t.state()
            out[t.id] = {"state": state, "current": t.current(), "goal": t.goal(),
                         "reason": t.reason() if state == "na" else "", "note": tweaks.pending_note(t, saved)}
        except Exception as e:          # one odd setting must never hide the rest
            out[t.id] = {"state": "na", "current": "", "goal": "", "note": "",
                         "reason": tr("grimoire.spells.optimizel.page", "Couldn't read this: {error}").format(error=e)}
    try:
        checks = tweaks.checks()
    except Exception:
        checks = {}
    return {"tweaks": out, "checks": checks}
