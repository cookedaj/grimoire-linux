# SPDX-License-Identifier: GPL-3.0-or-later
"""Mice, touchpads and the keyboard (no Qt).

Pointers are KWin's: /org/kde/KWin/InputDevice/<event> objects whose properties KWin applies at once and saves in
kcminputrc itself (what KDE's Mouse and Touchpad modules do). A mouse often shows up as several event devices with the
same name; a change goes to all of them, as their saved settings are shared. Keyboard layouts live in kxkbrc
(written, then KWin is told to reload with the org.kde.keyboard reloadConfig signal) and the repeat in kcminputrc
(KWin watches it).
"""

import gettext
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from grimoire.spells.settingl import kde

KWIN, ROOT, IFACE = "org.kde.KWin", "/org/kde/KWin/InputDevice", "org.kde.KWin.InputDevice"
XKB_RULES = Path("/usr/share/X11/xkb/rules/evdev.xml")
REPEAT_DELAY, REPEAT_RATE = 600, 25  # KDE's defaults (ms, per second)
# the properties the page can switch, and the "supports…" property that says whether a device has it
BOOLS = {
    "naturalScroll": "supportsNaturalScroll",
    "leftHanded": "supportsLeftHanded",
    "middleEmulation": "supportsMiddleEmulation",
    "tapToClick": "tapFingerCount",
    "disableWhileTyping": "supportsDisableWhileTyping",
    "scrollTwoFinger": "supportsScrollTwoFinger",
    "scrollEdge": "supportsScrollEdge",
}


def pointers() -> list[dict]:
    """Mice and touchpads, one entry per physical device: name, touchpad, the event devices, their properties."""
    names = kde.bus_call(KWIN, ROOT, "org.kde.KWin.InputDeviceManager", "ListPointers", quiet=True)
    if not names:
        return []
    events = names[0] if names and isinstance(names[0], list) else names
    groups: dict[tuple, dict] = {}
    for ev in events:
        props = kde.bus_props(KWIN, f"{ROOT}/{ev}", IFACE)
        if not props or not props.get("pointer") or props.get("isVirtual") or props.get("tabletTool"):
            continue
        key = (props.get("vendor"), props.get("product"), props.get("name"))
        g = groups.setdefault(key, {"name": props.get("name", ev), "events": [], "props": {}, "touchpad": False})
        g["events"].append(ev)
        g["touchpad"] |= bool(props.get("touchpad"))
        if not g["props"] or (
            props.get("supportsPointerAcceleration") and not g["props"].get("supportsPointerAcceleration")
        ):
            g["props"] = props  # the interface that is really the pointer leads
    out = [g for g in groups.values() if g["touchpad"] or g["props"].get("supportsPointerAcceleration")]
    return sorted(out, key=lambda g: (g["touchpad"], g["name"].casefold()))


def supports(dev: dict, prop: str) -> bool:
    p = dev["props"]
    if prop == "pointerAcceleration":
        return bool(p.get("supportsPointerAcceleration"))
    if prop == "profile":
        return bool(
            p.get("supportsPointerAccelerationProfileFlat") and p.get("supportsPointerAccelerationProfileAdaptive")
        )
    if prop == "scrollFactor":
        return True
    flag = BOOLS.get(prop)
    return bool(flag and p.get(flag))


def set_prop(dev: dict, prop: str, value):
    """Set one property on every event device of a pointer (KWin saves it)."""
    if prop == "profile":
        flat = value == "flat"
        for ev in dev["events"]:
            kde.bus_set(KWIN, f"{ROOT}/{ev}", IFACE, "pointerAccelerationProfileFlat", "b", flat)
            kde.bus_set(KWIN, f"{ROOT}/{ev}", IFACE, "pointerAccelerationProfileAdaptive", "b", not flat)
        return
    if prop in ("pointerAcceleration", "scrollFactor"):
        lo, hi = (-1.0, 1.0) if prop == "pointerAcceleration" else (0.1, 20.0)
        value = max(lo, min(hi, float(value)))
        sig = "d"
    elif prop in BOOLS:
        value, sig = bool(value), "b"
    else:
        raise ValueError(prop)
    errors = []
    for ev in dev["events"]:
        try:
            kde.bus_set(KWIN, f"{ROOT}/{ev}", IFACE, prop, sig, value)
        except RuntimeError as e:  # an extra interface of the device may not have it
            errors.append(str(e))
    if len(errors) == len(dev["events"]):
        raise RuntimeError(errors[-1])


# ---------------------------------------------------------------- keyboard
def _xkb_gettext():
    try:
        from grimoire import i18n

        code = i18n.loaded() or i18n.current()
        return gettext.translation("xkeyboard-config", languages=[{"pt": "pt_BR"}.get(code, code)]).gettext
    except (OSError, ImportError):
        return lambda s: s


@lru_cache(maxsize=1)
def catalog() -> list[dict]:
    """Every layout and variant xkb knows: [{"layout", "variant", "label", "short"}], sorted by label."""
    try:
        root = ET.parse(XKB_RULES).getroot()
    except (OSError, ET.ParseError):
        return []
    t = _xkb_gettext()
    out = []
    for lay in root.iterfind("layoutList/layout"):
        ci = lay.find("configItem")
        name, desc = ci.findtext("name", ""), ci.findtext("description", "")
        short = ci.findtext("shortDescription", "") or name
        out.append({"layout": name, "variant": "", "label": t(desc) or name, "short": short})
        for var in lay.iterfind("variantList/variant"):
            vi = var.find("configItem")
            out.append(
                {
                    "layout": name,
                    "variant": vi.findtext("name", ""),
                    "label": t(vi.findtext("description", "")) or vi.findtext("name", ""),
                    "short": vi.findtext("shortDescription", "") or short,
                }
            )
    return sorted(out, key=lambda x: x["label"].casefold())


def label(layout: str, variant: str = "") -> str:
    hit = next((c for c in catalog() if c["layout"] == layout and c["variant"] == variant), None)
    return hit["label"] if hit else (f"{layout} ({variant})" if variant else layout)


def keyboard() -> dict:
    """{"layouts": [(layout, variant)], "configured": bool, "delay", "rate", "repeat": bool, "current": index}"""
    kx = kde.parse("kxkbrc").get(("Layout",), {})
    lays = [x.strip() for x in kx.get("LayoutList", "").split(",")]
    vars_ = [x.strip() for x in kx.get("VariantList", "").split(",")]
    configured = kde.as_bool(kx.get("Use", ""), False) and any(lays)
    pairs = [(lay, vars_[i] if i < len(vars_) else "") for i, lay in enumerate(lays) if lay] if configured else []
    current = 0
    live = kde.bus_call("org.kde.keyboard", "/Layouts", "org.kde.KeyboardLayouts", "getLayoutsList", quiet=True)
    if not pairs and live:
        pairs = [(x[0], x[1]) for x in (live[0] if live and isinstance(live[0], list) else [])]
    idx = kde.bus_call("org.kde.keyboard", "/Layouts", "org.kde.KeyboardLayouts", "getLayout", quiet=True)
    if idx:
        current = int(idx[0])
    kb = kde.parse("kcminputrc").get(("Keyboard",), {})
    return {
        "layouts": pairs or [("us", "")],
        "configured": configured,
        "current": current,
        "delay": kde.as_int(kb.get("RepeatDelay", ""), REPEAT_DELAY),
        "rate": float(kb.get("RepeatRate", "") or REPEAT_RATE),
        "repeat": kb.get("KeyRepeat", "repeat") != "nothing",
    }


def set_layouts(pairs: list[tuple[str, str]]):
    """Save the layout list (first = default) and have KWin load it."""
    known = {(c["layout"], c["variant"]) for c in catalog()}
    if not pairs or any(p not in known for p in pairs):
        raise ValueError(pairs)
    kde.write("kxkbrc", "Layout", "Use", True)
    kde.write("kxkbrc", "Layout", "LayoutList", ",".join(p[0] for p in pairs))
    kde.write("kxkbrc", "Layout", "VariantList", ",".join(p[1] for p in pairs))
    kde.write("kxkbrc", "Layout", "DisplayNames", ",".join("" for _ in pairs))
    kde.check(["gdbus", "emit", "--session", "--object-path", "/Layouts", "--signal", "org.kde.keyboard.reloadConfig"])


def set_repeat(repeat: bool | None = None, delay: int | None = None, rate: float | None = None):
    if repeat is not None:
        kde.write("kcminputrc", "Keyboard", "KeyRepeat", "repeat" if repeat else "nothing")
    if delay is not None:
        kde.write("kcminputrc", "Keyboard", "RepeatDelay", int(max(100, min(5000, delay))))
    if rate is not None:
        kde.write("kcminputrc", "Keyboard", "RepeatRate", f"{max(0.2, min(100.0, rate)):g}")
