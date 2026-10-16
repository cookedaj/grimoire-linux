# SPDX-License-Identifier: GPL-3.0-or-later
"""The phone's text messages: conversations on the left, the open one on the right, a reply box under it.

KDE Connect hands messages over only as signals (the phone sends them after a request), so this panel asks
(requestAllConversationThreads / requestConversation) and fills itself from what listen.py hears. Sending always
asks first: it's a real text from your phone number.
"""
import re

from PySide6.QtCore import QDateTime, QLocale, QSize, Qt, QTimer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, tr
from grimoire.spells.phonel import kdc
from grimoire.spells.phonel.page import lead
from grimoire.spells.phonel.views import _clear, fetch
from grimoire.spells.systeml.page import _label

NUMBER = re.compile(r"^\+?[0-9][0-9 ()./-]{1,30}$")
SENT_QSS = "QFrame#Sent { background: #f2f2f2; border-radius: 12px; } QFrame#Sent QLabel { color: #000000; }"
GOT_QSS = "QFrame#Got { background: #141414; border: 1px solid #262626; border-radius: 12px; }"


def when(ms: int, short: bool = True) -> str:
    """A message's time: the time today, else the date (and time when not short)."""
    dt = QDateTime.fromMSecsSinceEpoch(int(ms))
    loc = QLocale()
    if dt.date() == QDateTime.currentDateTime().date():
        return loc.toString(dt.time(), QLocale.FormatType.ShortFormat)
    if short:
        return loc.toString(dt.date(), QLocale.FormatType.ShortFormat)
    return loc.toString(dt, QLocale.FormatType.ShortFormat)


class Bubble(QFrame):
    def __init__(self, msg: dict, sent: bool):
        super().__init__()
        self.setObjectName("Sent" if sent else "Got")
        self.setStyleSheet(SENT_QSS if sent else GOT_QSS)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 9, 14, 8)
        lay.setSpacing(3)
        body = QLabel(lead(msg["body"]))
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(body)
        t = _label(when(msg["date"], short=False), "Tiny")
        lay.addWidget(t, 0, Qt.AlignmentFlag.AlignTrailing)


class Messages(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.page = view.page
        self.dev = ""
        self.names: dict = {}
        self.latest: dict = {}           # thread → newest message
        self.threads: dict = {}          # thread → {uid or date: message}
        self.loaded: set = set()
        self.current: int | None = None
        self.new = False
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        ll.setSpacing(8)
        top = QHBoxLayout()
        self.new_btn = QPushButton(glyph("plus", 16), tr("grimoire.spells.phonel.sms", "New message"))
        self.new_btn.clicked.connect(self._new)
        top.addWidget(self.new_btn)
        top.addStretch(1)
        ll.addLayout(top)
        self.list = QListWidget()
        self.list.setMinimumWidth(240)
        self.list.currentItemChanged.connect(self._picked)
        ll.addWidget(self.list, 1)
        self.list_note = _label("", "Muted", wrap=True)
        ll.addWidget(self.list_note)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(8)
        self.who = _label("", "SectionTitle")
        self.who.setTextFormat(Qt.TextFormat.PlainText)
        rl.addWidget(self.who)
        self.to = QLineEdit()
        self.to.setPlaceholderText(tr("grimoire.spells.phonel.sms", "To: phone number (several: separate with commas)"))
        self.to.hide()
        rl.addWidget(self.to)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        self.thread_lay = QVBoxLayout(inner)
        self.thread_lay.setContentsMargins(0, 0, 12, 8)
        self.thread_lay.setSpacing(8)
        self.area.setWidget(inner)
        rl.addWidget(self.area, 1)
        compose = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText(tr("grimoire.spells.phonel.sms", "Text message"))
        self.text.setMaxLength(1600)
        self.text.returnPressed.connect(self._send)
        compose.addWidget(self.text, 1)
        self.send_btn = QPushButton(tr("grimoire.spells.phonel.sms", "Send…"))
        self.send_btn.setObjectName("Primary")
        self.send_btn.clicked.connect(self._send)
        compose.addWidget(self.send_btn)
        rl.addLayout(compose)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([300, 600])
        col.addWidget(split, 1)
        self._redraw = QTimer(self, singleShot=True, interval=120, timeout=self._draw_thread)
        self._relist = QTimer(self, singleShot=True, interval=120, timeout=self._draw_list)
        self._show_empty()

    # ------------------------------------------------------------ loading
    def reset(self):
        self.dev = ""
        self.latest, self.threads, self.loaded = {}, {}, set()
        self.current = None
        self.list.clear()
        self._show_empty()

    def showEvent(self, e):
        d = self.view.dev
        if d and d["id"] != self.dev:
            self.reset()
            self.dev = d["id"]
            dev = self.dev
            fetch(self, lambda: (kdc.contacts(dev), kdc.conversations(dev)), self._got)
            fetch(self, lambda: kdc.request_threads(dev), lambda _r: None)
            self.list_note.setText(tr("grimoire.spells.phonel.sms", "Asking the phone for its messages…"))
        super().showEvent(e)

    def _got(self, r):
        if r is None:
            self.list_note.setText(tr("grimoire.spells.phonel.sms", "The phone didn't send its messages. Allow SMS "
                                                                    "access for KDE Connect on the phone."))
            return
        self.names, convs = r
        for m in convs:
            self._take(m)
        self._draw_list()

    def _take(self, m: dict):
        t = m["thread"]
        old = self.latest.get(t)
        if old is None or m["date"] >= old["date"]:
            self.latest[t] = m
        self.threads.setdefault(t, {})[m["uid"] or m["date"]] = m

    def heard(self, member, path, args):
        if member in ("conversationCreated", "conversationUpdated") and args:
            m = kdc.parse_message(args[0])
            if m:
                self._take(m)
                self._relist.start()
                if m["thread"] == self.current:
                    self._redraw.start()
        elif member == "conversationLoaded" and args:
            self.loaded.add(int(args[0]))
            if int(args[0]) == self.current:
                self._redraw.start()
        elif member == "conversationRemoved" and args:
            self.latest.pop(int(args[0]), None)
            self._relist.start()

    # ------------------------------------------------------------ the list
    def title(self, m: dict) -> str:
        """Contact names where the phone shares them, else the numbers (kept left to right)."""
        names = [kdc.contact_name(self.names, a) or (i18n.ltr(a) if NUMBER.match(a) else a) for a in m["addresses"]]
        return ", ".join(names) or tr("grimoire.spells.phonel.sms", "Unknown")

    def _draw_list(self):
        convs = sorted(self.latest.values(), key=lambda m: -m["date"])
        self.list_note.setText("" if convs else tr("grimoire.spells.phonel.sms", "No conversations yet."))
        self.list.blockSignals(True)
        self.list.clear()
        for m in convs:
            unread = not m["read"] and m["type"] == kdc.SMS_INBOX
            preview = " ".join(m["body"].split())[:120]
            if m["type"] == kdc.SMS_SENT:
                preview = tr("grimoire.spells.phonel.sms", "You: {text}").format(text=isolate(preview))
            else:
                preview = lead(preview)
            cell = QWidget()
            lay = QVBoxLayout(cell)
            lay.setContentsMargins(12, 9, 12, 9)
            lay.setSpacing(4)
            top = QHBoxLayout()
            who = QLabel(("• " if unread else "") + lead(self.title(m)))
            who.setTextFormat(Qt.TextFormat.PlainText)
            who.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            who.setObjectName("RowTitle" if unread else "")
            top.addWidget(who, 1)
            top.addWidget(_label(when(m["date"]), "Tiny"))
            lay.addLayout(top)
            sub = _label(preview, "Muted")
            sub.setTextFormat(Qt.TextFormat.PlainText)
            sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            lay.addWidget(sub)
            for lab in (who, sub):
                lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, m["thread"])
            item.setToolTip(", ".join(m["addresses"]))
            cell.ensurePolished()
            item.setSizeHint(cell.sizeHint() + QSize(0, 6))
            self.list.addItem(item)
            self.list.setItemWidget(item, cell)
            if m["thread"] == self.current:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)

    def _picked(self, item, _prev=None):
        if item is None:
            return
        self.new = False
        self.to.hide()
        self.current = int(item.data(Qt.ItemDataRole.UserRole))
        self._draw_thread()
        if self.current not in self.loaded:
            dev, t = self.dev, self.current
            fetch(self, lambda: kdc.request_conversation(dev, t), lambda _r: None)
        self.text.setFocus()

    # ------------------------------------------------------------ the thread
    def _show_empty(self):
        _clear(self.thread_lay)
        self.who.setText(tr("grimoire.spells.phonel.sms", "Pick a conversation"))
        self.text.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.thread_lay.addStretch(1)

    def _draw_thread(self):
        if self.current is None:
            if not self.new:
                self._show_empty()
            return
        m = self.latest.get(self.current)
        self.who.setText(lead(self.title(m)) if m else "")
        self.text.setEnabled(True)
        self.send_btn.setEnabled(True)
        _clear(self.thread_lay)
        self.thread_lay.addStretch(1)
        msgs = sorted(self.threads.get(self.current, {}).values(), key=lambda x: x["date"])
        if self.current not in self.loaded:
            self.thread_lay.addWidget(_label(tr("grimoire.spells.phonel.sms", "Loading the conversation…"), "Tiny"),
                                      0, Qt.AlignmentFlag.AlignHCenter)
        for msg in msgs:
            sent = msg["type"] == kdc.SMS_SENT
            row = QHBoxLayout()
            b = Bubble(msg, sent)
            b.setMaximumWidth(max(260, int(self.area.width() * 0.72)))
            if sent:
                row.addStretch(1)
                row.addWidget(b)
            else:
                row.addWidget(b)
                row.addStretch(1)
            self.thread_lay.addLayout(row)
        QTimer.singleShot(0, lambda: self.area.verticalScrollBar().setValue(self.area.verticalScrollBar().maximum()))

    def _new(self):
        self.new = True
        self.current = None
        self.list.clearSelection()
        self.list.setCurrentItem(None)
        _clear(self.thread_lay)
        self.thread_lay.addStretch(1)
        self.who.setText(tr("grimoire.spells.phonel.sms", "New message"))
        self.to.show()
        self.to.clear()
        self.text.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.to.setFocus()

    # ------------------------------------------------------------ sending
    def _send(self):
        text = self.text.text().strip()
        d = self.view.dev
        if not text or not d:
            return
        if self.new:
            numbers = [n.strip() for n in self.to.text().split(",") if n.strip()]
            if not numbers or not all(NUMBER.match(n) for n in numbers):
                self.page.say(tr("grimoire.spells.phonel.sms", "Type a phone number to send to"))
                self.to.setFocus()
                return
            to = ", ".join(numbers)
        elif self.current is not None and self.current in self.latest:
            to = self.title(self.latest[self.current])
        else:
            return
        if not self.page.ask(tr("grimoire.spells.phonel.sms", "Send text message"),
                             tr("grimoire.spells.phonel.sms",
                                "Send this text message from {phone} to {to}?\n\n{text}\n\nIt goes out from your "
                                "phone's number; your carrier's usual charges apply.").format(
                                 phone=isolate(d["name"]), to=isolate(to), text=isolate(text)),
                             tr("grimoire.spells.phonel.sms", "Send")):
            return
        dev = d["id"]
        self.text.clear()
        if self.new:
            self.page.act(lambda: kdc.send_sms(dev, numbers, text),
                          tr("grimoire.spells.phonel.sms", "Sent to {to}").format(to=isolate(to)),
                          then=lambda: fetch(self, lambda: kdc.request_threads(dev), lambda _r: None))
        else:
            thread = self.current
            self.page.act(lambda: kdc.reply_sms(dev, thread, text),
                          tr("grimoire.spells.phonel.sms", "Sent to {to}").format(to=isolate(to)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.current is not None:
            self._redraw.start()

