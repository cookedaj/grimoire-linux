# SPDX-License-Identifier: GPL-3.0-or-later
"""GlyphL from a hotkey or a terminal.

    grimoire-glyphl [toggle]     show the picker, or hide it when it's in front (bind this to a key)
    grimoire-glyphl show|hide    just that
    grimoire-glyphl quit         stop the background popup
    grimoire-glyphl window       GlyphL's page in its own window

Bind it in Grimoire's Settings → Hotkeys ("Open GlyphL"), or in System Settings → Keyboard → Shortcuts →
Add Command.
"""
import sys


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "toggle"
    if cmd in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    if cmd == "window":
        from grimoire.standalone import run
        run("glyphl")
        return 0
    from grimoire.spells.glyphl import popup
    if cmd not in popup.COMMANDS or len(argv) > 1:
        print(__doc__.strip())
        return 2
    return popup.run(cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
