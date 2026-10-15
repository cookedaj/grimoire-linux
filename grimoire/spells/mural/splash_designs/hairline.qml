// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Rectangle {
    id: root
    color: "black"
    property int stage
    readonly property real progress: Math.min(stage, 6) / 6
    readonly property real speed: @SPEED@

    Item {
        id: content
        anchors.fill: parent
        opacity: 0

        Row {                                               // small wordmark, bottom-left
            x: 64; anchors.bottom: line.top; anchors.bottomMargin: 26
            spacing: 14
            Image { source: "images/clover5.svg"; sourceSize: Qt.size(18, 18); anchors.verticalCenter: parent.verticalCenter }
            Text { text: "GRIMOIRE"; color: "white"; anchors.verticalCenter: parent.verticalCenter
                   font.family: "IBM Plex Sans"; font.weight: Font.Medium; font.pixelSize: 12; font.letterSpacing: 6 }
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.right: parent.right; anchors.rightMargin: 64
            anchors.bottom: line.top; anchors.bottomMargin: 28
            text: @TAGLINE@
            color: "#6c6c6c"
            font.family: "IBM Plex Sans"; font.pixelSize: 11
            font.letterSpacing: /[\u0600-\u08FF\u0900-\u0DFF\uFB50-\uFDFF\uFE70-\uFEFF]/.test(text) ? 0 : 5
        }
        Rectangle {                                         // the whole width is the progress bar
            id: line
            anchors.bottom: parent.bottom; anchors.bottomMargin: 48
            x: 64; width: parent.width - 128; height: 1; color: "#1e1e1e"
            Rectangle {
                height: 1; color: "white"
                width: line.width * root.progress
                Behavior on width { NumberAnimation { duration: 800 / root.speed; easing.type: Easing.OutCubic } }
            }
        }
    }
    onStageChanged: if (stage >= 6) fadeOut.start()
    Component.onCompleted: fadeIn.start()
    OpacityAnimator { id: fadeIn; target: content; from: 0; to: 1; duration: 700 / root.speed }
    OpacityAnimator { id: fadeOut; target: content; from: 1; to: 0; duration: 500 / root.speed }
}
