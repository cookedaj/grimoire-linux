# SPDX-License-Identifier: GPL-3.0-or-later
"""First-run setup, after the first sign-in or guest start (and again from Settings → General): Welcome, your
spells, a look, hotkeys, language, done. Every step can be skipped; nothing on the desktop changes unless you
press Apply on a look. Choices go to prefs (settings.json of the active profile)."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QRadioButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from grimoire import NAME, i18n, prefs, session
from grimoire.glyphs import clover, glyph
from grimoire.settingsview import HotkeysPanel, _button, _label, restore_flow, run

STEPS = [("welcome", "Welcome"), ("spells", "Spells"), ("look", "Look"), ("hotkeys", "Hotkeys"),
         ("language", "Language"), ("done", "Done")]
QSS = """
QLabel#Step { color: #4a4a4a; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#Step[on="true"] { color: #ffffff; }
QLabel#Step[past="true"] { color: #8c8c8c; }
QFrame#Pick { background: #0f0f0f; border: 1px solid #1c1c1c; border-radius: 10px; }
QFrame#Pick[on="true"] { border-color: #f2f2f2; }
QRadioButton { spacing: 10px; }
QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid #4a4a4a; border-radius: 8px;
                         background: #0b0b0b; }
QRadioButton::indicator:checked { background: #f2f2f2; border-color: #f2f2f2; }
"""


def _page(title, sub):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    lay.addWidget(_label(title, "Hero"))
    s = _label(sub, "Muted")
    lay.addWidget(s)
    lay.addSpacing(14)
    return w, lay


class SpellPick(QFrame):
    def __init__(self, spell, on):
        super().__init__()
        self.setObjectName("Pick")
        self.spell = spell
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)
        self.box = QCheckBox()
        self.box.setChecked(on)
        self.box.toggled.connect(self._mark)
        lay.addWidget(self.box)
        icon = QLabel()
        icon.setPixmap(glyph(spell.icon, 22).pixmap(22, 22, QIcon.Mode.Active))
        lay.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(_label(spell.name, "RowTitle"))
        tag = _label(spell.tagline, "Muted")
        tag.setStyleSheet("font-size: 11px;")
        text.addWidget(tag)
        lay.addLayout(text, 1)
        self._mark(on)

    def _mark(self, on):
        self.setProperty("on", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, e):
        self.box.toggle()


class SetupWizard(QWidget):
    """finished() once Done (or Skip setup) is pressed; choices are saved by then."""
    finished = Signal()

    def __init__(self, start="welcome"):
        super().__init__()
        self.setObjectName("Page")
        self.setStyleSheet(QSS)
        p = prefs.load()
        self.hidden = set(p["hidden_spells"])
        root = QVBoxLayout(self)
        root.setContentsMargins(64, 40, 64, 32)
        root.setSpacing(18)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(clover(28))
        top.addWidget(logo)
        top.addSpacing(18)
        self.steps = []
        for i, (_, name) in enumerate(STEPS):
            lab = _label("{n}  {name}".format(n=i + 1, name=name.upper()), "Step", wrap=False)
            self.steps.append(lab)
            top.addWidget(lab)
            top.addSpacing(14)
        top.addStretch(1)
        self.skip = _button("Skip setup", self._finish, "Link")
        top.addWidget(self.skip)
        root.addLayout(top)
        rule = QFrame()
        rule.setObjectName("Rule")
        rule.setFixedHeight(1)
        root.addWidget(rule)

        self.stack = QStackedWidget()
        for build in (self._welcome, self._spells, self._look, self._hotkeys, self._language, self._done):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            inner = build()
            inner.setObjectName("Page")
            holder = QWidget()
            holder.setObjectName("Page")
            hl = QVBoxLayout(holder)
            hl.setContentsMargins(0, 18, 0, 0)
            hl.addWidget(inner)
            hl.addStretch(1)
            scroll.setWidget(holder)
            self.stack.addWidget(scroll)
        root.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        self.back = _button("Back", lambda: self.go(self.index - 1))
        nav.addWidget(self.back)
        nav.addStretch(1)
        self.next = _button("Next", self._next, "Primary")
        self.next.setMinimumWidth(140)
        nav.addWidget(self.next)
        root.addLayout(nav)
        self.index = 0
        self.go([k for k, _ in STEPS].index(start))

    # ---------------------------------------------------------------- pages
    def _welcome(self):
        who = session.active()
        name = who.username if who and not who.guest else ""
        w, lay = _page("Welcome, {name}.".format(name=name) if name else "Welcome to {app}.".format(app=NAME),
                       "A few quick choices and you're in. Everything here can be changed later in Settings, "
                       "and every step can be skipped.")
        if who and who.guest:
            lay.addWidget(_label("You're using Grimoire Linux as a guest: the choices you make now last until the "
                                 "next guest start. Create an account any time from Settings to keep them.",
                                 "Muted"))
        self.cloud = QFrame()
        self.cloud.setObjectName("Row")
        cl = QHBoxLayout(self.cloud)
        cl.setContentsMargins(18, 14, 14, 14)
        self.cloud_text = _label("", "Muted")
        cl.addWidget(self.cloud_text, 1)
        self.cloud_btn = _button("Restore them", self._restore_cloud, "Primary")
        cl.addWidget(self.cloud_btn)
        self.cloud.hide()
        lay.addWidget(self.cloud)
        if who and not who.guest:
            run(self._cloud_check, self._cloud_found)
        return w

    def _cloud_check(self):
        from grimoire import accounts
        if not accounts.BACKEND.configured():
            return None
        found = accounts.BACKEND.load_settings(session.live())
        return found and found[1]

    def _cloud_found(self, ok, when):
        if ok and when:
            self.cloud_text.setText("Your account has settings saved from another PC ({when}). Restore them here?"
                                    .format(when=when[:16].replace("T", " ")))
            self.cloud.show()

    def _restore_cloud(self):
        from grimoire import accounts

        def report(text, done):
            self.cloud_text.setText(text)
            self.cloud_btn.setEnabled(done)

        def got(ok, value):
            if not ok:
                report(value, True)
                return
            restore_flow(self, value[0], "your account", report, self._reload_choices)
        report("Downloading…", False)
        run(lambda: accounts.BACKEND.load_settings(session.live()), got)

    def _reload_choices(self):
        self.hidden = set(prefs.load()["hidden_spells"])
        for pick in self.picks:
            pick.box.setChecked(pick.spell.id not in self.hidden)

    def _spells(self):
        from grimoire.spells import SPELLS
        w, lay = _page("Pick your spells", "The ones you tick show in the rail and on the home page. Hidden ones "
                       "keep working (timers, hotkeys) and come back any time from Settings → General.")
        grid = QGridLayout()
        grid.setSpacing(10)
        self.picks = [SpellPick(s, s.id not in self.hidden) for s in SPELLS]
        for i, pick in enumerate(self.picks):
            grid.addWidget(pick, i // 2, i % 2)
        lay.addLayout(grid)
        return w

    def _look(self):
        w, lay = _page("A look", "MuraL can put a saved desktop look back in one go. This changes your desktop "
                       "(panels, colors, wallpaper…), so it's only done when you press Apply.")
        try:
            from grimoire.spells.mural import looks
            saved = looks.all_looks()
        except Exception:                      # MuraL missing pieces must not stop setup
            looks, saved = None, []
        self.look_group = QButtonGroup(self)
        keep = QRadioButton("Keep my current look")
        keep.setChecked(True)
        self.look_group.addButton(keep)
        lay.addWidget(keep)
        if not saved:
            lay.addWidget(_label("No saved looks yet. Save one in MuraL → Looks whenever you like.", "Muted"))
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, look in enumerate(saved[:6]):
            card = QFrame()
            card.setObjectName("Pick")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 10, 10, 10)
            thumb = QLabel()
            pm = QPixmap(str(looks.thumb_path(look["id"])))
            if not pm.isNull():
                thumb.setPixmap(pm.scaled(QSize(240, 135), Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
            else:
                thumb.setFixedSize(240, 135)
                thumb.setStyleSheet("background: #141414; border-radius: 6px;")
            cl.addWidget(thumb)
            rb = QRadioButton(str(look.get("name", "Look"))[:40])
            rb.setProperty("look_id", look.get("id"))
            self.look_group.addButton(rb)
            cl.addWidget(rb)
            grid.addWidget(card, i // 3, i % 3)
        lay.addLayout(grid)
        row = QHBoxLayout()
        self.apply_look = _button("Apply this look", self._apply_look)
        self.apply_look.setEnabled(False)
        row.addWidget(self.apply_look)
        self.look_note = _label("", "Muted")
        row.addWidget(self.look_note, 1)
        lay.addLayout(row)
        self.look_group.buttonToggled.connect(lambda *_: self.apply_look.setEnabled(
            bool(self.look_group.checkedButton() and self.look_group.checkedButton().property("look_id"))))
        return w

    def _apply_look(self):
        from grimoire.spells.mural import looks
        look_id = self.look_group.checkedButton().property("look_id")
        self.apply_look.setEnabled(False)
        self.look_note.setText("Applying (the panel may restart)…")

        def then(ok, value):
            self.apply_look.setEnabled(True)
            if not ok:
                self.look_note.setText("Couldn't apply it: {err}".format(err=value))
                return
            bad = sum(not r[1] for r in value)
            self.look_note.setText("Applied." if not bad else "Applied, but {n} part(s) failed; see MuraL → Looks."
                                   .format(n=bad))
        run(lambda: looks.restore(look_id), then)        # never the login/boot parts (those need a password)

    def _hotkeys(self):
        w, lay = _page("Hotkeys", "Keep the defaults or set your own. You can change them later in Settings.")
        lay.addWidget(HotkeysPanel())
        return w

    def _language(self):
        w, lay = _page("Language", "Which language should Grimoire Linux use?")
        self.lang = QComboBox()
        for code, native in i18n.LANGUAGES.items():
            self.lang.addItem(native, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(i18n.current())))
        self.lang.setFixedWidth(280)
        lay.addWidget(self.lang)
        lay.addWidget(_label("Grimoire Linux restarts in the new language when the setup ends. Translations are "
                             "machine-made; native speakers are welcome to improve them on GitHub.", "Muted"))
        return w

    def _done(self):
        w, lay = _page("You're all set.", "Your spells are waiting. Settings (the gear at the bottom of the rail) "
                       "has everything from this setup, plus backups and your account.")
        return w

    # ---------------------------------------------------------------- navigation
    def go(self, i):
        self.index = max(0, min(i, len(STEPS) - 1))
        self.stack.setCurrentIndex(self.index)
        for n, lab in enumerate(self.steps):
            lab.setProperty("on", n == self.index)
            lab.setProperty("past", n < self.index)
            lab.style().unpolish(lab)
            lab.style().polish(lab)
        self.back.setVisible(self.index > 0)
        last = self.index == len(STEPS) - 1
        self.next.setText("Open {app}".format(app=NAME) if last else "Next")
        self.skip.setVisible(not last)

    def _next(self):
        if self.index == len(STEPS) - 1:
            self._finish()
        else:
            self.go(self.index + 1)

    def _finish(self):
        hidden = sorted(p.spell.id for p in self.picks if not p.box.isChecked())
        prefs.save(hidden_spells=hidden, setup_done=True)
        try:
            i18n.choose(self.lang.currentData() or "en")       # applied by a restart (loginview.gate, Settings)
        except OSError:
            pass
        self.finished.emit()


class SetupDialog(QDialog):
    """"Run setup again" from Settings."""

    def __init__(self, parent=None, start="welcome"):
        super().__init__(parent)
        self.setWindowTitle("Setup")
        self.setObjectName("WhatsNew")
        self.resize(1100, 720)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        wiz = SetupWizard(start)
        wiz.finished.connect(self.accept)
        lay.addWidget(wiz)

