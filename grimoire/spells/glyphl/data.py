# SPDX-License-Identifier: GPL-3.0-or-later
"""GlyphL's characters: emoji with their names and keywords in the UI language, every named Unicode character, the
symbol categories, search, and the facts the info pane shows. No Qt, so it loads on a worker thread.

Emoji names and keywords come from the CLDR annotations Plasma's own emoji picker ships
(/usr/share/plasma/emoji/<lang>.dict: qCompress'd QDataStream records), in the UI language plus English, so both
searches work. Without them GlyphL falls back to emoji.tsv.gz (English, built by scripts/glyphl_data.py).
Unicode character names come from Python's unicodedata and are English only (Unicode publishes no translations).
"""
import bisect
import gzip
import html.entities
import os
import re
import struct
import unicodedata
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from grimoire.i18n import tr, tr_noop
from grimoire.spells.glyphl.blocks import BLOCKS

HERE = Path(__file__).resolve().parent
BUNDLED = HERE / "emoji.tsv.gz"
TONES = "\U0001F3FB\U0001F3FC\U0001F3FD\U0001F3FE\U0001F3FF"      # Fitzpatrick modifiers, light → dark
VS16, ZWJ = "️", "‍"
TONE_NAMES = (tr_noop("grimoire.spells.glyphl.data", "No skin tone"),
              tr_noop("grimoire.spells.glyphl.data", "Light skin tone"),
              tr_noop("grimoire.spells.glyphl.data", "Medium-light skin tone"),
              tr_noop("grimoire.spells.glyphl.data", "Medium skin tone"),
              tr_noop("grimoire.spells.glyphl.data", "Medium-dark skin tone"),
              tr_noop("grimoire.spells.glyphl.data", "Dark skin tone"))
# CLDR emoji groups as Plasma numbers them (3 = Component: skin tones and hair parts, not shown on their own)
GROUPS = {1: tr_noop("grimoire.spells.glyphl.data", "Smileys & emotion"),
          2: tr_noop("grimoire.spells.glyphl.data", "People & body"),
          4: tr_noop("grimoire.spells.glyphl.data", "Animals & nature"),
          5: tr_noop("grimoire.spells.glyphl.data", "Food & drink"),
          6: tr_noop("grimoire.spells.glyphl.data", "Travel & places"),
          7: tr_noop("grimoire.spells.glyphl.data", "Activities"),
          8: tr_noop("grimoire.spells.glyphl.data", "Objects"),
          9: tr_noop("grimoire.spells.glyphl.data", "Symbols"),
          10: tr_noop("grimoire.spells.glyphl.data", "Flags")}
# Grimoire's own picks: black & white symbols that read the same in any font, for notes, docs and chat
PICKS = ("✓ ✔ ✗ ✘ • · … — – ‒ ¶ § † ‡ ※ ‹ › « » “ ” ‘ ’ „ ′ ″ "
         "→ ← ↑ ↓ ↔ ↕ ⇒ ⇐ ⇔ ↩ ↪ ⟶ ⟵ ↗ ↘ "
         "★ ☆ ● ○ ◉ ◌ ◆ ◇ ■ □ ▪ ▫ ▲ △ ▼ ▽ ◀ ▶ ◢ ◣ ◤ ◥ "
         "± × ÷ − ≈ ≠ ≡ ≤ ≥ ∞ √ ∑ ∏ ∫ ∂ ∆ ∇ ∈ ∉ ∅ ∩ ∪ ⊂ ⊃ ∀ ∃ ¬ ∧ ∨ ° ′ µ π Ω λ α β γ θ "
         "© ® ™ ℗ № ℃ ℉ ‰ ‱ ¹ ² ³ ½ ⅓ ¼ ¾ "
         "⌘ ⌥ ⇧ ⌃ ⎋ ⏎ ⌫ ⌦ ⇥ ⏏ ⏻ ⌨ "
         "♠ ♣ ♥ ♦ ♤ ♧ ♡ ♢ ♩ ♪ ♫ ♬ ☼ ☾ ☽ ✦ ✧ ✶ ✳ ❖ ❦ ☙ ⚘ ⁂ ⌖ ⌗ ⍟ ☯ ☰ ☷ ⚐ ⚑ ⚠ ☐ ☑ ☒").split()
_PICKS = list(dict.fromkeys(PICKS))


def _ranges(*spans) -> list[str]:
    """The named characters in the given (first, last) code point spans."""
    out = []
    for lo, hi in spans:
        for cp in range(lo, hi + 1):
            if unicodedata.name(chr(cp), ""):
                out.append(chr(cp))
    return out


def _currency() -> list[str]:
    return [chr(cp) for cp in range(0x110000) if unicodedata.category(chr(cp)) == "Sc"]


# symbol categories: id → (label, how to list them); listed lazily and cached
SYMBOLS = {
    "arrows": (tr_noop("grimoire.spells.glyphl.data", "Arrows"),
               lambda: _ranges((0x2190, 0x21FF), (0x27F0, 0x27FF), (0x2900, 0x297F), (0x2B00, 0x2B2F),
                               (0x2B30, 0x2B4F), (0x2B5A, 0x2BFF), (0x1F800, 0x1F8FF))),
    "math": (tr_noop("grimoire.spells.glyphl.data", "Math"),
             lambda: list("±×÷¬°µ·¹²³¼½¾") + _ranges((0x2070, 0x209F), (0x2150, 0x218F), (0x2200, 0x22FF),
                                                      (0x27C0, 0x27EF), (0x2980, 0x29FF), (0x2A00, 0x2AFF))),
    "currency": (tr_noop("grimoire.spells.glyphl.data", "Currency"), _currency),
    "box": (tr_noop("grimoire.spells.glyphl.data", "Box drawing"),
            lambda: _ranges((0x2500, 0x257F), (0x2580, 0x259F), (0x25A0, 0x25FF), (0x1FB00, 0x1FBFF))),
    "punct": (tr_noop("grimoire.spells.glyphl.data", "Punctuation"),
              lambda: _ranges((0x00A1, 0x00BF), (0x2010, 0x205E), (0x2E00, 0x2E5D), (0x3001, 0x3003),
                              (0x3008, 0x3011))),
    "symbols": (tr_noop("grimoire.spells.glyphl.data", "Signs & shapes"),
                lambda: _ranges((0x2100, 0x214F), (0x2300, 0x23FF), (0x2400, 0x243F), (0x2460, 0x24FF),
                                (0x2600, 0x26FF), (0x2700, 0x27BF), (0x1F100, 0x1F1FF))),
    "latin": (tr_noop("grimoire.spells.glyphl.data", "Latin"),
              lambda: _ranges((0x00C0, 0x024F), (0x0250, 0x02AF), (0x1E00, 0x1EFF), (0x2C60, 0x2C7F),
                              (0xA720, 0xA7FF), (0xFB00, 0xFB06))),
    "greek": (tr_noop("grimoire.spells.glyphl.data", "Greek"), lambda: _ranges((0x0370, 0x03FF), (0x1F00, 0x1FFF))),
    "cyrillic": (tr_noop("grimoire.spells.glyphl.data", "Cyrillic"),
                 lambda: _ranges((0x0400, 0x052F), (0x1C80, 0x1C8F), (0x2DE0, 0x2DFF), (0xA640, 0xA69F))),
}


# ---------------------------------------------------------------- emoji
@dataclass(slots=True)
class Emoji:
    text: str
    name: str                       # in the UI language
    group: int
    keywords: tuple = ()
    english: str = ""               # the English name (casefolded), ranked like the UI language's own name
    tones: dict = field(default_factory=dict)        # 1..5 → the sequence in that skin tone
    hay: str = ""                   # everything searchable, casefolded, \x1f between fields

    def toned(self, tone: int) -> str:
        return self.tones.get(tone, self.text)


def fold(text: str) -> str:
    """Casefolded without Latin accents and ligatures, so "coeur" finds "cœur" and "cafe" "café". Only the
    combining accents of U+0300–036F go: Devanagari or Bengali vowel signs are marks too and must stay."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not 0x300 <= ord(c) <= 0x36F)
    return unicodedata.normalize("NFC", text).replace("œ", "oe").replace("æ", "ae")


def _key(text: str) -> str:
    """An emoji without its presentation selectors and skin tones: the same key for every variant."""
    return "".join(c for c in text if c != VS16 and c not in TONES)


def dict_paths(lang: str) -> list[Path]:
    """Plasma's emoji dictionaries for lang ("zh_CN" → zh_CN or zh, "pt" → pt_BR or pt), first found first."""
    base = lang.split("_")[0]
    names = list(dict.fromkeys([lang, "pt_BR" if lang == "pt" else lang, base]))
    dirs = [os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")]
    dirs += (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    if "/usr/share" not in dirs:
        dirs.append("/usr/share")
    out = []
    for name in names:
        for d in dirs:
            p = Path(d) / "plasma" / "emoji" / f"{name}.dict"
            if d and p.is_file() and p not in out:
                out.append(p)
    return out


def parse_dict(path: Path) -> list[tuple[str, int, str, list[str]]] | None:
    """One of Plasma's .dict files: (emoji, group, name, keywords) in CLDR order, or None when it can't be read."""
    try:
        raw = path.read_bytes()
        if len(raw) > 8 << 20:
            return None
        blob = zlib.decompress(raw[4:])                    # qCompress: a 4-byte length, then zlib
        pos = 0

        def num():
            nonlocal pos
            v = struct.unpack_from("<I", blob, pos)[0]
            pos += 4
            return v

        def text():
            nonlocal pos
            n = num()
            if n > 4096:
                raise ValueError("string too long")
            v = blob[pos:pos + n].decode()
            pos += n
            return v

        count = num()
        if count > 20000:
            return None
        out = []
        for _ in range(count):
            seq, name, group = text(), text(), num()
            n = num()
            if n > 500:
                return None
            out.append((seq, group, name, [text() for _ in range(n)]))
        return out
    except (OSError, ValueError, zlib.error, struct.error, UnicodeDecodeError):
        return None


def _bundled() -> list[tuple[str, int, str, list[str]]]:
    out = []
    try:
        with gzip.open(BUNDLED, "rt", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 4 and parts[1].isdigit():
                    out.append((parts[0], int(parts[1]), parts[2], [w for w in parts[3].split("|") if w]))
    except (OSError, EOFError, UnicodeDecodeError):
        pass
    return out


def _cap(name: str) -> str:
    return name[:1].upper() + name[1:]


class EmojiSet:
    """The emoji in CLDR order, grouped, each knowing its skin-tone variants."""

    def __init__(self, lang: str = "en"):
        found = dict_paths(lang)
        rows = parse_dict(found[0]) if found else None
        self.source = str(found[0]) if rows else str(BUNDLED)
        english = None
        if lang.split("_")[0] != "en":                       # English too, so either language finds an emoji
            en = dict_paths("en")
            english = (parse_dict(en[0]) if en else None) or _bundled()
        if not rows:                                         # no dictionary in this language: English names
            rows, english = (english or _bundled()), None
        en_by_key = {_key(seq): (name, words) for seq, _g, name, words in (english or [])}
        self.items: list[Emoji] = []
        self.by_text: dict[str, Emoji] = {}                  # every variant's text → its base emoji
        self.variant_names: dict[str, str] = {}              # "👍🏽" → "Thumbs up: medium skin tone"
        base: dict[str, Emoji] = {}
        variants = []
        for seq, group, name, words in rows:
            if group not in GROUPS or not seq:
                continue
            tones = {c for c in seq if c in TONES}
            if tones:
                variants.append((seq, tones))
                if name:
                    self.variant_names[seq] = _cap(name)
                continue
            k = _key(seq)
            if k in base:
                continue
            en_name, en_words = en_by_key.get(k, ("", []))
            e = Emoji(seq, _cap(name or en_name), group, tuple(words), fold(en_name))
            e.hay = fold("\x1f".join([name, *words, en_name, *en_words]))
            base[k] = e
            self.items.append(e)
            self.by_text[seq] = e
        for seq, tones in variants:
            e = base.get(_key(seq))
            if e is None:
                continue
            self.by_text[seq] = e
            if len(tones) == 1:                              # one tone throughout (not mixed couples)
                e.tones.setdefault(TONES.index(next(iter(tones))) + 1, seq)
        self.groups: dict[int, list[Emoji]] = {}
        for e in self.items:
            self.groups.setdefault(e.group, []).append(e)

    def get(self, text: str) -> Emoji | None:
        return self.by_text.get(text) or self.by_text.get(text + VS16) or self.by_text.get(text.replace(VS16, ""))


# ---------------------------------------------------------------- Unicode names
# generated names (CJK UNIFIED IDEOGRAPH-4E00…) only make the name search slow; the block browser still lists them
_GENERATED = ("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH", "HANGUL SYLLABLE", "TANGUT IDEOGRAPH",
              "TANGUT COMPONENT", "KHITAN SMALL SCRIPT", "NUSHU CHARACTER", "EGYPTIAN HIEROGLYPH")


class Names:
    """Every named character (but the generated ones), for the name search."""

    def __init__(self):
        cps, names = [], []
        for cp in range(0x20, 0x110000):
            n = unicodedata.name(chr(cp), "")
            if n and not n.startswith(_GENERATED):
                cps.append(cp)
                names.append(n)
        self.cps, self.names = cps, names


# ---------------------------------------------------------------- search
_HEX = re.compile(r"^(?:u\+|U\+|0x|\\u|\\U|&#x)([0-9a-fA-F]{1,6});?$")
_BARE_HEX = re.compile(r"^[0-9a-fA-F]{4,6}$")
_DEC = re.compile(r"^&#(\d{1,7});?$")
_ENTITY = re.compile(r"^&([A-Za-z][A-Za-z0-9]{1,31});?$")


def usable(cp: int) -> bool:
    return 0 <= cp < 0x110000 and unicodedata.category(chr(cp)) not in ("Cs", "Cn")


def direct(q: str, emoji: EmojiSet | None) -> list[str]:
    """What the query names outright: a code point (U+2192, 0x2192, &#x2192;, &#8594;, &rarr;, 2192) or pasted
    characters themselves."""
    q = q.strip()
    if not q:
        return []
    if m := _HEX.match(q):
        cp = int(m.group(1), 16)
        return [chr(cp)] if usable(cp) else []
    if m := _DEC.match(q):
        cp = int(m.group(1))
        return [chr(cp)] if usable(cp) else []
    if m := _ENTITY.match(q):
        cp = html.entities.name2codepoint.get(m.group(1))
        return [chr(cp)] if cp else []
    if _BARE_HEX.match(q) and any(c.isdigit() for c in q):
        cp = int(q, 16)
        return [chr(cp)] if usable(cp) else []
    if emoji and emoji.get(q):
        return [emoji.get(q).text]
    if len(q) == 1 and not q.isascii() and usable(ord(q)):     # a pasted letter: é, ж, ب
        return [q]
    if len(q) <= 3 and all(not c.isalnum() for c in q):          # pasted or typed symbols: themselves
        return list(dict.fromkeys(c for c in q if c != VS16))
    return []


def _wordstart(hay: str, word: str) -> bool:
    i = hay.find(word)
    while i != -1:
        if i == 0 or not hay[i - 1].isalnum():
            return True
        i = hay.find(word, i + 1)
    return False


def _whole_word(hay: str, phrase: str) -> bool:
    i = hay.find(phrase)
    while i != -1:
        end = i + len(phrase)
        if (i == 0 or not hay[i - 1].isalnum()) and (end == len(hay) or not hay[end].isalnum()):
            return True
        i = hay.find(phrase, i + 1)
    return False


def _name_score(name: str, whole: str, words: list[str], fields: list[str]) -> int:
    """How well an emoji's name (UI language or English) answers the query; 9 = only its keywords do."""
    if name == whole:
        return 0
    if _whole_word(name, whole):
        return 1
    if whole in fields[1:]:
        return 2
    if name.startswith(whole) or all(_wordstart(name, w) for w in words):
        return 3
    return 9


def search(q: str, emoji: EmojiSet | None, names: Names | None, limit: int = 1200) -> list[str]:
    """Emoji by name or keyword (UI language or English) and characters by Unicode name, best first."""
    out = direct(q, emoji)
    words = fold(q).split()
    if not words:
        return out
    whole = " ".join(words)
    hits = []
    if emoji:
        for i, e in enumerate(emoji.items):
            hay = e.hay
            if not all(w in hay for w in words):
                continue
            fields = hay.split("\x1f")
            score, length = min((_name_score(n, whole, words, fields), len(n)) for n in (fields[0], e.english) if n)
            if score == 9:
                score = 4 if all(_wordstart(hay, w) for w in words) else 6
            hits.append((score, 0, length if score < 4 else i, e.text))
    if names and all(w.isascii() for w in words):
        upper = [w.upper() for w in words]
        whole_up = whole.upper()
        found = 0
        for cp, n in zip(names.cps, names.names):
            if all(w in n for w in upper):
                if n == whole_up:
                    score = 0
                elif _whole_word(n, whole_up):
                    score = 1
                elif n.startswith(whole_up):
                    score = 3
                elif all(_wordstart(n, w) for w in upper):
                    score = 4 if len(n) < 30 else 5
                else:
                    score = 6
                common = 0 if cp < 0x3000 else 1 if cp < 0x10000 else 2     # everyday symbols first
                hits.append((score, 1, common * 1000 + len(n), chr(cp)))
                found += 1
                if found > 6000:
                    break
    hits.sort(key=lambda h: h[:3])
    seen = set(out)
    for h in hits:
        if h[3] not in seen:
            seen.add(h[3])
            out.append(h[3])
            if len(out) >= limit:
                break
    return out


# ---------------------------------------------------------------- lists for the categories
_cache: dict[str, list[str]] = {}


def symbols(cid: str) -> list[str]:
    if cid not in _cache:
        _cache[cid] = SYMBOLS[cid][1]() if cid in SYMBOLS else list(_PICKS) if cid == "picks" else []
    return _cache[cid]


def block_chars(index: int) -> list[str]:
    """The usable characters of one block (unassigned and surrogate code points left out)."""
    lo, hi, _name = BLOCKS[index]
    return [chr(cp) for cp in range(lo, hi + 1) if unicodedata.category(chr(cp)) not in ("Cn", "Cs")]


_STARTS = [b[0] for b in BLOCKS]


def block_index(cp: int) -> int:
    i = bisect.bisect_right(_STARTS, cp) - 1
    return i if i >= 0 and BLOCKS[i][0] <= cp <= BLOCKS[i][1] else -1


# ---------------------------------------------------------------- facts for the info pane
def codepoints(text: str) -> str:
    return " ".join(f"U+{ord(c):04X}" for c in text)


def utf8(text: str) -> str:
    return " ".join(f"{b:02X}" for b in text.encode("utf-8", "surrogatepass"))


def entity(text: str) -> str:
    """HTML: the named entity when there is one (&rarr;), else numeric references."""
    if len(text) == 1 and ord(text) in html.entities.codepoint2name:
        return f"&{html.entities.codepoint2name[ord(text)]};"
    return "".join(f"&#x{ord(c):X};" for c in text)


def name_of(text: str, emoji: EmojiSet | None = None) -> str:
    """The emoji's name in the UI language, else the character's Unicode name."""
    e = emoji.get(text) if emoji else None
    if e:
        if text in emoji.variant_names:
            return emoji.variant_names[text]
        tone = next((TONES.index(c) + 1 for c in text if c in TONES), 0)
        return f"{e.name}: {tr('grimoire.spells.glyphl.data', TONE_NAMES[tone]).lower()}" if tone else e.name
    if len(text) != 1:
        return " + ".join(name_of(c) for c in text if c not in (VS16, ZWJ))[:200]
    n = unicodedata.name(text, "")
    if n:
        return n
    cat = unicodedata.category(text)
    if cat == "Cc":
        return tr("grimoire.spells.glyphl.data", "Control character")
    if cat == "Co":
        return tr("grimoire.spells.glyphl.data", "Private use character")
    return tr("grimoire.spells.glyphl.data", "Unnamed character")


def block_name(text: str) -> str:
    i = block_index(ord(text[0])) if text else -1
    return BLOCKS[i][2] if i >= 0 else ""


def invisible(text: str) -> bool:
    """Spaces, controls and format characters: drawn as their code point instead of nothing."""
    return len(text) == 1 and unicodedata.category(text) in ("Zs", "Zl", "Zp", "Cc", "Cf", "Co")


def combining(text: str) -> bool:
    return len(text) == 1 and unicodedata.category(text) in ("Mn", "Me", "Mc")
