# SPDX-License-Identifier: GPL-3.0-or-later
"""The sign-in screen: Sign in, Create account, Forgot password, Google/GitHub, and Continue as Guest.

gate() runs it before the hub (or a standalone spell window) loads any spell, because the account decides which
settings folder every module reads (paths.py). Imports here must stay free of modules that read CONFIG.
"""
import os
import sys
import threading

from PySide6.QtCore import QEventLoop, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from grimoire import NAME, accounts, i18n, paths, session
from grimoire.glyphs import clover
from grimoire.i18n import tr
from grimoire.settingsview import _button, _label, run
from grimoire.theme import FONT

CARD_QSS = """
QFrame#AuthCard { background: #0e0e0e; border: 1px solid #1f1f1f; border-radius: 14px; }
QFrame#AuthCard QLineEdit { padding: 9px 10px; }
QFrame#AuthCard QPushButton#Primary { padding: 10px 14px; }
QFrame#Strength[on="true"] { background: #f2f2f2; border-radius: 2px; }
QFrame#Strength[on="false"] { background: #262626; border-radius: 2px; }
QLabel#Code { font-family: "IBM Plex Mono"; font-size: 24px; font-weight: 600; color: #ffffff; background: #080808;
              border: 1px solid #2a2a2a; border-radius: 8px; padding: 14px 18px; }
QPushButton#Guest { border: none; color: #d0d0d0; padding: 6px 10px; font-weight: 600; }
QPushButton#Guest:hover { color: #ffffff; text-decoration: underline; }
QFrame#Notice { background: #141414; border: 1px solid #2a2a2a; border-radius: 8px; }
"""


def _spaced(text, size, spacing):
    lab = QLabel(text)
    font = QFont(FONT, size, QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, i18n.spacing(text, spacing))
    lab.setFont(font)
    return lab


def _field(placeholder, password=False):
    f = QLineEdit()
    f.setPlaceholderText(placeholder)
    if password:
        f.setEchoMode(QLineEdit.EchoMode.Password)
    f.setMinimumWidth(320)
    return f


class Strength(QWidget):
    """Three bars and a hint under a new password."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        bars = QHBoxLayout()
        bars.setSpacing(4)
        self.bars = []
        for _ in range(3):
            b = QFrame()
            b.setObjectName("Strength")
            b.setFixedHeight(3)
            bars.addWidget(b)
            self.bars.append(b)
        lay.addLayout(bars)
        self.hint = _label("", "Muted")
        lay.addWidget(self.hint)
        self.update_for("")

    def update_for(self, password):
        score, hint = accounts.strength(password)
        for i, b in enumerate(self.bars):
            b.setProperty("on", i < score)
            b.style().unpolish(b)
            b.style().polish(b)
        self.hint.setText(hint or tr("grimoire.loginview", "At least {n} characters. A few words together make a "
                                                           "strong password.").format(n=accounts.MIN_PASSWORD))


class RecoveryCodeDialog(QDialog):
    """Shows a recovery code once; Continue unlocks after "I saved it" is ticked."""

    def __init__(self, username, code, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("grimoire.loginview", "Your recovery code"))
        self.setObjectName("WhatsNew")
        self.setStyleSheet(CARD_QSS)
        self.setModal(True)
        self.code, self.username = code, username
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(12)
        lay.addWidget(_label(tr("grimoire.loginview", "Save your recovery code"), "SectionTitle"))
        lay.addWidget(_label(tr("grimoire.loginview",
                                "If you forget your password, this code lets you set a new one. It's shown only now; "
                                "Grimoire Linux can't show it again. Keep it somewhere safe, like a password manager "
                                "or on paper."), "Muted"))
        code_label = _label(code, "Code", wrap=False)
        code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(code_label)
        row = QHBoxLayout()
        row.addWidget(_button(tr("grimoire.loginview", "Copy"), self._copy))
        row.addWidget(_button(tr("grimoire.loginview", "Save to a file…"), self._save))
        row.addStretch(1)
        lay.addLayout(row)
        self.note = _label("", "Muted")
        self.note.hide()
        lay.addWidget(self.note)
        self.saved = QCheckBox(tr("grimoire.loginview", "I saved my recovery code"))
        lay.addWidget(self.saved)
        self.go = _button(tr("grimoire.loginview", "Continue"), self.accept, "Primary")
        self.go.setEnabled(False)
        self.saved.toggled.connect(self.go.setEnabled)
        lay.addWidget(self.go, 0, Qt.AlignmentFlag.AlignRight)
        self.setMinimumWidth(480)

    def _copy(self):
        QGuiApplication.clipboard().setText(self.code)
        self.note.setText(tr("grimoire.loginview", "Copied. Paste it somewhere safe, then clear your clipboard."))
        self.note.show()

    def _save(self):
        from pathlib import Path

        from grimoire.fsutil import free_name
        start = str(Path.home() / "grimoire-recovery-code.txt")
        path, _ = QFileDialog.getSaveFileName(self, tr("grimoire.loginview", "Save recovery code"), start,
                                              tr("grimoire.loginview", "Text (*.txt)"))
        if not path:
            return
        dest = free_name(Path(path)) if Path(path).exists() else Path(path)
        try:
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                line = tr("grimoire.loginview", "Recovery code for {user}: {code}").format(user=self.username,
                                                                                           code=self.code)
                f.write("{name}\n{line}\n".format(name=NAME, line=line))
            self.note.setText(tr("grimoire.loginview", "Saved to {path}.").format(path=dest))
        except OSError as e:
            self.note.setText(tr("grimoire.loginview", "Couldn't save it: {err}").format(err=e.strerror or e))
        self.note.show()


class AuthCard(QFrame):
    """The form itself. finished(result): {"kind": "account", "session", "remember"} or {"kind": "guest"}."""
    finished = Signal(object)

    def __init__(self, allow_guest=True, mode="signin"):
        super().__init__()
        self.setObjectName("AuthCard")
        self.setStyleSheet(CARD_QSS)
        self.setFixedWidth(420)
        self.backend = accounts.BACKEND
        self._busy = False
        self._cancel = threading.Event()
        ready = self.backend.configured()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 30)
        lay.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(clover(56))
        logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(logo)
        lay.addSpacing(4)
        title = _spaced(NAME.upper(), 13, 5)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(title)
        self.heading = _label("", "SectionTitle")
        self.heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.heading)
        self.sub = _label("", "Muted")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.sub)
        lay.addSpacing(6)
        if not ready:
            notice = QFrame()
            notice.setObjectName("Notice")
            nl = QVBoxLayout(notice)
            nl.setContentsMargins(14, 12, 14, 12)
            nl.addWidget(_label(tr("grimoire.loginview",
                                   "Accounts aren't set up yet in this copy of Grimoire Linux, so signing in isn't "
                                   "possible for now. Continue as a guest: everything works, your settings just "
                                   "aren't kept."), "Muted"))
            lay.addWidget(notice)

        self.forms = QWidget()                   # one form visible at a time, the card as tall as that one
        fl = QVBoxLayout(self.forms)
        fl.setContentsMargins(0, 0, 0, 0)
        self.pages = [self._signin_form(), self._create_form(), self._forgot_form()]
        for page in self.pages:
            fl.addWidget(page)
        lay.addWidget(self.forms)
        self.status = _label("", "Muted")
        self.status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.status.hide()
        lay.addWidget(self.status)
        self.cancel_oauth = _button(tr("grimoire.loginview", "Cancel"), self._stop_oauth, "Link")
        self.cancel_oauth.hide()
        lay.addWidget(self.cancel_oauth, 0, Qt.AlignmentFlag.AlignHCenter)

        self.oauth = QWidget()
        ol = QVBoxLayout(self.oauth)
        ol.setContentsMargins(0, 4, 0, 0)
        ol.setSpacing(8)
        div = QHBoxLayout()
        for _ in range(2):
            line = QFrame()
            line.setObjectName("Rule")
            line.setFixedHeight(1)
            div.addWidget(line, 1)
            if _ == 0:
                div.addWidget(_label(tr("grimoire.loginview", "or"), "Muted", wrap=False))
        ol.addLayout(div)
        self.google = _button(tr("grimoire.loginview", "Sign in with Google") if ready else
                              tr("grimoire.loginview", "Sign in with Google · not set up yet"),
                              lambda: self._oauth("google"))
        self.github = _button(tr("grimoire.loginview", "Sign in with GitHub") if ready else
                              tr("grimoire.loginview", "Sign in with GitHub · not set up yet"),
                              lambda: self._oauth("github"))
        for b in (self.google, self.github):
            b.setEnabled(ready)
            ol.addWidget(b)
        lay.addWidget(self.oauth)

        self.guest = None
        if allow_guest:
            lay.addSpacing(8)
            self.guest = _button(tr("grimoire.loginview", "Continue as Guest"), self._guest,
                                 "Primary" if not ready else "Guest")
            if ready:
                lay.addWidget(self.guest, 0, Qt.AlignmentFlag.AlignHCenter)
            else:
                lay.addWidget(self.guest)
            g = _label(tr("grimoire.loginview", "Everything works as a guest, but settings are cleared next time."),
                       "Muted")
            g.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            g.setStyleSheet("font-size: 11px;")
            lay.addWidget(g)
        for w in self.forms.findChildren(QLineEdit) + self.forms.findChildren(QPushButton) + \
                self.forms.findChildren(QCheckBox):
            if not ready and w.objectName() != "Link":
                w.setEnabled(False)
        self.show_mode(mode)

    # ---------------------------------------------------------------- forms
    def _form(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        return w, lay

    def _signin_form(self):
        w, lay = self._form()
        self.si_user = _field(tr("grimoire.loginview", "Username"))
        self.si_pass = _field(tr("grimoire.loginview", "Password"), True)
        lay.addWidget(self.si_user)
        lay.addWidget(self.si_pass)
        row = QHBoxLayout()
        self.si_keep = QCheckBox(tr("grimoire.loginview", "Keep me signed in"))
        self.si_keep.setChecked(True)
        row.addWidget(self.si_keep)
        row.addStretch(1)
        row.addWidget(_button(tr("grimoire.loginview", "Forgot password?"), lambda: self.show_mode("forgot"), "Link"))
        lay.addLayout(row)
        self.si_go = _button(tr("grimoire.loginview", "Sign in"), self._sign_in, "Primary")
        lay.addWidget(self.si_go)
        lay.addWidget(_button(tr("grimoire.loginview", "New here? Create an account"), lambda: self.show_mode("create"),
                              "Link"), 0, Qt.AlignmentFlag.AlignHCenter)
        for f in (self.si_user, self.si_pass):
            f.returnPressed.connect(self._sign_in)
        return w

    def _create_form(self):
        w, lay = self._form()
        self.cr_user = _field(tr("grimoire.loginview", "Username"))
        self.cr_mail = _field(tr("grimoire.loginview", "Email (optional)"))
        self.cr_mail.setToolTip(tr("grimoire.loginview", "Kept privately with your account. It isn't used to sign in "
                                                         "and never shared."))
        self.cr_pass = _field(tr("grimoire.loginview", "Password"), True)
        self.cr_strength = Strength()
        self.cr_conf = _field(tr("grimoire.loginview", "Confirm password"), True)
        self.cr_pass.textChanged.connect(self.cr_strength.update_for)
        for f in (self.cr_user, self.cr_mail, self.cr_pass):
            lay.addWidget(f)
        lay.addWidget(self.cr_strength)
        lay.addWidget(self.cr_conf)
        self.cr_keep = QCheckBox(tr("grimoire.loginview", "Keep me signed in"))
        self.cr_keep.setChecked(True)
        lay.addWidget(self.cr_keep)
        self.cr_go = _button(tr("grimoire.loginview", "Create account"), self._create, "Primary")
        lay.addWidget(self.cr_go)
        lay.addWidget(_button(tr("grimoire.loginview", "Have an account? Sign in"), lambda: self.show_mode("signin"),
                              "Link"), 0, Qt.AlignmentFlag.AlignHCenter)
        self.cr_conf.returnPressed.connect(self._create)
        return w

    def _forgot_form(self):
        w, lay = self._form()
        lay.addWidget(_label(tr("grimoire.loginview",
                                "Enter your username and the recovery code you saved when you made the account. "
                                "Accounts made with Google or GitHub reset their password there."), "Muted"))
        self.fg_user = _field(tr("grimoire.loginview", "Username"))
        self.fg_code = _field(tr("grimoire.loginview", "Recovery code (like 1A2B3-C4D5E-…)"))
        self.fg_pass = _field(tr("grimoire.loginview", "New password"), True)
        self.fg_strength = Strength()
        self.fg_conf = _field(tr("grimoire.loginview", "Confirm new password"), True)
        self.fg_pass.textChanged.connect(self.fg_strength.update_for)
        for f in (self.fg_user, self.fg_code, self.fg_pass):
            lay.addWidget(f)
        lay.addWidget(self.fg_strength)
        lay.addWidget(self.fg_conf)
        self.fg_go = _button(tr("grimoire.loginview", "Set new password"), self._recover, "Primary")
        lay.addWidget(self.fg_go)
        lay.addWidget(_button(tr("grimoire.loginview", "Back to sign in"), lambda: self.show_mode("signin"), "Link"), 0,
                      Qt.AlignmentFlag.AlignHCenter)
        self.fg_conf.returnPressed.connect(self._recover)
        return w

    def show_mode(self, mode):
        index = {"signin": 0, "create": 1, "forgot": 2}[mode]
        self.mode = mode
        self.heading.setText({"signin": tr("grimoire.loginview", "Sign in"),
                              "create": tr("grimoire.loginview", "Create your account"),
                              "forgot": tr("grimoire.loginview", "Forgot your password?")}[mode])
        self.sub.setText({"signin": tr("grimoire.loginview", "Your settings, on every PC you sign in to."),
                          "create": tr("grimoire.loginview", "A username and a password. Email is optional."),
                          "forgot": tr("grimoire.loginview", "Set a new password with your recovery code.")}[mode])
        self.oauth.setVisible(mode != "forgot")
        self.say("")
        for i, page in enumerate(self.pages):
            page.setVisible(i == index)

    # ---------------------------------------------------------------- actions
    def say(self, text):
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _set_busy(self, busy, text=""):
        self._busy = busy
        for b in (self.si_go, self.cr_go, self.fg_go, self.google, self.github):
            b.setEnabled(not busy and self.backend.configured())
        if self.guest:
            self.guest.setEnabled(not busy)
        self.say(text)

    def _done(self, s, remember):
        self.finished.emit({"kind": "account", "session": s, "remember": remember, "mode": self.mode})

    def _sign_in(self):
        if self._busy:
            return
        user, pw = self.si_user.text().strip(), self.si_pass.text()
        if not user or not pw:
            self.say(tr("grimoire.loginview", "Enter your username and password."))
            return
        wait = accounts.wait_left(user)
        if wait:
            self.say(tr("grimoire.loginview", "Too many wrong passwords. Try again in %n second(s).", n=wait))
            return
        self._set_busy(True, tr("grimoire.loginview", "Signing in…"))
        keep = self.si_keep.isChecked()

        def work():
            try:
                s = self.backend.sign_in(user, pw)
            except accounts.AccountError as e:
                if e.kind == "credentials":              # only wrong passwords count, not being offline
                    accounts.note_attempt(user, False)
                raise
            accounts.note_attempt(user, True)
            return s

        def then(ok, value):
            self._set_busy(False)
            if ok:
                self.si_pass.clear()
                self._done(value, keep)
            else:
                self.say(value)
        run(work, then, (accounts.AccountError,))

    def _create(self):
        if self._busy:
            return
        user, mail = self.cr_user.text().strip(), self.cr_mail.text().strip()
        pw, conf = self.cr_pass.text(), self.cr_conf.text()
        problem = (accounts.username_problem(user) or accounts.email_problem(mail)
                   or accounts.password_problem(pw, conf))
        if problem:
            self.say(problem)
            return
        if accounts.strength(pw)[0] == 0:
            self.say(tr("grimoire.loginview", "That password is too easy to guess. Try a longer one."))
            return
        self._set_busy(True, tr("grimoire.loginview", "Creating your account…"))
        keep = self.cr_keep.isChecked()

        def then(ok, value):
            self._set_busy(False)
            if not ok:
                self.say(value)
                return
            s, code = value
            for f in (self.cr_pass, self.cr_conf):
                f.clear()
            RecoveryCodeDialog(s.user.username, code, self.window()).exec()
            self._done(s, keep)
        run(lambda: self.backend.sign_up(user, pw, mail), then, (accounts.AccountError,))

    def _recover(self):
        if self._busy:
            return
        user, code = self.fg_user.text().strip(), self.fg_code.text().strip()
        pw, conf = self.fg_pass.text(), self.fg_conf.text()
        problem = (tr("grimoire.loginview", "Enter your username and recovery code.") if not user or not code else
                   accounts.password_problem(pw, conf))
        if problem:
            self.say(problem)
            return
        self._set_busy(True, tr("grimoire.loginview", "Checking your recovery code…"))

        def then(ok, value):
            self._set_busy(False)
            if not ok:
                self.say(value)
                return
            for f in (self.fg_code, self.fg_pass, self.fg_conf):
                f.clear()
            RecoveryCodeDialog(user, value, self.window()).exec()
            self.si_user.setText(user)
            self.si_pass.setText(pw)
            self.show_mode("signin")
            self._sign_in()
        run(lambda: self.backend.recover(user, code, pw), then, (accounts.AccountError,))

    def _oauth(self, provider):
        if self._busy:
            return
        try:
            lb = accounts.Loopback()
        except OSError:
            self.say(tr("grimoire.loginview", "Couldn't open a local port for the browser to come back to."))
            return
        verifier, challenge = accounts.pkce_pair()
        try:
            url = self.backend.oauth_url(provider, lb.redirect, challenge)
        except accounts.AccountError as e:
            lb.close()
            self.say(str(e))
            return
        self._cancel.clear()
        self._set_busy(True, tr("grimoire.loginview", "Finish signing in with {p} in your browser…").format(
            p=accounts.PROVIDERS[provider]))
        self.cancel_oauth.show()
        QDesktopServices.openUrl(QUrl(url))
        keep = self.si_keep.isChecked() if self.mode == "signin" else self.cr_keep.isChecked()
        cancel = self._cancel

        def then(ok, value):
            self.cancel_oauth.hide()
            self._set_busy(False)
            if ok:
                self._done(value, keep)
            else:
                self.say(value)
        run(lambda: self.backend.oauth_finish(lb.wait(cancelled=cancel.is_set), verifier, provider), then,
            (accounts.AccountError,))

    def _stop_oauth(self):
        self._cancel.set()

    def _guest(self):
        self._cancel.set()
        self.finished.emit({"kind": "guest"})


class SignInScreen(QWidget):
    """The full-window screen: the card centered on black, a quiet footer."""
    finished = Signal(object)

    def __init__(self, allow_guest=True):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 16)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.card = AuthCard(allow_guest)
        self.card.finished.connect(self.finished)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        foot = _label(tr("grimoire.loginview", "Black & white tools for KDE Plasma"), "Tiny")
        foot.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(foot)


class AccountDialog(QDialog):
    """The same card inside the hub: a guest creating an account or signing in, without the Guest link."""

    def __init__(self, mode="create", parent=None):
        super().__init__(parent)
        self.setWindowTitle(NAME)
        self.setObjectName("WhatsNew")
        self.result_value = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        self.card = AuthCard(allow_guest=False, mode=mode)
        self.card.finished.connect(self._finish)
        lay.addWidget(self.card)

    def _finish(self, result):
        self.result_value = result
        self.accept()

    def done(self, r):
        self.card._cancel.set()                  # closed while a browser sign-in waits: free its local port
        super().done(r)


# ---------------------------------------------------------------- the gate
def restart() -> bool:
    """Start this program again (to load another profile); GRIMOIRE_PROFILE says which. A session that isn't kept
    in the keyring crosses the restart through a pipe (session.handoff), never a file or the environment.
    The open windows are closed first, so pages save what they hold (NoteL asks about unsaved files); exec skips
    every close handler. Returns False, and restarts nothing, when a window refuses to close."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.closeAllWindows()
        if any(w.isVisible() for w in app.topLevelWidgets() if w.isWindow()):
            return False
    sys.stdout.flush()
    session.handoff()
    os.execv(sys.executable, sys.orig_argv)


def _restart_once() -> bool:
    """Restart after a profile switch that a loaded module would miss. Never twice in a row: after a restart the
    profile comes from GRIMOIRE_PROFILE at import, so a second request means something else is wrong."""
    if os.environ.pop("GRIMOIRE_RESTARTED", ""):
        return True
    os.environ["GRIMOIRE_RESTARTED"] = "1"
    restart()


def _apply(result) -> bool:
    if result["kind"] == "guest":
        return session.begin_guest()
    return session.begin(result["session"], result["remember"])


def _off_thread(fn):
    """fn() on a worker while a local event loop keeps the window painting: saving the sign-in can wait on the
    keyring's unlock prompt for up to two minutes, which froze the sign-in screen. Returns fn()'s value or raises
    what it raised."""
    loop, box = QEventLoop(), {}

    def work():
        try:
            return True, fn()
        except Exception as e:                   # handed back and raised here, on the UI thread
            return False, e

    def then(_ok, value):
        box["r"] = value
        loop.quit()
    run(work, then)
    if "r" not in box:
        loop.exec()
    ok, value = box["r"]
    if not ok:
        raise value
    return value


def gate(title=NAME, size=(1440, 880), wizard=False) -> bool:
    """Before any spell loads: use the session this process inherited or remembered, else show the sign-in screen
    (and, for the hub, the first-run setup). False when the window was closed without choosing."""
    who = session.active() if os.environ.get("GRIMOIRE_PROFILE") else None
    if who and who.guest:
        ok = session.join_guest()
    elif who:
        ok = paths.activate(who.profile)
    elif (who := session.remembered()) is not None:
        ok = paths.activate(who.profile)
    else:
        ok = None
    if ok is None:
        win = QWidget()
        win.setWindowTitle(title)
        win.setObjectName("Page")
        win.resize(*size)
        lay = QVBoxLayout(win)
        lay.setContentsMargins(0, 0, 0, 0)
        screen = SignInScreen()
        lay.addWidget(screen)
        loop, box = QEventLoop(), {}
        screen.finished.connect(lambda r: (box.setdefault("r", r), loop.quit()))
        win.closeEvent = lambda e: (screen.card._cancel.set(), loop.quit(), e.accept())   # stops a waiting OAuth
        win.show()
        while True:
            loop.exec()
            if "r" not in box:
                return False
            screen.card._set_busy(True)
            try:
                ok = _off_thread(lambda r=box.pop("r"): _apply(r))
            except OSError as e:                         # e.g. an unsafe or full runtime dir for the guest profile
                ok = None
                screen.card._set_busy(False)
                screen.card.say(tr("grimoire.loginview", "Couldn't set up your profile: {err}").format(
                    err=e.strerror or e))
            if not win.isVisible():                      # closed while it was saving
                return False
            if ok is not None:
                break
        if wizard and ok:
            ok = _wizard(win, lay, screen)
        win.hide()
        win.deleteLater()
        if ok is None:
            return False
    elif wizard and ok:
        ok = _wizard_window(title, size)
        if ok is None:
            return False
    if not ok:
        _restart_once()
    os.environ.pop("GRIMOIRE_RESTARTED", None)
    again = os.environ.pop("GRIMOIRE_LANG_RESTARTED", "")
    if i18n.needs_restart() and not again:
        os.environ["GRIMOIRE_LANG_RESTARTED"] = "1"      # this account (or the setup) picked another language
        restart()
    return True


def _wizard(win, lay, screen):
    """The first-run setup in the sign-in window, when this profile hasn't done it yet. None = window closed."""
    from grimoire import prefs
    if prefs.load()["setup_done"]:
        return True
    from grimoire.setupwizard import SetupWizard
    wiz = SetupWizard()
    screen.hide()
    lay.addWidget(wiz)
    loop, box = QEventLoop(), {}
    wiz.finished.connect(lambda: (box.setdefault("done", True), loop.quit()))
    win.closeEvent = lambda e: (loop.quit(), e.accept())
    loop.exec()
    return True if box else None


def _wizard_window(title, size):
    from grimoire import prefs
    if prefs.load()["setup_done"]:
        return True
    win = QWidget()
    win.setWindowTitle(title)
    win.setObjectName("Page")
    win.resize(*size)
    lay = QVBoxLayout(win)
    lay.setContentsMargins(0, 0, 0, 0)
    dummy = QWidget()
    lay.addWidget(dummy)
    win.show()
    ok = _wizard(win, lay, dummy)
    win.hide()
    win.deleteLater()
    return ok
