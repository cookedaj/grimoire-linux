# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for KDE Connect's daemon on a private D-Bus, for PhoneL's tests and screenshots: the interfaces PhoneL
uses, made-up devices and data, and a log of every call. Nothing reaches a real phone or the network.

    from scripts.fake_kdeconnect import FakeKdeConnect
    with FakeKdeConnect(sandbox_dir) as fake:        # its own dbus-daemon; fake.address is the bus
        kdc.ADDRESS = fake.address
        ...
        fake.calls                                   # [(path, method, args), …]

    python3 scripts/fake_kdeconnect.py <sandbox_dir> [--empty|--no-daemon]   prints the address, serves until ^C

The bus has no service directories, so nothing on it can ever start the real kdeconnectd.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

SERVICE = "org.kde.kdeconnect"
ROOT = "/modules/kdeconnect"
D = "org.kde.kdeconnect.device"
CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:path={socket}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""
XML = f"""<node>
<interface name="org.kde.kdeconnect.daemon">
  <method name="devices"><arg type="b" direction="in"/><arg type="b" direction="in"/>
    <arg type="as" direction="out"/></method>
  <method name="announcedName"><arg type="s" direction="out"/></method>
  <method name="setAnnouncedName"><arg type="s" direction="in"/></method>
  <method name="forceOnNetworkChange"/>
  <property name="pairingRequests" type="as" access="read"/>
  <signal name="deviceListChanged"/>
  <signal name="pairingRequestsChanged"/>
</interface>
<interface name="{D}">
  <property name="name" type="s" access="read"/>
  <property name="type" type="s" access="read"/>
  <property name="iconName" type="s" access="read"/>
  <property name="isReachable" type="b" access="read"/>
  <property name="isPaired" type="b" access="read"/>
  <property name="isPairRequested" type="b" access="read"/>
  <property name="isPairRequestedByPeer" type="b" access="read"/>
  <property name="supportedPlugins" type="as" access="read"/>
  <method name="requestPairing"/><method name="acceptPairing"/><method name="cancelPairing"/><method name="unpair"/>
  <method name="loadedPlugins"><arg type="as" direction="out"/></method>
  <method name="verificationKey"><arg type="s" direction="out"/></method>
  <method name="isPluginEnabled"><arg type="s" direction="in"/><arg type="b" direction="out"/></method>
  <method name="setPluginEnabled"><arg type="s" direction="in"/><arg type="b" direction="in"/></method>
  <signal name="pairStateChanged"><arg type="i"/></signal>
  <signal name="reachableChanged"><arg type="b"/></signal>
</interface>
<interface name="{D}.conversations">
  <method name="activeConversations"><arg type="av" direction="out"/></method>
  <method name="requestAllConversationThreads"/>
  <method name="requestConversation"><arg type="x" direction="in"/><arg type="i" direction="in"/>
    <arg type="i" direction="in"/></method>
  <method name="replyToConversation"><arg type="x" direction="in"/><arg type="s" direction="in"/>
    <arg type="av" direction="in"/></method>
  <method name="sendWithoutConversation"><arg type="av" direction="in"/><arg type="s" direction="in"/>
    <arg type="av" direction="in"/></method>
  <signal name="conversationCreated"><arg type="v"/></signal>
  <signal name="conversationUpdated"><arg type="v"/></signal>
  <signal name="conversationLoaded"><arg type="x"/><arg type="t"/></signal>
</interface>
<interface name="{D}.battery">
  <property name="charge" type="i" access="read"/><property name="isCharging" type="b" access="read"/>
</interface>
<interface name="{D}.connectivity_report">
  <property name="cellularNetworkType" type="s" access="read"/>
  <property name="cellularNetworkStrength" type="i" access="read"/>
</interface>
<interface name="{D}.ping"><method name="sendPing"/></interface>
<interface name="{D}.findmyphone"><method name="ring"/></interface>
<interface name="{D}.share"><method name="shareUrls"><arg type="as" direction="in"/></method></interface>
<interface name="{D}.clipboard"><method name="sendClipboard"/></interface>
<interface name="{D}.sftp">
  <method name="mount"/><method name="unmount"/>
  <method name="isMounted"><arg type="b" direction="out"/></method>
  <method name="getMountError"><arg type="s" direction="out"/></method>
  <method name="mountPoint"><arg type="s" direction="out"/></method>
  <method name="getDirectories"><arg type="a{{sv}}" direction="out"/></method>
</interface>
<interface name="{D}.notifications">
  <method name="activeNotifications"><arg type="as" direction="out"/></method>
  <signal name="notificationPosted"><arg type="s"/></signal>
  <signal name="notificationRemoved"><arg type="s"/></signal>
</interface>
<interface name="{D}.notifications.notification">
  <property name="appName" type="s" access="read"/><property name="title" type="s" access="read"/>
  <property name="text" type="s" access="read"/><property name="ticker" type="s" access="read"/>
  <property name="dismissable" type="b" access="read"/><property name="replyId" type="s" access="read"/>
  <property name="silent" type="b" access="read"/>
  <method name="dismiss"/><method name="sendReply"><arg type="s" direction="in"/></method>
</interface>
<interface name="{D}.mprisremote">
  <property name="playerList" type="as" access="read"/><property name="player" type="s" access="readwrite"/>
  <property name="isPlaying" type="b" access="read"/><property name="volume" type="i" access="readwrite"/>
  <property name="length" type="i" access="read"/><property name="position" type="i" access="read"/>
  <property name="title" type="s" access="read"/><property name="artist" type="s" access="read"/>
  <property name="album" type="s" access="read"/><property name="canSeek" type="b" access="read"/>
  <method name="sendAction"><arg type="s" direction="in"/></method>
  <method name="requestPlayerList"/>
  <signal name="propertiesChanged"/>
</interface>
<interface name="{D}.remotecommands">
  <property name="commands" type="ay" access="read"/>
  <method name="triggerCommand"><arg type="s" direction="in"/></method>
</interface>
<interface name="{D}.remotekeyboard">
  <property name="remoteState" type="b" access="read"/>
  <method name="sendKeyPress"><arg type="s" direction="in"/><arg type="i" direction="in"/>
    <arg type="b" direction="in"/><arg type="b" direction="in"/><arg type="b" direction="in"/>
    <arg type="b" direction="in"/></method>
</interface>
<interface name="{D}.remotecontrol">
  <method name="moveCursor"><arg type="(ii)" direction="in"/></method>
  <method name="sendCommand"><arg type="a{{sv}}" direction="in"/></method>
</interface>
</node>"""
ALL = ["battery", "clipboard", "connectivity_report", "findmyphone", "mprisremote", "notifications", "ping",
       "remotecommands", "remotecontrol", "remotekeyboard", "sftp", "share", "sms"]
NOW = 1_792_150_000_000                       # ms, a fixed "now" so screenshots don't change


def _msg(body, address, minutes_ago, kind, thread, uid, read=True):
    return (1, body, [(address,)], NOW - minutes_ago * 60_000, kind, int(read), thread, uid, 0, [])


def sample_devices() -> dict:
    """Made-up devices: a connected phone with everything on, a tablet nearby, a phone asking to pair, an old one."""
    def dev(name, kind, reachable, paired, plugins=(), by_peer=False):
        return {"name": name, "type": kind, "isReachable": reachable, "isPaired": paired, "isPairRequested": False,
                "isPairRequestedByPeer": by_peer, "supportedPlugins": ["kdeconnect_" + p for p in ALL],
                "plugins": ["kdeconnect_" + p for p in plugins], "disabled": set()}
    return {"pixel9_7f3a": dev("Pixel 9", "phone", True, True, ALL),
            "tab_s9_51c2": dev("Galaxy Tab S9", "tablet", True, False),
            "moto_g_88e1": dev("moto g", "phone", True, False, by_peer=True),
            "oldphone_02": dev("Old phone", "phone", False, True)}


class FakeKdeConnect:
    def __init__(self, folder, devices: dict | None = None, daemon: bool = True):
        self.folder = Path(folder)
        self.devices = sample_devices() if devices is None else devices
        self.daemon_up = daemon
        self.calls: list = []
        self.name = "grimoire-pc"
        self.mounted = False
        self.battery = {"charge": 82, "isCharging": True}
        self.signal = {"cellularNetworkType": "5G", "cellularNetworkStrength": 3}
        self.notes = {
            "n1": {"appName": "Messages", "title": "Sam", "text": "Running 10 minutes late, save me a seat",
                   "ticker": "", "dismissable": True, "replyId": "r1", "silent": False},
            "n2": {"appName": "Calendar", "title": "Design review", "text": "Today 15:00 · Room 2",
                   "ticker": "", "dismissable": True, "replyId": "", "silent": False},
            "n3": {"appName": "Weather", "title": "Rain from 18:00", "text": "Take an umbrella",
                   "ticker": "", "dismissable": False, "replyId": "", "silent": True}}
        self.threads = {
            11: [_msg("Are we still on for Saturday?", "+1 555 0100", 300, 1, 11, 1),
                 _msg("Yes! 10am at the park", "+1 555 0100", 290, 2, 11, 2),
                 _msg("Running 10 minutes late, save me a seat", "+1 555 0100", 4, 1, 11, 3, read=False)],
            12: [_msg("Your code is 482913", "ACME Bank", 60 * 26, 1, 12, 4)],
            13: [_msg("Dinner at 8?", "+1 555 0142", 60 * 49, 2, 13, 5),
                 _msg("Perfect, see you there", "+1 555 0142", 60 * 48, 1, 13, 6)]}
        self.media = {"playerList": ["Spotify", "YouTube Music"], "player": "Spotify", "isPlaying": True,
                      "volume": 60, "length": 214_000, "position": 81_000, "title": "Night Drive",
                      "artist": "The Midnight Hours", "album": "Neon Roads", "canSeek": True}
        self.commands = {"c1": {"name": "Turn on the lights", "command": "lights on"},
                         "c2": {"name": "Silence the phone", "command": "silent"}}
        self.keyboard = True
        self.daemon = None
        self.address = ""
        self.loop = None
        self.conn = None
        self.regs = {}

    # ------------------------------------------------------------ life
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        socket = self.folder / "bus"
        (self.folder / "bus.conf").write_text(CONFIG.format(socket=socket))
        self.daemon = subprocess.Popen(["dbus-daemon", "--config-file", str(self.folder / "bus.conf"), "--nofork",
                                        "--print-address"], stdout=subprocess.PIPE, text=True)
        self.address = self.daemon.stdout.readline().strip()
        if self.daemon_up:
            ready = threading.Event()
            threading.Thread(target=self._serve, args=(ready,), daemon=True).start()
            if not ready.wait(5):
                raise RuntimeError("fake kdeconnect didn't start")

    def stop(self):
        if self.loop:
            self.loop.quit()
        if self.daemon:
            self.daemon.terminate()
            self.daemon.wait(5)

    def _serve(self, ready):
        ctx = GLib.MainContext.new()
        ctx.push_thread_default()
        flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
        self.conn = Gio.DBusConnection.new_for_address_sync(self.address, flags, None, None)
        self.info = Gio.DBusNodeInfo.new_for_xml(XML)
        self._reg(ROOT, "org.kde.kdeconnect.daemon")
        for dev in self.devices:
            self._register_device(dev)
        self.conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
                            GLib.Variant("(su)", (SERVICE, 4)), None, Gio.DBusCallFlags.NONE, -1, None)
        self.loop = GLib.MainLoop.new(ctx, False)
        ready.set()
        self.loop.run()

    def _reg(self, path, iface):
        if (path, iface) in self.regs:
            return
        self.regs[(path, iface)] = self.conn.register_object(path, self.info.lookup_interface(iface), self._call,
                                                             self._get, self._set)

    def _unreg(self, path, iface):
        rid = self.regs.pop((path, iface), None)
        if rid:
            self.conn.unregister_object(rid)

    def _register_device(self, dev):
        path = f"{ROOT}/devices/{dev}"
        self._reg(path, D)
        d = self.devices[dev]
        if d["isPaired"] and d["isReachable"]:
            if "kdeconnect_sms" in d["plugins"]:
                self._reg(path, D + ".conversations")
            for p in d["plugins"]:
                name = p.removeprefix("kdeconnect_")
                if name != "sms":
                    self._reg(f"{path}/{name}", f"{D}.{name}")
            if "kdeconnect_notifications" in d["plugins"]:
                for nid in self.notes:
                    self._reg(f"{path}/notifications/{nid}", D + ".notifications.notification")

    def _emit(self, path, iface, name, sig="", args=()):
        self.conn.emit_signal(None, path, iface, name, GLib.Variant(f"({sig})", tuple(args)) if sig else None)

    # ------------------------------------------------------------ properties
    def _dev_of(self, path):
        parts = path.split("/")
        return parts[4] if len(parts) > 4 else ""

    def _get(self, _conn, _sender, path, iface, prop):
        dev = self.devices.get(self._dev_of(path), {})
        if iface == "org.kde.kdeconnect.daemon":
            return GLib.Variant("as", [k for k, d in self.devices.items() if d["isPairRequestedByPeer"]])
        if iface == D:
            if prop == "iconName":
                return GLib.Variant("s", "smartphone")
            sig = {"supportedPlugins": "as", "name": "s", "type": "s"}.get(prop, "b")
            return GLib.Variant(sig, dev[prop])
        if iface == D + ".battery":
            return GLib.Variant("i" if prop == "charge" else "b", self.battery[prop])
        if iface == D + ".connectivity_report":
            return GLib.Variant("s" if prop == "cellularNetworkType" else "i", self.signal[prop])
        if iface == D + ".notifications.notification":
            v = self.notes.get(path.rsplit("/", 1)[1], {}).get(prop, "")
            return GLib.Variant("b" if isinstance(v, bool) else "s", v)
        if iface == D + ".mprisremote":
            v = self.media[prop]
            sig = "as" if isinstance(v, list) else "b" if isinstance(v, bool) else "i" if isinstance(v, int) else "s"
            return GLib.Variant(sig, v)
        if iface == D + ".remotecommands":
            import json
            return GLib.Variant("ay", json.dumps(self.commands).encode())
        if iface == D + ".remotekeyboard":
            return GLib.Variant("b", self.keyboard)
        return None

    def _set(self, _conn, _sender, path, iface, prop, value):
        self.calls.append((path, f"Set.{prop}", (value.unpack(),)))
        if iface == D + ".mprisremote":
            self.media[prop] = value.unpack()
            return True
        return False

    # ------------------------------------------------------------ methods
    def _call(self, _conn, _sender, path, iface, method, params, inv):
        args = params.unpack()
        self.calls.append((path, method, args))
        dev_id = self._dev_of(path)
        dev = self.devices.get(dev_id)
        out = None
        if iface == "org.kde.kdeconnect.daemon":
            if method == "devices":
                reach, paired = args
                out = GLib.Variant("(as)", ([k for k, d in self.devices.items() if (not reach or d["isReachable"])
                                             and (not paired or d["isPaired"])],))
            elif method == "announcedName":
                out = GLib.Variant("(s)", (self.name,))
            elif method == "setAnnouncedName":
                self.name = args[0]
        elif iface == D:
            if method == "loadedPlugins":
                out = GLib.Variant("(as)", ([p for p in dev["plugins"] if p not in dev["disabled"]]
                                            if dev["isPaired"] and dev["isReachable"] else [],))
            elif method == "verificationKey":
                out = GLib.Variant("(s)", ("4F2A 9C1B 77E0",))
            elif method == "isPluginEnabled":
                out = GLib.Variant("(b)", (args[0] not in dev["disabled"],))
            elif method == "setPluginEnabled":
                (dev["disabled"].discard if args[1] else dev["disabled"].add)(args[0])
            elif method == "requestPairing":
                dev["isPairRequested"] = True
            elif method == "acceptPairing":
                dev.update(isPaired=True, isPairRequestedByPeer=False)
            elif method == "cancelPairing":
                dev.update(isPairRequested=False, isPairRequestedByPeer=False)
            elif method == "unpair":
                dev["isPaired"] = False
            if method in ("requestPairing", "acceptPairing", "cancelPairing", "unpair"):
                self._emit(path, D, "pairStateChanged", "i", (0,))
        elif iface == D + ".conversations":
            if method == "activeConversations":
                out = GLib.Variant("(av)", ([GLib.Variant("(isa(s)xiixixa(xsss))", t[-1])
                                             for t in self.threads.values()],))
            elif method == "requestAllConversationThreads":
                for t in self.threads.values():
                    self._emit(path, iface, "conversationCreated", "v",
                               (GLib.Variant("(isa(s)xiixixa(xsss))", t[-1]),))
            elif method == "requestConversation":
                thread, start, end = args
                msgs = self.threads.get(thread, [])
                for m in list(reversed(msgs))[start:end]:
                    self._emit(path, iface, "conversationUpdated", "v", (GLib.Variant("(isa(s)xiixixa(xsss))", m),))
                self._emit(path, iface, "conversationLoaded", "xt", (thread, len(msgs)))
            elif method == "replyToConversation":
                thread, text, _ = args
                msgs = self.threads.setdefault(thread, [])
                m = _msg(text, msgs[0][2][0][0] if msgs else "?", 0, 2, thread, 100 + len(self.calls))
                msgs.append(m)
                self._emit(path, iface, "conversationUpdated", "v", (GLib.Variant("(isa(s)xiixixa(xsss))", m),))
        elif iface == D + ".sftp":
            mnt = self.folder / "mnt"
            if method == "mount":
                (mnt / "storage/emulated/0/DCIM").mkdir(parents=True, exist_ok=True)
                self.mounted = True
            elif method == "unmount":
                self.mounted = False
            elif method == "isMounted":
                out = GLib.Variant("(b)", (self.mounted,))
            elif method == "getMountError":
                out = GLib.Variant("(s)", ("",))
            elif method == "mountPoint":
                out = GLib.Variant("(s)", (str(mnt),))
            elif method == "getDirectories":
                out = GLib.Variant("(a{sv})", ({str(mnt / "storage/emulated/0"): GLib.Variant("s", "All files")},))
        elif iface == D + ".notifications" and method == "activeNotifications":
            out = GLib.Variant("(as)", (list(self.notes),))
        elif iface == D + ".notifications.notification" and method == "dismiss":
            nid = path.rsplit("/", 1)[1]
            self.notes.pop(nid, None)
            self._unreg(path, iface)
            self._emit(path.rsplit("/", 1)[0], D + ".notifications", "notificationRemoved", "s", (nid,))
        elif iface == D + ".mprisremote" and method == "sendAction":
            if args[0] in ("PlayPause", "Play", "Pause"):
                self.media["isPlaying"] = {"Play": True, "Pause": False}.get(args[0], not self.media["isPlaying"])
        inv.return_value(out)


def main():
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / ".cache/grimoire-fake-kdeconnect")
    fake = FakeKdeConnect(folder, devices={} if "--empty" in sys.argv else None,
                          daemon="--no-daemon" not in sys.argv)
    fake.start()
    print(fake.address, flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        fake.stop()


if __name__ == "__main__":
    main()
