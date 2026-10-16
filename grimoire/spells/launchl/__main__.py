# SPDX-License-Identifier: GPL-3.0-or-later
"""LaunchL from the command line.

    python3 -m grimoire.spells.launchl status
    python3 -m grimoire.spells.launchl install            install or upgrade the widget package
    python3 -m grimoire.spells.launchl replace [--dry-run] put LaunchL where Kickoff is (prints the script with --dry-run)
    python3 -m grimoire.spells.launchl restore [--dry-run] put the recorded Kickoff back and take LaunchL out
    python3 -m grimoire.spells.launchl uninstall          restore Kickoff if LaunchL replaced it, then remove the package
                                                          (exit 3: kept, because LaunchL is still in a panel)
    python3 -m grimoire.spells.launchl edit ID             the Edit dialog for an app (ID: org.kde.dolphin.desktop)
    python3 -m grimoire.spells.launchl hide|unhide ID      leave an app out of the menus, or show it again
    python3 -m grimoire.spells.launchl reset ID            undo every change to an app (your copy goes to the Trash)
    python3 -m grimoire.spells.launchl edited              the apps you changed
"""
import json
import sys

from grimoire.spells.launchl import panel

APP_COMMANDS = ("edit", "hide", "unhide", "reset")


def apps(cmd: str, app_id: str) -> int:
    """Edit/hide/reset an app's menu entry (appedit.py; no Qt except the dialog)."""
    from grimoire.spells.launchl import appedit
    if not appedit.valid_id(app_id):
        print(f"LaunchL: {app_id!r} isn't a desktop file id (like org.kde.dolphin.desktop)", file=sys.stderr)
        return 2
    if cmd == "edit":
        from grimoire.spells.launchl import editor
        return editor.run(app_id)
    try:
        if cmd == "reset":
            print(f"Moved {appedit.reset(app_id)} to the Trash")
        else:
            path = appedit.hide(app_id, cmd == "hide")
            print(f"{app_id} {'hidden from' if cmd == 'hide' else 'back in'} the menu ({path})")
    except (LookupError, ValueError, OSError) as err:
        print(f"LaunchL: {err}", file=sys.stderr)
        return 1
    appedit.rebuild()
    return 0


def main(argv: list[str]) -> int:
    cmd, dry = (argv[0] if argv else "status"), "--dry-run" in argv
    if cmd in APP_COMMANDS:
        if len(argv) != 2:
            print(__doc__)
            return 2
        return apps(cmd, argv[1])
    if cmd == "edited":
        from grimoire.spells.launchl import appedit
        for app in appedit.edited():
            print(f"{app.id}\t{'hidden' if app.hidden else 'edited'}\t{app.name}")
        return 0
    try:
        if cmd == "status":
            print(panel.status())
        elif cmd == "install":
            panel.install()
            print("LaunchL installed")
        elif cmd == "replace":
            record = panel.replace(dry_run=dry)
            if dry:
                print(json.dumps({k: v for k, v in record.items() if k != "script"}, indent=1))
                print(record["script"])
            else:
                print("LaunchL is in your panel" + (f". {record['check']}" if record.get("check") else ""))
        elif cmd == "restore":
            record = panel.restore(dry_run=dry)
            print(record["script"] if dry else f"{record['type']} is back in your panel")
        elif cmd == "uninstall":
            # never pull the package out from under a panel: that leaves a broken placeholder in it
            if panel.can_restore():
                try:
                    panel.restore()
                    print("Your old launcher is back in the panel")
                except RuntimeError as err:
                    print(f"LaunchL kept: couldn't put your old launcher back ({err}). Run "
                          "`python3 -m grimoire.spells.launchl restore` once Plasma is running.", file=sys.stderr)
                    return 3
            elif panel.in_panel():
                print("LaunchL kept: it's in a panel and Grimoire has no record of what it replaced. Remove it in "
                      "Edit Mode (and add Kickoff back), then uninstall again.", file=sys.stderr)
                return 3
            panel.uninstall_package()
            panel.cleanup_icons()
            print("LaunchL removed")
        else:
            print(__doc__)
            return 2
    except RuntimeError as err:
        print(f"LaunchL: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
