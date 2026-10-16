# SPDX-License-Identifier: GPL-3.0-or-later
"""The vault in memory: every note's text, tags and links, for the sidebar, search, backlinks and [[link]] lookups.
No Qt; built on a worker thread.

scan() walks the vault (hidden folders like .obsidian, .git and .trash are skipped, symlinked folders aren't followed)
and returns a new immutable Snapshot; unchanged files (same mtime and size) reuse the previous snapshot's parse, so a
rescan only reads what changed. search() runs on a snapshot, also off the UI thread.
"""
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from grimoire.spells.notel import store

MAX_FILES = 20000            # notes and attachments together; a home folder picked by mistake stays responsive
MAX_INDEX = 2 << 20          # bigger notes are listed but their text isn't searched
MAX_DIRS = 4000


@dataclass(frozen=True)
class Note:
    path: Path
    rel: str                 # relative to the vault, with "/"
    mtime: float
    size: int
    text: str = ""
    low: str = ""            # text lowercased, for search
    tags: frozenset = frozenset()
    links: tuple = ()        # link targets as written

    @property
    def title(self) -> str:
        return self.path.stem if store.is_markdown(self.path) else self.path.name


@dataclass
class Snapshot:
    root: Path
    notes: dict = field(default_factory=dict)          # rel -> Note
    folders: list = field(default_factory=list)        # rel paths of every folder, sorted
    files: dict = field(default_factory=dict)          # lowercased file name -> [Path] (attachments: images…)
    by_key: dict = field(default_factory=dict)         # link key (rel without .md, lowercased) -> rel
    by_stem: dict = field(default_factory=dict)        # lowercased name without .md -> [rel] (shortest first)
    backlinks: dict = field(default_factory=dict)      # rel -> [rel of notes linking to it]
    tags: Counter = field(default_factory=Counter)
    truncated: bool = False

    def resolve(self, target: str, source: str = "") -> str | None:
        """The note a link points to (Obsidian's rules: a path from the vault root or from the linking note's folder,
        else the closest note with that name), or None."""
        key = store.link_key(target)
        if not key:
            return None
        if source and "/" in source:
            here = source.rsplit("/", 1)[0].lower()
            rel = os.path.normpath(f"{here}/{key}").replace("\\", "/")
            if rel in self.by_key:
                return self.by_key[rel]
        if key in self.by_key:
            return self.by_key[key]
        name = key.rsplit("/", 1)[-1]
        hits = self.by_stem.get(name, [])
        if "/" in key:
            hits = [h for h in hits if store.link_key(h) == key or store.link_key(h).endswith("/" + key)]
        return hits[0] if hits else None

    def resolve_file(self, target: str, source: str = "") -> Path | None:
        """An attachment (an image for ![[pic.png]] or ![](pic.png)): next to the note, from the root, or by name."""
        target = target.strip().replace("\\", "/")
        if not target or target.startswith("/") or ".." in target.split("/"):
            return None
        bases = []
        if source:
            bases.append((self.root / source).parent)
        bases.append(self.root)
        for b in bases:
            p = b / target
            if p.is_file() and store.in_vault(p, self.root):
                return p
        hits = self.files.get(target.rsplit("/", 1)[-1].lower(), [])
        return hits[0] if hits else None

    def sorted_notes(self) -> list:
        return sorted(self.notes.values(), key=lambda n: n.rel.lower())

    def recent(self, n=1) -> list:
        return sorted(self.notes.values(), key=lambda x: -x.mtime)[:n]


def _walk(root: Path):
    """(notes: [(rel, path, stat)], folders: [rel], files: [(path)], truncated)."""
    notes, folders, files = [], [], []
    stack = [(root, "")]
    count = 0
    truncated = False
    while stack:
        d, rel = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            if e.name.startswith("."):
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    if len(folders) < MAX_DIRS:
                        sub = f"{rel}/{e.name}" if rel else e.name
                        folders.append(sub)
                        stack.append((Path(e.path), sub))
                    else:
                        truncated = True
                    continue
                if not e.is_file():
                    continue
            except OSError:
                continue
            count += 1
            if count > MAX_FILES:
                truncated = True
                continue
            low = e.name.lower()
            if low.endswith(store.NOTE_EXT):
                try:
                    st = e.stat()
                except OSError:
                    continue
                notes.append((f"{rel}/{e.name}" if rel else e.name, Path(e.path), st))
            elif low.endswith(store.IMAGE_EXT):
                files.append(Path(e.path))
    return notes, folders, files, truncated


def _read(path: Path, size: int) -> str:
    if size > MAX_INDEX:
        return ""
    try:
        with open(path, "rb") as f:
            data = f.read(MAX_INDEX)
        return store.decode(data)[0]
    except (OSError, store.NotText):
        return ""


def scan(root: Path, previous: Snapshot | None = None) -> Snapshot:
    notes, folders, files, truncated = _walk(root)
    old = previous.notes if previous and previous.root == root else {}
    snap = Snapshot(root=root, truncated=truncated)
    for rel, path, st in notes:
        prev = old.get(rel)
        if prev and prev.mtime == st.st_mtime and prev.size == st.st_size:
            snap.notes[rel] = prev
            continue
        text = _read(path, st.st_size)
        tags, links = store.parse(text) if store.is_markdown(path) else (set(), [])
        snap.notes[rel] = Note(path, rel, st.st_mtime, st.st_size, text, text.lower(), frozenset(tags), tuple(links))
    snap.folders = sorted(folders, key=str.lower)
    for p in files:
        snap.files.setdefault(p.name.lower(), []).append(p)
    _link_up(snap)
    return snap


def _link_up(snap: Snapshot):
    for rel in snap.notes:
        if store.is_markdown(Path(rel)):
            key = store.link_key(rel)
            snap.by_key[key] = rel
            snap.by_stem.setdefault(key.rsplit("/", 1)[-1], []).append(rel)
        else:
            snap.by_key.setdefault(rel.lower(), rel)
    for hits in snap.by_stem.values():
        hits.sort(key=lambda r: (r.count("/"), len(r), r.lower()))
    back: dict[str, set] = {}
    for rel, note in snap.notes.items():
        for t in note.links:
            hit = snap.resolve(t, rel)
            if hit and hit != rel:
                back.setdefault(hit, set()).add(rel)
        snap.tags.update(note.tags)
    snap.backlinks = {k: sorted(v, key=str.lower) for k, v in back.items()}


def with_note(snap: Snapshot, path: Path, text: str) -> Snapshot:
    """The snapshot with one note's text replaced (after NoteL saved it), without touching the disk."""
    try:
        rel = path.resolve().relative_to(snap.root.resolve()).as_posix()
        st = os.stat(path)
    except (ValueError, OSError):
        return snap
    tags, links = store.parse(text) if store.is_markdown(path) else (set(), [])
    new = Snapshot(root=snap.root, notes=dict(snap.notes), folders=snap.folders, files=snap.files,
                   truncated=snap.truncated)
    big = st.st_size > MAX_INDEX
    new.notes[rel] = Note(snap.root / rel, rel, st.st_mtime, st.st_size, "" if big else text,
                          "" if big else text.lower(), frozenset(tags), tuple(links))
    _link_up(new)
    return new


# ---------------------------------------------------------------- search
@dataclass
class Hit:
    note: Note
    score: float
    lines: list              # [(line number from 1, line text)]


TERM = re.compile(r'"([^"]+)"|(\S+)')


def terms(query: str) -> tuple[list[str], list[str]]:
    """(words and "quoted phrases", #tags) of a query, lowercased."""
    words, tags = [], []
    for m in TERM.finditer(query.lower()):
        t = m.group(1) or m.group(2)
        if m.group(2) and t.startswith("#") and len(t) > 1:
            tags.append(t[1:].rstrip("/"))
        elif t.strip():
            words.append(t.strip())
    return words, tags


def _has_tag(note: Note, tag: str) -> bool:
    return any(t == tag or t.startswith(tag + "/") for t in note.tags)


def search(snap: Snapshot, query: str, limit: int = 200, snippets: int = 3) -> list[Hit]:
    """Notes with every word (in the name or the text) and every #tag of query, best first: words in the name count
    more, then how often they appear, then the newest."""
    words, tags = terms(query)
    if not words and not tags:
        return []
    hits = []
    for note in snap.notes.values():
        if tags and not all(_has_tag(note, t) for t in tags):
            continue
        name = note.rel.lower()
        score = 0.0
        ok = True
        for w in words:
            in_name = w in name
            count = note.low.count(w)
            if not in_name and not count:
                ok = False
                break
            score += (10 if in_name else 0) + min(count, 20)
        if not ok:
            continue
        hits.append((score, note.mtime, note))
    hits.sort(key=lambda h: (-h[0], -h[1]))
    out = []
    for score, _, note in hits[:limit]:
        out.append(Hit(note, score, _lines(note, words, tags, snippets)))
    return out


def _lines(note: Note, words: list, tags: list, most: int) -> list:
    needles = words + ["#" + t for t in tags]
    found = []
    if not needles or not note.low:
        return found
    original = note.text.split("\n")           # lower() keeps the line breaks, so the lines line up
    for i, line in enumerate(note.low.split("\n")):
        at = min((line.find(n) for n in needles if n in line), default=-1)
        if at >= 0:
            text = original[i] if i < len(original) else ""
            start = max(0, at - 24) if at > 40 else 0         # the match stays in view in a narrow list
            found.append((i + 1, ("…" if start else "") + text[start:].strip()[:240]))
            if len(found) >= most:
                break
    return found
