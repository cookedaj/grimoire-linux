# SPDX-License-Identifier: GPL-3.0-or-later
"""Installing and removing (no Qt): a Task is one app to install or remove; run_batch() runs a list of them.

Everything needing root (APT, system Flatpaks, snaps) in a batch goes into ONE call of StoreL's root helper, steps
joined by "+", so a batch asks for the password once; the helper prints "@@step N" as each step starts. Your own
Flatpaks install and uninstall as you, with no prompt. APT steps were simulated for the preview (sources.simulate);
the helper simulates again and refuses any removal that isn't on the list you confirmed. Uninstalling a Flatpak
never deletes its data in ~/.var/app, and an APT removal never purges.
"""
import re
from dataclasses import dataclass, field

from grimoire import roothelper
from grimoire.i18n import tr
from grimoire.spells.storel import sources
from grimoire.spells.updatel.apply import parse_status, stream

SPELL = "storel"
WAITING, RUNNING, DONE, FAILED, CANCELLED = "waiting", "running", "done", "failed", "cancelled"


@dataclass
class Task:
    action: str                        # "install" | "remove"
    source: str                        # "apt" | "flatpak" | "snap"
    title: str                         # the app's name, for the queue
    key: str                           # the catalog key (to refresh that app after)
    names: list[str]                   # APT packages, Flatpak refs (app/…) or one snap
    scope: str = "system"              # Flatpak: "user" (no password) or "system"
    remote: str = ""                   # Flatpak install: where from
    classic: bool = False              # snap install with --classic
    removals: list[str] = field(default_factory=list)      # APT: what you confirmed may go (from the preview)
    state: str = WAITING
    progress: float = -1               # 0..100, -1 while unknown
    message: str = ""

    def root(self) -> bool:
        return not (self.source == "flatpak" and self.scope == "user")


def _check(kind: str, names: list[str]) -> list[str]:
    pattern = {"apt": sources.APT, "flatpak": sources.REF, "snap": sources.SNAP, "remote": sources.REMOTE}[kind]
    bad = [n for n in names if not pattern.fullmatch(n or "")]
    if bad or not names:
        raise ValueError(tr("grimoire.spells.storel.apply", "Not a valid name: {name}").format(
            name=bad[0] if bad else "–"))
    return names


def step(t: Task) -> list[str]:
    """The helper's words for one root task."""
    if t.source == "apt":
        gone = ",".join(_check("apt", sorted(set(t.removals)))) if t.removals else ""
        if t.action == "remove" and not gone:
            raise ValueError(tr("grimoire.spells.storel.apply", "A removal needs the confirmed list of packages."))
        return [f"apt-{t.action}", *([f"--removals={gone}"] if gone else []), *_check("apt", t.names)]
    if t.source == "flatpak":
        if t.action == "install":
            return ["flatpak-install", *_check("remote", [t.remote]), *_check("flatpak", t.names)]
        return ["flatpak-remove", *_check("flatpak", t.names)]
    if t.source == "snap":
        name = _check("snap", t.names[:1])
        if t.action == "remove" and sources.PROTECTED_SNAPS.fullmatch(name[0]):
            raise ValueError(tr("grimoire.spells.storel.apply", "Not a valid name: {name}").format(name=name[0]))
        return ["snap-install", *(["--classic"] if t.classic else []), *name] if t.action == "install" else \
            ["snap-remove", *name]
    raise ValueError(t.source)


def root_args(tasks: list[Task]) -> list[str]:
    out = []
    for t in tasks:
        out += (["+"] if out else []) + step(t)
    return out


def user_command(t: Task) -> list[str]:
    """Your own Flatpaks: no root needed."""
    if t.action == "install":
        return ["flatpak", "install", "--user", "-y", "--noninteractive", "--", *_check("remote", [t.remote]),
                *_check("flatpak", t.names)]
    return ["flatpak", "uninstall", "--user", "-y", "--noninteractive", "--", *_check("flatpak", t.names)]


_PCT = re.compile(r"(\d{1,3})%")


def progress(line: str) -> tuple[float, str] | None:
    """(percent, message) from an APT status line or a Flatpak progress line ("Installing 1/2… ███  45%")."""
    st = parse_status(line)
    if st:
        return st
    m = _PCT.findall(line)
    if m and ("Installing" in line or "Uninstalling" in line or "Downloading" in line):
        return min(100.0, float(m[-1])), ""
    return None


ROOT_COMMAND = roothelper.command          # tests swap this for the tree's copy run as you
STREAM = stream                            # tests swap this to record commands instead of running them


def _fail(code: int) -> str:
    return {126: tr("grimoire.spells.storel.apply", "The password prompt was cancelled; nothing was changed."),
            127: tr("grimoire.spells.storel.apply", "The password prompt was cancelled; nothing was changed."),
            3: tr("grimoire.spells.storel.apply", "Refused: this would remove a package that has to stay."),
            4: tr("grimoire.spells.storel.apply", "Refused: this would remove packages you didn't confirm."),
            5: tr("grimoire.spells.storel.apply", "APT couldn't plan this; see the log."),
            6: tr("grimoire.spells.storel.apply", "The plan changed since the preview; try again.")}.get(
        code, tr("grimoire.spells.storel.apply", "Stopped with an error (code {code}); see the log.").format(code=code))


def run_batch(tasks: list[Task], on_line, on_task) -> None:
    """Run tasks: the root ones in one helper call first (one prompt), then your Flatpaks one by one. on_line gets
    every output line; on_task(task) is called whenever a task's state, progress or message changes."""
    root = [t for t in tasks if t.root()]
    user = [t for t in tasks if not t.root()]
    if root:
        _run_root(root, on_line, on_task)
    for t in user:
        if t.state != WAITING:
            continue
        try:
            cmd = user_command(t)
        except ValueError as e:
            _set(t, on_task, FAILED, str(e))
            continue
        _set(t, on_task, RUNNING, "")
        on_line("$ " + " ".join(cmd))

        def line(text, t=t):
            p = progress(text)
            if p:
                t.progress = p[0]
                on_task(t)
            else:
                on_line(text)
        code = STREAM(cmd, line)
        _set(t, on_task, DONE if code == 0 else FAILED, "" if code == 0 else
             tr("grimoire.spells.storel.apply", "Flatpak stopped with an error (code {code}); see the log.").format(
                 code=code))


def _set(t: Task, on_task, state: str, message: str):
    t.state, t.message = state, message
    if state in (DONE, FAILED, CANCELLED):
        t.progress = 100 if state == DONE else -1
    on_task(t)


def _run_root(tasks: list[Task], on_line, on_task):
    try:
        args = root_args(tasks)
        cmd = ROOT_COMMAND(SPELL, *args)
    except (ValueError, roothelper.HelperError) as e:
        for t in tasks:
            _set(t, on_task, FAILED, str(e))
        return
    on_line("$ " + " ".join(["storel-root-helper", *args]))
    current = [None]

    def line(text):
        m = re.fullmatch(r"@@step (\d+)", text.strip())
        if m:
            n = int(m.group(1)) - 1
            if current[0] is not None:
                _set(current[0], on_task, DONE, "")
            current[0] = tasks[n] if 0 <= n < len(tasks) else None
            if current[0]:
                _set(current[0], on_task, RUNNING, "")
            return
        p = progress(text)
        if p and current[0]:
            current[0].progress = p[0]
            if p[1]:
                current[0].message = p[1]
            on_task(current[0])
            return
        on_line(text)
    code = STREAM(cmd, line)
    if code == 0:
        for t in tasks:
            if t.state in (WAITING, RUNNING):
                _set(t, on_task, DONE, "")
        return
    msg = _fail(code)
    for t in tasks:
        if t is current[0] or (current[0] is None and t.state == WAITING):
            _set(t, on_task, FAILED, msg)
        elif t.state == WAITING:            # after the one that failed: never started
            _set(t, on_task, CANCELLED, tr("grimoire.spells.storel.apply", "Not run: an earlier step failed."))
