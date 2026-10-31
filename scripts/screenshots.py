# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the README screenshots (docs/screenshots/*.png) offscreen, in a throwaway home, so nothing personal shows.

    python3 scripts/screenshots.py [name ...]        all of them, or e.g. hub vaultl terminall

It sets up ~/.cache/grimoire-screenshots/home (demo files for VaultL, a plain bash prompt for TerminalL, no session
bus, its own runtime dir), re-runs itself there with QT_QPA_PLATFORM=offscreen, opens the hub at 1440x900 on each
page, lets it load, grabs it and shrinks the PNG with Pillow. Look at every image before committing it: live pages
(SystemL, NetL) show this machine's numbers.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "screenshots"
BOX = Path.home() / ".cache" / "grimoire-screenshots"
W, H = 1440, 900
PAGES = ["hub", "mural", "sightc", "vaultl", "optimizel", "systeml", "terminall", "shotl", "focusl", "netl", "launchl",
         "settings", "tray", "gamel", "audiol", "widgetl"]


# ---------------------------------------------------------------- the sandbox
def _image(path: Path, seed: int, size=(960, 540)):
    """Abstract black & white art, so VaultL's thumbnails and MuraL's library have something to show."""
    import math
    from PIL import Image, ImageDraw, ImageFilter
    w, h = size
    img = Image.new("L", size, 8)
    d = ImageDraw.Draw(img)
    style = seed % 4
    if style == 0:                                       # ripples
        cx, cy = w * 0.62, h * 0.55
        for r in range(int(w), 0, -14):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=int(30 + 200 * (1 - r / w) ** 2), width=2)
    elif style == 1:                                     # dunes
        for k in range(26):
            y0 = h * (0.25 + k * 0.03)
            pts = [(x, y0 + 40 * math.sin(x / (90 + seed * 7) + k * 0.35)) for x in range(0, w + 8, 8)]
            d.line(pts, fill=int(40 + k * 8), width=3)
    elif style == 2:                                     # moon
        d.ellipse([w * 0.58, h * 0.18, w * 0.58 + h * 0.5, h * 0.68], fill=225)
        d.ellipse([w * 0.62, h * 0.14, w * 0.62 + h * 0.5, h * 0.64], fill=8)
        for i in range(160):
            x, y = (i * 7919 + seed * 31) % w, (i * 104729) % int(h * 0.8)
            d.point((x, y), fill=120 + i % 120)
    else:                                                # rain
        for i in range(0, w, 6):
            y = (i * 37 + seed * 11) % h
            d.line([(i, y), (i - 30, y + 160)], fill=50 + (i * 13) % 150, width=1)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.convert("RGB").save(path)


def sandbox() -> Path:
    home = BOX / "home"
    if BOX.exists():
        shutil.rmtree(BOX)                                   # our own throwaway folder, never user files
    for d in ("Desktop", "Documents/Projects", "Downloads", "Music", "Pictures/Wallpapers", "Videos", ".config",
              ".local/share", ".cache"):
        (home / d).mkdir(parents=True, exist_ok=True)
    files = {
        "Documents/Notes.md": "# Notes\n", "Documents/Budget 2026.ods": "", "Documents/Thesis draft.pdf": "%PDF-1.4\n",
        "Documents/Projects/README.md": "# Project\n", "Music/Intro.flac": "", "Music/Lo-fi mix.mp3": "",
        "Videos/Clip.mp4": "", "Downloads/setup-1.4.2.deb": "", "Downloads/report-q3.pdf": "%PDF-1.4\n",
        "Downloads/fonts.zip": "", "Downloads/song.mp3": "", "Downloads/notes.txt": "hello\n",
        "Downloads/editor.AppImage": "", "Downloads/data.csv": "a,b\n1,2\n", "Downloads/invoice.pdf": "%PDF-1.4\n",
    }
    for rel, text in files.items():
        (home / rel).write_text(text)
    library = home / ".local/share/grimoire/mural/library"
    library.mkdir(parents=True)
    for i, name in enumerate(("Ripples", "Dunes", "Moon", "Rain", "Dunes II", "Moonrise", "Drizzle", "Ripples II")):
        _image(library / f"{name}.png", i + (i // 4) * 5, (1920, 1080))
    for i, rel in enumerate(("Pictures/Wallpapers/Dune.png", "Pictures/Wallpapers/Rain.png", "Pictures/Mono.png",
                             "Downloads/photo-001.png", "Downloads/photo-002.png", "Downloads/screenshot.png")):
        _image(home / rel, i)
    (home / ".bashrc").write_text(
        "PS1='user@grimoire:\\w\\$ '\nexport LS_COLORS='di=1;37:ex=1;37:*.png=37:*.pdf=37'\nalias ls='ls --color=auto'\n"
        "export HISTFILE=/dev/null\n")
    (home / ".bash_profile").write_text("[ -f ~/.bashrc ] && . ~/.bashrc\n")
    run = BOX / "run"
    run.mkdir(mode=0o700)
    return home


# ---------------------------------------------------------------- rendering (inside the sandbox)
def render(names: list[str]):
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Grimoire Linux")
    from grimoire.app import Window, style_app
    style_app(app)

    def wait(ms):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    private_addresses()
    offline_stubs()
    demo_audio()
    demo_pc()
    demo_phone()
    OUT.mkdir(parents=True, exist_ok=True)
    win = Window()
    win.resize(W, H)
    win.show()
    wait(1500)
    for name in names:
        if name == "tray":
            tray_shot(wait)
            continue
        page = {"hub": "home", "printers": "settings"}.get(name, name)
        page = "home" if name == "hub" else PAGE_OF.get(name, name)
        if name == "shotl":
            seed_shots()
        win.open(page)
        prepare = PREPARE.get(name)
        if prepare:
            prepare(win.pages[page][1], wait)
        wait(WAIT.get(name, 2500))
        save(win.grab(), name)


def private_addresses():
    """NetL lists this machine's IPs and MACs; swap them for documentation addresses (RFC 5737 / 3849)."""
    from grimoire.spells.netl import probe
    real = probe.addresses

    def addresses():
        out = real()
        for i, a in enumerate(out):
            a["ipv4"] = [f"192.0.2.{10 + i}"] if a["ipv4"] else []
            a["ipv6"] = [f"2001:db8::{10 + i}", f"fe80::{10 + i}"] if a["ipv6"] else []
            a["mac"] = f"02:00:00:00:00:{10 + i:02x}" if a["mac"] else ""
        return out
    dev = next((d for _, d in probe.gateways()), "eth0")
    probe.addresses = addresses
    probe.gateways = lambda: [("192.0.2.1", dev)]
    probe.dns = lambda: [("192.0.2.1", dev), ("2001:db8::1", dev)]


def offline_stubs():
    """There's no session bus in the sandbox: show KDE's shortcut list and the panel as a fresh Plasma has them."""
    from grimoire import hotkeys
    from grimoire.spells.launchl import panel
    from grimoire.spells.sightc import overlay

    class Bus:
        def call(self, path, iface, method, sig="", *args):
            if method == "allComponents":
                return [["/component/sightsl"]]
            if method == "allShortcutInfos":
                return [[[a, n, overlay.COMPONENT, "Grimoire SightsL", "", "", [k], [k]]
                         for a, (n, k) in overlay.HOTKEYS.items()]]
            return [[]]
    hotkeys.BUS = Bus()
    panel.is_installed = lambda: True
    panel.needs_update = lambda: False
    panel.load_state = lambda: {}
    panel.scan = lambda: [{"id": 1, "order": "2;3;4", "widgets": [
        {"id": 2, "type": "org.kde.plasma.kickoff"}, {"id": 3, "type": "org.kde.plasma.icontasks"},
        {"id": 4, "type": "org.kde.plasma.systemtray"}]}]
    from grimoire.spells.launchl import appedit                  # sample apps changed with LaunchL's Edit…
    appedit.edited = lambda: [appedit.App(id="org.kde.kate.desktop", name="Kate", hidden=True, edited=True),
                              appedit.App(id="org.kde.konsole.desktop", name="Terminal", edited=True)]
    from grimoire.spells.widgetl import widgets
    widgets.is_installed = lambda wid: True
    widgets.needs_update = lambda wid: False
    widgets.scan = lambda timeout=20: [{"kind": "desktop", "containment": 1, "screen": 0, "widget": 30,
                                        "type": widgets.PREFIX + "clock"}]


def demo_audio():
    """AudioL reads the live PipeWire graph, which the sandbox can't reach: show a made-up PC's devices and apps."""
    from grimoire.spells.audiol import eq, pw

    def dev(i, name, label, vol, default=False, card=None, state="running"):
        return {"id": i, "serial": i + 100, "name": name, "label": label, "volume": vol, "mute": False, "channels": 2,
                "state": state, "card": card, "virtual": card is None, "eq": False, "default": default}

    def app(i, name, media, vol, target, state="running"):
        return {"id": i, "serial": i + 100, "name": name.lower(), "app": name, "media": media, "icon": name.lower(),
                "binary": "", "pid": None, "volume": vol, "mute": False, "channels": 2, "state": state,
                "target": target}

    def card(i, label, bus, form, active, profiles):
        return {"id": i, "name": f"card{i}", "label": label, "bus": bus, "form": form, "profile": active,
                "profile_name": "", "profiles": [{"index": n, "name": f"p{n}", "label": lab, "available": True,
                                                  "priority": 100 - n} for n, lab in enumerate(profiles)]}
    snap = {"outputs": [dev(41, "speakers", "Built-in Speakers", 62, True, 1),
                        dev(42, "hdmi", "HDMI / DisplayPort", 40, card=2, state="suspended"),
                        dev(43, "headphones", "USB Headphones", 75, card=3, state="suspended")],
            "inputs": [dev(51, "mic", "Built-in Microphone", 80, True, 1, state="suspended"),
                       dev(52, "usbmic", "USB Headphones Microphone", 100, card=3, state="suspended")],
            "playing": [app(61, "Firefox", "Lo-fi beats to focus to", 100, 41),
                        app(62, "Spotify", "Spotify", 70, 41, state="idle")],
            "recording": [], "default_output": "speakers", "default_input": "mic",
            "cards": [card(1, "Built-in Audio", "pci", "internal", 1, ["Off", "Analog Stereo Duplex", "Analog Stereo "
                                                                         "Output", "Pro Audio"]),
                      card(2, "HDMI Audio Controller", "pci", "", 1, ["Off", "Digital Stereo (HDMI) Output",
                                                                      "Digital Surround 5.1 (HDMI) Output"]),
                      card(3, "USB Headphones", "usb", "headset", 1, ["Off", "Analog Stereo Output + Mono Input",
                                                                      "Analog Stereo Output"])]}
    pw.available = lambda: True
    pw.snapshot = lambda: snap
    eq.uses_filter_chain = lambda: True
    eq.save({**eq.load(), "gains": [4.0, 3.5, 2.0, 0.0, -1.0, -1.0, 0.5, 2.0, 3.5, 3.0], "preamp": -5.0,
             "preset": "", "output": "speakers"})


def _audiol(page, wait):
    page.show_panel("eq")


def seed_shots():
    """ShotL's gallery: the pages rendered so far, as if they were screenshots taken today."""
    import time
    from grimoire.spells.shotl import shots
    folder = shots.folder()
    folder.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(("hub", "mural", "sightc", "vaultl", "optimizel", "systeml", "terminall")):
        src = OUT / f"{name}.png"
        if src.is_file():
            dst = folder / time.strftime(f"Screenshot_%Y-%m-%d_%H-%M-{i:02d}.png")
            shutil.copy(src, dst)
            shots.add(dst)


def save(pixmap, name):
    path = OUT / f"{name}.png"
    pixmap.save(str(path))
    shrink(path)
    print(f"{path.relative_to(REPO)}  {path.stat().st_size // 1024} KB")


def shrink(path: Path, limit=300 * 1024):
    """Grimoire is black & white, so a 64-color palette is visually lossless and keeps PNGs small."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    for colors in (128, 64, 32):
        img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(
            path, optimize=True)
        if path.stat().st_size <= limit:
            break


def tray_shot(wait):
    """The tray's icon (CPU/RAM bars) and its menu, side by side on Grimoire's black."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
    from grimoire import tray
    from grimoire.glyphs import meter
    t = tray.Tray()
    t.timer.stop()
    m = t.menu
    m.adjustSize()
    m.popup(QPoint(0, 0))
    wait(400)
    menu = m.grab()
    m.hide()
    pad, icon = 48, 96
    canvas = QPixmap(menu.width() + icon + pad * 3, max(menu.height(), icon) + pad * 2)
    canvas.fill(QColor("#0b0b0b"))
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.drawPixmap(pad, pad, meter(38, 61, icon))
    p.setPen(QColor("#8a8a8a"))
    p.setFont(QFont("IBM Plex Sans", 10))
    p.drawText(pad, pad + icon + 10, icon, 40, Qt.AlignmentFlag.AlignHCenter, "CPU   RAM")
    p.drawPixmap(pad * 2 + icon, pad, menu)
    p.end()
    save(canvas, "tray")


def _vaultl(page, wait):
    page.navigate(Path.home() / "Downloads")


def _terminal(page, wait):
    """Type a couple of harmless commands into the first terminal."""
    wait(1500)
    from PySide6.QtWidgets import QWidget
    term = next((w for w in page.findChildren(QWidget) if hasattr(w, "session")), None)
    if term is None:
        return
    demo = ("clear; cd ~; ls --color=always; echo; "
            "printf '\\e[1mGrimoire Linux\\e[0m  \\e[2mblack & white, full color when asked\\e[0m\\n'; "
            "for c in 1 2 3 4 5 6; do printf \"\\e[4${c}m   \\e[0m\"; done; printf '\\n'; "
            "for i in $(seq 232 255); do printf \"\\e[48;5;${i}m  \"; done; printf '\\e[0m\\n'\n")
    term.session.write(demo.encode())


def _gamel(page, wait):
    """A made-up Steam and Lutris library (fictional titles, abstract covers), never the real one."""
    import sqlite3
    import time
    now = int(time.time())
    steam = Path.home() / ".local/share/Steam"
    games = [(101, "Ashen Tide", 38, 2900), (102, "Orbital Drift", 1, 12400), (103, "Low Tide Diner", 5, 640),
             (104, "Paper Moons", 12, 75), (105, "Static Bloom", 60, 1800), (106, "Night Ferry", 0, 0),
             (107, "Glass Harbor", 3, 410), (108, "Quiet Signal", 200, 3300)]
    (steam / "steamapps/common").mkdir(parents=True, exist_ok=True)
    played = []
    for i, (appid, name, days, mins) in enumerate(games):
        (steam / f"steamapps/appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n"appid" "{appid}"\n"name" "{name}"\n"StateFlags" "4"\n"installdir" "{name}"\n'
            f'"SizeOnDisk" "{(i * 7 + 3) * 2 ** 30}"\n}}\n')
        (steam / "steamapps/common" / name).mkdir(exist_ok=True)
        art = steam / f"appcache/librarycache/{appid}/library_600x900.jpg"
        art.parent.mkdir(parents=True, exist_ok=True)
        _image(art, i, (600, 900))
        if mins:
            played.append(f'"{appid}" {{ "LastPlayed" "{now - days * 86400}" "Playtime" "{mins}" }}')
    cfg = steam / "userdata/1/config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "localconfig.vdf").write_text('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" { '
                                         + " ".join(played) + " } } } } }")
    lutris = Path.home() / ".local/share/lutris"
    lutris.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(lutris / "pga.db")
    con.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, slug TEXT, runner TEXT, directory TEXT, "
                "lastplayed INTEGER, installed INTEGER, playtime REAL)")
    con.execute("INSERT INTO games VALUES (1, 'Hollow Lanterns', 'hollow-lanterns', 'wine', '', ?, 1, 6.5)",
                (now - 9 * 86400,))
    con.commit()
    con.close()
    from grimoire.spells.gamel import others             # Roblox through a fake Sober; no menu games of this PC
    fake = Path.home() / "fake-flatpak"
    (fake / "app/org.vinegarhq.Sober/current/active").mkdir(parents=True, exist_ok=True)
    others.FLATPAK_SYSTEM = fake
    others.app_dirs = lambda: [Path.home() / ".local/share/applications"]
    page.scan()


PREPARE = {"vaultl": _vaultl, "terminall": _terminal, "gamel": _gamel}


def _updatel(page, wait):
    """A made-up last check (the page only reads its cache when opened) and a changelog, so nothing goes online."""
    import time
    from PySide6.QtCore import Qt
    from grimoire.spells.updatel import daily

    def it(src, name, cur, new, size, **kw):
        key = f"{src}:{kw.get('scope', 'system') + ':' if src == 'flatpak' else ''}{kw.get('ref', name)}"
        return {"key": key, "source": src, "name": name, "title": kw.pop("title", name), "current": cur, "new": new,
                "size": size, "security": kw.pop("security", False), "scope": "system", "notes": "", **kw}
    items = [it("apt", "curl", "8.18.0-1ubuntu2.6", "8.18.0-1ubuntu2.7", 412_000, security=True),
             it("apt", "libcurl4t64", "8.18.0-1ubuntu2.6", "8.18.0-1ubuntu2.7", 389_000, security=True),
             it("apt", "firefox", "1:1snap1-0ubuntu7", "1:1snap1-0ubuntu8", 82_000),
             it("apt", "linux-firmware", "20260915.git3c1d-0ubuntu1", "20261002.gitb7e2-0ubuntu1", 512_000_000),
             it("apt", "mesa-vulkan-drivers", "26.1.4-1ubuntu1", "26.1.5-1ubuntu1", 14_200_000),
             it("flatpak", "org.blender.Blender", "5.2", "5.2.1", 402_000_000, scope="user",
                ref="org.blender.Blender/x86_64/stable"),
             it("flatpak", "org.freedesktop.Platform", "freedesktop-sdk-25.08.16", "freedesktop-sdk-25.08.17",
                260_100_000, ref="org.freedesktop.Platform/x86_64/25.08", title="org.freedesktop.Platform (25.08)"),
             it("fwupd", "UEFI dbx", "371", "377", 24_576, device="0" * 40)]
    daily._write(daily.STATE, {"items": items, "held": [], "missing": ["snap"], "errors": {}, "reboot": None,
                               "t": time.time() - 2 * 3600, "notified": []})
    page._apply_state()
    page.updates.notes["apt:curl=8.18.0-1ubuntu2.7"] = (
        "curl (8.18.0-1ubuntu2.7) resolute-security; urgency=medium\n\n  * SECURITY UPDATE: authentication bypass "
        "in LDAP SASL negotiation.\n    - debian/patches/CVE-2026-13608.patch\n\n -- Ubuntu Security Team  Mon, 12 "
        "Oct 2026 10:00:00 +0000")
    tree = page.updates.tree
    for n in range(tree.topLevelItemCount()):
        row = tree.topLevelItem(n)
        if row.data(0, Qt.ItemDataRole.UserRole + 1) in ("apt:curl", "apt:libcurl4t64"):
            row.setCheckState(0, row.checkState(0).Checked)
        if row.data(0, Qt.ItemDataRole.UserRole + 1) == "apt:curl":
            tree.setCurrentItem(row)


PREPARE["updatel"] = _updatel
PAGES.insert(PAGES.index("settings"), "updatel")
PREPARE["audiol"] = _audiol


def _glyphl(page, wait):
    picker = page.picker
    picker._select_category("emoji:1")
    wait(400)
    picker.grid.setCurrentIndex(picker.model.index(14))


PREPARE["glyphl"] = _glyphl
PAGES.append("glyphl")


def _viewl(page, wait):
    """A folder of abstract sample pictures (one with made-up camera EXIF), opened full size with the info panel."""
    from PIL import Image
    pics = Path.home() / "Pictures" / "Samples"
    pics.mkdir(parents=True, exist_ok=True)
    for i in range(12):
        _image(pics / f"sample-{i + 1:02d}.png", i + 3, (1600, 1000))
    img = Image.open(pics / "sample-03.png").convert("RGB")
    exif = img.getexif()
    exif[0x010F], exif[0x0110] = "Camera", "Model 1"
    exif[0x8769] = {0x829A: 1 / 250, 0x829D: 4.0, 0x8827: 200, 0x9003: "2026:06:14 19:42:00", 0x920A: 35.0}
    img.save(pics / "sample-03.jpg", quality=92, exif=exif)
    (pics / "sample-03.png").unlink()
    page.s["info"] = True
    page.info.setVisible(True)
    page.info_btn.setChecked(True)
    page.open_path(pics / "sample-03.jpg")


PREPARE["viewl"] = _viewl
PAGES.insert(PAGES.index("settings"), "viewl")


def _storel(page, wait):
    """Home with a made-up set of installed apps (the catalog itself is Flathub's and Ubuntu's public metadata)."""
    for _ in range(100):
        if page.loaded:
            break
        wait(200)
    wait(1500)

    def flat(app_id, name, version, size, scope="system"):
        return {"id": app_id, "ref": f"app/{app_id}/x86_64/stable", "scope": scope, "version": version,
                "origin": "flathub", "name": name, "size": size}
    page._installed({"flatpak": [flat("org.mozilla.firefox", "Firefox", "144.0", 270_000_000),
                                 flat("org.kde.krita", "Krita", "5.3.1", 610_000_000, "user"),
                                 flat("com.obsproject.Studio", "OBS Studio", "32.2.2", 528_000_000)],
                     "apt": {}, "snap": [], "desktop": [], "remotes": {"flathub": ["user", "system"]}})


PREPARE["storel"] = _storel
PAGES.append("storel")


def _notel(page, wait):
    """A small made-up notes folder: a project note with a link, a tag and a checklist, open beside its preview."""
    notes = Path.home() / "Documents/Notes"
    (notes / "Projects").mkdir(parents=True, exist_ok=True)
    (notes / "Daily").mkdir(exist_ok=True)
    (notes / "Projects/Garden plan.md").write_text(
        "# Garden plan\n\nSpring beds for the back yard, see [[Seed list]] and [[Daily/2026-10-15|today's notes]]. "
        "#garden #spring\n\n## To do\n\n- [x] Measure the beds\n- [x] Order compost\n- [ ] Build the trellis\n"
        "- [ ] Plant the **tomatoes** after the last frost\n\n> Water early in the morning, never at noon.\n\n"
        "| Bed | Plants | Sun |\n|-----|--------|-----|\n| North | Herbs, lettuce | Half |\n"
        "| South | Tomatoes, beans | Full |\n\n```python\nwatering = {\"tomatoes\": 2, \"herbs\": 1}  # liters a day\n"
        "print(sum(watering.values()))\n```\n")
    (notes / "Seed list.md").write_text("# Seed list\n\n- Tomatoes\n- Beans\n\nFor the [[Garden plan]]. #garden\n")
    (notes / "Daily/2026-10-15.md").write_text("# 2026-10-15\n\nOrdered compost for the [[Garden plan]].\n")
    (notes / "Reading list.md").write_text("# Reading list\n\n1. The Overstory\n2. Braiding Sweetgrass\n#books\n")
    (notes / "Ideas.md").write_text("# Ideas\n\n- A rain barrel by the shed #garden\n")
    page.set_view("split")
    page.toggle_pin(notes / "Projects/Garden plan.md")
    page.scan()
    wait(800)
    page.open_path(notes / "Projects/Garden plan.md")
    wait(1200)
    page.links_btn.setChecked(True)
    item = page.tree.topLevelItem(0)
    if item:
        page.tree.setCurrentItem(item.child(0))


PREPARE["notel"] = _notel
PAGES.append("notel")


def _settingl(page, wait):
    """SettingL reads KWin and kscreen over the session bus, which the sandbox doesn't have: two made-up screens
    and night light on."""
    from grimoire.spells.settingl import displays

    def out(i, name, label, w, h, rates, x, primary):
        modes = [{"id": f"{i}{n}", "w": w, "h": h, "rate": r} for n, r in enumerate(rates)] + \
            [{"id": f"{i}9", "w": 1920, "h": 1080, "rate": 60.0}]
        return {"id": i, "name": name, "label": label, "enabled": True, "priority": 1 if primary else 2,
                "primary": primary, "x": x, "y": 0, "mode": f"{i}0", "modes": modes, "preferred": [f"{i}0"],
                "scale": 1.25 if w > 3000 else 1.0, "rotation": "none", "type": 14, "mm": (597, 336)}
    screens = [out(1, "DP-1", "Studio 27", 3840, 2160, [144.0, 120.0, 60.0], 0, True),
               out(2, "HDMI-A-1", "Office 24", 1920, 1080, [75.0, 60.0], 3072, False)]
    displays.read = lambda: {"outputs": [dict(o) for o in screens], "error": ""}
    displays.night = lambda: {"active": True, "mode": "daynight", "temperature": 3800, "available": True,
                              "running": False, "current": 6500, "daylight": True, "inhibited": False, "live": True}
    wait(1500)
    page.built["displays"].load(force=True)


PREPARE["settingl"] = _settingl
PAGES.insert(PAGES.index("settings"), "settingl")
WAIT = {"widgetl": 5000, "mural": 6000, "systeml": 30000, "netl": 30000, "optimizel": 5000, "terminall": 3500, "vaultl": 3000}


def demo_pc():
    """The home page's About this PC card and Settings → Printers, with made-up hardware and printers."""
    import time
    from grimoire import printers, printersview, sysinfo
    sysinfo._cache = {"machine": "Framework Laptop 13", "cpu": "AMD Ryzen 7 7840U", "threads": 16,
                      "gpus": ["AMD Radeon 780M"], "memory": 32 * 1024 ** 3, "system": "Kubuntu 26.04.1 LTS",
                      "disk": {"model": "WD_BLACK SN850X", "total": 1000 * 1024 ** 3, "free": 640 * 1024 ** 3},
                      "kernel": "7.0.0-38-generic", "plasma": "6.6.6", "session": "Wayland",
                      "boot": time.time() - 2 * 3600 - 17 * 60, "version": sysinfo.__version__,
                      "host": "grimoire", "user": "user"}

    class Dest:
        is_default = False

    class Conn:
        def getPrinters(self):
            return {"Office_Laser": {"printer-info": "Office Laser", "printer-location": "Study",
                                     "printer-make-and-model": "HP LaserJet Pro M404", "printer-state": 4,
                                     "printer-state-reasons": ["toner-low-warning"], "device-uri": "usb://HP/M404"},
                    "Photo_Inkjet": {"printer-info": "Photo Inkjet", "printer-make-and-model": "Epson ET-8550",
                                     "printer-state": 5, "printer-state-reasons": ["paused"],
                                     "device-uri": "implicitclass://Photo_Inkjet/"}}

        def getDests(self):
            return {}

        def getDefault(self):
            return "Office_Laser"

        def getJobs(self, **kw):
            now = int(time.time())
            return {12: {"job-name": "Thesis draft.pdf", "job-printer-uri": "ipp://localhost/printers/Office_Laser",
                         "job-state": 5, "job-k-octets": 1840, "time-at-creation": now - 120},
                    13: {"job-name": "Boarding pass", "job-printer-uri": "ipp://localhost/printers/Office_Laser",
                         "job-state": 3, "job-k-octets": 96, "time-at-creation": now - 30}}
    printers.CONNECT = Conn
    printersview.LAUNCH = lambda *a: (False, 0)


PREPARE["printers"] = lambda page, wait: page.show_section("printers")
PAGES.insert(PAGES.index("settings") + 1, "printers")


def _cloudl(page, wait):
    """Three made-up cloud drives (no rclone config, no mounts, nothing online): two mounted, one uploading."""
    from grimoire.spells.cloudl import rclone
    wait(800)                                        # let the first (empty, sandboxed) reading finish
    names = {"gdrive": "drive", "onedrive": "onedrive", "dropbox": "dropbox"}
    up = {"gdrive", "onedrive"}
    rclone.available = lambda: True
    rclone.remotes = lambda: [{"name": n, "type": t} for n, t in names.items()]
    rclone.mounts = lambda: {str(rclone.mountpoint(n)): f"{n}:" for n in up}
    rclone.service_state = lambda n: {"written": n in up, "enabled": n == "gdrive",
                                      "active": "active" if n in up else "inactive"}
    rclone.vfs_stats = lambda n: ({"uploading": 1, "queued": 2, "errored": 0, "cached": 1_310_000_000} if n == "gdrive"
                                  else {"uploading": 0, "queued": 0, "errored": 0, "cached": 86_000_000})
    rclone.about = lambda n: {"gdrive": {"total": 2 * 2**40, "used": 731 * 2**30, "free": 2 * 2**40 - 731 * 2**30},
                              "onedrive": {"total": 1 * 2**40, "used": 214 * 2**30, "free": 810 * 2**30},
                              "dropbox": {"total": 2 * 2**30 * 1000, "used": 1_640 * 2**30,
                                          "free": 360 * 2**30}}[n]
    page._busy = False
    page._refresh_all()


PAGES.append("cloudl")
PREPARE["cloudl"] = _cloudl


def _readl(page, wait):
    """A made-up little library (a PDF, an EPUB with an abstract cover, Markdown notes) with some reading progress,
    then the PDF open at its second page with the thumbnails showing."""
    import zipfile
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
    from grimoire.spells.readl import library
    docs = Path.home() / "Documents/Reading"
    docs.mkdir(parents=True, exist_ok=True)
    text = ("The keeper wrote every evening about the weather, the ships and the long slow turn of the lamp. "
            "Nothing much happened, and that was the point of it. ") * 4
    doc = QTextDocument()
    doc.setHtml("".join(f"<h1>{n}. {t}</h1>" + f"<p>{text}</p>" * 7 for n, t in enumerate(
        ("Arrival", "Weather", "Ships", "The Lamp", "Winter", "Letters", "Fog", "Departure"), 1)))
    w = QPdfWriter(str(docs / "The Lighthouse Log.pdf"))
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
    w.setPageMargins(QMarginsF(16, 16, 16, 16))
    w.setTitle("The Lighthouse Log")
    doc.print_(w)
    del w
    cover = docs / "cover.png"
    _image(cover, 2, (600, 900))
    with zipfile.ZipFile(docs / "The Salt Road.epub", "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="c.opf"/></rootfiles></container>')
        z.writestr("c.opf", '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://'
                   'purl.org/dc/elements/1.1/"><dc:title>The Salt Road</dc:title><dc:creator>A. Wanderer'
                   '</dc:creator></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"'
                   '/><item id="i" href="cover.png" media-type="image/png" properties="cover-image"/></manifest>'
                   '<spine><itemref idref="a"/></spine></package>')
        z.writestr("a.xhtml", f"<html><body><h1>The Flats</h1><p>{text}</p></body></html>")
        z.write(cover, "cover.png")
    cover.unlink()
    (docs / "Field notes.md").write_text("# Field notes\n\n" + text + "\n")
    for name, progress, hours in (("Field notes.md", 0.4, 30), ("The Salt Road.epub", 0.62, 6),
                                  ("The Lighthouse Log.pdf", 0.18, 1)):
        import time
        library.update(docs / name, opened=time.time() - hours * 3600, progress=progress)
    page.open_file(str(docs / "The Lighthouse Log.pdf"))
    wait(1500)
    page.reader.side.show_tab("pages")
    page.reader.set_layout("two")
    page.reader.set_fit("page")
    page.reader.view.go(2)


PREPARE["readl"] = _readl
PAGES.append("readl")
WAIT["readl"] = 3000


def demo_phone():
    """PhoneL talks to KDE Connect's daemon: start the made-up one (scripts/fake_kdeconnect.py) on a private bus."""
    import atexit
    sys.path.insert(0, str(REPO / "scripts"))
    from fake_kdeconnect import FakeKdeConnect
    from grimoire.spells.phonel import kdc
    fake = FakeKdeConnect(BOX / "kdeconnect")
    fake.start()
    atexit.register(fake.stop)
    kdc.ADDRESS = fake.address


PAGES.append("phonel")


def _vaultl_archive(page, wait):
    """VaultL browsing inside a made-up zip (abstract images and a note), a text file previewed."""
    import zipfile
    work = Path.home() / ".cache/archive-src"              # inside the sandbox home
    work.mkdir(parents=True, exist_ok=True)
    zpath = Path.home() / "Downloads/design-kit.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for i, name in enumerate(("cover.png", "dunes.png", "moon.png", "rain.png")):
            _image(work / name, i)
            z.write(work / name, f"design-kit/images/{name}")
        z.writestr("design-kit/README.md", "# Design kit\n\nBlack & white wallpapers and a palette.\n\n"
                                          "- images/: four 960x540 PNGs\n- palette.txt: the greys\n")
        z.writestr("design-kit/palette.txt", "#000000\n#0b0b0b\n#1a1a1a\n#8c8c8c\n#f2f2f2\n#ffffff\n")
        z.writestr("design-kit/fonts/LICENSE.txt", "SIL Open Font License 1.1\n")
    page.navigate(zpath.parent)
    page.open_archive(zpath)
    wait(1200)
    panel = page.archive_panel
    panel.go("design-kit")
    wait(200)
    view, model = panel.view, panel.model
    for r in range(model.rowCount()):
        if model.rows[r].name.endswith("README.md"):
            view.selectionModel().select(model.index(r, 0), view.selectionModel().SelectionFlag.ClearAndSelect
                                         | view.selectionModel().SelectionFlag.Rows)


PAGES.append("vaultl-archive")
PAGE_OF = {"vaultl-archive": "vaultl"}
PREPARE["vaultl-archive"] = _vaultl_archive
# PlayL: a few songs made here with ffmpeg (sine tones, B&W art from _image), the second one paused mid-way
PLAYL_SONGS = [("Ashen Tide", "Glass Harbor", "Night Ferry", 1, 0), ("Paper Moons", "Glass Harbor", "Night Ferry", 2, 0),
               ("Low Tide Diner", "Glass Harbor", "Night Ferry", 3, 0), ("Quiet Signal", "Orbital Drift", "Static Bloom", 1, 2),
               ("Hollow Lanterns", "Orbital Drift", "Static Bloom", 2, 2)]
if os.environ.get("GRIMOIRE_SCREENSHOTS") == "1":
    os.environ["PLAYL_AO"] = "null"                       # silent: mpv decodes but plays nowhere


def _playl(page, wait):
    if not page.player or not shutil.which("ffmpeg"):
        return
    music = Path.home() / "Music"
    paths = []
    for k, (title, artist, album, track, art) in enumerate(PLAYL_SONGS):
        folder = music / artist / album
        folder.mkdir(parents=True, exist_ok=True)
        cover = folder / "cover.png"
        if not cover.exists():
            _image(cover, art, (600, 600))
        out = folder / f"{track:02d} {title}.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={220 + 40 * k}",
                        "-t", str(150 + 20 * k), "-metadata", f"title={title}", "-metadata", f"artist={artist}",
                        "-metadata", f"album={album}", "-metadata", f"track={track}", str(out)], check=True)
        paths.append(str(out))
    from grimoire.spells.playl import library, media
    tracks = library.scan(media.library_roots())
    page.player.titles = {t["path"]: t for t in tracks}
    page.play_entries(paths, 1)
    wait(2500)
    page.player.seek(64)
    page.player.pause()
    wait(1200)
    page.queue.refresh()
    page.stage.activity()


PREPARE["playl"] = _playl
PAGES.insert(PAGES.index("settings"), "playl")
WAIT["playl"] = 1500
# ---------------------------------------------------------------- SystemL Logs/Drives, NetL Bluetooth (made-up data)
PAGE_OF = {}


def _systeml_logs(page, wait):
    """A made-up journal: the sandbox has none of its own and the real one is personal."""
    import json
    import time
    from grimoire.spells.systeml import journal
    now = time.time() - 600
    lines = [(0, 6, "systemd", "1", "init.scope", "Started session-2.scope - Session 2 of User user."),
             (2, 6, "NetworkManager", "812", "NetworkManager.service", "device (wlan0): state change: activated"),
             (5, 5, "kernel", "", "", "usb 3-2: new high-speed USB device number 7 using xhci_hcd"),
             (5, 6, "kernel", "", "", "usb-storage 3-2:1.0: USB Mass Storage device detected"),
             (6, 6, "udisksd", "1043", "udisks2.service", "Mounted /dev/sdb1 at /media/user/STICK on behalf of "
                                                           "uid 1000"),
             (40, 4, "pipewire", "1510", "pipewire.service", "spa.alsa: hw:1: snd_pcm_avail after recover: Broken "
                                                             "pipe"),
             (75, 6, "plasmashell", "1622", "plasma-plasmashell.service", "Notification server ready"),
             (120, 3, "bluetoothd", "905", "bluetooth.service", "src/service.c:btd_service_connect() a2dp-sink "
                                                                "profile connect failed for 02:00:00:00:00:10: "
                                                                "Device or resource busy"),
             (121, 6, "bluetoothd", "905", "bluetooth.service", "Endpoint registered: sender=:1.84 "
                                                                "path=/MediaEndpoint/A2DPSink/sbc"),
             (180, 7, "kwin_wayland", "1488", "plasma-kwin_wayland.service", "Output DP-1: mode 2560x1440@165"),
             (240, 4, "firefox", "4410", "app-firefox.scope", "Sandbox: seccomp sandbox violation: pid 4410, "
                                                             "syscall 41"),
             (300, 6, "systemd", "1", "init.scope", "Starting fwupd-refresh.service - Refresh fwupd metadata..."),
             (302, 6, "fwupd", "2290", "fwupd.service", "Daemon ready for requests"),
             (360, 2, "kernel", "", "", "nvme nvme0: I/O 412 QID 7 timeout, completion polled"),
             (420, 6, "grimoire-netl", "5120", "grimoire-netl-usage.service", "usage recorded"),
             (480, 6, "systemd", "1", "init.scope", "Finished fwupd-refresh.service - Refresh fwupd metadata.")]
    entries = []
    for dt, prio, ident, pid, unit, msg in lines:
        raw = {"__REALTIME_TIMESTAMP": str(int((now + dt) * 1e6)), "PRIORITY": str(prio), "SYSLOG_IDENTIFIER": ident,
               "_PID": pid, "_SYSTEMD_UNIT": unit, "MESSAGE": msg, "_HOSTNAME": "grimoire", "_BOOT_ID": "0" * 32,
               "_TRANSPORT": "kernel" if ident == "kernel" else "journal"}
        entries.append(journal.parse(json.dumps({k: v for k, v in raw.items() if v})))

    class Reader:
        def __init__(self, cmd):
            self.done, self.error, self._left = True, "", list(entries)

        def start(self):
            return self

        def take(self):
            out, self._left = self._left, []
            return out

        def stop(self):
            pass
    journal.Reader = Reader
    journal.boots = lambda scope="user": [{"id": "0" * 32, "index": 0, "first": now - 3600, "last": now}]
    journal.sources = lambda scope="user": sorted({e["unit"] for e in entries if e["unit"]})
    panel = page.panels["logs"]
    panel.system_ok = True
    panel.segs[1][0].setEnabled(True)
    page.show_panel("logs")
    panel.set_scope("system")
    wait(600)
    panel.view.setCurrentIndex(panel.model.index(7, 0))


def _systeml_drives(page, wait):
    from grimoire.spells.systeml import drives

    def part(n, label, fs, size, mounts=(), used=None, total=None, system=False, offset=0):
        return {"object": f"/fake/{label}{n}", "device": f"/dev/fake{n}", "number": n, "offset": offset,
                "size": size, "label": label, "fs": fs, "usage": "filesystem", "system": system, "can_mount": True,
                "mounts": list(mounts), "encrypted": False, "unlocked": False, "swap": False, "used": used,
                "total": total, "container": False, "type": ""}
    tb = 1000 ** 4
    nvme = {"object": "/fake/nvme", "model": "Example NVMe 1TB", "serial": "0000", "revision": "1.0", "size": tb,
            "kind": "nvme", "removable": False, "can_power_off": False, "ejectable": False, "media": True,
            "health": {"source": "nvme", "failing": False, "temp": 41.0, "hours": 1840, "selftest": "success"},
            "device": "/dev/nvme0n1", "table": "gpt", "sort": "0", "system": True,
            "parts": [part(1, "EFI", "vfat", 315 * 10 ** 6, ["/boot/efi"], 8 * 10 ** 6, 313 * 10 ** 6, True),
                      part(2, "kubuntu", "ext4", tb - 316 * 10 ** 6, ["/"], 412 * 10 ** 9, 983 * 10 ** 9, True)]}
    hdd = {"object": "/fake/hdd", "model": "Example HDD 4TB", "serial": "0001", "revision": "1.0", "size": 4 * tb,
           "kind": "hdd", "removable": False, "can_power_off": False, "ejectable": False, "media": True,
           "health": {"source": "ata", "failing": False, "temp": 34.0, "hours": 12020}, "device": "/dev/sda",
           "table": "gpt", "sort": "1", "system": False,
           "parts": [part(1, "Games", "ext4", 3 * tb, ["/mnt/games"], 1900 * 10 ** 9, 2950 * 10 ** 9),
                     part(2, "Archive", "ntfs", tb, [])]}
    usb = {"object": "/fake/usb", "model": "Generic Flash Disk", "serial": "0002", "revision": "8.07",
           "size": 32 * 10 ** 9, "kind": "usb", "removable": True, "can_power_off": True, "ejectable": True,
           "media": True, "health": {"source": "", "failing": None, "temp": None, "hours": None},
           "device": "/dev/sdb", "table": "dos", "sort": "2", "system": False,
           "parts": [part(1, "STICK", "vfat", 32 * 10 ** 9, ["/media/user/STICK"], 9 * 10 ** 9, 32 * 10 ** 9)]}
    drives.snapshot = lambda: {"udisks": True, "drives": [nvme, hdd, usb]}
    page.show_panel("drives")


def _netl_bluetooth(page, wait):
    from grimoire.spells.netl import bluez

    class Client:
        def __init__(self, **kw):
            pass

        def start(self):
            return self

        def snapshot(self):
            def dev(n, name, icon, paired, connected, battery=None, rssi=None):
                return {"path": f"/fake/dev{n}", "adapter": "/fake/hci0", "address": f"02:00:00:00:00:{n:02x}",
                        "name": name, "named": True, "icon": icon, "paired": paired, "bonded": paired,
                        "trusted": paired, "connected": connected, "blocked": False, "rssi": rssi,
                        "battery": battery}
            return {"running": True, "agent": True, "error": "",
                    "adapters": [{"path": "/fake/hci0", "name": "grimoire", "address": "02:00:00:00:00:01",
                                  "powered": True, "blocked": False, "discoverable": False, "discovering": True,
                                  "timeout": 180}],
                    "devices": [dev(16, "Studio Headphones", "audio-headset", True, True, 80),
                                dev(17, "Desk Keyboard", "input-keyboard", True, True, 64),
                                dev(18, "Game Controller", "input-gaming", True, False, 35),
                                dev(32, "Bookshelf Speaker", "audio-card", False, False, rssi=-58),
                                dev(33, "Phone", "phone", False, False, rssi=-79)]}

        def scan(self, adapter, on):
            pass

        def stop(self):
            pass
    bluez.missing = lambda: ""
    bluez.Client = Client
    page.show_panel("bluetooth")
    wait(800)
    panel = page.panels["bluetooth"]
    panel._scan_timer.start()
    panel.scan_btn.setText(panel.scan_btn.text())
    panel.load()


for _name, _page, _prep in (("systeml-logs", "systeml", _systeml_logs), ("systeml-drives", "systeml", _systeml_drives),
                            ("netl-bluetooth", "netl", _netl_bluetooth)):
    PAGES.append(_name)
    PAGE_OF[_name] = _page
    PREPARE[_name] = _prep
    WAIT[_name] = 3000


def main():
    names = [a for a in sys.argv[1:] if a in PAGES] or PAGES
    if os.environ.get("GRIMOIRE_SCREENSHOTS") == "1":
        render(names)
        return
    home = sandbox()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("XDG_", "DBUS_", "KDE_", "WAYLAND", "DISPLAY"))}
    env |= {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_CACHE_HOME": str(home / ".cache"), "XDG_RUNTIME_DIR": str(BOX / "run"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent", "QT_QPA_PLATFORM": "offscreen",
            "SHELL": "/bin/bash", "USER": "user", "LOGNAME": "user", "HOSTNAME": "grimoire",
            "GRIMOIRE_NO_UPDATE_CHECK": "1", "GRIMOIRE_SCREENSHOTS": "1", "PYTHONPATH": str(REPO),
            "PYTHONSAFEPATH": "1"}
    try:
        subprocess.run([sys.executable, __file__, *names], env=env, cwd=home, check=True, timeout=600)
    finally:
        shutil.rmtree(BOX, ignore_errors=True)


if __name__ == "__main__":
    main()
