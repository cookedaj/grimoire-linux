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

RUN = subprocess.run          # tests swap this for a stub, so nothing really changes the sound setup
OWN_PREFIX = "grimoire-audiol"       # AudioL's own level-meter streams, hidden from the Apps list
EQ_NODE = "grimoire_eq"              # the equalizer's virtual output (eq.py writes it)
MAX_VOLUME = 150                     # percent, like Plasma's "raise maximum volume"


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
        raise RuntimeError((r.stderr or "pw-dump failed").strip().splitlines()[-1])
    return json.loads(r.stdout or "[]")


def _truthy(v) -> bool:
    return v is True or v == "true" or v == 1


def _volume(params: dict) -> tuple[int, bool, int]:
    """(percent on the cubic scale, muted, channels) from a node's Props."""
    props = (params.get("Props") or [{}])[0] or {}
    vols = props.get("channelVolumes") or []
    lin = max(vols) if vols else props.get("volume", 1.0)
    return round(max(0.0, float(lin)) ** (1 / 3) * 100), bool(props.get("mute", False)), len(vols)


def _label(p: dict) -> str:
    return p.get("node.description") or p.get("node.nick") or p.get("node.name") or "?"


def parse(objs: list[dict]) -> dict:
    """{'outputs', 'inputs', 'playing', 'recording', 'cards', 'default_output', 'default_input'} from pw-dump."""
    defaults = {}
    nodes, cards, links = {}, [], []
    for o in objs:
        kind = o.get("type", "")
        if kind.endswith(":Metadata") and (o.get("props") or {}).get("metadata.name") == "default":
            for m in o.get("metadata") or []:
                val = m.get("value")
                if m.get("key") in ("default.audio.sink", "default.audio.source") and isinstance(val, dict):
                    defaults[m["key"]] = val.get("name", "")
        elif kind.endswith(":Link"):
            info = o.get("info") or {}
            links.append((info.get("output-node-id"), info.get("input-node-id")))
        elif kind.endswith(":Node") and o.get("info"):
            nodes[o["id"]] = o
        elif kind.endswith(":Device") and o.get("info"):
            p = o["info"].get("props") or {}
            if p.get("media.class") == "Audio/Device":
                cards.append(_card(o))

    out = {"outputs": [], "inputs": [], "playing": [], "recording": [], "cards": cards,
           "default_output": defaults.get("default.audio.sink", ""),
           "default_input": defaults.get("default.audio.source", "")}
    linked: dict[int, list[int]] = {}
    for a, b in links:
        linked.setdefault(a, []).append(b)
        linked.setdefault(b, []).append(a)
    for nid, o in nodes.items():
        p = o["info"].get("props") or {}
        cls = p.get("media.class", "")
        pct, mute, chans = _volume(o["info"].get("params") or {})
        base = {"id": nid, "serial": p.get("object.serial", nid), "name": p.get("node.name", ""), "volume": pct,
                "mute": mute, "channels": chans, "state": o["info"].get("state", "")}
        if cls in ("Audio/Sink", "Audio/Source", "Audio/Source/Virtual", "Audio/Duplex"):
            dev = {**base, "label": _label(p), "card": p.get("device.id"), "virtual": p.get("device.id") is None,
                   "eq": p.get("node.name") == EQ_NODE}
            if cls == "Audio/Sink":
                dev["default"] = dev["name"] == out["default_output"]
                out["outputs"].append(dev)
            else:
                dev["default"] = dev["name"] == out["default_input"]
                out["inputs"].append(dev)
        elif cls in ("Stream/Output/Audio", "Stream/Input/Audio"):
            if p.get("node.name", "").startswith(OWN_PREFIX) or _truthy(p.get("node.passive")) \
                    or p.get("node.name", "").startswith(EQ_NODE):
                continue                          # our meters, filter-chain internals (the EQ's own playback)
            app = p.get("application.name") or p.get("node.name") or "?"
            out["playing" if cls == "Stream/Output/Audio" else "recording"].append(
                {**base, "app": app, "media": p.get("media.name", ""), "icon": p.get("application.icon-name", ""),
                 "binary": p.get("application.process.binary", ""), "pid": p.get("application.process.id"),
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
    p, params = info.get("props") or {}, info.get("params") or {}
    active = (params.get("Profile") or [{}])[0] or {}
    profiles = [{"index": x.get("index"), "name": x.get("name", ""), "label": x.get("description") or x.get("name", ""),
                 "available": x.get("available", "unknown") != "no", "priority": x.get("priority", 0)}
                for x in params.get("EnumProfile") or [] if isinstance(x, dict)]
    return {"id": o["id"], "name": p.get("device.name", ""),
            "label": p.get("device.description") or p.get("device.nick") or p.get("device.name", "?"),
            "bus": p.get("device.bus", ""), "form": p.get("device.form-factor", ""),
            "profile": active.get("index"), "profile_name": active.get("name", ""), "profiles": profiles}


def snapshot() -> dict:
    return parse(dump())


def default(snap: dict, kind="outputs") -> dict | None:
    return next((d for d in snap[kind] if d["default"]), None)


def status_line() -> str:
    """Output · <device> · 45% (or muted), for the home card and the tray."""
    if not available():
        return "PipeWire not found"
    try:
        out = default(snapshot())
    except Exception:
        return "PipeWire not answering"
    if not out:
        return "No output"
    vol = "muted" if out["mute"] else f"{out['volume']}%"
    return "Output · {name} · {volume}".format(name=out["label"], volume=vol)


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
    """Send one app's stream to another output (or a recording to another input)."""
    if shutil.which("pactl"):
        verb = "move-sink-input" if playing else "move-source-output"
        return _check(_run("pactl", verb, str(int(stream["serial"])), device["name"]), "move")
    return _check(_run("pw-metadata", "-n", "default", str(int(stream["id"])), "target.object",
                       str(int(device["serial"]))), "move")


def set_props(node_id: int, params: dict[str, float]) -> str:
    """Change a filter-chain's controls live (e.g. {'eq_1:Gain': 3.0}) without restarting it."""
    flat = " ".join(f'"{k}" {float(v):.3f}' for k, v in params.items())
    return _check(_run("pw-cli", "set-param", str(int(node_id)), "Props", f"{{ params = [ {flat} ] }}"), "set")
