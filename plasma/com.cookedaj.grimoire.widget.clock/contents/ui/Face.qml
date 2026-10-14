/*
    WidgetL Clock: what the widget draws, in plain QtQuick so Grimoire can render the same file as its preview.
    i18n()/i18nc() come from Plasma here and from preview.py's stand-in there (the same .mo catalogs).
    main.qml feeds it the time and the settings.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Item {
    id: face

    property date now: new Date()
    property bool use24h: true
    property bool showSeconds: false
    property bool showDate: true
    property int backgroundOpacity: 80          // 0 = no panel behind the digits

    readonly property real designWidth: 360
    readonly property real designHeight: showDate ? 170 : 130
    implicitWidth: designWidth
    implicitHeight: designHeight

    // every size is a multiple of u, so the face grows with the widget (fonts sized, not scaled, stay sharp)
    readonly property real u: Math.max(0.3, Math.min(width / designWidth, height / designHeight))
    readonly property string fontName: "IBM Plex Sans"

    // letter spacing pulls joined scripts (Arabic, Devanagari, Bengali...) apart: none for those
    function spacing(text, px) {
        return /[؀-ࣿऀ-෿ﭐ-﷿ﹰ-﻿]/.test(String(text)) ? 0 : px;
    }

    // "h" alone is still 24-hour in Qt's formats (only "h AP" is 12-hour), so the 12-hour hour is worked out here
    readonly property string hours: use24h ? Qt.formatTime(now, "HH") : String(now.getHours() % 12 || 12)
    readonly property string minutes: Qt.formatTime(now, "mm")
    readonly property string seconds: Qt.formatTime(now, "ss")
    readonly property string ampm: now.getHours() < 12 ? Qt.locale().amText : Qt.locale().pmText

    Rectangle {
        anchors.fill: parent
        radius: 16 * face.u
        color: "#0b0b0b"
        opacity: face.backgroundOpacity / 100
        border.color: "#2a2a2a"
        border.width: face.backgroundOpacity > 0 ? 1 : 0
    }

    Column {
        anchors.centerIn: parent
        spacing: 2 * face.u

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8 * face.u

            Text {
                id: digits
                text: face.hours + ":" + face.minutes
                color: "#f2f2f2"
                font.family: face.fontName
                font.weight: Font.Thin
                font.pixelSize: 96 * face.u
                font.features: { "tnum": 1 }       // digits keep one width, so the clock doesn't wobble
            }

            // seconds sit on the digits' baseline, AM/PM above them (or alone on the baseline)
            Item {
                visible: face.showSeconds || !face.use24h
                width: Math.max(secondsText.visible ? secondsText.width : 0, ampmText.visible ? ampmText.width : 0)
                height: digits.height

                Text {
                    id: secondsText
                    visible: face.showSeconds
                    y: digits.baselineOffset - baselineOffset
                    text: face.seconds
                    color: "#8c8c8c"
                    font.family: face.fontName
                    font.weight: Font.ExtraLight
                    font.pixelSize: 32 * face.u
                    font.features: { "tnum": 1 }
                }
                Text {
                    id: ampmText
                    visible: !face.use24h
                    y: secondsText.visible ? secondsText.y - height + 4 * face.u : digits.baselineOffset - baselineOffset
                    text: face.ampm
                    color: "#8c8c8c"
                    font.family: face.fontName
                    font.weight: Font.Light
                    font.pixelSize: 16 * face.u
                    font.letterSpacing: face.spacing(text, 1.5 * face.u)
                }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: face.showDate
            text: Qt.locale().toString(face.now, "dddd d MMMM").toUpperCase()
            color: "#9a9a9a"
            font.family: face.fontName
            font.weight: Font.Normal
            font.pixelSize: 13 * face.u
            font.letterSpacing: face.spacing(text, 3 * face.u)
        }
    }
}
