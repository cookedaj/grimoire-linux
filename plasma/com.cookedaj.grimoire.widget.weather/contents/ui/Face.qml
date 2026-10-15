/*
    WidgetL Weather: what the widget draws, in plain QtQuick so Grimoire can render the same file as its preview.
    i18n()/i18nc() come from Plasma here and from preview.py's stand-in there (the same .mo catalogs).
    main.qml fetches the forecast from Open-Meteo and hands it over ready to show.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Item {
    id: face

    property string place: ""
    property string message: ""           // shown instead of the weather (no place yet, can't reach the service)
    property string note: ""              // small line under the weather ("Updated 14:05", "Offline, from 13:35")
    property bool hasData: false
    property real temperature: 0
    property real feelsLike: 0
    property int code: 0
    property bool isDay: true
    property real wind: 0
    property string windUnit: "km/h"
    property int humidity: 0
    property var days: []                 // [{name: "Thu", code: 3, high: 21, low: 12}, ...]
    property bool showForecast: true
    property int backgroundOpacity: 80

    readonly property real designWidth: 340
    readonly property real designHeight: showForecast ? 220 : 140
    implicitWidth: designWidth
    implicitHeight: designHeight

    readonly property real u: Math.max(0.3, Math.min(width / designWidth, height / designHeight))
    readonly property string fontName: "IBM Plex Sans"

    // letter spacing pulls joined scripts (Arabic, Devanagari, Bengali...) apart: none for those
    function spacing(text, px) {
        return /[؀-ࣿऀ-෿ﭐ-﷿ﹰ-﻿]/.test(String(text)) ? 0 : px;
    }

    function deg(v) {
        const n = Math.round(v);
        return (n < 0 ? "\u2212" + (-n) : n) + "°";            // a real minus sign, not a hyphen
    }

    function describe(c) {
        if (c <= 0) return i18n("Clear");
        if (c === 1) return i18n("Mostly clear");
        if (c === 2) return i18n("Partly cloudy");
        if (c === 3) return i18n("Overcast");
        if (c === 45 || c === 48) return i18n("Fog");
        if (c >= 51 && c <= 57) return i18n("Drizzle");
        if (c >= 61 && c <= 65) return i18n("Rain");
        if (c === 66 || c === 67) return i18n("Freezing rain");
        if (c >= 71 && c <= 77) return i18n("Snow");
        if (c >= 80 && c <= 82) return i18n("Showers");
        if (c === 85 || c === 86) return i18n("Snow showers");
        if (c >= 95) return i18n("Thunderstorm");
        return i18n("Cloudy");
    }

    Rectangle {
        anchors.fill: parent
        radius: 16 * face.u
        color: "#0b0b0b"
        opacity: face.backgroundOpacity / 100
        border.color: "#2a2a2a"
        border.width: face.backgroundOpacity > 0 ? 1 : 0
    }

    // no data: one calm line in the middle
    Column {
        visible: !face.hasData
        anchors.centerIn: parent
        width: parent.width - 48 * face.u
        spacing: 10 * face.u

        WeatherIcon {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 36 * face.u
            height: width
            code: 2
            ink: "#6f6f6f"
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: face.message
            textFormat: Text.PlainText
            color: "#9a9a9a"
            font.family: face.fontName
            font.pixelSize: 13 * face.u
        }
    }

    Item {
        visible: face.hasData
        anchors.fill: parent
        anchors.margins: 20 * face.u

        WeatherIcon {
            id: bigIcon
            width: 58 * face.u
            height: width
            code: face.code
            day: face.isDay
            stroke: 1.2
        }
        Text {
            id: tempText
            anchors.left: bigIcon.right
            anchors.leftMargin: 14 * face.u
            anchors.verticalCenter: bigIcon.verticalCenter
            text: face.deg(face.temperature)
            color: "#f2f2f2"
            font.family: face.fontName
            font.weight: Font.Thin
            font.pixelSize: 54 * face.u
        }
        Column {
            anchors.left: tempText.right
            anchors.leftMargin: 14 * face.u
            anchors.right: parent.right
            anchors.verticalCenter: bigIcon.verticalCenter
            spacing: 2 * face.u

            Text {
                width: parent.width
                elide: Text.ElideRight
                text: face.describe(face.code)
                color: "#ececec"
                font.family: face.fontName
                font.pixelSize: 14 * face.u
            }
            Text {
                width: parent.width
                elide: Text.ElideRight
                text: face.place.toUpperCase()
                textFormat: Text.PlainText
                color: "#6f6f6f"
                font.family: face.fontName
                font.pixelSize: 10 * face.u
                font.letterSpacing: face.spacing(text, 2 * face.u)
            }
        }

        Text {
            id: details
            anchors.top: bigIcon.bottom
            anchors.topMargin: 10 * face.u
            width: parent.width
            elide: Text.ElideRight
            text: i18n("Feels %1 · Wind %2 %3 · Humidity %4%", face.deg(face.feelsLike), Math.round(face.wind),
                       face.windUnit, face.humidity)
            color: "#8c8c8c"
            font.family: face.fontName
            font.pixelSize: 11 * face.u
        }

        Rectangle {
            id: rule
            visible: face.showForecast
            anchors.top: details.bottom
            anchors.topMargin: 12 * face.u
            width: parent.width
            height: 1
            color: "#222222"
        }

        Row {
            visible: face.showForecast
            anchors.top: rule.bottom
            anchors.topMargin: 10 * face.u
            width: parent.width

            Repeater {
                model: face.days
                Column {
                    required property var modelData
                    width: parent.width / Math.max(1, face.days.length)
                    spacing: 4 * face.u

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: String(modelData.name).toUpperCase()
                        color: "#6f6f6f"
                        font.family: face.fontName
                        font.pixelSize: 10 * face.u
                        font.letterSpacing: face.spacing(text, 1.5 * face.u)
                    }
                    WeatherIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 24 * face.u
                        height: width
                        code: modelData.code
                        ink: "#d0d0d0"
                    }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 5 * face.u
                        Text {
                            text: face.deg(modelData.high)
                            color: "#ececec"
                            font.family: face.fontName
                            font.pixelSize: 12 * face.u
                        }
                        Text {
                            text: face.deg(modelData.low)
                            color: "#6f6f6f"
                            font.family: face.fontName
                            font.pixelSize: 12 * face.u
                        }
                    }
                }
            }
        }

        Text {
            visible: face.note !== "" && !face.showForecast
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            text: face.note
            textFormat: Text.PlainText
            color: "#555555"
            font.family: face.fontName
            font.pixelSize: 9 * face.u
        }
    }
}
