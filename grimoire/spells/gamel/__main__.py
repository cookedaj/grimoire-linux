# SPDX-License-Identifier: GPL-3.0-or-later
"""GameL from a terminal:

    grimoire-gamel                 the window
    grimoire-gamel list            every installed game: launcher, id, name
    grimoire-gamel play <launcher:id>   start one (the same as its Play button)
    grimoire-gamel status          the home page's status line
"""
import sys

from grimoire.spells.gamel import launch, library


_app = None


def _english():
    """The status line comes from tr(), which spells out "%n game(s)" only with a QCoreApplication holding our
    catalogs; the CLI gets the English ones (its output isn't translated)."""
    global _app
    try:
        from PySide6.QtCore import QCoreApplication, QTranslator
    except ImportError:
        return
    from grimoire import i18n
    _app = QCoreApplication.instance() or QCoreApplication(["grimoire-gamel"])
    for qm in i18n.catalogs("en"):
        t = QTranslator(_app)
        if t.load(str(qm)):
            _app.installTranslator(t)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "list":
        games, problems = library.scan()
        for g in library.sort_games(games, "name"):
            print(f"{g.key}\t{g.name}")
        for p in problems:
            print(p, file=sys.stderr)
        return 0
    if cmd == "status":
        _english()
        print(library.status_line())
        return 0
    if cmd == "play" and len(argv) == 2:
        games, _ = library.scan()
        hit = next((g for g in games if g.key == argv[1]), None)
        if not hit:
            print("No installed game {key}. See: grimoire-gamel list".format(key=argv[1]), file=sys.stderr)
            return 1
        launch.play(hit)
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
