# SPDX-License-Identifier: GPL-3.0-or-later
"""SystemL's Logs: reading the systemd journal through `journalctl -o json` (no Qt, no root).

Your own journal (`--user`) is always readable; the system journal only for members of systemd-journal or adm
(journald's file permissions decide, so we check the groups instead of asking for a password). A Reader streams
journalctl's output on its own thread and hands parsed entries over in batches; follow mode keeps it running.

Log text comes from any program on the machine, so it's untrusted: messages are cleaned of terminal escapes,
control characters and bidi overrides here, and the UI only ever shows them as plain text.
"""
import grp
import json
import os
import re
import subprocess
import threading
import time

from grimoire.i18n import tr, tr_noop

JOURNALCTL = "journalctl"
READERS = ("systemd-journal", "adm", "wheel")        # groups journald lets read the system journal
# syslog priorities 0-7, as journalctl's -p takes them
LEVELS = [tr_noop("grimoire.spells.systeml.journal", "Emergency"), tr_noop("grimoire.spells.systeml.journal", "Alert"),
          tr_noop("grimoire.spells.systeml.journal", "Critical"), tr_noop("grimoire.spells.systeml.journal", "Error"),
          tr_noop("grimoire.spells.systeml.journal", "Warning"), tr_noop("grimoire.spells.systeml.journal", "Notice"),
          tr_noop("grimoire.spells.systeml.journal", "Info"), tr_noop("grimoire.spells.systeml.journal", "Debug")]
UNIT_SUFFIXES = (".service", ".scope", ".slice", ".socket", ".timer", ".mount", ".target", ".path", ".swap",
                 ".device", ".automount")
_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")
# C0/C1 controls except tab and newline, plus the bidi embeddings, overrides and isolates a line could use to
# make itself read differently from what it says
_UNSAFE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f‪-‮⁦-⁩‎‏؜]")


def level_text(prio: int) -> str:
    return tr("grimoire.spells.systeml.journal", LEVELS[prio]) if 0 <= prio < len(LEVELS) else str(prio)


def can_read_system() -> bool:
    """True when this user may read the system journal (root, or in one of journald's reader groups)."""
    if os.geteuid() == 0:
        return True
    names = set()
    for gid in set(os.getgroups()) | {os.getgid()}:
        try:
            names.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            pass
    return bool(names & set(READERS))


def clean(value) -> str:
    """A journal field as safe plain text: binary fields (lists of bytes) decoded, escapes and controls removed."""
    if value is None:
        return ""
    if isinstance(value, list):            # journalctl writes non-UTF-8 fields as arrays of byte values
        try:
            value = bytes(v for v in value if isinstance(v, int) and 0 <= v < 256).decode("utf-8", "replace")
        except (TypeError, ValueError):
            value = str(value)
    value = _ANSI.sub("", str(value)).replace("\r\n", "\n").replace("\r", "\n")
    return _UNSAFE.sub("�", value)


def parse(line: str) -> dict | None:
    """One `journalctl -o json` line as an entry: t (seconds), prio, source, pid, unit, msg and every field."""
    try:
        raw = json.loads(line)
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    fields = {k: clean(v) for k, v in raw.items()}
    try:
        t = int(fields.get("__REALTIME_TIMESTAMP") or 0) / 1e6
    except ValueError:
        t = 0.0
    try:
        prio = int(fields.get("PRIORITY", "6"))
    except ValueError:
        prio = 6
    source = fields.get("SYSLOG_IDENTIFIER") or fields.get("_COMM") or fields.get("_EXE", "").rsplit("/", 1)[-1] \
        or ("kernel" if fields.get("_TRANSPORT") == "kernel" else "")
    # systemd's own lines about a unit ("Started …") name it in (USER_)UNIT; the sender is then init.scope
    unit = fields.get("USER_UNIT") or fields.get("UNIT") or fields.get("_SYSTEMD_USER_UNIT") \
        or fields.get("_SYSTEMD_UNIT") or ""
    msg = fields.get("MESSAGE", "")
    return {"t": t, "prio": max(0, min(7, prio)), "source": source, "pid": fields.get("_PID", ""), "unit": unit,
            "msg": msg, "fields": fields, "cursor": fields.get("__CURSOR", "")}


def stamp(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else ""


def text_line(e: dict) -> str:
    """An entry as one line of text, the way `journalctl -o short-iso` prints it."""
    host = e["fields"].get("_HOSTNAME", "")
    who = e["source"] + (f"[{e['pid']}]" if e["pid"] else "")
    return f"{stamp(e['t'])} {host} {who}: {e['msg']}".replace(" :", ":", 1) if host else \
        f"{stamp(e['t'])} {who}: {e['msg']}"


def is_unit(name: str) -> bool:
    return name.endswith(UNIT_SUFFIXES)


def command(scope="user", prio=None, source="", boot=None, since=None, until=None, grep="", lines=2000,
            follow=False) -> list[str]:
    """journalctl's arguments for these filters. scope: "user" (your journal) or "system"; prio: show this level
    and worse (None = all); source: a unit name, else a syslog identifier (an app); boot: a boot id, or None for
    every boot; since/until: epoch seconds; grep: text searched in messages, case-insensitive."""
    cmd = [JOURNALCTL, "--user" if scope == "user" else "--system", "-o", "json", "--all", "--no-pager",
           "--quiet"]
    if prio is not None:
        cmd += ["-p", f"0..{int(prio)}"]
    if source:
        if is_unit(source):
            cmd += ["--user-unit" if scope == "user" else "-u", source]
        else:
            cmd += ["-t", source]
    if boot:
        if not re.fullmatch(r"[0-9a-f]{32}|-?\d+", boot):
            raise ValueError(boot)
        cmd += ["-b", boot]
    if since:
        cmd.append(f"--since=@{int(since)}")
    if until and not follow:
        cmd.append(f"--until=@{int(until)}")
    if grep:
        cmd += [f"--grep={re.escape(grep)}", "--case-sensitive=false"]
    if lines:
        cmd += ["-n", str(int(lines))]
    if follow:
        cmd.append("-f")
    return cmd


def _run(args: list[str], timeout=20) -> str:
    try:
        return subprocess.run([JOURNALCTL, *args], capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def boots(scope="user") -> list[dict]:
    """Boots the journal knows, newest first: {id, index, first, last} (epoch seconds)."""
    try:
        data = json.loads(_run(["--user" if scope == "user" else "--system", "--list-boots", "-o", "json",
                                "--no-pager"]) or "[]")
    except ValueError:
        return []
    out = []
    for b in data if isinstance(data, list) else []:
        try:
            out.append({"id": str(b["boot_id"]), "index": int(b["index"]), "first": int(b["first_entry"]) / 1e6,
                        "last": int(b["last_entry"]) / 1e6})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda b: -b["index"])


def sources(scope="user", limit=2000) -> list[str]:
    """Units and apps that wrote to this journal, for the source picker's suggestions."""
    sel = "--user" if scope == "user" else "--system"
    unit_field = "_SYSTEMD_USER_UNIT" if scope == "user" else "_SYSTEMD_UNIT"
    names = set()
    for field in (unit_field, "SYSLOG_IDENTIFIER"):
        for line in _run([sel, "-F", field]).splitlines()[:limit]:
            name = clean(line).strip()
            if name and len(name) < 200:
                names.add(name)
    return sorted(names, key=str.lower)


def export(entries: list[dict], path, as_json=False):
    """Write entries to path: plain lines, or JSON lines with every field. Atomic (temp file + rename)."""
    tmp = f"{path}.part"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write((json.dumps(e["fields"], ensure_ascii=False) if as_json else text_line(e)) + "\n")
    os.replace(tmp, path)


class Reader:
    """Runs journalctl on its own thread; the UI drains what arrived with take() (on a timer), so nothing blocks
    and a quiet journal in follow mode still shows its newest line at once. stop() ends it early (follow mode never
    ends by itself); `done` turns true once journalctl has ended, with `error` set if it failed."""

    def __init__(self, cmd: list[str]):
        self.cmd = cmd
        self.proc: subprocess.Popen | None = None
        self.stopped = self.done = False
        self.error = ""
        self._pending: list[dict] = []
        self._lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def take(self) -> list[dict]:
        with self._lock:
            out, self._pending = self._pending, []
        return out

    def stop(self):
        self.stopped = True
        p = self.proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass

    def _run(self):
        try:
            try:
                self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                             errors="replace", bufsize=1)
            except OSError as e:
                self.error = tr("grimoire.spells.systeml.journal", "Couldn't run journalctl: {error}").format(
                    error=e.strerror or str(e))
                return
            if self.stopped:                      # stop() came before the process existed
                self.proc.terminate()
            stderr: list[str] = []
            t_err = threading.Thread(target=lambda: stderr.extend(self.proc.stderr.read().splitlines()[-20:]),
                                     daemon=True)
            t_err.start()
            try:
                for line in self.proc.stdout:
                    if self.stopped:
                        break
                    e = parse(line)
                    if e:
                        with self._lock:
                            self._pending.append(e)
            except (OSError, ValueError):
                pass
            try:
                code = self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                code = -9
            t_err.join(timeout=1)
            if self.stopped:
                return
            last = next((l for l in reversed(stderr) if l.strip()), "")
            if code not in (0, 1):                   # 1: --grep found nothing
                self.error = clean(last) or tr("grimoire.spells.systeml.journal", "journalctl stopped ({code})"
                                               ).format(code=code)
            elif code == 1 and last and "match" not in last.lower():
                self.error = clean(last)
        finally:
            self.done = True
