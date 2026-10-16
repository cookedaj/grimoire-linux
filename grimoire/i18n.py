# SPDX-License-Identifier: GPL-3.0-or-later
"""Languages: which one is on, its Qt catalogs, right-to-left layout and per-script fonts.

Strings are wrapped with tr(context, text) (QCoreApplication.translate underneath, so it also works in Qt-free
modules and returns English there). The context is the dotted module name ("grimoire.app",
"grimoire.spells.vaultl.page"), and the context says which catalog holds the string: grimoire.spells.<area>.* goes to
translations/<area>/, everything else to translations/core/. scripts/i18n.py extracts the strings (its own ast
reader: lupdate's Python parser can't mark plurals) and builds the .qm files, which are committed so installs need
no Qt tools. A language change needs a restart: install() runs once, in style_app(), before any window exists.
"""
import json
import os
import re
from pathlib import Path

from grimoire.paths import CONFIG_ROOT, ROOT

# code → the language's own name (what the pickers show)
LANGUAGES = {"en": "English", "zh_CN": "中文（简体）", "hi": "हिन्दी", "es": "Español", "fr": "Français",
             "ar": "العربية", "bn": "বাংলা", "pt": "Português (Brasil)", "ru": "Русский", "ur": "اردو"}
RTL = {"ar", "ur"}
QT_LOCALE = {"pt": "pt_BR"}                      # our code → Qt's locale / qtbase catalog name when they differ
AREAS = ("core", "mural", "sightc", "vaultl", "optimizel", "systeml", "terminall", "shotl", "launchl", "focusl",
         "netl", "gamel", "updatel", "audiol", "widgetl", "glyphl")
         "netl", "gamel", "updatel", "audiol", "widgetl", "cloudl")
TRANSLATIONS = ROOT / "translations"
MACHINE = CONFIG_ROOT / "language"               # the last choice on this PC: the sign-in screen and guests follow it
SANS, MONO = "IBM Plex Sans", "IBM Plex Mono"
# fallbacks for the scripts IBM Plex Sans lacks; the current language's own script goes first (CJK must be the
# Simplified Chinese cut, not the Japanese one fontconfig picks). Urdu: Naskh in the dense UI, where Nastaliq's
# 2.5x line height overflows rows and fields and its dots blur at 13px; Nastaliq in the big headings (URDU_QSS).
URDU_QSS = """
QLabel#Hero, QLabel#Title, QLabel#PageHeading, QLabel#SectionTitle {
    font-family: "IBM Plex Sans", "Noto Nastaliq Urdu"; }
"""
SCRIPT_FONTS = {"ar": ["IBM Plex Sans Arabic", "Noto Sans Arabic", "Noto Naskh Arabic"],
                "ur": ["Noto Naskh Arabic UI", "Noto Naskh Arabic", "IBM Plex Sans Arabic"],
                "hi": ["IBM Plex Sans Devanagari", "Noto Sans Devanagari"],
                "bn": ["Noto Sans Bengali"],
                "zh_CN": ["Noto Sans CJK SC"]}
MONO_FONTS = {"zh_CN": ["Noto Sans Mono CJK SC"]}

_loaded = None                                   # the language install() set up in this process
_keep = []                                       # the translators (Qt holds them by pointer only)
_bare: dict = {"app": None, "areas": set(), "translators": []}   # install_catalogs(): what it made and loaded


def tr(context: str, text: str, disambiguation: str | None = None, n: int = -1) -> str:
    """Translate text; n picks the plural form of a "%n" text. Context and text must be string literals, so
    scripts/i18n.py can find them (use tr_noop for texts defined before the app exists)."""
    try:
        from PySide6.QtCore import QCoreApplication
    except ImportError:                          # no Qt in this process: English as written
        return text.replace("%n", str(n)) if n >= 0 else text
    return QCoreApplication.translate(context, text, disambiguation, n)


def tr_noop(context: str, text: str) -> str:
    """Marks a text for extraction without translating it yet (module-level tables, made before the catalogs
    load); translate it where it's shown with tr(the same context, value)."""
    return text


def _from_env() -> str:
    """The desktop's language (LANGUAGE, LC_ALL, LC_MESSAGES, LANG) when it's one of ours, else ""."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for item in os.environ.get(var, "").split(":"):
            code = re.split(r"[.@]", item)[0]
            if not code or code in ("C", "POSIX"):
                continue
            if code in LANGUAGES:
                return code
            base = code.split("_")[0]
            if base == "zh":
                return "zh_CN" if code in ("zh", "zh_CN", "zh_SG") else ""
            if base in LANGUAGES:
                return base
            if var != "LANGUAGE":
                return ""
    return ""


def current() -> str:
    """GRIMOIRE_LANG (for tests), else this profile's choice, else the last choice on this PC, else the desktop's
    language when we have it, else English."""
    env = os.environ.get("GRIMOIRE_LANG", "")
    if env in LANGUAGES:
        return env
    from grimoire import paths                   # read late, and not through prefs: a module that binds CONFIG
    try:                                         # before the sign-in gate would force a restart (paths.activate)
        code = json.loads((paths.CONFIG / "settings.json").read_text()).get("locale")
    except (OSError, ValueError, AttributeError):
        code = ""
    if code in LANGUAGES:
        return code
    try:
        code = MACHINE.read_text().strip()
    except OSError:
        code = ""
    return code if code in LANGUAGES else _from_env() or "en"


def choose(code: str):
    """Save a language choice (this profile and this PC); it applies from the next start."""
    if code not in LANGUAGES:
        raise ValueError(code)
    from grimoire import prefs
    prefs.save(locale=code)
    tmp = MACHINE.with_suffix(".tmp")
    tmp.write_text(code + "\n")
    tmp.replace(MACHINE)


def loaded() -> str:
    """The language this process runs in ("" before install)."""
    return _loaded or ""


def needs_restart() -> bool:
    return bool(_loaded) and current() != _loaded


def rtl(code: str | None = None) -> bool:
    return (code or _loaded or current()) in RTL


def catalogs(code: str) -> list[Path]:
    """This language's compiled catalogs that exist (one per area; a missing one just stays English)."""
    return [TRANSLATIONS / area / f"{code}.qm" for area in AREAS if (TRANSLATIONS / area / f"{code}.qm").is_file()]


def fonts(code: str) -> tuple[list[str], list[str]]:
    """(sans, mono) fallback families for a language: its own script first, then the other scripts we ship, so a
    language name in another script (the language picker) still draws with a proper font."""
    order = [code] + [c for c in SCRIPT_FONTS if c != code and not (c in RTL and code in RTL)]
    sans = [f for c in order for f in SCRIPT_FONTS.get(c, [])]
    mono = MONO_FONTS.get(code, []) + sans
    return list(dict.fromkeys(sans)), list(dict.fromkeys(mono))


def install(app, code: str | None = None) -> str:
    """Load the language into app (translators, Qt's own dialogs, direction, font fallbacks). Call once, before
    any widget is made; returns the language code used."""
    global _loaded
    from PySide6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator
    from PySide6.QtGui import QFont
    code = code if code in LANGUAGES else current()
    qt_code = QT_LOCALE.get(code, code)
    QLocale.setDefault(QLocale(qt_code))
    for t in _keep:
        app.removeTranslator(t)
    _keep.clear()
    qt_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    for qm in [qt_dir / f"qtbase_{qt_code}.qm"] * (code != "en") + catalogs(code):
        t = QTranslator(app)
        if t.load(str(qm)):
            app.installTranslator(t)
            _keep.append(t)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if code in RTL else Qt.LayoutDirection.LeftToRight)
    sans, mono = fonts(code)
    QFont.removeSubstitutions(SANS)
    QFont.removeSubstitutions(MONO)
    QFont.insertSubstitutions(SANS, sans)
    QFont.insertSubstitutions(MONO, mono)
    _loaded = code
    return code


def install_catalogs(areas=None) -> str:
    """Translations for a process without windows (timers, CLI commands, background runners): tr() needs a
    QCoreApplication and the catalogs, which install() only loads for a QApplication. Uses the running
    QCoreApplication or makes a bare one (QtCore only: no display needed), loads core plus the given areas (None: every
    area) for current() and sets QLocale's default, so tr() and fsutil.human() speak the language. Call again to add
    areas; never in a process that will make a QApplication later. Returns the language code ("en" without PySide6:
    tr() then gives English as written)."""
    global _loaded
    try:
        from PySide6.QtCore import QCoreApplication, QLocale, QTranslator
    except ImportError:
        return "en"
    if _keep:                                    # install() already loaded every area for a window
        return _loaded
    app = QCoreApplication.instance() or QCoreApplication(["grimoire"])
    _bare["app"] = app
    code = _loaded or current()
    QLocale.setDefault(QLocale(QT_LOCALE.get(code, code)))
    wanted = set(AREAS) if areas is None else {"core", *areas}
    for qm in catalogs(code):
        if qm.parent.name in wanted - _bare["areas"]:
            t = QTranslator(app)
            if t.load(str(qm)) and app.installTranslator(t):
                _bare["translators"].append(t)
    _bare["areas"] |= wanted
    _loaded = code
    return code


# bidi isolates: a path, number or version inside a right-to-left sentence keeps its own order (without them
# "/home/x/a b" or "v1.2 (3)" come out shuffled). Text is returned unchanged in left-to-right languages.
LRI, FSI, PDI = "\u2066", "\u2068", "\u2069"


def ltr(text) -> str:
    """text forced left to right (paths, numbers with units, versions, commands, key names) in an RTL language."""
    text = str(text)
    return f"{LRI}{text}{PDI}" if text and rtl() else text


def isolate(text) -> str:
    """text laid out by its own first letter (names, titles, anything a user or another program wrote) in an RTL
    language, so it can't pull the sentence around it into its direction."""
    text = str(text)
    return f"{FSI}{text}{PDI}" if text and rtl() else text


# Arabic (+ Urdu letters), Devanagari, Bengali
JOINED = re.compile("[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff\u0900-\u09ff]")
JOINED_LANGS = {"ar", "ur", "hi", "bn"}


def spacing(text: str, px: float) -> float:
    """Letter spacing for a label: none for scripts whose letters join or stack (spacing breaks the words apart)."""
    return 0 if JOINED.search(text) else px


def qss(css: str) -> str:
    """A stylesheet without letter-spacing when the language's script joins its letters."""
    code = _loaded or current()
    return re.sub(r"letter-spacing:\s*[\d.]+px;", "", css) if code in JOINED_LANGS else css


def mirrored(name: str) -> bool:
    """Glyphs that point along the reading direction (back/forward) flip in a right-to-left language."""
    return name in ("back", "forward") and bool(_loaded) and _loaded in RTL
