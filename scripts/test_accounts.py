# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks for accounts.py + session.py against scripts/fake_supabase.py, in a throwaway HOME.

    python3 scripts/test_accounts.py <sandbox folder under ~/.cache>

Never touches the real keyring (a dict stands in) or a real server.
"""
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

box = Path(sys.argv[1]).resolve()
assert box.is_relative_to(Path.home() / ".cache"), "use a sandbox under ~/.cache"
for k, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"), ("XDG_DATA_HOME", "home/.local/share"),
               ("XDG_CACHE_HOME", "home/.cache"), ("XDG_RUNTIME_DIR", "run")):
    (box / sub).mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ[k] = str(box / sub)
os.environ.pop("GRIMOIRE_PROFILE", None)
sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent)]

from fake_supabase import FakeSupabase  # noqa: E402

from grimoire import accounts, paths, session, supabase_app  # noqa: E402
from grimoire.accounts import AccountError  # noqa: E402


class FakeKeyring:
    def __init__(self):
        self.items = {}

    def store(self, secret, attrs, label=""):
        self.items[tuple(sorted(attrs.items()))] = secret

    def load(self, attrs):
        return self.items.get(tuple(sorted(attrs.items())))

    def delete(self, attrs):
        return int(self.items.pop(tuple(sorted(attrs.items())), None) is not None)


ring = session.KEYRING = FakeKeyring()
ok = 0


def check(cond, what):
    global ok
    if not cond:
        raise SystemExit(f"FAIL: {what}")
    ok += 1


def raises(fn, text):
    try:
        fn()
    except AccountError as e:
        check(text in str(e), f"{text!r} in {e!r}")
        return
    raise SystemExit(f"FAIL: expected AccountError {text!r}")


# never the real project: blank the shipped URL/key, the fake server sets its own through the env
supabase_app.SUPABASE_URL = supabase_app.SUPABASE_ANON_KEY = ""
for k in ("GRIMOIRE_SUPABASE_URL", "GRIMOIRE_SUPABASE_ANON_KEY"):
    os.environ.pop(k, None)
b = accounts.BACKEND
check(not b.configured(), "not configured without URL/key")
raises(lambda: b.sign_in("alice", "x" * 12), "aren't set up")

# a pre-accounts install has settings at the top of CONFIG
(paths.CONFIG_ROOT / "sightc.json").write_text('{"old": true}')

with FakeSupabase() as fake:
    check(b.configured(), "configured with env")
    raises(lambda: b.sign_up("al", "x" * 12), "3 to 32")
    raises(lambda: b.sign_up("alice", "short"), "at least 10")
    raises(lambda: b.sign_up("alice", "x" * 12, "not-an-email"), "doesn't look right")
    s, code = b.sign_up("Alice", "correct horse 1", "alice@example.com")
    check(s.user.username == "Alice" and len(code.replace("-", "")) == 20, "sign up gives a session and a code")
    check(fake.users[s.user.id]["email"] == "alice@users.grimoire.invalid", "synthetic login address")
    check(fake.profiles[s.user.id]["email"] == "alice@example.com", "contact email kept on the profile")
    raises(lambda: b.sign_up("ALICE", "another pass 1"), "taken")
    raises(lambda: b.sign_in("alice", "wrong password"), "Wrong username or password")
    try:
        b.sign_in("alice", "wrong password")
    except AccountError as e:
        check(e.kind == "credentials", "wrong password has a fixed kind (the UI never compares translated text)")
    s2 = b.sign_in("aLiCe", "correct horse 1")
    check(s2.user.id == s.user.id, "case-insensitive sign in")
    check("Token(" in repr(s2.access) and s2.access.reveal() not in repr(s2), "tokens hide in repr")

    # session: first account adopts the old settings by copy; keyring holds the refresh token
    check(session.begin(s2, remember=True), "activate without restart")
    check(paths.CONFIG == paths.PROFILES / s.user.id, "CONFIG is the account's profile")
    check((paths.CONFIG / "sightc.json").read_text() == '{"old": true}', "old settings copied")
    check((paths.CONFIG_ROOT / "sightc.json").exists(), "originals left in place")
    check(oct(paths.SESSION.stat().st_mode & 0o777) == "0o600", "session.json is 0600")
    check(ring.load(accounts.keyring_attrs(s.user.id)) == s2.refresh.reveal(), "refresh token in keyring")
    check(s2.refresh.reveal() not in paths.SESSION.read_text(), "no token in session.json")
    check(session.remembered().profile == s.user.id, "remembered")

    # settings sync, RLS-shaped
    session.CURRENT = None                                  # as after a remembered start: refresh from keyring
    live = session.live()
    check(live.access.reveal() != s2.access.reveal(), "refreshed")
    check(ring.load(accounts.keyring_attrs(s.user.id)) == live.refresh.reveal(), "rotated refresh token stored")
    check(b.load_settings(live) is None, "no settings yet")
    from grimoire import backup
    data = backup.export_bytes()
    b.save_settings(live, data)
    got, when = b.load_settings(live)
    check(got == data and when, "settings round trip")
    check(backup.inspect(got).entries, "downloaded settings pass backup.inspect")
    bob, _ = b.sign_up("bob", "bob password 1")
    check(b.load_settings(bob) is None, "bob can't read alice's row")
    bob.user.id = s.user.id                                  # pretend: write into alice's row with bob's token
    raises(lambda: b.save_settings(bob, b"x"), "refused")

    # recovery
    raises(lambda: b.recover("alice", "0000-0000", "new password 99"), "don't match")
    new_code = b.recover("alice", code.lower(), "new password 99")
    check(new_code != code, "code rotated")
    raises(lambda: b.recover("alice", code, "new password 98"), "don't match")      # old code is spent
    raises(lambda: b.sign_in("alice", "correct horse 1"), "Wrong")
    check(b.sign_in("alice", "new password 99").user.id == s.user.id, "new password works")
    for _ in range(5):
        raises(lambda: b.recover("ghost", "AAAAA-AAAAA-AAAAA-AAAAA", "whatever pass 1"), "")
    raises(lambda: b.recover("ghost", "AAAAA-AAAAA-AAAAA-AAAAA", "whatever pass 1"), "Too many wrong codes")
    raises(lambda: b.recover("no such name!", "AAAA", "whatever pass 1"), "don't match")
    check("no such name!" not in fake.attempts, "malformed names leave no attempts row")

    # OAuth PKCE through the loopback listener
    lb = accounts.Loopback()
    verifier, challenge = accounts.pkce_pair()
    url = b.oauth_url("github", lb.redirect, challenge)
    check(url.startswith(fake.url + "/auth/v1/authorize?") and "code_challenge_method=s256" in url, "authorize url")
    bad = lb.redirect.rsplit("/", 1)[0] + "/wrongstate?code=evil"
    import threading
    seen = []

    def browser(urls):
        for u in urls:
            try:
                urllib.request.urlopen(u, timeout=5).read()
                seen.append(200)
            except urllib.error.HTTPError as e:
                seen.append(e.code)
    back = fake.oauth_login(url)
    threading.Thread(target=browser, args=([bad, back],), daemon=True).start()
    code_ = lb.wait(timeout=10)
    check(seen[:1] == [404], "wrong state refused")
    raises(lambda: b.oauth_finish(code_, "not-the-verifier" * 4, "github"), "didn't match")
    back = fake.oauth_login(url)
    lb2 = accounts.Loopback()
    back = back.replace(lb.redirect, lb2.redirect)
    threading.Thread(target=browser, args=([back],), daemon=True).start()
    gh = b.oauth_finish(lb2.wait(timeout=10), verifier, "github")
    check(gh.user.username == "octo" and gh.user.provider == "github", "github account via PKCE")

    # a client that connects and says nothing can't stall the listener (it gives up on it after a few seconds)
    import socket
    lb3 = accounts.Loopback()
    idle = socket.create_connection(("127.0.0.1", lb3.port))
    back = fake.oauth_login(url).replace(lb.redirect, lb3.redirect)
    threading.Thread(target=browser, args=([back],), daemon=True).start()
    check(lb3.wait(timeout=15), "callback served after an idle connection")
    idle.close()

    # a restart hands the in-memory session over through a pipe (not remembered: nothing in the keyring)
    import json as _json
    os.environ["GRIMOIRE_PROFILE"] = s.user.id
    session.CURRENT = gh_like = b.sign_in("alice", "new password 99")
    session.handoff()
    fd = os.environ.get(session.HANDOFF, "")
    check(fd.isdigit() and gh_like.refresh.reveal() not in _json.dumps(dict(os.environ)), "token not in the env")
    session.CURRENT = None
    session.adopt()
    check(session.CURRENT is not None and session.CURRENT.refresh.reveal() == gh_like.refresh.reveal()
          and session.HANDOFF not in os.environ, "restarted process adopts the session once")
    try:
        os.fstat(int(fd))
        check(False, "handoff pipe closed after adopt")
    except OSError:
        check(True, "handoff pipe closed after adopt")
    os.environ[session.HANDOFF] = "0"                         # never someone else's descriptor
    session.adopt()
    check(os.fstat(0) is not None, "adopt leaves fd 0 alone")

    # two windows, one remembered account: the one holding a spent refresh token uses the keyring's newer one
    session.begin(gh_like, remember=True)
    other = session.live()                                    # "window A" refreshes and stores the new token
    session.CURRENT = accounts.Session(other.user, other.access, gh_like.refresh, 0)   # "window B": spent token
    check(session.live().user.id == s.user.id, "stale window refreshes with the keyring's token")
    check(ring.load(accounts.keyring_attrs(s.user.id)) == session.CURRENT.refresh.reveal(), "newest token kept")

    # sign out forgets the token and the remember flag
    session.end()
    check(ring.load(accounts.keyring_attrs(s.user.id)) is None, "token forgotten")
    check(session.remembered() is None and session.last().profile == s.user.id, "last kept for background jobs")

# throttle
accounts.THROTTLE.write_text('{"zed": {"fails": "x", "until": null}, "amy": 3, "bo": {"until": 1e999}}')
check(accounts.wait_left("zed") == 0 and accounts.wait_left("amy") == 0, "damaged throttle file is ignored")
accounts.note_attempt("zed", False, now=1000)
for _ in range(4):
    accounts.note_attempt("zed", False, now=1000)
check(accounts.wait_left("ZED", now=1000) == 30, "5 failures → 30 s")
accounts.note_attempt("zed", False, now=1000)
check(accounts.wait_left("zed", now=1000) == 60, "then doubles")
accounts.note_attempt("zed", True)
check(accounts.wait_left("zed") == 0, "success clears")

# guest: a new guest start empties the old guest profile; a second window shares it
check(not session.begin_guest(), "guest asks for a restart: backup.py holds the old CONFIG")
check(paths.CONFIG == paths.guest_dir() and str(paths.CONFIG).startswith(os.environ["XDG_RUNTIME_DIR"]), "guest dir")
(paths.CONFIG / "sightc.json").write_text("{}")
session._guest_lock.close()
session.begin_guest()
check(not (paths.CONFIG / "sightc.json").exists(), "wiped at the next guest start")
(paths.CONFIG / "keep.json").write_text("{}")
held = session._guest_lock
session.begin_guest()                                       # another window while the first still runs
check((paths.CONFIG / "keep.json").exists(), "shared while in use")
held.close()

# a shared XDG_RUNTIME_DIR where someone else planted grimoire/ as a link: the guest profile refuses it
held = session._guest_lock
held.close()
run_dir = Path(os.environ["XDG_RUNTIME_DIR"])
precious = box / "precious"
(precious / "guest-profile").mkdir(parents=True, exist_ok=True)
(precious / "guest-profile" / "keep.txt").write_text("mine")
(run_dir / "grimoire").rename(box / "grimoire-real")
(run_dir / "grimoire").symlink_to(precious)
try:
    session.begin_guest()
    check(False, "guest refuses a linked runtime folder")
except OSError:
    check((precious / "guest-profile" / "keep.txt").exists(), "nothing wiped through the link")
(run_dir / "grimoire").unlink()
(box / "grimoire-real").rename(run_dir / "grimoire")
os.chmod(run_dir / "grimoire", 0o777)
try:
    session.begin_guest()
    check(False, "guest refuses a world-writable runtime folder")
except OSError:
    check(True, "guest refuses a world-writable runtime folder")
os.chmod(run_dir / "grimoire", 0o700)
session.begin_guest()
(paths.guest_dir() / "keep.json").write_text("{}")             # what this guest set up

# a backup or setup with a corrupt compressed member is refused with its own error, not a crash
import io
import zipfile
from grimoire import backup as _backup
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("config/a.json", '{"x": "' + "a" * 5000 + '"}', zipfile.ZIP_DEFLATED)
    z.writestr("manifest.json", '{"format": "grimoire-backup", "format_version": 1, "files": []}')
raw = bytearray(buf.getvalue())
at = raw.find(b"PK\x03\x04") + 30 + len("config/a.json")
raw[at:at + 6] = bytes(x ^ 0xFF for x in raw[at:at + 6])
try:
    _backup.inspect(bytes(raw))
    check(False, "corrupt member refused")
except _backup.BackupError:
    check(True, "corrupt member refused")

# guest → new account keeps the guest's settings
with FakeSupabase():
    s3, _ = b.sign_up("carol", "carol password 1")
    session.begin(s3, remember=False, from_guest=True)
    check((paths.PROFILES / s3.user.id / "keep.json").exists(), "guest settings migrated")
    check(not (paths.PROFILES / s3.user.id / "sightc.json").exists(), "not seeded from the old top level")
    check(ring.load(accounts.keyring_attrs(s3.user.id)) is None, "not remembered → no token stored")

print(f"ok: {ok} checks")
