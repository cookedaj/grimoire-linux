/*
    WidgetL System: what the widget draws, in plain QtQuick so Grimoire can render the same file as its preview.
    i18n()/i18nc() come from Plasma here and from preview.py's stand-in there (the same .mo catalogs).
    main.qml feeds it Plasma's sensor readings. A value below 0 means "not available" and its row says so.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Item {
    id: face

    property real cpu: -1                // percent
    property real ram: -1
    property real gpu: -1
    property string ramDetail: ""        // "9.8 of 31 GB"
    property real cpuTemp: -1            // degrees Celsius
    property real gpuTemp: -1
    property var cpuHistory: []
    property var ramHistory: []
    property var gpuHistory: []
    property string style: "bars"        // "bars" or "sparkline"
    property bool showGpu: true
    property bool showTemps: true
    property bool fahrenheit: false
    property int backgroundOpacity: 80

    readonly property int rows: showGpu ? 3 : 2
    readonly property real rowHeight: style === "sparkline" ? 64 : 44
    readonly property real designWidth: 300
    readonly property real designHeight: 40 + rows * rowHeight + (showTemps ? 34 : 0)
    implicitWidth: designWidth
    implicitHeight: designHeight

    readonly property real u: Math.max(0.3, Math.min(width / designWidth, height / designHeight))

    // letter spacing pulls joined scripts (Arabic, Devanagari, Bengali...) apart: none for those
    function spacing(text, px) {
        return /[؀-ࣿऀ-෿ﭐ-﷿ﹰ-﻿]/.test(String(text)) ? 0 : px;
    }
    readonly property string fontName: "IBM Plex Sans"

    function temp(c) {
        if (c < 0 || isNaN(c))
            return "–";
        return Math.round(fahrenheit ? c * 9 / 5 + 32 : c) + "°";
    }

    Rectangle {
        anchors.fill: parent
        radius: 16 * face.u
        color: "#0b0b0b"
        opacity: face.backgroundOpacity / 100
        border.color: "#2a2a2a"
        border.width: face.backgroundOpacity > 0 ? 1 : 0
    }

    Column {
        anchors.fill: parent
        anchors.margins: 20 * face.u
        spacing: 0

        Metric {
            width: parent.width
            height: face.rowHeight * face.u
            u: face.u
            label: i18nc("processor, short label", "CPU")
            value: face.cpu
            history: face.cpuHistory
            sparkline: face.style === "sparkline"
        }
        Metric {
            width: parent.width
            height: face.rowHeight * face.u
            u: face.u
            label: i18nc("memory, short label", "RAM")
            value: face.ram
            detail: face.ramDetail
            history: face.ramHistory
            sparkline: face.style === "sparkline"
        }
        Metric {
            visible: face.showGpu
            width: parent.width
            height: face.rowHeight * face.u
            u: face.u
            label: i18nc("graphics card, short label", "GPU")
            value: face.gpu
            history: face.gpuHistory
            sparkline: face.style === "sparkline"
        }

        Item {
            visible: face.showTemps
            width: parent.width
            height: 34 * face.u

            Rectangle {
                width: parent.width
                height: 1
                y: 8 * face.u
                color: "#222222"
            }
            Row {
                anchors.bottom: parent.bottom
                spacing: 22 * face.u

                Repeater {
                    model: face.showGpu ? [[i18nc("processor, short label", "CPU"), face.cpuTemp], [i18nc("graphics card, short label", "GPU"), face.gpuTemp]]
                                        : [[i18nc("processor, short label", "CPU"), face.cpuTemp]]
                    Row {
                        required property var modelData
                        spacing: 6 * face.u
                        Text {
                            text: modelData[0]
                            color: "#6f6f6f"
                            font.family: face.fontName
                            font.pixelSize: 11 * face.u
                            font.letterSpacing: face.spacing(text, 2 * face.u)
                            anchors.baseline: tempValue.baseline
                        }
                        Text {
                            id: tempValue
                            text: face.temp(modelData[1])
                            color: "#ececec"
                            font.family: face.fontName
                            font.weight: Font.Light
                            font.pixelSize: 15 * face.u
                        }
                    }
                }
            }
        }
    }
}
