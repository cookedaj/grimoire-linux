# SPDX-License-Identifier: GPL-3.0-or-later
"""Bluetooth through BlueZ's D-Bus API (no Qt): adapters, paired devices, power, connect and disconnect.

Pairing a new device needs an agent to confirm codes, which KDE's Bluedevil already is: "Add a device" opens its
wizard (bluedevil-wizard) instead of a half-done one here. Nothing here pairs, forgets or trusts devices.
"""

import re

from grimoire.spells.settingl import kde

BLUEZ = "org.bluez"
# BlueZ's Icon names (freedesktop device icons) → our words for them
KINDS = (
    "audio-headset",
    "audio-headphones",
    "audio-card",
    "input-mouse",
    "input-keyboard",
    "input-gaming",
    "input-tablet",
    "phone",
    "computer",
    "camera-video",
    "printer",
    "multimedia-player",
)
PATH = re.compile(r"/org/bluez/hci\d+(/dev(_[0-9A-F]{2}){6})?")


def state() -> dict:
    """{"available": bool, "adapters": [...], "devices": [...]} — devices are the paired (or connected) ones."""
    r = kde.RUN(
        [
            "busctl",
            "--system",
            "--json=short",
            "call",
            BLUEZ,
            "/",
            "org.freedesktop.DBus.ObjectManager",
            "GetManagedObjects",
        ],
        10,
    )
    if r.returncode:
        return {"available": False, "adapters": [], "devices": []}
    import json

    try:
        objs = kde._plain(json.loads(r.stdout)["data"][0])
    except (ValueError, KeyError, IndexError):
        return {"available": False, "adapters": [], "devices": []}
    adapters, devices = [], []
    for path, ifaces in sorted(objs.items()):
        if "org.bluez.Adapter1" in ifaces:
            a = ifaces["org.bluez.Adapter1"]
            adapters.append(
                {
                    "path": path,
                    "name": a.get("Alias") or a.get("Name") or path.rsplit("/", 1)[-1],
                    "powered": bool(a.get("Powered")),
                    "state": a.get("PowerState", ""),
                    "discovering": bool(a.get("Discovering")),
                }
            )
        if "org.bluez.Device1" in ifaces:
            d = ifaces["org.bluez.Device1"]
            if not (d.get("Paired") or d.get("Bonded") or d.get("Connected")):
                continue
            battery = ifaces.get("org.bluez.Battery1", {}).get("Percentage")
            devices.append(
                {
                    "path": path,
                    "adapter": d.get("Adapter", ""),
                    "name": d.get("Alias") or d.get("Name") or d.get("Address", ""),
                    "icon": d.get("Icon", ""),
                    "connected": bool(d.get("Connected")),
                    "paired": bool(d.get("Paired")),
                    "trusted": bool(d.get("Trusted")),
                    "battery": battery,
                }
            )
    devices.sort(key=lambda d: (not d["connected"], d["name"].casefold()))
    return {"available": bool(adapters), "adapters": adapters, "devices": devices}


def _check_path(path: str):
    if not PATH.fullmatch(path or ""):
        raise ValueError(path)


def set_power(adapter: str, on: bool):
    _check_path(adapter)
    kde.bus_set(BLUEZ, adapter, "org.bluez.Adapter1", "Powered", "b", bool(on), system=True)


def connect(device: str, on: bool):
    _check_path(device)
    kde.bus_call(BLUEZ, device, "org.bluez.Device1", "Connect" if on else "Disconnect", system=True, timeout=40)


def add_device():
    """KDE's pairing wizard (it is the agent that confirms the codes)."""
    if kde.have("bluedevil-wizard"):
        kde.LAUNCH(["bluedevil-wizard"])
    else:
        kde.OPEN("kcm_bluetooth")
