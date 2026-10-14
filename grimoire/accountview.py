# SPDX-License-Identifier: GPL-3.0-or-later
"""Your account inside the hub: the Settings → Account panel, the guest bar on the home page and the quiet
settings sync (upload when something changed, at start and every 30 minutes, if turned on)."""
import hashlib

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from grimoire import NAME, accounts, session
from grimoire.settingsview import Row, _button, _label, restore_flow, run
from grimoire.widgets import Switch

PROVIDER_LINE = {"password": "Signed in with a username and password", "google": "Signed in with Google",
                 "github": "Signed in with GitHub"}


def _restart_as_new_session(result, parent, from_guest):
    """After the account dialog: begin the session, then restart the hub so every spell reads its settings."""
    from grimoire.loginview import restart
    try:
        session.begin(result["session"], result["remember"], from_guest=from_guest)
    except OSError as e:
        QMessageBox.warning(parent, NAME, "Couldn't set up your profile: {err}".format(err=e.strerror or e))
        return
    restart()


def create_account(parent, mode="create"):
    """A guest makes an account (their guest settings move into it) or signs in to one they have."""
    from grimoire.loginview import AccountDialog
    dlg = AccountDialog(mode, parent)
    if dlg.exec() and dlg.result_value:
        _restart_as_new_session(dlg.result_value, parent, from_guest=(mode == "create"))


def sign_out(parent):
    from grimoire.loginview import restart
    if QMessageBox.question(parent, NAME, "Sign out? Grimoire Linux restarts at the sign-in screen. Your settings "
                            "stay on this PC.") != QMessageBox.StandardButton.Yes:
        return
    session.end()
    import os
    os.environ.pop("GRIMOIRE_PROFILE", None)
    restart()


class GuestBar(QFrame):
    """Shown on the home page while using Grimoire as a guest."""

    def __init__(self):
        super().__init__()
        self.setObjectName("Pending")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 12, 12)
        lay.setSpacing(12)
        badge = QLabel("GUEST")
        badge.setStyleSheet("color: #ffffff; background: #000000; border-radius: 4px; padding: 2px 8px; "
                            "font-size: 10px; font-weight: 700; letter-spacing: 2px;")
        lay.addWidget(badge)
        lay.addWidget(_label("Guest: settings won't be kept after the next guest start.", "PendingText"), 1)
        make = _button("Create account to keep them", lambda: create_account(self.window()), "Primary")
        if not accounts.BACKEND.configured():
            make.setEnabled(False)
            make.setToolTip("Accounts aren't set up yet in this copy of Grimoire Linux.")
        lay.addWidget(make)
        self.setVisible(bool((who := session.active()) and who.guest))


class AccountPanel(QWidget):
    """Settings → Account."""

    def __init__(self):
        from grimoire import prefs
        super().__init__()
        who = session.active()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        if who is None or who.guest:
            lay.addWidget(_label("You're using Grimoire Linux as a guest. Everything works, but your settings are "
                                 "cleared at the next guest start. Create an account to keep them (what you set "
                                 "up as a guest comes along), or sign in to one you have.", "Muted"))
            buttons = [_button("Sign in", lambda: create_account(self.window(), "signin")),
                       _button("Create account to keep them", lambda: create_account(self.window()), "Primary")]
            lay.addWidget(Row("Guest", "Settings won't be kept.", buttons))
            if not accounts.BACKEND.configured():
                for b in buttons:
                    b.setEnabled(False)
                lay.addWidget(_label("Accounts aren't set up yet in this copy of Grimoire Linux.", "Muted"))
            lay.addStretch(1)
            return
        lay.addWidget(_label("Your account keeps a copy of your settings on Grimoire's account server, so they "
                             "follow you to any PC you sign in on. Each account on this PC has its own settings.",
                             "Muted"))
        card = QFrame()
        card.setObjectName("Row")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 14, 14, 14)
        cl.setSpacing(14)
        initial = QLabel((who.username or "?")[:1].upper())
        initial.setFixedSize(48, 48)
        initial.setAlignment(Qt.AlignmentFlag.AlignCenter)
        initial.setStyleSheet("background: #f2f2f2; color: #000000; border-radius: 24px; font-size: 20px; "
                              "font-weight: 600;")
        cl.addWidget(initial)
        names = QVBoxLayout()
        names.setSpacing(2)
        names.addWidget(_label(who.username or "Signed in", "RowTitle"))
        names.addWidget(_label(PROVIDER_LINE.get(who.provider, PROVIDER_LINE["password"]), "Muted"))
        cl.addLayout(names, 1)
        cl.addWidget(_button("Sign out", lambda: sign_out(self.window())))
        lay.addWidget(card)

        self.auto = Switch()
        self.auto.setChecked(prefs.load()["cloud_sync"])
        self.auto.toggled.connect(lambda on: prefs.save(cloud_sync=on))
        lay.addWidget(Row("Save settings to your account automatically",
                          "When something changed: at start and every 30 minutes while Grimoire is open. "
                          "MuraL's wallpaper library stays on this PC.", [self.auto]))
        self.up = _button("Save now", self._upload, "Primary")
        self.down = _button("Restore…", self._download)
        lay.addWidget(Row("Your settings on the server", "Restoring is checked, previewed and safety-backed-up "
                          "like a backup file.", [self.down, self.up]))
        if who.provider in ("", "password"):
            lay.addWidget(Row("Recovery code", "Lost the one from sign-up? Get a new one; the old one stops "
                              "working.", [_button("New recovery code…", self._new_code)]))
        self.status = _label("", "Status")
        self.status.hide()
        lay.addWidget(self.status)
        lay.addStretch(1)

    def say(self, text, done=True):
        self.status.setText(text)
        self.status.setVisible(bool(text))
        self.up.setEnabled(done)
        self.down.setEnabled(done)

    def _upload(self):
        self.say("Saving…", False)
        run(upload_now, lambda ok, v: self.say("Saved to your account." if ok else v))

    def _download(self):
        def got(ok, value):
            if not ok:
                self.say(value)
            elif value is None:
                self.say("Nothing saved on your account yet.")
            else:
                restore_flow(self, value[0], "your account", self.say)
        self.say("Downloading…", False)
        run(lambda: accounts.BACKEND.load_settings(session.live()), got, (accounts.AccountError,))

    def _new_code(self):
        from grimoire.loginview import RecoveryCodeDialog
        if QMessageBox.question(self, NAME, "Make a new recovery code? The old one stops working.") \
                != QMessageBox.StandardButton.Yes:
            return

        def then(ok, value):
            if ok:
                who = session.active()
                RecoveryCodeDialog(who.username if who else "", value, self.window()).exec()
            else:
                self.say(value)
        run(lambda: accounts.BACKEND.new_recovery_code(session.live()), then, (accounts.AccountError,))


def upload_now(only_if_changed=False) -> bool:
    """Upload this profile's settings backup (without the wallpaper library). Returns whether it uploaded."""
    from grimoire import backup, paths
    data = backup.export_bytes(False)
    sha = hashlib.sha256(_comparable(data)).hexdigest()
    mark = paths.CACHE / f"cloud-sync-{paths.PROFILE or 'default'}.sha256"     # what was uploaded last
    try:
        last = mark.read_text().strip()
    except OSError:
        last = ""
    if only_if_changed and sha == last:
        return False
    accounts.BACKEND.save_settings(session.live(), data)
    mark.write_text(sha)
    return True


def _comparable(data: bytes) -> bytes:
    """The backup minus its timestamps (manifest "created", zip dates), so an unchanged profile hashes the same."""
    import io
    import json
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files = json.loads(z.read("manifest.json"))["files"]
    return "\n".join(sorted(f"{f['path']}:{f['sha256']}" for f in files)).encode()


class AutoSync(QObject):
    """Quiet uploads for a signed-in account with "automatically" on. Failures stay quiet (offline is normal)."""

    def __init__(self, parent):
        super().__init__(parent)
        who = session.active()
        if not who or who.guest or not accounts.BACKEND.configured():
            return
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30 * 60 * 1000)
        QTimer.singleShot(20_000, self.tick)

    def tick(self):
        from grimoire import prefs
        if prefs.load()["cloud_sync"]:
            run(lambda: upload_now(only_if_changed=True), lambda ok, v: None, (Exception,))
