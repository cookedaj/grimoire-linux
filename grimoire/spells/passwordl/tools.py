# SPDX-License-Identifier: GPL-3.0-or-later
"""PasswordL's helpers (no Qt): the generator, a strength estimate, two-factor codes, the security audit, the
opt-in breach check and importers.

Randomness is `secrets` only. Two-factor codes are cryptography's TOTP (RFC 6238). The breach check is off until
you turn it on, and then sends only the first 5 hex characters of each password's SHA-1 to Have I Been Pwned's
range API (k-anonymity): never a password, a name or a site.
"""
import base64
import csv
import hashlib
import io
import json
import math
import re
import secrets
import string
import time
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.hashes import SHA1, SHA256, SHA512
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP

from grimoire.i18n import tr

WORDS_FILE = Path("/usr/share/dict/words")
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/"
LOOKALIKES = set("Il1O0o")


# ---------------------------------------------------------------- generator
def password(length: int = 20, upper=True, lower=True, digits=True, symbols=True, no_lookalikes=False) -> str:
    """Random characters with at least one from each chosen set."""
    sets = [s for s, on in ((string.ascii_uppercase, upper), (string.ascii_lowercase, lower),
                            (string.digits, digits), (SYMBOLS, symbols)) if on] or [string.ascii_lowercase]
    if no_lookalikes:
        sets = [''.join(c for c in s if c not in LOOKALIKES) for s in sets]
    length = max(length, len(sets), 4)
    alphabet = "".join(sets)
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if all(any(c in s for c in pw) for s in sets):
            return pw


_words: list[str] | None = None


def words() -> list[str]:
    global _words
    if _words is None:
        try:
            raw = WORDS_FILE.read_text(errors="ignore").split()
        except OSError:
            raw = []
        _words = sorted({w for w in raw if w.isascii() and w.isalpha() and w.islower() and 4 <= len(w) <= 8})
    return _words


def passphrase(count: int = 5, sep: str = "-", capitalize=True, number=True) -> str:
    """Random dictionary words (~15 bits each from /usr/share/dict); falls back to characters without a list."""
    pool = words()
    if len(pool) < 2000:
        return password(count * 5, symbols=False)
    parts = [secrets.choice(pool) for _ in range(max(3, count))]
    if capitalize:
        parts = [p.capitalize() for p in parts]
    if number:
        i = secrets.randbelow(len(parts))
        parts[i] += str(secrets.randbelow(10))
    return sep.join(parts)


# ---------------------------------------------------------------- strength
COMMON = {"password", "123456", "123456789", "qwerty", "letmein", "admin", "welcome", "iloveyou", "monkey", "dragon",
          "football", "abc123", "111111", "sunshine", "princess", "master", "login", "passw0rd", "starwars"}


def entropy(pw: str) -> float:
    """A rough estimate in bits: the character pool size, cut for repeats, sequences and common words."""
    if not pw:
        return 0.0
    pool = sum(n for s, n in ((string.ascii_lowercase, 26), (string.ascii_uppercase, 26), (string.digits, 10))
               if any(c in s for c in pw))
    pool += 33 if any(not c.isalnum() and c.isascii() for c in pw) else 0
    pool += 100 if any(not c.isascii() for c in pw) else 0
    unique = len(set(pw))
    bits = len(pw) * math.log2(max(pool, 2)) * min(1.0, unique / max(4, len(pw) * 0.6))
    low = pw.lower()
    if low in COMMON or re.fullmatch(r"(.)\1+", pw) or low.strip("0123456789!") in COMMON:
        bits = min(bits, 10)
    if re.search(r"(0123|1234|2345|3456|4567|5678|6789|abcd|qwer|asdf|zxcv)", low):
        bits *= 0.8
    return bits


def strength(pw: str) -> tuple[int, str]:
    """(0..4, word) for a meter."""
    b = entropy(pw)
    score = 0 if b < 28 else 1 if b < 40 else 2 if b < 60 else 3 if b < 80 else 4
    return score, (tr("grimoire.spells.passwordl.tools", "Very weak"), tr("grimoire.spells.passwordl.tools", "Weak"),
                   tr("grimoire.spells.passwordl.tools", "Fair"), tr("grimoire.spells.passwordl.tools", "Strong"),
                   tr("grimoire.spells.passwordl.tools", "Very strong"))[score]


# ---------------------------------------------------------------- two-factor codes
def parse_totp(text: str) -> dict | None:
    """A base32 secret or an otpauth://totp/ URI → {"secret", "digits", "period", "algorithm", "label"}."""
    text = (text or "").strip()
    out = {"digits": 6, "period": 30, "algorithm": "SHA1", "label": ""}
    if text.lower().startswith("otpauth://"):
        u = urllib.parse.urlparse(text)
        if u.netloc.lower() != "totp":
            return None
        q = {k.lower(): v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        out["label"] = urllib.parse.unquote(u.path.lstrip("/"))
        secret = q.get("secret", "")
        try:
            out["digits"] = int(q.get("digits", 6))
            out["period"] = int(q.get("period", 30))
        except ValueError:
            return None
        out["algorithm"] = q.get("algorithm", "SHA1").upper()
    else:
        secret = text
    secret = re.sub(r"[\s-]", "", secret).upper().rstrip("=")
    if not secret or not re.fullmatch(r"[A-Z2-7]+", secret) or out["digits"] not in (6, 7, 8) \
            or not 10 <= out["period"] <= 300 or out["algorithm"] not in ("SHA1", "SHA256", "SHA512"):
        return None
    out["secret"] = secret
    return out


def totp_code(text: str, now: float | None = None) -> tuple[str, int] | None:
    """(code, seconds left) for a stored two-factor key, or None if it isn't one."""
    p = parse_totp(text)
    if not p:
        return None
    try:
        key = base64.b32decode(p["secret"] + "=" * (-len(p["secret"]) % 8))
        algo = {"SHA1": SHA1, "SHA256": SHA256, "SHA512": SHA512}[p["algorithm"]]()
        t = TOTP(key, p["digits"], algo, p["period"], enforce_key_length=False)
    except (ValueError, InvalidToken):
        return None
    now = time.time() if now is None else now
    return t.generate(int(now)).decode(), p["period"] - int(now) % p["period"]


# ---------------------------------------------------------------- audit
def audit(records: list[dict]) -> dict:
    """{"weak": [rec], "reused": [[rec, rec…]], "old": [rec], "no2fa": [rec], "score": 0..100} over live logins."""
    logins = [r for r in records if r["fields"].get("password")]
    weak = [r for r in logins if strength(r["fields"]["password"])[0] <= 1]
    groups: dict[str, list] = {}
    for r in logins:
        groups.setdefault(r["fields"]["password"], []).append(r)
    reused = [g for g in groups.values() if len(g) > 1]
    year = 365 * 86400
    old = [r for r in logins if time.time() - (r["history"][-1]["changed"] if r["history"] else r["created"]) > year]
    no2fa = [r for r in logins if r["type"] == "login" and r["fields"].get("url") and not r["fields"].get("totp")]
    bad = {id(r) for r in weak} | {id(r) for g in reused for r in g}
    score = round(100 * (1 - len(bad) / len(logins))) if logins else 100
    return {"weak": weak, "reused": reused, "old": old, "no2fa": no2fa, "score": score, "total": len(logins)}


RANGE_API = "https://api.pwnedpasswords.com/range/"


def breached(passwords: list[str], fetch=None) -> dict[str, int]:
    """{password: times seen in breaches} for those that were, via the k-anonymity range API (only 5 hex characters
    of each SHA-1 leave this PC; the answer lists suffixes, matched here). Called only after you turn it on."""
    fetch = fetch or _fetch
    by_prefix: dict[str, list[str]] = {}
    for pw in set(passwords):
        h = hashlib.sha1(pw.encode("utf-8")).hexdigest().upper()
        by_prefix.setdefault(h[:5], []).append(pw)
    out = {}
    for prefix, pws in by_prefix.items():
        body = fetch(prefix)
        counts = {}
        for line in body.splitlines():
            suffix, _, n = line.strip().partition(":")
            if n.isdigit():
                counts[suffix.upper()] = int(n)
        for pw in pws:
            n = counts.get(hashlib.sha1(pw.encode("utf-8")).hexdigest().upper()[5:], 0)
            if n:
                out[pw] = n
    return out


def _fetch(prefix: str) -> str:
    req = urllib.request.Request(RANGE_API + prefix,
                                 headers={"Add-Padding": "true", "User-Agent": "Grimoire-PasswordL"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(2_000_000).decode("utf-8", "replace")


# ---------------------------------------------------------------- import
def _host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url if "://" in url else "https://" + url).hostname or url
    except ValueError:
        return url


def read_import(path: Path) -> tuple[str, list[dict]]:
    """(format name, [record dicts for Vault.add]) from a CSV (Bitwarden, Chrome/Edge/Brave, Firefox, Keeper,
    KeePassXC, LastPass, 1Password or any with name/username/password columns) or a JSON export (Bitwarden
    unencrypted, Keeper). Raises ValueError for anything else. Passwords stay in memory only."""
    raw = path.read_bytes()[:50_000_000].decode("utf-8-sig", "replace")
    if path.suffix.lower() == ".json" or raw.lstrip().startswith("{"):
        try:
            data = json.loads(raw)
        except ValueError as e:
            raise ValueError(tr("grimoire.spells.passwordl.tools", "This JSON file can't be read.")) from e
        if isinstance(data, dict) and data.get("encrypted"):
            raise ValueError(tr("grimoire.spells.passwordl.tools", "This export is encrypted; export it again "
                                "without a password, import it, then delete the file."))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return "Bitwarden", _bitwarden(data)
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return "Keeper", _keeper_json(data)
        raise ValueError(tr("grimoire.spells.passwordl.tools", "Not an export PasswordL knows."))
    rows = list(csv.reader(io.StringIO(raw)))
    if not rows:
        raise ValueError(tr("grimoire.spells.passwordl.tools", "The file is empty."))
    head = [h.strip().lower() for h in rows[0]]

    def col(*names):
        return next((head.index(n) for n in names if n in head), None)
    title_c, user_c = col("name", "title", "account"), col("login_username", "username", "user", "login", "email")
    pass_c, url_c = col("login_password", "password", "pass"), col("login_uri", "url", "uri", "website", "web site")
    note_c, folder_c, totp_c = col("notes", "note", "extra"), col("folder", "group", "grouping"), \
        col("login_totp", "totp", "otpauth", "one-time password")
    if pass_c is None:
        if len(head) >= 3 and not any(h in ("password", "username") for h in head):   # Keeper CSV has no header
            return "Keeper", _keeper_csv(rows)
        raise ValueError(tr("grimoire.spells.passwordl.tools", "No password column in this CSV file."))
    kind = "Bitwarden" if "login_uri" in head else "Firefox" if "httprealm" in head else \
        "Chrome" if head[:4] == ["name", "url", "username", "password"] else "KeePassXC" if "group" in head else "CSV"
    out = []
    for row in rows[1:]:
        def get(c, row=row):
            return row[c].strip() if c is not None and c < len(row) else ""
        if not any(row):
            continue
        url = get(url_c)
        out.append({"type": "login", "title": get(title_c) or _host(url) or get(user_c) or "?",
                    "folder": get(folder_c).strip("/").replace("Root/", ""),
                    "fields": {"username": get(user_c), "password": get(pass_c), "url": url,
                               "totp": get(totp_c), "notes": get(note_c)}})
    return kind, out


def _keeper_csv(rows) -> list[dict]:
    """Keeper's CSV: folder, title, login, password, website, notes, then custom name/value pairs."""
    out = []
    for row in rows:
        row = row + [""] * (6 - len(row))
        custom = [{"name": row[i], "value": row[i + 1], "secret": False} for i in range(7, len(row) - 1, 2) if row[i]]
        totp = next((v for v in row if v.startswith("otpauth://")), "")
        out.append({"type": "login", "title": row[1] or _host(row[4]) or "?", "folder": row[0],
                    "fields": {"username": row[2], "password": row[3], "url": row[4], "notes": row[5], "totp": totp},
                    "custom": [c for c in custom if c["value"] != totp]})
    return out


def _keeper_json(data) -> list[dict]:
    out = []
    for r in data["records"]:
        if not isinstance(r, dict):
            continue
        cf = r.get("custom_fields") if isinstance(r.get("custom_fields"), dict) else {}
        totp = next((str(v) for k, v in cf.items() if "otp" in str(k).lower()), "")
        folders = r.get("folders") if isinstance(r.get("folders"), list) else []
        folder = next((f.get("folder", "") for f in folders if isinstance(f, dict)), "")
        out.append({"type": "login", "title": str(r.get("title") or "?"), "folder": folder,
                    "fields": {"username": str(r.get("login") or ""), "password": str(r.get("password") or ""),
                               "url": str(r.get("login_url") or ""), "notes": str(r.get("notes") or ""),
                               "totp": totp},
                    "custom": [{"name": str(k), "value": str(v), "secret": False} for k, v in cf.items()
                               if str(v) != totp]})
    return out


def _bitwarden(data) -> list[dict]:
    folders = {f.get("id"): f.get("name", "") for f in data.get("folders", []) if isinstance(f, dict)}
    out = []
    for it in data["items"]:
        if not isinstance(it, dict):
            continue
        base = {"title": str(it.get("name") or "?"), "folder": folders.get(it.get("folderId"), ""),
                "fav": bool(it.get("favorite")),
                "custom": [{"name": str(f.get("name", "")), "value": str(f.get("value") or ""),
                            "secret": f.get("type") == 1} for f in it.get("fields") or [] if isinstance(f, dict)]}
        notes = str(it.get("notes") or "")
        t = it.get("type")
        if t == 1 and isinstance(it.get("login"), dict):
            lg = it["login"]
            uris = [u.get("uri", "") for u in lg.get("uris") or [] if isinstance(u, dict)]
            out.append({**base, "type": "login", "fields": {"username": str(lg.get("username") or ""),
                        "password": str(lg.get("password") or ""), "url": uris[0] if uris else "",
                        "totp": str(lg.get("totp") or ""), "notes": notes}})
        elif t == 3 and isinstance(it.get("card"), dict):
            c = it["card"]
            exp = f"{c.get('expMonth') or ''}/{str(c.get('expYear') or '')[-2:]}".strip("/")
            out.append({**base, "type": "card", "fields": {"cardholder": str(c.get("cardholderName") or ""),
                        "number": str(c.get("number") or ""), "expiry": exp, "cvv": str(c.get("code") or ""),
                        "notes": notes}})
        elif t == 4 and isinstance(it.get("identity"), dict):
            i = it["identity"]
            name = " ".join(str(i.get(k) or "") for k in ("firstName", "middleName", "lastName")).split()
            addr = ", ".join(str(i.get(k)) for k in ("address1", "address2", "city", "state", "postalCode",
                                                       "country") if i.get(k))
            out.append({**base, "type": "identity", "fields": {"name": " ".join(name),
                        "email": str(i.get("email") or ""), "phone": str(i.get("phone") or ""), "address": addr,
                        "id_number": str(i.get("passportNumber") or i.get("licenseNumber") or ""), "notes": notes}})
        else:
            out.append({**base, "type": "note", "fields": {"notes": notes}})
    return out
