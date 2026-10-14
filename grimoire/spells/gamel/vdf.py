# SPDX-License-Identifier: GPL-3.0-or-later
"""A small reader for Valve's text KeyValues files (libraryfolders.vdf, appmanifest_*.acf, localconfig.vdf).

    "key"  "value"            a string
    "key"  { ... }            a nested block (a dict)

Quotes are optional, `//` starts a comment, `[$WIN32]`-style conditions after a value are skipped, and a
repeated key keeps its last value. It never raises on odd input: whatever parsed before the problem is returned.
"""
from pathlib import Path

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
        return loads(Path(path).read_text(encoding="utf-8", errors="replace"))
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
