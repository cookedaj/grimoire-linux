# SPDX-License-Identifier: GPL-3.0-or-later
"""Grimoire Linux accounts: sign up, sign in (password, Google, GitHub), recovery codes and settings sync.

The UI talks to a Backend; today that's Supabase (Auth = GoTrue, data = PostgREST, set up by supabase/migrations/).
Another server only needs another Backend with the same methods. No Qt here, and every call blocks: the UI runs
them off its thread.

Accounts are usernames. Supabase Auth wants an email, so a username-only account signs in with a made-up address,
<username>@users.grimoire.invalid, that nothing ever mails; the username is the only thing a person types. An email
given at sign-up is kept privately on the account row (profiles.email, readable only by its owner), never used to
sign in, so no endpoint ever turns a username into someone's address. Forgotten passwords are reset with the
one-time recovery code shown at sign-up (checked and rotated by the recover_account() database function).

Secrets: the access token lives in memory only; the refresh token in the system keyring when "Keep me signed in"
is ticked (session.py), else nowhere. Both travel as Token objects that print as "Token(…)"; passwords are only
ever passed through. Error messages come from fixed texts and server error codes, never from request bodies.
"""
import base64
import hashlib
import hmac
import http.server
import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from grimoire import __version__, supabase_app
from grimoire.github import Token
from grimoire.paths import CACHE, GUEST, valid_profile

USERNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,31}")
EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+")
MIN_PASSWORD, MAX_PASSWORD = 10, 72                  # 72 bytes: bcrypt's limit (Supabase hashes with bcrypt)
PROVIDERS = {"google": "Google", "github": "GitHub"}
MAX_BODY = 4 << 20
MAX_SETTINGS = 1 << 20                               # the backup zip; the table allows its base64 (~1.4 MB)
UA = f"Grimoire-Linux/{__version__} (accounts)"
THROTTLE = CACHE / "signin-throttle.json"


class AccountError(RuntimeError):
    """A failure worth showing as is (never carries a token or password)."""


@dataclass
class User:
    id: str
    username: str
    provider: str = "password"                       # password | google | github


@dataclass
class Session:
    user: User
    access: Token
    refresh: Token
    expires_at: float

    def fresh(self) -> bool:
        return time.time() < self.expires_at - 60


# ---------------------------------------------------------------- checks the UI shows as you type
def username_problem(name: str) -> str:
    if not name:
        return "Choose a username."
    if not USERNAME.fullmatch(name):
        return "Usernames are 3 to 32 letters, digits, - or _, starting with a letter or digit."
    return ""


def email_problem(email: str) -> str:
    if email and (len(email) > 254 or not EMAIL.fullmatch(email)):
        return "That email address doesn't look right (or leave it empty)."
    return ""


def password_problem(password: str, confirm: str | None = None) -> str:
    if len(password) < MIN_PASSWORD:
        return "Passwords need at least {n} characters.".format(n=MIN_PASSWORD)
    if len(password.encode()) > MAX_PASSWORD:
        return "Passwords can be at most {n} bytes long.".format(n=MAX_PASSWORD)
    if confirm is not None and confirm != password:
        return "The two passwords don't match."
    return ""


def strength(password: str) -> tuple[int, str]:
    """A rough 0..3 score and a hint: length counts most, mixing kinds of characters a bit."""
    if not password:
        return 0, ""
    kinds = sum(bool(re.search(rx, password)) for rx in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))
    common = password.lower() in {"password123", "1234567890", "qwertyuiop", "iloveyou12", "grimoire123"}
    score = 0 if common or len(password) < MIN_PASSWORD else 1 + (len(password) >= 14) + (kinds >= 3)
    hint = ["Too weak: use a longer password.", "Okay. Longer is stronger.",
            "Good.", "Strong."][min(score, 3)]
    return min(score, 3), hint


def normalize_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code).upper()


# ---------------------------------------------------------------- sign-in throttle (on this PC)
def _throttle_load() -> dict:
    try:
        d = json.loads(THROTTLE.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def wait_left(username: str, now=None) -> int:
    """Seconds until this username may try again here (0 = now). The server has its own limits too."""
    e = _throttle_load().get(username.lower()) or {}
    left = float(e.get("until", 0) if isinstance(e, dict) else 0) - (now or time.time())
    return max(0, int(left + 0.999))


def note_attempt(username: str, ok: bool, now=None):
    """5 failures → 30 s, then twice as long after each further failure, at most 15 minutes. Success clears it."""
    d, key, now = _throttle_load(), username.lower(), now or time.time()
    if ok:
        d.pop(key, None)
    else:
        e = d.get(key) if isinstance(d.get(key), dict) else {}
        fails = int(e.get("fails", 0)) + 1
        until = now + min(900, 30 * 2 ** (fails - 5)) if fails >= 5 else 0
        d[key] = {"fails": fails, "until": until}
    THROTTLE.parent.mkdir(parents=True, exist_ok=True)
    tmp = THROTTLE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(THROTTLE)


# ---------------------------------------------------------------- OAuth (PKCE + loopback redirect)
def pkce_pair() -> tuple[str, str]:
    """(verifier, S256 challenge), RFC 7636."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


PAGE = ("<!doctype html><meta charset=utf-8><title>Grimoire Linux</title><body style=\"background:#0b0b0b;"
        "color:#e8e8e8;font:16px 'IBM Plex Sans',sans-serif;display:grid;place-items:center;height:90vh\">"
        "<div style=\"text-align:center\"><div style=\"font-size:22px;letter-spacing:4px\">GRIMOIRE LINUX</div>"
        "<p style=\"color:#8c8c8c\">{text}</p></div>")


class Loopback:
    """A one-shot web server on 127.0.0.1 (random port) that waits for the browser to come back with ?code=…
    on /callback/<state>. The random state in the path must match (constant-time), so a page that guesses the port
    can't feed in a code; and a code is useless without this process's PKCE verifier anyway."""

    def __init__(self):
        self.state = secrets.token_urlsafe(24)
        self.result: tuple[str, str] | None = None             # ("code", value) or ("error", message)
        self.done = threading.Event()
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                url = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(url.query)
                parts = url.path.split("/")
                if len(parts) != 3 or parts[1] != "callback" or \
                        not hmac.compare_digest(parts[2].encode(), outer.state.encode()) or outer.done.is_set():
                    self.send_error(404)
                    return
                if q.get("code"):
                    outer.result = ("code", q["code"][0][:512])
                    text = "Signed in. You can close this tab and go back to Grimoire Linux."
                else:
                    err = (q.get("error_description") or q.get("error") or ["sign-in was cancelled"])[0][:120]
                    outer.result = ("error", err)
                    text = "Sign-in didn't finish. You can close this tab."
                body = PAGE.format(text=text).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                outer.done.set()

            def log_message(self, *a):          # the query holds the code: never print requests
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.server.timeout = 0.5
        self.port = self.server.server_address[1]
        self.redirect = f"http://127.0.0.1:{self.port}/callback/{self.state}"

    def wait(self, timeout=300, cancelled=lambda: False) -> str:
        end = time.monotonic() + timeout
        try:
            while not self.done.is_set():
                if cancelled():
                    raise AccountError("Sign-in cancelled.")
                if time.monotonic() > end:
                    raise AccountError("Sign-in timed out. Try again.")
                self.server.handle_request()
        finally:
            self.server.server_close()
        kind, value = self.result
        if kind != "code":
            raise AccountError("The sign-in page said: {reason}".format(reason=value))
        return value

    def close(self):
        try:
            self.server.server_close()
        except OSError:
            pass


# ---------------------------------------------------------------- HTTP
class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """The API never redirects; following one would carry the token and the key elsewhere."""

    def redirect_request(self, *a, **kw):
        return None


_OPENER = urllib.request.build_opener(_NoRedirects)


def _urllib(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": UA, **headers})
    try:
        with _OPENER.open(req, timeout=30) as r:
            return r.status, r.read(MAX_BODY + 1)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(MAX_BODY + 1)
        except OSError:
            return e.code, b""
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AccountError("Couldn't reach the account server. Are you online?") from None


HTTP = _urllib


# ---------------------------------------------------------------- the backend interface
class Backend:
    """What the sign-in screen and Settings need from an account server."""
    name = "none"

    def configured(self) -> bool:
        return False

    def sign_up(self, username: str, password: str, email: str = "") -> tuple[Session, str]:
        """A new account, signed in, and its first recovery code (shown once)."""
        raise NotImplementedError

    def sign_in(self, username: str, password: str) -> Session:
        raise NotImplementedError

    def refresh(self, refresh: Token, provider: str = "password") -> Session:
        raise NotImplementedError

    def sign_out(self, session: Session):
        raise NotImplementedError

    def oauth_url(self, provider: str, redirect: str, challenge: str) -> str:
        raise NotImplementedError

    def oauth_finish(self, code: str, verifier: str, provider: str) -> Session:
        raise NotImplementedError

    def recover(self, username: str, code: str, new_password: str) -> str:
        """Set a new password with a recovery code; returns the next recovery code."""
        raise NotImplementedError

    def new_recovery_code(self, session: Session) -> str:
        raise NotImplementedError

    def load_settings(self, session: Session) -> tuple[bytes, str] | None:
        """(backup bytes, updated_at) or None when the account has none yet."""
        raise NotImplementedError

    def save_settings(self, session: Session, data: bytes):
        raise NotImplementedError


class Supabase(Backend):
    name = "supabase"

    def configured(self) -> bool:
        return supabase_app.configured()

    # -- plumbing
    def _call(self, method: str, path: str, payload=None, token: Token | None = None, prefer: str = ""):
        base, key = supabase_app.url(), supabase_app.anon_key()
        if not base or not key:
            raise AccountError("Accounts aren't set up yet in this copy of Grimoire Linux.")
        headers = {"apikey": key, "Accept": "application/json",
                   "Authorization": f"Bearer {token.reveal() if token else key}"}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        code, data = HTTP(method, base + path, headers, body)
        if len(data) > MAX_BODY:
            raise AccountError("The account server sent more than expected; stopped.")
        try:
            parsed = json.loads(data) if data.strip() else None
        except (ValueError, UnicodeDecodeError):
            parsed = None
        return code, parsed

    @staticmethod
    def _error(code: int, d) -> AccountError:
        d = d if isinstance(d, dict) else {}
        err = str(d.get("error_code") or d.get("code") or d.get("error") or "")
        known = {
            "invalid_credentials": "Wrong username or password.",
            "invalid_grant": "Wrong username or password.",
            "user_already_exists": "That username is taken. Pick another one.",
            "email_exists": "That username is taken. Pick another one.",
            "weak_password": "The server wants a stronger password (longer, or with more kinds of characters).",
            "over_request_rate_limit": "Too many tries. Wait a few minutes, then try again.",
            "over_email_send_rate_limit": "Too many tries. Wait a few minutes, then try again.",
            "signup_disabled": "New accounts are turned off on the server right now.",
            "email_provider_disabled": "Username accounts are turned off on the server right now.",
            "provider_disabled": "That sign-in option is turned off on the server.",
            "captcha_failed": "The server asks for a captcha, which this version of Grimoire Linux can't show yet.",
            "refresh_token_not_found": "Your sign-in expired. Sign in again.",
            "refresh_token_already_used": "Your sign-in expired. Sign in again.",
            "session_not_found": "Your sign-in expired. Sign in again.",
            "bad_code_verifier": "The sign-in didn't match this window. Try again.",
            "flow_state_not_found": "The sign-in took too long or was already used. Try again.",
            "flow_state_expired": "The sign-in took too long or was already used. Try again.",
            "23514": "The server refused that username.",
            "unexpected_failure": "The server couldn't create that account. Try another username.",
            "23505": "That username is taken. Pick another one.",
        }
        if err in known:
            return AccountError(known[err])
        if code == 429:
            return AccountError(known["over_request_rate_limit"])
        if code in (401, 403):
            return AccountError("The account server refused this (signed out or not allowed). Sign in again.")
        return AccountError("The account server answered {code} ({err}).".format(code=code, err=err[:40] or "error"))

    def _session(self, d, provider: str) -> Session:
        try:
            user = d["user"]
            uid = str(user["id"])
            if not valid_profile(uid) or uid == GUEST:     # also a folder name and a query value: a uuid only
                raise ValueError
            access, refresh = str(d["access_token"]), str(d["refresh_token"])
            expires = float(d.get("expires_at") or time.time() + float(d.get("expires_in", 3600)))
        except (KeyError, TypeError, ValueError):
            raise AccountError("The account server sent an unexpected answer.") from None
        meta = user.get("user_metadata") or {}
        name = str(meta.get("username") or "")
        s = Session(User(uid, name, provider), Token(access), Token(refresh), expires)
        if not USERNAME.fullmatch(name):                       # OAuth accounts get theirs from the database trigger
            s.user.username = self.username(s) or "you"
        return s

    def username(self, s: Session) -> str:
        code, d = self._call("GET", f"/rest/v1/profiles?select=username&id=eq.{s.user.id}", token=s.access)
        if code == 200 and isinstance(d, list) and d and isinstance(d[0], dict):
            name = str(d[0].get("username") or "")
            return name if USERNAME.fullmatch(name) else ""
        return ""

    @staticmethod
    def _login_email(username: str) -> str:
        return f"{username.lower()}@{supabase_app.synthetic_domain()}"

    def _rpc(self, name: str, args: dict, token: Token | None = None):
        code, d = self._call("POST", f"/rest/v1/rpc/{name}", args, token)
        if code != 200:
            raise self._error(code, d)
        return d

    # -- accounts
    def sign_up(self, username, password, email=""):
        problem = username_problem(username) or email_problem(email) or password_problem(password)
        if problem:
            raise AccountError(problem)
        code, d = self._call("POST", "/auth/v1/signup", {
            "email": self._login_email(username), "password": password,
            "data": {"username": username, "contact_email": email}})
        if code not in (200, 201):
            raise self._error(code, d)
        if not isinstance(d, dict) or not d.get("access_token"):
            raise AccountError("The server wants the account confirmed by email; turn \"Confirm email\" off "
                               "in Supabase (see supabase/README.md).")
        s = self._session(d, "password")
        s.user.username = username
        return s, self.new_recovery_code(s)

    def sign_in(self, username, password):
        if username_problem(username):
            raise AccountError("Wrong username or password.")
        code, d = self._call("POST", "/auth/v1/token?grant_type=password",
                             {"email": self._login_email(username), "password": password})
        if code != 200:
            raise self._error(code, d)
        return self._session(d, "password")

    def refresh(self, refresh, provider="password"):
        code, d = self._call("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": refresh.reveal()})
        if code != 200:
            raise self._error(code, d)
        return self._session(d, provider)

    def sign_out(self, session):
        code, d = self._call("POST", "/auth/v1/logout?scope=local", {}, session.access)
        if code not in (200, 204, 401, 403, 404):           # already gone on the server is fine
            raise self._error(code, d)

    def oauth_url(self, provider, redirect, challenge):
        if provider not in PROVIDERS:
            raise AccountError("Unknown sign-in option.")
        q = urllib.parse.urlencode({"provider": provider, "redirect_to": redirect, "code_challenge": challenge,
                                    "code_challenge_method": "s256"})
        return f"{supabase_app.url()}/auth/v1/authorize?{q}"

    def oauth_finish(self, code_, verifier, provider):
        code, d = self._call("POST", "/auth/v1/token?grant_type=pkce",
                             {"auth_code": code_, "code_verifier": verifier})
        if code != 200:
            raise self._error(code, d)
        return self._session(d, provider)

    def recover(self, username, code, new_password):
        problem = password_problem(new_password)
        if problem:
            raise AccountError(problem)
        d = self._rpc("recover_account", {"p_username": username, "p_code": normalize_code(code),
                                          "p_new_password": new_password})
        if not isinstance(d, dict):
            raise AccountError("The account server sent an unexpected answer.")
        if d.get("ok") and isinstance(d.get("code"), str):
            return d["code"]
        if d.get("error") == "locked":
            raise AccountError("Too many wrong codes for this username. Try again in {m} minutes.".format(
                m=max(1, int(d.get("retry_after") or 60) // 60)))
        if d.get("error") == "weak_password":
            raise AccountError(password_problem("") or "Choose a longer password.")
        raise AccountError("That username and recovery code don't match.")

    def new_recovery_code(self, session):
        d = self._rpc("issue_recovery_code", {}, session.access)
        if not isinstance(d, str) or not re.fullmatch(r"[0-9A-F-]{16,40}", d):
            raise AccountError("The account server sent an unexpected answer.")
        return d

    # -- settings sync (table user_settings, one row per account, guarded by row-level security)
    def load_settings(self, session):
        code, d = self._call("GET", f"/rest/v1/user_settings?select=data,updated_at&user_id=eq.{session.user.id}",
                             token=session.access)
        if code != 200 or not isinstance(d, list):
            raise self._error(code, d)
        if not d:
            return None
        try:
            raw = base64.b64decode(str(d[0]["data"]), validate=True)
        except (KeyError, TypeError, ValueError):
            raise AccountError("The settings saved on your account are damaged.") from None
        if len(raw) > MAX_SETTINGS:
            raise AccountError("The settings saved on your account are larger than the safety limit.")
        return raw, str(d[0].get("updated_at") or "")[:40]

    def save_settings(self, session, data):
        if len(data) > MAX_SETTINGS:
            raise AccountError("Your settings are too large to save on your account (over 1 MB).")
        code, d = self._call("POST", "/rest/v1/user_settings?on_conflict=user_id",
                             {"user_id": session.user.id, "data": base64.b64encode(data).decode()},
                             session.access, prefer="resolution=merge-duplicates,return=minimal")
        if code not in (200, 201, 204):
            raise self._error(code, d)


BACKEND: Backend = Supabase()


def keyring_attrs(uid: str) -> dict:
    return {"application": "grimoire", "service": "account", "user": uid}

