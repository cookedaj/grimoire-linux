# SPDX-License-Identifier: GPL-3.0-or-later
"""KDE Connect's signals, heard on a thread of their own. Text messages only arrive this way (the phone sends them
after a request), and the rest (a device appearing, a notification posted) lets the page refresh at once instead
of on its next poll.

GDBus delivers a subscription's signals in the main context that was the thread's default when subscribing, so the
thread pushes a private GLib.MainContext: Qt's own GLib event loop on the UI thread never runs these callbacks.
No Qt here: callback(member, path, args) is called on the listener's thread.
"""
import threading

from grimoire.spells.phonel import kdc


class Listener:
    def __init__(self, callback):
        self.callback = callback
        self.thread = None
        self.loop = None
        self.ctx = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        ready = threading.Event()
        self.thread = threading.Thread(target=self._run, args=(ready,), name="phonel-listen", daemon=True)
        self.thread.start()
        ready.wait(3)

    def _run(self, ready):
        try:
            Gio, GLib = kdc._gio()
            self.ctx = GLib.MainContext.new()
            self.ctx.push_thread_default()
            conn = kdc.connection()
            subs = [conn.signal_subscribe(kdc.SERVICE, None, None, None, None, Gio.DBusSignalFlags.NONE,
                                          self._heard, None)]
            self.loop = GLib.MainLoop.new(self.ctx, False)
        except Exception:
            ready.set()
            return
        ready.set()
        try:
            self.loop.run()
        finally:
            for s in subs:
                conn.signal_unsubscribe(s)
            self.ctx.pop_thread_default()

    def _heard(self, _conn, _sender, path, iface, member, params, _data):
        try:
            args = params.unpack() if params is not None else ()
        except Exception:
            args = ()
        try:
            self.callback(member, path, args)
        except RuntimeError:                       # the page went away
            self.stop()

    def stop(self):
        loop, ctx = self.loop, self.ctx
        if loop is not None and ctx is not None:
            # quit from inside the listener's own context, the only safe place to touch its loop
            from gi.repository import GLib
            src = GLib.idle_source_new()
            src.set_callback(lambda *_: (loop.quit(), False)[1])
            src.attach(ctx)
        self.loop = None
