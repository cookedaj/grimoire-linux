# SPDX-License-Identifier: GPL-3.0-or-later
"""Syntax highlighting in black & white: keywords bold white, strings and numbers in grays, comments dim italic.

One small tokenizer per language (Python, shell, JSON, YAML, INI/TOML, C-like: C, C++, JavaScript, TypeScript, Java,
Rust, Go…) plus Markdown, whose ``` code blocks are highlighted in their own language. Each language is one combined
regex scanned left to right, so a "#" inside a string never starts a comment; constructs that span lines (Python's
triple quotes, /* comments */, JavaScript template strings) carry over through the block state.
"""
import re
from functools import lru_cache

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from grimoire.i18n import MONO, tr

# ---------------------------------------------------------------- formats
STYLE = {   # key: (color, bold, italic, background, underline, strike)
    "keyword": ("#ffffff", True, False, None, False, False),
    "type": ("#f2f2f2", False, False, None, False, False),
    "const": ("#ffffff", False, True, None, False, False),
    "string": ("#949494", False, False, None, False, False),
    "comment": ("#5a5a5a", False, True, None, False, False),
    "number": ("#c4c4c4", False, False, None, False, False),
    "func": ("#f2f2f2", False, False, None, False, False),
    "meta": ("#8c8c8c", False, False, None, False, False),
    "key": ("#ffffff", False, False, None, False, False),
    "var": ("#e6e6e6", True, False, None, False, False),
    "heading": ("#ffffff", True, False, None, False, False),
    "marker": ("#6f6f6f", True, False, None, False, False),
    "strong": ("#ffffff", True, False, None, False, False),
    "em": ("#e8e8e8", False, True, None, False, False),
    "strike": ("#7a7a7a", False, False, None, False, True),
    "code": ("#c8c8c8", False, False, "#1a1a1a", False, False),
    "link": ("#f2f2f2", False, False, None, True, False),
    "url": ("#9a9a9a", False, False, None, True, False),
    "tag": ("#ffffff", False, False, "#202020", False, False),
    "quote": ("#9a9a9a", False, True, None, False, False),
}


@lru_cache(maxsize=256)
def fmt(key: str, mono: bool = False, size: int = 0) -> QTextCharFormat:
    """The format for a token kind; mono=True also sets the monospace font (code inside a Markdown note)."""
    f = QTextCharFormat()
    if key in STYLE:
        color, bold, italic, bg, underline, strike = STYLE[key]
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Weight.Bold)
        if italic:
            f.setFontItalic(True)
        if bg:
            f.setBackground(QColor(bg))
        if underline:
            f.setFontUnderline(True)
        if strike:
            f.setFontStrikeOut(True)
    if mono:
        f.setFontFamilies([MONO, "monospace"])
        f.setFontFixedPitch(True)
        if not f.hasProperty(QTextCharFormat.Property.BackgroundBrush):
            f.setBackground(QColor("#141414"))
        if not f.hasProperty(QTextCharFormat.Property.ForegroundBrush):
            f.setForeground(QColor("#cfcfcf"))
    return f


# ---------------------------------------------------------------- languages
def _words(*groups: str) -> str:
    return r"\b(?:" + "|".join(sorted({w for g in groups for w in g.split()}, key=len, reverse=True)) + r")\b"


DQ = r'"(?:\\.|[^"\\])*"?'
SQ = r"'(?:\\.|[^'\\])*'?"
NUM = r"\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(?:\.[\d_]+)?(?:[eE][+-]?\d+)?[jJlLuUfF]*)\b"
CALL = r"\b[A-Za-z_][\w]*(?=\s*\()"


class Lang:
    """tokens: [(format key, regex)] in priority order; blocks: [(format key, opening regex, closing regex)] for
    constructs that can continue on the next lines (block state = their index + 1)."""

    def __init__(self, name: str, tokens, blocks=(), flags=0):
        self.name = name
        self.blocks = [(k, re.compile(c, flags)) for k, _, c in blocks]
        parts = [f"(?P<b{i}>{o})" for i, (_, o, _) in enumerate(blocks)]
        parts += [f"(?P<t{i}>{p})" for i, (_, p) in enumerate(tokens)]
        self.keys = [k for k, _ in tokens]
        self.rx = re.compile("|".join(parts), flags)

    def run(self, text: str, state: int, put) -> int:
        """Highlight one line: put(start, end, key) for each token. Returns the state the next line starts in."""
        pos = 0
        if 0 < state <= len(self.blocks):
            key, close = self.blocks[state - 1]
            m = close.search(text)
            if not m:
                put(0, len(text), key)
                return state
            put(0, m.end(), key)
            pos = m.end()
        while pos <= len(text):
            m = self.rx.search(text, pos)
            if not m:
                break
            g = m.lastgroup
            if g[0] == "b":
                i = int(g[1:])
                key, close = self.blocks[i]
                c = close.search(text, m.end())
                if not c:
                    put(m.start(), len(text), key)
                    return i + 1
                put(m.start(), c.end(), key)
                pos = c.end()
                continue
            key = self.keys[int(g[1:])]
            if key:
                put(m.start(), m.end(), key)
            pos = m.end() if m.end() > m.start() else m.end() + 1
        return 0


PY_KW = ("and as assert async await break class continue def del elif else except finally for from global if import "
         "in is lambda nonlocal not or pass raise return try while with yield match case type")
PY_CONST = "True False None self cls NotImplemented Ellipsis __name__ __file__"
PY_BUILTIN = ("print len range open str int float bool list dict set tuple object super isinstance getattr setattr "
              "hasattr enumerate zip map filter sorted reversed min max sum any all abs repr type")
PYTHON = Lang("python", [
    ("comment", r"#.*"),
    ("string", r"[rRbBuUfF]{0,2}" + DQ), ("string", r"[rRbBuUfF]{0,2}" + SQ),
    ("meta", r"@[\w.]+"),
    ("keyword", _words(PY_KW)), ("const", _words(PY_CONST)),
    ("func", r"(?<=def )[A-Za-z_]\w*|(?<=class )[A-Za-z_]\w*"),
    ("type", _words(PY_BUILTIN)),
    ("number", NUM), ("func", CALL),
], blocks=[("string", r'[rRbBuUfF]{0,2}"""', r'"""'), ("string", r"[rRbBuUfF]{0,2}'''", r"'''")])

SH_KW = ("if then else elif fi for while until do done case esac in function select return local export readonly "
         "declare typeset break continue exit time coproc")
SH_BUILTIN = ("echo printf cd pwd read set unset source alias unalias test eval exec shift trap wait kill true false "
              "sudo mkdir rm cp mv ls cat grep sed awk find chmod chown ln touch")
SHELL = Lang("shell", [
    ("comment", r"(?:^|(?<=\s))#.*"),
    ("string", DQ), ("string", r"'[^']*'?"),
    ("var", r"\$\{[^}\n]*\}?|\$[A-Za-z_]\w*|\$[0-9@#?$!*-]|\$\(|\$\(\("),
    ("keyword", _words(SH_KW)),
    ("func", r"^\s*[A-Za-z_][\w-]*(?=\s*\(\s*\))"),
    ("type", _words(SH_BUILTIN)),
    ("meta", r"(?<=\s)--?[A-Za-z][\w-]*"),
    ("number", NUM),
])

JSON = Lang("json", [
    ("key", r'"(?:\\.|[^"\\])*"(?=\s*:)'),
    ("string", DQ),
    ("const", r"\b(?:true|false|null)\b"),
    ("number", r"-?" + NUM),
    ("comment", r"//.*"),
], blocks=[("comment", r"/\*", r"\*/")])

YAML = Lang("yaml", [
    ("comment", r"(?:^|(?<=\s))#.*"),
    ("meta", r"^(?:---|\.\.\.)\s*$"),
    ("marker", r"^\s*-(?=\s|$)"),
    ("key", r"^\s*(?:-\s+)?[^\s#'\"\-\[{][^#\n]*?(?=:(?:\s|$))|^\s*(?:-\s+)?\"[^\"]*\"(?=:(?:\s|$))"),
    ("string", DQ), ("string", r"'(?:''|[^'])*'?"),
    ("meta", r"[&*][\w-]+|!\S+"),
    ("const", r"\b(?:true|false|yes|no|on|off|null|True|False|Yes|No|Null|NULL)\b|(?<=:\s)~"),
    ("number", r"-?" + NUM),
])

INI = Lang("ini", [
    ("comment", r"^\s*[#;].*"),
    ("keyword", r"^\s*\[[^\]\n]*\]"),
    ("key", r"^\s*[\w.\-\[\]@ ]+?(?=\s*[=:])"),
    ("string", DQ), ("string", SQ),
    ("const", r"\b(?:true|false|yes|no|on|off)\b"),
    ("number", r"-?" + NUM),
])

C_KW = ("auto break case char const continue default do double else enum extern float for goto if inline int long "
        "register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while "
        "class namespace template typename public private protected virtual override final new delete operator "
        "friend using try catch throw noexcept constexpr explicit mutable this "
        "function var let const async await yield export import from default of in instanceof typeof extends "
        "implements interface package abstract synchronized transient throws boolean byte "
        "fn mut pub impl trait struct enum match loop where crate mod use as dyn ref move unsafe "
        "func go chan defer select map range type fallthrough "
        "fun val when object companion data sealed is "
        "let var guard defer protocol extension self Self "
        "echo foreach endforeach elseif")
C_CONST = "true false null nullptr NULL nil None undefined NaN Infinity this self super"
CLIKE = Lang("clike", [
    ("comment", r"//.*"),
    ("meta", r"^\s*#\s*[A-Za-z]+.*"),
    ("string", DQ), ("string", SQ),
    ("meta", r"@[A-Za-z_][\w.]*"),
    ("keyword", _words(C_KW)), ("const", _words(C_CONST)),
    ("type", r"\b[A-Z][A-Za-z0-9_]*\b"),
    ("number", NUM), ("func", CALL),
], blocks=[("comment", r"/\*", r"\*/"), ("string", r"`", r"(?<!\\)`")])

CSS = Lang("css", [
    ("string", DQ), ("string", SQ),
    ("meta", r"@[\w-]+"),
    ("key", r"[\w-]+(?=\s*:[^{}\n]*;)"),
    ("number", r"-?\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms|deg|pt)?\b|#[0-9a-fA-F]{3,8}\b"),
    ("keyword", r"[.#]?[A-Za-z_][\w-]*(?=[^{};\n]*\{)"),
], blocks=[("comment", r"/\*", r"\*/")])

LANGS = {lang.name: lang for lang in (PYTHON, SHELL, JSON, YAML, INI, CLIKE, CSS)}
LANG_IDS = list(LANGS) + ["markdown"]

EXT = {"py": "python", "pyw": "python", "pyi": "python",
       "sh": "shell", "bash": "shell", "zsh": "shell", "ksh": "shell", "fish": "shell",
       "json": "json", "jsonc": "json", "geojson": "json", "ipynb": "json",
       "yaml": "yaml", "yml": "yaml",
       "md": "markdown", "markdown": "markdown",
       "ini": "ini", "cfg": "ini", "conf": "ini", "toml": "ini", "desktop": "ini", "service": "ini", "timer": "ini",
       "properties": "ini", "rc": "ini",
       "css": "css", "qss": "css", "scss": "css",
       **{e: "clike" for e in "c h cpp cc cxx hpp hh hxx js mjs cjs jsx ts tsx java rs go cs kt kts swift php dart "
                              "scala groovy gradle qml vala zig d m mm glsl frag vert".split()}}
NAMES = {"bashrc": "shell", ".bashrc": "shell", ".profile": "shell", ".bash_profile": "shell", ".zshrc": "shell",
         ".bash_aliases": "shell", "pkgbuild": "shell", ".gitconfig": "ini", ".editorconfig": "ini",
         "user-dirs.dirs": "shell"}
FENCE_LANG = {"py": "python", "python": "python", "python3": "python", "sh": "shell", "bash": "shell",
              "shell": "shell", "zsh": "shell", "console": "shell", "json": "json", "yaml": "yaml", "yml": "yaml",
              "ini": "ini", "toml": "ini", "css": "css", "md": "markdown", "markdown": "markdown",
              **{e: "clike" for e in "c h cpp c++ js javascript ts typescript jsx tsx java rust rs go golang cs "
                                     "csharp kotlin kt swift php dart qml".split()}}
DISPLAY = {"python": "Python", "shell": "Shell", "json": "JSON", "yaml": "YAML", "ini": "INI / TOML", "css": "CSS",
           "markdown": "Markdown"}
CLIKE_NAMES = {"c": "C", "h": "C", "cpp": "C++", "cc": "C++", "cxx": "C++", "hpp": "C++", "js": "JavaScript",
               "mjs": "JavaScript", "jsx": "JavaScript", "ts": "TypeScript", "tsx": "TypeScript", "java": "Java",
               "rs": "Rust", "go": "Go", "cs": "C#", "kt": "Kotlin", "swift": "Swift", "php": "PHP", "dart": "Dart",
               "qml": "QML"}


def language_for(name: str, first_line: str = "") -> str:
    """A language id for a file name (and its first line, for #! scripts); "" for plain text."""
    low = name.lower()
    if low in NAMES:
        return NAMES[low]
    ext = low.rsplit(".", 1)[-1] if "." in low else ""
    if ext in EXT:
        return EXT[ext]
    if first_line.startswith("#!"):
        if "python" in first_line:
            return "python"
        if re.search(r"\b(?:ba|z|k|da)?sh\b", first_line):
            return "shell"
        if "node" in first_line:
            return "clike"
    return ""


def display_name(lang: str, name: str = "") -> str:
    if lang == "clike":
        ext = name.lower().rsplit(".", 1)[-1]
        return CLIKE_NAMES.get(ext, tr("grimoire.spells.notel.highlight", "Code"))
    if lang == "shell":
        return tr("grimoire.spells.notel.highlight", "Shell script")
    return DISPLAY.get(lang) or tr("grimoire.spells.notel.highlight", "Plain text")


# ---------------------------------------------------------------- Markdown
MD_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([\w+#.-]*)")
MD_HEADING = re.compile(r"^(#{1,6})(\s+.*|$)")
MD_LIST = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])(?=\s)(?:\s+\[[ xX]\](?=\s))?")
MD_QUOTE = re.compile(r"^\s{0,3}>")
MD_RULE = re.compile(r"^\s{0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
MD_INLINE = Lang("md-inline", [
    ("code", r"(?P<tick>`+)(?:(?!(?P=tick)).)+?(?P=tick)"),
    ("link", r"!?\[\[[^\[\]\n]+\]\]"),
    ("link", r"!?\[[^\]\n]*\]\([^)\n]*\)"),
    ("url", r"<https?://[^>\s]+>|\bhttps?://[^\s<>()\[\]]+[^\s<>()\[\].,;:!?'\"]"),
    ("strong", r"\*\*(?=\S)[^\n]+?(?<=\S)\*\*|__(?=\S)[^\n]+?(?<=\S)__"),
    ("em", r"(?<![*\w])\*(?=[^\s*])[^*\n]*?(?<=[^\s*])\*(?![*\w])|(?<![_\w])_(?=[^\s_])[^_\n]*?(?<=[^\s_])_(?!\w)"),
    ("strike", r"~~(?=\S)[^\n]+?(?<=\S)~~"),
    ("tag", r"(?<![^\s(\[,;])#[\w/-]*[^\W\d][\w/-]*"),
    ("meta", r"<!--.*?-->|<[A-Za-z/][^>\n]*>"),
])
FENCE_STATE = 1000          # + language index * 16 + that language's own block state
FRONT_STATE = 900


class Highlighter(QSyntaxHighlighter):
    """Highlights a QTextDocument as `lang` ("" = plain text, nothing to do)."""

    def __init__(self, document, lang: str = ""):
        super().__init__(document)
        self.lang = lang

    def set_language(self, lang: str):
        if lang != self.lang:
            self.lang = lang
            self.rehighlight()

    # Python indexes code points, Qt indexes UTF-16 units: they only differ after a character outside the BMP
    def _putter(self, text: str, mono: bool = False):
        if text.isascii() or max(text) <= "\uffff":
            offset = None
        else:
            offset = [0]
            for ch in text:
                offset.append(offset[-1] + (2 if ord(ch) > 0xFFFF else 1))

        def put(a: int, b: int, key: str):
            if offset is not None:
                a, b = offset[a], offset[min(b, len(text))]
            if b > a:
                self.setFormat(a, b - a, fmt(key, mono))
        return put

    def highlightBlock(self, text: str):
        if not self.lang:
            return
        prev = self.previousBlockState()
        if self.lang == "markdown":
            self.setCurrentBlockState(self._markdown(text, prev))
        else:
            lang = LANGS.get(self.lang)
            if lang:
                self.setCurrentBlockState(lang.run(text, max(prev, 0), self._putter(text)))

    def _markdown(self, text: str, prev: int) -> int:
        put = self._putter(text)
        # YAML front matter at the very top
        if prev == -1 and self.currentBlock().blockNumber() == 0 and text.rstrip() == "---":
            put(0, len(text), "meta")
            return FRONT_STATE
        if prev == FRONT_STATE:
            if text.rstrip() in ("---", "..."):
                put(0, len(text), "meta")
                return 0
            YAML.run(text, 0, put)
            return FRONT_STATE
        # fenced code blocks, highlighted in their language
        fence = MD_FENCE.match(text)
        if prev >= FENCE_STATE:
            mono = self._putter(text, mono=True)
            if fence and not fence.group(2):
                mono(0, len(text), "meta")
                return 0
            if text:
                mono(0, len(text), "")
            idx, inner = divmod(prev - FENCE_STATE, 16)
            lang = LANGS.get(LANG_IDS[idx]) if idx < len(LANG_IDS) else None
            if lang:
                inner = lang.run(text, inner, mono)
            return FENCE_STATE + idx * 16 + min(inner, 15)
        if fence:
            self._putter(text, mono=True)(0, len(text), "meta")
            lang = FENCE_LANG.get(fence.group(2).lower(), "")
            idx = LANG_IDS.index(lang) if lang in LANG_IDS and lang != "markdown" else 63
            return FENCE_STATE + idx * 16
        # line kinds
        h = MD_HEADING.match(text)
        if h:
            put(0, len(text), "heading")
            put(0, len(h.group(1)), "marker")
            self._inline(text, put, skip=len(h.group(1)))
            return 0
        if MD_RULE.match(text):
            put(0, len(text), "marker")
            return 0
        start = 0
        q = MD_QUOTE.match(text)
        if q:
            put(0, len(text), "quote")
            put(0, q.end(), "marker")
            start = q.end()
        li = MD_LIST.match(text, start)
        if li:
            put(li.start(), li.end(), "marker")
            start = li.end()
        if text.startswith(("    ", "\t")) and not li and not q:
            self._putter(text, mono=True)(0, len(text), "")
            return 0
        self._inline(text, put, skip=start)
        return 0

    def _inline(self, text: str, put, skip: int = 0):
        MD_INLINE.run(text[skip:], 0, lambda a, b, k: put(a + skip, b + skip, k)) if skip else MD_INLINE.run(
            text, 0, put)
        if "|" in text and text.lstrip().startswith("|"):          # table pipes
            for m in re.finditer(r"\|", text):
                put(m.start(), m.end(), "marker")
