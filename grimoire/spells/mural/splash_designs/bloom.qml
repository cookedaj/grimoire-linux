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

        Image {                                             // the four-leaf clover opening up as Plasma loads
            id: clover
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -30
            source: "images/clover4.svg"
            sourceSize: Qt.size(220, 220)
            width: 220; height: 220
            scale: 0.45 + 0.55 * root.progress
            opacity: 0.35 + 0.65 * root.progress
            Behavior on scale { NumberAnimation { duration: 900 / root.speed; easing.type: Easing.OutBack } }
            Behavior on opacity { NumberAnimation { duration: 900 / root.speed } }
            RotationAnimator on rotation { from: 0; to: 360; loops: Animation.Infinite; duration: 24000 / root.speed }
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: clover.bottom; anchors.topMargin: 40
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
