// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Rectangle {
    id: root
    color: "black"
    property int stage
    readonly property real speed: @SPEED@

    Item {
        id: content
        anchors.fill: parent
        opacity: 0

        Image {
            id: clover
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -50
            source: "images/clover5.svg"
            sourceSize: Qt.size(64, 64)
        }
        Row {                                               // one dot per startup stage
            id: dots
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: clover.bottom; anchors.topMargin: 52
            spacing: 22
            Repeater {
                model: 6
                Rectangle {
                    required property int index
                    readonly property bool done: index < root.stage
                    readonly property bool now: index === root.stage
                    width: 8; height: 8; radius: 4
                    color: done ? "white" : "transparent"
                    border.color: done || now ? "white" : "#3a3a3a"; border.width: 1
                    Behavior on color { ColorAnimation { duration: 300 / root.speed } }
                    SequentialAnimation on opacity {
                        running: now; loops: Animation.Infinite
                        NumberAnimation { from: 1; to: 0.25; duration: 600 / root.speed; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 0.25; to: 1; duration: 600 / root.speed; easing.type: Easing.InOutSine }
                    }
                }
            }
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: dots.bottom; anchors.topMargin: 30
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
