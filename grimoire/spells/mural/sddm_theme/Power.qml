// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Row {
    id: power
    property color ink: "white"
    property color muted: "#7a7a7a"
    property string family: "IBM Plex Sans"
    property bool lower: false                  // "sleep" instead of "SLEEP" (the console layout)
    spacing: 28
    Repeater {
        model: [
            { label: "Sleep", ok: sddm.canSuspend, act: function () { sddm.suspend() } },
            { label: "Restart", ok: sddm.canReboot, act: function () { sddm.reboot() } },
            { label: "Shut down", ok: sddm.canPowerOff, act: function () { sddm.powerOff() } }
        ]
        Text {
            required property var modelData
            visible: modelData.ok
            text: power.lower ? "[" + modelData.label.toLowerCase() + "]" : modelData.label.toUpperCase()
            color: hover.hovered ? power.ink : power.muted
            font.family: power.family; font.pixelSize: power.lower ? 13 : 11; font.letterSpacing: power.lower ? 0 : 3
            HoverHandler { id: hover }
            TapHandler { onTapped: modelData.act() }
        }
    }
}
