#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Installs and removals for Grimoire StoreL. Run through pkexec, one password prompt per batch:
#   root-helper.sh STEP [ARGS] [+ STEP [ARGS]]...
# Steps:
#   apt-install [--removals=PKG,...] PKG...   install packages (with apt's usual recommends)
#   apt-remove --removals=PKG,... PKG...      remove packages (no purge, no autoremove: settings and data stay)
#   flatpak-install REMOTE REF...             install apps into the system Flatpak installation (app/ID/ARCH/BRANCH)
#   flatpak-remove REF...                     uninstall system Flatpak apps (their data in your home stays)
#   snap-install [--classic] NAME             install a snap
#   snap-remove NAME                          remove a snap (snapd, bases and core runtimes are refused)
# Every step's arguments are checked before any step runs. Each APT step is simulated (apt-get -s) right before it
# runs: if it would remove anything Essential, of Priority required/important or on the protected list below (the
# desktop, its fonts, the packages that boot and run the system) the step is refused (exit 3); every other package
# it would remove must be on --removals, the exact list confirmed in StoreL's preview, else it's refused before
# anything changes (exit 6; exit 4 when no --removals was given). An install without --removals runs with
# --no-remove, so it can't remove anything. Each step starts with a line "@@step N" so StoreL can follow the batch.
# Testing: STOREL_DRY=1 checks and simulates as usual but only prints the commands that would change something
# (pkexec clears the environment, so this can't be passed through it).
set -euo pipefail
# if StoreL closes mid-run its end of our output pipe goes away: the commands below write into relay(), which then
# drains into /dev/null, so apt-get and dpkg never get SIGPIPE halfway through unpacking packages
trap '' PIPE

export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8
APT_OPTS=(-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold -o DPkg::Lock::Timeout=300
          -o APT::Status-Fd=1 -o Dpkg::Use-Pty=0)
# a name never ends in "-": "apt-get install foo-" means REMOVE foo (a removal that would install anything is refused)
PKG_RE='^[a-z0-9]([a-z0-9+.-]{0,98}[a-z0-9+.])?(:[a-z0-9]([a-z0-9-]{0,18}[a-z0-9])?)?$'
REF_RE='^app/[A-Za-z][A-Za-z0-9_.-]{0,254}/[A-Za-z0-9_]{1,20}/[A-Za-z0-9_.-]{1,100}$'
REMOTE_RE='^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'
SNAP_RE='^[a-z0-9][a-z0-9-]{0,39}$'
# kept in step with grimoire/spells/storel/sources.py (PROTECTED, PROTECTED_SNAPS); this copy can't read that file
PROTECTED_RE='^(kubuntu-.*|fonts-ibm-plex.*|plasma-desktop|plasma-workspace.*|kwin-.*|sddm.*|systemd.*|libsystemd.*|udev|apt|apt-utils|dpkg|sudo|sudo-rs|polkitd|pkexec|policykit-1|network-manager|linux-.*|grub-.*|grub2-.*|shim-.*|ubuntu-minimal|ubuntu-standard|init|base-files|bash|coreutils|login|dbus.*|python3|python3-minimal|python3-pyside6.*|pipewire.*|wireplumber|xdg-desktop-portal.*|flatpak|snapd|plymouth.*|grimoire-linux)$'
PROTECTED_SNAPS_RE='^(snapd|core[0-9]*|bare|gtk-common-themes|gnome-[0-9-]+.*|kf[0-9]+-.*|mesa-.*)$'

relay() { cat || cat >/dev/null; }
run() { if [[ -n "${STOREL_DRY:-}" ]]; then echo "would run: $*"; else "$@" 2>&1 | relay; fi; }
die() { echo "$2" >&2; exit "$1"; }

check_removals() {          # --removals=a,b,c
    local list=${1#--removals=} names p
    IFS=, read -r -a names <<<"$list"
    (( ${#names[@]} >= 1 && ${#names[@]} <= 2000 )) && [[ "$list" != *,,* && "$list" != *, && "$list" != ,* ]] \
        || die 2 "--removals takes 1 to 2000 package names joined by commas"
    for p in "${names[@]}"; do [[ "$p" =~ $PKG_RE ]] || die 2 "not a package name: $p"; done
}

# check ONE step's arguments (no side effects)
check_step() {
    local step=$1; shift
    case "$step" in
        apt-install|apt-remove)
            if [[ "${1:-}" == --removals=* ]]; then check_removals "$1"; shift
            elif [[ "$step" == apt-remove ]]; then die 2 "apt-remove needs --removals"; fi
            (( $# >= 1 && $# <= 200 )) || die 2 "$step: give 1 to 200 packages"
            for p in "$@"; do [[ "$p" =~ $PKG_RE ]] || die 2 "not a package name: $p"; done ;;
        flatpak-install)
            (( $# >= 2 && $# <= 51 )) || die 2 "flatpak-install: give a remote and 1 to 50 refs"
            [[ "$1" =~ $REMOTE_RE ]] || die 2 "not a remote name: $1"; shift
            for r in "$@"; do [[ "$r" =~ $REF_RE ]] || die 2 "not an app ref: $r"; done ;;
        flatpak-remove)
            (( $# >= 1 && $# <= 50 )) || die 2 "flatpak-remove: give 1 to 50 refs"
            for r in "$@"; do [[ "$r" =~ $REF_RE ]] || die 2 "not an app ref: $r"; done ;;
        snap-install)
            [[ "${1:-}" == --classic ]] && shift
            (( $# == 1 )) || die 2 "snap-install: give one snap"
            [[ "$1" =~ $SNAP_RE ]] || die 2 "not a snap name: $1" ;;
        snap-remove)
            (( $# == 1 )) || die 2 "snap-remove: give one snap"
            [[ "$1" =~ $SNAP_RE ]] || die 2 "not a snap name: $1"
            [[ "$1" =~ $PROTECTED_SNAPS_RE ]] && die 3 "refused: $1 is part of the system" ;;
        *) die 2 "unknown step: $step" ;;
    esac
    return 0
}

# may this package go? (protected list, Essential, Priority required/important)
keep_reason() {
    local p=$1 base=${1%%:*} fields
    [[ "$base" =~ $PROTECTED_RE ]] && { echo "protected"; return; }
    fields=$(dpkg-query -W -f='${Essential} ${Priority}' -- "$p" 2>/dev/null || true)
    case "$fields" in
        yes\ *) echo "essential" ;;
        *\ required|*\ important) echo "required" ;;
    esac
}

apt_step() {
    local action=$1 allow=0 sim removals r why blocked=() extra=() names
    local -A ok=()
    shift
    if [[ "${1:-}" == --removals=* ]]; then
        allow=1
        IFS=, read -r -a names <<<"${1#--removals=}"
        for r in "${names[@]}"; do ok[$r]=1; done
        shift
    fi
    local cmd=(-y "$action" -- "$@")
    echo "== Simulating (apt-get -s $action $*)"
    sim=$(apt-get -s "${cmd[@]}") || die 5 "apt-get couldn't plan this"
    removals=$(awk '/^Remv / {print $2}' <<<"$sim")
    if [[ "$action" == remove ]] && grep -q '^Inst ' <<<"$sim"; then
        die 3 "refused: this removal would install packages"
    fi
    for r in $removals; do
        why=$(keep_reason "$r")
        [[ -z "$why" ]] || blocked+=("$r ($why)")
    done
    (( ${#blocked[@]} == 0 )) || die 3 "refused: this would remove ${blocked[*]}"
    if [[ -n "$removals" && $allow == 0 ]]; then
        die 4 "refused: this would remove ${removals//$'\n'/ }; confirm the removals in StoreL first"
    fi
    for r in $removals; do [[ -n "${ok[$r]:-}" || -n "${ok[${r%%:*}]:-}" ]] || extra+=("$r"); done
    (( ${#extra[@]} == 0 )) || die 6 "refused: the plan changed since the preview; it would also remove ${extra[*]}"
    if [[ "$action" == install ]]; then
        echo "== Installing $*"
        if [[ -n "$removals" ]]; then run apt-get "${APT_OPTS[@]}" "${cmd[@]}"
        else run apt-get "${APT_OPTS[@]}" --no-remove "${cmd[@]}"; fi
    else
        echo "== Removing $*"
        run apt-get "${APT_OPTS[@]}" "${cmd[@]}"
    fi
}

do_step() {
    local step=$1; shift
    case "$step" in
        apt-install) apt_step install "$@" ;;
        apt-remove) apt_step remove "$@" ;;
        flatpak-install)
            local remote=$1; shift
            echo "== Installing $* (system Flatpak)"
            run flatpak install --system -y --noninteractive -- "$remote" "$@" ;;
        flatpak-remove)
            echo "== Uninstalling $* (system Flatpak)"
            run flatpak uninstall --system -y --noninteractive -- "$@" ;;
        snap-install)
            echo "== Installing snap ${*: -1}"
            if [[ "$1" == --classic ]]; then run snap install --classic -- "$2"; else run snap install -- "$1"; fi ;;
        snap-remove)
            echo "== Removing snap $1"
            run snap remove -- "$1" ;;
    esac
}

(( $# >= 1 )) || die 2 "usage: root-helper.sh apt-install|apt-remove|flatpak-install|flatpak-remove|snap-install|snap-remove ARGS [+ STEP ARGS]..."

# split the arguments into steps at each "+" and check them all before running any
steps=()            # each entry: the step's words joined by an ASCII unit separator
cur=()
for a in "$@"; do
    if [[ "$a" == + ]]; then
        (( ${#cur[@]} )) || die 2 "empty step"
        steps+=("$(IFS=$'\x1f'; echo "${cur[*]}")"); cur=()
    else
        [[ "$a" != *$'\x1f'* && "$a" != *$'\n'* ]] || die 2 "bad argument"
        cur+=("$a")
    fi
done
(( ${#cur[@]} )) || die 2 "empty step"
steps+=("$(IFS=$'\x1f'; echo "${cur[*]}")")
(( ${#steps[@]} <= 16 )) || die 2 "too many steps"

for s in "${steps[@]}"; do IFS=$'\x1f' read -r -a words <<<"$s"; check_step "${words[@]}"; done
n=0
for s in "${steps[@]}"; do
    n=$((n + 1))
    echo "@@step $n"
    IFS=$'\x1f' read -r -a words <<<"$s"
    do_step "${words[@]}"
done
echo "== Done"
