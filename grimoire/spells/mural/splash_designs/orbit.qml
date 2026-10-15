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

        Item {
            id: ring
            width: 200; height: 200
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -30
            Rectangle {                                     // the track
                anchors.fill: parent; radius: width / 2
                color: "transparent"; border.color: "#262626"; border.width: 1
            }
            Image { anchors.centerIn: parent; source: "images/clover5.svg"; sourceSize: Qt.size(72, 72) }
            Item {                                          // the moon: one white dot riding the track
                anchors.fill: parent
                RotationAnimator on rotation {
                    from: 0; to: 360; loops: Animation.Infinite; duration: 2600 / root.speed
                }
                Rectangle { width: 9; height: 9; radius: 4.5; color: "white"
                            x: parent.width / 2 - 4.5; y: -4.5 }
            }
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: ring.bottom; anchors.topMargin: 54
            text: @TAGLINE@
            color: "#8c8c8c"
            font.family: "IBM Plex Sans"; font.pixelSize: 12
            // spaced-out capitals, but joined scripts (Arabic, Devanagari, Bengali…) stay joined
            font.letterSpacing: /[\u0600-\u08FF\u0900-\u0DFF\uFB50-\uFDFF\uFE70-\uFEFF]/.test(text) ? 0 : 6
        }
    }
    onStageChanged: if (stage >= 6) fadeOut.start()
    Component.onCompleted: fadeIn.start()
    OpacityAnimator { id: fadeIn; target: content; from: 0; to: 1; duration: 700 / root.speed }
    OpacityAnimator { id: fadeOut; target: content; from: 1; to: 0; duration: 500 / root.speed }
}
