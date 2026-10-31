# SPDX-License-Identifier: GPL-3.0-or-later
"""SystemL's Drives: disks, partitions, mounting and health through udisks2 on the system D-Bus (no Qt).

Everything is done as you, the way Dolphin does it: udisks asks polkit, and Plasma's agent shows the password
prompt only when a drive needs it (internal disks usually do, USB sticks don't). Without udisks the list comes from
`lsblk -J` and nothing can be changed. Health comes from udisks (ATA SMART or NVMe health log), else from
`smartctl -j` when it can open the device as you (it usually can't without root).

Formatting and partition editing are left to KDE Partition Manager on purpose: they can wipe a disk, and a
half-finished copy of that tool would be worse than a link to the real one.

Every function here can take a moment (or wait on a password prompt): call it on a worker thread.
`BUS_ADDRESS` is the stub point: tests point it at a private bus with a fake udisks.
"""
import json
import shutil
import subprocess

import psutil

from grimoire.i18n import tr

BUS_ADDRESS: str | None = None          # None = the real system bus
UDISKS = "org.freedesktop.UDisks2"
ROOT = "/org/freedesktop/UDisks2"
I = {n: f"org.freedesktop.UDisks2.{n}" for n in ("Drive", "Drive.Ata", "Block", "Partition", "PartitionTable",
                                                 "Filesystem", "Encrypted", "NVMe.Controller", "Loop", "Swapspace")}
ACTION_TIMEOUT = 300 * 1000             # ms: mounting may wait on the password prompt
# mount points the session or the system lives on: never unmounted from here
SYSTEM_MOUNTS = ("/", "/boot", "/boot/efi", "/efi", "/home", "/usr", "/var", "/opt", "/srv", "/tmp", "/nix",
                 "/snap", "/recovery")
PARTITION_MANAGER = "partitionmanager"


class DriveError(RuntimeError):
    """Why an action failed, worded for the UI ("cancelled" when the password prompt was dismissed)."""


def _dbus():
    try:
        import dbus
        return dbus
    except ImportError:
        return None


def _bus():
    dbus = _dbus()
    if dbus is None:
        raise DriveError(tr("grimoire.spells.systeml.drives", "Drive actions need python3-dbus: {command}").format(
            command="sudo apt install python3-dbus"))
    if BUS_ADDRESS:
        return dbus.bus.BusConnection(BUS_ADDRESS)
    return dbus.SystemBus(private=True)


def _py(v):
    """dbus-python values as plain Python (byte arrays as bytes, strings as str)."""
    dbus = _dbus()
    if isinstance(v, dbus.Array) and v.signature == "y":
        return bytes(int(b) for b in v)
    if isinstance(v, (dbus.Array, list, tuple)):
        return [_py(x) for x in v]
    if isinstance(v, (dbus.Dictionary, dict)):
        return {str(k): _py(x) for k, x in v.items()}
    if isinstance(v, dbus.Boolean):
        return bool(v)
    if isinstance(v, (dbus.Byte, dbus.Int16, dbus.Int32, dbus.Int64, dbus.UInt16, dbus.UInt32, dbus.UInt64)):
        return int(v)
    if isinstance(v, dbus.Double):
        return float(v)
    if isinstance(v, (dbus.String, dbus.ObjectPath)):
        return str(v)
    return v


def _text(b) -> str:
    """A udisks byte string (NUL-terminated path) as text."""
    if isinstance(b, (bytes, bytearray)):
        return bytes(b).rstrip(b"\0").decode("utf-8", "replace")
    return str(b or "")


def _err(e) -> DriveError:
    name = e.get_dbus_name() or ""
    if name.endswith(("NotAuthorizedDismissed", "Cancelled")):
        return DriveError("cancelled")
    if name.endswith("NotAuthorized") or name.endswith("NotAuthorizedCanObtain"):
        return DriveError(tr("grimoire.spells.systeml.drives", "not allowed (polkit refused)"))
    if name.endswith("DeviceBusy"):
        return DriveError(tr("grimoire.spells.systeml.drives", "it's in use: close the files and apps using it, "
                                                               "then try again"))
    if name == "org.freedesktop.DBus.Error.ServiceUnknown":
        return DriveError(tr("grimoire.spells.systeml.drives", "udisks2 isn't running"))
    msg = (e.get_dbus_message() or name or str(e)).strip()
    return DriveError(msg.splitlines()[-1] if msg else name)


# ---------------------------------------------------------------- reading
def _objects() -> dict | None:
    """udisks' GetManagedObjects as plain dicts, or None when udisks isn't there."""
    dbus = _dbus()
    if dbus is None:
        return None
    try:
        bus = _bus()
    except Exception:
        return None
    try:
        om = dbus.Interface(bus.get_object(UDISKS, ROOT), "org.freedesktop.DBus.ObjectManager")
        return {str(p): _py(ifaces) for p, ifaces in om.GetManagedObjects(timeout=10).items()}
    except dbus.DBusException:
        return None
    finally:
        try:
            bus.close()
        except Exception:
            pass


def _usage(mount: str):
    try:
        u = psutil.disk_usage(mount)
        return u.used, u.total
    except OSError:
        return None, None


def _kind(drive: dict, nvme: bool) -> str:
    bus = drive.get("ConnectionBus", "")
    if drive.get("Optical") or any(m.startswith("optical") for m in drive.get("MediaCompatibility", [])):
        return "optical"
    if nvme:
        return "nvme"
    if bus == "usb":
        return "usb"
    if bus == "sdio" or any(m.startswith("flash_sd") for m in drive.get("MediaCompatibility", [])):
        return "card"
    return "hdd" if drive.get("RotationRate", 0) not in (0, -1) else "ssd"


def kind_text(kind: str) -> str:
    return {"nvme": "NVMe SSD", "ssd": "SSD", "usb": tr("grimoire.spells.systeml.drives", "USB drive"),
            "hdd": tr("grimoire.spells.systeml.drives", "Hard drive"),
            "optical": tr("grimoire.spells.systeml.drives", "Optical drive"),
            "card": tr("grimoire.spells.systeml.drives", "Memory card"),
            "virtual": tr("grimoire.spells.systeml.drives", "Virtual disk")}.get(kind, kind)


def _health(ifaces: dict) -> dict:
    """What the drive's own properties say about its health (no extra calls)."""
    ata, nvme = ifaces.get(I["Drive.Ata"]), ifaces.get(I["NVMe.Controller"])
    if ata and ata.get("SmartSupported") and ata.get("SmartEnabled") and ata.get("SmartUpdated"):
        t = ata.get("SmartTemperature") or 0
        return {"source": "ata", "failing": bool(ata.get("SmartFailing")), "temp": t - 273.15 if t > 0 else None,
                "hours": (ata.get("SmartPowerOnSeconds") or 0) // 3600 or None,
                "bad_sectors": ata.get("SmartNumBadSectors", 0), "selftest": ata.get("SmartSelftestStatus", "")}
    if nvme and nvme.get("SmartUpdated"):
        t = nvme.get("SmartTemperature") or 0
        warn = [w for w in nvme.get("SmartCriticalWarning") or [] if w]
        return {"source": "nvme", "failing": bool(warn), "warnings": warn, "temp": t - 273.15 if t > 0 else None,
                "hours": nvme.get("SmartPowerOnHours") or None, "selftest": nvme.get("SmartSelftestStatus", "")}
    if ata and ata.get("SmartSupported"):
        return {"source": "ata", "failing": None, "temp": None, "hours": None}
    return {"source": "", "failing": None, "temp": None, "hours": None}


def _part(path: str, ifaces: dict, objs: dict) -> dict:
    blk, part, fs = ifaces.get(I["Block"], {}), ifaces.get(I["Partition"], {}), ifaces.get(I["Filesystem"])
    out = {"object": path, "device": _text(blk.get("PreferredDevice") or blk.get("Device")),
           "number": part.get("Number", 0), "offset": part.get("Offset", 0), "size": blk.get("Size", 0),
           "label": blk.get("IdLabel") or part.get("Name", ""), "fs": blk.get("IdType", ""),
           "usage": blk.get("IdUsage", ""), "system": bool(blk.get("HintSystem")), "can_mount": fs is not None,
           "mounts": [_text(m) for m in (fs or {}).get("MountPoints", [])], "encrypted": False, "unlocked": False,
           "swap": I["Swapspace"] in ifaces or blk.get("IdType") == "swap", "used": None, "total": None,
           "container": bool(part.get("IsContainer")), "type": part.get("Type", "")}
    if I["Encrypted"] in ifaces or out["usage"] == "crypto":
        out["encrypted"] = True
        clear = next(((p, i) for p, i in objs.items() if i.get(I["Block"], {}).get("CryptoBackingDevice") == path),
                     None)
        if clear:                              # unlocked: show what's inside
            inner = _part(clear[0], clear[1], objs)
            out.update({k: inner[k] for k in ("fs", "mounts", "can_mount", "label")})
            out["inner"] = clear[0]
            out["unlocked"] = True
    if out["mounts"] and not out["swap"]:
        out["used"], out["total"] = _usage(out["mounts"][0])
    return out


def is_system_mount(mount: str) -> bool:
    return mount in SYSTEM_MOUNTS or mount.startswith(("/boot/", "/usr/", "/var/"))


def _from_udisks(objs: dict) -> list[dict]:
    drives = {}
    for path, ifaces in objs.items():
        d = ifaces.get(I["Drive"])
        if d is None:
            continue
        nvme = I["NVMe.Controller"] in ifaces
        model = " ".join(x for x in (d.get("Vendor", "").strip(), d.get("Model", "").strip()) if x)
        drives[path] = {"object": path, "model": model or d.get("Id", "") or path.rsplit("/", 1)[-1],
                        "serial": d.get("Serial", ""), "revision": d.get("Revision", ""), "size": d.get("Size", 0),
                        "kind": _kind(d, nvme), "removable": bool(d.get("Removable") or d.get("MediaRemovable")
                                                                  or d.get("ConnectionBus") == "usb"),
                        "can_power_off": bool(d.get("CanPowerOff")), "ejectable": bool(d.get("Ejectable")),
                        "media": bool(d.get("MediaAvailable", True)), "health": _health(ifaces),
                        "device": "", "table": "", "parts": [], "sort": d.get("SortKey", "")}
    for path, ifaces in objs.items():
        blk = ifaces.get(I["Block"])
        if not blk or blk.get("Drive", "/") not in drives or blk.get("CryptoBackingDevice", "/") != "/":
            continue
        drive = drives[blk["Drive"]]
        if I["Partition"] in ifaces:
            drive["parts"].append(_part(path, ifaces, objs))
        else:                                   # the whole disk: a partition table, or a file system on it all
            drive["device"] = _text(blk.get("PreferredDevice") or blk.get("Device"))
            drive["block"] = path
            if I["PartitionTable"] in ifaces:
                drive["table"] = ifaces[I["PartitionTable"]].get("Type", "")
            elif blk.get("IdUsage") or I["Filesystem"] in ifaces:
                whole = _part(path, ifaces, objs)
                whole["whole"] = True
                drive["parts"].append(whole)
            if not drive["size"]:
                drive["size"] = blk.get("Size", 0)
    out = []
    for d in drives.values():
        if not d["device"] and not d["parts"]:
            continue
        d["parts"].sort(key=lambda p: (p["offset"], p["number"]))
        d["system"] = any(p["system"] or any(is_system_mount(m) for m in p["mounts"]) for p in d["parts"])
        out.append(d)
    return sorted(out, key=lambda d: (d["removable"], d["sort"], d["model"]))


def _from_lsblk() -> list[dict]:
    """Read-only fallback without udisks."""
    try:
        data = json.loads(subprocess.run(
            ["lsblk", "-J", "-b", "-o", "NAME,PATH,MODEL,SERIAL,SIZE,TYPE,ROTA,TRAN,RM,MOUNTPOINTS,FSTYPE,LABEL"],
            capture_output=True, text=True, timeout=10).stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    out = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk" or dev["name"].startswith(("loop", "zram", "ram")):
            continue
        tran = dev.get("tran") or ""
        kind = "nvme" if tran == "nvme" else "usb" if tran == "usb" else "hdd" if dev.get("rota") else "ssd"
        parts = []
        for n, p in enumerate(dev.get("children") or [], 1):
            mounts = [m for m in (p.get("mountpoints") or []) if m]
            used, total = _usage(mounts[0]) if mounts and mounts[0] != "[SWAP]" else (None, None)
            parts.append({"object": "", "device": p.get("path") or f"/dev/{p['name']}", "number": n, "offset": 0,
                          "size": p.get("size") or 0, "label": p.get("label") or "", "fs": p.get("fstype") or "",
                          "usage": "", "system": any(is_system_mount(m) for m in mounts), "can_mount": False,
                          "mounts": [m for m in mounts if m != "[SWAP]"], "encrypted": p.get("fstype") ==
                          "crypto_LUKS", "unlocked": bool(p.get("children")), "swap": "[SWAP]" in mounts,
                          "used": used, "total": total, "container": False, "type": ""})
        out.append({"object": "", "model": (dev.get("model") or dev["name"]).strip(), "serial": dev.get("serial") or "",
                    "revision": "", "size": dev.get("size") or 0, "kind": kind,
                    "removable": bool(dev.get("rm")) or tran == "usb", "can_power_off": False, "ejectable": False,
                    "media": True, "health": {"source": "", "failing": None, "temp": None, "hours": None},
                    "device": dev.get("path") or f"/dev/{dev['name']}", "table": "", "parts": parts, "sort": "",
                    "system": any(p["system"] for p in parts)})
    return out


def snapshot() -> dict:
    """{"udisks": bool, "drives": [...]} for the panel; each drive has its partitions in disk order."""
    objs = _objects()
    if objs is None:
        return {"udisks": False, "drives": _from_lsblk()}
    return {"udisks": True, "drives": _from_udisks(objs)}


# ---------------------------------------------------------------- actions
def _call(path: str, iface: str, method: str, *args, timeout=ACTION_TIMEOUT):
    dbus = _dbus()
    bus = _bus()
    try:
        obj = bus.get_object(UDISKS, path)
        return _py(getattr(dbus.Interface(obj, iface), method)(*args, dbus.Dictionary({}, signature="sv"),
                                                               timeout=timeout / 1000))
    except dbus.DBusException as e:
        raise _err(e) from None
    finally:
        bus.close()


def _check_path(path: str):
    if not path.startswith(ROOT + "/") or ".." in path:
        raise DriveError(tr("grimoire.spells.systeml.drives", "not a udisks device"))


def mount(block: str) -> str:
    """Mount a file system where udisks puts it (/media/<you>/<label>); returns the folder."""
    _check_path(block)
    return _call(block, I["Filesystem"], "Mount")


def unmount(block: str, mounts: list[str]) -> str:
    _check_path(block)
    if any(is_system_mount(m) for m in mounts):
        raise DriveError(tr("grimoire.spells.systeml.drives", "the system runs from it, so it stays mounted"))
    _call(block, I["Filesystem"], "Unmount")
    return tr("grimoire.spells.systeml.drives", "unmounted")


def power_off(drive: dict) -> str:
    """Safely remove: unmount every file system on the drive, then power it off (or eject the media)."""
    _check_path(drive["object"])
    if drive.get("system"):
        raise DriveError(tr("grimoire.spells.systeml.drives", "the system runs from this drive"))
    for p in drive["parts"]:
        if p["mounts"] and p["can_mount"]:
            _call(p.get("inner") or p["object"], I["Filesystem"], "Unmount")
        if p.get("unlocked"):
            _call(p["object"], I["Encrypted"], "Lock")
    if drive["can_power_off"]:
        _call(drive["object"], I["Drive"], "PowerOff")
        return tr("grimoire.spells.systeml.drives", "safe to unplug")
    if drive["ejectable"]:
        _call(drive["object"], I["Drive"], "Eject")
        return tr("grimoire.spells.systeml.drives", "ejected")
    return tr("grimoire.spells.systeml.drives", "unmounted; safe to unplug")


def eject(drive: dict) -> str:
    _check_path(drive["object"])
    for p in drive["parts"]:
        if p["mounts"] and p["can_mount"]:
            _call(p.get("inner") or p["object"], I["Filesystem"], "Unmount")
    _call(drive["object"], I["Drive"], "Eject")
    return tr("grimoire.spells.systeml.drives", "ejected")


# ---------------------------------------------------------------- health
def health(drive: dict) -> dict:
    """Detailed health: {"verdict": "good"|"failing"|"unknown", "rows": [(name, value)], "source", "note"}.
    Values are raw numbers or text; the UI words them. Tries udisks, then smartctl."""
    rows: list[tuple[str, object]] = []
    h = drive.get("health") or {}
    note = ""
    if drive.get("object") and h.get("source") == "nvme":
        try:
            a = _call(drive["object"], I["NVMe.Controller"], "SmartGetAttributes", timeout=15000)
        except DriveError as e:
            a, note = {}, str(e)
        temps = [t - 273.15 for t in a.get("temp_sensors", []) if t]
        rows = [("temp", h.get("temp")), ("hours", h.get("hours")), ("percent_used", a.get("percent_used")),
                ("avail_spare", a.get("avail_spare")), ("spare_thresh", a.get("spare_thresh")),
                ("written", (a.get("total_data_written") or 0) or None), ("read", (a.get("total_data_read") or 0)
                                                                          or None),
                ("power_cycles", a.get("power_cycles")), ("unsafe_shutdowns", a.get("unsafe_shutdowns")),
                ("media_errors", a.get("media_errors")), ("error_log", a.get("num_err_log_entries")),
                ("sensors", temps or None), ("selftest", h.get("selftest") or None)]
        bad = h.get("failing") or (a.get("media_errors") or 0) > 0 or (
            a.get("avail_spare") is not None and a.get("spare_thresh") is not None
            and a["avail_spare"] <= a["spare_thresh"])
        return {"verdict": "failing" if bad else "good", "rows": [r for r in rows if r[1] is not None],
                "source": "udisks", "warnings": h.get("warnings", []), "note": note}
    if drive.get("object") and h.get("source") == "ata" and h.get("failing") is not None:
        try:
            attrs = _call(drive["object"], I["Drive.Ata"], "SmartGetAttributes", timeout=15000)
        except DriveError as e:
            attrs, note = [], str(e)
        rows = [("temp", h.get("temp")), ("hours", h.get("hours")), ("bad_sectors", h.get("bad_sectors")),
                ("selftest", h.get("selftest") or None)]
        failing_attr = False
        for a in attrs:
            try:
                aid, name, _flags, value, worst, thresh, pretty, unit = a[:8]
            except (TypeError, ValueError):
                continue
            if thresh > 0 and 0 < value <= thresh:
                failing_attr = True
            rows.append(("ata", (aid, name, value, worst, thresh, pretty, unit)))
        return {"verdict": "failing" if h["failing"] or failing_attr else "good",
                "rows": [r for r in rows if r[1] is not None], "source": "udisks", "warnings": [], "note": note}
    return _smartctl(drive)


def _smartctl(drive: dict) -> dict:
    tool = shutil.which("smartctl")
    dev = drive.get("device", "")
    empty = {"verdict": "unknown", "rows": [], "source": "", "warnings": []}
    if not tool or not dev.startswith("/dev/"):
        return empty | {"note": tr("grimoire.spells.systeml.drives", "This drive doesn't report its health to "
                                                                     "udisks.")}
    try:
        data = json.loads(subprocess.run([tool, "-j", "-H", "-A", dev], capture_output=True, text=True,
                                         timeout=20).stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        data = {}
    status = data.get("smart_status", {})
    if "passed" not in status:
        msgs = [m.get("string", "") for m in data.get("smartctl", {}).get("messages", [])]
        denied = any("ermission denied" in m for m in msgs)
        return empty | {"note": tr("grimoire.spells.systeml.drives", "smartctl needs root to read this drive; "
                                                                     "udisks has no health data for it.")
                        if denied else tr("grimoire.spells.systeml.drives", "No health data for this drive.")}
    rows = [("temp", data.get("temperature", {}).get("current")),
            ("hours", data.get("power_on_time", {}).get("hours")), ("power_cycles", data.get("power_cycle_count"))]
    for a in data.get("ata_smart_attributes", {}).get("table", []):
        rows.append(("ata", (a.get("id"), a.get("name", ""), a.get("value"), a.get("worst"), a.get("thresh"),
                             a.get("raw", {}).get("value"), 1)))
    log = data.get("nvme_smart_health_information_log", {})
    for key in ("percent_used", "available_spare", "media_errors", "unsafe_shutdowns"):
        if key in log:
            rows.append(({"available_spare": "avail_spare"}.get(key, key), log[key]))
    return {"verdict": "good" if status["passed"] else "failing", "rows": [r for r in rows if r[1] is not None],
            "source": "smartctl", "warnings": [], "note": ""}


def partition_manager() -> str | None:
    """KDE Partition Manager's command when it's installed."""
    return shutil.which(PARTITION_MANAGER)
