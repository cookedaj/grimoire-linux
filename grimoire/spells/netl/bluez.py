# SPDX-License-Identifier: GPL-3.0-or-later
"""NetL's Bluetooth: BlueZ (org.bluez) on the system D-Bus through GDBus (python3-gi), no Qt.

A Client owns one private bus connection with a GLib loop on its own thread. That loop delivers BlueZ's change
signals and the calls to our pairing agent (org.bluez.Agent1: PIN codes, passkeys, "does it show 123456?"); method
calls (power, scan, pair, connect…) are made from worker threads on the same connection, which GDBus allows.
BlueZ uses the agent of the connection that called Pair(), so ours answers for pairings started here while
Plasma's own agent stays the default for everything else (we never ask to become the default).

Agent calls are only accepted from bluetoothd's own bus name. `BUS_ADDRESS` is the stub point: tests point it at a
private bus with a fake BlueZ (never toggle, pair or connect real devices in tests).
"""
import threading

from grimoire.i18n import tr

BUS_ADDRESS: str | None = None          # None = the real system bus
BLUEZ = "org.bluez"
ADAPTER, DEVICE, BATTERY = "org.bluez.Adapter1", "org.bluez.Device1", "org.bluez.Battery1"
AGENT_MANAGER, AGENT_IFACE = "org.bluez.AgentManager1", "org.bluez.Agent1"
PROPS, OM = "org.freedesktop.DBus.Properties", "org.freedesktop.DBus.ObjectManager"
AGENT_PATH = "/com/cookedaj/grimoire/netl/agent"
CALL_TIMEOUT = 25_000                   # ms
PAIR_TIMEOUT = 120_000                  # ms: pairing waits on the person typing or confirming a code
AGENT_XML = """<node><interface name="org.bluez.Agent1">
<method name="Release"/>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/>
<arg type="q" direction="in"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="Cancel"/>
</interface></node>"""


class BluezError(RuntimeError):
    """Why something failed, worded for the UI; code is "NoService" when bluetoothd isn't on the bus."""
    code = ""


def missing() -> str:
    """Why Bluetooth can't be used from here at all ("" when it can)."""
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib  # noqa: F401
    except (ImportError, ValueError):
        return tr("grimoire.spells.netl.bluez", "Bluetooth needs python3-gi: {command}").format(
            command="sudo apt install python3-gi")
    return ""


def _gi():
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    return Gio, GLib


def _error_text(key: str) -> str:
    # spelled out so scripts/i18n.py sees every sentence
    return {"NotReady": tr("grimoire.spells.netl.bluez", "the adapter is off"),
            "AuthenticationFailed": tr("grimoire.spells.netl.bluez", "the codes didn't match, or the device refused"),
            "AuthenticationCanceled": "cancelled",
            "AuthenticationRejected": tr("grimoire.spells.netl.bluez", "the device refused"),
            "AuthenticationTimeout": tr("grimoire.spells.netl.bluez", "the device didn't answer in time"),
            "ConnectionAttemptFailed": tr("grimoire.spells.netl.bluez", "the device didn't answer: is it on and "
                                                                        "nearby?"),
            "AlreadyExists": tr("grimoire.spells.netl.bluez", "already paired"),
            "DoesNotExist": tr("grimoire.spells.netl.bluez", "the device is gone"),
            "InProgress": tr("grimoire.spells.netl.bluez", "already busy with this device"),
            "Blocked": tr("grimoire.spells.netl.bluez", "Bluetooth is blocked (airplane mode or a hardware switch)"),
            "NotPermitted": tr("grimoire.spells.netl.bluez", "not allowed"),
            "NotAvailable": tr("grimoire.spells.netl.bluez", "not available")}.get(key, "")


def _err(e) -> BluezError:
    Gio, _ = _gi()
    name = Gio.DBusError.get_remote_error(e) or ""
    msg = e.message or ""
    if Gio.DBusError.is_remote_error(e):
        Gio.DBusError.strip_remote_error(e)
        msg = e.message or name
    if name.endswith(("ServiceUnknown", "NameHasNoOwner")):
        e = BluezError(tr("grimoire.spells.netl.bluez", "the Bluetooth service isn't running"))
        e.code = "NoService"
        return e
    short = name.rsplit(".", 1)[-1] if name.startswith("org.bluez.Error.") else ""
    # BlueZ often puts the real reason in the message of a generic Failed ("br-connection-page-timeout"…)
    if short in ("Failed", "") and ("page-timeout" in msg or "Host is down" in msg):
        short = "ConnectionAttemptFailed"
    if "rfkill" in msg.lower() or "blocked" in msg.lower():
        short = "Blocked"
    return BluezError(_error_text(short) or msg.strip() or name)


class AgentRequest:
    """One question BlueZ asks while pairing. kind is the Agent1 method; the UI answers with accept(value) or
    reject(). Display* requests are answered at once (they only show a code) and stay open until done/cancelled."""

    def __init__(self, kind: str, device: str, name: str, value=None, uuid: str = "", invocation=None):
        self.kind, self.device, self.name, self.value, self.uuid = kind, device, name, value, uuid
        self._inv = invocation
        self._lock = threading.Lock()
        self.closed = False

    def accept(self, value=None):
        _, GLib = _gi()
        with self._lock:
            inv, self._inv = self._inv, None
        if inv is None:
            return
        if self.kind == "RequestPinCode":
            inv.return_value(GLib.Variant("(s)", (str(value),)))
        elif self.kind == "RequestPasskey":
            inv.return_value(GLib.Variant("(u)", (int(value),)))
        else:
            inv.return_value(None)

    def reject(self):
        with self._lock:
            inv, self._inv = self._inv, None
        if inv is not None:
            inv.return_dbus_error("org.bluez.Error.Rejected", "Rejected by the user")

    @property
    def pending(self) -> bool:
        return self._inv is not None


class Client:
    """BlueZ for one page. on_change() and on_request(AgentRequest) / on_cancel() are called from the loop thread:
    hand them over to the UI thread (Qt signals)."""

    def __init__(self, on_change=lambda: None, on_request=lambda r: None, on_cancel=lambda: None):
        self.on_change, self.on_request, self.on_cancel = on_change, on_request, on_cancel
        self.conn = None
        self.owner = ""                    # bluetoothd's unique bus name: the only caller our agent answers
        self.agent_ok = False
        self.error = ""
        self._loop = None
        self._ready = threading.Event()
        self._thread = None
        self._agent_id = 0
        self._requests: list[AgentRequest] = []

    # ------------------------------------------------------------ lifecycle
    def start(self, timeout=5.0) -> "Client":
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True, name="netl-bluez")
            self._thread.start()
        self._ready.wait(timeout)
        return self

    def _run(self):
        try:
            Gio, GLib = _gi()
        except (ImportError, ValueError):
            self.error = missing()
            self._ready.set()
            return
        ctx = GLib.MainContext()
        ctx.push_thread_default()
        try:
            address = BUS_ADDRESS or Gio.dbus_address_get_for_bus_sync(Gio.BusType.SYSTEM, None)
            self.conn = Gio.DBusConnection.new_for_address_sync(
                address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        except Exception as e:                       # GLib.Error: no system bus at all
            self.error = tr("grimoire.spells.netl.bluez", "Couldn't reach the system bus: {error}").format(
                error=getattr(e, "message", str(e)))
            self._ready.set()
            ctx.pop_thread_default()
            return
        self.conn.set_exit_on_close(False)
        self.conn.signal_subscribe(BLUEZ, None, None, None, None, Gio.DBusSignalFlags.NONE,
                                   lambda *a: self._changed(), None)
        self.conn.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
                                   "/org/freedesktop/DBus", BLUEZ, Gio.DBusSignalFlags.NONE, self._owner_changed,
                                   None)
        node = Gio.DBusNodeInfo.new_for_xml(AGENT_XML)
        self._agent_id = self.conn.register_object(AGENT_PATH, node.interfaces[0], self._agent_call, None, None)
        self._register()
        self._loop = GLib.MainLoop(ctx)
        self._ready.set()
        self._loop.run()
        ctx.pop_thread_default()

    def _register(self):
        """Find bluetoothd and register our agent with it (again after it restarts)."""
        Gio, GLib = _gi()
        self.agent_ok = False
        try:
            self.owner = self.conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                             "GetNameOwner", GLib.Variant("(s)", (BLUEZ,)), None,
                                             Gio.DBusCallFlags.NONE, CALL_TIMEOUT, None).unpack()[0]
        except Exception:
            self.owner = ""
            return
        try:
            self.conn.call_sync(BLUEZ, "/org/bluez", AGENT_MANAGER, "RegisterAgent",
                                GLib.Variant("(os)", (AGENT_PATH, "KeyboardDisplay")), None, Gio.DBusCallFlags.NONE,
                                CALL_TIMEOUT, None)
            self.agent_ok = True
        except Exception as e:
            self.agent_ok = "AlreadyExists" in getattr(e, "message", "")

    def _owner_changed(self, conn, sender, path, iface, signal, params, *_):
        _name, _old, new = params.unpack()
        self.owner = new
        if new:
            self._register()
        else:
            self.agent_ok = False
            self._cancel_all()
        self._changed()

    def _changed(self):
        try:
            self.on_change()
        except RuntimeError:                         # the page is gone
            pass

    def stop(self):
        """Unregister the agent and close the connection (BlueZ also forgets the agent when the connection
        closes)."""
        Gio, GLib = _gi()
        self._cancel_all()
        if self.conn is not None:
            if self.agent_ok:
                try:
                    self.conn.call_sync(BLUEZ, "/org/bluez", AGENT_MANAGER, "UnregisterAgent",
                                        GLib.Variant("(o)", (AGENT_PATH,)), None, Gio.DBusCallFlags.NONE, 3000, None)
                except Exception:
                    pass
            if self._agent_id:
                self.conn.unregister_object(self._agent_id)
            try:
                self.conn.close_sync(None)
            except Exception:
                pass
        if self._loop is not None:
            self._loop.quit()

    # ------------------------------------------------------------ the agent
    def _agent_call(self, conn, sender, path, iface, method, params, invocation):
        Gio, GLib = _gi()
        if not self.owner or sender != self.owner:
            invocation.return_dbus_error("org.bluez.Error.Rejected", "Not bluetoothd")
            return
        args = params.unpack()
        if method == "Release":
            invocation.return_value(None)
            return
        if method == "Cancel":
            invocation.return_value(None)
            self._cancel_all()
            return
        device = args[0] if args else ""
        name = self._name(device)
        value = args[1] if method in ("DisplayPinCode", "DisplayPasskey", "RequestConfirmation") else None
        uuid = args[1] if method == "AuthorizeService" else ""
        if method == "AuthorizeService" and self._trusted(device):
            invocation.return_value(None)            # a device you paired and trust: its services may connect
            return
        req = AgentRequest(method, device, name, value, uuid, invocation)
        if method in ("DisplayPinCode", "DisplayPasskey"):
            req.accept()                              # nothing to answer: the UI only shows the code
        self._requests = [r for r in self._requests if r.pending or r.kind.startswith("Display")] + [req]
        try:
            self.on_request(req)
        except RuntimeError:
            req.reject()

    def _cancel_all(self):
        for r in self._requests:
            r.closed = True
            r.reject()
        self._requests = []
        try:
            self.on_cancel()
        except RuntimeError:
            pass

    def _prop(self, path: str, iface: str, name: str):
        Gio, GLib = _gi()
        try:
            return self.conn.call_sync(BLUEZ, path, PROPS, "Get", GLib.Variant("(ss)", (iface, name)), None,
                                       Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
        except Exception:
            return None

    def _name(self, device: str) -> str:
        return str(self._prop(device, DEVICE, "Alias") or self._prop(device, DEVICE, "Address") or device)

    def _trusted(self, device: str) -> bool:
        return bool(self._prop(device, DEVICE, "Paired")) and bool(self._prop(device, DEVICE, "Trusted"))

    # ------------------------------------------------------------ reading
    def _call(self, path, iface, method, sig=None, args=(), timeout=CALL_TIMEOUT):
        Gio, GLib = _gi()
        if self.conn is None:
            raise BluezError(self.error or tr("grimoire.spells.netl.bluez", "the Bluetooth service isn't running"))
        try:
            v = self.conn.call_sync(BLUEZ, path, iface, method, GLib.Variant(sig, tuple(args)) if sig else None,
                                    None, Gio.DBusCallFlags.NONE, timeout, None)
        except Exception as e:
            if hasattr(e, "domain"):
                raise _err(e) from None
            raise
        return v.unpack() if v is not None else None

    def snapshot(self) -> dict:
        """{"running", "agent", "error", "adapters": [...], "devices": [...]} with plain Python values."""
        if self.conn is None:
            return {"running": False, "agent": False, "error": self.error, "adapters": [], "devices": []}
        try:
            objs = self._call("/", OM, "GetManagedObjects")[0]
        except BluezError as e:
            return {"running": False, "agent": False, "error": str(e), "code": e.code, "adapters": [],
                    "devices": []}
        adapters, devices = [], []
        for path, ifaces in sorted(objs.items()):
            a = ifaces.get(ADAPTER)
            if a is not None:
                state = str(a.get("PowerState", ""))
                adapters.append({"path": path, "name": str(a.get("Alias") or a.get("Name") or path.rsplit("/", 1)[-1]),
                                 "address": str(a.get("Address", "")), "powered": bool(a.get("Powered")),
                                 "blocked": state == "off-blocked", "discoverable": bool(a.get("Discoverable")),
                                 "discovering": bool(a.get("Discovering")),
                                 "timeout": int(a.get("DiscoverableTimeout", 0) or 0)})
            d = ifaces.get(DEVICE)
            if d is not None:
                bat = ifaces.get(BATTERY, {})
                address = str(d.get("Address", ""))
                name = str(d.get("Alias") or d.get("Name") or "")
                devices.append({"path": path, "adapter": str(d.get("Adapter", "")), "address": address,
                                "name": name, "named": bool(d.get("Name")),
                                "icon": str(d.get("Icon", "")), "paired": bool(d.get("Paired")),
                                "bonded": bool(d.get("Bonded")), "trusted": bool(d.get("Trusted")),
                                "connected": bool(d.get("Connected")), "blocked": bool(d.get("Blocked")),
                                "rssi": d.get("RSSI"), "battery": bat.get("Percentage")})
        return {"running": True, "agent": self.agent_ok, "error": "", "adapters": adapters, "devices": devices}

    # ------------------------------------------------------------ actions (call from a worker thread)
    def _set(self, path, iface, name, sig, value):
        Gio, GLib = _gi()
        self._call(path, PROPS, "Set", "(ssv)", (iface, name, GLib.Variant(sig, value)))

    def set_powered(self, adapter: str, on: bool):
        self._set(adapter, ADAPTER, "Powered", "b", on)

    def set_discoverable(self, adapter: str, on: bool):
        self._set(adapter, ADAPTER, "Discoverable", "b", on)

    def scan(self, adapter: str, on: bool):
        try:
            self._call(adapter, ADAPTER, "StartDiscovery" if on else "StopDiscovery")
        except BluezError as e:
            if on or "No discovery started" not in str(e):
                raise

    def pair(self, device: str) -> str:
        """Pair (answering BlueZ's questions through on_request), trust it so it reconnects by itself, then
        connect."""
        try:
            self._call(device, DEVICE, "Pair", timeout=PAIR_TIMEOUT)
        except BluezError as e:
            if str(e) != _error_text("AlreadyExists"):
                raise
        self._set(device, DEVICE, "Trusted", "b", True)
        try:
            self._call(device, DEVICE, "Connect", timeout=PAIR_TIMEOUT)
        except BluezError:
            return tr("grimoire.spells.netl.bluez", "paired; connect it when it's ready")
        return tr("grimoire.spells.netl.bluez", "paired and connected")

    def cancel_pairing(self, device: str):
        try:
            self._call(device, DEVICE, "CancelPairing")
        except BluezError:
            pass

    def connect(self, device: str) -> str:
        self._call(device, DEVICE, "Connect", timeout=PAIR_TIMEOUT)
        return tr("grimoire.spells.netl.bluez", "connected")

    def disconnect(self, device: str) -> str:
        self._call(device, DEVICE, "Disconnect")
        return tr("grimoire.spells.netl.bluez", "disconnected")

    def remove(self, adapter: str, device: str) -> str:
        self._call(adapter, ADAPTER, "RemoveDevice", "(o)", (device,))
        return tr("grimoire.spells.netl.bluez", "removed")
