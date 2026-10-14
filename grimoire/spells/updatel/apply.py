# SPDX-License-Identifier: GPL-3.0-or-later
"""Running updates (no Qt): a Plan says what to update; run() streams its output line by line.

Everything needing root (APT, system Flatpaks, snaps, firmware, refreshing the package lists) goes into ONE call of
UpdateL's root helper, steps joined by "+", so a batch asks for the password once. Your own Flatpaks update as you,
without a prompt. APT upgrades are simulated first (sources.simulate) so removals are shown before anything runs;
the helper simulates again and refuses removals that weren't confirmed.
"""
import re
import subprocess
from dataclasses import dataclass, field

from grimoire import roothelper
from grimoire.i18n import tr
from grimoire.spells.updatel import sources

SPELL = "updatel"


@dataclass
class Plan:
    apt: list[str] | None = field(default_factory=list)    # None = everything (apt-get upgrade)
    flatpak_user: list[str] | None = field(default_factory=list)
    flatpak_system: list[str] | None = field(default_factory=list)
    snap: list[str] | None = field(default_factory=list)
    fwupd: list[str] = field(default_factory=list)
    refresh: bool = False                                   # apt-get update first
    allow_removals: bool = False

    def empty(self) -> bool:
        return not (self.refresh or self.fwupd or any(x is None or x for x in
                                                      (self.apt, self.flatpak_user, self.flatpak_system, self.snap)))


def plan_for(items: list[dict], everything: set[str] = frozenset()) -> Plan:
    """A plan for these items; sources named in everything update whole (also what appeared since the check)."""
    p = Plan()
    for it in items:
        src = it["source"]
        if src == "apt":
            p.apt.append(it["name"])
        elif src == "flatpak":
            (p.flatpak_user if it["scope"] == "user" else p.flatpak_system).append(it["ref"])
        elif src == "snap":
            p.snap.append(it["name"])
        elif src == "fwupd":
            p.fwupd.append(it["device"])
    if "apt" in everything:
        p.apt = None
    if "flatpak" in everything:
        p.flatpak_user = None if p.flatpak_user else []
        p.flatpak_system = None if p.flatpak_system else []
    if "snap" in everything:
        p.snap = None
    return p


def _names(kind: str, names: list[str]) -> list[str]:
    bad = [n for n in names if not sources.valid(kind, n)]
    if bad:
        raise ValueError(tr("grimoire.spells.updatel.apply", "Not a valid name: {name}").format(name=bad[0]))
    return names


def root_args(p: Plan) -> list[str]:
    """The helper's arguments for the root part of a plan ([] when nothing needs root)."""
    steps = []
    if p.refresh:
        steps.append(["refresh"])
    if p.apt is None or p.apt:
        steps.append(["apt", *(["--allow-removals"] if p.allow_removals else []),
                      *(["--all"] if p.apt is None else _names("apt", sorted(set(p.apt))))])
    if p.flatpak_system is None or p.flatpak_system:
        steps.append(["flatpak", *(["--all"] if p.flatpak_system is None else _names("flatpak", p.flatpak_system))])
    if p.snap is None or p.snap:
        steps.append(["snap", *(["--all"] if p.snap is None else _names("snap", p.snap))])
    if p.fwupd:
        steps.append(["fwupd", *_names("fwupd", p.fwupd)])
    out = []
    for s in steps:
        out += (["+"] if out else []) + s
    return out


def user_command(p: Plan) -> list[str]:
    """Your own Flatpaks: no root needed."""
    if p.flatpak_user is None:
        return ["flatpak", "update", "--user", "-y", "--noninteractive"]
    if p.flatpak_user:
        return ["flatpak", "update", "--user", "-y", "--noninteractive", "--", *_names("flatpak", p.flatpak_user)]
    return []


# APT::Status-Fd lines: "pmstatus:curl:42.8571:Unpacking curl (amd64)", "dlstatus:3:30.5:Retrieving file 3 of 9"
_STATUS = re.compile(r"^(pm|dl)status:[^:]*:([\d.]+):(.*)$")


def parse_status(line: str) -> tuple[float, str] | None:
    """(percent, message) for an APT status line, else None."""
    m = _STATUS.match(line)
    if not m:
        return None
    try:
        pct = float(m.group(2))
    except ValueError:
        return None
    return (pct / 2 if m.group(1) == "dl" else 50 + pct / 2), m.group(3)


def stream(cmd: list[str], on_line, env=None) -> int:
    """Run cmd, feeding each output line (stdout and stderr together) to on_line; the exit code. The child keeps
    Python's ignored SIGPIPE (restore_signals=False): if the app closes mid-update, flatpak isn't killed halfway."""
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                          errors="replace", env=env, stdin=subprocess.DEVNULL, restore_signals=False) as proc:
        for line in proc.stdout:
            on_line(line.rstrip("\n").replace("\r", ""))
        return proc.wait()


ROOT_COMMAND = roothelper.command          # tests swap this for the tree's copy run as you


def run(p: Plan, on_line) -> tuple[bool, str]:
    """Run a plan: the root batch first (one prompt), then your Flatpaks. (ok, summary)."""
    args = root_args(p)
    ucmd = user_command(p)
    if args:
        try:
            cmd = ROOT_COMMAND(SPELL, *args)
        except roothelper.HelperError as e:
            return False, str(e)
        on_line("$ " + " ".join(["root-helper", *args]))
        code = stream(cmd, on_line)
        if code in (126, 127):
            return False, tr("grimoire.spells.updatel.apply",
                             "The password prompt was cancelled; nothing was changed.")
        if code == 3:
            return False, tr("grimoire.spells.updatel.apply",
                             "Refused: the upgrade would remove a package that has to stay (see the log).")
        if code == 4:
            return False, tr("grimoire.spells.updatel.apply",
                             "Refused: the upgrade would remove packages you didn't confirm (see the log).")
        if code:
            return False, tr("grimoire.spells.updatel.apply",
                             "The update stopped with an error (code {code}); see the log.").format(code=code)
    if ucmd:
        on_line("$ " + " ".join(ucmd))
        code = stream(ucmd, on_line)
        if code:
            return False, tr("grimoire.spells.updatel.apply",
                             "Updating your Flatpaks failed (code {code}); see the log.").format(code=code)
    only_lists = p.refresh and not ucmd and args == ["refresh"]
    return True, (tr("grimoire.spells.updatel.apply", "Package lists refreshed.") if only_lists
                  else tr("grimoire.spells.updatel.apply", "Updates installed."))
