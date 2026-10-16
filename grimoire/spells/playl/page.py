# SPDX-License-Identifier: GPL-3.0-or-later
"""PlayL page: Now playing (the stage + the queue), the music library and settings.

The player lives as long as the page: switching to another spell in the hub keeps the music going. Everything
that reads files (library scan, covers, resume points, previews) runs on worker threads.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QMenu, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from grimoire.glyphs import glyph
from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.playl import art, media, mpv
from grimoire.spells.playl.libraryview import LibraryPanel
from grimoire.spells.playl.queueview import QueuePanel
from grimoire.spells.playl.stage import Stage
from grimoire.spells.systeml.page import _label
from grimoire.widgets import Switch

PANELS = [("now", tr_noop("grimoire.spells.playl.page", "Now playing"), "playl"),
          ("albums", tr_noop("grimoire.spells.playl.page", "Albums"), "grid"),
          ("artists", tr_noop("grimoire.spells.playl.page", "Artists"), "login"),
          ("songs", tr_noop("grimoire.spells.playl.page", "Songs"), "music"),
          ("settings", tr_noop("grimoire.spells.playl.page", "Settings"), "gear")]
SEEK_STEP, SEEK_BIG, VOLUME_STEP = 5.0, 30.0, 5
# (keys, what they do) for the settings panel's list
KEYS = [("Space", tr_noop("grimoire.spells.playl.page", "Play or pause")),
        ("← →", tr_noop("grimoire.spells.playl.page", "Back or ahead 5 seconds (Shift: 30)")),
        ("↑ ↓", tr_noop("grimoire.spells.playl.page", "Volume")),
        ("F", tr_noop("grimoire.spells.playl.page", "Fullscreen (Esc leaves it)")),
        ("M", tr_noop("grimoire.spells.playl.page", "Mute")),
        ("N  P", tr_noop("grimoire.spells.playl.page", "Next or previous")),
        ("[  ]", tr_noop("grimoire.spells.playl.page", "Slower or faster (Backspace: normal speed)")),
        ("Q", tr_noop("grimoire.spells.playl.page", "Show or hide the queue")),
        ("Ctrl+O", tr_noop("grimoire.spells.playl.page", "Open files"))]


def _row(title: str, sub: str, *controls) -> QFrame:
    row = QFrame()
    row.setObjectName("Row")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(18, 12, 16, 12)
    lay.setSpacing(12)
    text = QVBoxLayout()
    text.setSpacing(3)
    text.addWidget(_label(title, "RowTitle"))
    if sub:
        text.addWidget(_label(sub, "Muted", wrap=True))
    lay.addLayout(text, 1)
    for c in controls:
        lay.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


def track_label(t: dict) -> str:
    """How an audio or subtitle track reads in its menu: its title, language and codec."""
    bits = [t.get("title") or "", (t.get("lang") or "").upper(), t.get("codec") or ""]
    if t.get("type") == "audio" and t.get("demux-channel-count"):
        bits.append(tr("grimoire.spells.playl.page", "%n channel(s)", n=int(t["demux-channel-count"])))
    if t.get("external"):
        bits.append(tr("grimoire.spells.playl.page", "from a file"))
    text = " · ".join(b for b in bits if b)
    return text or tr("grimoire.spells.playl.page", "Track {n}").format(n=t.get("id"))


class FullWindow(QWidget):
    """The stage on its own, fullscreen."""
    leave = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PlayL")
        self.setStyleSheet("background: #000000;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

    def closeEvent(self, e):
        self.leave.emit()
        super().closeEvent(e)


class SettingsPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(10)
        s = page.settings
        col.addWidget(_label(tr("grimoire.spells.playl.page", "PLAYBACK"), "NavSection"))
        self.resume = Switch()
        self.resume.setChecked(s["resume"])
        self.resume.toggled.connect(self._resume)
        forget = QPushButton(tr("grimoire.spells.playl.page", "Forget all"))
        forget.clicked.connect(self._forget)
        col.addWidget(_row(tr("grimoire.spells.playl.page", "Resume where you left off"),
                           tr("grimoire.spells.playl.page", "Files longer than a minute start again where you "
                                                            "stopped them."), forget, self.resume))
        self.hw = Switch()
        self.hw.setChecked(s["hwdec"])
        self.hw.toggled.connect(self._hwdec)
        self.hw_line = _label("", "Muted", wrap=True)
        col.addWidget(_row(tr("grimoire.spells.playl.page", "Hardware decoding"),
                           tr("grimoire.spells.playl.page", "Decode video on the graphics card when it can "
                                                            "(NVDEC, VA-API, Vulkan). Turn it off if a video "
                                                            "shows glitches."), self.hw))
        col.addWidget(self.hw_line)
        col.addSpacing(8)
        col.addWidget(_label(tr("grimoire.spells.playl.page", "LIBRARY FOLDERS"), "NavSection"))
        self.folders = QListWidget()
        self.folders.setObjectName("Places")
        self.folders.setMaximumHeight(110)
        col.addWidget(self.folders)
        btns = QHBoxLayout()
        add = QPushButton(glyph("plus", 16), " " + tr("grimoire.spells.playl.page", "Add folder…"))
        add.clicked.connect(self._add)
        rm = QPushButton(tr("grimoire.spells.playl.page", "Remove"))
        rm.clicked.connect(self._remove)
        btns.addWidget(add)
        btns.addWidget(rm)
        btns.addStretch(1)
        col.addLayout(btns)
        col.addSpacing(8)
        col.addWidget(_label(tr("grimoire.spells.playl.page", "KEYS"), "NavSection"))
        for keys, what in KEYS:
            r = QHBoxLayout()
            k = QLabel(keys)
            k.setObjectName("Key")
            k.setMinimumWidth(64)
            k.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r.addWidget(k)
            r.addWidget(_label(tr("grimoire.spells.playl.page", what)), 1)
            col.addLayout(r)
        col.addSpacing(8)
        col.addWidget(_label(tr("grimoire.spells.playl.page", "ABOUT"), "NavSection"))
        col.addWidget(_label(tr("grimoire.spells.playl.page",
                                "PlayL plays through libmpv, the engine behind mpv and Haruna. Its volume is its "
                                "own stream in PipeWire, the same one AudioL and Plasma's volume applet show. Once "
                                "its launcher is installed (Install on its card on the home page) it shows up in "
                                "Open With for videos and music; it never makes itself the default player."),
                             "Muted", wrap=True))
        col.addStretch(1)
        self.setWidget(inner)
        self._fill_folders()

    def showEvent(self, e):
        p = self.page.player
        cur = p.core.get("hwdec-current") if p else None
        self.hw_line.setText(tr("grimoire.spells.playl.page", "Decoding this video with: {method}").format(
            method=ltr(cur)) if cur and cur != "no" else "")
        self.hw_line.setVisible(bool(cur and cur != "no"))
        super().showEvent(e)

    def _fill_folders(self):
        self.folders.clear()
        for f in self.page.settings["library"]:
            self.folders.addItem(f)

    def _resume(self, on):
        self.page.save(resume=on)

    def _forget(self):
        if self.page.player:
            self.page.player.forget_positions()
        self.page.say(tr("grimoire.spells.playl.page", "Forgot every resume point"))

    def _hwdec(self, on):
        self.page.save(hwdec=on)
        if self.page.player:
            try:
                self.page.player.core.set("hwdec", "auto-safe" if on else "no")
            except mpv.MpvError:
                pass

    def _add(self):
        d = QFileDialog.getExistingDirectory(self, tr("grimoire.spells.playl.page", "Add a music folder"),
                                             str(Path.home()))
        if not d:
            return
        home = str(Path.home())
        d = "~" + d[len(home):] if d == home or d.startswith(home + "/") else d
        lib = self.page.settings["library"]
        if d not in lib:
            self.page.save(library=lib + [d])
            self._fill_folders()
            self.page.library.scan(force=True)

    def _remove(self):
        it = self.folders.currentItem()
        if not it:
            return
        lib = [f for f in self.page.settings["library"] if f != it.text()]
        self.page.save(library=lib)
        self._fill_folders()
        self.page.library.scan(force=True)


class PlayLPage(QWidget):
    _art_ready = Signal(str, object)

    def __init__(self, standalone: bool = False):
        super().__init__()
        self.setObjectName("Page")
        self.standalone = standalone
        self.settings = media.load()
        self.player = None
        self.mpris = None
        self.full: FullWindow | None = None
        self.art_path = None
        problem = ""
        if not mpv.available():
            problem = tr("grimoire.spells.playl.page", "PlayL plays through libmpv, which isn't installed. "
                                                       "Install it with:")
        else:
            try:
                from grimoire.spells.playl.player import Player
                self.player = Player(self.settings)
            except mpv.MpvError as e:
                problem = tr("grimoire.spells.playl.page", "libmpv didn't start: {error}").format(error=isolate(e))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setMinimumWidth(210)
        nav.setMaximumWidth(300)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("PlayL", "Title"))
        nl.addSpacing(12)
        self.nav = {}
        for pid, name, icon in PANELS:
            if pid == "now":
                nl.addWidget(_label(tr("grimoire.spells.playl.page", "PLAYER"), "NavSection"))
            elif pid == "albums":
                nl.addSpacing(8)
                nl.addWidget(_label(tr("grimoire.spells.playl.page", "MUSIC"), "NavSection"))
            elif pid == "settings":
                nl.addSpacing(8)
            b = QPushButton(glyph(icon, 18), "  " + tr("grimoire.spells.playl.page", name).replace("&", "&&"))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, p=pid: self.show_panel(p))
            nl.addWidget(b)
            self.nav[pid] = b
        nl.addStretch(1)
        self.foot = _label("", "Tiny")
        self.foot.setTextFormat(Qt.TextFormat.PlainText)
        self.foot.setWordWrap(True)
        nl.addWidget(self.foot)
        root.addWidget(nav)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        # now playing: the stage and the queue, edge to edge
        self.now = QWidget()
        self.now_lay = QHBoxLayout(self.now)
        self.now_lay.setContentsMargins(0, 0, 0, 0)
        self.now_lay.setSpacing(0)
        self.stage = Stage(message=problem, command=mpv.APT if problem and not mpv.available() else "")
        self.now_lay.addWidget(self.stage, 1)
        self.open_menu = QMenu(self)
        self.open_menu.addAction(tr("grimoire.spells.playl.page", "Files…"), lambda: self.open_files(False))
        self.open_menu.addAction(tr("grimoire.spells.playl.page", "Folder…"), lambda: self.open_folder(False))
        self.open_menu.addAction(tr("grimoire.spells.playl.page", "Address…"), lambda: self.open_url(False))
        self.queue = QueuePanel(self.player, self.open_menu) if self.player else None
        if self.queue:
            self.now_lay.addWidget(self.queue)
            self.queue.setVisible(self.settings["queue_open"])
        self.stack.addWidget(self.now)
        # library and settings, with the usual margins and heading
        self.library = LibraryPanel()
        self.library.play.connect(self.play_entries)
        self.library.enqueue.connect(self.enqueue)
        self.settings_panel = SettingsPanel(self)
        self.framed = {}
        for key, w in (("library", self.library), ("settings", self.settings_panel)):
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(32, 26, 32, 18)
            lay.setSpacing(14)
            heading = _label("", "PageHeading")
            lay.addWidget(heading)
            lay.addWidget(w, 1)
            self.framed[key] = (box, heading)
            self.stack.addWidget(box)

        st = self.stage
        st.empty.open_files.connect(lambda: self.open_files(True))
        st.empty.open_folder.connect(lambda: self.open_folder(True))
        st.empty.open_url.connect(lambda: self.open_url(True))
        st.dropped.connect(lambda paths: self.open_paths(paths))
        st.double_clicked.connect(self.toggle_full)
        c = st.controls
        c.full.clicked.connect(self.toggle_full)
        self._art_ready.connect(self._art_loaded)
        self._opened.connect(self._got_entries)
        if self.player:
            self._wire()
        self._keys(self)
        self.show_panel("now")
        self._status()

    # ------------------------------------------------------------ wiring
    def _wire(self):
        p, st, c = self.player, self.stage, self.stage.controls
        renderer = p.start_video()
        st.video.attach(renderer)
        c.play.clicked.connect(p.toggle)
        c.prev.clicked.connect(p.previous)
        c.next.clicked.connect(p.next)
        c.bar.seek.connect(lambda t: p.seek(t))
        c.bar.scrub.connect(lambda t: p.cmd("seek", f"{t:.2f}", "absolute+keyframes"))
        c.mute.toggled.connect(p.set_muted)
        c.volume.valueChanged.connect(p.set_volume)
        c.queue.setChecked(self.settings["queue_open"])
        c.queue.toggled.connect(self.show_queue)
        c.shuffle.setChecked(p.shuffle)
        c.shuffle.toggled.connect(p.set_shuffle)
        c.set_repeat(p.repeat)
        c.repeat.clicked.connect(self._cycle_repeat)
        speed = QMenu(self)
        speed.aboutToShow.connect(lambda: self._speed_menu(speed))
        c.speed.setMenu(speed)
        audio = QMenu(self)
        audio.aboutToShow.connect(lambda: self._track_menu(audio, "audio"))
        c.audio.setMenu(audio)
        subs = QMenu(self)
        subs.aboutToShow.connect(lambda: self._track_menu(subs, "sub"))
        c.subs.setMenu(subs)
        st.clicked.connect(lambda: st.mode == "video" and p.toggle())
        st.controls_shown.connect(self._sub_margin)
        st.start_over.connect(lambda: p.seek(0))
        from grimoire.spells.playl.thumbs import Thumbnailer
        self.thumbs = Thumbnailer()
        c.bar.hovered.connect(self._hovered)
        self.thumbs.ready.connect(self._thumb)
        p.state_changed.connect(self._state)
        p.position_changed.connect(lambda pos: (c.bar.set_position(pos), c.set_times(pos, p.length)))
        p.duration_changed.connect(lambda d: (c.bar.set_length(d), c.set_times(p.pos, d)))
        p.media_changed.connect(self._media)
        p.tracks_changed.connect(self._tracks)
        p.volume_changed.connect(lambda v: c.set_volume(v, p.muted))
        p.muted_changed.connect(lambda m: c.set_volume(p.volume, m))
        p.speed_changed.connect(lambda s: c.speed.setText(ltr(f"{s:g}×")))
        p.message.connect(self.say)
        p.resumed.connect(st.resumed)
        c.set_volume(None, False)
        c.bar.set_length(0)
        from grimoire.spells.playl import mpris
        self.inhibitor = mpris.Inhibitor(tr("grimoire.spells.playl.page", "Playing a video"),
                                         tr("grimoire.spells.playl.page", "Playing media"))
        self.mpris = mpris.start(p, self._raise, self._quit)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.library._scanned.connect(lambda _r: QTimer.singleShot(0, self._titles))

    def _titles(self):
        self.player.titles = self.library.titles()
        if self.queue:
            self.queue.refresh()

    def _keys(self, target: QWidget, fullscreen: bool = False):
        """Shortcuts on the page (and on the fullscreen window, which is a window of its own)."""
        ctx = Qt.ShortcutContext.WindowShortcut if fullscreen else Qt.ShortcutContext.WidgetWithChildrenShortcut
        p = self.player
        keys = {"Ctrl+O": lambda: self.open_files(True)}
        if p:
            keys |= {"Space": p.toggle, "K": p.toggle, "F": self.toggle_full, "M": lambda: p.set_muted(not p.muted),
                     "N": p.next, "P": p.previous, "[": lambda: self._step_speed(-1), "]": lambda: self._step_speed(1),
                     "Backspace": lambda: p.set_speed(1.0), "Q": lambda: self.stage.controls.queue.toggle()}
            moves = {"Left": lambda: p.seek(-SEEK_STEP, True), "Right": lambda: p.seek(SEEK_STEP, True),
                     "Shift+Left": lambda: p.seek(-SEEK_BIG, True), "Shift+Right": lambda: p.seek(SEEK_BIG, True),
                     "Up": lambda: self._nudge_volume(VOLUME_STEP), "Down": lambda: self._nudge_volume(-VOLUME_STEP)}
            if fullscreen:
                keys |= moves | {"Escape": self.toggle_full}
            else:
                for k, fn in moves.items():       # the arrows stay with lists and fields everywhere else
                    s = QShortcut(QKeySequence(k), self.now, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
                    s.activated.connect(fn)
        for k, fn in keys.items():
            s = QShortcut(QKeySequence(k), target, context=ctx)
            s.activated.connect(fn)

    # ------------------------------------------------------------ navigation
    def show_panel(self, pid: str):
        for p, b in self.nav.items():
            b.setChecked(p == pid)
        if pid == "now":
            self.stack.setCurrentWidget(self.now)
            self.stage.setFocus()
            return
        key = "settings" if pid == "settings" else "library"
        box, heading = self.framed[key]
        heading.setText(tr("grimoire.spells.playl.page", next(n for p, n, _ in PANELS if p == pid)))
        if key == "library":
            self.library.show_view(pid)
        self.stack.setCurrentWidget(box)

    def show_queue(self, on: bool):
        if self.queue:
            self.queue.setVisible(on)
            self.save(queue_open=on)

    def save(self, **changes):
        self.settings |= changes
        if self.player:
            self.player.settings |= changes
        POOL.start(Job(lambda: media.save(**changes), lambda _r: None))

    def say(self, text: str):
        self.stage.say(text)

    def _status(self):
        cur = self.player.current if self.player else {}
        if cur:
            self.foot.setText(" — ".join(x for x in (cur.get("artist"), cur.get("title")) if x))
        else:
            self.foot.setText("")

    # ------------------------------------------------------------ opening things
    def _start_dir(self) -> str:
        last = self.settings.get("last_folder") or ""
        return last if last and Path(last).is_dir() else str(Path.home() / "Videos" if (Path.home() / "Videos").is_dir()
                                                             else Path.home())

    def open_files(self, replace: bool = True):
        exts = " ".join(f"*{e}" for e in sorted(media.VIDEO | media.AUDIO | media.PLAYLISTS))
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("grimoire.spells.playl.page", "Open files"), self._start_dir(),
            tr("grimoire.spells.playl.page", "Videos, music and playlists") + f" ({exts});;"
            + tr("grimoire.spells.playl.page", "All files") + " (*)")
        if files:
            self.save(last_folder=str(Path(files[0]).parent))
            self.open_paths(files, replace)

    def open_folder(self, replace: bool = True):
        d = QFileDialog.getExistingDirectory(self, tr("grimoire.spells.playl.page", "Open a folder"),
                                             self._start_dir())
        if d:
            self.save(last_folder=d)
            self.open_paths([d], replace)

    def open_url(self, replace: bool = True):
        text, ok = QInputDialog.getText(self, tr("grimoire.spells.playl.page", "Open an address"),
                                        tr("grimoire.spells.playl.page", "A web address of a video, song or "
                                                                         "stream (http, https, rtsp…):"))
        text = text.strip()
        if ok and text:
            if not media.is_url(text):
                self.say(tr("grimoire.spells.playl.page", "That doesn't look like a web address"))
                return
            self.open_paths([text], replace)

    def open_paths(self, paths: list[str], replace: bool = True):
        """Files, folders, playlists or URLs: gathered on a worker (a big folder takes a moment), then played."""
        if not self.player:
            return
        self.show_panel("now")
        POOL.start(Job(lambda: media.gather(paths), lambda entries: self._opened.emit(entries, replace)))

    _opened = Signal(list, bool)

    def _got_entries(self, entries: list, replace: bool):
        if not entries:
            self.say(tr("grimoire.spells.playl.page", "Nothing to play there"))
            return
        if replace:
            self.player.open(entries)
        else:
            self.enqueue(entries)

    def play_entries(self, entries: list[str], start: int = 0):
        if self.player:
            self.player.open(entries, start)
            self.show_panel("now")

    def enqueue(self, entries: list[str]):
        if self.player:
            self.player.open(entries, replace=False, play=self.player.state() == "stopped")
            self.say(tr("grimoire.spells.playl.page", "Added %n to the queue", n=len(entries)))

    # ------------------------------------------------------------ player readings
    def _state(self, state: str):
        playing = state == "playing"
        self.stage.controls.set_playing(playing)
        self.stage.set_playing(playing)
        self.inhibitor.update(playing, bool(self.player.current.get("video")))
        self._status()

    def _media(self, info: dict):
        st, c = self.stage, self.stage.controls
        if not info:
            st.set_mode("empty")
            st.video.clear()
            c.title.setText("")
            c.sub.setText("")
            self._title("")
            self._status()
            return
        st.set_mode("video" if info.get("video") else "audio")
        c.title.setText(info["title"])
        c.sub.setText(" · ".join(x for x in (info.get("artist"), info.get("album")) if x))
        st.art.set_info(info["title"], info.get("artist", ""), info.get("album", ""))
        self._title(info["title"])
        self._status()
        self.inhibitor.update(self.player.state() == "playing", bool(info.get("video")))
        st.bubble.hide()
        self._sub_margin(st.controls.isVisible())
        entry = info["entry"]
        if entry != self.art_path:
            self.art_path = entry
            st.art.set_art(None)
            if self.mpris:
                self.mpris.set_art(None)
            if info.get("kind") == "audio":
                known = self.player.titles.get(entry, {})
                key = f"{(known.get('albumartist') or known.get('artist') or '').lower()}\x1f" \
                      f"{(known.get('album') or '').lower()}" if known.get("album") else ""
                POOL.start(Job(lambda: (entry, art.cover(entry, key)), lambda r: self._art_ready.emit(*r)))
            self.thumbs.clear()

    def _sub_margin(self, shown: bool):
        """mpv's subtitle margin is in 720-line units: lift the subtitles above the controls while they show."""
        st = self.stage
        lift = st.controls.height() / max(1, st.height()) * 720 if shown and st.mode == "video" else 0
        try:
            self.player.core.set("sub-margin-y", int(22 + lift))
        except mpv.MpvError:
            pass

    def _art_loaded(self, entry: str, path):
        if entry != self.art_path:
            return
        self.stage.art.set_art(QPixmap(str(path)) if path else None)
        if self.mpris:
            self.mpris.set_art(path)

    def _title(self, title: str):
        if self.standalone and self.window():
            self.window().setWindowTitle(f"{title} — PlayL" if title else "PlayL")

    def _tracks(self, tracks: list):
        c = self.stage.controls
        c.audio.setEnabled(sum(1 for t in tracks if t.get("type") == "audio") > 1)
        c.subs.setEnabled(self.player.current.get("video", False) or any(t.get("type") == "sub" for t in tracks))
        if self.player.current:
            video = any(t.get("type") == "video" and not t.get("albumart") and not t.get("image") for t in tracks)
            if video != (self.stage.mode == "video"):
                self.stage.set_mode("video" if video else "audio")

    def _track_menu(self, menu: QMenu, kind: str):
        menu.clear()
        group = QActionGroup(menu)
        tracks = [t for t in self.player.tracks if t.get("type") == kind]
        if kind == "sub":
            off = menu.addAction(tr("grimoire.spells.playl.page", "Off"))
            off.setCheckable(True)
            off.setChecked(not any(t.get("selected") for t in tracks))
            off.triggered.connect(lambda: self.player.set_track("sub", False))
            group.addAction(off)
        for t in tracks:
            a = menu.addAction(track_label(t))
            a.setCheckable(True)
            a.setChecked(bool(t.get("selected")))
            a.triggered.connect(lambda _=False, i=t["id"]: self.player.set_track(kind, i))
            group.addAction(a)
        if kind == "sub":
            menu.addSeparator()
            menu.addAction(tr("grimoire.spells.playl.page", "Load subtitles from a file…"), self._load_subs)

    def _load_subs(self):
        cur = self.player.current.get("entry", "")
        start = str(Path(cur).parent) if cur and not media.is_url(cur) else self._start_dir()
        exts = " ".join(f"*{e}" for e in sorted(media.SUBTITLES))
        path, _ = QFileDialog.getOpenFileName(self, tr("grimoire.spells.playl.page", "Load subtitles"), start,
                                              tr("grimoire.spells.playl.page", "Subtitles") + f" ({exts})")
        if path and self.player.add_subtitle(path):
            self.say(tr("grimoire.spells.playl.page", "Subtitles loaded: {name}").format(name=isolate(Path(path).name)))

    def _speed_menu(self, menu: QMenu):
        from grimoire.spells.playl.player import SPEEDS
        menu.clear()
        group = QActionGroup(menu)
        for s in SPEEDS:
            a = QAction(f"{s:g}×", menu)
            a.setCheckable(True)
            a.setChecked(abs(self.player.speed - s) < 0.001)
            a.triggered.connect(lambda _=False, v=s: self.player.set_speed(v))
            group.addAction(a)
            menu.addAction(a)

    def _step_speed(self, step: int):
        from grimoire.spells.playl.player import SPEEDS
        cur = self.player.speed
        i = min(range(len(SPEEDS)), key=lambda k: abs(SPEEDS[k] - cur))
        self.player.set_speed(SPEEDS[max(0, min(len(SPEEDS) - 1, i + step))])
        self.say(tr("grimoire.spells.playl.page", "Speed {speed}").format(
            speed=ltr(f"{SPEEDS[max(0, min(len(SPEEDS) - 1, i + step))]:g}×")))

    def _nudge_volume(self, step: int):
        p = self.player
        if p.volume is None:
            return
        p.set_volume(max(0, min(100, p.volume + step)))
        self.stage.controls.set_volume(p.volume, p.muted)
        self.stage.activity()

    def _cycle_repeat(self):
        modes = media.REPEATS
        mode = modes[(modes.index(self.player.repeat) + 1) % len(modes)]
        self.player.set_repeat(mode)
        self.stage.controls.set_repeat(mode)

    def _hovered(self, t: float):
        cur = self.player.current
        if cur.get("video") and cur.get("kind") == "video" and self.thumbs.available():
            self.thumbs.request(cur["entry"], t, self.player.length or 0)

    def _thumb(self, entry: str, t: float, img):
        bar = self.stage.controls.bar
        if entry == self.player.current.get("entry") and bar.hover is not None:
            self.stage.bubble.set_image(img)

    # ------------------------------------------------------------ fullscreen
    def toggle_full(self):
        if not self.player or self.stage.mode == "empty" and self.full is None:
            return
        c = self.stage.controls
        if self.full is None:
            self.full = FullWindow()
            self._keys(self.full, fullscreen=True)
            self.full.leave.connect(self._leave_full)
            self.now_lay.removeWidget(self.stage)
            self.full.layout().addWidget(self.stage)
            if self.window() and self.window().screen():
                self.full.setScreen(self.window().screen())
            self.full.showFullScreen()
            c.full.setIcon(glyph("unfullscreen", 20))
            c.full.setToolTip(tr("grimoire.spells.playl.page", "Leave fullscreen (F or Esc)"))
            self.stage.activity()
        else:
            self.full.close()

    def _leave_full(self):
        full, self.full = self.full, None
        if full is None:
            return
        full.layout().removeWidget(self.stage)
        self.now_lay.insertWidget(0, self.stage, 1)
        self.stage.show()
        full.hide()
        full.deleteLater()
        c = self.stage.controls
        c.full.setIcon(glyph("fullscreen", 20))
        c.full.setToolTip(tr("grimoire.spells.playl.stage", "Fullscreen (F)"))
        if self.window():
            self.window().activateWindow()

    # ------------------------------------------------------------ desktop
    def _raise(self):
        w = self.full or self.window()
        if w:
            w.show()
            w.raise_()
            w.activateWindow()

    def _quit(self):
        if self.standalone:
            QApplication.instance().quit()
        else:
            self.player.stop()

    def shutdown(self):
        if self.full:
            self._leave_full()
        if getattr(self, "inhibitor", None):
            self.inhibitor.release_all()
        if self.mpris:
            self.mpris.close()
            self.mpris = None
        if self.player:
            self.player.close()
            self.player = None
