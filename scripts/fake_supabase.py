# SPDX-License-Identifier: GPL-3.0-or-later
"""A tiny in-process stand-in for a Supabase project (GoTrue auth + the PostgREST calls Grimoire makes), for tests.

It behaves like supabase/migrations/ set up: usernames unique (case-insensitive) and checked like the SQL CHECK,
"Confirm email" off, PKCE for OAuth (S256 checked), refresh tokens single-use, recovery codes hashed and rotated
with a lockout, and user_settings rows visible only to their owner (row-level security shaped answers).

    from scripts.fake_supabase import FakeSupabase
    with FakeSupabase() as fake:          # sets GRIMOIRE_SUPABASE_URL / _ANON_KEY for this process
        ...
"""
import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANON = "fake-anon-key-for-tests-0123456789"
USERNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,31}")


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


class FakeSupabase:
    def __init__(self):
        self.users = {}            # id -> {email, password_hash, meta}
        self.profiles = {}         # id -> {username, email}
        self.access = {}           # token -> (id, expires)
        self.refresh = {}          # token -> id
        self.flows = {}            # auth code -> (challenge, provider, id)
        self.codes = {}            # id -> sha256(code)
        self.attempts = {}         # lower(username) -> [fails, locked_until]
        self.settings = {}         # id -> (data, updated_at)
        self.requests = []         # (method, path) for assertions; never bodies
        self.lock = threading.Lock()
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, payload=None, headers=None):
                body = b"" if payload is None else json.dumps(payload).encode()
                self.send_response(code)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    return json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    return {}

            def _caller(self):
                auth = self.headers.get("Authorization", "")
                tok = auth.removeprefix("Bearer ")
                entry = fake.access.get(tok)
                return entry[0] if entry and entry[1] > time.time() else None

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def _route(self, method):
                fake.requests.append((method, self.path.split("?")[0]))
                if self.headers.get("apikey") != ANON:
                    return self._send(401, {"message": "Invalid API key"})
                url = urllib.parse.urlparse(self.path)
                q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
                with fake.lock:
                    fake.handle(self, method, url.path, q)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self._env = {k: os.environ.get(k) for k in ("GRIMOIRE_SUPABASE_URL", "GRIMOIRE_SUPABASE_ANON_KEY")}
        os.environ["GRIMOIRE_SUPABASE_URL"] = self.url
        os.environ["GRIMOIRE_SUPABASE_ANON_KEY"] = ANON
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # ---------------------------------------------------------------- helpers
    def _session(self, uid, ttl=3600):
        a, r = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        self.access[a] = (uid, time.time() + ttl)
        self.refresh[r] = uid
        u = self.users[uid]
        return {"access_token": a, "refresh_token": r, "expires_in": ttl, "token_type": "bearer",
                "user": {"id": uid, "email": u["email"], "user_metadata": u["meta"]}}

    def _new_user(self, email, password, meta):
        uid = str(uuid.uuid4())
        name = meta.get("username") or meta.get("user_name") or "user"
        base, n = re.sub(r"[^A-Za-z0-9_-]", "", name)[:28] or "user", 1
        name = base
        while any(p["username"].lower() == name.lower() for p in self.profiles.values()):
            n += 1
            name = f"{base}{n}"
        self.users[uid] = {"email": email, "pw": _h(password or secrets.token_hex()), "meta": meta}
        self.profiles[uid] = {"username": name, "email": meta.get("contact_email", "")}
        return uid

    def oauth_login(self, authorize_url: str, provider_login="octo") -> str:
        """Play the browser + provider: follow /authorize and return the URL Supabase would redirect to."""
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(authorize_url).query).items()}
        assert q["code_challenge_method"] == "s256"
        uid = next((i for i, u in self.users.items() if u["meta"].get("user_name") == provider_login), None)
        if uid is None:
            uid = self._new_user(f"{provider_login}@example.com", "", {"user_name": provider_login})
        code = secrets.token_urlsafe(16)
        self.flows[code] = (q["code_challenge"], q["provider"], uid)
        return f"{q['redirect_to']}?code={code}"

    # ---------------------------------------------------------------- routes
    def handle(self, h, method, path, q):
        uid = h._caller()
        if (method, path) == ("POST", "/auth/v1/signup"):
            b = h._body()
            email, pw, meta = str(b.get("email", "")).lower(), str(b.get("password", "")), b.get("data") or {}
            if len(pw) < 10:
                return h._send(422, {"code": 422, "error_code": "weak_password", "msg": "weak"})
            if any(u["email"] == email for u in self.users.values()):
                return h._send(422, {"code": 422, "error_code": "user_already_exists", "msg": "exists"})
            if not USERNAME.fullmatch(str(meta.get("username", ""))):
                return h._send(500, {"code": 500, "error_code": "unexpected_failure", "msg": "db"})
            if any(p["username"].lower() == meta["username"].lower() for p in self.profiles.values()):
                return h._send(422, {"code": 422, "error_code": "user_already_exists", "msg": "exists"})
            return h._send(200, self._session(self._new_user(email, pw, meta)))
        if (method, path) == ("POST", "/auth/v1/token"):
            b, grant = h._body(), q.get("grant_type")
            if grant == "password":
                email = str(b.get("email", "")).lower()
                hit = next((i for i, u in self.users.items() if u["email"] == email), None)
                if hit is None or self.users[hit]["pw"] != _h(str(b.get("password", ""))):
                    return h._send(400, {"code": 400, "error_code": "invalid_credentials", "msg": "Invalid"})
                return h._send(200, self._session(hit))
            if grant == "refresh_token":
                hit = self.refresh.pop(str(b.get("refresh_token", "")), None)
                if hit is None:
                    return h._send(400, {"code": 400, "error_code": "refresh_token_not_found", "msg": "nf"})
                return h._send(200, self._session(hit))
            if grant == "pkce":
                flow = self.flows.pop(str(b.get("auth_code", "")), None)
                if flow is None:
                    return h._send(404, {"code": 404, "error_code": "flow_state_not_found", "msg": "nf"})
                verifier = str(b.get("code_verifier", ""))
                calc = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
                if calc != flow[0]:
                    return h._send(400, {"code": 400, "error_code": "bad_code_verifier", "msg": "bad"})
                return h._send(200, self._session(flow[2]))
            return h._send(400, {"code": 400, "error_code": "unsupported_grant_type"})
        if (method, path) == ("POST", "/auth/v1/logout"):
            if uid is None:
                return h._send(401, {"code": 401, "error_code": "no_authorization"})
            for t in [t for t, v in self.access.items() if v[0] == uid]:
                del self.access[t]
            for t in [t for t, v in self.refresh.items() if v == uid]:
                del self.refresh[t]
            return h._send(204)
        if (method, path) == ("GET", "/rest/v1/profiles"):
            want = q.get("id", "").removeprefix("eq.")
            rows = [{"username": p["username"]} for i, p in self.profiles.items() if i == uid and i == want]
            return h._send(200, rows)
        if (method, path) == ("POST", "/rest/v1/rpc/issue_recovery_code"):
            if uid is None:
                return h._send(401, {"code": "42501", "message": "permission denied"})
            code = "-".join(secrets.token_hex(10).upper()[i:i + 5] for i in range(0, 20, 5))
            self.codes[uid] = _h(code.replace("-", ""))
            return h._send(200, code)
        if (method, path) == ("POST", "/rest/v1/rpc/recover_account"):
            b = h._body()
            name, code, pw = str(b.get("p_username", "")), str(b.get("p_code", "")), str(b.get("p_new_password", ""))
            if len(pw) < 10:
                return h._send(200, {"ok": False, "error": "weak_password"})
            att = self.attempts.setdefault(name.lower(), [0, 0])
            if att[1] > time.time():
                return h._send(200, {"ok": False, "error": "locked", "retry_after": int(att[1] - time.time())})
            hit = next((i for i, p in self.profiles.items() if p["username"].lower() == name.lower()), None)
            if hit is None or self.codes.get(hit) != _h(code):
                att[0] += 1
                if att[0] >= 5:
                    att[1] = time.time() + min(900, 30 * 2 ** (att[0] - 5))
                return h._send(200, {"ok": False, "error": "invalid"})
            self.attempts.pop(name.lower(), None)
            self.users[hit]["pw"] = _h(pw)
            for t in [t for t, v in self.refresh.items() if v == hit]:
                del self.refresh[t]
            new = "-".join(secrets.token_hex(10).upper()[i:i + 5] for i in range(0, 20, 5))
            self.codes[hit] = _h(new.replace("-", ""))
            return h._send(200, {"ok": True, "code": new})
        if path == "/rest/v1/user_settings":
            if uid is None:
                return h._send(401, {"code": "42501", "message": "permission denied"})
            if method == "GET":
                want = q.get("user_id", "").removeprefix("eq.")
                row = self.settings.get(uid) if want == uid else None      # RLS: only your own row
                return h._send(200, [{"data": row[0], "updated_at": row[1]}] if row else [])
            b = h._body()
            if b.get("user_id") != uid:
                return h._send(403, {"code": "42501", "message": "new row violates row-level security policy"})
            if len(str(b.get("data", ""))) > 1_500_000:
                return h._send(400, {"code": "23514", "message": "check constraint"})
            self.settings[uid] = (str(b["data"]), time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()))
            return h._send(201)
        return h._send(404, {"message": "not found"})
