/*
    WidgetL Now Playing settings.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    // Plasma hands every setting (and its default) to the page as cfg_<name>; each one needs a property here
    property alias cfg_grayscaleCover: grayscaleCover.checked
    property alias cfg_showAlbum: showAlbum.checked
    property alias cfg_backgroundOpacity: backgroundSlider.value
    property bool cfg_grayscaleCoverDefault
    property bool cfg_showAlbumDefault
    property int cfg_backgroundOpacityDefault

    Kirigami.FormLayout {
        QQC2.CheckBox {
            id: grayscaleCover
            Kirigami.FormData.label: i18n("Cover:")
            text: i18n("In grayscale")
        }
        QQC2.CheckBox {
            id: showAlbum
            Kirigami.FormData.label: i18n("Show:")
            text: i18n("The album after the artist")
        }
        QQC2.Slider {
            id: backgroundSlider
            Kirigami.FormData.label: i18n("Background:")
            from: 0
            to: 100
            stepSize: 5
        }
        QQC2.Label {
            text: backgroundSlider.value > 0 ? i18n("%1% dark", backgroundSlider.value) : i18n("None, only the player")
        }
    }
}
