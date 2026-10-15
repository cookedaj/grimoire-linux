# SPDX-License-Identifier: GPL-3.0-or-later
"""MuraL community store: top items from the KDE Store (OCS API) and Wallhaven, installed on demand.

Nothing is downloaded until you press Install. Archives are extracted defensively (no absolute paths,
no "..", regular files only, size-capped) and only the recognised theme files are copied into place:

    kind        installs to                                   applied by
    plasma      ~/.local/share/plasma/desktoptheme/<dir>      MuraL Taskbar / Style
    colors      ~/.local/share/color-schemes/<name>.colors    MuraL Colors
    cursor      ~/.local/share/icons/<dir>                    MuraL Cursor
    icons       ~/.local/share/icons/<dir>                    MuraL Icons
    aurorae     ~/.local/share/aurorae/themes/<dir>           MuraL Windows
    splash      ~/.local/share/plasma/look-and-feel/<id>      MuraL Splash
    konsole     ~/.local/share/konsole/<name>.colorscheme     MuraL Terminal
    sddm        staged; copied to /usr/share/sddm/themes on Install (password prompt)
    plymouth    staged; copied to /usr/share/plymouth/themes on Install (password prompt)
    wallpaper   MuraL library (optionally converted to black & white)

install_from() does the unpacking and copying for both a download (install) and a file or folder you import
yourself (imports.py), so both get the same checks; imports are registered with item ids "import:<sha256 prefix>".
"""
import hashlib
import json
import os
import re
import stat
import shutil
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from configparser import ConfigParser
from dataclasses import asdict, dataclass, field
from pathlib import Path

from grimoire.i18n import tr, tr_noop
from grimoire.paths import CACHE, DATA, HOME

UA = {"User-Agent": "Grimoire-MuraL/0.1 (personal KDE customizer)"}
OCS = "https://api.kde-look.org/ocs/v1/content/data"
WALLHAVEN = "https://wallhaven.cc/api/v1/search"
STORE_CACHE = CACHE / "store"
DOWNLOADS = STORE_CACHE / "downloads"
STAGED = DATA / "mural" / "staged"
REGISTRY = DATA / "mural" / "store-installed.json"
MAX_ARCHIVE = 600 * 1024 * 1024
MAX_FILES = 100_000                # members in one archive / files in one imported folder
MAX_THUMB = 8 * 1024 * 1024
LIST_TTL = 6 * 3600
THUMB_TTL = 14 * 24 * 3600
_lock = threading.Lock()


@dataclass(frozen=True)
class Category:
    key: str
    title: str                    # tr_noop'd: shown with tr("grimoire.spells.mural.store", title)
    kind: str
    ocs: tuple = ()               # KDE Store category ids
    wallhaven: str = ""           # Wallhaven query (wallpapers only)


CATEGORIES = {
    "plasma": Category("plasma", tr_noop("grimoire.spells.mural.store", "Plasma styles"), "plasma", (104,)),
    "colors": Category("colors", tr_noop("grimoire.spells.mural.store", "Color schemes"), "colors", (112,)),
    "cursor": Category("cursor", tr_noop("grimoire.spells.mural.store", "Cursors"), "cursor", (107,)),
    "icons": Category("icons", tr_noop("grimoire.spells.mural.store", "Icon themes"), "icons", (132,)),
    "aurorae": Category("aurorae", tr_noop("grimoire.spells.mural.store", "Window decorations"), "aurorae", (717, 114)),
    "splash": Category("splash", tr_noop("grimoire.spells.mural.store", "Splash screens"), "splash", (716,)),
    "konsole": Category("konsole", tr_noop("grimoire.spells.mural.store", "Konsole color schemes"), "konsole", (462,)),
    "sddm": Category("sddm", tr_noop("grimoire.spells.mural.store", "Login themes (SDDM)"), "sddm", (101,)),
    "plymouth": Category("plymouth", tr_noop("grimoire.spells.mural.store", "Boot themes (Plymouth)"),
                         "plymouth", (108,)),
    "wallpaper": Category("wallpaper", tr_noop("grimoire.spells.mural.store", "KDE wallpapers"), "wallpaper", (299,)),
    "wallhaven-bw": Category("wallhaven-bw", tr_noop("grimoire.spells.mural.store", "Wallhaven · black & white anime"),
                             "wallpaper", wallhaven="anime monochrome"),
    "wallhaven-bc": Category("wallhaven-bc", tr_noop("grimoire.spells.mural.store", "Wallhaven · Black Clover"),
                             "wallpaper", wallhaven="Black Clover"),
}


@dataclass
class Item:
    id: str
    name: str
    author: str = ""
    downloads: int = 0
    score: int = 0                # 0..100
    preview: str = ""             # image URL
    summary: str = ""
    files: list = field(default_factory=list)   # [(url, filename, size_kb)]
    page: str = ""


# ---------------------------------------------------------------- networking
def _web(url: str) -> str:
    """Store data is untrusted: only fetch http(s) (urllib would also read file:// URLs off this machine)."""
    if urllib.parse.urlparse(url).scheme not in ("https", "http"):
        raise RuntimeError(tr("grimoire.spells.mural.store", "not a web address: {url}").format(url=url[:80]))
    return url


def _get(url: str, timeout=30, limit=64 * 1024 * 1024) -> bytes:
    req = urllib.request.Request(_web(url), headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError(tr("grimoire.spells.mural.store", "the download is larger than the safety limit"))
    return data


def _write(path: Path, data: bytes):
    """Write via a temporary name, so a reader on another thread never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _download(url: str, dest: Path, limit=MAX_ARCHIVE):
    req = urllib.request.Request(_web(url), headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = 0
        while chunk := r.read(1 << 16):
            total += len(chunk)
            if total > limit:
                raise RuntimeError(tr("grimoire.spells.mural.store", "the download is larger than the safety limit"))
            f.write(chunk)


def _list_cache(cat: Category, sort: str, search: str, page: int) -> Path:
    key = hashlib.sha1(json.dumps([cat.key, sort, search, page]).encode()).hexdigest()[:16]
    return STORE_CACHE / f"list-{key}.json"


def cached_top(cat: Category, sort: str = "down", search: str = "", page: int = 0) -> list[Item] | None:
    """The cached listing if it's younger than LIST_TTL, else None. Reads only the disk."""
    cache = _list_cache(cat, sort, search, page)
    try:
        if time.time() - cache.stat().st_mtime < LIST_TTL:
            return [Item(**d) for d in json.loads(cache.read_text())]
    except (OSError, ValueError, TypeError):
        pass
    return None


def top(cat: Category, sort: str = "down", search: str = "", page: int = 0, fresh: bool = False) -> list[Item]:
    """Top items (sort: down = most downloaded, high = best rated, new = newest). Cached for 6 h; fresh=True
    asks the store again (Refresh). When the store can't be reached an older cached listing is better than none."""
    if not fresh and (items := cached_top(cat, sort, search, page)) is not None:
        return items
    cache = _list_cache(cat, sort, search, page)
    try:
        items = _wallhaven(cat, sort, search, page) if cat.wallhaven else _ocs(cat, sort, search, page)
    except Exception as e:
        try:
            return [Item(**d) for d in json.loads(cache.read_text())]
        except (OSError, ValueError, TypeError):
            raise e from None
    _write(cache, json.dumps([asdict(i) for i in items]).encode())
    return items


def _ocs(cat, sort, search, page) -> list[Item]:
    params = {"categories": "x".join(map(str, cat.ocs)), "sortmode": sort, "pagesize": 100, "page": page,
              "format": "json"}
    if search:
        params["search"] = search
    data = json.loads(_get(OCS + "?" + urllib.parse.urlencode(params)))
    return [_ocs_item(d) for d in data.get("data", [])]


def _ocs_item(d: dict) -> Item:
    files = []
    for n in range(1, 30):
        link = d.get(f"downloadlink{n}")
        if not link:
            break
        files.append((link, d.get(f"downloadname{n}") or "", int(d.get(f"downloadsize{n}") or 0)))
    return Item(id=f"kde-{d['id']}", name=d.get("name", "?"), author=d.get("personid", ""),
                downloads=int(d.get("downloads") or 0), score=int(float(d.get("score") or 0)),
                preview=d.get("smallpreviewpic1") or d.get("previewpic1") or "",
                summary=re.sub(r"<[^>]+>", "", d.get("summary") or "")[:200], files=files,
                page=d.get("detailpage", ""))


def _wallhaven(cat, sort, search, page) -> list[Item]:
    sorting = {"down": "favorites", "high": "toplist", "new": "date_added"}.get(sort, "favorites")
    params = {"q": search or cat.wallhaven, "categories": "010", "purity": "100", "atleast": "1920x1080",
              "sorting": sorting, "page": page + 1}
    get = lambda p: json.loads(_get(WALLHAVEN + "?" + urllib.parse.urlencode({**params, "page": p})))
    first = get(params["page"])                   # 24/page → ~96: the other three pages at once, not in turn
    last = min(params["page"] + 3, int(first.get("meta", {}).get("last_page", 1) or 1))
    with ThreadPoolExecutor(3) as ex:
        rest = list(ex.map(get, range(params["page"] + 1, last + 1)))
    return [_wh_item(d) for data in (first, *rest) for d in data.get("data", [])]


def _wh_item(d: dict) -> Item:
    return Item(id=f"wh-{d['id']}", name=f"{d['id']} · {d['resolution']}", author="wallhaven",
                downloads=int(d.get("favorites") or 0), preview=d["thumbs"]["small"],
                summary=f"{d['resolution']} · {int(d.get('file_size', 0)) // 1024} KB",
                files=[(d["path"], d["path"].rsplit("/", 1)[-1], int(d.get("file_size", 0)) // 1024)],
                page=d.get("url", ""))


def fetch(item_id: str) -> Item:
    """One store item by its id ("kde-123", "wh-abc"), e.g. one a shared setup refers to. Raises RuntimeError."""
    if m := re.fullmatch(r"kde-(\d{1,12})", item_id):
        data = json.loads(_get(f"{OCS}/{m[1]}?format=json")).get("data") or []
        if data:
            return _ocs_item(data[0])
    elif m := re.fullmatch(r"wh-([a-z0-9]{1,16})", item_id):
        data = json.loads(_get(f"https://wallhaven.cc/api/v1/w/{m[1]}")).get("data")
        if isinstance(data, dict):
            return _wh_item(data)
    raise RuntimeError(tr("grimoire.spells.mural.store", "the store doesn't have {item} any more")
                       .format(item=item_id[:40]))


def thumb_path(url: str) -> Path:
    suffix = re.sub(r"[^A-Za-z0-9.]", "", Path(urllib.parse.urlparse(url).path).suffix)[:5]
    return STORE_CACHE / "thumbs" / (hashlib.sha1(url.encode()).hexdigest() + suffix)


def thumbnail(url: str) -> Path | None:
    """Cached preview image for a store item (kept THUMB_TTL; an older copy is used if the store is unreachable)."""
    if not url:
        return None
    path = thumb_path(url)
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        age = None
    if age is None or age > THUMB_TTL:
        try:
            _write(path, _get(url, timeout=20, limit=MAX_THUMB))
        except (OSError, RuntimeError, ValueError):
            return path if age is not None else None
    return path


# ---------------------------------------------------------------- registry
def registry() -> dict:
    try:
        return json.loads(REGISTRY.read_text())
    except (OSError, ValueError):
        return {}


def installed(cat_kind: str) -> list[dict]:
    """[{item, name, ident, path, preview}] for this kind, newest first."""
    return [e for e in registry().values() if e["kind"] == cat_kind][::-1]


def _record(entry: dict):
    with _lock:
        reg = registry()
        reg[entry["key"]] = entry
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(json.dumps(reg, indent=2))


def is_installed(item_id: str) -> bool:
    return any(e["item"] == item_id for e in registry().values())


def uninstall(key: str):
    with _lock:
        reg = registry()
        entry = reg.pop(key, None)
        REGISTRY.write_text(json.dumps(reg, indent=2))
    if entry:
        p = Path(entry["path"])
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------- safe extraction
class Unusable(RuntimeError):
    """Nothing in the archive or folder was a theme of the kind asked for."""


def _fresh(folder: Path) -> Path:
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    return folder


def _unsafe(name: str) -> RuntimeError:
    return RuntimeError(tr("grimoire.spells.mural.store", "unsafe path in the archive: {path}").format(path=name[:120]))


def _too_large() -> RuntimeError:
    return RuntimeError(tr("grimoire.spells.mural.store", "the archive expands too large"))


def _extract(archive: Path, dest: Path) -> Path:
    """Extract into dest (fresh dir). Rejects absolute paths, '..', links and huge expansions."""
    _fresh(dest)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            members = z.infolist()
            if len(members) > MAX_FILES:
                raise _too_large()
            total, top = 0, dest.resolve()
            for info in members:
                parts = Path(info.filename).parts
                if info.filename.startswith("/") or ".." in parts:
                    raise _unsafe(info.filename)
                if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):    # links: never followed or made
                    continue
                target = dest / info.filename
                if not target.resolve().is_relative_to(top):
                    raise _unsafe(info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(target, "wb") as out:    # count real bytes: sizes can lie
                    while chunk := src.read(1 << 16):
                        total += len(chunk)
                        if total > MAX_ARCHIVE * 3:
                            raise _too_large()
                        out.write(chunk)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as t:
            members = []
            for m in t:                            # streams: a member bomb stops here, not after reading all
                members.append(m)
                if len(members) > MAX_FILES:
                    raise _too_large()
            if sum(m.size for m in members) > MAX_ARCHIVE * 3:
                raise _too_large()
            for m in members:
                if m.name.startswith("/") or ".." in Path(m.name).parts:
                    raise _unsafe(m.name)
            # Python's "data" filter: no links that leave dest, no devices, no setuid bits. Links inside the theme
            # stay (icon themes are full of them); the copy into place turns them into plain files.
            try:
                t.extractall(dest, members=members, filter="data")
            except tarfile.FilterError as e:      # a link leaving the theme, a device, an absolute link…
                raise _unsafe(getattr(e.tarinfo, "name", "")) from None
    else:                                          # a plain file (.colors, .colorscheme, an image…)
        if archive.stat().st_size > MAX_ARCHIVE:
            raise _too_large()
        shutil.copy(archive, dest / archive.name)
    return dest


def _copy_folder(src: Path, dest: Path) -> Path:
    """Copy a folder you picked into dest (fresh dir), the way _extract treats an archive: regular files only,
    links copied only when they point at a file inside the folder (icon themes are full of those), capped."""
    _fresh(dest)
    top, total, count = src.resolve(), 0, 0
    for here, dirs, files in os.walk(top, followlinks=False):
        rel = Path(here).relative_to(top)
        dirs[:] = [d for d in dirs if not (Path(here) / d).is_symlink()]
        for name in files:
            p = Path(here) / name
            real = p.resolve()
            if not real.is_relative_to(top) or not stat.S_ISREG(real.stat().st_mode if real.exists() else 0):
                continue
            count += 1
            total += real.stat().st_size
            if count > MAX_FILES or total > MAX_ARCHIVE * 3:
                raise _too_large()
            (dest / rel).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real, dest / rel / name)
    return dest


def _pick_file(item: Item) -> tuple[str, str]:
    """Choose which of an item's files to download (prefer archives / matching extensions)."""
    if not item.files:
        raise RuntimeError(tr("grimoire.spells.mural.store", "this item has no downloadable file"))
    prefs = (".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar", ".zip", ".colors", ".colorscheme",
             ".plasmoid", ".knsrc", ".png", ".jpg", ".jpeg", ".webp")
    for ext in prefs:
        for url, fname, _ in item.files:
            if fname.lower().endswith(ext):
                return url, fname
    return item.files[0][0], item.files[0][1] or "download"


# ---------------------------------------------------------------- install per kind
def _dirs_with(root: Path, predicate) -> list[Path]:
    return [d for d in [root, *sorted(p for p in root.rglob("*") if p.is_dir())] if predicate(d)]


def _ini(path: Path) -> ConfigParser:
    c = ConfigParser(interpolation=None, strict=False)
    c.optionxform = str
    try:
        c.read(path, encoding="utf-8")
    except Exception:
        pass
    return c


def _claim(dst: Path, item: str):
    """Refuse to replace something Grimoire didn't install for this item (your own theme with the same folder
    name, or another store item's)."""
    if dst.exists() or dst.is_symlink():
        owners = {e.get("item") for e in registry().values() if e["path"] == str(dst)}
        if item not in owners:
            raise RuntimeError(tr("grimoire.spells.mural.store", "you already have “{name}” in {folder}; "
                                  "Grimoire won't replace it").format(name=dst.name, folder=dst.parent))


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(text)).strip("._")[:80]


def _copyfile(src: Path, dst: Path, item: str):
    _claim(dst, item)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)


def _copytree(src: Path, dst: Path, item: str):
    if dst.resolve().parent != dst.parent.resolve():
        raise RuntimeError(tr("grimoire.spells.mural.store", "unsafe theme name: {name}").format(name=dst.name))
    _claim(dst, item)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns("*.sh", "*.py", "install*"))


def install(cat: Category, item: Item, to_bw: bool = False) -> list[dict]:
    """Download + install one store item. Returns the registry entries created."""
    url, fname = _pick_file(item)
    work = _fresh(DOWNLOADS / (_slug(item.id) or "item"))  # ids come from the store: never let one be a path
    try:
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", fname)[:120] or "download"
        archive = work / safe_name
        _download(url, archive)
        try:
            return install_from(cat.kind, archive, item.id, item.name, item.author,
                                str(thumbnail(item.preview) or ""), to_bw, work)
        except Unusable:
            raise RuntimeError(tr("grimoire.spells.mural.store",
                                  "didn't find a usable theme inside this download")) from None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _inner_preview(d: Path) -> str:
    """A preview picture a theme ships (look-and-feel previews, SDDM's Screenshot=, preview.png…), or ""."""
    names = []
    if (d / "metadata.desktop").is_file():
        names.append(_ini(d / "metadata.desktop").get("SddmGreeterTheme", "Screenshot", fallback=""))
    names += ["contents/previews/splash.png", "contents/previews/preview.png",
              "contents/previews/fullscreenpreview.jpg",
              "preview.png", "preview.jpg", "screenshot.png", "screenshot.jpg", "Preview.png", "Screenshot.png"]
    for n in filter(None, names):
        p = (d / n).resolve()
        if p.is_relative_to(d.resolve()) and p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            return str(p)
    return ""


def install_from(kind: str, source: Path, item_id: str, name: str, author: str = "", preview: str = "",
                 to_bw: bool = False, work: Path | None = None) -> list[dict]:
    """Install a theme of `kind` from an archive, a plain theme file or a folder. Store downloads and your own
    imports both come here, so they get the same checks. Raises Unusable when nothing of that kind is inside."""
    item_slug = _slug(item_id) or "item"
    work = work or DOWNLOADS / item_slug
    source = Path(source)
    root = _copy_folder(source, work / "x") if source.is_dir() else _extract(source, work / "x")
    entries = []

    def add(name, ident, path):
        pic = preview or (_inner_preview(Path(path)) if Path(path).is_dir() else "")
        e = {"key": f"{kind}:{ident}", "item": item_id, "kind": kind, "name": name, "ident": ident,
             "path": str(path), "preview": pic, "author": author}
        _record(e)
        entries.append(e)

    k = kind

    def folder(d: Path) -> str:               # a flat archive's root is the work folder, not a theme name
        return d.name if d != root else (_slug(name) or item_slug)
    if k == "colors":
        for f in root.rglob("*.colors"):
            dst = HOME / ".local/share/color-schemes" / f.name
            _copyfile(f, dst, item_id)
            add(_ini(f).get("General", "Name", fallback=f.stem), f.stem, dst)
    elif k == "konsole":
        for f in root.rglob("*.colorscheme"):
            dst = HOME / ".local/share/konsole" / f.name
            _copyfile(f, dst, item_id)
            add(_ini(f).get("General", "Description", fallback=f.stem), f.stem, dst)
    elif k == "cursor":
        for d in _dirs_with(root, lambda d: (d / "cursors").is_dir()):
            dst = HOME / ".local/share/icons" / folder(d)
            _copytree(d, dst, item_id)
            add(_ini(d / "index.theme").get("Icon Theme", "Name", fallback=folder(d)), folder(d), dst)
    elif k == "icons":
        for d in _dirs_with(root, lambda d: (d / "index.theme").is_file()
                            and _ini(d / "index.theme").has_option("Icon Theme", "Directories")):
            dst = HOME / ".local/share/icons" / folder(d)
            _copytree(d, dst, item_id)
            add(_ini(d / "index.theme").get("Icon Theme", "Name", fallback=folder(d)), folder(d), dst)
    elif k == "plasma":
        for d in _dirs_with(root, lambda d: ((d / "metadata.json").is_file() or (d / "metadata.desktop").is_file())
                            and ((d / "widgets").is_dir() or (d / "colors").is_file() or (d / "dialogs").is_dir())):
            dst = HOME / ".local/share/plasma/desktoptheme" / folder(d)
            _copytree(d, dst, item_id)
            add(name if d == root else d.name, folder(d), dst)
    elif k == "aurorae":
        for d in _dirs_with(root, lambda d: any(d.glob("decoration.svg*"))):
            dst = HOME / ".local/share/aurorae/themes" / folder(d)
            _copytree(d, dst, item_id)
            add(folder(d), folder(d), dst)
    elif k == "splash":
        for d in _dirs_with(root, lambda d: (d / "contents/splash").is_dir()):
            meta = d / "metadata.json"
            ident = folder(d)
            if meta.is_file():
                try:
                    ident = _slug(json.loads(meta.read_text())["KPlugin"]["Id"]) or ident   # never a path
                except (ValueError, KeyError, TypeError):
                    pass
            dst = HOME / ".local/share/plasma/look-and-feel" / ident
            _copytree(d, dst, item_id)
            add(name, ident, dst)
    elif k == "sddm":
        for d in _dirs_with(root, lambda d: (d / "metadata.desktop").is_file() and (d / "Main.qml").is_file()):
            ident = _slug(folder(d)) or item_slug
            dst = STAGED / "sddm" / ident
            _copytree(d, dst, item_id)
            add(_ini(d / "metadata.desktop").get("SddmGreeterTheme", "Name", fallback=d.name), ident, dst)
    elif k == "plymouth":
        for d in _dirs_with(root, lambda d: any(d.glob("*.plymouth"))):
            ident = re.sub(r"[^A-Za-z0-9._-]", "_", next(d.glob("*.plymouth")).stem)
            dst = STAGED / "plymouth" / ident
            _copytree(d, dst, item_id)
            add(_ini(next(d.glob("*.plymouth"))).get("Plymouth Theme", "Name", fallback=ident), ident, dst)
    elif k == "wallpaper":
        from grimoire.spells.mural import library
        images = [p for p in root.rglob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
                  and p.stat().st_size > 50_000]
        images.sort(key=lambda p: p.stat().st_size, reverse=True)
        for p in images[:1]:                       # the largest image = the actual wallpaper
            dst = library.LIBRARY / f"{item_slug}{p.suffix.lower()}"
            if to_bw:
                from PIL import Image, ImageOps
                ImageOps.autocontrast(Image.open(p).convert("L"), cutoff=1).save(dst.with_suffix(".png"))
                dst = dst.with_suffix(".png")
            else:
                shutil.copy(p, dst)
            add(name, dst.name, dst)
    if not entries:
        raise Unusable(kind)
    return entries
