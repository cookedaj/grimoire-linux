# SPDX-License-Identifier: GPL-3.0-or-later
"""The player: one mpv core, PlayL's queue (play order, repeat, shuffle), resume points and the readings the UI,
MPRIS and the sleep inhibitor follow through signals.

mpv events are drained on the UI thread when mpv's wakeup callback says there are some (never polled). Volume is
the PipeWire stream's own (mpv's ao-volume, the same number AudioL and Plasma show for "PlayL"), never a second
software mixer; WirePlumber remembers it between runs.
"""
import atexit
import os
import random
import weakref
import time
from collections import deque

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from grimoire.i18n import isolate, tr
from grimoire.jobs import POOL, Job
from grimoire.spells.playl import media, mpv

SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0)
OBSERVED = ("time-pos", "duration", "pause", "eof-reached", "idle-active", "track-list", "speed", "ao-volume",
            "ao-mute", "media-title", "metadata", "seekable", "paused-for-cache")
SAVE_EVERY_MS = 15000
PREV_RESTARTS = 3.0          # Previous within the first 3 s goes to the previous file, later it restarts this one


class Player(QObject):
    state_changed = Signal(str)          # "playing", "paused", "stopped"
    position_changed = Signal(float)
    duration_changed = Signal(float)
    media_changed = Signal(dict)         # the current file: entry, title, artist, album, kind, video
    tracks_changed = Signal(list)
    volume_changed = Signal(object)      # 0..100, or None while there's no audio stream to set
    muted_changed = Signal(bool)
    speed_changed = Signal(float)
    queue_changed = Signal()
    current_changed = Signal(int)
    seeked = Signal(float)
    resumed = Signal(float)
    message = Signal(str)
    _wake = Signal()

    def __init__(self, settings: dict | None = None, **extra_options):
        super().__init__()
        self.settings = settings or media.load()
        options = {"vo": "libmpv", "hwdec": "auto-safe" if self.settings["hwdec"] else "no", "keep_open": "yes",
                   "idle": "yes", "config": "no", "load_scripts": "no", "input_default_bindings": "no",
                   "input_vo_keyboard": "no", "osc": "no", "osd_level": "0", "terminal": "no",
                   "audio_client_name": "PlayL", "audio_display": "no", "sub_auto": "fuzzy", "volume": "100",
                   "volume_max": "100", "save_position_on_quit": "no", "screenshot_directory": "",
                   "title": "PlayL"} | extra_options
        if os.environ.get("PLAYL_AO"):                # tests: PLAYL_AO=null keeps them silent
            options["ao"] = os.environ["PLAYL_AO"]
        self.core = mpv.MPV(**options)
        for name in OBSERVED:
            self.core.observe(name)
        self.core.request_log("error")
        self.renderer = None
        self.queue: list[str] = []
        self.order: list[int] = []           # play order (positions in queue); shuffled when shuffle is on
        self.index = -1                      # the current entry in queue
        self.repeat = self.settings["repeat"]
        self.shuffle = self.settings["shuffle"]
        self.titles: dict[str, dict] = {}    # entry → known tags (from the library), for the queue's names
        self.pos: float | None = None
        self.length: float | None = None
        self.paused = True
        self.idle = True
        self.eof = False
        self.speed = 1.0
        self.volume: float | None = None
        self.muted = False
        self.seekable = False
        self.tracks: list[dict] = []
        self.current: dict = {}
        self._fails = 0
        self._loading = ""                   # the entry mpv is opening now (between start-file and end/loaded)
        self._requested: deque[str] = deque()   # loadfile commands sent, in order; start-file events pop them
        self._last_error = ""
        self._pending_wake = False
        self._last_pos_emit = 0.0
        self.positions = media.Positions({})
        POOL.start(Job(lambda: media.Positions().data, self._positions_loaded))
        self._pos_timer = QTimer(self, singleShot=True, interval=200, timeout=self._emit_pos)
        self._save_timer = QTimer(self, interval=SAVE_EVERY_MS, timeout=self._save_position)
        self._vol_timer = QTimer(self, interval=1500, timeout=self._poll_volume)
        self._wake.connect(self._drain, Qt.ConnectionType.QueuedConnection)   # never inside an mpv call
        self.core.on_wakeup(self._wakeup)
        me = weakref.ref(self)                # a process that ends without aboutToQuit still frees mpv in order
        atexit.register(lambda: me() is not None and me().core.h and me().close())

    def _positions_loaded(self, data: dict):
        # runs on the pool thread: plain dict merge (anything remembered meanwhile wins)
        self.positions.data = data | self.positions.data

    def start_video(self):
        """Make the render thread (after a QApplication exists); without it mpv still plays sound."""
        from grimoire.spells.playl.video import Renderer
        if self.renderer is None:
            self.renderer = Renderer(self.core)
        return self.renderer

    # ------------------------------------------------------------ mpv events
    def _wakeup(self):                   # mpv's thread: just ask the UI thread to drain
        if not self._pending_wake:
            self._pending_wake = True
            self._wake.emit()

    def _drain(self):
        self._pending_wake = False
        if not self.core.h:
            return
        for ev in self.core.events():
            kind = ev[0]
            if kind == "property":
                self._property(ev[1], ev[2])
            elif kind == "end-file":
                self._ended(ev[1], ev[2])
            elif kind == "start-file":
                self._loading = self._requested.popleft() if self._requested else ""
                self._last_error = ""
            elif kind == "file-loaded":
                self._fails = 0
                self._loaded()
            elif kind == "log" and ev[1] in ("error", "fatal") and ev[2]:
                self._log_error(ev[2])
            elif kind == "restart":
                self.seeked.emit(self.pos or 0.0)

    def _property(self, name: str, value):
        if name == "time-pos":
            self.pos = value if isinstance(value, (int, float)) else None
            if not self._pos_timer.isActive():
                self._pos_timer.start(0 if time.monotonic() - self._last_pos_emit > 0.2 else 200)
        elif name == "duration":
            self.length = value if isinstance(value, (int, float)) else None
            self.duration_changed.emit(self.length or 0.0)
        elif name == "pause":
            self.paused = bool(value)
            self._state()
        elif name == "idle-active":
            self.idle = bool(value)
            self._state()
        elif name == "eof-reached":
            self.eof = bool(value)
            if self.eof:
                self._at_end()
        elif name == "track-list":
            self.tracks = value if isinstance(value, list) else []
            self.tracks_changed.emit(self.tracks)
            self._media_info()
        elif name == "speed":
            self.speed = float(value or 1.0)
            self.speed_changed.emit(self.speed)
        elif name == "ao-volume":
            self._set_volume_reading(value)
        elif name == "ao-mute":
            if value is not None and bool(value) != self.muted:
                self.muted = bool(value)
                self.muted_changed.emit(self.muted)
        elif name in ("media-title", "metadata"):
            self._media_info()
        elif name == "seekable":
            self.seekable = bool(value)

    def _set_volume_reading(self, value):
        v = float(value) if isinstance(value, (int, float)) else None
        if v != self.volume:
            self.volume = v
            self.volume_changed.emit(v)

    def _poll_volume(self):
        """mpv reports a change made elsewhere (AudioL, Plasma's mixer) only when asked again."""
        if self.core.h and not self.idle:
            self._set_volume_reading(self.core.get("ao-volume"))
            m = self.core.get("ao-mute")
            if m is not None and bool(m) != self.muted:
                self.muted = bool(m)
                self.muted_changed.emit(self.muted)

    def _emit_pos(self):
        self._last_pos_emit = time.monotonic()
        self.position_changed.emit(self.pos or 0.0)

    def state(self) -> str:
        if self.idle or self.index < 0:
            return "stopped"
        return "paused" if self.paused or self.eof else "playing"

    def _state(self):
        s = self.state()
        if s == "playing":
            self._save_timer.start()
            self._vol_timer.start()
        else:
            self._save_timer.stop()
        if self.current:
            media.NOW.update(title=self.current.get("title", ""), playing=s == "playing")
        else:
            media.NOW.clear()
        self.state_changed.emit(s)

    def _log_error(self, text: str):
        if self._loading:                      # the reason for a failed load; the end-file event says it failed
            self._last_error = text

    def _ended(self, reason: int, error: int):
        if reason == mpv.END_ERROR:
            entry = self._loading
            why = self._last_error or self.core.error_text(error)
            self.message.emit(tr("grimoire.spells.playl.player", "Couldn't play {name}: {error}").format(
                name=isolate(media.display_name(entry)), error=isolate(why)))
            self._fails += 1
            self._loading = ""
            current = self.queue[self.index] if 0 <= self.index < len(self.queue) else None
            if entry != current or self._requested:
                return                         # an older file failed while another one was already asked for
            if self._fails < len(self.queue):
                self._advance(+1, auto=True)
            else:
                self._fails = 0
                self._state()
        elif reason in (mpv.END_EOF, mpv.END_STOP, mpv.END_QUIT):
            self._loading = ""

    def _loaded(self):
        self._loading = ""
        self._last_error = ""
        self._media_info()
        self._state()

    def _media_info(self):
        if self.index < 0 or self.index >= len(self.queue):
            return
        entry = self.queue[self.index]
        meta = self.core.get("metadata") or {}
        low = {str(k).lower(): v for k, v in meta.items()} if isinstance(meta, dict) else {}
        known = self.titles.get(entry, {})
        title = (low.get("title") or known.get("title") or self.core.get("media-title")
                 or media.display_name(entry))
        video = any(t.get("type") == "video" and not t.get("albumart") and not t.get("image") for t in self.tracks)
        info = {"entry": entry, "title": str(title), "artist": str(low.get("artist") or known.get("artist") or ""),
                "album": str(low.get("album") or known.get("album") or ""), "kind": media.kind(entry),
                "video": video, "index": self.index}
        if info != self.current:
            self.current = info
            self.media_changed.emit(info)

    def _at_end(self):
        """keep-open stopped at the end of a file: repeat it, go on, or stay paused at the end of the queue."""
        if self.index < 0:
            return
        if self.repeat == "one":
            self.seek(0)
            self.play()
            return
        if not self._advance(+1, auto=True):
            self._state()

    # ------------------------------------------------------------ the queue
    def _rebuild_order(self, keep_current=True):
        n = len(self.queue)
        if not self.shuffle:
            self.order = list(range(n))
            return
        rest = [i for i in range(n) if not (keep_current and i == self.index)]
        random.shuffle(rest)
        self.order = ([self.index] if keep_current and 0 <= self.index < n else []) + rest

    def open(self, entries: list[str], start: int = 0, replace: bool = True, play: bool = True):
        """Put entries in the queue (replacing it, or after it) and start playing entries[start]."""
        if not entries:
            return
        if replace:
            self._save_position()
            self.queue = list(entries)
            self.index = -1
            self._rebuild_order(keep_current=False)
            if self.shuffle and 0 <= start < len(entries):
                self.order.remove(start)
                self.order.insert(0, start)
            self.queue_changed.emit()
            if play:
                self.play_index(start)
        else:
            first = len(self.queue)
            self.queue += entries
            self._rebuild_order()
            self.queue_changed.emit()
            if play and (self.index < 0 or self.state() == "stopped"):
                self.play_index(first + start)

    def play_index(self, i: int):
        if not 0 <= i < len(self.queue):
            return
        self._save_position()
        self.index = i
        entry = self.queue[i]
        if media.kind(entry) != "url" and not os.path.exists(entry):
            self.index = i
            self.current_changed.emit(i)
            self.message.emit(tr("grimoire.spells.playl.player", "{name} isn't there anymore").format(
                name=isolate(media.display_name(entry))))
            self._fails += 1
            if self._fails < len(self.queue):
                QTimer.singleShot(0, lambda: self._advance(+1, auto=True))
            else:
                self._fails = 0
            return
        self._requested.append(entry)
        self.pos, self.length, self.eof = None, None, False
        start = self.positions.get(entry) if self.settings["resume"] else 0.0
        opts = f"start=+{start:.1f}" if start else ""
        self.cmd("loadfile", entry, "replace", "-1", opts)
        self._set("pause", False)
        self.current = {}
        self._media_info()
        self.current_changed.emit(i)
        if start:
            self.resumed.emit(start)

    def _advance(self, step: int, auto=False) -> bool:
        if not self.queue or not self.core.h:     # a skip queued just before close()
            return False
        if self.index not in self.order:
            self._rebuild_order()
        at = self.order.index(self.index) if self.index in self.order else -1
        nxt = at + step
        if not 0 <= nxt < len(self.order):
            if self.repeat == "all":
                if self.shuffle and nxt >= len(self.order):
                    self._rebuild_order(keep_current=False)
                nxt %= len(self.order)
            else:
                return False
        self.play_index(self.order[nxt])
        return True

    def next(self):
        self._advance(+1)

    def previous(self):
        if (self.pos or 0) > PREV_RESTARTS or not self._advance(-1):
            self.seek(0)

    def move(self, src: int, dst: int):
        """Drag reorder: the entry at src goes to dst (the current entry keeps playing)."""
        if not (0 <= src < len(self.queue) and 0 <= dst < len(self.queue)) or src == dst:
            return
        cur = self.queue[self.index] if 0 <= self.index < len(self.queue) else None
        item = self.queue.pop(src)
        self.queue.insert(dst, item)
        if cur is not None:
            self.index = self._index_after_move(self.index, src, dst)
        self._rebuild_order()
        self.queue_changed.emit()
        self.current_changed.emit(self.index)

    def reorder(self, order: list[int]):
        """The queue in a new order: order[k] is the old position of what's now at k (the current one keeps
        playing)."""
        if sorted(order) != list(range(len(self.queue))):
            self.queue_changed.emit()             # out of step with the list: just redraw it
            return
        self.queue = [self.queue[i] for i in order]
        if 0 <= self.index < len(order):
            self.index = order.index(self.index)
        self._rebuild_order()
        self.queue_changed.emit()
        self.current_changed.emit(self.index)

    @staticmethod
    def _index_after_move(i: int, src: int, dst: int) -> int:
        if i == src:
            return dst
        if src < i <= dst:
            return i - 1
        if dst <= i < src:
            return i + 1
        return i

    def remove(self, rows: list[int]):
        playing = self.index in rows
        keep = [e for k, e in enumerate(self.queue) if k not in set(rows)]
        before = sum(1 for r in rows if r < self.index)
        self.queue = keep
        if playing:
            self.stop()
        else:
            self.index -= before
        self._rebuild_order()
        self.queue_changed.emit()
        self.current_changed.emit(self.index)

    def clear(self):
        self.stop()
        self.queue = []
        self.order = []
        self.queue_changed.emit()

    def set_repeat(self, mode: str):
        self.repeat = mode if mode in media.REPEATS else "off"
        self._persist(repeat=self.repeat)

    def set_shuffle(self, on: bool):
        self.shuffle = bool(on)
        self._rebuild_order()
        self._persist(shuffle=self.shuffle)

    def _persist(self, **changes):
        self.settings |= changes
        POOL.start(Job(lambda: media.save(**changes), lambda _r: None))

    # ------------------------------------------------------------ transport
    def _set(self, name: str, value):
        try:
            self.core.set(name, value)
        except mpv.MpvError:                  # closed, or mpv refused the value: nothing to do about it here
            pass

    def cmd(self, *args):
        try:
            self.core.command_async(*args)
        except mpv.MpvError:
            pass

    def play(self):
        if self.index < 0 and self.queue:
            self.play_index(self.order[0] if self.order else 0)
            return
        if self.eof:                          # at the end: from the top again
            self.seek(0)
        self._set("pause", False)

    def pause(self):
        self._set("pause", True)

    def toggle(self):
        if self.state() == "playing":
            self.pause()
        else:
            self.play()

    def stop(self):
        self._save_position()
        self.cmd("stop")
        self.index = -1
        self.current = {}
        self.pos = self.length = None
        media.NOW.clear()
        self.media_changed.emit({})
        self.current_changed.emit(-1)

    def seek(self, seconds: float, relative: bool = False):
        if self.index < 0:
            return
        if relative:
            self.cmd("seek", f"{seconds:.3f}", "relative+exact")
        else:
            self.cmd("seek", f"{max(0.0, seconds):.3f}", "absolute+exact")
        self.eof = False

    def set_speed(self, speed: float):
        self._set("speed", float(speed))

    def set_volume(self, percent: float):
        """The PipeWire stream volume (0..100); ignored before mpv has an audio stream."""
        try:
            self.core.set("ao-volume", float(max(0, min(100, percent))))
        except mpv.MpvError:
            return
        self.volume = float(percent)

    def set_muted(self, on: bool):
        try:
            self.core.set("ao-mute", bool(on))
        except mpv.MpvError:
            return
        self.muted = bool(on)
        self.muted_changed.emit(self.muted)

    def set_track(self, kind: str, track_id):
        """kind "audio" or "sub"; track_id an int, or False for none (subtitles off)."""
        prop = {"audio": "aid", "sub": "sid"}[kind]
        try:
            self.core.set(prop, "no" if track_id is False else str(track_id))
        except mpv.MpvError:
            pass

    def add_subtitle(self, path: str) -> bool:
        try:
            self.core.command("sub-add", path, "select")
            return True
        except mpv.MpvError as e:
            self.message.emit(tr("grimoire.spells.playl.player", "Couldn't load the subtitles: {error}").format(
                error=isolate(str(e))))
            return False

    # ------------------------------------------------------------ resume points
    def _save_position(self):
        if not (0 <= self.index < len(self.queue)) or not self.settings["resume"]:
            return
        entry = self.queue[self.index]
        if media.kind(entry) == "url":
            return
        if self.positions.put(entry, self.pos, self.length):
            pos = self.positions
            POOL.start(Job(pos.save, lambda _r: None))

    def forget_positions(self):
        self.positions.clear()
        POOL.start(Job(self.positions.save, lambda _r: None))

    def close(self):
        """Remember where we were, then free the render context and the core."""
        for t in (self._save_timer, self._vol_timer, self._pos_timer):
            t.stop()                           # a pending position tick would reach widgets already gone
        if 0 <= self.index < len(self.queue) and self.settings["resume"]:
            if self.positions.put(self.queue[self.index], self.pos, self.length):
                self.positions.save()
        if self.renderer:
            self.renderer.stop()
        media.NOW.clear()
        self.core.close()
