# SPDX-License-Identifier: GPL-3.0-or-later
"""WidgetL from the command line (grimoire-widgetl <command> does the same).

    python3 -m grimoire.spells.widgetl status
    python3 -m grimoire.spells.widgetl list                 the widgets, installed or not, and how many are out
    python3 -m grimoire.spells.widgetl install              install or upgrade the widget packages
    python3 -m grimoire.spells.widgetl add ID [--dry-run]   put one on the desktop (clock, system, weather, nowplaying);
                                                            --dry-run prints the desktop script instead
    python3 -m grimoire.spells.widgetl remove [--dry-run]   take every WidgetL widget off the desktops and panels
    python3 -m grimoire.spells.widgetl uninstall [--dry-run]
                                                            remove them from desktops and panels, then the packages
                                                            (exit 3: packages kept, because Plasma couldn't be asked)
"""
import json
import sys

from grimoire.spells.widgetl import widgets


def _uninstall(dry: bool) -> int:
    if not any(widgets.installed_dir(w.id).exists() for w in widgets.WIDGETS):
        print("WidgetL's widgets aren't installed")
        return 0
    try:
        result = widgets.remove_all(dry_run=dry)
    except RuntimeError as err:
        # never pull a package out from under a desktop that shows it: Plasma would leave an error box there
        if widgets.mentioned_in_config():
            print(f"WidgetL kept: Plasma isn't answering ({err}) and your desktop layout still has its widgets. "
                  "Remove them from the desktop (or start Plasma), then uninstall again.", file=sys.stderr)
            return 3
        result = {"found": [], "removed": 0, "script": ""}
    if dry:
        for f in result["found"]:
            print(f"[dry] would remove {f['type']} (widget {f['widget']}) from {f['kind']} {f['containment']}")
        if result["found"]:
            print("[dry] evaluateScript:\n" + result["script"], end="")
        for w in widgets.WIDGETS:
            if widgets.installed_dir(w.id).exists():
                print(f"[dry] would remove the package {widgets.installed_dir(w.id)}")
        return 0
    if result["removed"]:
        print(f"Took {result['removed']} widget(s) off your desktop and panels")
    gone = widgets.uninstall_packages()
    print("WidgetL removed" if gone else "WidgetL's widgets weren't installed")
    return 0


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    cmd = args[0] if args else "status"
    try:
        if cmd == "status":
            print(widgets.status())
        elif cmd == "list":
            try:
                counts = widgets.counts(widgets.scan())
            except (RuntimeError, ValueError):
                counts = None
            for w in widgets.WIDGETS:
                state = ("installed" + (", update ready" if widgets.needs_update(w.id) else "")
                         if widgets.is_installed(w.id) else "not installed")
                out = "?" if counts is None else counts[w.id]
                print(f"{w.id:<11} {w.name:<12} {state:<26} on desktop/panels: {out}")
        elif cmd == "install":
            done = widgets.install()
            print("Installed or updated: " + ", ".join(done) if done else "Everything was already up to date")
        elif cmd == "add":
            if len(args) < 2:
                print(__doc__)
                return 2
            result = widgets.add(args[1], dry_run=dry)
            print(result["script"] if dry else json.dumps(result))
        elif cmd == "remove":
            result = widgets.remove_all(dry_run=dry)
            if dry:
                print(json.dumps(result["found"], indent=1))
                print(result["script"], end="")
            else:
                print(f"Took {result['removed']} widget(s) off your desktop and panels")
        elif cmd == "uninstall":
            return _uninstall(dry)
        else:
            print(__doc__)
            return 2
    except RuntimeError as err:
        print(f"WidgetL: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
