# SPDX-License-Identifier: GPL-3.0-or-later
"""Edit an app's menu entry without touching system files (no Qt). The freedesktop menu takes a user's
~/.local/share/applications/<id>.desktop over the system one with the same id, so every change is a copy of the
system file with a few keys changed (name, icon, command, NoDisplay=true to hide it), marked X-Grimoire-Edited.
"Reset to default" moves that copy to the Trash. kbuildsycoca6 then tells Plasma's menus about it."""
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from grimoire.i18n import tr
from grimoire.paths import HOME

GROUP = "Desktop Entry"
MARK = "X-Grimoire-Edited"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\.desktop")
FIELD_CODES = set("fFuUdDnNickvm")
MAX_SIZE = 512 * 1024
RUN = subprocess.run                           # stub point for tests (kbuildsycoca6)


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")


def data_dirs() -> list[Path]:
    dirs = [Path(d) for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    return [d for d in dirs if d != data_home()]


def user_dir() -> Path:
    return data_home() / "applications"


def valid_id(app_id: str) -> bool:
    return bool(ID.fullmatch(app_id or ""))


def _find(base: Path, app_id: str) -> Path | None:
    """The file with this desktop id under an applications folder ("kde4-foo.desktop" may be kde4/foo.desktop)."""
    direct = base / app_id
    if direct.is_file():
        return direct
    if "-" not in app_id or not base.is_dir():
        return None
    parts = app_id.split("-")
    for cut in range(1, len(parts)):                      # kde4/foo-bar.desktop, kde4/foo/bar.desktop, ...
        for sub in _splits(parts[:cut]):
            p = base.joinpath(*sub, "-".join(parts[cut:]))
            if p.is_file():
                return p
    return None


def _splits(parts: list[str]):
    """Every way to make folder names from these dash-separated parts (a-b → [a-b], [a, b])."""
    if len(parts) == 1:
        yield [parts[0]]
        return
    for rest in _splits(parts[1:]):
        yield [parts[0]] + rest
        yield [parts[0] + "-" + rest[0]] + rest[1:]


def system_file(app_id: str) -> Path | None:
    return next((p for d in data_dirs() if (p := _find(d / "applications", app_id))), None)


def user_file(app_id: str) -> Path | None:
    return _find(user_dir(), app_id)


# ---- reading and writing the [Desktop Entry] group ----------------------------------------------------------------

def _unescape(v: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}.get(m.group(1),
                                                                                              m.group(0)), v)


def _escape(v: str) -> str:
    return v.replace("\\", "\\\\")


def read_group(text: str) -> dict:
    """{key: raw value} of the [Desktop Entry] group (localized keys like Name[fr] included)."""
    out, inside = {}, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            inside = s[1:-1] == GROUP
        elif inside and "=" in s and not s.startswith("#"):
            k, v = s.split("=", 1)
            out.setdefault(k.strip(), v.strip())
    return out


def edit_group(text: str, sets: dict, drop_localized: set = frozenset(), remove: set = frozenset()) -> str:
    """text with keys in [Desktop Entry] set (raw values), localized variants of drop_localized and the keys in
    remove taken out. Everything else (comments, other groups, actions) stays as it was."""
    lines = text.splitlines()
    out, inside, done, end = [], False, set(), None
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if inside and end is None:
                end = len(out)
            inside = s[1:-1] == GROUP
            out.append(line)
            continue
        if inside and "=" in s and not s.startswith("#"):
            key = s.split("=", 1)[0].strip()
            base = key.split("[", 1)[0]
            if key in remove or (base in drop_localized and key != base):
                continue
            if key in sets:
                if key in done:
                    continue
                out.append(f"{key}={sets[key]}")
                done.add(key)
                continue
        out.append(line)
    if end is None:
        end = len(out)
    while end > 1 and out[end - 1].strip() == "":       # new keys go before the blank line that ends the group
        end -= 1
    missing = [f"{k}={v}" for k, v in sets.items() if k not in done]
    out[end:end] = missing
    return "\n".join(out) + "\n"


# ---- the command --------------------------------------------------------------------------------------------------

def split_exec(cmd: str) -> list[str]:
    """An Exec value's arguments, quoted as the spec (and KDE) allow: "double quotes" with \\" \\` \\$ \\\\ escapes,
    'single quotes', and a backslash before any character outside quotes. Raises ValueError for unclosed quotes."""
    args, cur, have, i = [], "", False, 0
    while i < len(cmd):
        c = cmd[i]
        if c in " \t":
            if have:
                args.append(cur)
                cur, have = "", False
        elif c == '"':
            have, i = True, i + 1
            while i < len(cmd) and cmd[i] != '"':
                if cmd[i] == "\\" and i + 1 < len(cmd) and cmd[i + 1] in '"`$\\':
                    i += 1
                cur += cmd[i]
                i += 1
            if i >= len(cmd):
                raise ValueError(tr("grimoire.spells.launchl.appedit", "A double quote isn't closed."))
        elif c == "'":
            end = cmd.find("'", i + 1)
            if end < 0:
                raise ValueError(tr("grimoire.spells.launchl.appedit", "A single quote isn't closed."))
            cur, have, i = cur + cmd[i + 1:end], True, end
        elif c == "\\" and i + 1 < len(cmd):
            cur, have, i = cur + cmd[i + 1], True, i + 1
        else:
            cur, have = cur + c, True
        i += 1
    if have:
        args.append(cur)
    return args


@dataclass
class Check:
    args: list[str] = field(default_factory=list)       # what runs, field codes as written (%u, %F, ...)
    error: str = ""                                     # can't be saved
    warnings: list[str] = field(default_factory=list)   # can be saved


def check_exec(cmd: str) -> Check:
    """Whether a command can go in Exec=, and what it runs."""
    c = Check()
    if not cmd.strip():
        c.error = tr("grimoire.spells.launchl.appedit", "The command can't be empty.")
        return c
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cmd):
        c.error = tr("grimoire.spells.launchl.appedit", "The command can't contain line breaks or other control "
                     "characters.")
        return c
    try:
        c.args = split_exec(cmd)
    except ValueError as err:
        c.error = str(err)
        return c
    if not c.args:
        c.error = tr("grimoire.spells.launchl.appedit", "The command can't be empty.")
        return c
    for code in re.findall(r"%(.)", re.sub(r"%%", "", cmd)):
        if code not in FIELD_CODES:
            c.warnings.append(tr("grimoire.spells.launchl.appedit", "%{code} isn't a field code menus know; write "
                                 "%% for a percent sign.").format(code=code))
            break
    # the program: after "env" and any NAME=value settings
    words = c.args[1:] if c.args[0] == "env" else c.args
    prog = next((a for a in words if not ("=" in a and a.split("=", 1)[0].isidentifier())), c.args[0])
    path = os.environ.get("PATH", "/usr/bin:/bin")
    path = f"{HOME}/.local/bin:{path}"
    if not (shutil.which(prog, path=path) or (os.path.isabs(prog) and os.access(prog, os.X_OK))):
        c.warnings.append(tr("grimoire.spells.launchl.appedit", "{program} isn't installed or isn't in your "
                             "PATH, so the app may not start.").format(program=prog))
    return c


# ---- apps ---------------------------------------------------------------------------------------------------------

@dataclass
class App:
    id: str
    name: str = ""                 # in the current language, as the menu shows it
    icon: str = ""
    exec: str = ""                 # unescaped (as split_exec reads it)
    hidden: bool = False
    dbus: bool = False             # DBusActivatable: Plasma starts it over D-Bus, Exec is only a fallback
    system: Path | None = None     # the system file it's based on
    user: Path | None = None       # the user's copy, if there is one
    edited: bool = False           # that copy is ours (X-Grimoire-Edited)
    keys: dict = field(default_factory=dict)

    @property
    def resettable(self) -> bool:
        return self.user is not None and (self.system is not None or self.edited)


def _lang_keys() -> list[str]:
    """Locale suffixes to look up, best first (fr_FR → fr_FR, fr)."""
    from grimoire import i18n
    code = i18n.current()
    code = {"pt": "pt_BR"}.get(code, code)
    return [k for k in dict.fromkeys([code, code.split("_")[0]]) if k and k != "en"]


def _localized(keys: dict, key: str) -> str:
    for lang in _lang_keys():
        if keys.get(f"{key}[{lang}]"):
            return keys[f"{key}[{lang}]"]
    return keys.get(key, "")


def _read(p: Path) -> str:
    if p.stat().st_size > MAX_SIZE:
        raise OSError(tr("grimoire.spells.launchl.appedit", "That desktop file is too big to be a menu entry."))
    return p.read_text(errors="replace")


def load(app_id: str) -> App:
    """An app's entry as the menu sees it (the user's copy wins). Raises LookupError when there's no such app."""
    if not valid_id(app_id):
        raise LookupError(tr("grimoire.spells.launchl.appedit", "“{id}” isn't an app id.").format(id=app_id))
    system, user = system_file(app_id), user_file(app_id)
    src = user or system
    if src is None:
        raise LookupError(tr("grimoire.spells.launchl.appedit", "No app called {id} is installed.").format(
            id=app_id))
    keys = read_group(_read(src))
    if not keys:
        raise LookupError(tr("grimoire.spells.launchl.appedit", "{id} isn't a menu entry.").format(id=app_id))
    return App(id=app_id, name=_unescape(_localized(keys, "Name")), icon=_unescape(_localized(keys, "Icon")),
               exec=_unescape(keys.get("Exec", "")),
               hidden=keys.get("NoDisplay", "").lower() == "true" or keys.get("Hidden", "").lower() == "true",
               dbus=keys.get("DBusActivatable", "").lower() == "true", system=system, user=user,
               edited=keys.get(MARK, "").lower() == "true", keys=keys)


def _clean(value: str) -> str:
    value = value.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(tr("grimoire.spells.launchl.appedit", "Names and icons can't contain line breaks."))
    return value


def save(app: App, name: str | None = None, icon: str | None = None, command: str | None = None,
         hidden: bool | None = None) -> Path:
    """Write the user's copy with the changed fields (None = unchanged); returns its path. System files are
    only read. Raises ValueError for values that can't go in a desktop file, OSError when writing fails."""
    sets, drop, remove = {}, set(), set()
    if name is not None and name.strip() != app.name:
        name = _clean(name)
        if not name:
            raise ValueError(tr("grimoire.spells.launchl.appedit", "The name can't be empty."))
        sets["Name"] = _escape(name)
        drop.add("Name")                                 # one name in every language: the one you chose
    if icon is not None and icon.strip() != app.icon:
        sets["Icon"] = _escape(_clean(icon))
        drop.add("Icon")
    if command is not None and command.strip() != app.exec:
        check = check_exec(command)
        if check.error:
            raise ValueError(check.error)
        sets["Exec"] = _escape(command.strip())
        if app.dbus:
            sets["DBusActivatable"] = "false"            # else Plasma starts it over D-Bus and skips Exec
    if hidden is not None and hidden != app.hidden:
        if hidden:
            sets["NoDisplay"] = "true"
        else:
            base = read_group(_read(app.system)) if app.system else {}
            if base.get("NoDisplay", "").lower() == "true":
                sets["NoDisplay"] = "false"
            else:
                remove.add("NoDisplay")
            remove.add("Hidden")
    src = app.user or app.system
    if src is None:
        raise OSError(tr("grimoire.spells.launchl.appedit", "The app's desktop file is gone."))
    if not sets and not remove:                          # nothing changed: no copy needed
        return app.user or src
    sets[MARK] = "true"
    text = edit_group(_read(src), sets, drop, remove)
    if app.system is not None and _same(text, _read(app.system)):
        # back to exactly the system entry (say, shown again after hiding): no copy needed any more
        if app.user is not None and app.edited:
            from grimoire.fsutil import trash
            trash(app.user)
        if app.user is None or app.edited:
            return app.system
    dest = app.user if app.user is not None else user_dir() / app.id
    _write(dest, text)
    return dest


def _same(ours: str, system: str) -> bool:
    """Whether our copy says the same as the system file, apart from our mark."""
    def norm(t):
        return [l.rstrip() for l in t.splitlines() if l.strip() and not l.startswith(MARK + "=")]
    return norm(ours) == norm(system)


def _write(dest: Path, text: str):
    """Atomically, so a crash never leaves half a menu entry (a symlink is replaced, its target left alone)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.grimoire-tmp")
    tmp.write_text(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, dest)


def hide(app_id: str, on: bool = True) -> Path:
    return save(load(app_id), hidden=on)


def reset(app_id: str) -> Path:
    """Move the user's copy to the Trash, so the system entry shows again. Returns the trashed path."""
    from grimoire.fsutil import trash
    app = load(app_id)
    if not app.resettable:
        raise LookupError(tr("grimoire.spells.launchl.appedit", "{id} has no changes to undo: it's your own "
                             "app, not a copy of a system one.").format(id=app_id) if app.user
                          else tr("grimoire.spells.launchl.appedit", "{id} has no changes to undo.").format(
            id=app_id))
    trash(app.user)
    return app.user


def edited() -> list[App]:
    """The apps Grimoire changed (copies marked X-Grimoire-Edited in the user's applications folder), by name."""
    out = []
    base = user_dir()
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*.desktop")):
        try:
            if p.stat().st_size > MAX_SIZE or MARK not in p.read_text(errors="replace"):
                continue
        except OSError:
            continue
        app_id = "-".join(p.relative_to(base).parts)
        try:
            app = load(app_id)
        except (LookupError, OSError):
            continue
        if app.edited:
            out.append(app)
    return sorted(out, key=lambda a: a.name.casefold())


def rebuild():
    """Tell KDE's app cache (and so every menu) about the change. Missing kbuildsycoca6 isn't an error."""
    try:
        RUN(["kbuildsycoca6"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass
