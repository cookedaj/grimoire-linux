// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Rectangle {
    id: root
    color: "black"
    property int stage
    readonly property real progress: Math.min(stage, 6) / 6
    readonly property real speed: @SPEED@
    readonly property string phrase: @SHOW_TAGLINE@ ? @TAGLINE@ : "GRIMOIRE"
    property int typed: 0

    Timer {                                                 // types the phrase, one character at a time
        interval: 70 / root.speed; repeat: true
        running: root.typed < root.phrase.length
        onTriggered: root.typed += 1
    }

    Item {
        id: content
        anchors.fill: parent
        opacity: 0

        Column {
            anchors.centerIn: parent
            spacing: 26
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 6
                Text {
                    text: "> " + root.phrase.substring(0, root.typed)
                    color: "white"
                    font.family: "IBM Plex Mono"; font.pixelSize: 22
                }
                Rectangle {                                 // block cursor, blinking
                    width: 12; height: 24; color: "white"; anchors.verticalCenter: parent.verticalCenter
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        PropertyAction { value: 1 }
                        PauseAnimation { duration: 530 }
                        PropertyAction { value: 0 }
                        PauseAnimation { duration: 530 }
                    }
                }
            }
            Text {                                          // a text-mode progress bar
                anchors.horizontalCenter: parent.horizontalCenter
                readonly property int cells: 24
                readonly property int full: Math.round(root.progress * cells)
                text: "[" + "#".repeat(full) + ".".repeat(cells - full) + "]  " + Math.round(root.progress * 100) + "%"
                color: "#7a7a7a"
                font.family: "IBM Plex Mono"; font.pixelSize: 13
            }
        }
    }
    onStageChanged: if (stage >= 6) fadeOut.start()
    Component.onCompleted: fadeIn.start()
    OpacityAnimator { id: fadeIn; target: content; from: 0; to: 1; duration: 400 / root.speed }
    OpacityAnimator { id: fadeOut; target: content; from: 1; to: 0; duration: 500 / root.speed }
}
