# SPDX-License-Identifier: GPL-3.0-or-later
"""AudioL's system-wide equalizer, the PipeWire way: a filter-chain of builtin biquads (a preamp and ten peaking
bands) that shows up as one more output, "Grimoire EQ", and plays into the device you pick.

The chain lives in a drop-in config, `~/.config/pipewire/filter-chain.conf.d/grimoire-eq.conf`, run by PipeWire's
own filter-chain.service (a separate small daemon, so turning the EQ on or off restarts only that, never your
sound server). Without that unit the drop-in goes in `pipewire.conf.d/` and applying restarts pipewire.service,
which cuts the sound for a moment. Restarting is always an explicit button on the page, never automatic.

While it runs, moving a band changes it live (`pw-cli set-param … Props`) and rewrites the drop-in, so the next
login starts with the same curve. Every file written is checked with `spa-json-dump` (PipeWire's own parser)
first. Turning it off moves the drop-in aside into AudioL's config folder (it's AudioL's own file, regenerated
from audiol.json); a file of the same name that AudioL didn't write is moved aside under a free name, never
overwritten. No Qt here; RUN (pw.RUN) is the stub point for tests.
"""
import cmath
import json
import math
import os
import shutil
from pathlib import Path

from grimoire.fsutil import free_name
from grimoire.paths import CONFIG
from grimoire.spells.audiol import pw

FREQS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
Q = 1.41                           # one octave wide: neighbouring bands blend into a smooth curve
LIMIT = 12.0                       # dB either way
SETTINGS = CONFIG / "audiol.json"
ASIDE = CONFIG / "audiol"          # the drop-in rests here while the EQ is off
FILE = "grimoire-eq.conf"
MARK = "# Written by Grimoire Linux AudioL."
UNIT = "filter-chain.service"
PIPEWIRE_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pipewire"

PRESETS = {                        # name: (gains for FREQS, preamp); the preamp keeps boosted bands from clipping
    "Flat": ([0] * 10, 0.0),
    "Bass boost": ([6, 5, 4, 2, 0, 0, 0, 0, 0, 0], -6.0),
    "Vocal": ([-2, -2, -1, 1, 3, 4, 4, 2, 0, -1], -4.0),
    "Treble": ([0, 0, 0, 0, 0, 1, 2, 4, 5, 6], -6.0),
    "Loudness": ([5, 4, 2, 0, -1, -1, 0, 2, 4, 4], -5.0),
}
DEFAULTS = {"on": False, "gains": [0.0] * 10, "preamp": 0.0, "preset": "Flat", "output": "", "restore": "",
            "presets": {}, "enabled_unit": False}


# ---------------------------------------------------------------- settings
def _clamp(v, lo=-LIMIT, hi=LIMIT) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(v) else round(min(hi, max(lo, v)), 1)


def _gains(v) -> list[float]:
    return [_clamp(x) for x in v][:10] if isinstance(v, list) and len(v) == 10 else [0.0] * 10


def load() -> dict:
    """audiol.json's 'eq' section over the defaults, wrong types dropped and gains clamped."""
    try:
        saved = json.loads(SETTINGS.read_text()).get("eq", {})
    except (OSError, ValueError, AttributeError):
        saved = {}
    out = json.loads(json.dumps(DEFAULTS))
    if not isinstance(saved, dict):
        return out
    for k in ("on", "enabled_unit"):
        if isinstance(saved.get(k), bool):
            out[k] = saved[k]
    for k in ("preset", "output", "restore"):
        if isinstance(saved.get(k), str):
            out[k] = saved[k][:300]
    out["gains"] = _gains(saved.get("gains"))
    out["preamp"] = _clamp(saved.get("preamp", 0.0))
    if isinstance(saved.get("presets"), dict):
        out["presets"] = {str(n)[:60]: {"gains": _gains(p.get("gains")), "preamp": _clamp(p.get("preamp", 0))}
                          for n, p in list(saved["presets"].items())[:50] if isinstance(p, dict)}
    return out


def save(s: dict):
    try:
        whole = json.loads(SETTINGS.read_text())
        whole = whole if isinstance(whole, dict) else {}
    except (OSError, ValueError):
        whole = {}
    whole["eq"] = s
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(whole, indent=1))
    tmp.replace(SETTINGS)


def all_presets(s: dict) -> dict[str, tuple[list[float], float]]:
    return {**{n: (list(map(float, g)), p) for n, (g, p) in PRESETS.items()},
            **{n: (p["gains"], p["preamp"]) for n, p in s["presets"].items() if n not in PRESETS}}


def matching_preset(s: dict) -> str:
    """The preset the current curve is, or "" when it's been changed by hand."""
    for name, (gains, pre) in all_presets(s).items():
        if [round(g, 1) for g in gains] == s["gains"] and round(pre, 1) == s["preamp"]:
            return name
    return ""


def suggested_preamp(gains: list[float]) -> float:
    """Enough cut that the curve's highest point (neighbouring boosts add up) can't clip, in half-dB steps."""
    grid = [20 * 1000 ** (k / 199) for k in range(200)]
    peak = max(0.0, max(response(gains, 0.0, grid)))
    return _clamp(-math.ceil(peak * 2) / 2)


# ---------------------------------------------------------------- the curve (for drawing)
def _peaking(f0: float, gain: float, q: float, fs: float):
    a = 10 ** (gain / 40)
    w0 = 2 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2 * q)
    cw = math.cos(w0)
    return (1 + alpha * a, -2 * cw, 1 - alpha * a), (1 + alpha / a, -2 * cw, 1 - alpha / a)


def response(gains: list[float], preamp: float, freqs: list[float], fs=48000.0) -> list[float]:
    """The chain's gain in dB at each of freqs (RBJ cookbook biquads, the same ones PipeWire's builtins use)."""
    filters = [_peaking(f0, g, Q, fs) for f0, g in zip(FREQS, gains) if abs(g) > 1e-6]
    out = []
    for f in freqs:
        z = cmath.exp(-1j * 2 * math.pi * f / fs)
        h = 1 + 0j
        for (b0, b1, b2), (a0, a1, a2) in filters:
            h *= (b0 + b1 * z + b2 * z * z) / (a0 + a1 * z + a2 * z * z)
        out.append(20 * math.log10(max(abs(h), 1e-9)) + preamp)
    return out


# ---------------------------------------------------------------- the drop-in
def _quote(s: str) -> str:
    if any(c in s for c in "\n\r\0"):
        raise ValueError("bad device name")
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(gains: list[float], preamp: float, output: str) -> str:
    """The filter-chain drop-in for this curve, playing into the output named (node.name)."""
    gains = _gains(list(gains))
    nodes = ['                    { type = builtin name = pre label = bq_highshelf '
             f'control = {{ "Freq" = 0.0 "Q" = 1.0 "Gain" = {_clamp(preamp):.1f} }} }}']
    for i, (f, g) in enumerate(zip(FREQS, gains), 1):
        nodes.append(f'                    {{ type = builtin name = eq_{i} label = bq_peaking '
                     f'control = {{ "Freq" = {f:.1f} "Q" = {Q} "Gain" = {g:.1f} }} }}')
    names = ["pre"] + [f"eq_{i}" for i in range(1, 11)]
    links = [f'                    {{ output = "{a}:Out" input = "{b}:In" }}' for a, b in zip(names, names[1:])]
    target = f"\n                target.object = {_quote(output)}" if output else ""
    return f"""{MARK} Changes here are replaced the next time it applies the equalizer.
# Your settings live in ~/.config/grimoire/audiol.json; turn the EQ off from AudioL to remove this file.
context.modules = [
    {{ name = libpipewire-module-filter-chain
        flags = [ nofail ]
        args = {{
            node.description = "Grimoire EQ"
            media.name = "Grimoire EQ"
            filter.graph = {{
                nodes = [
{chr(10).join(nodes)}
                ]
                links = [
{chr(10).join(links)}
                ]
            }}
            audio.channels = 2
            audio.position = [ FL FR ]
            capture.props = {{
                node.name = "{pw.EQ_NODE}"
                media.class = Audio/Sink
            }}
            playback.props = {{
                node.name = "{pw.EQ_NODE}.output"
                node.passive = true
                node.dont-fallback = true{target}
            }}
        }}
    }}
]
"""


def validate(text: str, scratch: Path | None = None) -> dict:
    """Parse the drop-in with PipeWire's own SPA-JSON parser (spa-json-dump) and check the chain's shape.
    Returns the parsed config; raises ValueError when PipeWire would reject it."""
    parsed = None
    if shutil.which("spa-json-dump"):
        scratch = scratch or ASIDE
        scratch.mkdir(parents=True, exist_ok=True)
        tmp = scratch / f".check-{os.getpid()}.conf"
        tmp.write_text(text)
        try:
            r = pw._run("spa-json-dump", str(tmp), timeout=10)
        finally:
            tmp.unlink(missing_ok=True)                 # our own scratch copy, written a moment ago
        if r.returncode:
            raise ValueError((r.stderr or "spa-json-dump failed").strip())
        try:
            parsed = json.loads(r.stdout)
        except ValueError:
            parsed = None                               # a stubbed runner in tests: fall through to our checks
    if parsed is None:
        parsed = _spa_to_json(text)
    mods = parsed.get("context.modules")
    if not (isinstance(mods, list) and len(mods) == 1 and mods[0].get("name") == "libpipewire-module-filter-chain"):
        raise ValueError("expected one filter-chain module")
    graph = mods[0]["args"]["filter.graph"]
    if len(graph["nodes"]) != 11 or len(graph["links"]) != 10:
        raise ValueError("expected a preamp and ten bands")
    for n in graph["nodes"]:
        if n["type"] != "builtin" or n["label"] not in ("bq_peaking", "bq_highshelf"):
            raise ValueError(f"unexpected node {n.get('name')}")
        if not -LIMIT <= float(n["control"]["Gain"]) <= LIMIT:
            raise ValueError("gain out of range")
    return parsed


def _spa_to_json(text: str) -> dict:
    """A small SPA-JSON reader (bare words, '=' or ':' separators, optional commas, # comments) for when
    spa-json-dump isn't installed. Enough for the files AudioL writes."""
    tokens, i = [], 0
    while i < len(text):
        c = text[i]
        if c.isspace() or c in ",:=":
            i += 1
        elif c == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
        elif c in "{}[]":
            tokens.append(c)
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < len(text) and text[j] != '"':
                if text[j] == "\\" and j + 1 < len(text):
                    j += 1
                buf.append(text[j])
                j += 1
            if j >= len(text):
                raise ValueError("unterminated string")
            tokens.append(("s", "".join(buf)))
            i = j + 1
        else:
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in '{}[]",:=#':
                j += 1
            tokens.append(("w", text[i:j]))
            i = j
    pos = 0

    def value():
        nonlocal pos
        if pos >= len(tokens):
            raise ValueError("unexpected end")
        t = tokens[pos]
        pos += 1
        if t == "{":
            return obj("}")
        if t == "[":
            out = []
            while pos < len(tokens) and tokens[pos] != "]":
                out.append(value())
            if pos >= len(tokens):
                raise ValueError("Mismatched bracket")
            pos += 1
            return out
        if t in ("}", "]"):
            raise ValueError("Mismatched bracket")
        kind, s = t
        if kind == "s":
            return s
        if s in ("true", "false"):
            return s == "true"
        if s == "null":
            return None
        try:
            return float(s) if any(ch in s for ch in ".eE") else int(s)
        except ValueError:
            return s

    def obj(end):
        nonlocal pos
        out = {}
        while pos < len(tokens) and tokens[pos] != end:
            key = tokens[pos]
            if not isinstance(key, tuple):
                raise ValueError("expected a key")
            pos += 1
            out[key[1]] = value()
        if end and pos >= len(tokens):
            raise ValueError("Mismatched bracket")
        pos += 1
        return out
    top = obj(None)
    return top


# ---------------------------------------------------------------- where it goes
def uses_filter_chain() -> bool:
    """PipeWire's separate filter-chain daemon is installed (Ubuntu ships it with pipewire-bin)."""
    r = pw._run("systemctl", "--user", "show", "-p", "LoadState", "--value", UNIT)
    return r.returncode == 0 and r.stdout.strip() == "loaded"


def drop_in(filter_chain: bool | None = None) -> Path:
    fc = uses_filter_chain() if filter_chain is None else filter_chain
    return PIPEWIRE_DIR / ("filter-chain.conf.d" if fc else "pipewire.conf.d") / FILE


def installed(path: Path | None = None) -> bool:
    path = path or drop_in()
    try:
        return path.read_text(errors="replace").startswith(MARK)
    except OSError:
        return False


def installed_output(path: Path | None = None) -> str | None:
    """The device the drop-in in place plays into ("" for the default), or None when there's none."""
    path = path or drop_in()
    if not installed(path):
        return None
    try:
        mod = _spa_to_json(path.read_text())["context.modules"][0]
        return str(mod["args"]["playback.props"].get("target.object", ""))
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        return ""


def write(s: dict, path: Path | None = None) -> Path:
    """Write (or rewrite) the drop-in for the saved curve; checked by PipeWire's parser before it lands."""
    path = path or drop_in()
    text = render(s["gains"], s["preamp"], s["output"])
    validate(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    if (path.exists() or path.is_symlink()) and not installed(path):
        ASIDE.mkdir(parents=True, exist_ok=True)        # someone else's file of that name: keep it, out of the way
        shutil.move(str(path), free_name(ASIDE / f"{FILE}.yours"))
    tmp = path.with_name(f".{FILE}.{os.getpid()}.tmp")
    tmp.write_text(text)
    tmp.replace(path)
    return path


def put_aside(path: Path | None = None) -> bool:
    """Take the drop-in out of PipeWire's way (into AudioL's folder). True when there was one."""
    path = path or drop_in()
    if not installed(path):
        return False
    ASIDE.mkdir(parents=True, exist_ok=True)
    os.replace(path, ASIDE / f"{FILE}.off")              # our own regenerated file, replacing the last copy of it
    return True


def restart(filter_chain: bool | None = None) -> str:
    """The explicit Apply step: restart filter-chain.service (or pipewire.service without it)."""
    fc = uses_filter_chain() if filter_chain is None else filter_chain
    unit = UNIT if fc else "pipewire.service"
    pw._check(pw._run("systemctl", "--user", "restart", unit, timeout=30), f"restart {unit}")
    return unit


def unit_enabled() -> bool:
    r = pw._run("systemctl", "--user", "is-enabled", UNIT)
    return r.stdout.strip() in ("enabled", "enabled-runtime", "static", "indirect", "alias")


def set_unit_enabled(on: bool) -> str:
    return pw._check(pw._run("systemctl", "--user", "enable" if on else "disable", UNIT, timeout=30), "enable")


def live_params(gains: list[float], preamp: float) -> dict[str, float]:
    return {"pre:Gain": _clamp(preamp), **{f"eq_{i}:Gain": _clamp(g) for i, g in enumerate(gains, 1)}}
