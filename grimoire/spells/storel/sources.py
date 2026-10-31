# SPDX-License-Identifier: GPL-3.0-or-later
"""What's installed and what an install or removal would do, read as you (no root, no Qt).

Every outside command goes through RUN, the stub point for tests (as in UpdateL). APT plans come from `apt-get -s`
(parsed by UpdateL's parse_simulation); removing anything Essential, of Priority required/important or on the
PROTECTED list is refused here and again by the root helper, which keeps its own copy of the list (it may not read
files next to itself). Names that reach the helper are checked against UpdateL's VALID patterns here and there.
"""
import configparser
import os
import re
import shutil
import subprocess
from pathlib import Path

from grimoire import i18n
from grimoire.i18n import tr
from grimoire.spells.updatel.sources import VALID, parse_simulation

# never removed, by StoreL or as a side effect of an install or removal: the desktop and its fonts (CLAUDE.md), the
# packages that boot and run the system and Grimoire's own Qt. The helper has the same list.
PROTECTED = re.compile(
    r"kubuntu-.*|fonts-ibm-plex.*|plasma-desktop|plasma-workspace.*|kwin-.*|sddm.*|systemd.*|libsystemd.*|udev"
    r"|apt|apt-utils|dpkg|sudo|sudo-rs|polkitd|pkexec|policykit-1|network-manager|linux-.*|grub-.*|grub2-.*|shim-.*"
    r"|ubuntu-minimal|ubuntu-standard|init|base-files|bash|coreutils|login|dbus.*|python3|python3-minimal"
    r"|python3-pyside6.*|pipewire.*|wireplumber|xdg-desktop-portal.*|flatpak|snapd|plymouth.*|grimoire-linux")
PROTECTED_SNAPS = re.compile(r"snapd|core[0-9]*|bare|gtk-common-themes|gnome-[0-9-]+.*|kf[0-9]+-.*|mesa-.*")
# what reaches the helper: full app refs (no runtimes on their own), remote names, snap names
REF = re.compile(r"app/[A-Za-z][A-Za-z0-9_.-]{0,254}/[A-Za-z0-9_]{1,20}/[A-Za-z0-9_.-]{1,100}")
REMOTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
SNAP = VALID["snap"]
APT = VALID["apt"]
APPS_DIR = Path("/usr/share/applications")


def _run(cmd: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")      # parse untranslated output
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)


RUN = _run


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def protected(pkg: str) -> bool:
    return bool(PROTECTED.fullmatch(pkg.split(":")[0]))


# ---------------------------------------------------------------- sizes
_UNITS = {"b": 1, "kb": 1000, "mb": 1000**2, "gb": 1000**3, "kib": 1024, "mib": 1024**2, "gib": 1024**3,
          "k": 1000, "m": 1000**2, "g": 1000**3, "bytes": 1}


def parse_size(text: str) -> int | None:
    """'101.5 MB', '268,4 kB', '12MB' -> bytes; None when it isn't a size."""
    m = re.fullmatch(r"\s*([\d.,]+)\s*([A-Za-z]*)\s*", (text or "").replace("\xa0", " "))
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    unit = _UNITS.get(m.group(2).lower() or "b")
    return round(n * unit) if unit else None


# ---------------------------------------------------------------- what's installed
def flatpak_remotes() -> dict[str, list[str]]:
    """remote → the installations it's configured in ("user", "system")."""
    if not have("flatpak"):
        return {}
    r = RUN(["flatpak", "remotes", "--columns=name,options"], timeout=30)
    out: dict[str, list[str]] = {}
    for line in r.stdout.splitlines():
        f = line.split("\t")
        if len(f) >= 2 and REMOTE.fullmatch(f[0]) and "disabled" not in f[1]:
            for scope in ("user", "system"):
                if scope in f[1].split(","):
                    out.setdefault(f[0], []).append(scope)
    return out


def flatpak_installed() -> list[dict]:
    """Installed Flatpak apps: {"id", "ref" (app/…), "scope", "version", "origin", "name", "size"}."""
    if not have("flatpak"):
        return []
    r = RUN(["flatpak", "list", "--app", "--columns=application,arch,branch,installation,version,origin,name,size"],
            timeout=60)
    out = []
    for line in r.stdout.splitlines():
        f = line.split("\t")
        if len(f) < 8:
            continue
        app, arch, branch, scope, version, origin, name, size = f[:8]
        ref = f"app/{app}/{arch}/{branch}"
        if REF.fullmatch(ref) and scope in ("user", "system"):
            out.append({"id": app, "ref": ref, "scope": scope, "version": version, "origin": origin,
                        "name": name or app, "size": parse_size(size)})
    return out


DPKG_FIELDS = "${binary:Package}\\t${db:Status-Abbrev}\\t${Version}\\t${Installed-Size}\\t${Essential}\\t${Priority}\\n"


def parse_dpkg(text: str) -> dict[str, dict]:
    """dpkg-query -W rows → {package: {"version", "size" (bytes), "essential", "priority"}} for installed ones."""
    out = {}
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) < 6 or not f[1].startswith("ii"):
            continue
        name = f[0]
        try:
            size = int(f[3]) * 1024 if f[3] else None
        except ValueError:
            size = None
        out[name] = {"version": f[2], "size": size, "essential": f[4] == "yes", "priority": f[5]}
        out.setdefault(name.split(":")[0], out[name])            # libfoo:amd64 also answers to libfoo
    return out


def apt_installed() -> dict[str, dict]:
    if not have("dpkg-query"):
        return {}
    return parse_dpkg(RUN(["dpkg-query", "-W", f"-f={DPKG_FIELDS}"], timeout=60).stdout)


def removable(pkg: str, info: dict | None) -> str:
    """'' when StoreL may offer to remove this package, else why not (shown as the button's tooltip)."""
    if protected(pkg):
        return tr("grimoire.spells.storel.sources", "Part of the desktop or the system: StoreL never removes it.")
    if info and info.get("essential"):
        return tr("grimoire.spells.storel.sources", "An essential package: the system needs it.")
    if info and info.get("priority") in ("required", "important"):
        return tr("grimoire.spells.storel.sources", "A required system package: StoreL never removes it.")
    return ""


def desktop_apps() -> list[dict]:
    """Installed system apps from their .desktop files (also those without AppStream metadata), with the package
    that owns each: {"key", "id", "name", "summary", "icon", "cats", "pkg", "desktop"}."""
    try:
        files = sorted(p for p in APPS_DIR.glob("*.desktop") if p.is_file())
    except OSError:
        return []
    shown = []
    for p in files:
        cp = configparser.RawConfigParser(strict=False, interpolation=None)
        cp.optionxform = str
        try:
            cp.read(p, encoding="utf-8")
            e = cp["Desktop Entry"]
        except (configparser.Error, KeyError, UnicodeDecodeError, OSError):
            continue
        if e.get("Type") != "Application" or e.get("NoDisplay", "").lower() == "true" or \
                e.get("Hidden", "").lower() == "true" or e.get("OnlyShowIn"):
            continue
        shown.append((p, e))
    if not shown or not have("dpkg-query"):
        return []
    owners = {}
    r = RUN(["dpkg-query", "-S", "--", *[str(p) for p, _e in shown]], timeout=60)
    for line in r.stdout.splitlines():
        pkgs, _sep, path = line.partition(": ")
        if path:
            owners[path.strip()] = pkgs.split(",")[0].strip()
    out = []
    for p, e in shown:
        pkg = owners.get(str(p))
        if not pkg or not APT.fullmatch(pkg):
            continue
        lang = i18n.current()
        names = [f"Name[{lang}]", f"Name[{lang.split('_')[0]}]", "Name"]
        comments = [f"Comment[{lang}]", f"Comment[{lang.split('_')[0]}]", "Comment",
                    f"GenericName[{lang}]", "GenericName"]
        out.append({"key": p.stem.lower(), "id": p.stem, "name": next((e[k] for k in names if e.get(k)), p.stem),
                    "summary": next((e[k] for k in comments if e.get(k)), ""), "icon": e.get("Icon", ""),
                    "cats": [c for c in e.get("Categories", "").split(";") if c], "pkg": pkg, "desktop": str(p)})
    return out


def snap_installed() -> list[dict]:
    """Installed snaps that are apps (not bases, snapd or the core runtimes)."""
    if not have("snap"):
        return []
    r = RUN(["snap", "list"], timeout=60)
    return [s for s in parse_snap_list(r.stdout) if not PROTECTED_SNAPS.fullmatch(s["name"])]


def _columns(text: str) -> list[list[str]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return [ln.split() for ln in lines[1:]] if lines else []


def parse_snap_list(text: str) -> list[dict]:
    out = []
    for f in _columns(text):
        if len(f) >= 5 and SNAP.fullmatch(f[0]) and not any(n in f[5:6] for n in ("base", "core", "snapd")):
            out.append({"name": f[0], "version": f[1], "publisher": f[4].rstrip("✓*"),
                        "classic": "classic" in " ".join(f[5:])})
    return out


def installed() -> dict:
    """Everything installed, in one pass: {"flatpak": [...], "apt": {pkg: info}, "snap": [...],
    "desktop": [...], "remotes": {remote: scopes}}. A tool that fails only empties its own part."""
    out = {"flatpak": [], "apt": {}, "snap": [], "desktop": [], "remotes": {}}
    for key, fn in (("flatpak", flatpak_installed), ("apt", apt_installed), ("snap", snap_installed),
                    ("desktop", desktop_apps), ("remotes", flatpak_remotes)):
        try:
            out[key] = fn()
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return out


# ---------------------------------------------------------------- details (may go online)
def apt_details(pkgs: list[str]) -> dict[str, dict]:
    """The candidate's version, download and installed size from apt-cache (no network)."""
    pkgs = [p for p in pkgs if APT.fullmatch(p)]
    if not pkgs or not have("apt-cache"):
        return {}
    r = RUN(["apt-cache", "show", "--no-all-versions", "--", *pkgs], timeout=60)
    out, cur = {}, {}
    for line in r.stdout.splitlines() + [""]:
        if not line.strip():
            if cur.get("Package"):
                out.setdefault(cur["Package"], {"version": cur.get("Version", ""),
                                                "download": _int(cur.get("Size")),
                                                "installed": _int(cur.get("Installed-Size"), 1024),
                                                "priority": cur.get("Priority", ""),
                                                "section": cur.get("Section", "")})
            cur = {}
            continue
        k, sep, v = line.partition(": ")
        if sep and not line.startswith(" "):
            cur[k] = v.strip()
    return out


def _int(text, unit: int = 1) -> int | None:
    try:
        return int(text) * unit
    except (TypeError, ValueError):
        return None


def flatpak_details(offer: dict, scope: str) -> dict:
    """`flatpak remote-info`: version, download and installed size, runtime (asks the remote: online)."""
    if not have("flatpak") or not REF.fullmatch(offer.get("ref", "")) or not REMOTE.fullmatch(offer.get("remote", "")):
        return {}
    r = RUN(["flatpak", "remote-info", f"--{scope}", "--", offer["remote"], offer["ref"]], timeout=60)
    info = {}
    for line in r.stdout.splitlines():
        k, sep, v = line.strip().partition(":")
        if sep:
            info[k.strip()] = v.strip()
    return {"version": info.get("Version", ""), "download": parse_size(info.get("Download", "")),
            "installed": parse_size(info.get("Installed", "")), "runtime": info.get("Runtime", ""),
            "license": info.get("License", "")} if r.returncode == 0 else {}


def runtime_installed(runtime: str) -> bool:
    """Is the runtime an app needs (org.kde.Platform/x86_64/6.9) already on this machine, in either installation?"""
    if not runtime or not have("flatpak"):
        return False
    r = RUN(["flatpak", "list", "--runtime", "--columns=ref"], timeout=60)
    return runtime in {ln.strip() for ln in r.stdout.splitlines()}


def snap_search(query: str) -> list[dict]:
    """`snap find` (online): {"name", "version", "publisher", "summary"} rows."""
    if not have("snap") or not query.strip():
        return []
    r = RUN(["snap", "find", "--", query.strip()[:80]], timeout=60)
    out = []
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if not lines or not lines[0].startswith("Name"):
        return []
    head = lines[0]
    cut = head.index("Summary") if "Summary" in head else None
    for ln in lines[1:]:
        f = ln.split()
        if len(f) >= 3 and SNAP.fullmatch(f[0]):
            out.append({"name": f[0], "version": f[1], "publisher": f[2].rstrip("✓*"),
                        "summary": ln[cut:].strip() if cut is not None and len(ln) > cut else ""})
    return out


def snap_details(name: str) -> dict:
    """`snap info` (online): summary, description, license, publisher, confinement."""
    if not have("snap") or not SNAP.fullmatch(name):
        return {}
    r = RUN(["snap", "info", "--", name], timeout=60)
    info, desc, in_desc = {}, [], False
    for line in r.stdout.splitlines():
        if in_desc:
            if line.startswith("  "):
                desc.append(line.strip())
                continue
            in_desc = False
        k, sep, v = line.partition(":")
        if sep and not line.startswith(" "):
            info[k.strip()] = v.strip()
            in_desc = k.strip() == "description" and v.strip() in ("|", "")
    channels = r.stdout.split("channels:")[-1] if "channels:" in r.stdout else ""
    return {"summary": info.get("summary", ""), "desc": "\n".join(desc), "license": info.get("license", ""),
            "publisher": info.get("publisher", "").rstrip("✓*"), "classic": "classic" in channels,
            "home": info.get("contact", "")}


def flatpak_search(query: str) -> list[dict]:
    """`flatpak search` for when no remote has downloaded its AppStream data yet (else the catalog is better)."""
    if not have("flatpak") or not query.strip():
        return []
    r = RUN(["flatpak", "search", "--columns=application,name,description,version,branch,remotes", "--",
             query.strip()[:80]], timeout=60)
    out = []
    for line in r.stdout.splitlines():
        f = line.split("\t")
        if len(f) >= 6 and f[0] and REMOTE.fullmatch(f[5].split(",")[0]):
            out.append({"id": f[0], "name": f[1], "summary": f[2], "version": f[3], "branch": f[4],
                        "remote": f[5].split(",")[0]})
    return out


# ---------------------------------------------------------------- APT plans (apt-get -s, as you)
def apt_command(action: str, pkgs: list[str]) -> list[str]:
    """What the helper runs (minus -s): install with apt's usual recommends, or remove (never purge or autoremove)."""
    return ["apt-get", "-y", "install" if action == "install" else "remove", "--", *pkgs]


def simulate(action: str, pkgs: list[str]) -> dict:
    """What installing or removing these packages would do: parse_simulation's dict plus "blocked" (packages that
    may never go, with why), "download" and "disk" (bytes, from apt-cache/dpkg; None when unknown).
    Raises RuntimeError with apt's message when apt can't plan it."""
    bad = [p for p in pkgs if not APT.fullmatch(p)]
    if bad or not pkgs:
        raise RuntimeError(tr("grimoire.spells.storel.sources", "Not a package name: {name}").format(
            name=bad[0] if bad else "–"))
    cmd = apt_command(action, pkgs)
    r = RUN([cmd[0], "-s", *cmd[1:]], timeout=180)
    if r.returncode:
        msg = [ln for ln in (r.stderr or r.stdout).splitlines() if ln.startswith("E:")] or [r.stderr.strip()]
        raise RuntimeError(msg[-1] or tr("grimoire.spells.storel.sources", "APT couldn't plan this."))
    sim = parse_simulation(r.stdout)
    # apt set to purge (APT::Get::Purge) says "Purg" instead of "Remv": still a removal, as the helper counts it
    sim["remove"] += [m.group(1) for m in re.finditer(r"^Purg (\S+)", r.stdout, re.M)
                      if m.group(1) not in sim["remove"]]
    have_now = apt_installed()
    sim["blocked"] = [(n, removable(n.split(":")[0], have_now.get(n) or have_now.get(n.split(":")[0])))
                      for n in sim["remove"]]
    sim["blocked"] = [(n, why) for n, why in sim["blocked"] if why]
    new = [n for n, _v in sim["install"]] + [n for n, _o, _v in sim["upgrade"]]
    det = apt_details([n.split(":")[0] for n in new]) if new else {}
    dl = [det.get(n.split(":")[0], {}).get("download") for n in new]
    grow = [det.get(n.split(":")[0], {}).get("installed") for n, _v in sim["install"]]
    shrink = [(have_now.get(n) or {}).get("size") for n in sim["remove"]]
    sim["download"] = sum(x for x in dl if x) if all(x is not None for x in dl) else None
    sim["disk"] = (sum(x or 0 for x in grow) - sum(x or 0 for x in shrink)) if new or sim["remove"] else 0
    return sim
