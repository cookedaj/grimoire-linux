# SPDX-License-Identifier: GPL-3.0-or-later
"""The music library (no Qt): audio files under the library folders (~/Music by default) with their tags.

Tags come from mutagen when it's installed (python3-mutagen), else from the file and folder names
("Artist/Album/01 Title.flac" or "Artist - Title.mp3"). A scan reuses the cached entry of every file whose size and
mtime didn't change, so a second scan of a big library only lists folders. Read-only: nothing here writes to your
music. Cover art bytes come from the file's embedded picture or a cover/folder/front image next to it.
"""
import json
import os
import re
import time
from pathlib import Path

from grimoire import paths
from grimoire.spells.playl import media

CACHE_FILE = paths.CACHE / "playl" / "library.json"
FOLDER_ART = ("cover", "folder", "front", "album", "albumart", "albumartsmall")
ART_EXT = (".jpg", ".jpeg", ".png", ".webp")
MAX_TRACKS = 50000
_count: int | None = None


def has_mutagen() -> bool:
    try:
        import mutagen  # noqa: F401
        return True
    except ImportError:
        return False


def _first(tags, key) -> str:
    try:
        v = tags.get(key)
    except (KeyError, ValueError, TypeError):
        return ""
    if isinstance(v, list):
        v = v[0] if v else ""
    return str(v).strip() if v else ""


def _number(text: str) -> int:
    m = re.match(r"\s*(\d+)", text or "")
    return int(m.group(1)) if m else 0


def _guess(path: Path, root: Path) -> dict:
    """Title/artist/album from names: Artist/Album/NN Title, or "Artist - Title"."""
    stem = path.stem
    track = 0
    m = re.match(r"^(\d{1,3})[\s.\-_]+(.+)$", stem)
    if m:
        track, stem = int(m.group(1)), m.group(2)
    artist, title = "", stem
    if " - " in stem:
        artist, title = (x.strip() for x in stem.split(" - ", 1))
    rel = path.parent.relative_to(root).parts if path.parent != root else ()
    album = rel[-1] if rel else ""
    if not artist and len(rel) >= 2:
        artist = rel[-2]
    return {"title": title, "artist": artist, "album": album, "albumartist": "", "track": track, "disc": 0,
            "year": "", "duration": 0.0}


def read_tags(path: Path, root: Path) -> dict:
    """Tags of one file (falls back to names for anything missing)."""
    info = _guess(path, root)
    if not has_mutagen():
        return info
    try:
        import mutagen
        f = mutagen.File(str(path), easy=True)
    except Exception:                     # mutagen raises many kinds on odd files; the names will do
        return info
    if f is None:
        return info
    tags = f.tags or {}
    for key, field in (("title", "title"), ("artist", "artist"), ("album", "album"), ("albumartist", "albumartist"),
                       ("date", "year")):
        v = _first(tags, key)
        if v:
            info[field] = v[:4] if field == "year" else v
    t, d = _number(_first(tags, "tracknumber")), _number(_first(tags, "discnumber"))
    info["track"] = t or info["track"]
    info["disc"] = d
    try:
        info["duration"] = float(f.info.length or 0)
    except (AttributeError, TypeError, ValueError):
        pass
    return info


def scan(roots: list[Path], progress=None) -> list[dict]:
    """Every audio file under roots with its tags; cached entries are reused when size and mtime match.
    progress(n) is called now and then from this (worker) thread."""
    old = {t["path"]: t for t in load_cache()}
    tracks, seen = [], set()
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if name.startswith(".") or Path(name).suffix.lower() not in media.AUDIO:
                    continue
                p = Path(dirpath) / name
                sp = str(p)
                if sp in seen:
                    continue
                seen.add(sp)
                try:
                    st = p.stat()
                except OSError:
                    continue
                prev = old.get(sp)
                if prev and prev.get("size") == st.st_size and prev.get("mtime") == int(st.st_mtime):
                    tracks.append(prev)
                else:
                    tracks.append({"path": sp, "size": st.st_size, "mtime": int(st.st_mtime), "root": str(root)}
                                  | read_tags(p, root))
                if progress and len(tracks) % 200 == 0:
                    progress(len(tracks))
                if len(tracks) >= MAX_TRACKS:
                    break
    save_cache(tracks)
    return tracks


def load_cache() -> list[dict]:
    try:
        data = json.loads(CACHE_FILE.read_text())
        return [t for t in data.get("tracks", []) if isinstance(t, dict) and isinstance(t.get("path"), str)]
    except (OSError, ValueError, AttributeError):
        return []


def save_cache(tracks: list[dict]):
    global _count
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"scanned": int(time.time()), "tracks": tracks}))
    tmp.replace(CACHE_FILE)
    _count = len(tracks)


def cached_count() -> int:
    """How many songs the last scan found (read once per process)."""
    global _count
    if _count is None:
        try:
            raw = CACHE_FILE.read_text()
            _count = raw.count('"path":')
        except OSError:
            _count = 0
    return _count


# ---------------------------------------------------------------- grouping
def album_key(t: dict) -> str:
    return f"{(t.get('albumartist') or t.get('artist') or '').lower()}\x1f{(t.get('album') or '').lower()}"


def sort_key(t: dict):
    return (t.get("disc") or 0, t.get("track") or 0, media._natural(t.get("title") or ""))


def albums(tracks: list[dict]) -> list[dict]:
    """[{key, title, artist, year, tracks: [...]}] sorted by artist then title; tracks in disc/track order."""
    groups: dict[str, dict] = {}
    for t in tracks:
        if not t.get("album"):
            continue
        g = groups.setdefault(album_key(t), {"key": album_key(t), "title": t["album"],
                                             "artist": t.get("albumartist") or t.get("artist") or "",
                                             "year": t.get("year") or "", "tracks": []})
        g["tracks"].append(t)
    for g in groups.values():
        g["tracks"].sort(key=sort_key)
        artists = {x.get("artist") for x in g["tracks"] if x.get("artist")}
        if not g["artist"] and len(artists) == 1:
            g["artist"] = artists.pop()
    return sorted(groups.values(), key=lambda g: (media._natural(g["artist"]), media._natural(g["title"])))


def artists(tracks: list[dict]) -> list[tuple[str, list[dict]]]:
    out: dict[str, list] = {}
    for t in tracks:
        out.setdefault(t.get("albumartist") or t.get("artist") or "", []).append(t)
    for v in out.values():
        v.sort(key=lambda t: (media._natural(t.get("album") or ""), *sort_key(t)))
    return sorted(out.items(), key=lambda kv: (kv[0] == "", media._natural(kv[0])))


def matches(t: dict, words: list[str]) -> bool:
    hay = " ".join(str(t.get(k) or "") for k in ("title", "artist", "album", "albumartist")).lower()
    return all(w in hay for w in words)


# ---------------------------------------------------------------- cover art
def art_bytes(path: str) -> bytes | None:
    """The picture embedded in an audio file, else a cover image in its folder; None when there's none."""
    data = _embedded(path) if has_mutagen() else None
    if data:
        return data
    folder = Path(path).parent
    try:
        names = {p.name.lower(): p for p in folder.iterdir() if p.suffix.lower() in ART_EXT}
    except OSError:
        return None
    for base in FOLDER_ART:
        for ext in ART_EXT:
            p = names.get(base + ext)
            if p:
                try:
                    return p.read_bytes()[:20_000_000]
                except OSError:
                    return None
    return None


def _embedded(path: str) -> bytes | None:
    try:
        import mutagen
        f = mutagen.File(path)
    except Exception:
        return None
    if f is None:
        return None
    pics = getattr(f, "pictures", None)                      # FLAC
    if pics:
        return pics[0].data
    tags = f.tags
    if tags is None:
        return None
    try:
        for k in tags.keys():
            if str(k).startswith("APIC"):                    # ID3 (mp3, aiff, wav)
                return tags[k].data
        if "covr" in tags and tags["covr"]:                  # MP4/M4A
            return bytes(tags["covr"][0])
        if "metadata_block_picture" in tags:                 # Ogg Vorbis/Opus
            import base64
            from mutagen.flac import Picture
            return Picture(base64.b64decode(tags["metadata_block_picture"][0])).data
        for k in tags.keys():
            if str(k).startswith("WM/Picture"):              # ASF/WMA
                v = tags[k][0].value
                return v[v.find(b"\xff\xd8"):] if b"\xff\xd8" in v else None
    except Exception:
        return None
    return None
