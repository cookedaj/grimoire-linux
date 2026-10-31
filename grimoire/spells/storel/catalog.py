# SPDX-License-Identifier: GPL-3.0-or-later
"""The app catalog (no Qt): every app Flathub and the APT archive describe in their AppStream metadata, merged into
one entry per app, read from the files already on disk (no network):

    Flatpak  ~/.local/share/flatpak/appstream/<remote>/<arch>/active/appstream.xml.gz   (your remotes)
             /var/lib/flatpak/appstream/<remote>/<arch>/active/appstream.xml.gz         (the system's)
    APT      /var/lib/swcatalog/yaml/*.yml.gz (DEP-11, from apt-get update) + icons in /var/lib/swcatalog/icons

Parsing them takes a few seconds, so the result is kept in CACHE/storel/catalog.json and rebuilt only when one of
those files changes or the language does. An app is a plain dict:

    {"key": "org.gimp.gimp", "id": "org.gimp.GIMP", "name", "summary", "desc" (plain text), "cats": [...],
     "kw": [...], "license", "dev", "home", "icon": {"file", "stock", "url"}, "shots": [[thumb, full], ...],
     "verified": bool, "offers": [{"src": "flatpak", "remote", "ref", "id", "version", "scopes": [...]},
                                  {"src": "apt", "pkg", "version"}]}

Descriptions are reduced to plain text here (AppStream allows only <p>, <ul>/<ol>/<li>, <em> and <code>); the page
never shows them as rich text.
"""
import gzip
import importlib.util
import json
import os
import platform
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from grimoire import i18n
from grimoire.paths import CACHE, HOME

VERSION = 3
CACHE_FILE = CACHE / "storel" / "catalog.json"
USER_FLATPAK = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "flatpak"
SYSTEM_FLATPAK = Path("/var/lib/flatpak")
SWCATALOG = Path("/var/lib/swcatalog")
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
KINDS = {"desktop-application", "desktop"}          # what a store lists (not runtimes, add-ons, fonts or codecs)
ARCHES = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64", "i686": "i386"}

# the main AppStream categories, in the order Home shows them (several map onto one: Audio and Video)
CATEGORIES = ["AudioVideo", "Development", "Education", "Game", "Graphics", "Network", "Office", "Science",
              "System", "Utility"]
ALIASES = {"Audio": "AudioVideo", "Video": "AudioVideo"}
# hand-picked apps for Home (shown when the catalog has them); keys are lower-case ids without ".desktop"
PICKS = ["org.mozilla.firefox", "org.kde.krita", "org.gimp.gimp", "org.inkscape.inkscape", "org.blender.blender",
         "com.obsproject.studio", "org.kde.kdenlive", "org.videolan.vlc", "org.libreoffice.libreoffice",
         "org.audacityteam.audacity", "com.valvesoftware.steam", "net.lutris.lutris", "org.signal.signal",
         "org.telegram.desktop", "md.obsidian.obsidian", "com.visualstudio.code", "org.mozilla.thunderbird",
         "org.kde.okular", "org.kde.gwenview", "com.github.tchx84.flatseal", "org.kde.kdenlive", "io.mpv.mpv",
         "org.kde.digikam", "org.darktable.darktable", "org.freecad.freecad", "org.qbittorrent.qbittorrent"]


def key_of(app_id: str) -> str:
    """The id apps are matched by across sources: lower case, no ".desktop" ("gimp.desktop" → "gimp")."""
    return (app_id or "").strip().removesuffix(".desktop").lower()


def langs() -> list[str]:
    """AppStream language tags to look for, best first, ending in the untranslated text ("C" / no tag)."""
    code = i18n.current()
    out = {"zh_CN": ["zh_CN", "zh-CN", "zh_Hans", "zh-Hans", "zh"], "pt": ["pt_BR", "pt-BR", "pt"]}.get(code, [code])
    return out + ["en", "C", ""] if code != "en" else ["en_US", "en-US", "en", "C", ""]


def arch() -> str:
    return ARCHES.get(platform.machine(), platform.machine())


# ---------------------------------------------------------------- text
def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def plain(node) -> str:
    """An AppStream <description> element as plain text: paragraphs apart, list items as "• " lines."""
    out = []
    for child in list(node):
        if child.tag == "p":
            out.append(_clean("".join(child.itertext())))
        elif child.tag in ("ul", "ol"):
            for n, li in enumerate([c for c in child if c.tag == "li"], 1):
                mark = "•" if child.tag == "ul" else f"{n}."
                out.append(f"{mark} {_clean(''.join(li.itertext()))}")
    if not out and node.text:
        out.append(_clean(node.text))
    text = []
    for line in out:                       # list items sit together, paragraphs get a blank line around them
        bullet = line[:1] == "•" or re.match(r"\d+\. ", line)
        if text and not (bullet and text[-1] and (text[-1][:1] == "•" or re.match(r"\d+\. ", text[-1]))):
            text.append("")
        text.append(line)
    return "\n".join(text).strip()


def plain_markup(markup: str) -> str:
    """DEP-11 descriptions are the same markup as a string."""
    try:
        return plain(ET.fromstring(f"<description>{markup}</description>"))
    except ET.ParseError:
        return _clean(re.sub(r"<[^>]+>", " ", markup or ""))


def _pick(values: dict) -> str:
    for lang in langs():
        if values.get(lang):
            return values[lang]
    return next(iter(values.values()), "") if values else ""


# ---------------------------------------------------------------- Flathub (AppStream XML)
def flatpak_files() -> list[tuple[str, str, Path]]:
    """(scope, remote, appstream.xml.gz) for every remote that has metadata for this machine's architecture."""
    out = []
    for scope, base in (("user", USER_FLATPAK), ("system", SYSTEM_FLATPAK)):
        root = base / "appstream"
        try:
            remotes = sorted(p.name for p in root.iterdir() if p.is_dir())
        except OSError:
            continue
        for remote in remotes:
            f = root / remote / arch() / "active" / "appstream.xml.gz"
            if f.is_file():
                out.append((scope, remote, f))
    return out


def _icon_paths(base: Path, name: str) -> str:
    if not name or "/" in name or name.startswith("."):          # a file in the icons folder, nothing else
        return ""
    for size in ("128x128", "64x64"):
        p = base / "icons" / size / name
        if p.is_file():
            return str(p)
    return ""


def parse_flatpak(path: Path, remote: str) -> list[dict]:
    """One remote's apps as catalog entries (one offer each)."""
    base = path.parent
    out = []
    with gzip.open(path) as f:
        for _ev, el in ET.iterparse(f):
            if el.tag != "component":
                continue
            try:
                app = _flatpak_component(el, base, remote)
            except (AttributeError, ValueError):
                app = None
            el.clear()
            if app:
                out.append(app)
    return out


def _flatpak_component(el, base: Path, remote: str) -> dict | None:
    if el.get("type") not in KINDS:
        return None
    app_id = (el.findtext("id") or "").strip()
    bundle = el.find("bundle")
    ref = (bundle.text or "").strip() if bundle is not None and bundle.get("type") == "flatpak" else ""
    if not app_id or not ref.startswith("app/"):
        return None
    names, sums, descs = {}, {}, {}
    for child in el:
        lang = child.get(XML_LANG, "")
        if child.tag == "name":
            names[lang] = _clean(child.text)
        elif child.tag == "summary":
            sums[lang] = _clean(child.text)
        elif child.tag == "description":
            descs[lang] = child
    desc = _pick(descs)
    icon = {"file": "", "stock": "", "url": ""}
    for ic in el.findall("icon"):
        kind, text = ic.get("type"), (ic.text or "").strip()
        if kind == "cached" and not icon["file"]:
            icon["file"] = _icon_paths(base, text)
        elif kind == "stock":
            icon["stock"] = text
        elif kind == "remote" and text.startswith("https://") and not icon["url"]:
            icon["url"] = text
    shots = []
    for sc in el.iter("screenshot"):
        thumbs = sorted(((int(i.get("width") or 0), (i.text or "").strip()) for i in sc.findall("image")
                         if i.get("type") == "thumbnail"), key=lambda t: abs(t[0] - 752))
        full = next(((i.text or "").strip() for i in sc.findall("image") if i.get("type") == "source"), "")
        thumb = thumbs[0][1] if thumbs else full
        if thumb.startswith("https://"):
            shots.append([thumb, full if full.startswith("https://") else thumb])
    cats = [c.text.strip() for c in el.iter("category") if c.text]
    kws = [k.text.strip() for kw in el.findall("keywords") if kw.get(XML_LANG, "") in langs()
           for k in kw.findall("keyword") if k.text]
    custom = {v.get("key"): (v.text or "") for v in el.iter("value")}
    rel = el.find("releases/release")
    aliases = [key_of(p.text) for p in el.findall("provides/id") if p.text]
    aliases += [key_of(lc.text) for lc in el.findall("launchable") if lc.text and lc.get("type") == "desktop-id"]
    devs = {n.get(XML_LANG, ""): _clean(n.text) for n in el.findall("developer/name")}
    devs = devs or {n.get(XML_LANG, ""): _clean(n.text) for n in el.findall("developer_name")}
    homes = {u.get("type"): (u.text or "").strip() for u in el.findall("url")}
    return {
        "key": key_of(app_id), "id": app_id, "aliases": sorted(set(aliases) - {key_of(app_id)}),
        "name": _pick(names) or app_id, "summary": _pick(sums),
        "desc": plain(desc) if desc is not None else "", "cats": cats, "kw": kws[:30],
        "license": (el.findtext("project_license") or "").strip(),
        "dev": _pick(devs),
        "home": homes.get("homepage", ""), "icon": icon, "shots": shots[:8],
        "verified": custom.get("flathub::verification::verified") == "true",
        "offers": [{"src": "flatpak", "remote": remote, "ref": ref, "id": app_id,
                    "version": rel.get("version", "") if rel is not None else ""}],
    }


# ---------------------------------------------------------------- APT (DEP-11 YAML)
def apt_files() -> list[Path]:
    try:
        return sorted(p for p in (SWCATALOG / "yaml").iterdir() if p.name.endswith((".yml.gz", ".yaml.gz")))
    except OSError:
        return []


def parse_dep11(path: Path) -> list[dict]:
    """One DEP-11 file's apps. Needs python3-yaml (Kubuntu has it); without it APT apps come only from the
    desktop files of what's installed."""
    import yaml
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    out, origin, media = [], "", ""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for doc in yaml.load_all(f, Loader=loader):
            if not isinstance(doc, dict):
                continue
            if doc.get("File") == "DEP-11":
                origin, media = str(doc.get("Origin", "")), str(doc.get("MediaBaseUrl", "")).rstrip("/")
                continue
            try:
                app = _dep11_component(doc, origin, media)
            except (AttributeError, TypeError, ValueError):
                app = None
            if app:
                out.append(app)
    return out


def _loc(value) -> str:
    return _clean(_pick({str(k): str(v) for k, v in value.items()})) if isinstance(value, dict) else _clean(value or "")


def _dep11_component(doc: dict, origin: str, media: str) -> dict | None:
    if doc.get("Type") not in KINDS or not doc.get("Package") or not doc.get("ID"):
        return None
    pkg, app_id = str(doc["Package"]), str(doc["ID"])
    icon = {"file": "", "stock": "", "url": ""}
    ic = doc.get("Icon") or {}
    if isinstance(ic, dict):
        icon["stock"] = str(ic.get("stock") or "")
        for c in sorted(ic.get("cached") or [], key=lambda c: -int(c.get("width") or 0) if isinstance(c, dict) else 0):
            name = str(c.get("name", "")) if isinstance(c, dict) else ""
            size = f"{c.get('width')}x{c.get('height')}" if name else ""
            # names from the metadata stay inside the icons folder
            if origin and re.fullmatch(r"\d+x\d+", size) and not c.get("scale") and \
                    not any("/" in t or t.startswith(".") for t in (name, origin)):
                p = SWCATALOG / "icons" / origin / size / name
                if p.is_file():
                    icon["file"] = str(p)
                    break
        remote = [r for r in ic.get("remote") or [] if isinstance(r, dict) and r.get("url")]
        if remote and media.startswith("https://"):
            icon["url"] = f"{media}/{remote[0]['url']}"
    shots = []
    for sc in doc.get("Screenshots") or []:
        if not isinstance(sc, dict) or not media.startswith("https://"):
            continue
        src = (sc.get("source-image") or {}).get("url", "") if isinstance(sc.get("source-image"), dict) else ""
        thumbs = sorted((t for t in sc.get("thumbnails") or [] if isinstance(t, dict) and t.get("url")),
                        key=lambda t: abs(int(t.get("width") or 0) - 752))
        thumb = thumbs[0]["url"] if thumbs else src
        if thumb:
            shots.append([f"{media}/{thumb}", f"{media}/{src or thumb}"])
    desc = doc.get("Description") or {}
    kws = doc.get("Keywords") or {}
    kw = _pick({str(k): v for k, v in kws.items()}) if isinstance(kws, dict) else []
    prov = (doc.get("Provides") or {}).get("ids") or [] if isinstance(doc.get("Provides"), dict) else []
    launch = (doc.get("Launchable") or {}).get("desktop-id") or [] if isinstance(doc.get("Launchable"), dict) else []
    aliases = {key_of(str(a)) for a in [*prov, *launch]} - {key_of(app_id)}
    dev = doc.get("Developer") if isinstance(doc.get("Developer"), dict) else {}
    url = doc.get("Url") if isinstance(doc.get("Url"), dict) else {}
    return {
        "key": key_of(app_id), "id": app_id, "aliases": sorted(aliases),
        "name": _loc(doc.get("Name")) or pkg, "summary": _loc(doc.get("Summary")),
        "desc": plain_markup(_pick({str(k): str(v) for k, v in desc.items()})) if isinstance(desc, dict) else "",
        "cats": [str(c) for c in doc.get("Categories") or []], "kw": [str(k) for k in kw or []][:30],
        "license": str(doc.get("ProjectLicense") or ""),
        "dev": _loc(dev.get("name")) if dev else _loc(doc.get("DeveloperName")),
        "home": str(url.get("homepage") or ""), "icon": icon, "shots": shots[:8], "verified": False,
        "offers": [{"src": "apt", "pkg": pkg, "version": ""}],
    }


# ---------------------------------------------------------------- merging
def merge(entries: list[dict]) -> list[dict]:
    """One entry per app: an app Flathub and Ubuntu both ship (matched by id, its old ".desktop" id or a launcher it
    provides) gets both offers. Flathub's text and screenshots come first: they're usually the fuller ones."""
    entries = sorted(entries, key=lambda e: e["offers"][0]["src"] != "flatpak")
    ids: dict[str, dict] = {}                   # an entry's own key
    known: dict[str, dict] = {}                 # its own key and every alias
    out = []
    for e in entries:
        src = e["offers"][0]["src"]
        # the same id always joins (another branch or remote); an old id or a launcher it provides only joins
        # another source's entry: on Flathub, "provides" also names apps it replaced, which are separate there
        hit = ids.get(e["key"])
        if hit is None:
            hit = next((known[k] for k in [e["key"], *e["aliases"]] if k in known and
                        all(o["src"] != src for o in known[k]["offers"])), None)
        if hit is None:
            out.append(e)
            ids.setdefault(e["key"], e)
            for k in [e["key"], *e["aliases"]]:
                known.setdefault(k, e)
            continue
        for o in e["offers"]:
            if not any(x["src"] == o["src"] and x.get("ref", x.get("pkg")) == o.get("ref", o.get("pkg"))
                       for x in hit["offers"]):
                hit["offers"].append(o)
        for field in ("summary", "desc", "license", "dev", "home"):
            hit[field] = hit[field] or e[field]
        hit["shots"] = hit["shots"] or e["shots"]
        hit["cats"] = list(dict.fromkeys(hit["cats"] + e["cats"]))
        for k in ("file", "stock", "url"):
            hit["icon"][k] = hit["icon"][k] or e["icon"][k]
        for k in [e["key"], *e["aliases"]]:
            known.setdefault(k, hit)
    for e in out:
        e.pop("aliases", None)
    return out


# ---------------------------------------------------------------- building and caching
def stamp() -> list:
    """What the cache depends on: each metadata file's path, size and time, and the language."""
    files = [str(f) for *_x, f in flatpak_files()] + [str(f) for f in apt_files()]
    out = [VERSION, i18n.current()]
    for f in files:
        try:
            st = os.stat(f)
            out.append([f, st.st_size, int(st.st_mtime)])
        except OSError:
            continue
    return out


def build(remotes: dict[str, list[str]] | None = None) -> dict:
    """Parse everything (a few seconds). remotes: remote → the scopes it's configured in (from `flatpak remotes`);
    by default a remote counts in each scope that has its metadata."""
    entries, notes = [], []
    seen = {}
    for scope, remote, path in flatpak_files():
        seen.setdefault(remote, []).append((scope, path))
    for remote, where in seen.items():
        path = max(where, key=lambda w: w[1].stat().st_mtime)[1]          # the freshest copy of this remote
        scopes = (remotes or {}).get(remote) or [s for s, _p in where]
        try:
            apps = parse_flatpak(path, remote)
        except (OSError, ET.ParseError, EOFError) as e:
            notes.append(f"{remote}: {e}")
            continue
        for a in apps:
            a["offers"][0]["scopes"] = scopes
        entries += apps
    have_yaml = importlib.util.find_spec("yaml") is not None
    if not have_yaml:
        notes.append("python3-yaml")
    for path in apt_files() if have_yaml else []:
        try:
            entries += parse_dep11(path)
        except Exception as e:                  # one broken file only loses its own apps
            notes.append(f"{path.name}: {e}")
    return {"stamp": stamp(), "apps": merge(entries), "notes": notes}


def load(remotes: dict[str, list[str]] | None = None, force: bool = False) -> dict:
    """The catalog: from the cache when nothing changed, else built again and cached."""
    want = stamp()
    if not force:
        try:
            data = json.loads(CACHE_FILE.read_text())
            if data.get("stamp") == want and isinstance(data.get("apps"), list):
                return data
        except (OSError, ValueError):
            pass
    data = build(remotes)
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        os.replace(tmp, CACHE_FILE)
    except OSError:
        pass
    return data


# ---------------------------------------------------------------- finding
def category_of(app: dict) -> list[str]:
    return list(dict.fromkeys(ALIASES.get(c, c) for c in app["cats"] if ALIASES.get(c, c) in CATEGORIES))


def rank(app: dict) -> float:
    """Better-described apps first: a pick, Flathub-verified, with screenshots and an icon; KDE apps get a nudge on
    a KDE desktop."""
    return ((5 if app["key"] in PICKS else 0) + (2 if app.get("verified") else 0) + (1 if app["shots"] else 0)
            + (1 if app["icon"]["file"] or app["icon"]["stock"] else 0) + (0.5 if app["key"].startswith("org.kde.")
                                                                           else 0))


def in_category(apps: list[dict], cat: str) -> list[dict]:
    return sorted((a for a in apps if cat in category_of(a)), key=lambda a: (-rank(a), a["name"].casefold()))


def picks(apps: list[dict]) -> list[dict]:
    by = {a["key"]: a for a in apps}
    return [by[k] for k in dict.fromkeys(PICKS) if k in by]


def search(apps: list[dict], query: str, limit: int = 300) -> list[dict]:
    """Apps matching every word of query, best first: name, then keywords, id and package, then summary."""
    words = [w for w in query.casefold().split() if w]
    if not words:
        return []
    scored = []
    for a in apps:
        name = a["name"].casefold()
        hay_kw = " ".join(a["kw"]).casefold()
        hay_id = " ".join([a["id"], *(o.get("pkg", "") for o in a["offers"])]).casefold()
        summary = a["summary"].casefold()
        score = 0.0
        for w in words:
            if name == w:
                s = 10
            elif name.startswith(w):
                s = 7
            elif w in name:
                s = 5
            elif w in hay_kw or w in hay_id:
                s = 3
            elif w in summary:
                s = 1.5
            else:
                score = -1
                break
            score += s
        if score > 0:
            phrase = " ".join(words)
            if len(words) > 1 and (phrase in name or phrase in summary):     # "video editor" as written
                score += 6
            scored.append((score + rank(a) / 10, a))
    scored.sort(key=lambda t: (-t[0], t[1]["name"].casefold()))
    return [a for _s, a in scored[:limit]]
