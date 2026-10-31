# SPDX-License-Identifier: GPL-3.0-or-later
"""Screens and night light (no Qt).

Screens are read and changed with kscreen-doctor, KDE's own tool: every change of one Apply goes in a single call,
so KWin applies it at once, and the page keeps the previous layout to put back if you don't confirm it (like KDE's
"Keep display configuration?"). Monitor names come from the EDID the kernel exposes. Night light is KWin's: the
NightColor group of kwinrc, written with --notify so KWin reloads it, and read live from its D-Bus object.
"""

from pathlib import Path

from grimoire.spells.settingl import kde

DRM = Path("/sys/class/drm")
ROTATIONS = {1: "none", 2: "left", 4: "inverted", 8: "right"}  # KScreen's values → kscreen-doctor's names
NIGHT_MIN, NIGHT_MAX, NIGHT_DEFAULT = 1000, 6500, 4500
NIGHT_PATH = "/org/kde/KWin/NightLight"


def edid_name(connector: str) -> str:
    """The monitor's own name (EDID descriptor 0xFC), e.g. "DELL U2720Q"; "" when unknown."""
    for f in DRM.glob(f"card*-{connector}/edid"):
        try:
            data = f.read_bytes()
        except OSError:
            continue
        for off in (54, 72, 90, 108):
            block = data[off : off + 18]
            if len(block) == 18 and block[:3] == b"\0\0\0" and block[3] == 0xFC:
                return block[5:].split(b"\n")[0].decode("ascii", "replace").strip()
    return ""


def _mode(m: dict) -> dict:
    return {
        "id": str(m["id"]),
        "w": m["size"]["width"],
        "h": m["size"]["height"],
        "rate": round(float(m.get("refreshRate", 0)), 2),
    }


def read() -> dict:
    """{"outputs": [...], "error": str}. Each output: id, name (connector), label, enabled, primary, x, y, mode
    (id), modes, scale, rotation (name), preferred (mode ids)."""
    r = kde.RUN(["kscreen-doctor", "-j"], 15)
    if r.returncode:
        return {"outputs": [], "error": ((r.stderr or "").strip().splitlines() or ["kscreen-doctor"])[-1]}
    import json

    try:
        data = json.loads(r.stdout)
    except ValueError:
        return {"outputs": [], "error": "kscreen-doctor"}
    outs = []
    for o in data.get("outputs", []):
        if not o.get("connected"):
            continue
        modes = [_mode(m) for m in o.get("modes", [])]
        outs.append(
            {
                "id": o["id"],
                "name": o["name"],
                "label": edid_name(o["name"]),
                "enabled": bool(o.get("enabled")),
                "priority": o.get("priority", 0),
                "primary": o.get("priority") == 1,
                "x": o.get("pos", {}).get("x", 0),
                "y": o.get("pos", {}).get("y", 0),
                "mode": str(o.get("currentModeId", "")),
                "modes": modes,
                "preferred": [str(p) for p in o.get("preferredModes", [])],
                "scale": round(float(o.get("scale", 1)), 2),
                "rotation": ROTATIONS.get(o.get("rotation", 1), "none"),
                "type": o.get("type", 0),
                "mm": (o.get("sizeMM", {}).get("width", 0), o.get("sizeMM", {}).get("height", 0)),
            }
        )
    outs.sort(key=lambda o: (not o["enabled"], o["x"], o["y"]))
    return {"outputs": outs, "error": ""}


def mode_of(out: dict, mid: str | None = None) -> dict | None:
    mid = out["mode"] if mid is None else mid
    return next((m for m in out["modes"] if m["id"] == mid), None)


def logical_size(out: dict) -> tuple[int, int]:
    """Size on the desktop: the mode, turned, divided by the scale."""
    m = mode_of(out) or {"w": 1920, "h": 1080}
    w, h = m["w"], m["h"]
    if out["rotation"] in ("left", "right"):
        w, h = h, w
    s = out["scale"] or 1
    return round(w / s), round(h / s)


def sizes(out: dict) -> list[tuple[int, int]]:
    """Resolutions, biggest first."""
    return sorted({(m["w"], m["h"]) for m in out["modes"]}, key=lambda s: (-s[0] * s[1], -s[0]))


def rates(out: dict, size: tuple[int, int]) -> list[dict]:
    """The modes of one resolution, fastest first."""
    return sorted((m for m in out["modes"] if (m["w"], m["h"]) == size), key=lambda m: -m["rate"])


def tidy(outs: list[dict]):
    """Moves the layout so its top-left screen sits at 0,0 (KWin wants no negative positions)."""
    on = [o for o in outs if o["enabled"]]
    if not on:
        return
    dx, dy = min(o["x"] for o in on), min(o["y"] for o in on)
    for o in on:
        o["x"] -= dx
        o["y"] -= dy


def reflow(outs: list[dict], changed: dict, old_size: tuple[int, int]):
    """A screen changed size: screens that touched its right or bottom edge move with that edge."""
    new = logical_size(changed)
    dw, dh = new[0] - old_size[0], new[1] - old_size[1]
    for o in outs:
        if o is changed or not o["enabled"]:
            continue
        if dw and o["x"] >= changed["x"] + old_size[0] - 1:
            o["x"] += dw
        if dh and o["y"] >= changed["y"] + old_size[1] - 1 and o["x"] < changed["x"] + old_size[0]:
            o["y"] += dh


def _scale(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def args_for(outs: list[dict], before: list[dict] | None = None) -> list[str]:
    """kscreen-doctor arguments that make the screens look like outs (only what differs from before)."""
    old = {o["name"]: o for o in before or []}
    args: list[str] = []
    for o in outs:
        p, b = f"output.{o['name']}.", old.get(o["name"])
        if not o["enabled"]:
            if not b or b["enabled"]:
                args.append(p + "disable")
            continue
        if not b or not b["enabled"]:
            args.append(p + "enable")
        if not b or b["mode"] != o["mode"] or not b["enabled"]:
            args.append(p + f"mode.{o['mode']}")
        if not b or abs(b["scale"] - o["scale"]) > 0.001:
            args.append(p + f"scale.{_scale(o['scale'])}")
        if not b or b["rotation"] != o["rotation"]:
            args.append(p + f"rotation.{o['rotation']}")
        if not b or (b["x"], b["y"]) != (o["x"], o["y"]):
            args.append(p + f"position.{o['x']},{o['y']}")
        if o["primary"] and (not b or not b["primary"]):
            args.append(p + "priority.1")
    return args


def apply(outs: list[dict], before: list[dict]):
    """Apply a whole layout in one kscreen-doctor call. Raises with its message."""
    args = args_for(outs, before)
    if args:
        kde.check(["kscreen-doctor", *args], 30)


def revert(before: list[dict]):
    """Put a previous layout back in full."""
    kde.check(["kscreen-doctor", *args_for(before)], 30)


# ---------------------------------------------------------------- night light
def night() -> dict:
    """Night light: what kwinrc says, and what KWin is doing now (when it answers)."""
    cfg = kde.parse("kwinrc").get(("NightColor",), {})
    live = kde.bus_props("org.kde.KWin", NIGHT_PATH, "org.kde.KWin.NightLight")
    return {
        "active": kde.as_bool(cfg.get("Active", ""), False),
        "mode": "constant" if cfg.get("Mode", "") == "Constant" else "daynight",
        "temperature": max(NIGHT_MIN, min(NIGHT_MAX, kde.as_int(cfg.get("NightTemperature", ""), NIGHT_DEFAULT))),
        "available": live.get("available", True) if live else True,
        "running": bool(live.get("running")),
        "current": live.get("currentTemperature") or 0,
        "daylight": live.get("daylight"),
        "inhibited": bool(live.get("inhibited")),
        "live": bool(live),
    }


def set_night(active: bool | None = None, mode: str | None = None, temperature: int | None = None):
    if active is not None:
        kde.write("kwinrc", "NightColor", "Active", bool(active))
    if mode is not None:
        kde.write("kwinrc", "NightColor", "Mode", "Constant" if mode == "constant" else "DarkLight")
    if temperature is not None:
        kde.write("kwinrc", "NightColor", "NightTemperature", int(max(NIGHT_MIN, min(NIGHT_MAX, temperature))))
