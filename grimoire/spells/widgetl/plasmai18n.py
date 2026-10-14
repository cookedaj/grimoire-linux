# SPDX-License-Identifier: GPL-3.0-or-later
"""Translations of Grimoire's Plasma widgets (LaunchL and WidgetL's four). Their QML runs inside plasmashell, where
Grimoire's Qt catalogs aren't loaded: Plasma translates an applet's i18n()/i18nc() with the gettext domain
"plasma_applet_<plugin id>" and finds the .mo files in the package's contents/locale/<lang>/LC_MESSAGES/. The .po
sources live in translations/<area>/plasma/<lang>.po (one per area and language, shared by that area's packages).
Python's gettext reads the same .mo files for WidgetL's previews (preview.py), so they show the language too.
No Qt here and no gettext tools needed (this system has no xgettext/msgfmt): extraction and .mo writing are ours.

    python3 -m grimoire.spells.widgetl.plasmai18n update     QML strings → translations/<area>/plasma/<lang>.po
    python3 -m grimoire.spells.widgetl.plasmai18n release    .po → each package's .mo + metadata.json names
    python3 -m grimoire.spells.widgetl.plasmai18n stats      translated / unfinished per area and language
    python3 -m grimoire.spells.widgetl.plasmai18n check      %1-style placeholders that differ from the English
"""
import gettext
import json
import re
import struct
import sys
from pathlib import Path

from grimoire.paths import ROOT

LANGS = ("zh_CN", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur")       # grimoire.i18n.LANGUAGES minus English
KDE_CODE = {"pt": "pt_BR"}                     # our code → KDE's locale folder (our Portuguese is Brazilian)
PACKAGES = {"launchl": ["com.cookedaj.grimoire.launchl"],
            "widgetl": [f"com.cookedaj.grimoire.widget.{w}" for w in ("clock", "system", "weather", "nowplaying")]}
META = "metadata.json"                         # its Name/Description get translated too (msgctxt "metadata.json …")
_CALL = re.compile(r"(?<![\w.])(i18nc?)\(\s*")
_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_ESC = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'"}


def kde(code: str) -> str:
    return KDE_CODE.get(code, code)


def package_dir(plugin: str) -> Path:
    return ROOT / "plasma" / plugin


def domain(plugin: str) -> str:
    return "plasma_applet_" + plugin


def mo_path(plugin: str, code: str, root: Path | None = None) -> Path:
    return (root or package_dir(plugin)) / "contents" / "locale" / kde(code) / "LC_MESSAGES" / f"{domain(plugin)}.mo"


def po_path(area: str, code: str) -> Path:
    return ROOT / "translations" / area / "plasma" / f"{code}.po"


# ---- extraction ---------------------------------------------------------------------------------------------------

def _unescape(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: _ESC.get(m.group(1), m.group(1)), s)


def _literals(text: str, pos: int, count: int) -> list[str] | None:
    """count string literals separated by commas from pos (each may be "a" + "b"), or None when one isn't a literal."""
    out = []
    for i in range(count):
        parts = []
        while True:
            m = _STRING.match(text, pos)
            if not m:
                return None
            parts.append(_unescape(m.group(1)))
            pos = m.end()
            plus = re.match(r"\s*\+\s*", text[pos:])
            if plus and _STRING.match(text, pos + plus.end()):
                pos += plus.end()
                continue
            break
        out.append("".join(parts))
        if i < count - 1:
            comma = re.match(r"\s*,\s*", text[pos:])
            if not comma:
                return None
            pos += comma.end()
    return out


def _code_only(text: str) -> str:
    """text with its // and /* */ comments blanked out (same length, so offsets still match). Strings and regex
    literals are skipped over, so a "//" or a quote inside them doesn't count."""
    out, i, n = list(text), 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            i += 1
            while i < n and text[i] != c:
                i += 2 if text[i] == "\\" else 1
        elif text.startswith("//", i) or text.startswith("/*", i):
            end = text.find("\n", i) if text[i + 1] == "/" else text.find("*/", i) + 2
            end = n if end < i else end
            out[i:end] = [ch if ch == "\n" else " " for ch in text[i:end]]
            i = end
            continue
        elif c == "/" and text[:i].rstrip()[-1:] in tuple("(,=:[!&|?{};") + ("",):
            i += 1                                       # a regex literal: up to its closing / outside a [class]
            klass = False
            while i < n and (text[i] != "/" or klass) and text[i] != "\n":
                klass = (klass and text[i] != "]") or (not klass and text[i] == "[")
                i += 2 if text[i] == "\\" else 1
        i += 1
    return "".join(out)


def extract(plugin: str) -> list[tuple[str, str]]:
    """(context, text) of every i18n("text") / i18nc("context", "text") in a package's QML, in order, plus its
    metadata.json Name and Description."""
    found = []
    for qml in sorted((package_dir(plugin) / "contents").rglob("*.qml")):
        text = _code_only(qml.read_text())
        for m in _CALL.finditer(text):
            got = _literals(text, m.end(), 2 if m.group(1) == "i18nc" else 1)
            if got is None:
                print(f"{qml.relative_to(ROOT)}: {m.group(1)}() without a string literal at offset {m.start()}",
                      file=sys.stderr)
                continue
            found.append(("", got[0]) if len(got) == 1 else (got[0], got[1]))
    meta = json.loads((package_dir(plugin) / META).read_text())["KPlugin"]
    for key in ("Name", "Description"):
        found.append((f"{META} {key}", meta[key]))
    return list(dict.fromkeys(found))


# ---- .po files ----------------------------------------------------------------------------------------------------

def _po_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


def read_po(path: Path) -> dict:
    """{(context, msgid): msgstr} of a .po file (only the subset we write: no plurals, no obsolete entries)."""
    entries, cur, field = {}, {}, None
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return {}

    def flush():
        if "msgid" in cur and cur["msgid"]:
            entries[(cur.get("msgctxt", ""), cur["msgid"])] = cur.get("msgstr", "")
        cur.clear()
    for line in lines + [""]:
        line = line.strip()
        if not line or line.startswith("#"):
            if not line:
                flush()
            continue
        m = re.match(r"(msgctxt|msgid|msgstr)\s+(\".*\")$", line)
        if m:
            if m.group(1) == "msgctxt" or (m.group(1) == "msgid" and "msgid" in cur):
                flush()
            field = m.group(1)
            cur[field] = _unescape(m.group(2)[1:-1])
        elif line.startswith('"') and field:
            cur[field] += _unescape(line[1:-1])
    return entries


def write_po(path: Path, code: str, msgs: list[tuple[str, str]], where: dict, old: dict):
    out = [f"# Grimoire Linux's Plasma widgets, {code}. SPDX-License-Identifier: GPL-3.0-or-later",
           'msgid ""', 'msgstr ""', '"Content-Type: text/plain; charset=UTF-8\\n"', f'"Language: {kde(code)}\\n"', ""]
    for ctx, msgid in msgs:
        out.append(f"#: {' '.join(where[(ctx, msgid)])}")
        if ctx:
            out.append(f"msgctxt {_po_quote(ctx)}")
        out += [f"msgid {_po_quote(msgid)}", f"msgstr {_po_quote(old.get((ctx, msgid), ''))}", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out))


def write_mo(path: Path, catalog: dict):
    """A GNU .mo file of {(context, msgid): msgstr} (untranslated entries left out)."""
    items = {"": "Content-Type: text/plain; charset=UTF-8\n"}
    for (ctx, msgid), msgstr in catalog.items():
        if msgstr:
            items[(ctx + "\x04" if ctx else "") + msgid] = msgstr
    keys = sorted(items, key=lambda k: k.encode())
    ids, strs = [k.encode() for k in keys], [items[k].encode() for k in keys]
    n = len(keys)
    start = 7 * 4 + n * 16
    offsets, data = [], b""
    for blob in ids + strs:
        offsets.append((len(blob), start + len(data)))
        data += blob + b"\0"
    head = struct.pack("<7I", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    table = b"".join(struct.pack("<2I", *o) for o in offsets)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(head + table + data)


# ---- runtime (the previews) ---------------------------------------------------------------------------------------

def translator(plugin: str, code: str, root: Path | None = None):
    """(i18n, i18nc) functions with Plasma's %1..%9 substitution, from a package's .mo for language code."""
    try:
        with open(mo_path(plugin, code, root), "rb") as f:
            cat = gettext.GNUTranslations(f)
    except OSError:
        cat = gettext.NullTranslations()

    def show(v):                       # numbers as KLocalizedString writes them ('g': 12.0 → 12)
        return f"{v:g}" if isinstance(v, float) else str(v)

    def fill(text, args):
        return re.sub(r"%(\d)", lambda m: show(args[int(m.group(1)) - 1]) if 0 < int(m.group(1)) <= len(args)
                      else m.group(0), text)
    return (lambda text, *args: fill(cat.gettext(text), args),
            lambda ctx, text, *args: fill(cat.pgettext(ctx, text), args))


# ---- commands -----------------------------------------------------------------------------------------------------

def _area_msgs(area: str) -> tuple[list, dict]:
    msgs, where = [], {}
    for plugin in PACKAGES[area]:
        for key in extract(plugin):
            if key not in where:
                msgs.append(key)
            where.setdefault(key, []).append(plugin.rsplit(".", 1)[-1])
    return msgs, where


def update():
    for area in PACKAGES:
        msgs, where = _area_msgs(area)
        for code in LANGS:
            write_po(po_path(area, code), code, msgs, where, read_po(po_path(area, code)))
        print(f"{area}: {len(msgs)} strings")


def release():
    for area, plugins in PACKAGES.items():
        for plugin in plugins:
            keys = extract(plugin)
            meta_path = package_dir(plugin) / META
            meta = json.loads(meta_path.read_text())
            for code in LANGS:
                po = read_po(po_path(area, code))
                write_mo(mo_path(plugin, code), {k: po.get(k, "") for k in keys if not k[0].startswith(META)})
                for key in ("Name", "Description"):
                    value = po.get((f"{META} {key}", meta["KPlugin"][key]), "")
                    if value and value != meta["KPlugin"][key]:
                        meta["KPlugin"][f"{key}[{kde(code)}]"] = value
                    else:
                        meta["KPlugin"].pop(f"{key}[{kde(code)}]", None)
            meta["KPlugin"] = dict(sorted(meta["KPlugin"].items(), key=lambda kv: (kv[0].split("[")[0], kv[0])))
            meta_path.write_text(json.dumps(meta, indent=4, ensure_ascii=False) + "\n")
        print(f"{area}: {len(plugins)} package(s) × {len(LANGS)} languages")


def stats() -> int:
    unfinished = 0
    for area in PACKAGES:
        msgs, _ = _area_msgs(area)
        for code in LANGS:
            po = read_po(po_path(area, code))
            done = sum(bool(po.get(k)) for k in msgs)
            unfinished += len(msgs) - done
            print(f"{area:<8} {code:<6} {done:>3} translated, {len(msgs) - done:>3} unfinished")
    return 1 if unfinished else 0


def check() -> int:
    bad = 0
    for area in PACKAGES:
        msgs, _ = _area_msgs(area)
        for code in LANGS:
            po = read_po(po_path(area, code))
            for key in msgs:
                value = po.get(key, "")
                if value and sorted(re.findall(r"%\d", value)) != sorted(re.findall(r"%\d", key[1])):
                    print(f"{area} {code}: placeholders differ in {key[1]!r} → {value!r}")
                    bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd in ("update", "release"):
        {"update": update, "release": release}[cmd]()
    elif cmd in ("stats", "check"):
        sys.exit({"stats": stats, "check": check}[cmd]())
    else:
        print(__doc__)
        sys.exit(2)
