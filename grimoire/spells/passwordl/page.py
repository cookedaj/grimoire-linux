# SPDX-License-Identifier: GPL-3.0-or-later
"""PasswordL's page: create or unlock the vault, then items (logins, cards, notes, identities, Wi-Fi, SSH keys,
bank accounts) in folders with search, a detail view that shows secrets only when asked, live two-factor codes,
the generator, the security audit, import/export and settings.

Secrets copied to the clipboard carry KDE's password-manager hint (Klipper keeps them out of its history) and are
cleared after the vault's clipboard_seconds, unless something else was copied since. The vault locks after
lock_minutes without input in this window, when the screen locks (logind's Lock signal isn't ours to hear here, so
also when the window is minimized if lock_on_minimize is on), and with Lock now. Unlocking runs Argon2id on a worker
thread so the window stays responsive.
"""
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.passwordl import crypto, tools, vault


def _label(text="", name="", wrap=True) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)          # titles, usernames and notes are the user's own text
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _nav_names() -> dict:
    return {"all": tr("grimoire.spells.passwordl.page", "All items"),
            "fav": tr("grimoire.spells.passwordl.page", "Favorites"),
            "audit": tr("grimoire.spells.passwordl.page", "Security audit"),
            "generator": tr("grimoire.spells.passwordl.page", "Generator"),
            "trash": tr("grimoire.spells.passwordl.page", "Trash"),
            "settings": tr("grimoire.spells.passwordl.page", "Settings")}


def type_name(kind: str) -> str:
    return tr("grimoire.spells.passwordl.vault", vault.TYPES[kind][0])


def subtitle(r: dict) -> str:
    f = r["fields"]
    if r["type"] == "card":
        n = f.get("number", "")
        return "•••• " + n[-4:] if len(n) >= 4 else type_name("card")
    return f.get("username") or f.get("email") or f.get("ssid") or f.get("bank") or f.get("host") or \
        tools._host(f.get("url", "")) or type_name(r["type"])


class _Signals(QObject):
    unlocked = Signal(object)              # Vault or an error text
    created = Signal(object)
    breaches = Signal(object)


class StrengthBar(QProgressBar):
    def __init__(self):
        super().__init__()
        self.setRange(0, 4)
        self.setTextVisible(True)
        self.setFixedHeight(16)
        self.setObjectName("Strength")

    def show_for(self, pw: str):
        score, word = tools.strength(pw)
        self.setValue(score if pw else 0)
        self.setFormat(word if pw else "")


class PasswordLPage(QWidget):
    def __init__(self, path: Path | None = None):
        super().__init__()
        self.setObjectName("Page")
        self.path = path or vault.FILE
        self.vault: vault.Vault | None = None
        self.current: str | None = None             # selected record id
        self.view = "all"
        self.sig = _Signals()
        self.sig.unlocked.connect(self._unlocked)
        self.sig.created.connect(self._unlocked)
        self.sig.breaches.connect(self._breaches_done)
        self._last_input = time.monotonic()
        self._clip_value: str | None = None
        self.idle = QTimer(self, interval=5000, timeout=self._check_idle)
        self.clip_timer = QTimer(self, singleShot=True, timeout=self._clear_clipboard)
        self.code_timer = QTimer(self, interval=1000, timeout=self._tick_codes)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        self.stack.addWidget(self._gate_page())          # 0: create or unlock
        self.stack.addWidget(self._main_page())          # 1: the vault
        self._show_gate()
        QApplication.instance().installEventFilter(self)

    # ================================================================== create / unlock
    def _gate_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.addStretch(1)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(460)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 26, 28, 24)
        lay.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(glyph("passwordl", 40).pixmap(40, 40))
        icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(icon)
        self.gate_title = _label("", "SectionTitle")
        self.gate_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.gate_title)
        self.gate_text = _label("", "Muted")
        self.gate_text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.gate_text)
        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw1.setPlaceholderText(tr("grimoire.spells.passwordl.page", "Master password"))
        self.pw1.returnPressed.connect(self._gate_go)
        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw2.setPlaceholderText(tr("grimoire.spells.passwordl.page", "Type it again"))
        self.pw2.returnPressed.connect(self._gate_go)
        self.gate_meter = StrengthBar()
        self.pw1.textChanged.connect(self.gate_meter.show_for)
        lay.addWidget(self.pw1)
        lay.addWidget(self.pw2)
        lay.addWidget(self.gate_meter)
        self.gate_msg = _label("", "Muted")
        lay.addWidget(self.gate_msg)
        self.gate_btn = QPushButton()
        self.gate_btn.setObjectName("Primary")
        self.gate_btn.clicked.connect(self._gate_go)
        lay.addWidget(self.gate_btn)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(2)
        return w

    def _show_gate(self):
        new = not vault.exists(self.path)
        self.gate_title.setText(tr("grimoire.spells.passwordl.page", "Create your vault") if new
                                else tr("grimoire.spells.passwordl.page", "PasswordL is locked"))
        self.gate_text.setText(
            tr("grimoire.spells.passwordl.page", "Pick a master password. It encrypts everything on this PC and "
                                                 "can't be recovered if you forget it, so make it long and memorable.")
            if new else tr("grimoire.spells.passwordl.page", "Enter your master password to unlock."))
        self.pw2.setVisible(new)
        self.gate_meter.setVisible(new)
        self.gate_btn.setText(tr("grimoire.spells.passwordl.page", "Create vault") if new
                              else tr("grimoire.spells.passwordl.page", "Unlock"))
        self.gate_msg.setText("")
        self.pw1.clear()
        self.pw2.clear()
        self.stack.setCurrentIndex(0)
        QTimer.singleShot(0, self.pw1.setFocus)

    def _gate_go(self):
        pw = self.pw1.text()
        new = not vault.exists(self.path)
        if new:
            if len(pw) < 10:
                self.gate_msg.setText(tr("grimoire.spells.passwordl.page", "Use at least 10 characters."))
                return
            if pw != self.pw2.text():
                self.gate_msg.setText(tr("grimoire.spells.passwordl.page", "The two passwords don't match."))
                return
        elif not pw:
            return
        self.gate_btn.setEnabled(False)
        self.gate_msg.setText(tr("grimoire.spells.passwordl.page", "Creating…") if new
                              else tr("grimoire.spells.passwordl.page", "Unlocking…"))
        path, sig = self.path, self.sig

        def work():
            try:
                return vault.Vault.create(pw, path) if new else vault.Vault.unlock(pw, path)
            except crypto.BadPassword:
                return tr("grimoire.spells.passwordl.page", "Wrong master password.")
            except crypto.BadFile as e:
                return tr("grimoire.spells.passwordl.page", "The vault file can't be read: {err}").format(err=e)
            except OSError as e:
                return str(e.strerror or e)
        POOL.start(Job(work, (sig.created if new else sig.unlocked).emit))

    def _unlocked(self, result):
        self.gate_btn.setEnabled(True)
        self.pw1.clear()
        self.pw2.clear()
        if isinstance(result, str):
            self.gate_msg.setText(result)
            return
        self.vault = result
        self._last_input = time.monotonic()
        self.idle.start()
        self.code_timer.start()
        self.stack.setCurrentIndex(1)
        self._fill_nav()
        self.go("all")

    def lock(self):
        if not self.vault:
            return
        self.vault.lock()
        self.vault = None
        self.current = None
        self.idle.stop()
        self.code_timer.stop()
        self.list.clear()
        self._clear_detail()
        self._clear_clipboard(force=True)
        self._show_gate()

    # ================================================================== the vault
    def _main_page(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("SubNav")
        side.setFixedWidth(210)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(12, 18, 12, 14)
        sv.setSpacing(4)
        title = _label("PasswordL", "Title")
        sv.addWidget(title)
        sv.addSpacing(8)
        self.nav = QListWidget()
        self.nav.setObjectName("Places")
        self.nav.itemClicked.connect(lambda it: self.go(it.data(Qt.ItemDataRole.UserRole)))
        self.nav.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.nav.customContextMenuRequested.connect(self._nav_menu)
        sv.addWidget(self.nav, 1)
        lock = QPushButton(tr("grimoire.spells.passwordl.page", "Lock now"))
        lock.clicked.connect(self.lock)
        sv.addWidget(lock)
        h.addWidget(side)

        self.body = QStackedWidget()                  # 0: list + detail, 1: generator, 2: audit, 3: settings
        h.addWidget(self.body, 1)
        self.body.addWidget(self._items_view())
        self.body.addWidget(self._generator_view())
        self.body.addWidget(self._audit_view())
        self.body.addWidget(self._settings_view())
        return w

    def _fill_nav(self):
        self.nav.clear()
        names = _nav_names()

        def add(key, text, icon):
            it = QListWidgetItem(glyph(icon, 18), text)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(it)
        add("all", names["all"], "keys")
        add("fav", names["fav"], "star")
        for kind in vault.TYPES:
            add("type:" + kind, type_name(kind), "document")
        for f in self.vault.folders:
            add("folder:" + f, f, "folder")
        add("audit", names["audit"], "shield")
        add("generator", names["generator"], "dice")
        add("trash", names["trash"], "trash")
        add("settings", names["settings"], "gear")
        self._mark_nav()

    def _mark_nav(self):
        for i in range(self.nav.count()):
            it = self.nav.item(i)
            it.setSelected(it.data(Qt.ItemDataRole.UserRole) == self.view)

    def _nav_menu(self, pos):
        it = self.nav.itemAt(pos)
        m = QMenu(self)
        m.addAction(tr("grimoire.spells.passwordl.page", "New folder…"), self._new_folder)
        key = it.data(Qt.ItemDataRole.UserRole) if it else ""
        if key.startswith("folder:"):
            m.addAction(tr("grimoire.spells.passwordl.page", "Remove folder (items stay)"),
                        lambda: (self.vault.remove_folder(key[7:]), self._fill_nav(), self.go("all")))
        m.exec(self.nav.viewport().mapToGlobal(pos))

    def _new_folder(self):
        name, ok = QInputDialog.getText(self, tr("grimoire.spells.passwordl.page", "New folder"),
                                        tr("grimoire.spells.passwordl.page", "Name"))
        if ok and name.strip():
            self.vault.add_folder(name)
            self._fill_nav()

    def go(self, key: str):
        self.view = key
        self._mark_nav()
        pages = {"generator": 1, "audit": 2, "settings": 3}
        self.body.setCurrentIndex(pages.get(key, 0))
        if key == "audit":
            self._run_audit()
        elif key == "settings":
            self._fill_settings()
        elif key not in pages:
            self._fill_list()

    # ------------------------------------------------------------ list + detail
    def _items_view(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(18, 16, 18, 12)
        h.setSpacing(14)
        left = QVBoxLayout()
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.passwordl.page", "Search (Ctrl+F)"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._fill_list())
        top.addWidget(self.search, 1)
        new = QToolButton()
        new.setText(tr("grimoire.spells.passwordl.page", "New"))
        new.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(new)
        for kind in vault.TYPES:
            menu.addAction(type_name(kind), lambda k=kind: self._new(k))
        new.setMenu(menu)
        top.addWidget(new)
        left.addLayout(top)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(lambda it, _p: self._show(it.data(Qt.ItemDataRole.UserRole) if it
                                                                        else None))
        left.addWidget(self.list, 1)
        self.count = _label("", "Muted", wrap=False)
        left.addWidget(self.count)
        lw = QWidget()
        lw.setLayout(left)
        lw.setMinimumWidth(280)
        lw.setMaximumWidth(380)
        h.addWidget(lw)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail = QWidget()
        self.detail_lay = QVBoxLayout(self.detail)
        self.detail_lay.setContentsMargins(4, 4, 4, 4)
        self.detail_scroll.setWidget(self.detail)
        h.addWidget(self.detail_scroll, 1)
        return w

    def _records(self) -> list[dict]:
        v = self.vault
        if self.view == "trash":
            recs = [r for r in v.records.values() if r["deleted"]]
        else:
            recs = v.live()
            if self.view == "fav":
                recs = [r for r in recs if r["fav"]]
            elif self.view.startswith("type:"):
                recs = [r for r in recs if r["type"] == self.view[5:]]
            elif self.view.startswith("folder:"):
                recs = [r for r in recs if r["folder"] == self.view[7:]]
        text = self.search.text().strip()
        if text:
            recs = v.search(text, recs)
        return sorted(recs, key=lambda r: (not r["fav"], r["title"].lower()))

    def _fill_list(self):
        if not self.vault:
            return
        keep = self.current
        self.list.blockSignals(True)
        self.list.clear()
        for r in self._records():
            it = QListWidgetItem(("★ " if r["fav"] else "") + f"{r['title']}\n{subtitle(r)}")
            it.setData(Qt.ItemDataRole.UserRole, r["id"])
            it.setSizeHint(QSize(0, 2 * self.list.fontMetrics().height() + 18))   # both lines, also when selected
            self.list.addItem(it)
            if r["id"] == keep:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        self.count.setText(tr("grimoire.spells.passwordl.page", "%n item(s)", n=self.list.count()))
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        elif not self.list.count():
            self._show(None)
        else:
            self._show(keep)

    def _clear_detail(self):
        self._codes = []
        while self.detail_lay.count():
            item = self.detail_lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()                                  # gone now, not at the next event loop pass
                w.deleteLater()
            elif item.layout():
                _drop_layout(item.layout())

    def _show(self, rid: str | None):
        self._clear_detail()
        self.current = rid
        r = self.vault.records.get(rid) if self.vault and rid else None
        if not r:
            self.detail_lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Nothing selected. Make a new "
                                                "item with New, or import from another password manager in "
                                                "Settings."), "Muted"))
            self.detail_lay.addStretch(1)
            return
        head = QHBoxLayout()
        head.addWidget(_label(r["title"] or "—", "PageHeading"), 1)
        if r["deleted"]:
            for text, fn in ((tr("grimoire.spells.passwordl.page", "Restore"), lambda: self._restore(rid)),
                             (tr("grimoire.spells.passwordl.page", "Delete forever…"), lambda: self._purge(rid))):
                b = QPushButton(text)
                b.clicked.connect(fn)
                head.addWidget(b)
        else:
            fav = QPushButton(tr("grimoire.spells.passwordl.page", "Unfavorite") if r["fav"]
                              else tr("grimoire.spells.passwordl.page", "Favorite"))
            fav.clicked.connect(lambda: self._save(rid, fav=not r["fav"]))
            edit = QPushButton(tr("grimoire.spells.passwordl.page", "Edit"))
            edit.setObjectName("Primary")
            edit.clicked.connect(lambda: self._edit(rid))
            head.addWidget(fav)
            head.addWidget(edit)
        self.detail_lay.addLayout(head)
        meta = [type_name(r["type"])] + ([r["folder"]] if r["folder"] else []) + r["tags"]
        self.detail_lay.addWidget(_label("  ·  ".join(meta), "Muted"))
        for name, label, secret, multiline in vault.fields_of(r["type"]):
            value = r["fields"].get(name, "")
            if value:
                self._field_row(tr("grimoire.spells.passwordl.vault", label), value, secret, multiline,
                                name=name, kind=r["type"])
        for c in r["custom"]:
            if c["value"]:
                self._field_row(c["name"] or "—", c["value"], c["secret"], "\n" in c["value"])
        if r["history"]:
            self.detail_lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Password history"), "NavSection"))
            for h in reversed(r["history"]):
                self._field_row(time.strftime("%Y-%m-%d", time.localtime(h["changed"])), h["password"], True, False)
        self.detail_lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Changed {when}").format(
            when=time.strftime("%Y-%m-%d %H:%M", time.localtime(r["modified"]))), "Muted"))
        self.detail_lay.addStretch(1)

    def _field_row(self, label: str, value: str, secret: bool, multiline: bool, name: str = "", kind: str = ""):
        box = QFrame()
        box.setObjectName("Card")
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(4)
        v.addWidget(_label(label, "Muted"))
        row = QHBoxLayout()
        is_totp = name == "totp"
        shown = _label("", "RowTitle", wrap=multiline)
        shown.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if not is_totp:
            shown.setText("••••••••••" if secret else value)
        row.addWidget(shown, 1)
        if is_totp:
            self._codes.append((shown, value))
            self._tick_codes()
        elif secret:
            eye = QToolButton()
            eye.setIcon(glyph("hidden", 16))
            eye.setCheckable(True)
            eye.setToolTip(tr("grimoire.spells.passwordl.page", "Show"))
            eye.toggled.connect(lambda on, s=shown, val=value: s.setText(val if on else "••••••••••"))
            row.addWidget(eye)
        if name == "url" and value:
            go = QToolButton()
            go.setText(tr("grimoire.spells.passwordl.page", "Open"))
            go.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(value if "://" in value else "https://" + value)))
            row.addWidget(go)
        copy = QToolButton()
        copy.setIcon(glyph("copies", 16))
        copy.setToolTip(tr("grimoire.spells.passwordl.page", "Copy"))
        copy.clicked.connect(lambda: self.copy((tools.totp_code(value) or ("",))[0] if is_totp else value,
                                               secret or is_totp))
        row.addWidget(copy)
        v.addLayout(row)
        self.detail_lay.addWidget(box)

    def _tick_codes(self):
        for lab, secret in getattr(self, "_codes", []):
            try:
                got = tools.totp_code(secret)
            except RuntimeError:
                return                                   # the label went with a redraw
            lab.setText(f"{got[0][:3]} {got[0][3:]}   ·   {got[1]}s" if got
                        else tr("grimoire.spells.passwordl.page", "Not a valid two-factor key"))

    # ------------------------------------------------------------ editing
    def _new(self, kind: str):
        folder = self.view[7:] if self.view.startswith("folder:") else ""
        self._edit(None, kind, folder)

    def _edit(self, rid: str | None, kind: str = "login", folder: str = ""):
        self._clear_detail()
        r = self.vault.records.get(rid) if rid else None
        kind = r["type"] if r else kind
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        title = QLineEdit(r["title"] if r else "")
        title.setPlaceholderText(type_name(kind))
        form.addRow(tr("grimoire.spells.passwordl.page", "Title"), title)
        folder_box = QComboBox()
        folder_box.setEditable(True)
        folder_box.addItems(["", *self.vault.folders])
        folder_box.setCurrentText(r["folder"] if r else folder)
        form.addRow(tr("grimoire.spells.passwordl.page", "Folder"), folder_box)
        tags = QLineEdit(", ".join(r["tags"]) if r else "")
        tags.setPlaceholderText(tr("grimoire.spells.passwordl.page", "work, shared, bank…"))
        form.addRow(tr("grimoire.spells.passwordl.page", "Tags"), tags)
        edits = {}
        for name, label, secret, multiline in vault.fields_of(kind):
            value = r["fields"].get(name, "") if r else ""
            if multiline:
                e = QPlainTextEdit(value)
                e.setFixedHeight(90)
            else:
                e = QLineEdit(value)
                if secret:
                    e.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
            edits[name] = e
            if name == "password":
                row = QHBoxLayout()
                row.addWidget(e, 1)
                gen = QToolButton()
                gen.setText(tr("grimoire.spells.passwordl.page", "Generate"))
                gen.clicked.connect(lambda _=False, e=e: (e.setEchoMode(QLineEdit.EchoMode.Normal),
                                                          e.setText(self._generate())))
                row.addWidget(gen)
                meter = StrengthBar()
                e.textChanged.connect(meter.show_for)
                meter.show_for(value)
                col = QVBoxLayout()
                col.addLayout(row)
                col.addWidget(meter)
                holder = QWidget()
                holder.setLayout(col)
                col.setContentsMargins(0, 0, 0, 0)
                form.addRow(tr("grimoire.spells.passwordl.vault", label), holder)
            else:
                if name == "totp":
                    e.setPlaceholderText(tr("grimoire.spells.passwordl.page", "The setup key or otpauth:// link"))
                form.addRow(tr("grimoire.spells.passwordl.vault", label), e)
        custom = QPlainTextEdit("\n".join(f"{c['name']}{' (secret)' if c['secret'] else ''}: {c['value']}"
                                          for c in (r["custom"] if r else [])))
        custom.setPlaceholderText(tr("grimoire.spells.passwordl.page", "One per line, as Name: value. Add "
                                     "(secret) after the name to hide the value."))
        custom.setFixedHeight(70)
        form.addRow(tr("grimoire.spells.passwordl.page", "More fields"), custom)
        holder = QWidget()
        holder.setLayout(form)
        self.detail_lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Edit {kind}").format(
            kind=type_name(kind)) if r else tr("grimoire.spells.passwordl.page", "New {kind}").format(
            kind=type_name(kind)), "PageHeading"))
        self.detail_lay.addWidget(holder)
        btns = QHBoxLayout()
        if r:
            trash = QPushButton(tr("grimoire.spells.passwordl.page", "Move to Trash"))
            trash.clicked.connect(lambda: (self.vault.trash(rid), self._fill_list()))
            btns.addWidget(trash)
        btns.addStretch(1)
        cancel = QPushButton(tr("grimoire.spells.passwordl.page", "Cancel"))
        cancel.clicked.connect(lambda: self._show(rid) if rid else self._fill_list())
        save = QPushButton(tr("grimoire.spells.passwordl.page", "Save"))
        save.setObjectName("Primary")

        def do_save():
            fields = {n: (e.toPlainText() if isinstance(e, QPlainTextEdit) else e.text()) for n, e in edits.items()}
            if fields.get("totp") and not tools.parse_totp(fields["totp"]):
                QMessageBox.warning(self, "PasswordL", tr("grimoire.spells.passwordl.page",
                                                          "That two-factor key isn't valid."))
                return
            values = dict(title=title.text().strip() or type_name(kind), folder=folder_box.currentText().strip(),
                          tags=[t.strip() for t in tags.text().split(",") if t.strip()], fields=fields,
                          custom=_parse_custom(custom.toPlainText()))
            if r:
                self.vault.update(rid, **values)
                self.current = rid
            else:
                self.current = self.vault.add(kind, **values)["id"]
            self._fill_nav()
            self._fill_list()
        save.clicked.connect(do_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        self.detail_lay.addLayout(btns)
        self.detail_lay.addStretch(1)
        title.setFocus()

    def _save(self, rid, **changes):
        self.vault.update(rid, **changes)
        self._fill_list()

    def _restore(self, rid):
        self.vault.restore(rid)
        self._fill_list()

    def _purge(self, rid):
        if QMessageBox.warning(self, "PasswordL", tr("grimoire.spells.passwordl.page", "Delete this item for good? "
                                                     "It can't be brought back."),
                               QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                               QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Yes:
            self.vault.delete_forever(rid)
            self._fill_list()

    # ------------------------------------------------------------ generator
    def _generator_view(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 26, 32, 18)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Generator"), "PageHeading"))
        self.gen_out = QLineEdit()
        self.gen_out.setReadOnly(True)
        self.gen_out.setObjectName("Mono")
        self.gen_out.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.gen_meter = StrengthBar()
        row = QHBoxLayout()
        row.addWidget(self.gen_out, 1)
        again = QPushButton(tr("grimoire.spells.passwordl.page", "New one"))
        again.clicked.connect(lambda: self._show_generated())
        copy = QPushButton(tr("grimoire.spells.passwordl.page", "Copy"))
        copy.setObjectName("Primary")
        copy.clicked.connect(lambda: self.copy(self.gen_out.text(), True))
        row.addWidget(again)
        row.addWidget(copy)
        lay.addLayout(row)
        lay.addWidget(self.gen_meter)
        self.gen_mode = QComboBox()
        self.gen_mode.addItem(tr("grimoire.spells.passwordl.page", "Random characters"), "chars")
        self.gen_mode.addItem(tr("grimoire.spells.passwordl.page", "Words (easier to type)"), "words")
        self.gen_len = QSlider(Qt.Orientation.Horizontal)
        self.gen_len.setRange(8, 64)
        self.gen_len.setValue(20)
        self.gen_words = QSpinBox()
        self.gen_words.setRange(3, 12)
        self.gen_words.setValue(5)
        self.gen_opts = {k: QCheckBox(t) for k, t in (
            ("upper", tr("grimoire.spells.passwordl.page", "A–Z")), ("lower", tr("grimoire.spells.passwordl.page",
                                                                                  "a–z")),
            ("digits", tr("grimoire.spells.passwordl.page", "0–9")), ("symbols", tr("grimoire.spells.passwordl.page",
                                                                                     "Symbols")),
            ("no_lookalikes", tr("grimoire.spells.passwordl.page", "No look-alikes (Il1O0)")))}
        for k, cb in self.gen_opts.items():
            cb.setChecked(k != "no_lookalikes")
            cb.toggled.connect(lambda _on: self._show_generated())
        form = QFormLayout()
        form.addRow(tr("grimoire.spells.passwordl.page", "Kind"), self.gen_mode)
        self.len_label = _label("", "Muted", wrap=False)
        lrow = QHBoxLayout()
        lrow.addWidget(self.gen_len, 1)
        lrow.addWidget(self.len_label)
        form.addRow(tr("grimoire.spells.passwordl.page", "Length"), lrow)
        form.addRow(tr("grimoire.spells.passwordl.page", "Words"), self.gen_words)
        opts = QHBoxLayout()
        for cb in self.gen_opts.values():
            opts.addWidget(cb)
        opts.addStretch(1)
        form.addRow(tr("grimoire.spells.passwordl.page", "Use"), opts)
        lay.addLayout(form)
        lay.addStretch(1)
        self.gen_mode.currentIndexChanged.connect(lambda _i: self._show_generated())
        self.gen_len.valueChanged.connect(lambda _v: self._show_generated())
        self.gen_words.valueChanged.connect(lambda _v: self._show_generated())
        self._show_generated()
        return w

    def _generate(self) -> str:
        if self.gen_mode.currentData() == "words":
            return tools.passphrase(self.gen_words.value())
        o = {k: cb.isChecked() for k, cb in self.gen_opts.items()}
        return tools.password(self.gen_len.value(), **o)

    def _show_generated(self):
        words = self.gen_mode.currentData() == "words"
        self.gen_len.setEnabled(not words)
        self.gen_words.setEnabled(words)
        for cb in self.gen_opts.values():
            cb.setEnabled(not words)
        self.len_label.setText(str(self.gen_len.value()))
        pw = self._generate()
        self.gen_out.setText(pw)
        self.gen_meter.show_for(pw)

    # ------------------------------------------------------------ audit
    def _audit_view(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 26, 32, 18)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Security audit"), "PageHeading"))
        self.audit_score = _label("", "Hero", wrap=False)
        lay.addWidget(self.audit_score)
        self.audit_list = QListWidget()
        self.audit_list.itemActivated.connect(self._audit_open)
        self.audit_list.itemClicked.connect(self._audit_open)
        lay.addWidget(self.audit_list, 1)
        brow = QHBoxLayout()
        self.breach_note = _label(tr("grimoire.spells.passwordl.page", "Breach check (optional): asks Have I Been "
                                     "Pwned whether your passwords appear in known leaks. Only the first 5 "
                                     "characters of each password's SHA-1 hash leave this PC; never a password, "
                                     "a name or a site."), "Muted")
        brow.addWidget(self.breach_note, 1)
        self.breach_btn = QPushButton(tr("grimoire.spells.passwordl.page", "Check for breaches"))
        self.breach_btn.clicked.connect(self._check_breaches)
        brow.addWidget(self.breach_btn)
        lay.addLayout(brow)
        self._breached: dict = {}
        return w

    def _run_audit(self):
        a = tools.audit(self.vault.live())
        self.audit_score.setText(tr("grimoire.spells.passwordl.page", "Score {score}/100").format(score=a["score"])
                                 if a["total"] else tr("grimoire.spells.passwordl.page", "No passwords yet"))
        self.audit_list.clear()

        def section(title, recs, why):
            if not recs:
                return
            head = QListWidgetItem(f"{title} · {len(recs)}")
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            self.audit_list.addItem(head)
            for r in recs:
                it = QListWidgetItem(f"    {r['title']}  —  {why(r)}")
                it.setData(Qt.ItemDataRole.UserRole, r["id"])
                self.audit_list.addItem(it)
        live = self.vault.live()
        pw_of = {r["id"]: r["fields"].get("password", "") for r in live}
        section(tr("grimoire.spells.passwordl.page", "Found in breaches"),
                [r for r in live if pw_of[r["id"]] in self._breached],
                lambda r: tr("grimoire.spells.passwordl.page", "seen {n} times").format(
                    n=self._breached[pw_of[r["id"]]]))
        section(tr("grimoire.spells.passwordl.page", "Weak"), a["weak"],
                lambda r: tools.strength(r["fields"]["password"])[1])
        section(tr("grimoire.spells.passwordl.page", "Reused"), [r for g in a["reused"] for r in g],
                lambda r: tr("grimoire.spells.passwordl.page", "same password as another item"))
        section(tr("grimoire.spells.passwordl.page", "Older than a year"), a["old"],
                lambda r: tr("grimoire.spells.passwordl.page", "time for a new one"))
        section(tr("grimoire.spells.passwordl.page", "No two-factor code saved"), a["no2fa"],
                lambda r: tools._host(r["fields"].get("url", "")))

    def _audit_open(self, it):
        rid = it.data(Qt.ItemDataRole.UserRole)
        if rid:
            self.go("all")
            self.current = rid
            self._fill_list()

    def _check_breaches(self):
        pws = [r["fields"]["password"] for r in self.vault.live() if r["fields"].get("password")]
        if not pws:
            return
        self.breach_btn.setEnabled(False)
        self.breach_btn.setText(tr("grimoire.spells.passwordl.page", "Checking…"))
        sig = self.sig

        def work():
            try:
                return tools.breached(pws)
            except OSError as e:
                return str(e)
        POOL.start(Job(work, sig.breaches.emit))

    def _breaches_done(self, result):
        self.breach_btn.setEnabled(True)
        self.breach_btn.setText(tr("grimoire.spells.passwordl.page", "Check for breaches"))
        if isinstance(result, str):
            self.breach_note.setText(tr("grimoire.spells.passwordl.page", "Couldn't reach the breach service: "
                                        "{err}").format(err=result))
            return
        self._breached = result
        if self.vault:
            self._run_audit()

    # ------------------------------------------------------------ settings, import, export
    def _settings_view(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 26, 32, 18)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Settings"), "PageHeading"))
        form = QFormLayout()
        self.set_lock = QSpinBox()
        self.set_lock.setRange(1, 240)
        self.set_lock.setSuffix(tr("grimoire.spells.passwordl.page", " min"))
        self.set_clip = QSpinBox()
        self.set_clip.setRange(5, 300)
        self.set_clip.setSuffix(tr("grimoire.spells.passwordl.page", " s"))
        self.set_min = QCheckBox(tr("grimoire.spells.passwordl.page", "Lock when the window is minimized"))
        form.addRow(tr("grimoire.spells.passwordl.page", "Lock after no use for"), self.set_lock)
        form.addRow(tr("grimoire.spells.passwordl.page", "Clear copied secrets after"), self.set_clip)
        form.addRow("", self.set_min)
        lay.addLayout(form)
        for wdg in (self.set_lock, self.set_clip):
            wdg.valueChanged.connect(lambda _v: self._store_settings())
        self.set_min.toggled.connect(lambda _on: self._store_settings())
        row = QHBoxLayout()
        for text, fn in ((tr("grimoire.spells.passwordl.page", "Change master password…"), self._change_password),
                         (tr("grimoire.spells.passwordl.page", "Import…"), self._import),
                         (tr("grimoire.spells.passwordl.page", "Export encrypted copy…"), self._export)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_label(tr("grimoire.spells.passwordl.page", "Import reads CSV exports from Chrome, Edge, "
                                "Brave, Firefox, Bitwarden, Keeper, KeePassXC, LastPass and 1Password, and "
                                "unencrypted JSON from Bitwarden and Keeper. Delete the export file afterwards: it "
                                "holds your passwords in plain text."), "Muted"))
        self.vault_where = _label("", "Muted")
        lay.addWidget(self.vault_where)
        lay.addStretch(1)
        return w

    def _fill_settings(self):
        s = self.vault.settings
        for wdg, val in ((self.set_lock, s["lock_minutes"]), (self.set_clip, s["clipboard_seconds"])):
            wdg.blockSignals(True)
            wdg.setValue(val)
            wdg.blockSignals(False)
        self.set_min.blockSignals(True)
        self.set_min.setChecked(s["lock_on_minimize"])
        self.set_min.blockSignals(False)
        self.vault_where.setText(tr("grimoire.spells.passwordl.page", "Vault file: {path} (encrypted with "
                                    "Argon2id + ChaCha20-Poly1305; the last 5 sealed copies are kept next to it)")
                                 .format(path=i18n.ltr(str(self.path))))

    def _store_settings(self):
        if self.vault:
            self.vault.set(lock_minutes=self.set_lock.value(), clipboard_seconds=self.set_clip.value(),
                           lock_on_minimize=self.set_min.isChecked())

    def _ask_password(self, title: str, twice: bool) -> str | None:
        pw, ok = QInputDialog.getText(self, title, tr("grimoire.spells.passwordl.page", "Password"),
                                      QLineEdit.EchoMode.Password)
        if not ok or not pw:
            return None
        if twice:
            again, ok = QInputDialog.getText(self, title, tr("grimoire.spells.passwordl.page", "Type it again"),
                                             QLineEdit.EchoMode.Password)
            if not ok or again != pw:
                QMessageBox.warning(self, "PasswordL", tr("grimoire.spells.passwordl.page",
                                                          "The two passwords don't match."))
                return None
        if len(pw) < 10:
            QMessageBox.warning(self, "PasswordL", tr("grimoire.spells.passwordl.page", "Use at least 10 characters."))
            return None
        return pw

    def _change_password(self):
        old, ok = QInputDialog.getText(self, "PasswordL", tr("grimoire.spells.passwordl.page", "Current master "
                                                                                                 "password"),
                                       QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            vault.Vault.unlock(old, self.path).lock()
        except (crypto.BadPassword, crypto.BadFile, OSError):
            QMessageBox.warning(self, "PasswordL", tr("grimoire.spells.passwordl.page", "Wrong master password."))
            return
        new = self._ask_password(tr("grimoire.spells.passwordl.page", "New master password"), True)
        if new:
            self.vault.change_password(new)
            QMessageBox.information(self, "PasswordL", tr("grimoire.spells.passwordl.page",
                                                          "Master password changed."))

    def _import(self):
        path, _f = QFileDialog.getOpenFileName(self, tr("grimoire.spells.passwordl.page", "Import passwords"),
                                               str(Path.home()), "CSV / JSON (*.csv *.json)")
        if not path:
            return
        try:
            kind, recs = tools.read_import(Path(path))
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "PasswordL", str(e))
            return
        if QMessageBox.question(self, "PasswordL", tr("grimoire.spells.passwordl.page", "Import %n item(s) from "
                                                      "{kind}?", n=len(recs)).format(kind=kind)) \
                != QMessageBox.StandardButton.Yes:
            return
        self.vault.add_many(recs)
        self._fill_nav()
        self.go("all")
        QMessageBox.information(self, "PasswordL", tr("grimoire.spells.passwordl.page", "Imported %n item(s). "
                                                      "Now delete the export file: it isn't encrypted.",
                                                      n=len(recs)))

    def _export(self):
        path, _f = QFileDialog.getSaveFileName(self, tr("grimoire.spells.passwordl.page", "Export encrypted copy"),
                                               str(Path.home() / "passwords.pwl"), "PasswordL (*.pwl)")
        if not path:
            return
        pw = self._ask_password(tr("grimoire.spells.passwordl.page", "A password for the copy"), True)
        if pw:
            self.vault.export_to(Path(path), pw)
            QMessageBox.information(self, "PasswordL", tr("grimoire.spells.passwordl.page", "Saved. Open it with "
                                                          "PasswordL using that password."))

    # ================================================================== clipboard, idle lock
    def copy(self, text: str, secret: bool):
        if not text:
            return
        data = QMimeData()
        data.setText(text)
        if secret:
            data.setData("x-kde-passwordManagerHint", b"secret")    # Klipper keeps it out of the history
        QGuiApplication.clipboard().setMimeData(data)
        if secret and self.vault:
            self._clip_value = text
            self.clip_timer.start(self.vault.settings["clipboard_seconds"] * 1000)

    def _clear_clipboard(self, force=False):
        cb = QGuiApplication.clipboard()
        if self._clip_value is not None and (force or cb.text() == self._clip_value):
            if cb.text() == self._clip_value:
                cb.clear()
        self._clip_value = None

    def eventFilter(self, obj, e):
        t = e.type()
        if t in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
            if isinstance(obj, QWidget) and obj.window() is self.window():
                self._last_input = time.monotonic()
        elif t == QEvent.Type.WindowStateChange and obj is self.window() and self.vault \
                and self.vault.settings["lock_on_minimize"] and self.window().isMinimized():
            QTimer.singleShot(0, self.lock)
        return False

    def _check_idle(self):
        if self.vault and time.monotonic() - self._last_input > self.vault.settings["lock_minutes"] * 60:
            self.lock()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F and e.modifiers() & Qt.KeyboardModifier.ControlModifier and self.vault:
            if self.body.currentIndex() != 0:
                self.go("all")
            self.search.setFocus()
            self.search.selectAll()
            return
        super().keyPressEvent(e)


def _parse_custom(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        name, sep, value = line.partition(":")
        if not sep:
            continue
        name = name.strip()
        secret = name.endswith("(secret)")
        out.append({"name": name.removesuffix("(secret)").strip(), "value": value.strip(), "secret": secret})
    return out


def _drop_layout(lay):
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            _drop_layout(item.layout())
