# Security and privacy

Grimoire Linux runs as you. It only asks for your password (through `pkexec` and KDE's own prompt) for the few
things that change the system, and those go through small helper scripts that know a fixed list of actions:

| Helper (source in `grimoire/spells/<spell>/root-helper.sh`) | Used for | Keeps a backup in |
|---|---|---|
| `mural-root-helper.sh` | login screen (SDDM) and boot (Plymouth) themes | `/etc/sddm.conf.grimoire-backup`, `/var/lib/grimoire-plymouth-previous`, so Restore works |
| `optimizel-root-helper.sh` | system tweaks (sysctl.d, journald, zram, GRUB, services…) | `/var/lib/grimoire-optimizel` |
| `systeml-root-helper.sh` | other users' processes, system services, emptying swap | (nothing to restore) |
| `focusl-root-helper.sh` | a marked block of focus-time sites in `/etc/hosts` | `/var/lib/grimoire-focusl`; the block is removed when the session ends |
| `updatel-root-helper.sh` | `apt-get update`/upgrade of checked package names, system Flatpaks, snaps, fwupd devices | (apt keeps its own log); upgrades are simulated first, removals need `--removals=` with the exact list confirmed in the preview (anything else is refused before changes), `kubuntu-desktop`/IBM Plex fonts are never removed |
| `storel-root-helper.sh` | installing/removing checked APT package names, system Flatpak apps (`app/…` refs from a checked remote) and snaps | (apt keeps its own log); each APT step is simulated right before it runs: removing anything Essential, Priority required/important or on its protected list (the desktop, its fonts, boot and system packages) is refused, other removals must match `--removals=` from the preview, removals never purge |

Every helper validates its arguments and refuses anything else; files it writes carry a Grimoire mark so "off"
only ever removes what Grimoire put there. Your own files are never deleted: they go to the Trash.

Some spells change per-user services without a password: AudioL's equalizer writes one PipeWire drop-in
(`~/.config/pipewire/filter-chain.conf.d/grimoire-eq.conf`, marked as Grimoire's) and restarts your
`filter-chain.service` only when you press Apply.
CloudL writes one user service per cloud drive you mount (`~/.config/systemd/user/grimoire-cloudl-<name>.service`,
marked as Grimoire's) and starts it only when you press Mount. The accounts' keys live in rclone's own
`rclone.conf`, written by rclone's sign-in; Grimoire never reads that file, and the sign-in's output is never saved.

### Where the helpers live

pkexec only ever runs a **root-owned system copy** of a helper, never the one in your per-user install
(`~/.local/share/grimoire/app` is writable by anything running as you, so a helper there could be edited before the
next password prompt and run as root):

- `./install.sh` puts them in `/usr/local/libexec/grimoire-linux/` (root:root, 0755) with a polkit action file,
  `/usr/share/polkit-1/actions/io.github.cookedaj.grimoire-linux.local.policy`. It asks for your password once, and
  again only when a newer version changes a helper (it compares sha256 sums). The root step is a fixed script that
  decodes the helpers into a root-only temp folder and installs them from there, so nothing can swap a file in
  between. `./install.sh --no-system` skips it; without the helpers only the root features are unavailable.
- The .deb and AUR packages put them in `/usr/libexec/grimoire-linux/` with
  `/usr/share/polkit-1/actions/io.github.cookedaj.grimoire-linux.policy`.
- Before every run, Grimoire checks that the helper and every folder above it up to `/` are owned by root, aren't
  symlinks and aren't writable by group or others. If not, or if the helper is missing, it refuses and says so
  ("System helpers aren't installed / aren't safe to run; run ./install.sh again"); it never falls back to the
  per-user copy.
- The polkit actions name Grimoire Linux in the prompt and use `auth_admin_keep`: a second root action from the same
  app within a few minutes doesn't ask again.
- `uninstall.sh` removes the `/usr/local` helpers and their polkit file with one prompt (and prints the command if
  you cancel); a package's helpers go with the package.

What this doesn't cover: something already running as you could still start its own `pkexec` prompt, or change the
per-user Python code to ask for root differently. Only answer a password prompt you expected; Grimoire's own say
"Grimoire Linux … needs your password" and name the helper under `/usr/local/libexec` or `/usr/libexec`.

## Network

Nothing is sent anywhere unless you ask, except the update check: every few hours Grimoire asks GitHub's public
API for the newest commit on `main` (no account, no identifiers beyond a normal HTTPS request; turn it off in
Settings → General or with `GRIMOIRE_NO_UPDATE_CHECK=1`). Packaged installs (.deb, AUR) don't check at all.
On demand only: the MuraL community store (KDE Store, Wallhaven) when you open it and install, NetL's public IP and
ping checks when you press them, UpdateL's Check now (Flatpak remotes, fwupd metadata; its optional daily check does
the same) and changelogs when you open one, StoreL's app sizes (`flatpak remote-info`), screenshots and remote icons (HTTPS
from Flathub's and Ubuntu's media servers) when you open an app, its Snap search and "download the app list again",
GitHub sign-in / gist backup, and your Grimoire account (sign-in, settings sync)
when you use one; guests never go online for it. There is no telemetry and no analytics.
Once you put WidgetL's Weather widget on the desktop and pick a place, it asks Open-Meteo (api.open-meteo.com) for
the forecast at that place's coordinates every 30 minutes; its city search (geocoding-api.open-meteo.com) sends what you
typed, only when you press Search. Your location is never looked up from your IP address.
CloudL's mounts talk to the cloud services you signed in to (through rclone) while they're mounted; signing in opens
the service's own page in your browser.

## Sign-in and backups: threat model

- **No password, no server.** Sign-in is GitHub's OAuth *device flow*: Grimoire shows a code, you approve it on
  github.com in your own browser. There's no redirect or local web server, so nothing to forge (no CSRF `state`
  needed), and no client secret exists, in the repo or anywhere else.
- **Least access.** The token only gets the `gist` scope: it can read and write your gists, nothing else on your
  account. Revoke it any time at github.com/settings/applications (Sign out links there; GitHub doesn't let an app
  without a client secret revoke its own token).
- **Token storage.** Only in the system keyring (Secret Service: KWallet on Plasma), as an item with
  `application=grimoire, service=github`. Never in a file, a log, an error message or the UI; inside Grimoire it's
  wrapped so printing it shows `Token(…)`. It crosses the local session bus to the keyring unencrypted ("plain"
  session), like most keyring clients.
- **Secret isn't private.** The backup gist is *secret*: unlisted, but anyone who has its link can read it. It holds
  your Grimoire settings (which can include local file paths such as wallpaper locations), never the token.
- **Restores are untrusted input**, whether a file or the gist: zip only, size and file-count caps, only known
  relative paths under Grimoire's config/data folders, no absolute or `..` paths, no links or special files, every
  file matching the manifest's sha256, JSON that parses; unknown files are ignored and nothing is executed. Machine
  "undo" state (OptimizeL's originals, store install records) is never backed up or restored. A safety backup is
  made before anything is written, and each file is replaced atomically.
- **Network.** All calls run off the UI thread with clear messages for offline, rate limits (GitHub's slow_down and
  hourly limits are respected) and revoked sign-ins. Only github.com, api.github.com, gist.githubusercontent.com and
  avatars.githubusercontent.com are contacted.

## Shared setups

- **What goes out.** A `.grimoire-setup` file or `GS1-` code holds the look only: MuraL designs and options, the
  wallpaper playlist by file name (pictures only if you tick it), store items by store id, crosshair and terminal
  profiles, LaunchL's favorites order, the tray meter. Never accounts, tokens, gist ids, tidy rules, history, network
  or usage data, TerminalL's palette commands or any path. Before writing, every string (title, author, names,
  options) is checked for your home path, `/home/` paths, your user name, the computer's name and email addresses;
  a match stops the export and says where it is.
- **What comes in is untrusted.** Checked like a restore (zip only, size and count caps, allowlisted names, no
  links, absolute or `..` paths, no encryption, sha256 per file, pictures must really be PNG/JPEG/WebP), then
  `setup.json` is rebuilt from a schema: unknown keys dropped, numbers clamped, text length-capped with control
  characters removed and `<` `>` replaced, design and theme ids checked against what Grimoire knows. Palette commands
  are never read from a shared file. Text from it is only shown as plain text. A safety backup comes first, files are
  written atomically, pictures never overwrite (a clash becomes "name (2).png"), and nothing changes the desktop or
  downloads from the store until you click.

## Accounts and guest mode: threat model

Grimoire Linux asks you to sign in or continue as a guest. Accounts live on one Supabase project (managed
Postgres + Supabase Auth); its schema is in `supabase/migrations/`, its setup in `supabase/README.md`. The client
is `grimoire/accounts.py` (no extra dependencies, every call off the UI thread), the local side `grimoire/session.py`.

**What an account is for.** Signing in picks which settings folder Grimoire uses on this PC and lets those settings
follow you to other PCs. It is not encryption and not a lock: anything running as your Linux user can read
`~/.config/grimoire` (every profile, the guest one too) just as it can read the rest of your home folder. Your
Linux login is what protects your files; Grimoire doesn't pretend otherwise and doesn't encrypt settings.

**Profiles on this PC.** Each account gets `~/.config/grimoire/profiles/<account id>/` (0700). The first account
signed in on a PC starts with a *copy* of the settings Grimoire had before accounts (the originals stay put).
`session.json` (0600, written atomically) remembers the last account (id, username, how it signed in) and
whether to stay signed in; it holds no token. Timers, the tray and hotkeys use the last signed-in account's
profile. Machine state (OptimizeL's originals, history) stays shared in `~/.local/share/grimoire`, because it
describes the PC, not a person.

**Guest.** Works offline and never talks to the account server. Its profile is in `$XDG_RUNTIME_DIR` (memory,
gone at logout) and is emptied when the next guest session starts, unless another guest window still uses it
(a file lock decides). "Create account to keep them" copies it into the new account's profile.

**Usernames without email.** Supabase Auth needs an email, so a username account signs in with
`<username>@users.grimoire.invalid`, an address that can't exist (RFC 2606) and is never mailed; "Confirm
email" is off for that reason. The email you may type at sign-up is stored on your private profile row
(only you can read it, through row-level security), never used to sign in and never sent anywhere by Grimoire.
Because the login address is derived from the username, no endpoint turns a username into an email address.
Triggers refuse any sign-up whose synthetic address doesn't match its username and any later change of such an
address, so one account can't take over another username's sign-in.

**Account enumeration.** Sign-up says when a username is taken (it has to). Sign-in answers "wrong username or
password" for both cases. The recovery function counts failures for unknown usernames too, always runs one
bcrypt, and answers the same for "no such user" and "wrong code".

**Brute force.** Supabase rate-limits sign-ins and sign-ups per IP (Authentication → Rate Limits). The app
additionally waits after repeated wrong passwords for a username (5 failures → 30 s, doubling, up to 15 min,
kept in `~/.cache/grimoire/signin-throttle.json`; a local courtesy, not a security boundary). Passwords need at
least 10 characters (set the same minimum in Supabase). Captcha (hCaptcha or Cloudflare Turnstile, under
Authentication → Attack Protection) is available against sign-up spam; this version doesn't show one yet, so
enabling it would block sign-ups until the app supports it.

**Recovery codes.** Shown once at sign-up (copy, or save as a 0600 text file), 80 random bits, stored only as a
bcrypt hash in a table the API can't reach. `recover_account()` checks it with a per-username lockout (5 wrong →
30 s, doubling, up to 15 min), sets the new password (bcrypt, as Supabase Auth stores them), signs the account
out everywhere and returns a fresh code; the used one stops working. Anyone holding your code can reset your
password: keep it like a password. Someone with a stolen live session could also issue a new code; signing out
everywhere (a password reset does that) ends it. Google/GitHub accounts recover through Google/GitHub.

**Row-level security.** `profiles`, `user_settings` and the recovery tables have RLS on; the API roles get only
the grants they need (`authenticated` may read its own profile, change only its email, and read/write only its
own settings row; `anon` may only call `recover_account`). Functions that touch `auth` are `security definer` with
an empty `search_path`, and nothing else is executable by the API roles. The publishable key in the app grants
nothing beyond these policies; the service-role key is never in the app or the repo.

**OAuth (Google, GitHub).** Through Supabase's providers with PKCE (S256): the app opens your browser at
`/auth/v1/authorize`, listens once on `127.0.0.1` on a random port at `/callback/<random state>` (compared in
constant time; other paths get 404), and exchanges the code with its verifier at `/auth/v1/token?grant_type=pkce`.
A code caught by anything else is useless without the verifier, which never leaves the process. Requests are never
logged (the query holds the code). Google is asked only for `openid email profile`.

**Tokens.** The access token lives in memory only. The refresh token is stored only in the system keyring
(KWallet; `application=grimoire, service=account, user=<id>`) and only when "Keep me signed in" is ticked;
otherwise it's forgotten when Grimoire closes. Tokens print as `Token(…)`, passwords are only passed through, and
error messages are fixed texts or server error codes, never request or response bodies. Requests to the account
server never follow redirects (they carry the key and token), and only https is accepted (plain http only for a
`127.0.0.1` test server).

**Settings sync.** The same `.grimoire-backup` zip as a file (without MuraL's wallpaper library), at most 1 MB,
in your `user_settings` row. Restoring it goes through the same checks, preview and safety backup as any backup
file. The older GitHub gist backup stays available in Settings → GitHub backup as an optional extra.
