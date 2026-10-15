// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Rectangle {
    id: root
    color: "black"
    property int stage
    readonly property real progress: Math.min(stage, 6) / 6
    readonly property real speed: @SPEED@
    readonly property string word: "GRIMOIRE"

    Item {
        id: content
        anchors.fill: parent
        opacity: 0

        Row {                                               // the name, lit letter by letter as Plasma loads
            id: name
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -20
            spacing: 26
            Repeater {
                model: root.word.length
                Text {
                    required property int index
                    text: root.word.charAt(index)
                    color: "white"
                    opacity: index < Math.ceil(root.progress * root.word.length) ? 1 : 0.14
                    Behavior on opacity { NumberAnimation { duration: 500 / root.speed } }
                    font.family: "IBM Plex Sans"; font.weight: Font.ExtraLight; font.pixelSize: 64
                }
            }
        }
        Rectangle {
            id: rule
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: name.bottom; anchors.topMargin: 30
            width: name.width; height: 1; color: "#262626"
        }
        Text {
            visible: @SHOW_TAGLINE@
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: rule.bottom; anchors.topMargin: 24
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
