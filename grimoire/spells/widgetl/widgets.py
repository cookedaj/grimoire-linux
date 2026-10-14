# SPDX-License-Identifier: GPL-3.0-or-later
"""WidgetL and Plasma: install the four desktop widgets (plasma/com.cookedaj.grimoire.widget.*), find them on the
desktops and panels, add one to the desktop and take them all off again before an uninstall.

Everything that touches the desktop is a plasmashell desktop script (evaluateScript). The script text is built by
add_script()/remove_script() so it can be read and tested without running it; `plasma_script` is the one call that
reaches plasmashell (tests swap it). No Qt here: uninstall.sh runs `python3 -m grimoire.spells.widgetl uninstall`.
"""
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from grimoire.paths import DATA, ROOT

PREFIX = "com.cookedaj.grimoire.widget."


@dataclass(frozen=True)
class Widget:
    id: str             # clock, system, weather, nowplaying
    name: str
    blurb: str
    size: tuple         # (width, height) it gets when added to the desktop

    @property
    def plugin(self) -> str:
        return PREFIX + self.id


WIDGETS = [
    Widget("clock", "Clock", "Big thin digits and the date. Seconds and the 24-hour clock are options.", (360, 170)),
    Widget("system", "System", "CPU, memory, graphics card and temperatures, as thin bars or sparklines.", (300, 206)),
    Widget("weather", "Weather", "Now and the next five days from Open-Meteo, for a place you pick. No account "
           "needed.", (340, 220)),
    Widget("nowplaying", "Now Playing", "What's playing in any app, with the cover in grayscale and play, pause, "
           "next and previous.", (380, 144)),
]
BY_ID = {w.id: w for w in WIDGETS}
PLUGINS = [w.plugin for w in WIDGETS]


def get(wid: str) -> Widget:
    if wid not in BY_ID:
        raise RuntimeError(f"no widget called {wid!r} (pick one of: {', '.join(BY_ID)})")
    return BY_ID[wid]


# ---- the packages -------------------------------------------------------------------------------------------------

def _share() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")


def source_dir(wid: str) -> Path:
    """The package to install: from the installed app copy when there is one (nothing may point into a download),
    else from this copy (a checkout or a distro package's /usr/share/grimoire-linux)."""
    installed = DATA / "app" / "plasma" / (PREFIX + wid)
    return installed if installed.is_dir() else ROOT / "plasma" / (PREFIX + wid)


def installed_dir(wid: str) -> Path:
    return _share() / "plasma" / "plasmoids" / (PREFIX + wid)


def is_installed(wid: str) -> bool:
    return (installed_dir(wid) / "metadata.json").is_file()


def _files(d: Path) -> dict:
    return {p.relative_to(d): p.read_bytes() for p in d.rglob("*") if p.is_file()}


def needs_update(wid: str) -> bool:
    """True when the installed package differs from the one Grimoire ships (any file)."""
    src, dst = source_dir(wid), installed_dir(wid)
    if not dst.is_dir():
        return False
    try:
        return _files(src) != _files(dst)
    except OSError:
        return True


def installed_count() -> int:
    return sum(is_installed(w.id) for w in WIDGETS)


def updates() -> list[str]:
    return [w.id for w in WIDGETS if needs_update(w.id)]


def kpackagetool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["kpackagetool6", "--type", "Plasma/Applet", *args], capture_output=True, text=True)


def install(ids: list[str] | None = None) -> list[str]:
    """Install or upgrade the widgets (all by default) with kpackagetool6. Returns the ids it installed or updated;
    RuntimeError with kpackagetool6's message on the first failure."""
    done = []
    for wid in ids or [w.id for w in WIDGETS]:
        src = source_dir(get(wid).id)
        if not (src / "metadata.json").is_file():
            raise RuntimeError(f"the {wid} widget's package is missing from {src}")
        if is_installed(wid) and not needs_update(wid):
            continue
        r = kpackagetool("-u" if is_installed(wid) else "-i", str(src))
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout).strip() or "kpackagetool6 failed")
        done.append(wid)
    return done


def uninstall_packages() -> list[str]:
    """Remove every installed widget package; returns the ids removed. Only ever our own folders under
    plasma/plasmoids, by exact name."""
    gone = []
    for w in WIDGETS:
        if not installed_dir(w.id).exists():
            continue
        r = kpackagetool("-r", w.plugin)
        if r.returncode and installed_dir(w.id).exists():
            shutil.rmtree(installed_dir(w.id))        # a copy install.sh made that kpackagetool6 doesn't know
        gone.append(w.id)
    return gone


# ---- reading the desktops (read-only) -------------------------------------------------------------------------------

def plasma_script(script: str, timeout: float = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["qdbus6", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript",
                           script], capture_output=True, text=True, timeout=timeout)


def run(script: str, timeout: float = 20) -> str:
    """Run a desktop script; returns what it printed. RuntimeError when plasmashell isn't there or the script threw."""
    try:
        r = plasma_script(script, timeout)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise RuntimeError(f"couldn't reach plasmashell: {err}")
    out = r.stdout.strip()
    if r.returncode or out.startswith("Error:"):
        raise RuntimeError((r.stderr or out).strip() or "plasmashell rejected the script")
    return out


SCAN_JS = """
var out = [];
function look(kind, cs) {
    for (var i = 0; i < cs.length; i++) {
        var ws = cs[i].widgets();
        for (var j = 0; j < ws.length; j++) {
            if (PLUGINS.indexOf(ws[j].type) >= 0) {
                out.push({kind: kind, containment: cs[i].id, screen: cs[i].screen, widget: ws[j].id,
                          type: ws[j].type});
            }
        }
    }
}
look("desktop", desktops());
look("panel", panels());
print(JSON.stringify(out));
"""


def scan(timeout: float = 20) -> list[dict]:
    """Every WidgetL widget on a desktop or in a panel: {kind, containment, screen, widget, type}."""
    return json.loads(run(f"var PLUGINS = {json.dumps(PLUGINS)};\n" + SCAN_JS, timeout) or "[]")


def counts(found: list[dict]) -> dict:
    """How many of each widget (by id) are out there."""
    c = {w.id: 0 for w in WIDGETS}
    for f in found:
        wid = f["type"].removeprefix(PREFIX)
        if wid in c:
            c[wid] += 1
    return c


def status() -> str:
    n = installed_count()
    if not n:
        return "Not installed"
    try:
        found = scan(timeout=3)          # the home page asks on the UI thread, so don't wait long
    except (RuntimeError, ValueError):
        return "Installed · Plasma isn't answering"
    on = len(found)
    line = ("No widgets on your desktop yet" if on == 0 else
            "1 widget on your desktop" if on == 1 else
            "{n} widgets on your desktop".format(n=on))
    return line + (" · update ready" if updates() else "")


# ---- adding and removing ------------------------------------------------------------------------------------------

def add_script(wid: str, screen: int = 0) -> str:
    """Desktop script: put one widget on the desktop of `screen`, in a column down its right-hand side under any
    WidgetL widgets already there. Prints the new widget's id."""
    w = get(wid)
    width, height = w.size
    return f"""
var PLUGINS = {json.dumps(PLUGINS)};
var d = desktopForScreen({int(screen)});
if (!d) {{ var all = desktops(); d = all.length ? all[0] : null; }}
if (!d) {{ throw new Error("no desktop found"); }}
var g = screenGeometry(d.screen);
var x = Math.max(0, g.width - {width} - 48), y = 48;
var ws = d.widgets();
for (var i = 0; i < ws.length; i++) {{
    if (PLUGINS.indexOf(ws[i].type) >= 0) {{
        var b = ws[i].geometry;
        y = Math.max(y, b.y + b.height + 32);
    }}
}}
if (y + {height} > g.height) {{ y = 48; x = Math.max(0, x - {width} - 24); }}
var a = d.addWidget({json.dumps(w.plugin)}, x, y, {width}, {height});
if (!a) {{ throw new Error("Plasma couldn't create the widget (is it installed?)"); }}
print(a.id);
""".strip() + "\n"


def remove_script(plugins: list[str] | None = None) -> str:
    """Desktop script: remove every instance of the given widgets (all of WidgetL's by default) from every desktop and
    panel. Prints how many it removed."""
    return f"""
var PLUGINS = {json.dumps(plugins or PLUGINS)};
var removed = 0;
var cs = desktops().concat(panels());
for (var i = 0; i < cs.length; i++) {{
    var ws = cs[i].widgets();
    for (var j = 0; j < ws.length; j++) {{
        if (PLUGINS.indexOf(ws[j].type) >= 0) {{ ws[j].remove(); removed++; }}
    }}
}}
print(removed);
""".strip() + "\n"


def add(wid: str, dry_run: bool = False) -> dict:
    """Add a widget to the desktop (installing it first if needed). dry_run returns the script and changes nothing."""
    script = add_script(wid)
    if dry_run:
        return {"widget": wid, "script": script}
    if not is_installed(wid):
        install([wid])
    out = run(script)
    last = out.splitlines()[-1] if out else ""
    return {"widget": wid, "id": int(last) if last.isdigit() else -1}


def remove_all(dry_run: bool = False) -> dict:
    """Take every WidgetL widget off the desktops and panels. dry_run lists them with the script, changes nothing."""
    found = scan()
    script = remove_script()
    if dry_run or not found:
        return {"found": found, "removed": 0, "script": script}
    out = run(script)
    last = out.splitlines()[-1] if out else ""
    return {"found": found, "removed": int(last) if last.isdigit() else len(found)}


def mentioned_in_config() -> bool:
    """Whether Plasma's saved layout still names one of the widgets (what's left to check when it isn't running)."""
    path = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "plasma-org.kde.plasma.desktop-appletsrc"
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return False
    return any(f"plugin={p}" in text for p in PLUGINS)
