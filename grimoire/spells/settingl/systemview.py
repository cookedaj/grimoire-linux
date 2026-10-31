# SPDX-License-Identifier: GPL-3.0-or-later
"""System pages: date & time, language & region, users, default apps, notifications and About this PC."""

from datetime import datetime

from PySide6.QtCore import QDateTime, QLocale, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QCompleter,
    QDateTimeEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from grimoire import NAME, i18n
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.spells.settingl import about, clock, defaults, kde, notify, region, users
from grimoire.spells.settingl.common import Panel, Row, combo, gray_icon, label
from grimoire.widgets import Switch

CTX = "grimoire.spells.settingl.systemview"


def _clear(lay):
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())


def _locale() -> QLocale:
    return QLocale()


# ---------------------------------------------------------------- date & time
class DateTimePanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        self._quiet = False
        self.time = label("", "Hero")
        self.date = label("", "Muted")
        self.col.addWidget(self.time)
        self.col.addWidget(self.date)
        self._clock = QTimer(self, interval=1000, timeout=self._tick)
        self.ntp = Switch()
        self.ntp.toggled.connect(self._ntp)
        self.ntp_row = Row(tr("grimoire.spells.settingl.systemview", "Set the time automatically"), "", self.ntp)
        self.col.addSpacing(8)
        self.col.addWidget(self.ntp_row)
        self.zone = combo(300)
        self.zone.setEditable(True)
        self.zone.setInsertPolicy(self.zone.InsertPolicy.NoInsert)
        self.zone.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.zone.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.zone_btn = QPushButton(tr("grimoire.spells.settingl.systemview", "Set"))
        self.zone_btn.clicked.connect(self._zone)
        self.zone_btn.setEnabled(False)
        self.zone.currentTextChanged.connect(lambda _: self._zone_ready())
        zone = QWidget()
        zl = QHBoxLayout(zone)
        zl.setContentsMargins(0, 0, 0, 0)
        zl.addWidget(self.zone)
        zl.addWidget(self.zone_btn)
        self.zone_row = Row(tr("grimoire.spells.settingl.systemview", "Time zone"), "", zone)
        self.col.addWidget(self.zone_row)
        self.manual = QDateTimeEdit()
        self.manual.setCalendarPopup(True)
        self.manual.setDisplayFormat(_locale().dateTimeFormat(QLocale.FormatType.ShortFormat))
        self.manual_btn = QPushButton(tr("grimoire.spells.settingl.systemview", "Set"))
        self.manual_btn.clicked.connect(self._manual)
        man = QWidget()
        ml = QHBoxLayout(man)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(self.manual)
        ml.addWidget(self.manual_btn)
        self.manual_row = Row(
            tr("grimoire.spells.settingl.systemview", "Date and time"),
            tr("grimoire.spells.settingl.systemview", "Turn off automatic time to set it by hand."),
            man,
        )
        self.col.addWidget(self.manual_row)
        self.note(
            tr(
                "grimoire.spells.settingl.systemview",
                "Changing these is for the whole PC, so the system asks for your password, as it does in "
                "KDE's own Date & Time settings.",
            )
        )
        self.kde_links(["kcm_clock", "kcm_nighttime", "kcm_regionandlang"])
        self.finish()
        self._zones_loaded = False

    def read(self):
        d = clock.read()
        if not self._zones_loaded:
            d["zones"] = clock.zones()
        return d

    def fill(self, d):
        self._quiet = True
        if "zones" in d and d["zones"]:
            self._zones_loaded = True
            self.zone.clear()
            self.zone.addItems(d["zones"])
        if not self.zone.hasFocus():
            self.zone.setCurrentText(d["timezone"])
        self.ntp.setChecked(d["ntp"])
        self.ntp.setEnabled(d["can_ntp"])
        self.ntp_row.set_sub(
            (
                tr("grimoire.spells.settingl.systemview", "On, and in sync with internet time.")
                if d["synced"]
                else tr("grimoire.spells.settingl.systemview", "On, not in sync yet.")
            )
            if d["ntp"]
            else tr("grimoire.spells.settingl.systemview", "Off: the clock keeps the time you set.")
        )
        self.zone_row.set_sub(
            tr("grimoire.spells.settingl.systemview", "Now {zone}").format(zone=i18n.ltr(d["timezone"]))
            if d["timezone"]
            else ""
        )
        self._zone_ready()
        self.manual_row.setEnabled(not d["ntp"])
        if not self.manual.hasFocus():
            self.manual.setDateTime(QDateTime.currentDateTime())
        self._quiet = False
        if not d["ok"]:
            self.host.say(tr("grimoire.spells.settingl.systemview", "systemd's time service didn't answer."))

    def _tick(self):
        loc = _locale()
        now = QDateTime.currentDateTime()
        self.time.setText(loc.toString(now.time(), QLocale.FormatType.ShortFormat))
        self.date.setText(loc.toString(now.date(), QLocale.FormatType.LongFormat))

    def showEvent(self, e):
        super().showEvent(e)
        self._tick()
        self._clock.start()

    def hideEvent(self, e):
        self._clock.stop()
        super().hideEvent(e)

    def _ntp(self, on: bool):
        if not self._quiet:
            self.act(
                tr("grimoire.spells.settingl.systemview", "Automatic time"),
                lambda: (
                    clock.set_ntp(on)
                    or (
                        tr("grimoire.spells.settingl.systemview", "on")
                        if on
                        else tr("grimoire.spells.settingl.systemview", "off")
                    )
                ),
            )

    def _zone_ready(self):
        """Set only for a known zone that isn't the one in use."""
        z = self.zone.currentText().strip()
        now = (self.data or {}).get("timezone", "")
        self.zone_btn.setEnabled(bool(z) and z != now and self.zone.findText(z) >= 0)

    def _zone(self):
        z = self.zone.currentText().strip()
        self.act(tr("grimoire.spells.settingl.systemview", "Time zone"), lambda: clock.set_timezone(z) or i18n.ltr(z))

    def _manual(self):
        when = self.manual.dateTime().toPython()
        self.act(
            tr("grimoire.spells.settingl.systemview", "Date and time"),
            lambda: clock.set_time(when) or tr("grimoire.spells.settingl.systemview", "set"),
        )


# ---------------------------------------------------------------- language & region
def _lang_name(code: str) -> str:
    loc = QLocale(code)
    native = loc.nativeLanguageName()
    if "_" in code and loc.nativeTerritoryName():
        native = f"{native} ({loc.nativeTerritoryName()})"
    return f"{native.capitalize() if native else code} · {code}"


class RegionPanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        self._quiet = False
        self.section(NAME)
        self.glang = combo(220)
        for code, native in i18n.LANGUAGES.items():
            self.glang.addItem(native, code)
        self.glang.setCurrentIndex(max(0, self.glang.findData(i18n.current())))
        self.glang.activated.connect(self._grimoire)
        self.glang_row = Row(tr("grimoire.spells.settingl.systemview", "Language of Grimoire Linux"), "", self.glang)
        self.col.addWidget(self.glang_row)
        self._grimoire_note()
        self.section("KDE Plasma")
        self.plang = combo(280)
        self.plang.activated.connect(self._plasma_lang)
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.systemview", "Language of the desktop"),
                tr("grimoire.spells.settingl.systemview", "Plasma and KDE apps use it from your next login."),
                self.plang,
            )
        )
        self.fmt = combo(280)
        self.fmt.activated.connect(self._formats)
        self.fmt_row = Row(tr("grimoire.spells.settingl.systemview", "Formats"), "", self.fmt)
        self.col.addWidget(self.fmt_row)
        self.sys_row = Row(tr("grimoire.spells.settingl.systemview", "System language"), "", None)
        self.col.addWidget(self.sys_row)
        self.note(
            tr(
                "grimoire.spells.settingl.systemview",
                "Only languages and formats this PC already has are listed. KDE's Region & Language "
                "settings can add others (that needs your password).",
            )
        )
        self.kde_links(["kcm_regionandlang", "kcmspellchecking", "kcm_keyboard"])
        self.finish()

    def read(self):
        return {"now": region.read(), "languages": region.languages(), "formats": region.formats()}

    def fill(self, d):
        self._quiet = True
        now = d["now"]
        self.plang.clear()
        self.plang.addItem(tr("grimoire.spells.settingl.systemview", "Same as the system"), "")
        for code in d["languages"]:
            self.plang.addItem(_lang_name(code), code)
        first = now["language"].split(":")[0]
        self.plang.setCurrentIndex(max(0, self.plang.findData(first)))
        self.fmt.clear()
        self.fmt.addItem(tr("grimoire.spells.settingl.systemview", "Same as the language"), "")
        for f in d["formats"]:
            self.fmt.addItem(_lang_name(f.split(".")[0]), f)
        self.fmt.setCurrentIndex(max(0, self.fmt.findData(now["formats"])))
        self._sample(now["formats"] or now["system"])
        self.sys_row.set_sub(
            tr("grimoire.spells.settingl.systemview", "{locale}, for the login screen and new users").format(
                locale=i18n.ltr(now["system"])
            )
            if now["system"]
            else ""
        )
        self._quiet = False

    def _sample(self, name: str):
        loc = QLocale(name.split(".")[0]) if name else QLocale.system()
        now = QDateTime.currentDateTime()
        bits = [
            loc.toString(now, QLocale.FormatType.ShortFormat),
            loc.toString(1234567.89, "f", 2),
            loc.toCurrencyString(1234.5),
        ]
        self.fmt_row.set_sub(
            tr("grimoire.spells.settingl.systemview", "Numbers, dates and money: {sample}").format(
                sample=i18n.isolate("   ".join(bits))
            )
        )

    def _grimoire(self, _i):
        try:
            i18n.choose(self.glang.currentData())
        except (OSError, ValueError) as e:
            self.host.say(tr("grimoire.spells.settingl.systemview", "Couldn't change it: {error}").format(error=e))
        self._grimoire_note()
        from grimoire.settingsview import offer_restart

        offer_restart(self)

    def _grimoire_note(self):
        self.glang_row.set_sub(
            tr("grimoire.spells.settingl.systemview", "Grimoire Linux switches to {language} when it restarts.").format(
                language=i18n.LANGUAGES[i18n.current()]
            )
            if i18n.needs_restart()
            else tr(
                "grimoire.spells.settingl.systemview",
                "The language of Grimoire Linux and its spells. Changing it needs a restart.",
            )
        )

    def _plasma_lang(self, _i):
        if self._quiet:
            return
        code = self.plang.currentData()
        self.act(
            tr("grimoire.spells.settingl.systemview", "Language of the desktop"),
            lambda: (
                region.set_language(code)
                or tr("grimoire.spells.settingl.systemview", "saved: it applies from your next login")
            ),
        )

    def _formats(self, _i):
        if self._quiet:
            return
        f = self.fmt.currentData()
        self._sample(f)
        self.act(
            tr("grimoire.spells.settingl.systemview", "Formats"),
            lambda: (
                region.set_formats(f)
                or tr("grimoire.spells.settingl.systemview", "saved: it applies from your next login")
            ),
        )


# ---------------------------------------------------------------- users
def _avatar(path: str, size: int = 72) -> QPixmap | None:
    pm = QPixmap(path) if path else QPixmap()
    if pm.isNull():
        return None
    pm = pm.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
    )
    gray = pm.toImage().convertToFormat(pm.toImage().Format.Format_Grayscale8)
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    p.setClipPath(clip)
    p.drawImage(0, 0, gray)
    p.end()
    return out


class UsersPanel(Panel):
    STALE = 30.0

    def __init__(self, host):
        super().__init__(host)
        card = QWidget()
        cl = QHBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(18)
        self.pic = QLabel()
        self.pic.setFixedSize(72, 72)
        cl.addWidget(self.pic)
        text = QVBoxLayout()
        self.name = label("", "SectionTitle", plain=True)
        self.who = label("", "Muted", plain=True)
        text.addStretch(1)
        text.addWidget(self.name)
        text.addWidget(self.who)
        text.addStretch(1)
        cl.addLayout(text, 1)
        self.col.addWidget(card)
        self.facts = QVBoxLayout()
        self.facts.setSpacing(8)
        self.col.addLayout(self.facts)
        self.others_title = self.section(tr("grimoire.spells.settingl.systemview", "Other people on this PC"))
        self.others = QVBoxLayout()
        self.others.setSpacing(8)
        self.col.addLayout(self.others)
        self.note(
            tr(
                "grimoire.spells.settingl.systemview",
                "To add people, change a password or a picture, use KDE's Users settings.",
            )
        )
        self.kde_links(["kcm_users", "kcm_sddm", "kcm_screenlocker", "kcm_kwallet5", "kcm_kaccounts"])
        self.finish()

    def read(self):
        return users.read()

    def fill(self, d):
        me = d["me"]
        pm = _avatar(me.get("icon", ""))
        self.pic.setPixmap(pm if pm else glyph("login", 64).pixmap(64, 64))
        self.name.setText(me.get("name") or me.get("user", ""))
        role = (
            tr("grimoire.spells.settingl.systemview", "Administrator")
            if me.get("admin")
            else tr("grimoire.spells.settingl.systemview", "Standard user")
        )
        self.who.setText(" · ".join(x for x in (me.get("user", ""), role) if x))
        _clear(self.facts)
        facts = [
            (tr("grimoire.spells.settingl.systemview", "Home folder"), me.get("home", "")),
            (tr("grimoire.spells.settingl.systemview", "Shell"), me.get("shell", "")),
        ]
        if me.get("last_login"):
            when = QDateTime.fromSecsSinceEpoch(int(me["last_login"]))
            facts.append(
                (
                    tr("grimoire.spells.settingl.systemview", "Last login"),
                    _locale().toString(when, QLocale.FormatType.ShortFormat),
                )
            )
        if me.get("groups"):
            facts.append((tr("grimoire.spells.settingl.systemview", "Groups"), ", ".join(me["groups"])))
        if me.get("auto_login"):
            facts.append(
                (
                    tr("grimoire.spells.settingl.systemview", "Logs in automatically"),
                    tr("grimoire.spells.settingl.systemview", "Yes"),
                )
            )
        for title, value in facts:
            if value:
                row = Row(title, value)
                row.sub.setTextFormat(Qt.TextFormat.PlainText)
                row.sub.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.facts.addWidget(row)
        _clear(self.others)
        for o in d["others"]:
            role = (
                tr("grimoire.spells.settingl.systemview", "Administrator")
                if o.get("admin")
                else tr("grimoire.spells.settingl.systemview", "Standard user")
            )
            pm = _avatar(o.get("icon", ""), 28)
            row = Row(o.get("name") or o["user"], " · ".join(x for x in (o["user"], role) if x), None, None)
            row.title.setTextFormat(Qt.TextFormat.PlainText)
            if pm:
                ic = QLabel()
                ic.setPixmap(pm)
                row.layout().insertWidget(0, ic)
            self.others.addWidget(row)
        self.others_title.setVisible(bool(d["others"]))


# ---------------------------------------------------------------- default apps
class DefaultsPanel(Panel):
    STALE = 10.0

    def __init__(self, host):
        super().__init__(host)
        self.note(
            tr(
                "grimoire.spells.settingl.systemview",
                "Which app opens each kind of thing. Nothing here changes until you pick an app and press Set.",
            )
        )
        self.rows: dict[str, tuple] = {}
        for kind, title, _ in defaults.KINDS:
            c = combo(260)
            b = QPushButton(tr("grimoire.spells.settingl.systemview", "Set"))
            b.setEnabled(False)
            b.clicked.connect(lambda _=False, k=kind: self._set(k))
            c.activated.connect(lambda _i, k=kind: self._picked(k))
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.addWidget(c)
            wl.addWidget(b)
            row = Row(tr("grimoire.spells.settingl.defaults", title), "", w)
            self.col.addWidget(row)
            self.rows[kind] = (row, c, b)
        self.kde_links(["kcm_componentchooser", "kcm_filetypes"])
        self.finish()

    def read(self):
        return defaults.read(kcms_lang())

    def fill(self, d):
        apps = d["apps"]
        for kind, (row, c, b) in self.rows.items():
            cur = d["current"].get(kind, "")
            ids = [i for i in d["choices"][kind] if not apps[i]["nodisplay"] or i == cur]
            if cur and cur not in ids and cur in apps:
                ids.insert(0, cur)
            names = [apps[i]["name"] for i in ids]
            c.clear()
            for i in ids:
                name = apps[i]["name"]
                text = f"{name} ({i.removesuffix('.desktop')})" if names.count(name) > 1 else name
                icon = gray_icon(apps[i]["icon"], 16)
                c.addItem(icon, text, i) if icon else c.addItem(text, i)
            if cur and cur not in apps:
                c.addItem(cur.removesuffix(".desktop"), cur)
            c.setCurrentIndex(c.findData(cur))
            row.set_sub(
                tr("grimoire.spells.settingl.systemview", "Now: {app}").format(
                    app=i18n.isolate(apps[cur]["name"] if cur in apps else cur)
                )
                if cur
                else tr("grimoire.spells.settingl.systemview", "No default yet")
            )
            b.setEnabled(False)

    def _picked(self, kind: str):
        row, c, b = self.rows[kind]
        b.setEnabled(bool(self.data) and c.currentData() != self.data["current"].get(kind))

    def _set(self, kind: str):
        row, c, b = self.rows[kind]
        app = c.currentData()
        if not app or not self.data:
            return
        apps = self.data["apps"]
        b.setEnabled(False)
        title = next(t for k, t, _ in defaults.KINDS if k == kind)
        self.act(
            tr("grimoire.spells.settingl.defaults", title),
            lambda: (
                defaults.set_default(kind, app, apps)
                or tr("grimoire.spells.settingl.systemview", "now {app}").format(app=i18n.isolate(apps[app]["name"]))
            ),
        )


def kcms_lang() -> str:
    code = i18n.loaded() or i18n.current()
    return {"pt": "pt_BR"}.get(code, code)


# ---------------------------------------------------------------- notifications
DND_FOR = [
    (60, tr_noop("grimoire.spells.settingl.systemview", "For 1 hour")),
    (-1, tr_noop("grimoire.spells.settingl.systemview", "Until tomorrow morning")),
    (0, tr_noop("grimoire.spells.settingl.systemview", "Until I turn it off")),
]


class NotificationsPanel(Panel):
    POLL = 10000

    def __init__(self, host):
        super().__init__(host)
        self._quiet = False
        self.dnd = Switch()
        self.dnd.toggled.connect(self._dnd)
        self.dnd_for = combo(200)
        for m, text in DND_FOR:
            self.dnd_for.addItem(tr("grimoire.spells.settingl.systemview", text), m)
        w = QWidget()
        wl = QHBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(self.dnd_for)
        wl.addWidget(self.dnd)
        self.dnd_row = Row(tr("grimoire.spells.settingl.systemview", "Do Not Disturb"), "", w)
        self.col.addWidget(self.dnd_row)
        self.section(tr("grimoire.spells.settingl.systemview", "Apps"))
        self.note(
            tr(
                "grimoire.spells.settingl.systemview",
                "Apps that have sent notifications. Popups show on screen; the history keeps them in the "
                "panel's notification list.",
            )
        )
        head = QHBoxLayout()
        head.addStretch(1)
        for text in (
            tr("grimoire.spells.settingl.systemview", "Popups"),
            tr("grimoire.spells.settingl.systemview", "History"),
        ):
            h = label(text, "NavSection")
            h.setMinimumWidth(64)
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.addWidget(h)
        head.addSpacing(18)
        self.col.addLayout(head)
        self.apps = QVBoxLayout()
        self.apps.setSpacing(8)
        self.col.addLayout(self.apps)
        self.keys = None
        self.kde_links(["kcm_notifications", "kcm_soundtheme", "kcm_notificationhelper"])
        self.finish()

    def read(self):
        d = notify.read()
        names = defaults.apps(kcms_lang())
        for a in d["apps"]:
            e = names.get(a["id"] + ".desktop") or next(
                (x for x in names.values() if x["id"].lower() == a["id"].lower() + ".desktop"), None
            )
            a["name"] = e["name"] if e else a["id"]
            a["icon"] = e["icon"] if e else a["id"]
        d["apps"] = sorted((a for a in d["apps"] if not a["id"].startswith("@")), key=lambda a: a["name"].casefold())
        return d

    def fill(self, d):
        self._quiet = True
        self.dnd.setChecked(d["dnd"])
        self.dnd_for.setEnabled(not d["dnd"])
        if d["dnd"] and d["until"] and d["until"].year - datetime.now().year < 1:
            when = QDateTime(d["until"])
            sub = tr("grimoire.spells.settingl.systemview", "On until {time}").format(
                time=_locale().toString(when, QLocale.FormatType.ShortFormat)
            )
        elif d["dnd"]:
            sub = tr("grimoire.spells.settingl.systemview", "On until you turn it off")
        elif d["inhibited"]:
            sub = tr(
                "grimoire.spells.settingl.systemview",
                "An app is holding notifications back right now (a game or a full-screen video).",
            )
        else:
            sub = tr("grimoire.spells.settingl.systemview", "Holds popups back; they still go to the history.")
        self.dnd_row.set_sub(sub)
        keys = tuple((a["id"], a["popups"], a["history"]) for a in d["apps"])
        if keys != self.keys:
            self.keys = keys
            _clear(self.apps)
            if not d["apps"]:
                self.apps.addWidget(
                    label(tr("grimoire.spells.settingl.systemview", "No app has sent a notification yet."), "Muted")
                )
            for a in d["apps"]:
                pop, hist = Switch(), Switch()
                pop.setChecked(a["popups"])
                hist.setChecked(a["history"])
                pop.toggled.connect(lambda on, i=a["id"], n=a["name"]: self._app(i, n, "ShowPopups", on))
                hist.toggled.connect(lambda on, i=a["id"], n=a["name"]: self._app(i, n, "ShowInHistory", on))
                w = QWidget()
                wl = QHBoxLayout(w)
                wl.setContentsMargins(0, 0, 0, 0)
                wl.setSpacing(18)
                wl.addWidget(pop)
                wl.addWidget(hist)
                row = Row(a["name"], "", w, gray_icon(a["icon"]) or glyph("bell", 24))
                row.title.setTextFormat(Qt.TextFormat.PlainText)
                self.apps.addWidget(row)
        self._quiet = False

    def _dnd(self, on: bool):
        if self._quiet:
            return
        m = self.dnd_for.currentData()
        mins = None if not on else (notify.until_morning() if m == -1 else m)
        self.dnd_for.setEnabled(not on)
        self.act(
            tr("grimoire.spells.settingl.systemview", "Do Not Disturb"),
            lambda: (
                notify.set_dnd(mins)
                or (
                    tr("grimoire.spells.settingl.systemview", "on")
                    if on
                    else tr("grimoire.spells.settingl.systemview", "off")
                )
            ),
        )

    def _app(self, app: str, name: str, key: str, on: bool):
        if not self._quiet:
            self.act(name, lambda: notify.set_app(app, key, on) or "", quiet=True)


# ---------------------------------------------------------------- about
class AboutPanel(Panel):
    STALE = 60.0

    def __init__(self, host):
        super().__init__(host)
        self.os = label("", "Hero", plain=True)
        self.col.addWidget(self.os)
        self.sub = label("", "Muted", plain=True)
        self.col.addWidget(self.sub)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(8)
        box = QFrame()
        box.setObjectName("Row")
        box.setLayout(self.grid)
        self.col.addSpacing(10)
        self.col.addWidget(box)
        btns = QHBoxLayout()
        copy = QPushButton(tr("grimoire.spells.settingl.systemview", "Copy details"))
        copy.clicked.connect(self._copy)
        btns.addWidget(copy)
        more = QPushButton(tr("grimoire.spells.settingl.systemview", "More in Info Center"))
        more.setVisible(kde.have("kinfocenter"))
        more.clicked.connect(
            lambda: self.host.act("Info Center", lambda: kde.LAUNCH(["kinfocenter"]) or "", quiet=True)
        )
        btns.addWidget(more)
        btns.addStretch(1)
        self.col.addLayout(btns)
        self.kde_links(["kcm_feedback", "kcm_updates"])
        self.finish()
        self.lines: list[tuple[str, str]] = []

    def read(self):
        return about.read()

    def fill(self, d):
        from grimoire.fsutil import human

        self.os.setText(d["os"])
        self.sub.setText(" · ".join(x for x in (d["host"], f"KDE Plasma {d['plasma']}" if d["plasma"] else "") if x))
        host = (tr("grimoire.spells.settingl.systemview", "Computer name"), d["host"])
        rows = [
            (tr("grimoire.spells.settingl.systemview", "SOFTWARE"), None),
            ("KDE Plasma", d["plasma"]),
            ("KDE Frameworks", d["frameworks"]),
            ("Qt", d["qt"]),
            (tr("grimoire.spells.settingl.systemview", "Kernel"), f"{d['kernel']} ({d['arch']})"),
            (
                tr("grimoire.spells.settingl.systemview", "Graphics platform"),
                d["session"].capitalize() if d["session"] else "",
            ),
            (tr("grimoire.spells.settingl.systemview", "HARDWARE"), None),
            (tr("grimoire.spells.settingl.systemview", "Made by"), d["vendor"]),
            (tr("grimoire.spells.settingl.systemview", "Model"), d["product"]),
            (
                tr("grimoire.spells.settingl.systemview", "Processor"),
                tr("grimoire.spells.settingl.systemview", "{cpu} · %n thread(s)", n=d["threads"]).format(
                    cpu=i18n.isolate(d["cpu"])
                )
                if d["cpu"]
                else "",
            ),
            (tr("grimoire.spells.settingl.systemview", "Memory"), human(d["memory"]) if d["memory"] else ""),
            (tr("grimoire.spells.settingl.systemview", "Graphics"), ", ".join(d["gpus"])),
            (tr("grimoire.spells.settingl.systemview", "System disk"), human(d["disk"]) if d["disk"] else ""),
            host,
        ]
        _clear(self.grid)
        self.grid.setContentsMargins(20, 16, 20, 16)
        self.lines = []
        r = 0
        for title, value in rows:
            if value is None:
                head = label(title, "NavSection")
                self.grid.addWidget(head, r, 0, 1, 2)
                self.lines.append(("", ""))
                r += 1
                continue
            if not value:
                continue
            t = label(title, "Muted")
            v = label(value, "", plain=True)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.grid.addWidget(t, r, 0)
            self.grid.addWidget(v, r, 1)
            if title is not host[0]:  # the copied details get shared: the computer's name stays out of them
                self.lines.append((title, value))
            r += 1
        self.grid.setColumnStretch(1, 1)
        self.data = d

    def _copy(self):
        if not self.data:
            return
        text = "\n".join(f"{t}: {v}" if t else "" for t, v in self.lines).strip()
        QGuiApplication.clipboard().setText(f"{self.data['os']}\n{text}\n")
        self.host.say(tr("grimoire.spells.settingl.systemview", "Copied the details."))
