# SPDX-License-Identifier: GPL-3.0-or-later
"""Your apps (no Qt): the catalog matched with what's installed, apps the catalog doesn't know (desktop files,
other Flatpak remotes, snaps), how to open one, and the status line.

An installed copy is a dict {"src", "name" (package / ref / snap), "scope", "version", "size", "keep"} where "keep"
is why StoreL won't offer to remove it ('' when it may).
"""
import json
import os
import subprocess
import time

from grimoire import i18n
from grimoire.i18n import tr
from grimoire.paths import CACHE
from grimoire.spells.storel import sources

STATUS = CACHE / "storel" / "status.json"
SOURCE_NAMES = {"flatpak": "Flathub", "apt": "APT", "snap": "Snap"}


def offer_name(offer: dict) -> str:
    """How a source is named on a badge or a button: the Flatpak remote's name, APT or Snap."""
    if offer["src"] == "flatpak":
        remote = offer.get("remote") or "flathub"
        name = "Flathub" if remote == "flathub" else remote
        branch = offer.get("ref", "").split("/")[-1]
        return name if branch in ("stable", "") else f"{name} · {branch}"
    return SOURCE_NAMES[offer["src"]]


def offer_id(offer: dict) -> str:
    return offer.get("ref") or offer.get("pkg") or offer.get("name") or ""


def copies(app: dict, inst: dict) -> list[dict]:
    """The installed copies of a catalog app (one per installed offer and Flatpak installation)."""
    out = []
    for o in app["offers"]:
        if o["src"] == "flatpak":
            for f in inst.get("flatpak", []):
                if f["ref"] == o["ref"]:
                    out.append({"src": "flatpak", "name": f["ref"], "scope": f["scope"], "version": f["version"],
                                "size": f["size"], "keep": "", "offer": offer_id(o)})
        elif o["src"] == "apt":
            info = inst.get("apt", {}).get(o["pkg"])
            if info:
                out.append({"src": "apt", "name": o["pkg"], "scope": "system", "version": info["version"],
                            "size": info["size"], "keep": sources.removable(o["pkg"], info), "offer": offer_id(o)})
        elif o["src"] == "snap":
            s = next((s for s in inst.get("snap", []) if s["name"] == o["name"]), None)
            if s:
                out.append({"src": "snap", "name": s["name"], "scope": "system", "version": s["version"],
                            "size": None, "keep": "", "offer": offer_id(o)})
    return out


def _bare(key: str, name: str, summary: str = "", icon: dict | None = None, cats=None, offers=None) -> dict:
    """An app the catalog doesn't describe, in the catalog's shape."""
    return {"key": key, "id": key, "name": name, "summary": summary, "desc": "", "cats": cats or [], "kw": [],
            "license": "", "dev": "", "home": "", "icon": icon or {"file": "", "stock": "", "url": ""}, "shots": [],
            "verified": False, "offers": offers or []}


def installed_apps(apps: list[dict], inst: dict) -> list[tuple[dict, list[dict]]]:
    """(app, its installed copies) for everything you can open from the menu: catalog apps first, then desktop
    files of APT packages the catalog doesn't list, Flatpaks from other remotes and snaps."""
    out, seen_pkgs, seen_refs, seen_snaps = [], set(), set(), set()
    for a in apps:
        # a package with several launchers (kdeconnect) is listed once, under its first app
        c = [x for x in copies(a, inst) if x["name"] not in (seen_pkgs if x["src"] == "apt" else seen_refs)]
        if c:
            out.append((a, c))
            seen_pkgs |= {x["name"] for x in c if x["src"] == "apt"}
            seen_refs |= {x["name"] for x in c if x["src"] == "flatpak"}
    # every package that owns a catalog app's launcher counts as listed, installed or not
    listed = {o["pkg"] for a in apps for o in a["offers"] if o["src"] == "apt"}
    for d in inst.get("desktop", []):
        pkg = d["pkg"]
        if pkg in seen_pkgs or pkg in listed:
            continue
        info = inst.get("apt", {}).get(pkg)
        if not info:
            continue
        seen_pkgs.add(pkg)
        app = _bare(f"desktop:{d['key']}", d["name"], d["summary"], {"file": "", "stock": d["icon"], "url": ""},
                    d["cats"], [{"src": "apt", "pkg": pkg, "version": ""}])
        app["desktop"] = d["desktop"]
        out.append((app, [{"src": "apt", "name": pkg, "scope": "system", "version": info["version"],
                           "size": info["size"], "keep": sources.removable(pkg, info), "offer": pkg}]))
    for f in inst.get("flatpak", []):
        if f["ref"] in seen_refs:
            continue
        offer = {"src": "flatpak", "remote": f["origin"], "ref": f["ref"], "id": f["id"], "version": f["version"],
                 "scopes": [f["scope"]]}
        out.append((_bare(f["id"].lower(), f["name"], offers=[offer], icon={"file": "", "stock": f["id"], "url": ""}),
                    [{"src": "flatpak", "name": f["ref"], "scope": f["scope"], "version": f["version"],
                      "size": f["size"], "keep": "", "offer": f["ref"]}]))
    for s in inst.get("snap", []):
        if s["name"] in seen_snaps:
            continue
        seen_snaps.add(s["name"])
        out.append((_bare(f"snap:{s['name']}", s["name"], offers=[{"src": "snap", "name": s["name"],
                                                                   "version": s["version"]}]),
                    [{"src": "snap", "name": s["name"], "scope": "system", "version": s["version"], "size": None,
                      "keep": "", "offer": s["name"]}]))
    out.sort(key=lambda t: t[0]["name"].casefold())
    return out


def snap_app(row: dict) -> dict:
    """A `snap find` row as an app."""
    return _bare(f"snap:{row['name']}", row["name"], row.get("summary", ""),
                 offers=[{"src": "snap", "name": row["name"], "version": row.get("version", ""),
                          "publisher": row.get("publisher", "")}])


def flatpak_search_app(row: dict, arch: str) -> dict:
    """A `flatpak search` row as an app (when the catalog has no Flatpak metadata yet)."""
    ref = f"app/{row['id']}/{arch}/{row['branch'] or 'stable'}"
    return _bare(row["id"].lower(), row["name"] or row["id"], row["summary"],
                 icon={"file": "", "stock": row["id"], "url": ""},
                 offers=[{"src": "flatpak", "remote": row["remote"], "ref": ref, "id": row["id"],
                          "version": row["version"], "scopes": []}])


# ---------------------------------------------------------------- opening an app
def _launch(cmd: list[str]):
    subprocess.Popen(cmd, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


LAUNCH = _launch                    # tests swap this: never start real apps in tests


def open_command(app: dict, copy: dict, inst: dict) -> list[str]:
    """How to start an installed copy ([] when there's no launcher to start)."""
    if copy["src"] == "flatpak":
        app_id = copy["name"].split("/")[1]
        return ["flatpak", "run", f"--{copy['scope']}", app_id]
    if copy["src"] == "snap":
        return ["snap", "run", copy["name"]]
    desktop = app.get("desktop") or ""
    if not desktop:
        want = {app["id"], app["id"].removesuffix(".desktop")}
        mine = [d for d in inst.get("desktop", []) if d["pkg"] == copy["name"]]
        hit = next((d for d in mine if d["id"] in want), None) or (mine[0] if mine else None)
        desktop = hit["desktop"] if hit else ""
    return ["gio", "launch", desktop] if desktop else []


# ---------------------------------------------------------------- status line
def save_status(installed_count: int, catalog_count: int):
    try:
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps({"installed": installed_count, "catalog": catalog_count, "t": time.time()}))
        os.replace(tmp, STATUS)
    except OSError:
        pass


def status_line() -> str:
    """For the hub's card: what StoreL saw last time it was open (it never reads the system for this)."""
    try:
        s = json.loads(STATUS.read_text())
        return " · ".join([tr("grimoire.spells.storel.library", "%n app(s) installed", n=int(s["installed"])),
                           tr("grimoire.spells.storel.library", "%n app(s) to browse", n=int(s["catalog"]))])
    except (OSError, ValueError, KeyError, TypeError):
        return tr("grimoire.spells.storel.library", "Apps from Flathub and Ubuntu, without Discover")


def isolate(text) -> str:
    return i18n.isolate(text)
