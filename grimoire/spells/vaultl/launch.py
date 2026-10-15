# SPDX-License-Identifier: GPL-3.0-or-later
"""What double-clicking a file should do when it's a program. KDE's KIO refuses to start executables that a plain
"open this URL" asks for ("launching executables is not allowed in this context"), so VaultL sorts them out itself,
like Dolphin: native programs and scripts are run after a question, .desktop launchers through gio, Windows and
macOS programs get an explanation (and a Windows compatibility tool when one is installed). No Qt widgets here.
"""
import configparser
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from grimoire.paths import HOME

NATIVE, SCRIPT, DESKTOP, WINDOWS, MAC, OTHER = "native", "script", "desktop", "windows", "mac", "other"
WIN_EXT = {".exe", ".msi", ".msp", ".bat", ".cmd", ".com", ".scr"}
MAC_EXT = {".dmg", ".pkg", ".mpkg"}
NOT_PROGRAMS = {".so", ".o", ".ko", ".a", ".efi"}     # ELF/PE files that are libraries or firmware, not programs
HEAD = 4096


def _head(p: Path) -> bytes:
    """The first bytes of a regular file (never a FIFO or device: reading those would hang)."""
    try:
        if not stat.S_ISREG(p.stat().st_mode):
            return b""
        with open(p, "rb") as f:
            return f.read(HEAD)
    except OSError:
        return b""


def executable(p: Path) -> bool:
    return os.access(p, os.X_OK) and p.is_file()


def is_appimage(p: Path, head: bytes | None = None) -> bool:
    head = _head(p) if head is None else head
    return p.suffix.lower() == ".appimage" or head[:4] == b"\x7fELF" and head[8:11] in (b"AI\x01", b"AI\x02")


def _pe(head: bytes) -> bool:
    """A DOS/Windows executable: "MZ", and the PE signature where the DOS header points."""
    if head[:2] != b"MZ" or len(head) < 64:
        return False
    at = int.from_bytes(head[60:64], "little")
    return head[at:at + 4] == b"PE\0\0" if at + 4 <= len(head) else True


def classify(p: Path) -> str:
    """NATIVE (ELF program or AppImage, runnable or not yet), SCRIPT (shebang + exec bit), DESKTOP (.desktop
    launcher), WINDOWS (.exe/.msi/.bat… or PE), MAC (.dmg/.pkg or an .app bundle), else OTHER (open it normally)."""
    ext = p.suffix.lower()
    if p.is_dir():
        return MAC if ext == ".app" and (p / "Contents").is_dir() else OTHER
    head = _head(p)
    if is_appimage(p, head):
        return NATIVE
    if ext == ".desktop":
        return DESKTOP
    if ext in WIN_EXT:
        return WINDOWS
    if ext in MAC_EXT:
        return MAC
    if head[:4] == b"\x7fELF":
        if ext in NOT_PROGRAMS or ".so." in p.name:      # libraries often carry the exec bit too
            return OTHER
        return NATIVE if executable(p) or head[16:17] in (b"\x02", b"\x03") else OTHER   # ET_EXEC / ET_DYN
    if head[:2] == b"#!" and executable(p):
        return SCRIPT
    if _pe(head) and ext not in NOT_PROGRAMS and ext != ".dll":
        return WINDOWS
    return OTHER


def make_executable(p: Path):
    """chmod u+x, nothing more (group and others keep what they had)."""
    os.chmod(p, p.stat().st_mode | stat.S_IXUSR)


# ------------------------------------------------------------------ .desktop launchers
@dataclass
class Entry:
    name: str
    exec: str
    type: str
    url: str
    terminal: bool


def desktop_entry(p: Path) -> Entry | None:
    """The [Desktop Entry] group of a launcher, or None if it isn't one."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str                                  # keys are case-sensitive (Name, Exec…)
    try:
        cp.read_string(p.read_text(errors="replace")[:200_000])
    except (OSError, configparser.Error):
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    d = cp["Desktop Entry"]
    return Entry(name=d.get("Name", p.stem), exec=d.get("Exec", ""), type=d.get("Type", "Application"),
                 url=d.get("URL", ""), terminal=d.get("Terminal", "false").lower() == "true")


def app_dirs() -> list[Path]:
    data_home = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    dirs = [data_home] + [Path(d) for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
                          if d]
    dirs += [data_home / "flatpak/exports/share", Path("/var/lib/flatpak/exports/share")]
    seen, out = set(), []
    for d in dirs:
        if (d / "applications") not in seen:
            seen.add(d / "applications")
            out.append(d / "applications")
    return out


def desktop_file(desktop_id: str) -> Path | None:
    """An installed app's .desktop file by its id ("org.kde.kate.desktop")."""
    return next((d / desktop_id for d in app_dirs() if (d / desktop_id).is_file()), None)


def default_app(mime: str) -> Path | None:
    """The .desktop file of the app the system opens this type with (gio mime)."""
    try:
        out = subprocess.run(["gio", "mime", mime], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    first = out.splitlines()[0] if out else ""
    return desktop_file(first.rsplit(":", 1)[-1].strip()) if first.startswith("Default application") else None


# ------------------------------------------------------------------ commands (never through a shell)
def run_command(p: Path) -> list[str]:
    return ["gio", "launch", str(p)] if classify(p) == DESKTOP else [str(p)]


def text_command(p: Path) -> list[str] | None:
    """Open a script or launcher as text, in the default text editor (straight, not through KIO, which would refuse
    an executable script)."""
    app = default_app("text/plain")
    return ["gio", "launch", str(app), str(p)] if app else None


@dataclass
class Runner:
    id: str
    name: str                                             # a product name: not translated
    command: list[str]                                    # the file's path goes at the end


def runners() -> list[Runner]:
    """Windows compatibility tools that are installed: Wine, Bottles, Protontricks (native or Flatpak)."""
    found = []
    if shutil.which("wine"):
        found.append(Runner("wine", "Wine", ["wine", "start", "/unix"]))
    for desktop_id in ("com.usebottles.bottles.desktop",):
        if (f := desktop_file(desktop_id)):
            found.append(Runner("bottles", "Bottles", ["gio", "launch", str(f)]))
    if (cmd := shutil.which("protontricks-launch")):
        found.append(Runner("protontricks", "Protontricks", [cmd, "--no-term"]))
    elif (f := desktop_file("com.github.Matoking.protontricks-launch.desktop")):
        found.append(Runner("protontricks", "Protontricks", ["gio", "launch", str(f)]))
    return found


def start(argv: list[str], cwd: Path) -> tuple[bool, str]:
    """Start a program on its own (it outlives VaultL), in its folder. Returns (started, error)."""
    from PySide6.QtCore import QProcess
    proc = QProcess()
    proc.setProgram(argv[0])
    proc.setArguments(argv[1:])
    proc.setWorkingDirectory(str(cwd))
    ok = bool(proc.startDetached())                       # PySide6: a bool (the pid is not needed)
    return ok, "" if ok else proc.errorString()


RUN = start                                               # stub point for tests
