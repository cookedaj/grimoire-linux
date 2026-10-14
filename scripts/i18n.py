#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translation catalogs: extract, compile, count, and hand strings to/from a translator.

    scripts/i18n.py update [AREA…]          strings from the code → translations/<area>/<lang>.ts (all languages)
    scripts/i18n.py release [AREA…]         .ts → .qm with lrelease (the .qm files are committed)
    scripts/i18n.py stats [AREA…]           translated / unfinished per area and language
    scripts/i18n.py check [AREA…]           placeholders ({name}, %n) that differ from the English text
    scripts/i18n.py export AREA LANG [--all] > todo.json      the unfinished strings as JSON
    scripts/i18n.py import AREA LANG todo.json               fills them back in (then run release)

Areas are "core" and one per spell folder (grimoire/i18n.py AREAS). A string's area comes from its tr() context:
grimoire.spells.<area>.… → <area>, anything else → core, so each area's catalogs only change with its own strings.
Extraction is our own (ast): lupdate's Python parser can't mark "%n" plurals and drops their forms when merging.
Only tr("context", "text"[, "disambiguation"][, n=…]) and tr_noop("context", "text") calls with string literals are
read. The English catalog (en.ts) holds only the plurals ("%n file(s)" → "%n file" / "%n files").
"""
import ast
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from grimoire.i18n import AREAS, LANGUAGES, QT_LOCALE, TRANSLATIONS  # noqa: E402

# plural forms Qt uses per language (measured with lrelease + QTranslator), in Qt's order
FORMS = {"en": 2, "zh_CN": 1, "hi": 2, "es": 2, "fr": 2, "ar": 6, "bn": 2, "pt": 2, "ru": 3, "ur": 2}
FORM_NAMES = {"en": ["one", "other"], "zh_CN": ["all"], "hi": ["one", "other"], "es": ["one", "other"],
              "fr": ["0 and 1", "other"], "ar": ["zero", "one", "two", "few (3-10)", "many (11-99)", "other (100+)"],
              "bn": ["one", "other"], "pt": ["0 and 1", "other"], "ru": ["one (1, 21…)", "few (2-4, 22…)",
                                                                             "many (0, 5-20…)"],
              "ur": ["one", "other"]}
LRELEASE = ["/usr/lib/qt6/bin/lrelease", "lrelease6", "lrelease"]
PLACEHOLDER = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*(?:![rsa])?(?::[^{}]*)?\}|%n|%\d")


class Msg:
    def __init__(self, context, source, comment, numerus):
        self.context, self.source, self.comment, self.numerus = context, source, comment, numerus
        self.files = []

    @property
    def key(self):
        return self.context, self.source, self.comment or ""


def area_of(context: str) -> str:
    parts = context.split(".")
    if len(parts) >= 3 and parts[:2] == ["grimoire", "spells"] and parts[2] in AREAS:
        return parts[2]
    return "core"


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def extract() -> tuple[dict, list]:
    """Every tr()/tr_noop() string in grimoire/, grouped by area, in file order; plus problems found."""
    found, problems = {}, []
    for path in sorted((ROOT / "grimoire").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(), rel)
        except SyntaxError as e:
            problems.append(f"{rel}: {e}")
            continue
        calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
        for node in calls:
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "i18n"
                else None)
            if name not in ("tr", "tr_noop") or len(node.args) < 2:
                continue
            ctx, text = _literal(node.args[0]), node.args[1]
            where = f"{rel}:{node.lineno}"
            if isinstance(text, ast.JoinedStr):
                problems.append(f"{where}: f-string in {name}() (use \"…{{x}}…\".format(x=…))")
                continue
            text = _literal(text)
            if text is None:
                continue                                 # a variable: translated text from a table (tr_noop)
            if ctx is None:
                problems.append(f"{where}: the context must be a string literal")
                continue
            comment = _literal(node.args[2]) if len(node.args) > 2 else None
            for kw in node.keywords:
                if kw.arg == "disambiguation":
                    comment = _literal(kw.value)
            numerus = name == "tr" and (len(node.args) > 3 or any(kw.arg == "n" for kw in node.keywords))
            if numerus and "%n" not in text:
                problems.append(f"{where}: a plural text needs %n")
            key = (ctx, text, comment or "")
            area = found.setdefault(area_of(ctx), {})
            msg = area.get(key)
            if msg is None:
                msg = area[key] = Msg(ctx, text, comment, numerus)
            msg.numerus |= numerus
            if rel not in msg.files:
                msg.files.append(rel)
    return found, problems


# ---------------------------------------------------------------- .ts files
def ts_path(area: str, lang: str) -> Path:
    return TRANSLATIONS / area / f"{lang}.ts"


def read_ts(path: Path) -> dict:
    """key → (translation: str | list[str], finished: bool, numerus)"""
    out = {}
    if not path.exists():
        return out
    for ctx in ET.parse(path).getroot().iter("context"):
        cname = ctx.findtext("name") or ""
        for m in ctx.iter("message"):
            tnode = m.find("translation")
            kind = tnode.get("type", "") if tnode is not None else "unfinished"
            if m.get("numerus") == "yes":
                value = [nf.text or "" for nf in tnode.iter("numerusform")] if tnode is not None else []
            else:
                value = (tnode.text or "") if tnode is not None else ""
            key = (cname, m.findtext("source") or "", m.findtext("comment") or "")
            out[key] = (value, kind == "" and bool(value) and all(value), kind)
    return out


def _x(text: str) -> str:
    return escape(text, {'"': "&quot;", "'": "&apos;"})


def write_ts(path: Path, lang: str, msgs: list[Msg], old: dict):
    """Rewrite one catalog: current strings in order (keeping translations), then vanished ones (kept, so a
    reworded string's old translation is still there to copy; lrelease skips them)."""
    forms = FORMS[lang]
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>",
             f'<TS version="2.1" language="{QT_LOCALE.get(lang, lang)}" sourcelanguage="en">']
    by_ctx: dict[str, list] = {}
    for m in msgs:
        by_ctx.setdefault(m.context, []).append(m)
    current = {m.key for m in msgs}
    vanished = [(k, v) for k, v in old.items() if k not in current and (v[0] if isinstance(v[0], str) else any(v[0]))]
    for k, v in vanished:
        by_ctx.setdefault(k[0], []).append((k, v))
    up = "../" * len(path.relative_to(ROOT).parts[:-1])
    for ctx in by_ctx:
        lines += ["<context>", f"    <name>{_x(ctx)}</name>"]
        for m in by_ctx[ctx]:
            if isinstance(m, tuple):                     # vanished
                (_, source, comment), (value, _, _) = m
                numerus, files, state = isinstance(value, list), [], "vanished"
            else:
                source, comment, numerus, files = m.source, m.comment, m.numerus, m.files
                value, done, _ = old.get(m.key, ("", False, ""))
                state = "" if done else "unfinished"
            if numerus:
                value = value if isinstance(value, list) else ([value] if value else [])
                value = (value + [""] * forms)[:forms]
                if state == "" and not all(value):
                    state = "unfinished"
            elif isinstance(value, list):
                value, state = (value[0] if value else ""), "unfinished"
            lines.append('    <message numerus="yes">' if numerus else "    <message>")
            lines += [f'        <location filename="{up}{f}"/>' for f in files]
            lines.append(f"        <source>{_x(source)}</source>")
            if comment:
                lines.append(f"        <comment>{_x(comment)}</comment>")
            attr = f' type="{state}"' if state else ""
            if numerus:
                lines.append(f"        <translation{attr}>")
                lines += [f"            <numerusform>{_x(v)}</numerusform>" for v in value]
                lines.append("        </translation>")
            else:
                lines.append(f"        <translation{attr}>{_x(value)}</translation>")
            lines.append("    </message>")
        lines.append("</context>")
    lines.append("</TS>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def areas_arg(args) -> list[str]:
    bad = [a for a in args if a not in AREAS]
    if bad:
        sys.exit(f"unknown area: {', '.join(bad)} (areas: {', '.join(AREAS)})")
    return list(args) or list(AREAS)


def cmd_update(args):
    found, problems = extract()
    for p in problems:
        print("warning:", p, file=sys.stderr)
    for area in areas_arg(args):
        msgs = list(found.get(area, {}).values())
        if not msgs and not (TRANSLATIONS / area).exists():
            continue
        for lang in LANGUAGES:
            mine = [m for m in msgs if m.numerus] if lang == "en" else msgs
            write_ts(ts_path(area, lang), lang, mine, read_ts(ts_path(area, lang)))
        print(f"{area}: {len(msgs)} strings ({sum(m.numerus for m in msgs)} plural)")


def lrelease() -> str:
    for c in LRELEASE:
        if shutil.which(c):
            return shutil.which(c)
    sys.exit("lrelease not found: sudo apt install qt6-l10n-tools")


def cmd_release(args):
    tool = lrelease()
    for area in areas_arg(args):
        for ts in sorted((TRANSLATIONS / area).glob("*.ts")):
            r = subprocess.run([tool, "-silent", "-nounfinished", str(ts), "-qm", str(ts.with_suffix(".qm"))],
                               capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"{ts}: {r.stderr.strip()}")
    print("released:", ", ".join(areas_arg(args)))


def counts(area, lang):
    data = read_ts(ts_path(area, lang))
    live = {k: v for k, v in data.items() if v[2] != "vanished"}
    return sum(v[1] for v in live.values()), len(live)


def cmd_stats(args):
    langs = [lang for lang in LANGUAGES]
    print("area".ljust(11) + "".join(lang.rjust(10) for lang in langs))
    for area in areas_arg(args):
        if not (TRANSLATIONS / area).exists():
            continue
        row = []
        for lang in langs:
            done, total = counts(area, lang)
            row.append(f"{done}/{total}".rjust(10))
        print(area.ljust(11) + "".join(row))


def placeholders(text: str) -> list[str]:
    return sorted(PLACEHOLDER.findall(text))


def problems_in(source, value, lang, numerus) -> list[str]:
    want = [p for p in placeholders(source) if p != "%n"]
    out = []
    values = value if isinstance(value, list) else [value]
    for i, v in enumerate(values):
        if not v:
            continue
        got = [p for p in placeholders(v) if p != "%n"]
        if got != want:
            out.append(f"placeholders {got} ≠ {want}")
        # a form that only ever means one number (Arabic zero/one/two, the "one" of 2-form languages) may spell it
        exact = {"ar": {0, 1, 2}}.get(lang, {0} if FORMS[lang] == 2 and lang not in ("fr", "pt") else set())
        if numerus and "%n" not in v and i not in exact:
            out.append(f"form {i} lacks %n")
    return out


def cmd_check(args):
    bad = 0
    for area in areas_arg(args):
        for lang in LANGUAGES:
            for (ctx, source, _), (value, done, kind) in read_ts(ts_path(area, lang)).items():
                if kind == "vanished":
                    continue
                for p in problems_in(source, value, lang, isinstance(value, list)):
                    bad += 1
                    print(f"{area}/{lang} [{ctx}] {source[:60]!r}: {p}")
    found, problems = extract()
    for p in problems:
        bad += 1
        print("code:", p)
    print("ok" if not bad else f"{bad} problem(s)")
    sys.exit(1 if bad else 0)


def cmd_export(args):
    if len(args) < 2:
        sys.exit("usage: export AREA LANG [--all]")
    area, lang = args[0], args[1]
    out = []
    for (ctx, source, comment), (value, done, kind) in read_ts(ts_path(area, lang)).items():
        if kind == "vanished" or (done and "--all" not in args):
            continue
        item = {"context": ctx, "source": source}
        if comment:
            item["comment"] = comment
        if isinstance(value, list):
            item["forms"] = FORM_NAMES[lang]
            item["translation"] = value
        else:
            item["translation"] = value
        out.append(item)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


def cmd_import(args):
    if len(args) != 3:
        sys.exit("usage: import AREA LANG FILE.json")
    area, lang, file = args
    items = json.loads(Path(file).read_text())
    path = ts_path(area, lang)
    tree = ET.parse(path)
    index = {}
    for ctx in tree.getroot().iter("context"):
        for m in ctx.iter("message"):
            index[(ctx.findtext("name") or "", m.findtext("source") or "", m.findtext("comment") or "")] = m
    filled = skipped = 0
    for it in items:
        key = (it["context"], it["source"], it.get("comment", ""))
        m, value = index.get(key), it.get("translation")
        if m is None or not value:
            skipped += 1
            continue
        numerus = m.get("numerus") == "yes"
        if numerus != isinstance(value, list) or (numerus and len(value) != FORMS[lang]):
            print(f"skip (wrong form count): {it['source'][:60]!r}", file=sys.stderr)
            skipped += 1
            continue
        issues = problems_in(it["source"], value, lang, numerus)
        t = m.find("translation")
        if numerus:
            for nf in list(t):
                t.remove(nf)
            for v in value:
                ET.SubElement(t, "numerusform").text = v
        else:
            t.text = value
        if issues:
            print(f"left unfinished ({'; '.join(issues)}): {it['source'][:60]!r}", file=sys.stderr)
            t.set("type", "unfinished")
            skipped += 1
        else:
            t.attrib.pop("type", None)
            filled += 1
    old = read_ts_tree(tree)
    found, _ = extract()
    msgs = list(found.get(area, {}).values())
    write_ts(path, lang, [m for m in msgs if m.numerus] if lang == "en" else msgs, old)
    print(f"{area}/{lang}: {filled} filled, {skipped} skipped")


def read_ts_tree(tree) -> dict:
    tmp = Path(TRANSLATIONS / ".import.ts")
    tree.write(tmp, encoding="utf-8")
    try:
        return read_ts(tmp)
    finally:
        tmp.unlink()


COMMANDS = {"update": cmd_update, "release": cmd_release, "stats": cmd_stats, "check": cmd_check,
            "export": cmd_export, "import": cmd_import}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2:])
