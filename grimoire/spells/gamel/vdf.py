# SPDX-License-Identifier: GPL-3.0-or-later
"""Small readers for Valve's KeyValues files: the text ones (libraryfolders.vdf, appmanifest_*.acf, localconfig.vdf)
and the binary one non-Steam shortcuts live in (userdata/*/config/shortcuts.vdf, see loads_binary).

    "key"  "value"            a string
    "key"  { ... }            a nested block (a dict)

Quotes are optional, `//` starts a comment, `[$WIN32]`-style conditions after a value are skipped, and a
repeated key keeps its last value. It never raises on odd input: whatever parsed before the problem is returned.
Nesting is walked without recursion, and files over MAX_BYTES are read only up to it.
"""
import struct
from pathlib import Path

MAX_BYTES = 64 * 1024 * 1024                               # Steam's own files are a few MB at most

_ESC = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


def _tokens(text: str):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == "/" and text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
        elif c in "{}":
            yield c, True
            i += 1
        elif c == "[":                                     # a platform condition: ignore it
            j = text.find("]", i)
            i = n if j < 0 else j + 1
        elif c == '"':
            out, i = [], i + 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    out.append(_ESC.get(text[i + 1], "\\" + text[i + 1]))
                    i += 2
                else:
                    out.append(text[i])
                    i += 1
            yield "".join(out), False
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '{}"':
                j += 1
            yield text[i:j], False
            i = j


def loads(text: str) -> dict:
    root: dict = {}
    stack = [root]
    key = None
    for tok, brace in _tokens(text):
        if brace and tok == "{":
            child: dict = {}
            if key is not None:
                stack[-1][key] = child
            stack.append(child)
            key = None
        elif brace:                                        # "}"
            if len(stack) > 1:
                stack.pop()
            key = None
        elif key is None:
            key = tok
        else:
            stack[-1][key] = tok
            key = None
    return root


def load(path: Path) -> dict:
    """{} when the file is missing or unreadable."""
    try:
        with open(path, "rb") as f:
            return loads(f.read(MAX_BYTES).decode("utf-8", errors="replace"))
    except OSError:
        return {}


def find(d: dict, *keys: str):
    """d[k1][k2]… with keys matched without case (Steam writes both "Software" and "software"); None if absent."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        hit = d.get(k)
        if hit is None:
            low = k.lower()
            hit = next((v for kk, v in d.items() if kk.lower() == low), None)
        d = hit
    return d


def block(d: dict, *keys: str) -> dict:
    """find() for a nested block: {} when it's missing or a plain string (an odd file must not break the reader)."""
    hit = find(d, *keys)
    return hit if isinstance(hit, dict) else {}


# ---------------------------------------------------------------- binary
# Each entry: a type byte, a NUL-ended key, then its value. 0x00 opens a nested map, 0x08 closes one.
_B_MAP, _B_STR, _B_INT, _B_FLOAT, _B_PTR, _B_WSTR, _B_COLOR, _B_U64, _B_END, _B_I64, _B_END2 = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11)
_FIXED = {_B_INT: ("<i", 4), _B_FLOAT: ("<f", 4), _B_PTR: ("<I", 4), _B_COLOR: ("<I", 4), _B_U64: ("<Q", 8),
          _B_I64: ("<q", 8)}


def loads_binary(data: bytes) -> dict:
    """The binary KeyValues format. Like loads(), it never raises: an unknown type or a cut-off file ends the
    read and returns what came before. Strings are UTF-8 (odd bytes replaced); nesting is walked without recursion."""
    root: dict = {}
    stack = [root]
    i, n = 0, len(data)

    def cstr(at: int) -> tuple[str, int]:
        j = data.find(b"\0", at)
        if j < 0:
            raise IndexError
        return data[at:j].decode("utf-8", errors="replace"), j + 1

    try:
        while i < n:
            t = data[i]
            i += 1
            if t in (_B_END, _B_END2):
                if len(stack) == 1:
                    break
                stack.pop()
                continue
            key, i = cstr(i)
            if t == _B_MAP:
                child: dict = {}
                stack[-1][key] = child
                stack.append(child)
            elif t == _B_STR:
                stack[-1][key], i = cstr(i)
            elif t == _B_WSTR:                             # UTF-16LE, ended by two NULs
                j = i
                while j + 1 < n and data[j:j + 2] != b"\0\0":
                    j += 2
                if j + 1 >= n:
                    break
                stack[-1][key] = data[i:j].decode("utf-16-le", errors="replace")
                i = j + 2
            elif t in _FIXED:
                fmt, size = _FIXED[t]
                if i + size > n:
                    break
                stack[-1][key] = struct.unpack_from(fmt, data, i)[0]
                i += size
            else:
                break
    except IndexError:
        pass
    return root


def load_binary(path: Path) -> dict:
    """{} when the file is missing or unreadable."""
    try:
        with open(path, "rb") as f:
            return loads_binary(f.read(MAX_BYTES))
    except OSError:
        return {}
