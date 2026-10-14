# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings → Share setup: save your look as a .grimoire-setup file or a short code, and preview + import one.

The work is in sharesetup.py; this file lays it out and runs everything slow off the UI thread. Every bit of text
from a shared file (title, author, names) goes into plain-text labels only, never rich text.
"""
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QImageReader, QPixmap
from PySide6.QtWidgets import QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from grimoire.i18n import tr
from grimoire.settingsview import Row, _button, _label, _scroll, _size, _when, run

PREVIEW = QSize(480, 270)


def _png(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def _preview_png() -> bytes:
    """The look as MuraL's saved looks draw it (worker-thread safe). Empty if it can't be drawn."""
    try:
        from grimoire.spells.mural import looks
        return _png(looks.render_thumb(looks.capture()))
    except Exception:                       # a preview is a nicety; never stop a share over it
        return b""


def _image(data: bytes) -> QImage:
    """An untrusted PNG, read with a size check before it is decoded."""
    if not data:
        return QImage()
    buf = QBuffer()
    buf.setData(QByteArray(data))
    buf.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buf, b"png")
    size = reader.size()
    if not size.isValid() or size.width() > 4096 or size.height() > 4096:
        return QImage()
    return reader.read()


def _summary(setup: dict) -> str:
    """What a setup holds, in one line."""
    bits = []
    m = setup.get("mural") or {}
    if m:
        pics = len((m.get("desktop") or {}).get("items", []))
        bits.append(tr("grimoire.shareview", "MuraL: %n screen(s) and {wallpapers}", n=len(m.get("tabs", {}))).format(
            wallpapers=tr("grimoire.shareview", "%n wallpaper(s)", n=pics)))
    if setup.get("store"):
        bits.append(tr("grimoire.shareview", "%n community item(s) by store link", n=len(setup["store"])))
    s = setup.get("sightc") or {}
    if s:
        bits.append(tr("grimoire.shareview", "SightsL: crosshair and %n profile(s)", n=len(s.get("profiles", {}))))
    if setup.get("terminall"):
        bits.append(tr("grimoire.shareview", "TerminalL: %n profile(s)", n=len(setup["terminall"]["profiles"])))
    if setup.get("launchl"):
        bits.append(tr("grimoire.shareview", "LaunchL: %n favorite(s) in order", n=len(setup["launchl"]["favorites"])))
    if setup.get("tray"):
        bits.append(tr("grimoire.shareview", "the tray meter"))
    return " · ".join(bits) or tr("grimoire.shareview", "Nothing yet.")


# ---------------------------------------------------------------- the preview dialog
class SetupPreview(QDialog):
    """What a shared setup would change (current → new, per spell), store links, then Import and Apply now."""

    def __init__(self, shared, parent=None):
        from grimoire import sharesetup
        super().__init__(parent)
        self.setObjectName("WhatsNew")
        self.setWindowTitle(tr("grimoire.shareview", "Import a setup"))
        self.resize(700, 760)
        self.shared, self.result = shared, None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(6)
        lay.addWidget(_label(shared.title, "PageHeading"))
        meta = []
        if shared.author:
            meta.append(tr("grimoire.shareview", "by {author}").format(author=shared.author))
        if _when(shared.created):
            meta.append(tr("grimoire.shareview", "made {when}").format(when=_when(shared.created)))
        if shared.app_version:
            meta.append(tr("grimoire.shareview", "Grimoire v{version}").format(version=shared.app_version))
        if shared.source is None:
            meta.append(tr("grimoire.shareview", "from a share code"))
        lay.addWidget(_label(" · ".join(meta), "Muted"))
        lay.addSpacing(6)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 8, 0)
        bl.setSpacing(4)
        img = _image(shared.preview)
        if not img.isNull():
            pic = QLabel()
            pic.setPixmap(QPixmap.fromImage(img.scaled(PREVIEW, Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)))
            bl.addWidget(pic, 0, Qt.AlignmentFlag.AlignLeft)
            bl.addSpacing(8)
        self.ticks = {}
        for spell, rows in sharesetup.changes(shared).items():
            box = QCheckBox(tr("grimoire.sharesetup", sharesetup.SPELL_NAMES[spell]))
            box.setObjectName("RowTitle")
            box.setChecked(True)
            box.toggled.connect(self._sync)
            self.ticks[spell] = box
            bl.addSpacing(8)
            bl.addWidget(box)
            for c in rows:
                bl.addWidget(self._line(c))
        self.missing = sharesetup.missing_store(shared)
        if self.missing:
            bl.addSpacing(14)
            bl.addWidget(_label(tr("grimoire.shareview", "FROM THE COMMUNITY STORE"), "Section"))
            bl.addWidget(_label(tr("grimoire.shareview",
                                   "This setup uses these community themes and wallpapers. They aren't inside the "
                                   "file: Grimoire downloads each one from the store only when you click its button."),
                                "Muted"))
            for ref in self.missing:
                bl.addWidget(self._store_row(ref))
        notes = []
        pics = sharesetup.missing_pictures(shared)
        if pics:
            notes.append(tr("grimoire.shareview", "%n wallpaper(s) aren't included and aren't in your library: "
                            "{names}. Those parts are left out when you apply the look.", n=len(pics)).format(
                names=", ".join(pics[:6])))
        if shared.ignored:
            notes.append(tr("grimoire.shareview", "%n unknown file(s) in the setup were ignored.",
                            n=len(shared.ignored)))
        for n in notes:
            bl.addSpacing(8)
            bl.addWidget(_label(n, "Muted"))
        bl.addStretch(1)
        lay.addWidget(_scroll(body), 1)

        self.message = _label(tr("grimoire.shareview",
                                 "A safety backup of your current settings is saved first. Importing changes "
                                 "no screen: the MuraL look is saved under MuraL → Looks, and you choose whether "
                                 "to apply it now."),
                              "Status")
        lay.addWidget(self.message)
        self.root = QCheckBox(tr("grimoire.shareview", "Include the login and boot screens (asks for your password)"))
        self.root.hide()
        lay.addWidget(self.root)
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel = _button(tr("grimoire.shareview", "Cancel"), self.reject)
        row.addWidget(self.cancel)
        self.go = _button(tr("grimoire.shareview", "Import"), self._import, "Primary")
        row.addWidget(self.go)
        self.now = _button(tr("grimoire.shareview", "Apply the look now"), self._apply_now, "Primary",
                           tip=tr("grimoire.shareview", "Changes your desktop: wallpaper, taskbar, colors, windows…"))
        self.now.hide()
        row.addWidget(self.now)
        lay.addLayout(row)
        self._sync()

    @staticmethod
    def _line(change):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 3, 0, 3)
        h.setSpacing(10)
        label = _label(change.label, "Muted")              # wraps: "<tab> options" runs long in some languages
        label.setFixedWidth(150)
        h.addWidget(label)
        now = _label(change.now, "Muted")
        h.addWidget(now, 1)
        h.addWidget(_label("←" if w.isRightToLeft() else "→", "Muted", wrap=False))   # points from now to new
        new = _label(change.new, "Muted" if change.same else "RowTitle")
        h.addWidget(new, 1)
        if change.same:
            h.addWidget(_label(tr("grimoire.shareview", "SAME"), "Badge", wrap=False))
        return w

    def _store_row(self, ref):
        from grimoire import sharesetup
        b = _button(tr("grimoire.shareview", "Get from store"), lambda: get())
        row = Row(ref["name"], tr("grimoire.shareview", "{kind} · by {author}").format(
            kind=ref["kind"], author=ref["author"] or tr("grimoire.shareview", "unknown")), [b])

        def got(ok, value):
            b.setText(tr("grimoire.shareview", "Installed") if ok else tr("grimoire.shareview", "Try again"))
            b.setEnabled(not ok)
            row.sub.setText(tr("grimoire.shareview", "Installed.") if ok
                            else tr("grimoire.shareview", "Couldn't get it: {error}").format(error=value))

        def get():
            b.setEnabled(False)
            b.setText(tr("grimoire.shareview", "Getting…"))
            run(lambda: sharesetup.get_from_store(ref), got)
        return row

    def parts(self) -> set:
        return {k for k, box in self.ticks.items() if box.isChecked()}

    def _sync(self):
        self.go.setEnabled(bool(self.parts()))

    def _busy(self, text):
        self.message.setText(text)
        for b in (self.go, self.now, self.cancel):
            b.setEnabled(False)
        for box in self.ticks.values():
            box.setEnabled(False)

    def _import(self):
        from grimoire import sharesetup
        shared, parts = self.shared, self.parts()
        self._busy(tr("grimoire.shareview", "Saving a safety backup, then importing…"))
        run(lambda: sharesetup.apply(shared, parts), self._imported)

    def _imported(self, ok, value):
        self.cancel.setEnabled(True)
        if not ok:
            self.message.setText(value)
            self.go.setEnabled(True)
            for box in self.ticks.values():
                box.setEnabled(True)
            return
        self.result = value
        self.cancel.setText(tr("grimoire.shareview", "Close"))
        self.go.hide()
        text = tr("grimoire.shareview", "Imported. Your previous settings are saved in {safety}.").format(
            safety=value.safety.name)
        if value.look_id:
            text += " " + tr("grimoire.shareview", "The look is saved in MuraL → Looks as “{title}”.").format(
                title=self.shared.title)
        if value.look_id or value.favorites:
            text += " " + tr("grimoire.shareview", "Apply it now to change your desktop, or later from MuraL.")
            self.now.show()
            self.now.setEnabled(True)
            self.root.setVisible(bool(value.look_id))
        self.message.setText(text)

    def _apply_now(self):
        from grimoire import sharesetup
        result, root = self.result, {"login", "boot"} if self.root.isChecked() else set()
        self._busy(tr("grimoire.shareview", "Applying the look… (the taskbar may blink while Plasma restarts)"))
        self.root.setEnabled(False)
        run(lambda: sharesetup.apply_look(result, root), self._applied)

    def _applied(self, ok, value):
        self.cancel.setEnabled(True)
        if not ok:
            self.message.setText(tr("grimoire.shareview", "Couldn't apply the look: {error}").format(error=value))
            self.now.setEnabled(True)
            return
        self.message.setText("\n".join(tr("grimoire.shareview", "{part}: {message}").format(part=part, message=msg)
                                       for part, _, msg in value) or tr("grimoire.shareview", "Nothing to apply."))


# ---------------------------------------------------------------- the panel
class SharePanel(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        lay.addWidget(_label(tr("grimoire.shareview",
                                "Share your whole Grimoire look as one file: MuraL's screens and wallpaper "
                                "playlist, your crosshair, terminal profiles, LaunchL's favorites order and the tray "
                                "meter. Never your accounts, sign-ins, folders, tidy rules, history, network data or "
                                "terminal commands. Community themes travel as store links, not files."), "Muted"))
        lay.addWidget(_label(tr("grimoire.shareview", "SHARE"), "Section"))
        self.title = QLineEdit()
        self.title.setMaxLength(60)
        self.title.setPlaceholderText(tr("grimoire.shareview", "Monochrome Clover"))
        self.title.setFixedWidth(260)
        lay.addWidget(Row(tr("grimoire.shareview", "Name of this setup"),
                          tr("grimoire.shareview", "Shown to whoever opens it."), [self.title]))
        self.author = QLineEdit()
        self.author.setMaxLength(40)
        self.author.setPlaceholderText(tr("grimoire.shareview", "Optional"))
        self.author.setFixedWidth(260)
        lay.addWidget(Row(tr("grimoire.shareview", "Made by"),
                          tr("grimoire.shareview", "Any name you like; leave it empty to stay anonymous."),
                          [self.author]))
        self.pictures = QCheckBox(tr("grimoire.shareview", "Include wallpaper pictures"))
        self.pictures.setToolTip(tr("grimoire.shareview",
                                    "Pictures in your MuraL library that this look uses, up to 100 MB in total"))
        self.save = _button(tr("grimoire.shareview", "Save setup…"), self._export, "Primary")
        lay.addWidget(Row(tr("grimoire.shareview", "Save as a file"),
                          tr("grimoire.shareview", "A .grimoire-setup file to send or post anywhere. Grimoire "
                                                   "checks it holds nothing personal before saving."),
                          [self.pictures, self.save]))
        self.copy = _button(tr("grimoire.shareview", "Copy share code"), self._code)
        lay.addWidget(Row(tr("grimoire.shareview", "Copy a share code"),
                          tr("grimoire.shareview", "A short text code for chats (small setups only, no pictures)."),
                          [self.copy]))
        self.contents = _label("", "Muted")
        lay.addWidget(self.contents)

        lay.addSpacing(10)
        lay.addWidget(_label(tr("grimoire.shareview", "IMPORT"), "Section"))
        self.open = _button(tr("grimoire.shareview", "Open setup…"), self._open)
        lay.addWidget(Row(tr("grimoire.shareview", "Open a setup file"),
                          tr("grimoire.shareview",
                             "Checked, then previewed: you see what changes before anything does."),
                          [self.open]))
        self.paste = QLineEdit()
        self.paste.setPlaceholderText("GS1-…")
        self.paste.setFixedWidth(260)
        self.paste.returnPressed.connect(self._paste)
        self.check = _button(tr("grimoire.shareview", "Preview"), self._paste)
        lay.addWidget(Row(tr("grimoire.shareview", "Paste a share code"), "", [self.paste, self.check]))
        self.status = _label("", "Status")
        self.status.hide()
        lay.addWidget(self.status)
        lay.addStretch(1)
        self._loaded = False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def refresh(self):
        from grimoire import sharesetup
        run(lambda: sharesetup.draft(True), self._drafted)

    def _drafted(self, ok, d):
        if not ok:
            self.contents.setText(d)
            return
        self.contents.setText(tr("grimoire.shareview", "In it now: {summary}").format(summary=_summary(d.setup)))
        size = sum(s for _, _, s in d.wallpapers)
        if d.wallpapers:
            self.pictures.setText(tr("grimoire.shareview", "Include wallpaper pictures ({size})").format(
                size=_size(size)))
        else:
            self.pictures.setText(tr("grimoire.shareview", "Include wallpaper pictures (none to include)"))
        self.pictures.setEnabled(bool(d.wallpapers))

    def report(self, text, done=True):
        self.status.setText(text)
        self.status.setVisible(bool(text))
        for b in (self.save, self.copy, self.open, self.check):
            b.setEnabled(done)

    def _name(self) -> str:
        return self.title.text().strip() or tr("grimoire.shareview", "My Grimoire setup")

    def _export(self):
        from grimoire import sharesetup
        from grimoire.fsutil import free_name
        title, author, pics = self._name(), self.author.text(), self.pictures.isChecked()
        start = str(Path.home() / sharesetup.default_name(title))
        path, _ = QFileDialog.getSaveFileName(self, tr("grimoire.shareview", "Save Grimoire setup"), start,
                                              tr("grimoire.shareview", "Grimoire setup (*.grimoire-setup)"))
        if not path:
            return
        dest = Path(path)
        if dest.suffix != sharesetup.SUFFIX:          # the dialog only confirmed overwriting the name as typed
            dest = free_name(dest.with_name(dest.name + sharesetup.SUFFIX))
        self.report(tr("grimoire.shareview", "Checking and saving…"), False)

        def work():
            d = sharesetup.draft(pics)
            sharesetup.export(dest, d, title, author, _preview_png())
            return d

        def done(ok, d):
            if not ok:
                self.report(d)
                return
            text = tr("grimoire.shareview", "Saved {name}.").format(name=dest.name)
            if d.left_out:
                names = ", ".join(tr("grimoire.shareview", "{name} ({reason})").format(name=n, reason=why)
                                  for n, why in d.left_out[:4])
                text += " " + tr("grimoire.shareview", "Left out: {names}.").format(names=names)
            self.report(text)
        run(work, done)

    def _code(self):
        from grimoire import sharesetup
        title, author = self._name(), self.author.text()
        self.report(tr("grimoire.shareview", "Checking…"), False)

        def done(ok, code):
            if not ok:
                self.report(code)
            elif code is None:
                self.report(tr("grimoire.shareview", "This setup is too big for a code; save it as a file instead."))
            else:
                QGuiApplication.clipboard().setText(code)
                self.report(tr("grimoire.shareview", "Share code copied (%n character(s)).", n=len(code)))
        run(lambda: sharesetup.share_code(sharesetup.draft(False), title, author), done)

    def _open(self):
        from grimoire import sharesetup
        path, _ = QFileDialog.getOpenFileName(self, tr("grimoire.shareview", "Open Grimoire setup"), str(Path.home()),
                                              tr("grimoire.shareview",
                                                 "Grimoire setup (*.grimoire-setup);;All files (*)"))
        if path:
            self.report(tr("grimoire.shareview", "Checking the setup…"), False)
            run(lambda: sharesetup.inspect(Path(path)), self._show, (sharesetup.ShareError, OSError))

    def _paste(self):
        from grimoire import sharesetup
        text = self.paste.text()
        if not text.strip():
            return
        try:
            shared = sharesetup.from_code(text)
        except sharesetup.ShareError as e:
            self.report(str(e))
            return
        self._show(True, shared)

    def _show(self, ok, shared):
        if not ok:
            self.report(shared)
            return
        self.report("")
        dlg = SetupPreview(shared, self.window())
        dlg.exec()
        if dlg.result:
            self.paste.clear()
            self.report(tr("grimoire.shareview", "Imported “{title}”.").format(title=shared.title))
            self.refresh()
        else:
            self.report(tr("grimoire.shareview", "Import cancelled; nothing changed."))
