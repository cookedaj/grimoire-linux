/*
    WidgetL Clock settings.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    // Plasma hands every setting (and its default) to the page as cfg_<name>; each one needs a property here
    property alias cfg_use24h: use24h.checked
    property alias cfg_showSeconds: showSeconds.checked
    property alias cfg_showDate: showDate.checked
    property alias cfg_backgroundOpacity: backgroundSlider.value
    property bool cfg_use24hDefault
    property bool cfg_showSecondsDefault
    property bool cfg_showDateDefault
    property int cfg_backgroundOpacityDefault

    Kirigami.FormLayout {
        QQC2.CheckBox {
            id: use24h
            Kirigami.FormData.label: i18n("Time:")
            text: i18n("24-hour clock")
        }
        QQC2.CheckBox {
            id: showSeconds
            text: i18n("Show seconds")
        }
        QQC2.CheckBox {
            id: showDate
            text: i18n("Show the date")
        }
        QQC2.Slider {
            id: backgroundSlider
            Kirigami.FormData.label: i18n("Background:")
            from: 0
            to: 100
            stepSize: 5
        }
        QQC2.Label {
            text: backgroundSlider.value > 0 ? i18n("%1% dark", backgroundSlider.value) : i18n("None, only the digits")
        }
    }
}
