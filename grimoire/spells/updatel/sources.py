# SPDX-License-Identifier: GPL-3.0-or-later
"""What can be updated, read as you (no root, no Qt): APT, Flatpak (yours and the system's), Snap and firmware.

Every outside command goes through RUN, the stub point for tests. Each source is read on its own, so a missing or
broken tool only leaves its own list empty with a note. Items are plain dicts:

    {"key": "apt:curl", "source": "apt", "name": "curl", "title": "curl", "current": "8.18.0-1", "new": "8.18.0-2",
     "size": 412345 | None, "security": bool, "scope": "system"|"user", "ref": …, "device": …, "notes": …}

Names and ids that later reach the root helper are checked here too (VALID), and again by the helper itself.
"""
import gzip
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from grimoire import i18n
from grimoire.i18n import tr, tr_noop

REBOOT = Path("/var/run/reboot-required")
# what may reach the root helper; the helper has the same patterns
VALID = {
    "apt": re.compile(r"[a-z0-9]([a-z0-9+.-]{0,98}[a-z0-9+.])?(:[a-z0-9]([a-z0-9-]{0,18}[a-z0-9])?)?"),  # no "x-"
    "flatpak": re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,254}(/[A-Za-z0-9_]{0,20}(/[A-Za-z0-9_.-]{0,100})?)?"),
    "snap": re.compile(r"[a-z0-9][a-z0-9-]{0,39}"),
    "fwupd": re.compile(r"[0-9a-f]{40}"),
}
# never removed by an upgrade, whatever apt wants (CLAUDE.md: the desktop and its fonts stay)
PROTECTED = re.compile(r"kubuntu-desktop|fonts-ibm-plex.*")
SOURCES = ("apt", "flatpak", "snap", "fwupd")
NAMES = {"apt": "APT", "flatpak": "Flatpak", "snap": "Snap",
         "fwupd": tr_noop("grimoire.spells.updatel.sources", "Firmware")}


def name(src: str) -> str:
    """A source's name as shown (APT, Flatpak and Snap are names; "Firmware" is translated)."""
    return tr("grimoire.spells.updatel.sources", NAMES[src])


def isolate(text: str) -> str:
    """A value set into a translated sentence or a table cell (package names, versions, sizes, errors) as its own
    direction island (FSI…PDI), so a right-to-left language doesn't reorder "20261002.git3c1d" or "APT: 5"."""
    return f"\u2068{text}\u2069" if text and i18n.rtl() else text


def _run(cmd: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")      # parse untranslated output
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


RUN = _run


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def valid(source: str, name: str) -> bool:
    return bool(VALID[source].fullmatch(name or ""))


# ---------------------------------------------------------------- sizes
_UNITS = {"b": 1, "kb": 1000, "mb": 1000**2, "gb": 1000**3, "kib": 1024, "mib": 1024**2, "gib": 1024**3,
          "k": 1000, "m": 1000**2, "g": 1000**3, "bytes": 1}


def parse_size(text: str) -> int | None:
    """'129.7 MB', '75.8 kB', '12MB' -> bytes; None when it isn't a size."""
    m = re.fullmatch(r"\s*([\d.,]+)\s*([A-Za-z]*)\s*", (text or "").replace("\xa0", " "))
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = _UNITS.get(m.group(2).lower() or "b")
    return round(n * unit) if unit else None


# ---------------------------------------------------------------- APT
_APT_LINE = re.compile(r"^(\S+?)/(\S+)\s+(\S+)\s+(\S+)\s+\[upgradable from: ([^\]]+)\]")


def parse_apt_list(text: str, native: str = "") -> list[dict]:
    """`apt list --upgradable`: 'curl/resolute-security,resolute-updates 8.18 amd64 [upgradable from: 8.17]'.
    A foreign-architecture copy (libc6 i386 next to libc6 amd64, e.g. for Steam) is listed as "libc6:i386", so it
    has its own row and key and `apt-get install --only-upgrade` upgrades that copy."""
    out = []
    for line in text.splitlines():
        m = _APT_LINE.match(line.strip())
        if not m:
            continue
        name, suites, new, arch, old = m.groups()
        if native and arch not in (native, "all") and ":" not in name:
            name = f"{name}:{arch}"
        if not valid("apt", name):
            continue
        out.append({"key": f"apt:{name}", "source": "apt", "name": name, "title": name, "current": old,
                    "new": new, "size": None, "security": "-security" in suites, "scope": "system",
                    "notes": suites if suites != "unknown" else ""})
    return out


def _apt_sizes(names: list[str]) -> dict[str, int]:
    """Download sizes from python-apt when it's installed; {} otherwise (sizes stay unknown)."""
    try:
        import apt
        cache = apt.Cache()
    except Exception:
        return {}
    out = {}
    for n in names:
        try:
            cand = cache[n].candidate
            if cand is not None:
                out[n] = int(cand.size)
        except (KeyError, AttributeError, ValueError):
            continue
    return out


APT_SIZES = _apt_sizes


def native_arch() -> str:
    """dpkg's own architecture (amd64), "" when it can't be read."""
    try:
        r = RUN(["dpkg", "--print-architecture"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    arch = (r.stdout or "").strip()
    return arch if r.returncode == 0 and re.fullmatch(r"[a-z0-9-]{1,20}", arch) else ""


def apt_updates() -> list[dict]:
    r = RUN(["apt", "list", "--upgradable"])
    items = parse_apt_list(r.stdout, native_arch())
    sizes = APT_SIZES([i["name"] for i in items]) if items else {}
    for i in items:
        i["size"] = sizes.get(i["name"])
    return items


def held() -> list[str]:
    """Packages kept back on purpose (apt-mark hold)."""
    if not have("apt-mark"):
        return []
    r = RUN(["apt-mark", "showhold"], timeout=30)
    return [n for n in r.stdout.split() if valid("apt", n)]


_ENTRY = re.compile(r"^([a-z0-9][a-z0-9+.-]*) \(([^)]+)\) [^;]*;.*$")


def newer_entries(changelog: str, installed: str) -> str:
    """The changelog's entries above the installed version: what the update brings."""
    out, seen = [], False
    for line in changelog.splitlines():
        m = _ENTRY.match(line)
        if m:
            if m.group(2) == installed:
                break
            seen = True
        if seen:
            out.append(line)
    return "\n".join(out).strip()


def apt_changelog(item: dict) -> str:
    """The entries between the installed and the new version, fetched with `apt-get changelog`; else the installed
    copy's latest entry with a note (third-party repositories often publish no changelog)."""
    name = item["name"]
    try:
        r = RUN(["apt-get", "changelog", "--", name], timeout=60)
        text = newer_entries(r.stdout, item["current"]) if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        text = ""
    if text:
        return text
    local = Path("/usr/share/doc") / name.split(":")[0] / "changelog.Debian.gz"
    try:
        with gzip.open(local, "rt", errors="replace") as f:
            head = f.read(200_000)
    except OSError:
        return tr("grimoire.spells.updatel.sources", "No changelog is published for {name} {new}.").format(
            name=name, new=item["new"])
    first = []
    for line in head.splitlines():
        if first and _ENTRY.match(line):
            break
        first.append(line)
    return (tr("grimoire.spells.updatel.sources", "The changelog for {new} couldn't be fetched. The installed "
               "version's latest entry:\n\n{entry}")
            .format(new=item["new"], entry="\n".join(first).strip()))


# ---------------------------------------------------------------- simulation (apt-get -s, as you)
_INST = re.compile(r"^Inst (\S+)(?: \[([^\]]+)\])? \((\S+)")
_REMV = re.compile(r"^Remv (\S+)(?: \[([^\]]+)\])?")


def parse_simulation(text: str) -> dict:
    """apt-get -s output -> {"upgrade": [(name, old, new)], "install": [(name, new)], "remove": [name],
    "kept": [name], "protected": [name]}."""
    up, new, rm, kept = [], [], [], []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if m := _INST.match(line):
            (up.append((m.group(1), m.group(2), m.group(3))) if m.group(2) else new.append((m.group(1), m.group(3))))
        elif m := _REMV.match(line):
            rm.append(m.group(1))
        elif line.startswith("The following packages have been kept back"):
            for more in lines[i + 1:]:
                if not more.startswith("  "):
                    break
                kept += more.split()
    return {"upgrade": up, "install": new, "remove": rm, "kept": kept,
            "protected": [n for n in rm if PROTECTED.fullmatch(n.split(":")[0])]}


def apt_command(names: list[str] | None) -> list[str]:
    """The upgrade the helper runs (minus -s): everything, or just the picked packages."""
    if names is None:
        return ["apt-get", "-y", "--with-new-pkgs", "upgrade"]
    return ["apt-get", "-y", "--only-upgrade", "install", "--", *names]


def simulate(names: list[str] | None) -> dict:
    """What an upgrade would do, without root: apt-get -s. Raises RuntimeError with apt's message on failure."""
    bad = [n for n in names or [] if not valid("apt", n)]
    if bad:
        raise RuntimeError(tr("grimoire.spells.updatel.sources", "Not a package name: {name}").format(name=bad[0]))
    cmd = apt_command(names)
    r = RUN([cmd[0], "-s", *cmd[1:]], timeout=180)
    if r.returncode:
        msg = [ln for ln in (r.stderr or r.stdout).splitlines() if ln.startswith("E:")] or [r.stderr.strip()]
        raise RuntimeError(msg[-1] or tr("grimoire.spells.updatel.sources", "APT couldn't simulate the upgrade."))
    return parse_simulation(r.stdout)


# ---------------------------------------------------------------- Flatpak
FLATPAK_COLS = "application,arch,branch,version,origin,download-size,commit"


def parse_flatpak(text: str, scope: str, installed: dict[tuple, tuple[str, str]]) -> list[dict]:
    """remote-ls --updates rows; a rebuild of the same version shows the commits, so it doesn't read "1.0 → 1.0"."""
    out = []
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) < 7 or not f[0]:
            continue
        app, arch, branch, version, origin, size, commit = f[:7]
        ref = f"{app}/{arch}/{branch}"
        if not valid("flatpak", ref):
            continue
        cur_ver, cur_commit = installed.get((app, arch, branch, scope), ("", ""))
        cur, new = cur_ver or cur_commit[:8], version or commit[:8]
        if version and version == cur_ver:
            cur, new = f"{cur_ver} · {cur_commit[:8]}", f"{version} · {commit[:8]}"
        title = app if branch in ("stable", "") else f"{app} ({branch})"
        out.append({"key": f"flatpak:{scope}:{ref}", "source": "flatpak", "name": app, "title": title,
                    "current": cur, "new": new, "size": parse_size(size), "security": False,
                    "scope": scope, "ref": ref, "origin": origin, "notes": scope})
    return out


def _flatpak_installed() -> dict[tuple, tuple[str, str]]:
    """(app, arch, branch, installation) -> (version, active commit)."""
    r = RUN(["flatpak", "list", "--columns=application,arch,branch,installation,version,active"], timeout=60)
    out = {}
    for line in r.stdout.splitlines():
        f = line.split("\t")
        if len(f) >= 6:
            out[(f[0], f[1], f[2], f[3])] = (f[4], f[5])
    return out


def flatpak_updates() -> list[dict]:
    installed = _flatpak_installed()
    out = []
    for scope in ("user", "system"):
        r = RUN(["flatpak", "remote-ls", f"--{scope}", "--updates", f"--columns={FLATPAK_COLS}"], timeout=180)
        out += parse_flatpak(r.stdout, scope, installed)
    return out


def flatpak_changelog(item: dict) -> str:
    r = RUN(["flatpak", "remote-info", f"--{item['scope']}", "--", item.get("origin") or "flathub", item["ref"]],
            timeout=60)
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    keep = [ln for ln in lines if ln.split(":")[0] in ("Version", "Subject", "Date", "Commit", "Download")]
    if keep and ":" not in lines[0]:                      # the app's name and summary line
        keep.insert(0, lines[0] + "\n")
    return "\n".join(keep) or tr("grimoire.spells.updatel.sources", "Flatpak has no release notes for {name}.").format(
        name=item["name"])


# ---------------------------------------------------------------- Snap
def _columns(text: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    head = lines[0].split()
    return [dict(zip(head, ln.split())) for ln in lines[1:]]


def parse_snap(refresh: str, listing: str) -> list[dict]:
    cur = {r.get("Name"): r.get("Version", "") for r in _columns(listing)}
    out = []
    for r in _columns(refresh):
        name = r.get("Name", "")
        if not valid("snap", name):
            continue
        out.append({"key": f"snap:{name}", "source": "snap", "name": name, "title": name,
                    "current": cur.get(name, ""), "new": r.get("Version", ""), "size": parse_size(r.get("Size", "")),
                    "security": False, "scope": "system", "notes": r.get("Publisher", "").rstrip("✓*")})
    return out


def snap_updates() -> list[dict]:
    r = RUN(["snap", "refresh", "--list"], timeout=120)
    if r.returncode or "All snaps up to date" in r.stdout + r.stderr:
        return []
    return parse_snap(r.stdout, RUN(["snap", "list"], timeout=60).stdout)


# ---------------------------------------------------------------- firmware
def strip_markup(text: str) -> str:
    """fwupd's release descriptions are small XML-ish snippets (<p>, <ul><li>)."""
    text = re.sub(r"<li>\s*", "• ", text or "")
    text = re.sub(r"</(p|li|ul|ol)>|<br\s*/?>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(ln.strip() for ln in text.splitlines())).strip()


def parse_fwupd(text: str) -> list[dict]:
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return []
    out = []
    for d in data.get("Devices", []) if isinstance(data, dict) else []:
        if not isinstance(d, dict) or not isinstance(d.get("Releases") or [], list):
            continue
        rel = (d.get("Releases") or [None])[0]
        dev = str(d.get("DeviceId", ""))
        if not isinstance(rel, dict) or not valid("fwupd", dev):
            continue
        out.append({"key": f"fwupd:{dev}", "source": "fwupd", "name": str(d.get("Name") or dev[:8]),
                    "title": str(d.get("Name") or dev[:8]), "current": str(d.get("Version", "")),
                    "new": str(rel.get("Version", "")), "size": rel.get("Size") if isinstance(rel.get("Size"), int)
                    else None, "security": False, "scope": "system", "device": dev,
                    "notes": str(d.get("Vendor", "")),
                    "description": strip_markup(str(rel.get("Description") or rel.get("Summary") or ""))})
    return out


def fwupd_updates() -> list[dict]:
    r = RUN(["fwupdmgr", "get-updates", "--json", "--no-unreported-check", "--no-metadata-check"], timeout=120)
    return parse_fwupd(r.stdout)


# ---------------------------------------------------------------- everything
TOOLS = {"apt": "apt", "flatpak": "flatpak", "snap": "snap", "fwupd": "fwupdmgr"}
READERS = {"apt": apt_updates, "flatpak": flatpak_updates, "snap": snap_updates, "fwupd": fwupd_updates}


def check() -> dict:
    """One pass over every source: {"items": [...], "held": [...], "missing": [source], "errors": {source: msg},
    "reboot": [packages]}. Never raises."""
    items, missing, errors = [], [], {}
    for src in SOURCES:
        if not have(TOOLS[src]):
            missing.append(src)
            continue
        try:
            items += READERS[src]()
        except Exception as e:                  # odd output from one tool only empties its own list
            errors[src] = str(e) or type(e).__name__
    try:
        hold = held()
    except (OSError, subprocess.SubprocessError):
        hold = []
    return {"items": items, "held": hold, "missing": missing, "errors": errors, "reboot": reboot_required()}


def reboot_required() -> list[str] | None:
    """None when no restart is pending, else the packages that asked for it (maybe none listed)."""
    if not REBOOT.exists():
        return None
    try:
        return REBOOT.with_name(REBOOT.name + ".pkgs").read_text().split()
    except OSError:
        return []


def changelog(item: dict) -> str:
    """What's new in this update, as plain text (may go online: apt-get changelog, flatpak remote-info)."""
    try:
        if item["source"] == "apt":
            return apt_changelog(item)
        if item["source"] == "flatpak":
            return flatpak_changelog(item)
        if item["source"] == "fwupd":
            return item.get("description") or tr("grimoire.spells.updatel.sources",
                                                 "The vendor gave no release notes.")
        if item["source"] == "snap":
            return tr("grimoire.spells.updatel.sources", "Snap doesn't publish changelogs. Publisher: {who}").format(
                who=item.get("notes") or tr("grimoire.spells.updatel.sources", "unknown", "publisher"))
    except (OSError, subprocess.SubprocessError) as e:
        return tr("grimoire.spells.updatel.sources", "Couldn't read the changelog: {err}").format(err=e)
    return ""
