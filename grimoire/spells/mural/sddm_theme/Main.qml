// SPDX-License-Identifier: GPL-3.0-or-later
// Grimoire login (SDDM). Layout and look come from theme.conf, written by Grimoire → MuraL → Login.
// Each layout is a Component; only the chosen one is loaded, so there is exactly one password field.
import QtQuick

Rectangle {
    id: root
    width: 1920; height: 1080
    color: "black"

    readonly property string layout: String(config.layout || "card")
    readonly property real dim: Number(config.dim || 55) / 100
    readonly property bool use24: String(config.clock24) === "true"
    readonly property bool showPower: String(config.showPower) !== "false"
    readonly property real u: Math.min(width / 1920, height / 1080)     // scale unit
    readonly property string mono: "IBM Plex Mono"

    Image {
        id: bg
        anchors.fill: parent
        source: config.background ? Qt.resolvedUrl(config.background) : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: false
    }
    Rectangle { anchors.fill: parent; color: "black"; opacity: root.layout === "console" ? Math.max(root.dim, 0.8) : root.dim }

    Loader {
        anchors.fill: parent
        focus: true
        sourceComponent: ({ card: card, minimal: minimal, sidebar: sidebar, paper: paper, console: consoleLayout,
                            corner: corner, frame: frame, display: display, daylight: daylight })[root.layout] || card
    }

    // Card: small clock top-left, a dark floating card with the clover and login, power row below
    Component {
        id: card
        Item {
            Clock { x: 72 * root.u; y: 56 * root.u; width: 400 * root.u; size: 44 * root.u
                    align: Text.AlignLeft; use24: root.use24 }
            Rectangle {
                anchors.centerIn: parent
                width: 420 * root.u; height: 380 * root.u
                radius: 18 * root.u
                color: Qt.rgba(0.03, 0.03, 0.03, 0.82)
                border.color: "#2e2e2e"; border.width: 1
                Column {
                    anchors.centerIn: parent
                    spacing: 40 * root.u
                    Image { anchors.horizontalCenter: parent.horizontalCenter; source: "clover5.svg"
                            sourceSize: Qt.size(64 * root.u, 64 * root.u) }
                    Form { fieldWidth: 300 * root.u }
                }
            }
            Power { visible: root.showPower; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 48 * root.u }
        }
    }

    // Minimal: nothing but a clock and the line, centered over the art
    Component {
        id: minimal
        Item {
            Column {
                anchors.centerIn: parent
                spacing: 90 * root.u
                Clock { width: 600 * root.u; size: 96 * root.u; use24: root.use24; upper: true }
                Form { anchors.horizontalCenter: parent.horizontalCenter; fieldWidth: 320 * root.u }
            }
            Power { visible: root.showPower; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 48 * root.u }
        }
    }

    // Sidebar: a solid black column on the left holds everything; the art fills the rest
    Component {
        id: sidebar
        Item {
            Rectangle {
                id: side
                width: Math.max(420 * root.u, parent.width * 0.32); height: parent.height
                color: "#050505"
                Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: "#262626" }
                Image { x: 80 * root.u; y: 80 * root.u; source: "clover5.svg"
                        sourceSize: Qt.size(40 * root.u, 40 * root.u) }
                Column {
                    x: 80 * root.u; anchors.verticalCenter: parent.verticalCenter
                    width: side.width - 160 * root.u
                    spacing: 80 * root.u
                    Clock { width: parent.width; size: 72 * root.u; align: Text.AlignLeft; use24: root.use24 }
                    Form { fieldWidth: parent.width; align: Text.AlignLeft }
                }
                Power { visible: root.showPower; x: 80 * root.u
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 64 * root.u }
            }
        }
    }

    // Paper: the same column in white with black ink
    Component {
        id: paper
        Item {
            Rectangle {
                id: sheet
                width: Math.max(460 * root.u, parent.width * 0.36); height: parent.height
                color: "#f2f2f2"
                Text { x: 88 * root.u; y: 88 * root.u; text: "GRIMOIRE"; color: "#111111"
                       font.family: "IBM Plex Sans"; font.weight: Font.DemiBold; font.pixelSize: 13 * Math.max(1, root.u)
                       font.letterSpacing: 6 }
                Column {
                    x: 88 * root.u; anchors.verticalCenter: parent.verticalCenter
                    width: sheet.width - 176 * root.u
                    spacing: 80 * root.u
                    Clock { width: parent.width; size: 88 * root.u; align: Text.AlignLeft; use24: root.use24
                            ink: "#0a0a0a"; sub: "#5c5c5c"; weight: Font.ExtraLight }
                    Form { fieldWidth: parent.width; align: Text.AlignLeft
                           ink: "#0a0a0a"; muted: "#555555"; faint: "#a0a0a0"; rest: "#8a8a8a" }
                }
                Power { visible: root.showPower; x: 88 * root.u; ink: "black"; muted: "#7a7a7a"
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 64 * root.u }
            }
        }
    }

    // Console: a text-mode login in IBM Plex Mono, top-left, over a nearly black screen
    Component {
        id: consoleLayout
        Item {
            Column {
                x: 96 * root.u; y: 88 * root.u
                spacing: 26 * root.u
                Text { text: "Grimoire Linux  ·  " + Qt.formatDate(new Date(), "yyyy-MM-dd"); color: "#7a7a7a"
                       font.family: root.mono; font.pixelSize: 15 }
                Clock { width: 600 * root.u; size: 64 * root.u; align: Text.AlignLeft; use24: root.use24
                        family: root.mono; weight: Font.Normal; showDate: false }
                Item { width: 1; height: 20 * root.u }
                Form { fieldWidth: 520 * root.u; align: Text.AlignLeft; family: root.mono; prompt: "> "
                       muted: "#8a8a8a"; faint: "#4a4a4a"; rest: "#2a2a2a" }
            }
            Power { visible: root.showPower; x: 96 * root.u; lower: true; family: root.mono
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 64 * root.u }
        }
    }

    // Corner: an oversized clock bottom-left, the login line bottom-right
    Component {
        id: corner
        Item {
            Image { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 72 * root.u
                    source: "clover5.svg"; sourceSize: Qt.size(36 * root.u, 36 * root.u) }
            Clock { x: 88 * root.u; anchors.bottom: parent.bottom; anchors.bottomMargin: 80 * root.u
                    width: 900 * root.u; size: 168 * root.u; align: Text.AlignLeft; use24: root.use24
                    weight: Font.Thin; upper: true }
            Column {
                anchors.right: parent.right; anchors.bottom: parent.bottom
                anchors.rightMargin: 96 * root.u; anchors.bottomMargin: 96 * root.u
                spacing: 36 * root.u
                Form { fieldWidth: 320 * root.u; align: Text.AlignLeft }
                Power { visible: root.showPower }
            }
        }
    }

    // Frame: a hairline border inset around the screen, everything centered inside it
    Component {
        id: frame
        Item {
            Rectangle {
                anchors.fill: parent; anchors.margins: 40 * root.u
                color: "transparent"; border.color: "#d8d8d8"; border.width: 1
                Rectangle { anchors.fill: parent; anchors.margins: 8 * root.u
                            color: "transparent"; border.color: "#4a4a4a"; border.width: 1 }
            }
            Clock { anchors.horizontalCenter: parent.horizontalCenter; y: 150 * root.u
                    width: 700 * root.u; size: 64 * root.u; use24: root.use24; upper: true }
            Column {
                anchors.centerIn: parent; anchors.verticalCenterOffset: 60 * root.u
                spacing: 36 * root.u
                Image { anchors.horizontalCenter: parent.horizontalCenter; source: "clover5.svg"
                        sourceSize: Qt.size(48 * root.u, 48 * root.u) }
                Form { fieldWidth: 320 * root.u }
            }
            Power { visible: root.showPower; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 96 * root.u }
        }
    }

    // Display: one enormous thin clock fills the screen; the login waits small underneath
    Component {
        id: display
        Item {
            Clock { anchors.horizontalCenter: parent.horizontalCenter; y: parent.height * 0.18
                    width: parent.width; size: 300 * root.u; use24: root.use24; weight: Font.Thin; upper: true }
            Form { anchors.horizontalCenter: parent.horizontalCenter; y: parent.height * 0.66
                   fieldWidth: 300 * root.u }
            Power { visible: root.showPower; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 48 * root.u }
        }
    }

    // Daylight: a white card with black ink floating over the art
    Component {
        id: daylight
        Item {
            Clock { x: 72 * root.u; y: 56 * root.u; width: 400 * root.u; size: 44 * root.u
                    align: Text.AlignLeft; use24: root.use24 }
            Rectangle {
                anchors.centerIn: parent
                width: 440 * root.u; height: 340 * root.u
                radius: 6 * root.u
                color: "#f4f4f4"
                Column {
                    anchors.centerIn: parent
                    spacing: 44 * root.u
                    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "WELCOME BACK"; color: "#111111"
                           font.family: "IBM Plex Sans"; font.weight: Font.DemiBold; font.pixelSize: 13
                           font.letterSpacing: 6 }
                    Form { fieldWidth: 320 * root.u; boxed: true
                           ink: "#0a0a0a"; muted: "#555555"; faint: "#9a9a9a" }
                }
            }
            Power { visible: root.showPower; anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 48 * root.u }
        }
    }
}
