# SPDX-License-Identifier: GPL-3.0-or-later
"""Who uses this PC (no Qt, read only): AccountsService over D-Bus, else the passwd database. Adding users or
changing passwords stays in KDE's Users module, which has the polkit rules for it."""

import grp
import os
import pwd

from grimoire.spells.settingl import kde

DEST, ROOT = "org.freedesktop.Accounts", "/org/freedesktop/Accounts"


def _account(path: str) -> dict:
    p = kde.bus_props(DEST, path, "org.freedesktop.Accounts.User", system=True)
    if not p:
        return {}
    return {
        "uid": p.get("Uid"),
        "user": p.get("UserName", ""),
        "name": p.get("RealName", ""),
        "admin": p.get("AccountType") == 1,
        "icon": p.get("IconFile", ""),
        "locked": bool(p.get("Locked")),
        "auto_login": bool(p.get("AutomaticLogin")),
        "last_login": p.get("LoginTime") or 0,
        "shell": p.get("Shell", ""),
        "home": p.get("HomeDirectory", ""),
    }


def _from_passwd(pw) -> dict:
    groups = {g.gr_name for g in grp.getgrall() if pw.pw_name in g.gr_mem}
    return {
        "uid": pw.pw_uid,
        "user": pw.pw_name,
        "name": pw.pw_gecos.split(",")[0],
        "shell": pw.pw_shell,
        "home": pw.pw_dir,
        "admin": bool(groups & {"sudo", "wheel", "admin"}),
        "icon": "",
        "locked": False,
        "auto_login": False,
        "last_login": 0,
    }


def read() -> dict:
    """{"me": {...}, "others": [...]} — others are the other people (not system accounts)."""
    uid = os.getuid()
    me = {}
    found = kde.bus_call(DEST, ROOT, DEST, "FindUserById", "x", uid, system=True, quiet=True)
    if found:
        me = _account(found[0] if isinstance(found[0], str) else found[0][0])
    try:
        base = _from_passwd(pwd.getpwuid(uid))
    except KeyError:
        base = {
            "uid": uid,
            "user": str(uid),
            "name": "",
            "shell": "",
            "home": "",
            "admin": False,
            "icon": "",
            "locked": False,
            "auto_login": False,
            "last_login": 0,
        }
    me = {**base, **{k: v for k, v in me.items() if v not in ("", None)}}
    me["groups"] = sorted(g.gr_name for g in grp.getgrall() if me["user"] in g.gr_mem)
    others = []
    listed = kde.bus_call(DEST, ROOT, DEST, "ListCachedUsers", system=True, quiet=True)
    paths = listed[0] if listed and isinstance(listed[0], list) else (listed or [])
    for path in paths:
        a = _account(path)
        if a and a.get("uid") != uid:
            others.append(a)
    if not paths:  # no AccountsService: people have uids from 1000
        others = [_from_passwd(p) for p in pwd.getpwall() if 1000 <= p.pw_uid < 60000 and p.pw_uid != uid]
    return {"me": me, "others": sorted(others, key=lambda a: a["user"])}
