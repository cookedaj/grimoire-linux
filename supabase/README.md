# Grimoire Linux account server (Supabase)

Accounts (username + password, or Google / GitHub) and settings sync run on one Supabase project. Until it exists,
the sign-in screen says "Accounts aren't set up yet" and offers Guest. Everything here is free-tier friendly.

What ships in the app: only the project URL and the **publishable (anon) key**, in `grimoire/supabase_app.py`
(or `GRIMOIRE_SUPABASE_URL` / `GRIMOIRE_SUPABASE_ANON_KEY`). They're public by design; the row-level security in
`migrations/` is what protects data. **Never** put the `service_role` / secret key or the database password in
the app, the repo or an issue.

## 1. Create the project

1. supabase.com → New project. Name `grimoire-linux`, a strong database password (keep it in your password
   manager, nowhere else), the region closest to you.
2. Project Settings → API (or "API Keys"): copy the **Project URL** and the **publishable / anon** key.

## 2. Apply the migrations

Either paste them in order into **SQL Editor → New query → Run**:

1. `migrations/20261014000001_profiles.sql`
2. `migrations/20261014000002_recovery_codes.sql`
3. `migrations/20261014000003_user_settings.sql`

or with the Supabase CLI: `supabase link --project-ref <ref>` then `supabase db push` (from the repo root).

Check: Table Editor shows `profiles` and `user_settings` with RLS **enabled**; Database → Functions shows
`issue_recovery_code` and `recover_account` in `public` and the rest in `private`.

## 3. Auth settings (Authentication → Sign In / Providers, and → Rate Limits)

- **Email provider: enabled. "Confirm email": OFF.** Username accounts sign in with a made-up address
  `<username>@users.grimoire.invalid` that can't receive mail, so a confirmation could never arrive. (Nothing is
  ever mailed; the optional email people type is stored privately on their profile row, not used to sign in.)
- **Minimum password length: 10** (the app asks for 10 too). Optionally "Password requirements: letters and
  digits".
- **Secure email change: ON** (default). The database also refuses any change of a `@users.grimoire.invalid`
  address.
- **Leaked password protection** (Pro plan): turn on if available.
- **Rate limits**: keep the defaults or lower them; sign-in/sign-up per IP at about 30 per 5 minutes is plenty
  for a desktop app. The app also slows down repeated wrong passwords on its own, and recovery codes lock a
  username after 5 wrong tries (30 s, doubling, up to 15 min).
- **Captcha** (Authentication → Attack Protection): available (hCaptcha or Cloudflare Turnstile), but this version
  of the app can't show one, so leave it off for now; if sign-up spam ever starts, it can be added (the app would
  open the captcha in the browser like the OAuth sign-in).

If Supabase ever refuses the `.invalid` sign-up address, use a subdomain you own without mail (for example
`users.example.org`) and change it in three places: `SYNTHETIC_DOMAIN` in `grimoire/supabase_app.py` and the two
`domain constant` lines plus the `like '%@users.grimoire.invalid'` in the migrations.

## 4. URL configuration (Authentication → URL Configuration)

- **Site URL**: `https://github.com/cookedaj/grimoire-linux` (only used as a fallback).
- **Redirect URLs**, add exactly: `http://127.0.0.1:*/callback/*`

  The app opens a one-shot listener on 127.0.0.1 with a random port and a random path part (checked when the
  browser comes back), so the allow-list needs the port and the last path part as wildcards (`*` matches anything
  without `.` or `/`). If it's missing, Supabase sends the browser to the Site URL instead and the app's sign-in
  times out.

## 5. Sign in with GitHub

This is a **new** GitHub OAuth App, separate from the device-flow one the app already uses for gist backups.

1. github.com → Settings → Developer settings → OAuth Apps → New OAuth App.
2. Name `Grimoire Linux`, homepage `https://github.com/cookedaj/grimoire-linux`,
   **Authorization callback URL** `https://<project-ref>.supabase.co/auth/v1/callback`.
   Leave "Enable Device Flow" off.
3. Generate a client secret. Paste the Client ID and secret into Supabase → Authentication → Providers →
   GitHub, and enable it. (The secret lives only in Supabase.)

## 6. Sign in with Google

1. console.cloud.google.com → create a project `grimoire-linux`.
2. APIs & Services → **OAuth consent screen** (Google Auth Platform → Branding/Audience): User type **External**,
   app name `Grimoire Linux`, your support email, developer contact. Under Data Access add only the scopes
   `openid`, `.../auth/userinfo.email`, `.../auth/userinfo.profile`. While "Testing", add yourself (and anyone
   else) under **Test users**; publish it later (these scopes don't need Google's verification).
3. Credentials (Clients) → **Create OAuth client ID** → type **Web application** (Supabase does the exchange, not
   the desktop app) → Authorized redirect URI `https://<project-ref>.supabase.co/auth/v1/callback`.
4. Paste the client ID and secret into Supabase → Authentication → Providers → Google, and enable it.

## 7. Put the URL and key in the app

In `grimoire/supabase_app.py` set `SUPABASE_URL = "https://<project-ref>.supabase.co"` and
`SUPABASE_ANON_KEY = "<publishable key>"`, or try first with

    GRIMOIRE_SUPABASE_URL=https://<project-ref>.supabase.co GRIMOIRE_SUPABASE_ANON_KEY=<key> grimoire

## Local testing without a project

`scripts/fake_supabase.py` is an in-process stand-in (auth, PKCE, recovery codes, RLS-shaped settings) used by
`python3 scripts/test_accounts.py ~/.cache/<sandbox>`. With Docker, `supabase start` also works: it serves on
`http://127.0.0.1:54321`, which the app accepts (plain http only for loopback addresses).

## Housekeeping

`private.recovery_attempts` keeps one small row per username that ever got a wrong recovery code. If it grows,
`delete from private.recovery_attempts where updated_at < now() - interval '1 day' and (locked_until is null or
locked_until < now());` (by hand, or with the pg_cron extension).
