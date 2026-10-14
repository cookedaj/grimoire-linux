# SPDX-License-Identifier: GPL-3.0-or-later
"""AudioL's view of PipeWire: one `pw-dump` (a JSON list of every object, ~15 ms) read into outputs, inputs, app
streams and sound cards, and the few writes AudioL makes, all through WirePlumber's own `wpctl` as you (no root).

Volumes: PipeWire stores linear channel volumes; wpctl, Plasma and pavucontrol show their cube root (a "cubic"
scale that matches how loud it sounds), so 0.064 linear reads 40%. AudioL shows and sets that same scale.

Moving a stream to another output uses pipewire-pulse's `pactl move-sink-input` when pactl is installed (its
stream index is PipeWire's object.serial), else WirePlumber's `target.object` metadata through pw-metadata.
No Qt here: the page calls these on a worker thread. RUN is the stub point for tests.
"""
import json
import shutil
import subprocess

from grimoire import i18n
from grimoire.i18n import tr

RUN = subprocess.run          # tests swap this for a stub, so nothing really changes the sound setup
OWN_PREFIX = "grimoire-audiol"       # AudioL's own level-meter streams, hidden from the Apps list
EQ_NODE = "grimoire_eq"              # the equalizer's virtual output (eq.py writes it)
MAX_VOLUME = 150                     # percent, like Plasma's "raise maximum volume"


def isolate(text: str) -> str:
    """A device or app name set into a translated sentence, as its own direction island (FSI…PDI) in a
    right-to-left language, so "Couldn't change Built-in Speakers: …" keeps its order."""
    return f"\u2068{text}\u2069" if text and i18n.rtl() else text


def lead(text: str) -> str:
    """A label made of a name only (a device's title): starts right-to-left in a right-to-left language, so it lines
    up with the translated text around it instead of hugging the other side."""
    return "\u200f" + text if text and i18n.rtl() else text


def available() -> bool:
    return shutil.which("pw-dump") is not None and shutil.which("wpctl") is not None


def _run(*args: str, timeout=10) -> subprocess.CompletedProcess:
    try:
        return RUN(list(args), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as err:
        return subprocess.CompletedProcess(args, 1, "", str(err))


def _check(r: subprocess.CompletedProcess, what: str) -> str:
    if r.returncode:
        msg = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(msg[-1] if msg else f"{what} failed ({r.returncode})")
    return "done"


# ---------------------------------------------------------------- reads
def dump() -> list[dict]:
    r = _run("pw-dump", timeout=10)
    if r.returncode:
        raise RuntimeError(((r.stderr or "").strip() or "pw-dump failed").splitlines()[-1])
    objs = json.loads(r.stdout or "[]")
    return [o for o in objs if isinstance(o, dict)] if isinstance(objs, list) else []


def _str(v, default="") -> str:
    """A property as text. pw-dump prints any value that looks like a number or a boolean bare, so an app named
    "2048" arrives as the number 2048; anything else (lists, objects) counts as missing."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v) if isinstance(v, (str, int, float)) else default


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _truthy(v) -> bool:
    return v is True or v == "true" or v == 1


def _volume(params: dict) -> tuple[int, bool, int]:
    """(percent on the cubic scale, muted, channels) from a node's Props."""
    props = params.get("Props") if isinstance(params.get("Props"), list) else []
    props = _dict(props[0]) if props else {}
    vols = [v for v in props.get("channelVolumes") or [] if isinstance(v, (int, float))] \
        if isinstance(props.get("channelVolumes"), list) else []
    lin = max(vols) if vols else props.get("volume", 1.0)
    try:
        pct = round(max(0.0, float(lin)) ** (1 / 3) * 100)
    except (TypeError, ValueError, OverflowError):
        pct = 0
    return min(pct, 1000), props.get("mute") is True, len(vols)


def _label(p: dict) -> str:
    return _str(p.get("node.description")) or _str(p.get("node.nick")) or _str(p.get("node.name")) or "?"


def parse(objs: list[dict]) -> dict:
    """{'outputs', 'inputs', 'playing', 'recording', 'cards', 'default_output', 'default_input'} from pw-dump."""
    defaults = {}
    nodes, cards, links = {}, [], []
    for o in objs:
        if not isinstance(o, dict) or _int(o.get("id")) is None:
            continue
        kind = _str(o.get("type"))
        info = _dict(o.get("info"))
        if kind.endswith(":Metadata") and _dict(o.get("props")).get("metadata.name") == "default":
            for m in o.get("metadata") if isinstance(o.get("metadata"), list) else []:
                val = _dict(m).get("value")
                if _dict(m).get("key") in ("default.audio.sink", "default.audio.source") and isinstance(val, dict):
                    defaults[m["key"]] = _str(val.get("name"))
        elif kind.endswith(":Link"):
            links.append((info.get("output-node-id"), info.get("input-node-id")))
        elif kind.endswith(":Node") and info:
            nodes[int(o["id"])] = o
        elif kind.endswith(":Device") and info:
            if _dict(info.get("props")).get("media.class") == "Audio/Device":
                cards.append(_card(o))

    out = {"outputs": [], "inputs": [], "playing": [], "recording": [], "cards": cards,
           "default_output": defaults.get("default.audio.sink", ""),
           "default_input": defaults.get("default.audio.source", "")}
    linked: dict[int, list[int]] = {}
    for a, b in links:
        linked.setdefault(a, []).append(b)
        linked.setdefault(b, []).append(a)
    for nid, o in nodes.items():
        p = _dict(o["info"].get("props"))
        cls = _str(p.get("media.class"))
        pct, mute, chans = _volume(_dict(o["info"].get("params")))
        name = _str(p.get("node.name"))
        base = {"id": nid, "serial": _int(p.get("object.serial"), nid), "name": name, "volume": pct,
                "mute": mute, "channels": chans, "state": _str(o["info"].get("state"))}
        if cls in ("Audio/Sink", "Audio/Source", "Audio/Source/Virtual", "Audio/Duplex"):
            dev = {**base, "label": _label(p), "card": _int(p.get("device.id")), "virtual": p.get("device.id") is None,
                   "eq": name == EQ_NODE}
            if cls == "Audio/Sink":
                dev["default"] = dev["name"] == out["default_output"]
                out["outputs"].append(dev)
            else:
                dev["default"] = dev["name"] == out["default_input"]
                out["inputs"].append(dev)
        elif cls in ("Stream/Output/Audio", "Stream/Input/Audio"):
            if name.startswith(OWN_PREFIX) or _truthy(p.get("node.passive")) or name.startswith(EQ_NODE):
                continue                          # our meters, filter-chain internals (the EQ's own playback)
            app = _str(p.get("application.name")) or name or "?"
            out["playing" if cls == "Stream/Output/Audio" else "recording"].append(
                {**base, "app": app, "media": _str(p.get("media.name")), "icon": _str(p.get("application.icon-name")),
                 "binary": _str(p.get("application.process.binary")), "pid": _int(p.get("application.process.id")),
                 "peers": linked.get(nid, [])})
    devs = {d["id"]: d for d in out["outputs"] + out["inputs"]}
    for s in out["playing"] + out["recording"]:
        s["target"] = next((devs[i]["id"] for i in s.pop("peers") if i in devs), None)
    for key in ("outputs", "inputs"):
        out[key].sort(key=lambda d: (d["virtual"], d["label"].lower()))
    for key in ("playing", "recording"):
        out[key].sort(key=lambda s: (s["app"].lower(), s["id"]))
    return out


def _card(o: dict) -> dict:
    info = o["info"]
    p, params = _dict(info.get("props")), _dict(info.get("params"))
    active = params.get("Profile") if isinstance(params.get("Profile"), list) else []
    active = _dict(active[0]) if active else {}
    enum = params.get("EnumProfile") if isinstance(params.get("EnumProfile"), list) else []
    profiles = [{"index": _int(x.get("index")), "name": _str(x.get("name")),
                 "label": _str(x.get("description")) or _str(x.get("name")),
                 "available": x.get("available", "unknown") != "no", "priority": _int(x.get("priority"), 0)}
                for x in enum if isinstance(x, dict) and _int(x.get("index")) is not None]
    return {"id": int(o["id"]), "name": _str(p.get("device.name")),
            "label": _str(p.get("device.description")) or _str(p.get("device.nick")) or _str(p.get("device.name"))
            or "?", "bus": _str(p.get("device.bus")), "form": _str(p.get("device.form-factor")),
            "profile": _int(active.get("index")), "profile_name": _str(active.get("name")), "profiles": profiles}


def snapshot() -> dict:
    return parse(dump())


def default(snap: dict, kind="outputs") -> dict | None:
    return next((d for d in snap[kind] if d["default"]), None)


def status_line() -> str:
    """Output · <device> · 45% (or muted), for the home card and the tray."""
    if not available():
        return tr("grimoire.spells.audiol.pw", "PipeWire not found")
    try:
        out = default(snapshot())
    except Exception:
        return tr("grimoire.spells.audiol.pw", "PipeWire not answering")
    if not out:
        return tr("grimoire.spells.audiol.pw", "No output")
    vol = tr("grimoire.spells.audiol.pw",
             "muted") if out["mute"] else tr("grimoire.spells.audiol.pw", "{n}%").format(n=out["volume"])
    return tr("grimoire.spells.audiol.pw", "Output · {name} · {volume}").format(name=isolate(out["label"]),
                                                                              volume=vol)


# ---------------------------------------------------------------- writes
def set_default(node_id: int) -> str:
    return _check(_run("wpctl", "set-default", str(int(node_id))), "set default")


def set_volume(node_id: int, percent: int) -> str:
    pct = max(0, min(MAX_VOLUME, int(percent)))
    return _check(_run("wpctl", "set-volume", "-l", f"{MAX_VOLUME / 100:.2f}", str(int(node_id)),
                       f"{pct / 100:.2f}"), "set volume")


def set_mute(node_id: int, mute: bool) -> str:
    return _check(_run("wpctl", "set-mute", str(int(node_id)), "1" if mute else "0"), "mute")


def set_profile(card_id: int, index: int) -> str:
    return _check(_run("wpctl", "set-profile", str(int(card_id)), str(int(index))), "set profile")


def move_stream(stream: dict, device: dict, playing=True) -> str:
    """Send one app's stream to another output (or a recording to another input). Devices go by serial (pactl's
    index too), never by name: a name like "42" or "-x" would read as another index or an option."""
    if shutil.which("pactl"):
        verb = "move-sink-input" if playing else "move-source-output"
        return _check(_run("pactl", verb, str(int(stream["serial"])), str(int(device["serial"]))), "move")
    return _check(_run("pw-metadata", "-n", "default", str(int(stream["id"])), "target.object",
                       str(int(device["serial"]))), "move")


def set_props(node_id: int, params: dict[str, float]) -> str:
    """Change a filter-chain's controls live (e.g. {'eq_1:Gain': 3.0}) without restarting it."""
    flat = " ".join(f'"{k}" {float(v):.3f}' for k, v in params.items())
    return _check(_run("pw-cli", "set-param", str(int(node_id)), "Props", f"{{ params = [ {flat} ] }}"), "set")
