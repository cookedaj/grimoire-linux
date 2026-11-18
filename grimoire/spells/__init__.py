# SPDX-License-Identifier: GPL-3.0-or-later
"""Registry of spells (tools) shown in Grimoire. Add new spells to SPELLS."""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from grimoire.i18n import tr, tr_noop

if TYPE_CHECKING:               # background commands (alert checks, auto-tidy) import spells without loading Qt
    from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class Spell:
    id: str
    name: str
    tagline: str
    page: Callable[[], "QWidget"]
    icon: str                       # glyph name (grimoire/glyphs.py)
    status: Callable[[], str] = lambda: ""


def _mural():
    from grimoire.spells.mural.page import MuralPage
    return MuralPage()


def _sightc():
    from grimoire.spells.sightc.page import SightCPage
    return SightCPage()


def _mural_status() -> str:
    from grimoire.spells.mural.screens import load_state
    state = load_state()
    names = {"lock": tr("grimoire.spells", "Lock"), "splash": tr("grimoire.spells", "Splash"),
             "login": tr("grimoire.spells", "Login"), "boot": tr("grimoire.spells", "Boot"),
             "taskbar": tr("grimoire.spells", "Taskbar"), "terminal": tr("grimoire.spells", "Terminal"),
             "fonts": tr("grimoire.spells", "Fonts"), "cursor": tr("grimoire.spells", "Cursor"),
             "colors": tr("grimoire.spells", "Colors"), "style": tr("grimoire.spells", "Style")}
    bits = [f"{label} · {str(state[k].get('design')).removeprefix('store:').split(':')[-1].replace('_', ' ').title()}"
            for k, label in names.items() if isinstance(state.get(k), dict) and state[k].get('design')]
    from grimoire.spells.mural.looks import active_name
    look = active_name()
    bits = ([tr("grimoire.spells", "Look") + f" · {look}"] if look else []) + bits
    return "   ".join(bits[:6]) or tr("grimoire.spells", "Nothing applied yet")


def _sightc_status() -> str:
    from grimoire.spells.sightc import overlay
    return tr("grimoire.spells", "Crosshair on · Ctrl+Alt+X hides it") if overlay.running_pid() \
        else tr("grimoire.spells", "Crosshair off")


def _vaultl():
    from grimoire.spells.vaultl.page import VaultLPage
    return VaultLPage()


def _default_file_manager() -> bool:
    """Is VaultL what opens folders? Read from the user's mimeapps.list (no process started for a status line)."""
    import configparser
    import os
    from pathlib import Path
    for f in (Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "mimeapps.list",):
        cp = configparser.RawConfigParser(strict=False, interpolation=None)
        try:
            cp.read(f, encoding="utf-8")
            first = cp.get("Default Applications", "inode/directory", fallback="").split(";")[0].strip()
        except (configparser.Error, OSError, UnicodeDecodeError):
            continue
        if first:
            return first.startswith(("grimoire-vaultl", "grimoire-filel"))
    return False


def _vaultl_status() -> str:
    from grimoire.spells.vaultl import cli, tidy
    moved = sum(1 for e in tidy.history(2000) if e["action"] == "move")
    return " · ".join([*([tr("grimoire.spells", "Default file manager")] if _default_file_manager() else []),
                       tr("grimoire.spells", "Auto-tidy on") if cli.timer_active()
                       else tr("grimoire.spells", "Auto-tidy off"),
                       tr("grimoire.spells", "%n file(s) sorted so far", n=moved)])


def _optimizel():
    from grimoire.spells.optimizel.page import OptimizeLPage
    return OptimizeLPage()


def _optimizel_status() -> str:
    from grimoire.spells.optimizel import tweaks
    saved = tweaks.load_saved()
    on = sum(t.is_on() for t in tweaks.TWEAKS)
    waiting = sum(bool(tweaks.pending_note(t, saved)) for t in tweaks.TWEAKS)
    text = tr("grimoire.spells", "{on} of {total} optimizations on").format(on=on, total=len(tweaks.TWEAKS))
    return text + (" · " + tr("grimoire.spells", "restart to finish {n}").format(n=waiting) if waiting else "")


def _systeml():
    from grimoire.spells.systeml.page import SystemLPage
    return SystemLPage()


def _systeml_status() -> str:
    import psutil
    from grimoire.spells.systeml import alerts
    mem = psutil.virtual_memory()
    return " · ".join([
        tr("grimoire.spells", "CPU {pct}%").format(pct=f"{psutil.cpu_percent(interval=0.1):.0f}"),
        tr("grimoire.spells", "RAM {used} of {total} GB").format(used=f"{(mem.total - mem.available) / 2**30:.1f}",
                                                                 total=f"{mem.total / 2**30:.0f}"),
        tr("grimoire.spells", "Alerts on") if alerts.enabled() else tr("grimoire.spells", "Alerts off")])


def _terminall():
    from grimoire.spells.terminall.page import TerminalLPage
    return TerminalLPage()


def _terminall_status() -> str:
    from grimoire.spells.terminall.page import status
    return status()


def _shotl():
    from grimoire.spells.shotl.page import ShotLPage
    return ShotLPage()


def _shotl_status() -> str:
    from grimoire.spells.shotl import shots
    return shots.status()


def _launchl():
    from grimoire.spells.launchl.page import LaunchLPage
    return LaunchLPage()


def _launchl_status() -> str:
    from grimoire.spells.launchl import panel
    return panel.status()


SPELLS = [
    Spell("mural", "MuraL",
          tr_noop("grimoire.spells", "Every screen and surface: wallpaper, lock, login, boot, taskbar, windows, "
                                     "colors, icons, fonts, cursor, terminal, plus the community store"),
          _mural, "mural", _mural_status),
    Spell("sightc", "SightsL",
          tr_noop("grimoire.spells", "Crosshair overlay above every game, click-through"),
          _sightc, "sight", _sightc_status),
    Spell("vaultl", "VaultL",
          tr_noop("grimoire.spells", "Your file manager with tidying built in: places, drives, previews, trash with "
                                     "restore, plus auto-sorted Downloads, undo, big files and duplicates"),
          _vaultl, "vault", _vaultl_status),
    Spell("optimizel", "OptimizeL",
          tr_noop("grimoire.spells", "Tunes the PC for speed: CPU, memory, boot, network, startup apps and games. "
                                     "Every tweak is a switch that survives restarts and turns back off cleanly"),
          _optimizel, "optimize", _optimizel_status),
    Spell("systeml", "SystemL",
          tr_noop("grimoire.spells", "Your system monitor: live graphs, processes, per-app history, services, startup "
                                     "apps, disks and background alerts"),
          _systeml, "system", _systeml_status),
    Spell("terminall", "TerminalL",
          tr_noop("grimoire.spells", "Your terminal: tabs and splits, full color, scrollback search, profiles and "
                                     "saved commands, opening right in VaultL's folder"),
          _terminall, "terminall", _terminall_status),
    Spell("shotl", "ShotL",
          tr_noop("grimoire.spells", "Screenshots and screen recordings: region, window or screen, a black & white "
                                     "editor to mark them up, and a gallery of every one"),
          _shotl, "shot", _shotl_status),
    Spell("launchl", "LaunchL",
          tr_noop("grimoire.spells", "Your app launcher in Kickoff's place: favorites, categories, places, search with "
                                     "files, sums and Grimoire's spells, and the leave buttons. Meta opens it"),
          _launchl, "launchl", _launchl_status),
]


def _focusl():
    from grimoire.spells.focusl.page import FocusLPage
    return FocusLPage()


def _focusl_status() -> str:
    from grimoire.spells.focusl import store
    return store.status_line()


SPELLS.append(Spell("focusl", "FocusL",
                    tr_noop("grimoire.spells", "A focus timer in rounds with breaks: Do Not Disturb, no crosshair and "
                                               "your distracting apps and sites kept away while you focus, plus your "
                                               "streak and stats"),
                    _focusl, "focus", _focusl_status))


def _netl():
    from grimoire.spells.netl.page import NetLPage
    return NetLPage()


def _netl_status() -> str:
    from grimoire.spells.netl.probe import status_line
    return status_line()


SPELLS.append(Spell("netl", "NetL",
                    tr_noop("grimoire.spells", "Your network: live traffic per interface and per app, connections, "
                                               "Wi-Fi and VPN switches, and daily and monthly usage"),
                    _netl, "net", _netl_status))


def _gamel():
    from grimoire.spells.gamel.page import GameLPage
    return GameLPage()


def _gamel_status() -> str:
    from grimoire.spells.gamel.library import status_line
    return status_line()


SPELLS.append(Spell("gamel", "GameL",
                    tr_noop("grimoire.spells", "One library for your Steam, Heroic and Lutris games: covers, search, "
                                               "playtime and a Play button, plus a black & white MangoHud overlay and "
                                               "Performance mode, both switched by hand"),
                    _gamel, "game", _gamel_status))


def _updatel():
    from grimoire.spells.updatel.page import UpdateLPage
    return UpdateLPage()


def _updatel_status() -> str:
    from grimoire.spells.updatel.daily import status_line
    return status_line()


SPELLS.append(Spell("updatel", "UpdateL",
                    tr_noop("grimoire.spells", "Every update in one place: system packages, Flatpaks, snaps and "
                                               "firmware, with changelogs, a preview of anything that would be "
                                               "removed, and an optional daily check"),
                    _updatel, "updatel", _updatel_status))


def _audiol():
    from grimoire.spells.audiol.page import AudioLPage
    return AudioLPage()


def _audiol_status() -> str:
    from grimoire.spells.audiol.pw import status_line
    return status_line()


SPELLS.append(Spell("audiol", "AudioL",
                    tr_noop("grimoire.spells", "Your sound on PipeWire: outputs and inputs, each app's volume and "
                                               "device, a system-wide equalizer with presets, and sound card profiles"),
                    _audiol, "audio", _audiol_status))


def _widgetl():
    from grimoire.spells.widgetl.page import WidgetLPage
    return WidgetLPage()


def _widgetl_status() -> str:
    from grimoire.spells.widgetl import widgets
    return widgets.status()


SPELLS.append(Spell("widgetl", "WidgetL",
                    tr_noop("grimoire.spells", "Desktop widgets in black and white: a clock, your system's readings, "
                                               "the weather and what's playing"),
                    _widgetl, "widgets", _widgetl_status))


def _glyphl():
    from grimoire.spells.glyphl.page import GlyphLPage
    return GlyphLPage()


def _glyphl_status() -> str:
    from grimoire.spells.glyphl import store
    return store.status_line()


SPELLS.append(Spell("glyphl", "GlyphL",
                    tr_noop("grimoire.spells", "Emoji, symbols and every Unicode character on a hotkey: search in your "
                                               "language, skin tones, favorites and a full Unicode block browser"),
                    _glyphl, "glyphl", _glyphl_status))


def _cloudl():
    from grimoire.spells.cloudl.page import CloudLPage
    return CloudLPage()


def _cloudl_status() -> str:
    from grimoire.spells.cloudl.rclone import status_line
    return status_line()


SPELLS.append(Spell("cloudl", "CloudL",
                    tr_noop("grimoire.spells", "Google Drive, OneDrive and Dropbox as folders on your PC through "
                                               "rclone: sign in from your browser, mount, see the space left and "
                                               "what is still uploading, and open them in VaultL"),
                    _cloudl, "cloud", _cloudl_status))


def _viewl():
    from grimoire.spells.viewl.page import ViewLPage
    return ViewLPage()


def _viewl_status() -> str:
    from grimoire.spells.viewl.images import status_line
    return status_line()


SPELLS.append(Spell("viewl", "ViewL",
                    tr_noop("grimoire.spells", "Your pictures: a fast thumbnail grid, a full view with zoom, turns, "
                                               "slideshow and EXIF info, plus rename, Trash and set as wallpaper"),
                    _viewl, "viewl", _viewl_status))


def _storel():
    from grimoire.spells.storel.page import StoreLPage
    return StoreLPage()


def _storel_status() -> str:
    from grimoire.spells.storel.library import status_line
    return status_line()


SPELLS.append(Spell("storel", "StoreL",
                    tr_noop("grimoire.spells", "Install and remove apps from Flathub, Ubuntu's archive and the Snap "
                                               "Store: search, screenshots, a preview of every change, and each "
                                               "Flatpak's permissions"),
                    _storel, "storel", _storel_status))


def _readl():
    from grimoire.spells.readl.page import ReadLPage
    return ReadLPage()


def _readl_status() -> str:
    from grimoire.spells.readl.library import status_line
    return status_line()


SPELLS.append(Spell("readl", "ReadL",
                    tr_noop("grimoire.spells", "A quiet reader for PDFs, EPUB books, Markdown and text: covers, "
                                               "contents, search, bookmarks, night and paper pages, and it "
                                               "remembers where you stopped"),
                    _readl, "read", _readl_status))


def _phonel():
    from grimoire.spells.phonel.page import PhoneLPage
    return PhoneLPage()


def _phonel_status() -> str:
    from grimoire.spells.phonel.kdc import status_line
    return status_line()


SPELLS.append(Spell("phonel", "PhoneL",
                    tr_noop("grimoire.spells", "Your phone on this PC through KDE Connect: send files, ring it, "
                                               "share the clipboard, browse its files, read and dismiss its "
                                               "notifications, text messages, media and commands"),
                    _phonel, "phone", _phonel_status))


def _notel():
    from grimoire.spells.notel.page import NoteLPage
    return NoteLPage()


def _notel_status() -> str:
    from grimoire.spells.notel.store import status_line
    return status_line()


SPELLS.append(Spell("notel", "NoteL",
                    tr_noop("grimoire.spells", "Markdown notes and a text editor in one: a notes folder with search, "
                                               "tags, [[links]] and backlinks, a live preview, tabs, and syntax "
                                               "colors for code"),
                    _notel, "notel", _notel_status))


def _playl():
    from grimoire.spells.playl.page import PlayLPage
    return PlayLPage()


def _playl_status() -> str:
    from grimoire.spells.playl.media import status_line
    return status_line()


SPELLS.append(Spell("playl", "PlayL",
                    tr_noop("grimoire.spells", "Videos and music: a queue you can drag around, subtitles and audio "
                                               "tracks, resume where you stopped, your music library with covers, "
                                               "and Plasma's media controls"),
                    _playl, "playl", _playl_status))


def _settingl():
    from grimoire.spells.settingl.page import SettingLPage
    return SettingLPage()


def _settingl_status() -> str:
    from grimoire.spells.settingl.page import status
    return status()


SPELLS.append(Spell("settingl", "SettingL",
                    tr_noop("grimoire.spells", "KDE's settings in black and white: displays, sound, network, "
                                               "Bluetooth, mouse, keyboard, power, date, language, default apps and "
                                               "more, with every other KDE module one search away"),
                    _settingl, "settingl", _settingl_status))


def _uninstallerl():
    from grimoire.spells.cleanupl.view import RemovalPage
    return RemovalPage("all")


def _uninstallerl_status() -> str:
    from grimoire.spells.cleanupl.engine import status_line
    return status_line("all")


SPELLS.append(Spell("uninstallerl", "UninstallerL",
                    tr_noop("grimoire.spells", "Uninstall any app (packages, Flatpaks, snaps, AppImages, home "
                                               "installs) or the ones Grimoire replaces, then sweep up their "
                                               "settings, caches and autostart entries"),
                    _uninstallerl, "uninstallerl", _uninstallerl_status))


def _passwordl():
    from grimoire.spells.passwordl.page import PasswordLPage
    return PasswordLPage()


def _passwordl_status() -> str:
    from grimoire.spells.passwordl import vault
    return tr("grimoire.spells", "Vault ready · locked") if vault.exists() else tr("grimoire.spells", "No vault yet")


SPELLS.append(Spell("passwordl", "PasswordL",
                    tr_noop("grimoire.spells", "Your passwords, cards, notes and two-factor codes in an encrypted "
                                               "vault on this PC: generator, security audit, import from other "
                                               "password managers"),
                    _passwordl, "passwordl", _passwordl_status))


def _calculatorl():
    from grimoire.spells.calculatorl.page import CalculatorLPage
    return CalculatorLPage()


def _calculatorl_status() -> str:
    from grimoire.spells.calculatorl.page import status_line
    return status_line()


SPELLS.append(Spell("calculatorl", "CalculatorL",
                    tr_noop("grimoire.spells", "A calculator in black and white: standard and scientific, history, "
                                               "and conversions of units and currencies, all from the keyboard"),
                    _calculatorl, "calculatorl", _calculatorl_status))
