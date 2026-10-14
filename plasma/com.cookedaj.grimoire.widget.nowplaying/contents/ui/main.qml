/*
    WidgetL Now Playing: what's playing in any MPRIS app (music players, browsers, video), with the cover in
    grayscale and previous / play-pause / next. It follows the same "current player" as Plasma's own media
    controls (Plasma's Mpris2Model). The drawing is Face.qml.
    Note: never declare properties typed with the private Mpris types (they fail inside plasmashell); `var` it is.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.mpris as Mpris

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground      // Face draws its own black panel
    preferredRepresentation: fullRepresentation
    toolTipMainText: player ? (player.track || player.identity) : i18n("Nothing playing")
    toolTipSubText: player ? player.artist : ""

    Mpris.Mpris2Model {
        id: mpris
    }

    readonly property var player: mpris.currentPlayer
    readonly property bool playing: player !== null && player !== undefined
                                    && player.playbackStatus === Mpris.PlaybackStatus.Playing

    // the position only arrives on seeks; ask for it every second while something plays
    Timer {
        interval: 1000
        repeat: true
        running: root.playing
        onTriggered: root.player.updatePosition()
    }

    fullRepresentation: Face {
        Layout.minimumWidth: 220
        Layout.minimumHeight: 84
        Layout.preferredWidth: implicitWidth
        Layout.preferredHeight: implicitHeight
        hasPlayer: !!root.player
        title: root.player ? root.player.track : ""
        artist: root.player ? root.player.artist : ""
        album: Plasmoid.configuration.showAlbum && root.player ? root.player.album : ""
        playerName: root.player ? root.player.identity : ""
        artUrl: root.player ? root.player.artUrl : ""
        playing: root.playing
        canControl: root.player ? root.player.canControl : false
        canPrevious: root.player ? root.player.canGoPrevious : false
        canNext: root.player ? root.player.canGoNext : false
        position: root.player ? root.player.position / 1000000 : 0          // MPRIS counts microseconds
        length: root.player ? root.player.length / 1000000 : 0
        grayscaleCover: Plasmoid.configuration.grayscaleCover
        backgroundOpacity: Plasmoid.configuration.backgroundOpacity
        coverEffect: Component {
            MultiEffect {
                saturation: -1.0
            }
        }
        onPrevious: if (root.player) root.player.Previous()
        onPlayPause: if (root.player) root.player.PlayPause()
        onNext: if (root.player) root.player.Next()
    }
}
