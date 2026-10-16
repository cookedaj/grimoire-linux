# SPDX-License-Identifier: GPL-3.0-or-later
"""GE-Proton, the way ProtonUp-Qt does it: the releases on GitHub, the builds in Steam's compatibilitytools.d (the
normal Steam's and the Flatpak one's), and which games Steam was told to run with which tool. No Qt.

Nothing is downloaded until install() is called (the page's Install button). A build is checked against the
.sha512sum file of its release (and GitHub's own sha256 digest when the API gives one) before it's unpacked;
unpacking is defensive (one top folder named like the release, relative names, files/folders/links only, links that
stay inside, size-capped, then Python's "data" filter) into a hidden folder that's renamed into place at the end.
Removing a build moves it to the Trash. OPEN is the one place the network is reached, so tests swap it.
"""
import hashlib
import json
import platform
import re
import shutil
import tarfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from grimoire.fsutil import trash
from grimoire.i18n import tr
from grimoire.paths import CACHE
from grimoire.spells.gamel import library, vdf

REPO = "GloriousEggroll/proton-ge-custom"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=12"
UA = {"User-Agent": "Grimoire-Linux-GameL", "Accept": "application/vnd.github+json"}
TAG_RE = re.compile(r"^GE-Proton\d{1,3}-\d{1,4}(-rc\d{0,3})?$")
LIST_TTL = 3600                                  # GitHub allows 60 unauthenticated API calls an hour
MAX_DOWNLOAD = 3 * 1024 ** 3                     # builds are ~0.6 GB
MAX_EXPANDED = 10 * 1024 ** 3
MAX_MEMBERS = 200_000


class ProtonError(Exception):
    pass


class Cancelled(ProtonError):
    pass


@dataclass
class Release:
    tag: str
    date: str                   # ISO, from GitHub
    url: str                    # the .tar.gz
    size: int
    sha_url: str                # the .sha512sum
    sha256: str = ""            # GitHub's digest of the .tar.gz, when it gives one
    notes: str = ""

    @property
    def asset(self) -> str:
        return self.url.rsplit("/", 1)[-1]


@dataclass
class Tool:
    name: str                   # Steam's internal name (what CompatToolMapping uses)
    display: str
    path: str                   # its folder ("" for Steam's own, which Steam manages)
    target: str                 # the compatibilitytools.d it's in, or Steam's library folder
    flatpak: bool = False
    steam: bool = False         # one of Valve's (Proton Experimental, Proton 9.0…): installed and removed by Steam


def _open(url: str, headers: dict, timeout: float):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


OPEN = _open


def _cache() -> Path:
    return CACHE / "gamel"


# ---------------------------------------------------------------- releases
def _release_url(url: str, tag: str) -> bool:
    """Only files of this repo's release with this tag (the API's answer is data like any other)."""
    u = urlparse(url)
    return (u.scheme == "https" and u.hostname == "github.com"
            and u.path.startswith(f"/{REPO}/releases/download/{tag}/") and u.path.count("/") == 6)


def _arch() -> str:
    m = platform.machine().lower()
    return "aarch64" if m in ("aarch64", "arm64") else "x86_64"


def parse_releases(data) -> list[Release]:
    out = []
    for r in data if isinstance(data, list) else []:
        if not isinstance(r, dict) or r.get("draft"):
            continue
        tag = str(r.get("tag_name") or "")
        if not TAG_RE.match(tag):
            continue
        assets = {str(a.get("name")): a for a in r.get("assets") or [] if isinstance(a, dict)}
        for base in (f"{tag}-{_arch()}", tag):          # newer releases name the architecture
            tar, sha = assets.get(base + ".tar.gz"), assets.get(base + ".sha512sum")
            if tar and sha:
                break
        else:
            continue
        url, sha_url = str(tar.get("browser_download_url") or ""), str(sha.get("browser_download_url") or "")
        if not (_release_url(url, tag) and _release_url(sha_url, tag)):
            continue
        digest = str(tar.get("digest") or "")
        sha256 = digest[7:].lower() if digest.startswith("sha256:") else ""
        out.append(Release(tag, str(r.get("published_at") or ""), url, library._int(tar.get("size")), sha_url,
                           sha256 if re.fullmatch(r"[0-9a-f]{64}", sha256) else "", str(r.get("body") or "")[:4000]))
    return out


def releases(force: bool = False) -> list[Release]:
    """The latest GE-Proton releases. Cached for an hour; a refresh sends the ETag, so an unchanged list costs
    nothing against GitHub's limit. Raises ProtonError with a message for the page."""
    f = _cache() / "proton-releases.json"
    try:
        cached = json.loads(f.read_text())
        if not isinstance(cached, dict):
            cached = {}
    except (OSError, ValueError):
        cached = {}
    if not force and cached.get("data") is not None and time.time() - library._int(cached.get("at")) < LIST_TTL:
        return parse_releases(cached["data"])
    headers = dict(UA)
    if cached.get("etag") and cached.get("data") is not None:
        headers["If-None-Match"] = str(cached["etag"])
    try:
        with OPEN(API, headers, 20) as r:
            body, etag = r.read(4 * 1024 * 1024), r.headers.get("ETag", "")
        data = json.loads(body)
    except urllib.error.HTTPError as e:
        if e.code == 304:
            data, etag = cached["data"], cached.get("etag", "")
        elif e.code in (403, 429):
            reset = e.headers.get("X-RateLimit-Reset") if e.headers else None
            if (reset or "").isdigit():
                raise ProtonError(tr("grimoire.spells.gamel.proton", "GitHub's hourly limit is used up; try again "
                                     "after {time}.").format(time=time.strftime("%H:%M", time.localtime(int(reset)))))
            raise ProtonError(tr("grimoire.spells.gamel.proton", "GitHub's hourly limit is used up; try again later."))
        else:
            raise ProtonError(tr("grimoire.spells.gamel.proton", "GitHub answered {code}.").format(code=e.code))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if cached.get("data") is not None:
            return parse_releases(cached["data"])
        raise ProtonError(tr("grimoire.spells.gamel.proton", "Couldn't reach GitHub (offline?): {reason}").format(
            reason=getattr(e, "reason", e)))
    except ValueError:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "GitHub sent an answer that isn't JSON.")) from None
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(json.dumps({"at": int(time.time()), "etag": etag, "data": data}))
        tmp.replace(f)
    except OSError:
        pass
    return parse_releases(data)


# ---------------------------------------------------------------- what's installed
def targets() -> list[tuple[Path, bool]]:
    """Each Steam's compatibilitytools.d (it may not exist yet), as (folder, is_flatpak)."""
    return [(root / "compatibilitytools.d", flat) for root, flat in library.steam_roots()]


def _tool_names(folder: Path) -> tuple[str, str]:
    """(internal name, display name) from a build's compatibilitytool.vdf; the folder name when it has none."""
    tools = vdf.block(vdf.load(folder / "compatibilitytool.vdf"), "compatibilitytools", "compat_tools")
    for name, d in tools.items():
        if isinstance(d, dict):
            return name, str(d.get("display_name") or name)
    return folder.name, folder.name


def _steam_name(display: str) -> str:
    """Steam's internal name for one of Valve's Protons: "Proton 9.0" -> proton_9, "Proton 5.13" -> proton_513."""
    m = re.match(r"^Proton (\d+)\.(\d+)", display)
    if m:
        return f"proton_{m.group(1)}" + ("" if m.group(2) == "0" else m.group(2))
    return re.sub(r"[^a-z0-9]+", "_", display.lower()).strip("_")


def installed() -> list[Tool]:
    out = []
    for target, flat in targets():
        try:
            dirs = sorted((d for d in target.iterdir() if d.is_dir() and not d.name.startswith(".")),
                          key=lambda d: d.name.casefold())
        except OSError:
            dirs = []
        for d in dirs:
            if (d / "compatibilitytool.vdf").is_file() or (d / "proton").is_file():
                name, display = _tool_names(d)
                out.append(Tool(name, display, str(d), str(target), flat))
    for root, flat in library.steam_roots():
        for lib in library.steam_libraries(root):
            for acf in sorted((lib / "steamapps").glob("appmanifest_*.acf")):
                st = vdf.block(vdf.load(acf), "AppState")
                name = str(st.get("name") or "")
                if re.match(r"^Proton\b", name):
                    out.append(Tool(_steam_name(name), name, "", str(lib), flat, steam=True))
    return out


def mapping() -> dict[str, list[str]]:
    """Steam's choices: tool name -> app ids that use it ("0" = the default for every game). Read from each
    Steam's config/config.vdf (CompatToolMapping)."""
    out: dict[str, list[str]] = {}
    for root, _ in library.steam_roots():
        m = vdf.block(vdf.load(root / "config/config.vdf"), "InstallConfigStore", "Software", "Valve", "Steam",
                      "CompatToolMapping")
        for appid, d in m.items():
            name = str(d.get("name") or "") if isinstance(d, dict) else ""
            if name and library.ID_RE.match(appid) and appid not in out.setdefault(name, []):
                out[name].append(appid)
    return out


def used_by(tool: Tool, games: list, table: dict | None = None) -> tuple[bool, list[str]]:
    """(default for all games, names of the games set to it) — app ids Steam has but GameL doesn't list are shown
    as their number."""
    table = mapping() if table is None else table
    ids = table.get(tool.name, [])
    names = {g.id: g.name for g in games if g.source == "steam"}
    return "0" in ids, sorted((names.get(a, a) for a in ids if a != "0"), key=str.casefold)


# ---------------------------------------------------------------- install / remove
def _get_small(url: str, limit: int = 64 * 1024) -> bytes:
    with OPEN(url, {"User-Agent": UA["User-Agent"]}, 30) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "The checksum file is too large."))
    return data


def expected_sha512(text: str, asset: str) -> str:
    """The hash for asset in a sha512sum file ("<hash>  <name>" lines, or a bare hash)."""
    for line in text.splitlines():
        parts = line.split()
        if not parts or not re.fullmatch(r"[0-9a-fA-F]{128}", parts[0]):
            continue
        if len(parts) == 1 or parts[-1].lstrip("*").rsplit("/", 1)[-1] == asset:
            return parts[0].lower()
    raise ProtonError(tr("grimoire.spells.gamel.proton", "The release's checksum file doesn't list {name}.").format(
        name=asset))


def _download(rel: Release, dest: Path, progress, cancel) -> tuple[str, str]:
    """Streams the build to dest; returns its (sha512, sha256)."""
    h512, h256 = hashlib.sha512(), hashlib.sha256()
    try:
        with OPEN(rel.url, {"User-Agent": UA["User-Agent"]}, 60) as r, open(dest, "wb") as f:
            total = library._int(r.headers.get("Content-Length")) or rel.size
            done, last = 0, 0.0
            while chunk := r.read(1 << 20):
                if cancel():
                    raise Cancelled()
                done += len(chunk)
                if done > MAX_DOWNLOAD:
                    raise ProtonError(tr("grimoire.spells.gamel.proton", "The download is larger than the safety "
                                         "limit; not installing it."))
                f.write(chunk)
                h512.update(chunk)
                h256.update(chunk)
                if time.monotonic() - last > 0.1:
                    last = time.monotonic()
                    progress(done, total)
            progress(done, total)
    except urllib.error.HTTPError as e:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "The download failed: {code}.").format(code=e.code)) \
            from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "The download failed (offline?): {reason}").format(
            reason=getattr(e, "reason", e))) from None
    return h512.hexdigest(), h256.hexdigest()


def check_members(members: list, tag: str):
    """Raises ProtonError unless the archive is one folder named tag holding plain files, folders and links."""
    if len(members) > MAX_MEMBERS:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "The archive has too many files; not installing it."))
    total = 0
    for m in members:
        if m.type in (tarfile.XGLTYPE, tarfile.XHDTYPE):
            continue
        name = m.name.rstrip("/")
        parts = Path(name).parts
        if name.startswith("/") or not parts or ".." in parts or parts[0] != tag:
            raise ProtonError(tr("grimoire.spells.gamel.proton", "The archive contains an unexpected path ({name}); "
                                 "not installing it.").format(name=m.name[:200]))
        if not (m.isfile() or m.isdir() or m.issym() or m.islnk()):
            raise ProtonError(tr("grimoire.spells.gamel.proton", "The archive contains a special file ({name}); not "
                                 "installing it.").format(name=m.name[:200]))
        if m.issym() and (m.linkname.startswith("/") or not m.linkname):
            raise ProtonError(tr("grimoire.spells.gamel.proton", "The archive contains a link out of its folder "
                                 "({name}); not installing it.").format(name=m.name[:200]))
        total += max(0, m.size)
        if total > MAX_EXPANDED:
            raise ProtonError(tr("grimoire.spells.gamel.proton", "The archive expands too large; not installing it."))


def extract(archive: Path, target: Path, tag: str) -> Path:
    """Unpacks into target/.grimoire-<tag>.part, then renames the build into target/<tag>."""
    final = target / tag
    if final.exists() or final.is_symlink():
        raise ProtonError(tr("grimoire.spells.gamel.proton", "{name} is already installed.").format(name=tag))
    work = target / f".grimoire-{tag}.part"
    if work.is_symlink():
        work.unlink()
    elif work.exists():
        shutil.rmtree(work)                                  # GameL's own leftover from an interrupted install
    work.mkdir(parents=True)
    try:
        try:
            with tarfile.open(archive, "r:*") as t:
                members = [m for m in t.getmembers() if m.type not in (tarfile.XGLTYPE, tarfile.XHDTYPE)]
                check_members(members, tag)
                t.extractall(work, members=members, filter="data")
        except (tarfile.TarError, EOFError, OSError) as e:
            raise ProtonError(tr("grimoire.spells.gamel.proton", "The archive is damaged or unsafe: {error}").format(
                error=(str(e).splitlines() or [""])[0].rstrip(":"))) from None
        built = work / tag
        if not built.is_dir() or not ((built / "compatibilitytool.vdf").is_file() or (built / "proton").is_file()):
            raise ProtonError(tr("grimoire.spells.gamel.proton", "The archive isn't laid out like a Proton build; "
                                 "not installing it."))
        if final.exists() or final.is_symlink():
            raise ProtonError(tr("grimoire.spells.gamel.proton", "{name} is already installed.").format(name=tag))
        built.rename(final)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return final


def install(rel: Release, target: Path, progress=lambda done, total: None, cancel=lambda: False) -> Path:
    """Downloads, verifies and unpacks one release into target (a compatibilitytools.d). Raises ProtonError
    (Cancelled when cancel() said so). The download is removed afterwards either way."""
    if not TAG_RE.match(rel.tag) or not (_release_url(rel.url, rel.tag) and _release_url(rel.sha_url, rel.tag)):
        raise ProtonError(tr("grimoire.spells.gamel.proton", "That isn't a GE-Proton release."))
    if (target / rel.tag).exists():
        raise ProtonError(tr("grimoire.spells.gamel.proton", "{name} is already installed.").format(name=rel.tag))
    target.mkdir(parents=True, exist_ok=True)
    need = rel.size * 3 if rel.size else 2 * 1024 ** 3
    if shutil.disk_usage(target).free < need:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "Not enough free space: it needs about {size}.").format(
            size=f"{need / 1024 ** 3:.1f} GB"))
    try:
        want = expected_sha512(_get_small(rel.sha_url).decode("utf-8", errors="replace"), rel.asset)
    except urllib.error.HTTPError as e:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "The download failed: {code}.").format(code=e.code)) \
            from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "The download failed (offline?): {reason}").format(
            reason=getattr(e, "reason", e))) from None
    folder = _cache() / "proton"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (rel.asset + ".part")
    try:
        got512, got256 = _download(rel, dest, progress, cancel)
        if got512 != want or (rel.sha256 and got256 != rel.sha256):
            raise ProtonError(tr("grimoire.spells.gamel.proton", "The download doesn't match the release's checksum; "
                                 "not installing it."))
        if cancel():
            raise Cancelled()
        return extract(dest, target, rel.tag)
    finally:
        dest.unlink(missing_ok=True)                         # GameL's own download, not a user file


def remove(tool: Tool):
    """Moves a build GameL can manage (a folder right inside a compatibilitytools.d) to the Trash."""
    p = Path(tool.path)
    parents = {t.resolve() for t, _ in targets() if t.exists()}
    if tool.steam or not tool.path or p.is_symlink() or not p.is_dir() or p.parent.resolve() not in parents:
        raise ProtonError(tr("grimoire.spells.gamel.proton", "GameL only removes builds in compatibilitytools.d."))
    try:
        trash(p)
    except OSError as e:
        raise ProtonError(str(e)) from None
