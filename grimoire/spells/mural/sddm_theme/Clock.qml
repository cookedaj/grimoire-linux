// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Column {
    id: clock
    property real size: 72
    property int align: Text.AlignHCenter
    property bool use24: false
    property date now: new Date()
    property color ink: "white"
    property color sub: "#b0b0b0"
    property string family: "IBM Plex Sans"
    property int weight: Font.Light
    property bool showDate: true
    property bool upper: false                  // date in spaced capitals
    spacing: size * 0.06

    Timer { interval: 1000; running: true; repeat: true; onTriggered: clock.now = new Date() }

    Text {
        width: parent.width
        horizontalAlignment: clock.align
        text: Qt.formatTime(clock.now, clock.use24 ? "HH:mm" : "h:mm AP")
        color: clock.ink
        font.family: clock.family; font.weight: clock.weight; font.pixelSize: clock.size
    }
    Text {
        visible: clock.showDate
        width: parent.width
        horizontalAlignment: clock.align
        text: clock.upper ? Qt.formatDate(clock.now, "dddd d MMMM").toUpperCase() : Qt.formatDate(clock.now, "dddd, MMMM d")
        color: clock.sub
        font.family: clock.family; font.pixelSize: Math.max(13, clock.size * (clock.upper ? 0.13 : 0.2))
        font.letterSpacing: clock.upper ? 4 : 0
    }
}
