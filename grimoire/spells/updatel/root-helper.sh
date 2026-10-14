#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# System updates for Grimoire UpdateL. Run through pkexec, one password prompt per batch:
#   root-helper.sh STEP [ARGS] [+ STEP [ARGS]]...
# Steps:
#   refresh                                    apt-get update (the package lists)
#   apt [--removals=PKG,PKG...] --all | PKG... upgrade everything (with new dependencies) or just these packages
#   flatpak --all | REF...                     update the system Flatpak installation (app/arch/branch refs)
#   snap --all | NAME...                       refresh snaps
#   fwupd DEVICE-ID...                         install the newest firmware for these fwupd devices (40 hex digits)
# Every step is checked before any runs. An APT upgrade is simulated (apt-get -s) first: if it would remove
# kubuntu-desktop or the IBM Plex fonts it's refused, and every other package it would remove must be in --removals
# (the exact list you confirmed in the app's preview): one more (say the lists were refreshed since) refuses the whole
# batch before anything changes (exit 6). Without --removals apt-get runs with --no-remove, so it can't remove anything.
# Testing: UPDATEL_DRY=1 checks and simulates as usual but only prints the commands that would change something
# (pkexec clears the environment, so this can't be passed through it).
set -euo pipefail
# if UpdateL closes mid-run its end of our output pipe goes away: the commands below write into relay(), which then
# drains into /dev/null, so apt-get and dpkg never get SIGPIPE or EPIPE halfway through unpacking packages
trap '' PIPE

export DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8
APT_OPTS=(-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold -o DPkg::Lock::Timeout=300
          -o APT::Status-Fd=1 -o Dpkg::Use-Pty=0)
# a name never ends in "-": "apt-get install foo-" means REMOVE foo (also after an :arch)
PKG_RE='^[a-z0-9]([a-z0-9+.-]{0,98}[a-z0-9+.])?(:[a-z0-9]([a-z0-9-]{0,18}[a-z0-9])?)?$'
REF_RE='^[A-Za-z][A-Za-z0-9_.-]{0,254}(/[A-Za-z0-9_]{0,20}(/[A-Za-z0-9_.-]{0,100})?)?$'
SNAP_RE='^[a-z0-9][a-z0-9-]{0,39}$'
DEV_RE='^[0-9a-f]{40}$'

relay() { cat || cat >/dev/null; }
run() { if [[ -n "${UPDATEL_DRY:-}" ]]; then echo "would run: $*"; else "$@" 2>&1 | relay; fi; }
die() { echo "$2" >&2; exit "$1"; }

# check ONE step's arguments (no side effects)
check_step() {
    local step=$1; shift
    case "$step" in
        refresh) (( $# == 0 )) || die 2 "refresh takes no arguments" ;;
        apt)
            if [[ "${1:-}" == --removals=* ]]; then
                local list=${1#--removals=} names; shift
                IFS=, read -r -a names <<<"$list"
                (( ${#names[@]} >= 1 && ${#names[@]} <= 2000 )) && [[ "$list" != *,,* && "$list" != *, ]] \
                    || die 2 "apt: --removals takes 1 to 2000 package names joined by commas"
                for p in "${names[@]}"; do [[ "$p" =~ $PKG_RE ]] || die 2 "not a package name: $p"; done
            fi
            (( $# >= 1 && $# <= 2000 )) || die 2 "apt: give --all or 1 to 2000 packages"
            if [[ "$1" == --all ]]; then (( $# == 1 )) || die 2 "apt: --all takes no package names"; return; fi
            for p in "$@"; do [[ "$p" =~ $PKG_RE ]] || die 2 "not a package name: $p"; done ;;
        flatpak)
            (( $# >= 1 && $# <= 500 )) || die 2 "flatpak: give --all or 1 to 500 refs"
            [[ "$1" == --all && $# == 1 ]] && return
            for r in "$@"; do [[ "$r" =~ $REF_RE ]] || die 2 "not a Flatpak ref: $r"; done ;;
        snap)
            (( $# >= 1 && $# <= 500 )) || die 2 "snap: give --all or 1 to 500 snaps"
            [[ "$1" == --all && $# == 1 ]] && return
            for s in "$@"; do [[ "$s" =~ $SNAP_RE ]] || die 2 "not a snap name: $s"; done ;;
        fwupd)
            (( $# >= 1 && $# <= 50 )) || die 2 "fwupd: give 1 to 50 device ids"
            for d in "$@"; do [[ "$d" =~ $DEV_RE ]] || die 2 "not a fwupd device id: $d"; done ;;
        *) die 2 "unknown step: $step" ;;
    esac
}

apt_step() {
    local allow=0 cmd sim removals r protected=() extra=() names
    local -A ok=()
    if [[ "$1" == --removals=* ]]; then
        allow=1
        IFS=, read -r -a names <<<"${1#--removals=}"
        for r in "${names[@]}"; do ok[$r]=1; done
        shift
    fi
    if [[ "$1" == --all ]]; then cmd=(-y --with-new-pkgs upgrade); else cmd=(-y --only-upgrade install -- "$@"); fi
    echo "== Simulating the upgrade (apt-get -s)"
    sim=$(apt-get -s "${cmd[@]}") || die 5 "apt-get couldn't plan this upgrade"
    removals=$(awk '/^Remv / {print $2}' <<<"$sim")
    for r in $removals; do
        case "${r%%:*}" in kubuntu-desktop|fonts-ibm-plex*) protected+=("$r") ;; esac
    done
    (( ${#protected[@]} == 0 )) || die 3 "refused: this upgrade would remove ${protected[*]}"
    if [[ -n "$removals" && $allow == 0 ]]; then
        die 4 "refused: this upgrade would remove ${removals//$'\n'/ }; confirm the removals in UpdateL first"
    fi
    for r in $removals; do [[ -n "${ok[$r]:-}" ]] || extra+=("$r"); done
    (( ${#extra[@]} == 0 )) || die 6 "refused: the plan changed since the preview; it would also remove ${extra[*]}"
    echo "== Upgrading packages"
    if [[ -n "$removals" ]]; then
        run apt-get "${APT_OPTS[@]}" "${cmd[@]}"
    else
        run apt-get "${APT_OPTS[@]}" --no-remove "${cmd[@]}"
    fi
}

do_step() {
    local step=$1; shift
    case "$step" in
        refresh)
            echo "== Refreshing the package lists (apt-get update)"
            run apt-get -o DPkg::Lock::Timeout=300 update ;;
        apt) apt_step "$@" ;;
        flatpak)
            echo "== Updating system Flatpaks"
            if [[ "$1" == --all ]]; then run flatpak update --system -y --noninteractive
            else run flatpak update --system -y --noninteractive -- "$@"; fi ;;
        snap)
            echo "== Refreshing snaps"
            if [[ "$1" == --all ]]; then run snap refresh; else run snap refresh -- "$@"; fi ;;
        fwupd)
            for d in "$@"; do
                echo "== Updating firmware of device $d"
                run fwupdmgr update --assume-yes --no-reboot-check --no-unreported-check --no-metadata-check "$d"
            done ;;
    esac
}

(( $# >= 1 )) || die 2 "usage: root-helper.sh refresh|apt|flatpak|snap|fwupd ARGS [+ STEP ARGS]..."

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
(( ${#steps[@]} <= 8 )) || die 2 "too many steps"

for s in "${steps[@]}"; do IFS=$'\x1f' read -r -a words <<<"$s"; check_step "${words[@]}"; done
for s in "${steps[@]}"; do IFS=$'\x1f' read -r -a words <<<"$s"; do_step "${words[@]}"; done
echo "== Done"
