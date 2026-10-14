/*
    A round, borderless control button for WidgetL Now Playing: a line glyph that brightens and gets a ring on hover.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Item {
    id: button

    property alias glyph: icon.name
    property string label                       // read by screen readers
    property bool primary: false
    signal clicked()

    Accessible.role: Accessible.Button
    Accessible.name: label
    Accessible.onPressAction: if (enabled) button.clicked()
    opacity: enabled ? 1 : 0.3

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: button.primary ? (mouse.pressed ? "#d0d0d0" : "#f2f2f2") : "transparent"
        border.color: button.primary ? "transparent" : (mouse.containsMouse ? "#5a5a5a" : "transparent")
        border.width: 1
    }
    Glyph {
        id: icon
        anchors.centerIn: parent
        width: parent.width * 0.55
        height: width
        ink: button.primary ? "#0b0b0b" : (mouse.containsMouse ? "#ffffff" : "#bdbdbd")
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: button.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: button.clicked()
    }
}
