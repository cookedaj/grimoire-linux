# SPDX-License-Identifier: GPL-3.0-or-later
"""Printers for Settings → Printers: CUPS through python3-cups (no Qt).

Every call opens its own short connection (they run on worker threads). Admin operations (pause, remove, the
system-wide default) may be refused by CUPS when you're not in the lpadmin group; that comes back as a PrinterError
worded for the UI, never as a hang: the password callback aborts instead of prompting on a terminal. Setting the
default falls back to your own default (`lpoptions -d`, ~/.cups/lpoptions), which needs no rights.
Adding printers and drivers is left to KDE's printer settings (print-manager). Tests swap CONNECT and RUN.
"""
import subprocess
from dataclasses import dataclass, field

from grimoire.i18n import tr, tr_noop

try:
    import cups
except ImportError:                    # python3-cups not installed: the panel says how to get it
    cups = None

CONNECT = cups.Connection if cups else None
RUN = subprocess.run
INSTALL = "sudo apt install python3-cups"

IDLE, PRINTING, STOPPED = 3, 4, 5
JOB_STATES = {3: tr_noop("grimoire.printers", "Waiting"), 4: tr_noop("grimoire.printers", "Held"),
              5: tr_noop("grimoire.printers", "Printing"), 6: tr_noop("grimoire.printers", "Stopped")}
# printer-state-reasons worth showing (CUPS adds -report/-warning/-error suffixes)
REASONS = {"media-empty": tr_noop("grimoire.printers", "Out of paper"),
           "media-needed": tr_noop("grimoire.printers", "Out of paper"),
           "media-jam": tr_noop("grimoire.printers", "Paper jam"),
           "toner-low": tr_noop("grimoire.printers", "Toner low"),
           "toner-empty": tr_noop("grimoire.printers", "Out of toner"),
           "marker-supply-low": tr_noop("grimoire.printers", "Ink low"),
           "marker-supply-empty": tr_noop("grimoire.printers", "Out of ink"),
           "door-open": tr_noop("grimoire.printers", "Cover open"),
           "cover-open": tr_noop("grimoire.printers", "Cover open"),
           "offline": tr_noop("grimoire.printers", "Offline"),
           "connecting-to-device": tr_noop("grimoire.printers", "Connecting…"),
           "cups-missing-filter": tr_noop("grimoire.printers", "Driver problem"),
           "cups-insecure-filter": tr_noop("grimoire.printers", "Driver problem")}
JOB_ATTRS = ["job-id", "job-name", "job-printer-uri", "job-state", "job-k-octets", "time-at-creation",
             "job-originating-user-name"]


class PrinterError(Exception):
    """A CUPS failure worded for the UI."""


@dataclass
class Printer:
    name: str
    info: str = ""
    location: str = ""
    model: str = ""
    state: int = IDLE
    message: str = ""
    reasons: list = field(default_factory=list)
    default: bool = False
    shared: bool = False
    uri: str = ""

    @property
    def label(self) -> str:
        """The name people read: CUPS's description, or the queue name with spaces for underscores."""
        return self.info if self.info and self.info != self.name else self.name.replace("_", " ")

    @property
    def paused(self) -> bool:
        return self.state == STOPPED

    @property
    def network(self) -> bool:
        """Found on the network by cups-browsed/driverless: removing it may not stick."""
        return self.uri.startswith(("implicitclass:", "dnssd:", "ipps:", "ipp:"))


@dataclass
class Job:
    id: int
    name: str
    printer: str
    state: int
    size: int = 0                 # bytes
    created: int = 0              # epoch seconds
    user: str = ""


def available() -> bool:
    return CONNECT is not None


def _no_password(prompt):
    return None                   # never prompt on stdin from a worker thread: abort and report instead


def _error(err: Exception) -> PrinterError:
    if cups and isinstance(err, cups.IPPError):
        status, text = (err.args + (None, ""))[:2]
        if status in (cups.IPP_NOT_AUTHORIZED, cups.IPP_FORBIDDEN, getattr(cups, "IPP_AUTHENTICATION_CANCELED", -1)):
            return PrinterError(tr("grimoire.printers", "CUPS needs printer admin rights for this. Use KDE's printer "
                                   "settings, which can ask for your password, or join the lpadmin group."))
        if status == cups.IPP_NOT_FOUND:
            return PrinterError(tr("grimoire.printers", "That printer or job is gone."))
        return PrinterError(tr("grimoire.printers", "CUPS said: {err}").format(err=text or status))
    if cups and isinstance(err, cups.HTTPError):
        return PrinterError(tr("grimoire.printers", "Couldn't talk to CUPS (HTTP {code}).").format(code=err.args[0]))
    if isinstance(err, RuntimeError):
        return PrinterError(tr("grimoire.printers", "The printing service (CUPS) isn't running."))
    return PrinterError(str(err) or type(err).__name__)


def _conn():
    if CONNECT is None:
        raise PrinterError(tr("grimoire.printers", "Printing needs python3-cups: {cmd}").format(cmd=INSTALL))
    if cups:                      # per thread in pycups and libcups: set it on every worker, not once at import
        cups.setPasswordCB(_no_password)
    try:
        return CONNECT()
    except Exception as e:
        raise _error(e) from None


def _call(fn):
    try:
        return fn(_conn())
    except PrinterError:
        raise
    except Exception as e:
        raise _error(e) from None


def _default(c) -> str:
    """Your default as apps see it (lpoptions over the server's), else the server's."""
    try:
        for (name, instance), dest in c.getDests().items():
            if dest.is_default and not instance:
                return name
    except Exception:
        pass
    try:
        return c.getDefault() or ""
    except Exception:
        return ""


def listing() -> tuple[list[Printer], list[Job]]:
    """Every printer (default first, then by name) and the jobs not finished yet."""
    def go(c):
        default = _default(c)
        printers = []
        for name, a in c.getPrinters().items():
            printers.append(Printer(name=name, info=a.get("printer-info") or "",
                                    location=a.get("printer-location") or "",
                                    model=a.get("printer-make-and-model") or "", state=a.get("printer-state", IDLE),
                                    message=a.get("printer-state-message") or "",
                                    reasons=[r for r in a.get("printer-state-reasons", []) if r != "none"],
                                    default=name == default, shared=bool(a.get("printer-is-shared")),
                                    uri=a.get("device-uri") or ""))
        printers.sort(key=lambda p: (not p.default, p.name.lower()))
        jobs = []
        for jid, a in c.getJobs(which_jobs="not-completed", requested_attributes=JOB_ATTRS).items():
            jobs.append(Job(id=jid, name=a.get("job-name") or "",
                            printer=(a.get("job-printer-uri") or "").rsplit("/", 1)[-1],
                            state=a.get("job-state", 3), size=int(a.get("job-k-octets") or 0) * 1024,
                            created=int(a.get("time-at-creation") or 0), user=a.get("job-originating-user-name") or ""))
        jobs.sort(key=lambda j: j.id)
        return printers, jobs
    return _call(go)


def reasons(p: Printer) -> list[str]:
    """The printer's state reasons we know how to say, as tr_noop keys (translate where shown)."""
    out = []
    for r in p.reasons:
        key = r.rsplit("-", 1)[0] if r.endswith(("-report", "-warning", "-error")) else r
        if key in REASONS and REASONS[key] not in out:
            out.append(REASONS[key])
    return out


def set_default(name: str) -> str:
    """'system' when CUPS took it system-wide, 'user' when it fell back to your own default (lpoptions)."""
    try:
        _call(lambda c: c.setDefault(name))
        return "system"
    except PrinterError:
        try:
            out = RUN(["lpoptions", "-d", name], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as e:
            raise PrinterError(tr("grimoire.printers", "Couldn't set the default printer: {err}").format(err=e))
        if out.returncode != 0:
            raise PrinterError(tr("grimoire.printers", "Couldn't set the default printer: {err}").format(
                err=(out.stderr or "").strip() or out.returncode))
        return "user"


def pause(name: str):
    _call(lambda c: c.disablePrinter(name))


def resume(name: str):
    _call(lambda c: c.enablePrinter(name))


def test_page(name: str) -> int:
    return _call(lambda c: c.printTestPage(name))


def cancel(job_id: int):
    _call(lambda c: c.cancelJob(job_id))


def remove(name: str):
    _call(lambda c: c.deletePrinter(name))
