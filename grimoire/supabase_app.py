# SPDX-License-Identifier: GPL-3.0-or-later
"""Grimoire's account server: a Supabase project (managed Postgres + Auth). Setup: supabase/README.md.

Only the project URL and its publishable ("anon") key ship in the app. Both are public by design: every request
they allow is limited by the row-level security policies in supabase/migrations/. The service_role key and the
database password never belong in the app or the repo. While these are empty, the sign-in screen says accounts
aren't set up yet and offers Guest. GRIMOIRE_SUPABASE_URL / GRIMOIRE_SUPABASE_ANON_KEY override them (testing,
a self-hosted or local `supabase start` project).
"""
import os
import re
import urllib.parse

SUPABASE_URL = "https://dvqkcrmeeorgsqyurryz.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_rvJiMQYqsv2LytIMFmkD6g_g8Qa3qAk"
# Username-only accounts sign in to Supabase Auth with a made-up address <username>@<this>: never mailed (the
# .invalid top-level domain can't exist, RFC 2606). If Supabase ever refuses it, use a subdomain you own that has
# no mail service; nothing else depends on it.
SYNTHETIC_DOMAIN = "users.grimoire.invalid"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def url() -> str:
    """The project URL, or "" when unset or not https (plain http only for a local test server)."""
    raw = os.environ.get("GRIMOIRE_SUPABASE_URL", SUPABASE_URL).strip().rstrip("/")
    try:
        p = urllib.parse.urlparse(raw)
        p.port                                             # raises on a bad port
    except ValueError:
        return ""
    ok = p.hostname and not p.username and not p.password and not p.query and not p.fragment and p.path in ("",) \
        and (p.scheme == "https" or (p.scheme == "http" and p.hostname in LOOPBACK))
    return raw if ok else ""


def anon_key() -> str:
    key = os.environ.get("GRIMOIRE_SUPABASE_ANON_KEY", SUPABASE_ANON_KEY).strip()
    return key if re.fullmatch(r"[A-Za-z0-9._\-]{20,2048}", key) else ""


def configured() -> bool:
    return bool(url() and anon_key())


def synthetic_domain() -> str:
    return os.environ.get("GRIMOIRE_SUPABASE_EMAIL_DOMAIN", SYNTHETIC_DOMAIN).strip().lower() or SYNTHETIC_DOMAIN
