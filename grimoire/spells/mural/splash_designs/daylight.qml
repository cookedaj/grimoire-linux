// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Rectangle {
    id: root
    color: "#f2f2f2"
    property int stage
    readonly property real progress: Math.min(stage, 6) / 6
    readonly property real speed: @SPEED@

    Item {
        id: content
        anchors.fill: parent
        opacity: 0

        Image {
            id: clover
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -40
            source: "images/clover5-black.svg"
            sourceSize: Qt.size(104, 104)
            SequentialAnimation on scale {
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 1.04; duration: 1600 / root.speed; easing.type: Easing.InOutSine }
                NumberAnimation { from: 1.04; to: 1.0; duration: 1600 / root.speed; easing.type: Easing.InOutSine }
            }
        }
        Rectangle {
            id: track
            width: 220; height: 2; radius: 1; color: "#d4d4d4"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: clover.bottom; anchors.topMargin: 56
            Rectangle {
                height: 2; radius: 1; color: "#0a0a0a"
                width: track.width * root.progress
                Behavior on width { NumberAnimation { duration: 600 / root.speed; easing.type: Easing.OutCubic } }
            }
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: track.bottom; anchors.topMargin: 22
            text: @TAGLINE@
            color: "#5c5c5c"
            font.family: "IBM Plex Sans"; font.pixelSize: 12
            font.letterSpacing: /[\u0600-\u08FF\u0900-\u0DFF\uFB50-\uFDFF\uFE70-\uFEFF]/.test(text) ? 0 : 6
        }
    }
    onStageChanged: if (stage >= 6) fadeOut.start()
    Component.onCompleted: fadeIn.start()
    OpacityAnimator { id: fadeIn; target: content; from: 0; to: 1; duration: 700 / root.speed }
    OpacityAnimator { id: fadeOut; target: content; from: 1; to: 0; duration: 500 / root.speed }
}
