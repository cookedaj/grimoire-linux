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
            id: center
            width: 96; height: 96
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -30
            Repeater {                                      // three rings, one after another, spreading out
                model: 3
                Rectangle {
                    id: ring
                    required property int index
                    anchors.centerIn: parent
                    width: 96; height: 96; radius: 48
                    color: "transparent"; border.color: "white"; border.width: 1
                    scale: 1; opacity: 0
                    ParallelAnimation {
                        running: true; loops: Animation.Infinite
                        SequentialAnimation {
                            PauseAnimation { duration: index * 900 / root.speed }
                            NumberAnimation { target: ring; property: "scale"; from: 0.9; to: 3.2
                                              duration: 2700 / root.speed; easing.type: Easing.OutCubic }
                        }
                        SequentialAnimation {
                            PauseAnimation { duration: index * 900 / root.speed }
                            NumberAnimation { target: ring; property: "opacity"; from: 0.55; to: 0
                                              duration: 2700 / root.speed; easing.type: Easing.OutQuad }
                        }
                    }
                }
            }
            Image { anchors.centerIn: parent; source: "images/clover5.svg"; sourceSize: Qt.size(80, 80) }
        }
        Rectangle {
            id: track
            width: 160; height: 1; color: "#2a2a2a"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: center.bottom; anchors.topMargin: 120
            Rectangle {
                height: 1; color: "white"
                width: track.width * root.progress
                Behavior on width { NumberAnimation { duration: 600 / root.speed; easing.type: Easing.OutCubic } }
            }
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: track.bottom; anchors.topMargin: 22
            text: @TAGLINE@
            color: "#8c8c8c"
            font.family: "IBM Plex Sans"; font.pixelSize: 12
            font.letterSpacing: /[\u0600-\u08FF\u0900-\u0DFF\uFB50-\uFDFF\uFE70-\uFEFF]/.test(text) ? 0 : 6
        }
    }
    onStageChanged: if (stage >= 6) fadeOut.start()
    Component.onCompleted: fadeIn.start()
    OpacityAnimator { id: fadeIn; target: content; from: 0; to: 1; duration: 700 / root.speed }
    OpacityAnimator { id: fadeOut; target: content; from: 1; to: 0; duration: 500 / root.speed }
}
