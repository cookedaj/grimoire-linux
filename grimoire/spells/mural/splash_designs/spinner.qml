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
            id: dial
            width: 150; height: 150
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -30
            Canvas {                                        // a hairline arc sweeping round the clover
                id: arc
                anchors.fill: parent
                onPaint: {
                    const c = getContext("2d");
                    c.reset();
                    c.lineWidth = 1.5;
                    c.strokeStyle = "#262626";
                    c.beginPath(); c.arc(width / 2, height / 2, width / 2 - 2, 0, 2 * Math.PI); c.stroke();
                    c.strokeStyle = "white";
                    c.lineCap = "round";
                    c.beginPath(); c.arc(width / 2, height / 2, width / 2 - 2, -Math.PI / 2, 0); c.stroke();
                }
                RotationAnimator on rotation { from: 0; to: 360; loops: Animation.Infinite; duration: 1400 / root.speed }
            }
            Image { anchors.centerIn: parent; source: "images/clover5.svg"; sourceSize: Qt.size(60, 60) }
        }
        Text {
            id: pct
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: dial.bottom; anchors.topMargin: 40
            text: Math.round(root.progress * 100) + "%"
            color: "white"
            font.family: "IBM Plex Mono"; font.pixelSize: 13
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: pct.bottom; anchors.topMargin: 14
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
