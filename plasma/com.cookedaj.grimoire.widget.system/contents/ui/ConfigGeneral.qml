/*
    WidgetL System settings.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    // Plasma hands every setting (and its default) to the page as cfg_<name>; each one needs a property here
    property string cfg_style
    property alias cfg_showGpu: showGpu.checked
    property alias cfg_showTemps: showTemps.checked
    property alias cfg_fahrenheit: fahrenheit.checked
    property alias cfg_backgroundOpacity: backgroundSlider.value
    property string cfg_styleDefault
    property bool cfg_showGpuDefault
    property bool cfg_showTempsDefault
    property bool cfg_fahrenheitDefault
    property int cfg_backgroundOpacityDefault

    Kirigami.FormLayout {
        QQC2.RadioButton {
            Kirigami.FormData.label: i18n("Draw readings as:")
            text: i18n("Thin bars")
            checked: cfg_style !== "sparkline"
            onToggled: if (checked) cfg_style = "bars"
        }
        QQC2.RadioButton {
            text: i18n("Sparklines of the last two minutes")
            checked: cfg_style === "sparkline"
            onToggled: if (checked) cfg_style = "sparkline"
        }
        QQC2.CheckBox {
            id: showGpu
            Kirigami.FormData.label: i18n("Show:")
            text: i18n("Graphics card")
        }
        QQC2.CheckBox {
            id: showTemps
            text: i18n("Temperatures")
        }
        QQC2.CheckBox {
            id: fahrenheit
            enabled: showTemps.checked
            text: i18n("In Fahrenheit")
        }
        QQC2.Slider {
            id: backgroundSlider
            Kirigami.FormData.label: i18n("Background:")
            from: 0
            to: 100
            stepSize: 5
        }
        QQC2.Label {
            text: backgroundSlider.value > 0 ? i18n("%1% dark", backgroundSlider.value) : i18n("None, only the readings")
        }
    }
}
