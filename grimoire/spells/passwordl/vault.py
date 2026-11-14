# SPDX-License-Identifier: GPL-3.0-or-later
"""The vault in memory and on disk (no Qt).

On disk: one file, DATA/passwordl/vault.pwl (0600 in a 0700 folder), written atomically (temp file + fsync +
rename), sealed by crypto.py; the last BACKUPS sealed copies stay in backups/ (sealed too, same password). Nothing
here ever logs, prints or sends a record. In memory while unlocked: a dict of records, settings and folders;
Vault.lock() drops it.

A record: {"id", "type", "title", "folder", "tags", "fav", "fields": {name: text}, "custom": [{"name", "value",
"secret"}], "history": [{"password", "changed"}], "created", "modified", "deleted": None | timestamp}.
"""
import json
import os
import secrets
import shutil
import time
from pathlib import Path

from grimoire.i18n import tr_noop
from grimoire.paths import DATA
from grimoire.spells.passwordl import crypto

HOME_DIR = DATA / "passwordl"
FILE = HOME_DIR / "vault.pwl"
BACKUPS = 5

# type → [(field, label, secret, multiline)]; labels are tr_noop'd and translated where shown
TYPES = {
    "login": (tr_noop("grimoire.spells.passwordl.vault", "Login"),
              [("username", tr_noop("grimoire.spells.passwordl.vault", "Username"), False, False),
               ("password", tr_noop("grimoire.spells.passwordl.vault", "Password"), True, False),
               ("url", tr_noop("grimoire.spells.passwordl.vault", "Website"), False, False),
               ("totp", tr_noop("grimoire.spells.passwordl.vault", "Two-factor key"), True, False),
               ("notes", tr_noop("grimoire.spells.passwordl.vault", "Notes"), False, True)]),
    "card": (tr_noop("grimoire.spells.passwordl.vault", "Payment card"),
             [("cardholder", tr_noop("grimoire.spells.passwordl.vault", "Name on card"), False, False),
              ("number", tr_noop("grimoire.spells.passwordl.vault", "Card number"), True, False),
              ("expiry", tr_noop("grimoire.spells.passwordl.vault", "Expires (MM/YY)"), False, False),
              ("cvv", tr_noop("grimoire.spells.passwordl.vault", "Security code"), True, False),
              ("pin", tr_noop("grimoire.spells.passwordl.vault", "PIN"), True, False),
              ("notes", tr_noop("grimoire.spells.passwordl.vault", "Notes"), False, True)]),
    "note": (tr_noop("grimoire.spells.passwordl.vault", "Secure note"),
             [("notes", tr_noop("grimoire.spells.passwordl.vault", "Note"), False, True)]),
    "identity": (tr_noop("grimoire.spells.passwordl.vault", "Identity"),
                 [("name", tr_noop("grimoire.spells.passwordl.vault", "Full name"), False, False),
                  ("email", tr_noop("grimoire.spells.passwordl.vault", "Email"), False, False),
                  ("phone", tr_noop("grimoire.spells.passwordl.vault", "Phone"), False, False),
                  ("address", tr_noop("grimoire.spells.passwordl.vault", "Address"), False, True),
                  ("birthday", tr_noop("grimoire.spells.passwordl.vault", "Birthday"), False, False),
                  ("id_number", tr_noop("grimoire.spells.passwordl.vault", "ID or passport number"), True, False),
                  ("notes", tr_noop("grimoire.spells.passwordl.vault", "Notes"), False, True)]),
    "wifi": (tr_noop("grimoire.spells.passwordl.vault", "Wi-Fi"),
             [("ssid", tr_noop("grimoire.spells.passwordl.vault", "Network name"), False, False),
              ("password", tr_noop("grimoire.spells.passwordl.vault", "Password"), True, False),
              ("notes", tr_noop("grimoire.spells.passwordl.vault", "Notes"), False, True)]),
    "ssh": (tr_noop("grimoire.spells.passwordl.vault", "SSH key"),
            [("username", tr_noop("grimoire.spells.passwordl.vault", "Username"), False, False),
             ("host", tr_noop("grimoire.spells.passwordl.vault", "Host"), False, False),
             ("private_key", tr_noop("grimoire.spells.passwordl.vault", "Private key"), True, True),
             ("passphrase", tr_noop("grimoire.spells.passwordl.vault", "Passphrase"), True, False),
             ("notes", tr_noop("grimoire.spells.passwordl.vault", "Notes"), False, True)]),
    "bank": (tr_noop("grimoire.spells.passwordl.vault", "Bank account"),
             [("bank", tr_noop("grimoire.spells.passwordl.vault", "Bank"), False, False),
              ("account", tr_noop("grimoire.spells.passwordl.vault", "Account number"), True, False),
              ("routing", tr_noop("grimoire.spells.passwordl.vault", "Routing or sort code"), False, False),
              ("iban", tr_noop("grimoire.spells.passwordl.vault", "IBAN"), True, False),
              ("notes", tr_noop("grimoire.spells.passwordl.vault", "Notes"), False, True)]),
}
SETTINGS = {"lock_minutes": 5, "clipboard_seconds": 20, "lock_on_minimize": False, "breach_check": False}
HISTORY_KEEP = 10
TRASH_DAYS = 30


def fields_of(kind: str) -> list:
    return TYPES.get(kind, TYPES["login"])[1]


def secret_field(kind: str, name: str) -> bool:
    return any(f == name and s for f, _l, s, _m in fields_of(kind))


def exists(path: Path = FILE) -> bool:
    return path.is_file()


def _clean_record(r) -> dict | None:
    """A record as stored, from anything (an old file, an import): wrong types dropped, never trusted."""
    if not isinstance(r, dict):
        return None
    kind = r.get("type") if r.get("type") in TYPES else "login"
    fields = r.get("fields") if isinstance(r.get("fields"), dict) else {}
    out = {"id": str(r.get("id") or secrets.token_hex(8))[:40], "type": kind,
           "title": str(r.get("title") or "")[:300], "folder": str(r.get("folder") or "")[:200],
           "tags": [str(t)[:60] for t in r["tags"] if isinstance(t, str)][:30]
           if isinstance(r.get("tags"), list) else [],
           "fav": bool(r.get("fav")),
           "fields": {str(k)[:60]: str(v)[:100000] for k, v in fields.items() if isinstance(v, (str, int, float))},
           "custom": [{"name": str(c.get("name", ""))[:100], "value": str(c.get("value", ""))[:100000],
                       "secret": bool(c.get("secret"))}
                      for c in (r.get("custom") or []) if isinstance(c, dict)][:50]
           if isinstance(r.get("custom"), list) else [],
           "history": [{"password": str(h.get("password", "")), "changed": int(h.get("changed") or 0)}
                       for h in (r.get("history") or []) if isinstance(h, dict)][-HISTORY_KEEP:]
           if isinstance(r.get("history"), list) else [],
           "created": int(r.get("created") or time.time()), "modified": int(r.get("modified") or time.time()),
           "deleted": int(r["deleted"]) if isinstance(r.get("deleted"), (int, float)) else None}
    return out


class Vault:
    """An unlocked vault. Every change goes through a method that saves right away (a crash never loses an edit)."""

    def __init__(self, sealed: crypto.Sealed, data: dict, path: Path = FILE):
        self.sealed = sealed
        self.path = path
        records = data.get("records") if isinstance(data.get("records"), list) else []
        self.records: dict[str, dict] = {}
        for r in records:
            c = _clean_record(r)
            if c:
                self.records[c["id"]] = c
        s = data.get("settings") if isinstance(data.get("settings"), dict) else {}
        self.settings = {k: s[k] if type(s.get(k)) is type(v) else v for k, v in SETTINGS.items()}
        self.folders: list[str] = sorted({str(f) for f in data.get("folders", []) if isinstance(f, str)}
                                         | {r["folder"] for r in self.records.values() if r["folder"]}) \
            if isinstance(data.get("folders", []), list) else []
        self._purge_trash()

    # ------------------------------------------------------------ opening and creating
    @classmethod
    def create(cls, password: str, path: Path = FILE, kdf: dict | None = None) -> "Vault":
        if path.exists():
            raise FileExistsError(str(path))
        v = cls(crypto.Sealed.create(password, kdf), {}, path)
        v.save()
        return v

    @classmethod
    def unlock(cls, password: str, path: Path = FILE) -> "Vault":
        """Raises crypto.BadPassword, crypto.BadFile or OSError."""
        sealed, plain = crypto.Sealed.open(path.read_bytes(), password)
        try:
            data = json.loads(plain.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise crypto.BadFile("damaged contents") from e
        return cls(sealed, data if isinstance(data, dict) else {}, path)

    def lock(self):
        self.sealed.forget()
        self.records.clear()
        self.folders.clear()

    # ------------------------------------------------------------ saving
    def to_json(self) -> bytes:
        return json.dumps({"records": list(self.records.values()), "settings": self.settings,
                           "folders": self.folders}).encode("utf-8")

    def save(self):
        blob = self.sealed.seal(self.to_json())
        _write_private(self.path, blob, keep=BACKUPS)

    def change_password(self, new_password: str):
        self.sealed.change_password(new_password)
        self.save()

    def export_to(self, path: Path, password: str):
        """An encrypted copy under its own password (a .pwl file PasswordL can import or open)."""
        sealed = crypto.Sealed.create(password, self.sealed.header["kdf"])
        _write_private(path, sealed.seal(self.to_json()), keep=0)
        sealed.forget()

    # ------------------------------------------------------------ records
    def add(self, kind: str, title: str, fields: dict | None = None, **extra) -> dict:
        r = _clean_record({"type": kind, "title": title, "fields": fields or {}, **extra,
                           "id": secrets.token_hex(8), "created": time.time(), "modified": time.time()})
        self.records[r["id"]] = r
        if r["folder"] and r["folder"] not in self.folders:
            self.folders = sorted({*self.folders, r["folder"]})
        self.save()
        return r

    def add_many(self, records: list[dict]) -> int:
        """Imported records ({"type", "title", "fields", …}), saved once at the end."""
        n = 0
        for raw in records:
            r = _clean_record({**raw, "id": secrets.token_hex(8), "created": time.time(), "modified": time.time()})
            if r:
                self.records[r["id"]] = r
                n += 1
        self.folders = sorted({*self.folders, *(r["folder"] for r in self.records.values() if r["folder"])})
        self.save()
        return n

    def update(self, rid: str, **changes) -> dict:
        r = self.records[rid]
        new = dict(r)
        new.update(changes)
        old_pw = r["fields"].get("password", "")
        new_pw = new.get("fields", {}).get("password", "") if isinstance(new.get("fields"), dict) else old_pw
        if old_pw and new_pw != old_pw:                     # keep the old one (Password history)
            new["history"] = [*r["history"], {"password": old_pw, "changed": int(time.time())}][-HISTORY_KEEP:]
        new["modified"] = int(time.time())
        c = _clean_record(new)
        c["id"], c["created"] = r["id"], r["created"]
        self.records[rid] = c
        if c["folder"] and c["folder"] not in self.folders:
            self.folders = sorted({*self.folders, c["folder"]})
        self.save()
        return c

    def trash(self, rid: str):
        self.update(rid, deleted=int(time.time()))

    def restore(self, rid: str):
        self.update(rid, deleted=None)

    def delete_forever(self, rid: str):
        self.records.pop(rid, None)
        self.save()

    def _purge_trash(self):
        cutoff = time.time() - TRASH_DAYS * 86400
        for rid in [r["id"] for r in self.records.values() if r["deleted"] and r["deleted"] < cutoff]:
            del self.records[rid]

    def add_folder(self, name: str):
        name = name.strip()[:200]
        if name and name not in self.folders:
            self.folders = sorted({*self.folders, name})
            self.save()

    def remove_folder(self, name: str):
        """Its records move to no folder; nothing is deleted."""
        for r in self.records.values():
            if r["folder"] == name:
                r["folder"] = ""
        self.folders = [f for f in self.folders if f != name]
        self.save()

    def set(self, **settings):
        for k, v in settings.items():
            if k in SETTINGS and type(v) is type(SETTINGS[k]):
                self.settings[k] = v
        self.save()

    def live(self) -> list[dict]:
        return [r for r in self.records.values() if not r["deleted"]]

    def search(self, text: str, records: list[dict] | None = None) -> list[dict]:
        """Title, username, website, folder, tags and notes; never secret fields."""
        words = text.lower().split()
        out = []
        for r in records if records is not None else self.live():
            hay = " ".join([r["title"], r["folder"], " ".join(r["tags"]),
                            *(v for k, v in r["fields"].items() if not secret_field(r["type"], k))]).lower()
            if all(w in hay for w in words):
                out.append(r)
        return out


def _write_private(path: Path, blob: bytes, keep: int):
    """Atomic 0600 write in a 0700 folder; the previous file joins backups/ (newest `keep` kept)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    if keep and path.exists():                           # at most one sealed copy an hour, the newest `keep` kept
        bdir = path.parent / "backups"
        bdir.mkdir(exist_ok=True, mode=0o700)
        copies = sorted(bdir.glob(f"{path.stem}-*{path.suffix}"))
        if not copies or time.time() - copies[-1].stat().st_mtime > 3600:
            target = bdir / f"{path.stem}-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}"
            try:
                shutil.copy2(path, target)
                os.chmod(target, 0o600)
                copies.append(target)
            except OSError:
                pass
        for old in copies[:-keep]:
            old.unlink(missing_ok=True)                  # older sealed copies of the vault itself, nothing else
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, blob)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
