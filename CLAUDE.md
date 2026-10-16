# Grimoire Linux — notes for Claude

A black & white suite of desktop tools ("spells") for KDE Plasma 6 (Wayland), written in Python + PySide6.
Public repo: github.com/cookedaj/grimoire-linux (old names redirect). Runs on the owner's own Kubuntu 26.04 machine.
Product name "Grimoire Linux" (`grimoire.NAME`) wherever users see it; the package, commands (`grimoire*`), config
folders, desktop file ids and app ids keep the short name `grimoire` so existing installs keep working. GPL-3.0-or-later:
new files start with an `SPDX-License-Identifier: GPL-3.0-or-later` line (after any shebang).

## Spells
| Spell | Package | What |
|---|---|---|
| MuraL | `grimoire/spells/mural/` | customizes every screen/surface; tabs built on `screens.py:ScreenTab`; community store in `store.py` + `storeview.py` |
| SightsL | `grimoire/spells/sightc/` | layer-shell crosshair overlay (`overlay.py`/`overlay.qml`), drawing in `draw.py`, settings/presets/profiles in `config.py`, hotkeys via KGlobalAccel |
| VaultL | `grimoire/spells/vaultl/` | file manager with tidying built in (FileL + TidyL merged); `page.py` window (Tidy section in the sidebar), `ops.py` file operations, `tidyview.py` tidy panels, `tidy.py` sorting engine (migrates TidyL's json/log once by copying), `launch.py` sorts opened files into programs/scripts/.desktop/Windows/macOS (no Qt; `RUN` is the stub point) and `runview.py` asks Run / Open as text / Cancel (KIO refuses executables from `openUrl`; runs via `QProcess.startDetached`, launchers via `gio launch`, never a shell), `cli.py` (timer keeps the name `grimoire-tidyl.timer`), `__main__.py` standalone window (default for inode/directory). `grimoire-filel`/`grimoire-tidyl` stay as aliases; `standalone.MERGED` keeps their old desktop entries as hidden aliases |
| OptimizeL | `grimoire/spells/optimizel/` | speed tweaks as persistent on/off switches (tier Safe/Aggressive, gain, risk); tweak kinds + detection in `kinds.py` (sysctl.d, tmpfiles.d, udev, GRUB, modprobe.d, units…), the catalog + checks + `apply()` in `tweaks.py`, one-click plans in `profiles.py`, before/after tests in `bench.py` (child process) + `benchview.py`; system ones in its own whitelisted `root-helper.sh` (test with `OPTIMIZEL_ROOT=<sandbox> OPTIMIZEL_DRY=1 OPTIMIZEL_UID=$(id -u)`; the same `OPTIMIZEL_ROOT` makes the Python side read the sandbox) |
| SystemL | `grimoire/spells/systeml/` | system monitor; `probe.py` readings (psutil, one `Sampler` per page, rates from the previous sample), `graph.py` B&W graphs, `history.py` per-app minutes, `system.py` signals/priority/services/startup/disks, `root-helper.sh` for root actions, `page.py` panels (samples only while visible), `alerts.py` background alert check (no Qt; timer `grimoire-systeml-alerts.timer`, `grimoire-systeml alerts …`) + `alertview.py` its panel |
| TerminalL | `grimoire/spells/terminall/` | terminal emulator; `emulator.py` pyte screen + scrollback/alt screen/xterm extras and an input filter, `session.py` PTY + shell (via `setsid -c`, read with QSocketNotifier), `keys.py` key encoding, `view.py` painter/selection/search/mouse, `page.py` tabs/splits/search/palette/profiles, `config.py` (`terminall.json`). Needs `python3-pyte`; without it the page shows the apt command. Test with `uv pip install --target <sandbox>/pydeps pyte` + PYTHONPATH |
| NetL | `grimoire/spells/netl/` | network monitor + quick controls; `probe.py` interface rates, addresses, `ss` parsing and per-app TCP bytes (`AppMeter` diffs per-socket counters), `nm.py` nmcli wrappers (`nm.RUN` is the stub point for tests; Wi-Fi keys go through a 0600 passwd-file in `$XDG_RUNTIME_DIR`), `usage.py` day/month totals (no Qt; timer `grimoire-netl-usage.timer`, `grimoire-netl usage …`), `page.py` + `wifiview.py` + `usageview.py` panels; reuses SystemL's graphs/tables. Never switch networks/VPNs/radios in tests |
| ShotL | `grimoire/spells/shotl/` | screenshots + recording; `capture.py` stills via `spectacle -b` (region/monitor cut from a full grab, `region.py` picker), `editor.py` B&W annotation as a replayed op list (undo = pop), `record.py` separate recorder process (portal ScreenCast → GStreamer → ffmpeg nvenc/x264, VP8 fallback; SIGINT stops, state in CACHE/shotl/recording.json), `shots.py` settings/history (no Qt), `__main__.py` CLI `grimoire-shotl region|window|full|screen|record`. Test recording with `record.encode(<videotestsrc>, …)`; a real `record start` pops KDE's share dialog |
| LaunchL | `grimoire/spells/launchl/` + `plasma/com.cookedaj.grimoire.launchl/` | panel launcher widget (QML on Plasma's kicker models, `X-Plasma-Provides` launchermenu so Meta opens it); `panel.py` installs it and swaps it for Kickoff (desktop scripts built by `replace_script`/`restore_script`, record in `launchl.json`), `page.py` the page, `python3 -m grimoire.spells.launchl` the CLI (uninstall.sh restores Kickoff with it). Never declare `Kicker.*`-typed QML properties (fails inside plasmashell); test in a nested `kwin_wayland --virtual` + plasmashell with its own HOME/bus, not only plasmawindowed |
| GameL | `grimoire/spells/gamel/` | game library; `library.py` read-only readers (Steam roots incl. Flatpak + `libraryfolders.vdf`/`appmanifest_*.acf`/`localconfig.vdf` via `vdf.py`, Heroic `installed.json`s + `store/timestamp.json`, Lutris `pga.db` mode=ro; no Qt, `status_line()`), `launch.py` (`RUN` is the stub point: never launch real games in tests), `overlay.py` settings (`gamel.json`) + B&W MangoHud.conf (moves a foreign one aside with `free_name`), `page.py` grid/list/details + Overlay + Performance mode (`optimizel/perfmode.py`). Everything manual: no per-game automatic changes. Test with a fake library in a sandbox HOME |
| UpdateL | `grimoire/spells/updatel/` | all system updates; `sources.py` reads APT/Flatpak/Snap/fwupd as you (`sources.RUN` + `APT_SIZES` are the stub points), changelogs, `apt-get -s` simulation (`PROTECTED`: kubuntu-desktop, IBM Plex fonts), `apply.py` plans + one helper batch (`step + step`, `ROOT_COMMAND` swappable) + user Flatpaks, streamed, `daily.py` cache/status line/notify (no Qt; timer `grimoire-updatel-check.timer`, `grimoire-updatel check …`), `preview.py` the removal preview, `page.py`. Opening the page reads only the cache (no network). Test the helper with stub apt-get/flatpak/snap/fwupdmgr on PATH and `UPDATEL_DRY=1`; never run a real upgrade |
| AudioL | `grimoire/spells/audiol/` | sound on PipeWire; `pw.py` one `pw-dump` parsed into outputs/inputs/streams/cards + writes via `wpctl` (volume on the cubic scale, default, mute, `set-profile`) and `pactl move-sink-input` (else `pw-metadata target.object`); `pw.RUN` is the stub point. `eq.py` 10-band filter-chain drop-in (`filter-chain.conf.d/grimoire-eq.conf`, checked by `spa-json-dump`, settings in `audiol.json`), Apply restarts `filter-chain.service` (explicit button), live gains via `pw-cli set-param`; `eqview.py` curve + presets, `meter.py` `pw-record` level meters, `page.py` panels (polls only while visible). Never change real volumes/defaults/profiles or restart PipeWire in tests: stub `pw.RUN`; test the EQ graph on a private `pipewire` with its own `XDG_RUNTIME_DIR`/`PIPEWIRE_RUNTIME_DIR` |
| WidgetL | `grimoire/spells/widgetl/` + `plasma/com.cookedaj.grimoire.widget.{clock,system,weather,nowplaying}/` | desktop widgets; each package's `Face.qml` is plain QtQuick (data in through properties, `qsTr`) so `preview.py` renders the same file offscreen in a child process for the page (cached in CACHE/widgetl by the faces' hash); `main.qml` feeds it (ksysguard `Sensor`s, Open-Meteo by XHR every 30 min with no IP lookup, `Mpris2Model` as `var`, never typed); every config key needs `cfg_<key>` and `cfg_<key>Default` in `ConfigGeneral.qml`. `widgets.py` (no Qt) installs with kpackagetool6, `add_script`/`remove_script` build the desktop scripts, `plasma_script` is the stub point; `python3 -m grimoire.spells.widgetl` the CLI (uninstall.sh takes them off desktops/panels first; exit 3 keeps them when Plasma is down). Nested test: also set `XDG_CONFIG_DIRS=/etc/xdg`, `XDG_DATA_DIRS`, a sandbox `XDG_RUNTIME_DIR` and start kactivitymanagerd before plasmashell. "Created graphical object was not placed in the graphics scene" on config pages is Plasma's own (any applet) |
| PhoneL | `grimoire/spells/phonel/` | phone link on KDE Connect's daemon (never its own pairing/crypto); `kdc.py` GDBus client (no Qt; every call NO_AUTO_START, `ADDRESS`/`START` are the stub points; devices, pair/unpair, share, ping, findmyphone, clipboard, sftp mount → VaultL via `page.OPEN_FOLDER`, notifications, SMS structs, mprisremote, remotecommands, remotekeyboard/remotecontrol, plugin switches, read-only contact names from kpeoplevcard), `listen.py` signals on a thread with its own GLib context (SMS only arrive as signals), `page.py` frame + pairing + not-running states, `views.py` device tabs, `sms.py` messages. Pair/unpair/accept/SMS always ask. Test only against `scripts/fake_kdeconnect.py` (private dbus-daemon with no service dirs); never pair, ring or text a real device; read-only calls on the real daemon are fine |

Tray: `grimoire/tray.py` (`grimoire-tray`, QSystemTrayIcon → StatusNotifierItem): live CPU/RAM bars drawn by
`glyphs.meter()`, menu for crosshair/tidy/performance mode/spells, single instance via a QLocalServer socket in
`$XDG_RUNTIME_DIR`, opt-in autostart `~/.config/autostart/grimoire-tray.desktop` (home page checkbox or its menu).
Performance mode lives in `optimizel/perfmode.py` (flips `IDS` through `tweaks.apply`, records what it changed).

Shell: `grimoire/app.py` (icon rail, home, `style_app()`), icons drawn in code in `grimoire/glyphs.py`, styles in
`grimoire/theme.py` (QSS). New spells register in `grimoire/spells/__init__.py` (`Spell(id, name, tagline, page, icon,
status)`). Folder names stay as-is when display names change (e.g. SightsL lives in `sightc/`).

## Style rules (the owner cares about these)
- Strictly black & white: no accent colors, Fusion style + the monochrome palette in `style_app()`.
- Sleek and simple; new icons are line glyphs in `glyphs.py`, never colored theme icons in Grimoire's own chrome.
- New spells are named `<Word>L` (MuraL, SightsL, VaultL). Spells get a page, a rail icon and a status line.
- Match surrounding code: small focused modules, short docstrings on the "why".

## Safety rules
- Never permanently delete user files: use the Trash (`gio trash`, or the freedesktop spec as in `vaultl/ops.py`);
  never overwrite on name clashes (`free_name()` → "name (2).ext").
- Anything needing root goes through a spell's `root-helper.sh` via `pkexec` (MuraL's, OptimizeL's, SystemL's or FocusL's:
  whitelisted actions, validated input, old values backed up), always through `grimoire/roothelper.py`
  (`roothelper.run(spell, …)`/`command()`): pkexec runs only the root-owned system copy
  (`/usr/libexec/grimoire-linux/<spell>-root-helper.sh` from packages, `/usr/local/libexec/grimoire-linux/` from
  install.sh, one prompt when they change, `--no-system` skips), checked before every run (root-owned up to `/`, no
  group/world write, no symlinks), never the user-writable copy in the tree. A new helper goes in `roothelper.SPELLS`
  (its polkit message). Helpers must not read code or data from their own folder (they run from /usr/…/libexec).
- Simulate package removals (`apt-get -s`) before suggesting them; never let `kubuntu-desktop` or IBM Plex fonts go.
- Community store downloads happen only on the user's Install click; keep the defensive extraction in `store.py`.
- Never commit personal info: author `cookedaj` with the GitHub noreply email; no `/home/<user>` paths or real names.

## Testing (do this before saying something works)
- Render UI offscreen: `QT_QPA_PLATFORM=offscreen` + `QWidget.grab().save(...)`, then look at the image.
- Test file operations in a sandbox under `~/.cache/…` (not `/tmp`: gio can't trash from there) and clean up.
- Live checks on the desktop: `qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '…'`,
  `journalctl --user` for plasmashell/QML errors. plasmashell caches QML: restart it after plugin edits.
- Don't `pkill -f <pattern>` with a pattern that also matches your own shell command; anchor it (`^python3 -m …`).
- Qt signals carrying sizes/large numbers: use `object`, not `int` (32-bit overflow).
- Root helpers: never run them with sudo/pkexec here. Test them as you on a sandbox (`OPTIMIZEL_ROOT`/`OPTIMIZEL_DRY`,
  `FOCUSL_ROOT`/`FOCUSL_DRY`; `roothelper.source(spell)` is the tree's copy) and the callers with a stub `pkexec` on
  PATH plus `roothelper.LOCAL_DIR`/`PACKAGE_DIR` pointed at a sandbox and `roothelper.unsafe` stubbed (or
  `TRUSTED_UIDS.add(os.getuid())` on a folder chain nobody else can write).
  Test install.sh/uninstall.sh's system step with a stub pkexec and `GRIMOIRE_SYSTEM_TEST=1
  GRIMOIRE_SYSTEM_PREFIX=<sandbox>` (ignored without the TEST var), in a sandbox HOME.

## Install / run
`./install.sh` copies the app (rsync, no `.git`) into `~/.local/share/grimoire/app`, links its `bin/*` into
`~/.local/bin`, writes desktop entries and copies the MuraL wallpaper plugin; re-running it from a newer checkout
upgrades. Nothing installed may point into the clone (public repo: it must work from any download location), so
after editing code, re-run `./install.sh` to see it in the menu apps. `uninstall.sh [--purge]` undoes it.
Run `grimoire [spell-id]`, `grimoire-vaultl [folder]`, `grimoire-sightc on|off|next`, `grimoire-vaultl tidy run`.
Standalone spells: `grimoire/standalone.py` opens any spell in its own window and writes its launcher (command link,
glyph icon, menu entry; links target the installed copy when there is one); a spell gets an Install button on its home card once `bin/grimoire-<id>` exists (no args
opens the window). `./install.sh --all` installs every launcher; plain `./install.sh` refreshes installed ones.
Self-update: install.sh records the source commit in `app/INSTALLED.json` (`GRIMOIRE_SOURCE_SHA` from the updater, else
the checkout's HEAD); `grimoire/update.py` compares it with GitHub main (API answers cached in CACHE, 60 req/h limit),
downloads codeload's tarball, extracts it defensively and runs its install.sh; `updateview.py` is the hub's UI and
`grimoire update [--check]` the CLI. Test it with HOME/XDG dirs in a sandbox, never against the real install.
Settings (gear at the foot of the rail): `settingsview.py` lays out Qt-free modules: `hotkeys.py` (KGlobalAccel via
busctl through a swappable `BUS`; commands bind as hidden `grimoire-hotkey-<id>.desktop` components with `_launch`;
conflicts checked against allShortcutInfos), `backup.py` (`.grimoire-backup` zip + manifest; strict `inspect()`, safety
backup in `DATA/backups`, atomic writes; allowlist in `RULES`/`EXCLUDE`), `prefs.py` (`settings.json`: auto_update,
gist_id; open-at-login autostart), `github.py` (device flow + gists, `HTTP` swappable, `Token` hides itself),
`github_app.py` (`GITHUB_CLIENT_ID`, env `GRIMOIRE_GITHUB_CLIENT_ID`), `keystore.py` (Secret Service over dbus-python;
PySide6 QtDBus can't marshal a{ss}/(oayays)). Test hotkey writes with a stub `BUS`, never the real KGlobalAccel; test
the keyring only with throwaway attributes you delete. Threat model: docs/security.md.
Dependencies are Ubuntu's `python3-pyside6.*` packages (no pip on this system); `uv` is available for side tools.
Packages: `packaging/stage.sh DESTDIR KIND` lays out the system-wide tree (`/usr/share/grimoire-linux` + `PACKAGED`
marker, `/usr/bin` links, menu entries, icons, MuraL plugin, AppStream, root helpers in
`/usr/libexec/grimoire-linux` + polkit actions; the app tree carries no helper copies) for both `packaging/debian` (hand-written
rules, no debhelper; `packaging/build-deb.sh` builds under ~/.cache, never install it here) and `packaging/aur`.
`paths.packaged()`/`command()`/`unit_command()` make timers/autostart/hotkeys run `/usr/bin` commands there and
`update.managed()` turns the self-updater off. Releases: `scripts/release.sh X.Y.Z` (bump, changelog, PKGBUILD,
commit, tag; no push), then `.github/workflows/release.yml` builds and publishes on the pushed tag. README images:
`python3 scripts/screenshots.py [names]` (sandbox home, no session bus, NetL addresses faked); look at each one.
User-facing docs: README.md (pitch, spells, install, FAQ), docs/how-it-works.md, docs/security.md.

## Git
Branch `main`, push to `origin` (github.com/cookedaj/grimoire-linux). Commit messages: a short title + bullet body.
Parallel work goes in git worktrees under `.worktrees/<name>` (gitignored, skipped by `install.sh`), never as sibling
folders next to the repo; remove them with `git worktree remove` once merged, keep the branch.

## FocusL
`grimoire/spells/focusl/`: Pomodoro timer. `store.py` settings/state/control/history/stats (no Qt), `runner.py` the
background session (`grimoire-focusl run`, single instance by flock on `CACHE/focusl.lock`, cleans up on
SIGTERM/INT/HUP; the page and CLI steer it through `focusl-control.json`), `guards.py` DND (`Inhibit` on
org.freedesktop.Notifications, auto-released by Plasma if we die), crosshair, app blocking, sites via its
`root-helper.sh` (marked block in /etc/hosts; test with `FOCUSL_ROOT=<sandbox>`), `dial.py` ring + bars, `page.py`.
Test with `FOCUSL_DRY=1` (logs DND/notify/kill/crosshair, hosts helper on a sandbox copy) and a sandbox HOME.

## Share setup
Settings → Share setup: `grimoire/sharesetup.py` (Qt-free at import; schema built lazily from MuraL's tab modules)
exports the look as `.grimoire-setup` (zip: manifest + `setup.json` + `preview.png` + optional `wallpapers/`) or a
`GS1-` code (zlib + base64, ≤2 KB); `scrub()` refuses home path/user/host/email; `inspect()`/`from_code()` validate
like `backup.inspect()` and `clean()` rebuilds every field (never TerminalL `commands`); `apply()` = safety backup →
wallpapers into the library (`free`-style names) → a MuraL saved look + sightc/terminall/tray files; `apply_look()`
(user click only) runs `looks.restore` + LaunchL `write_order`; store refs install via `store.fetch()`+`install()`.
`shareview.py` is the panel + preview dialog. Test with two sandbox HOMEs (export on one, import on the other) and
stub `looks.restore`/`panel.write_order`; never apply a look to the live desktop.

## Accounts
Sign-in screen + guest mode + first-run setup (not a spell). `paths.py` picks the profile before any spell imports
(`CONFIG` = `CONFIG_ROOT/profiles/<account uuid>/`, guest `$XDG_RUNTIME_DIR/grimoire/guest-profile`, else
`CONFIG_ROOT`; `GRIMOIRE_PROFILE` env, else `session.json`'s last account); `paths.activate()` switches it and says
when a loaded module holds the old one (then `loginview.restart()` re-execs). `accounts.py` backend interface +
Supabase client (GoTrue/PostgREST over urllib, `HTTP` swappable, username → `<name>@users.grimoire.invalid`,
PKCE `Loopback`, recovery codes, sync), `supabase_app.py` URL/anon key (env `GRIMOIRE_SUPABASE_URL`/`_ANON_KEY`),
`session.py` (session.json, profiles, guest lock/wipe, seeding, refresh token in keyring via swappable `KEYRING`),
`loginview.py` (`gate()` in app/standalone/vaultl/terminall mains; imports there must not bind CONFIG),
`setupwizard.py`, `accountview.py` (Settings → Account, guest bar, auto-sync). Server SQL in
`supabase/migrations/`, setup in `supabase/README.md`. Test with `python3 scripts/test_accounts.py
~/.cache/<sandbox>` (in-process `scripts/fake_supabase.py`, fake keyring); never against a real project.

## Languages (i18n)
`grimoire/i18n.py`: `LANGUAGES` (en, zh_CN, hi, es, fr, ar, bn, pt = Brazilian wording, ru, ur; code → native name),
`current()` (env `GRIMOIRE_LANG`, else the profile's `settings.json` "locale", else `CONFIG_ROOT/language` = last
choice on this PC, else the desktop's `LANG`, else en; never imports prefs, so it binds no CONFIG before the gate),
`choose(code)`, `install(app)` (called by `style_app()`: one QTranslator per area catalog
`translations/<area>/<lang>.qm` + Qt's `qtbase_<lang>.qm`, right-to-left for ar/ur, font fallbacks as `QFont`
substitutions of "IBM Plex Sans"/"IBM Plex Mono": Plex Arabic/Devanagari, Noto Naskh Arabic UI for Urdu (Nastaliq
only in big headings via `URDU_QSS`: its 2.5x line height overflows rows), Noto Sans Bengali, Noto Sans CJK SC).
A change applies on restart (`settingsview.restart_now()`/`offer_restart()`; `loginview.gate()` restarts once when
the signed-in profile's language differs). Every QApplication goes through `style_app()` (hub, standalone windows,
tray, spell `__main__`s). The .qm files are committed (installs need no Qt tools); packages ship `translations/`.

Wrapping strings (every user-visible string; phase 2 = one area per spell, each agent touches only its area):
- `from grimoire.i18n import tr` and `tr("<context>", "Text")`. The context is the module's dotted name as a
  **string literal** (`"grimoire.app"`, `"grimoire.spells.vaultl.page"`); it decides the catalog:
  `grimoire.spells.<area>.…` → `translations/<area>/`, anything else → `translations/core/` (spell taglines and the
  status lines in `spells/__init__.py` use `"grimoire.spells"` = core). Never a variable or an f-string as context
  or text (`scripts/i18n.py` reads literals with `ast`; adjacent literals joined are fine).
- Placeholders: `tr(ctx, "Signed in as {name}").format(name=…)` (format after tr, named fields, whole sentences;
  never glue translated fragments together, never `+` a sentence from parts; " · " joins of separate bits are ok).
- Plurals: `tr(ctx, "%n file(s) moved", n=count)` (`.format()` after if needed). Qt plural forms: zh_CN 1;
  en/hi/es/fr/bn/pt/ur 2; ru 3 (one/few/many); ar 6 (zero/one/two/few/many/other). Then write the English forms
  (`export <area> en` → fill → `import`); en.ts holds only plurals.
- Disambiguation for a short word used two ways: `tr(ctx, "Open", "verb")`.
- Text made at import time (module-level tables, dataclass defaults, `Spell(...)` taglines): mark with
  `tr_noop(ctx, "Text")` and translate where shown with `tr(ctx, value)` (same context literal).
- Don't wrap: spell/product names (MuraL, Grimoire Linux), commands, paths, file names, config keys, log/CLI/terminal
  output, desktop-entry fields, polkit messages, text sent to other programs or KDE. Do wrap error messages in
  Qt-free modules that reach the UI (`tr` works without Qt; it returns English there).
- Never compare a widget's text to decide logic (it's translated); keep ids in data.
- RTL (ar, ur): layouts mirror by themselves; Switch and back/forward glyphs (`i18n.mirrored()`) flip; charts,
  meters, the terminal and canvases call `setLayoutDirection(LeftToRight)` and plot left to right (QPainter text
  alignment still follows the app direction). `import` prefixes U+200F to ar/ur translations that start with Latin,
  a digit or a `{field}` so the line still reads right to left. Inside a translated sentence, wrap paths, sizes,
  numbers with units, versions, commands and key names in `i18n.ltr(x)` (LRI…PDI) and names/titles from users or
  other programs in `i18n.isolate(x)` (FSI…PDI); both return the text unchanged in LTR languages (spells' private
  `ltr`/`isolate` copies can switch to these).
- Segmented buttons (objectName "Segment" in a row): call `widgets.segments(buttons)`, which sets the `seg`
  property theme.py styles (rounded outer ends, one border between, mirrored for RTL). Never `setProperty("pos", …)`:
  `pos` is QWidget's own position property, so it silently stays a QPoint and the selector never matches.
- Processes without windows (timers, CLI, background runners) call `i18n.install_catalogs([areas])` before tr():
  it makes/uses a bare QCoreApplication (QtCore only), loads core + those areas (None = all) and QLocale's default.
  Never in a process that makes a QApplication later (that goes through `style_app()`).
- Sizes: `fsutil.human(n)` follows the loaded language (QLocale decimal separator, units from the core catalog:
  "1,5 Ko") once `i18n.install()`/`install_catalogs()` ran; in English or without Qt it is exactly "1.5 KB".
- Letter spacing breaks Arabic/Devanagari/Bengali words apart: use `i18n.spacing(text, px)` for
  `QFont.setLetterSpacing` and pass stylesheets with `letter-spacing` through `i18n.qss(css)`. Avoid fixed widths and
  heights around text (translations run 30-60% longer).
- Workflow for an area: `python3 scripts/i18n.py update <area>` (writes `translations/<area>/<lang>.ts` for all ten),
  translate (`export <area> <lang> > todo.json`, fill each `translation` — a list in the `forms` order for plurals —
  then `import <area> <lang> todo.json`; or Qt Linguist on the .ts), `check <area>` (placeholders, %n, format()
  errors, extraction problems), `release <area>` (lrelease from qt6-l10n-tools), `stats [area]` (0 unfinished before
  committing). Translators keep product names, `{placeholders}`, `%n`, shortcuts (Ctrl+F); ar/ur write `←` for `→`.
- Test a language offscreen: `GRIMOIRE_LANG=ar QT_QPA_PLATFORM=offscreen` with a sandbox HOME/XDG dirs, build the
  widget after `style_app(app)`, `grab()` and look: no tofu boxes, no clipped text, RTL mirrored, graphs not. Check
  en, zh_CN, hi, ar, ur, bn, ru at least.
