# SPDX-License-Identifier: GPL-3.0-or-later
"""PlayL on the session bus: MPRIS (org.mpris.MediaPlayer2.grimoire_playl) so Plasma's media controls, the lock
screen, KDE Connect and media keys see and steer it, plus the screensaver/sleep inhibitor while playing.

dbus-python (python3-dbus) rather than QtDBus: PySide6 can't export properties or marshal MPRIS's a{sv} metadata.
Its GLib main loop runs inside Qt's (Qt on Linux uses GLib's event dispatcher), so calls arrive on the UI thread.
Without python3-dbus or a session bus both quietly do nothing. Inhibit calls are asynchronous: never a UI stall.
"""
import os
from pathlib import Path

from grimoire.spells.playl import media

BUS_NAME = "org.mpris.MediaPlayer2.grimoire_playl"
PATH = "/org/mpris/MediaPlayer2"
ROOT_IF = "org.mpris.MediaPlayer2"
PLAYER_IF = "org.mpris.MediaPlayer2.Player"
PROPS_IF = "org.freedesktop.DBus.Properties"
TRACK_PATH = "/io/github/cookedaj/grimoire/playl/track/{n}"
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"

_bus = None


def bus():
    """The session bus on the GLib main loop, or None (no python3-dbus, no session bus)."""
    global _bus
    if _bus is None:
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            _bus = dbus.SessionBus(mainloop=DBusGMainLoop())
        except Exception:                # ImportError, DBusException: run without the desktop integration
            _bus = False
    return _bus or None


def _text(s) -> str:
    """D-Bus strings must be valid UTF-8: a file name that isn't (undecodable bytes kept as surrogates) would make
    every Metadata read and change signal fail, and Plasma's media controls lose PlayL."""
    return str(s).encode("utf-8", "surrogateescape").decode("utf-8", "replace")


def _us(seconds) -> int:
    return int((seconds or 0) * 1_000_000)


def start(player, window_raise, quit_app):
    """Export MPRIS for player; returns the service (keep a reference) or None."""
    b = bus()
    if b is None:
        return None
    try:
        return _service_class()(b, player, window_raise, quit_app)
    except Exception as e:               # name clash handling failed, bus went away…
        print(f"PlayL: no MPRIS ({e})")
        return None


def _service_class():
    import dbus
    import dbus.service

    class Mpris(dbus.service.Object):
        def __init__(self, b, player, window_raise, quit_app):
            self.player, self.window_raise, self.quit_app = player, window_raise, quit_app
            name = BUS_NAME
            if b.name_has_owner(name):                  # the hub and a standalone window both playing
                name = f"{BUS_NAME}.instance{os.getpid()}"
            self.name = dbus.service.BusName(name, b, do_not_queue=True)
            super().__init__(b, PATH)
            self.art = ""
            self._last = {}
            p = player
            p.state_changed.connect(lambda _s: self._changed("PlaybackStatus", "CanPlay", "CanPause"))
            p.media_changed.connect(lambda _m: self._changed("Metadata", "CanSeek", "CanGoNext", "CanGoPrevious"))
            p.duration_changed.connect(lambda _d: self._changed("Metadata"))
            p.speed_changed.connect(lambda _s: self._changed("Rate"))
            p.volume_changed.connect(lambda _v: self._changed("Volume"))
            p.queue_changed.connect(lambda: self._changed("CanGoNext", "CanGoPrevious"))
            p.seeked.connect(lambda pos: self.Seeked(dbus.Int64(_us(pos))))

        def set_art(self, path):
            self.art = path.as_uri() if path else ""
            self._changed("Metadata")

        def close(self):
            try:
                self.remove_from_connection()
                self.name.get_bus().release_name(self.name.get_name())
            except Exception:
                pass

        # ------------------------------------------------------------ properties
        def _metadata(self):
            p = self.player
            cur = p.current
            if not cur:
                return dbus.Dictionary({"mpris:trackid": dbus.ObjectPath(NO_TRACK)}, signature="sv")
            m = {"mpris:trackid": dbus.ObjectPath(TRACK_PATH.format(n=max(0, p.index))),
                 "xesam:title": _text(cur.get("title") or media.display_name(cur["entry"]))}
            if p.length:
                m["mpris:length"] = dbus.Int64(_us(p.length))
            if cur.get("artist"):
                m["xesam:artist"] = dbus.Array([_text(cur["artist"])], signature="s")
            if cur.get("album"):
                m["xesam:album"] = _text(cur["album"])
            entry = cur["entry"]
            try:
                m["xesam:url"] = _text(entry) if media.is_url(entry) else Path(entry).absolute().as_uri()
            except ValueError:
                pass
            if self.art and not cur.get("video"):
                m["mpris:artUrl"] = self.art
            return dbus.Dictionary(m, signature="sv")

        def _props(self, iface):
            p = self.player
            if iface == ROOT_IF:
                return {"CanQuit": True, "CanRaise": True, "CanSetFullscreen": False, "HasTrackList": False,
                        "Identity": "PlayL", "DesktopEntry": "grimoire-playl",
                        "SupportedUriSchemes": dbus.Array(["file", *media.SCHEMES], signature="s"),
                        "SupportedMimeTypes": dbus.Array(media.MIME_TYPES, signature="s")}
            if iface == PLAYER_IF:
                status = {"playing": "Playing", "paused": "Paused"}.get(p.state(), "Stopped")
                loop = {"one": "Track", "all": "Playlist"}.get(p.repeat, "None")
                has = bool(p.queue)
                return {"PlaybackStatus": status, "LoopStatus": loop, "Rate": dbus.Double(p.speed),
                        "Shuffle": bool(p.shuffle), "Metadata": self._metadata(),
                        "Volume": dbus.Double((p.volume if p.volume is not None else 100) / 100),
                        "Position": dbus.Int64(_us(p.pos)), "MinimumRate": dbus.Double(0.25),
                        "MaximumRate": dbus.Double(3.0), "CanGoNext": has, "CanGoPrevious": has,
                        "CanPlay": has, "CanPause": has, "CanSeek": bool(p.current) and p.seekable,
                        "CanControl": True}
            raise dbus.exceptions.DBusException(f"no interface {iface}",
                                                name="org.freedesktop.DBus.Error.UnknownInterface")

        def _changed(self, *names):
            props = self._props(PLAYER_IF)
            out = {}
            for n in names:
                v = props[n]
                if self._last.get(n) != v:
                    self._last[n] = v
                    out[n] = v
            if out:
                self.PropertiesChanged(PLAYER_IF, dbus.Dictionary(out, signature="sv"), dbus.Array([], signature="s"))

        @dbus.service.method(PROPS_IF, in_signature="ss", out_signature="v")
        def Get(self, iface, prop):
            return self._props(iface)[prop]

        @dbus.service.method(PROPS_IF, in_signature="s", out_signature="a{sv}")
        def GetAll(self, iface):
            return dbus.Dictionary(self._props(iface), signature="sv")

        @dbus.service.method(PROPS_IF, in_signature="ssv")
        def Set(self, iface, prop, value):
            p = self.player
            if prop == "Volume":
                p.set_volume(float(value) * 100)
            elif prop == "Rate":
                p.set_speed(min(3.0, max(0.25, float(value))))
            elif prop == "Shuffle":
                p.set_shuffle(bool(value))
            elif prop == "LoopStatus":
                p.set_repeat({"Track": "one", "Playlist": "all"}.get(str(value), "off"))
                self._changed("LoopStatus")
            if prop == "Shuffle":
                self._changed("Shuffle")

        @dbus.service.signal(PROPS_IF, signature="sa{sv}as")
        def PropertiesChanged(self, iface, changed, invalidated):
            pass

        # ------------------------------------------------------------ org.mpris.MediaPlayer2
        @dbus.service.method(ROOT_IF)
        def Raise(self):
            self.window_raise()

        @dbus.service.method(ROOT_IF)
        def Quit(self):
            self.quit_app()

        # ------------------------------------------------------------ the player
        @dbus.service.method(PLAYER_IF)
        def Next(self):
            self.player.next()

        @dbus.service.method(PLAYER_IF)
        def Previous(self):
            self.player.previous()

        @dbus.service.method(PLAYER_IF)
        def Pause(self):
            self.player.pause()

        @dbus.service.method(PLAYER_IF)
        def PlayPause(self):
            self.player.toggle()

        @dbus.service.method(PLAYER_IF)
        def Stop(self):
            self.player.stop()

        @dbus.service.method(PLAYER_IF)
        def Play(self):
            self.player.play()

        @dbus.service.method(PLAYER_IF, in_signature="x")
        def Seek(self, offset):
            p = self.player
            target = (p.pos or 0) + offset / 1_000_000
            if p.length and target > p.length:
                p.next()
            else:
                p.seek(max(0.0, target))

        @dbus.service.method(PLAYER_IF, in_signature="ox")
        def SetPosition(self, track, position):
            p = self.player
            if str(track) == TRACK_PATH.format(n=max(0, p.index)) and 0 <= position / 1e6 <= (p.length or 0):
                p.seek(position / 1_000_000)

        @dbus.service.method(PLAYER_IF, in_signature="s")
        def OpenUri(self, uri):
            entries = media.gather([str(uri)])
            if entries:
                self.player.open(entries)

        @dbus.service.signal(PLAYER_IF, signature="x")
        def Seeked(self, position):
            pass

    return Mpris


class Inhibitor:
    """Keeps the screen on while a video plays (org.freedesktop.ScreenSaver) and the computer awake while anything
    plays (org.freedesktop.PowerManagement.Inhibit). Plasma drops both if PlayL dies, as they're tied to our bus
    connection."""
    SCREEN = ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver")
    SLEEP = ("org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement/Inhibit",
             "org.freedesktop.PowerManagement.Inhibit")

    def __init__(self, reason_video: str, reason_audio: str):
        self.reasons = {"screen": reason_video, "sleep": reason_audio}
        self.cookies: dict[str, object] = {}      # what -> cookie, or "pending" while the call runs
        self.want: set[str] = set()

    def update(self, playing: bool, video: bool):
        want = set()
        if playing:
            want.add("sleep")
            if video:
                want.add("screen")
        self.want = want
        for what in ("screen", "sleep"):
            if what in want and what not in self.cookies:
                self._inhibit(what)
            elif what not in want and isinstance(self.cookies.get(what), int):
                self._release(what)

    def _iface(self, what):
        b = bus()
        if b is None:
            return None, None
        svc, path, iface = self.SCREEN if what == "screen" else self.SLEEP
        try:
            return b.get_object(svc, path, introspect=False), iface
        except Exception:
            return None, None

    def _inhibit(self, what):
        obj, iface = self._iface(what)
        if obj is None:
            return
        self.cookies[what] = "pending"

        def got(cookie):
            self.cookies[what] = int(cookie)
            if what not in self.want:              # stopped while the call was on its way
                self._release(what)

        def failed(_err):
            self.cookies.pop(what, None)
        obj.Inhibit("PlayL", self.reasons["screen" if what == "screen" else "sleep"], dbus_interface=iface,
                    reply_handler=got, error_handler=failed, timeout=5)

    def _release(self, what):
        cookie = self.cookies.pop(what, None)
        obj, iface = self._iface(what)
        if obj is None or not isinstance(cookie, int):
            return
        import dbus
        obj.UnInhibit(dbus.UInt32(cookie), dbus_interface=iface, reply_handler=lambda *a: None,
                      error_handler=lambda *a: None, timeout=5)

    def release_all(self):
        self.want = set()
        for what in list(self.cookies):
            if isinstance(self.cookies[what], int):
                self._release(what)
