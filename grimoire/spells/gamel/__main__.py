# SPDX-License-Identifier: GPL-3.0-or-later
"""GameL from a terminal:

    grimoire-gamel                 the window
    grimoire-gamel list            every installed game: launcher, id, name
    grimoire-gamel play <launcher:id>   start one (the same as its Play button)
    grimoire-gamel status          the home page's status line
"""
import sys

from grimoire.spells.gamel import launch, library


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
