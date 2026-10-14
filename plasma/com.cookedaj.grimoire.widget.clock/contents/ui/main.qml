/*
    WidgetL Clock: big thin digits and the date, in black and white. The drawing is Face.qml; this file gives it
    the time (re-aligned to the second each tick) and the settings.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground      // Face draws its own black panel
    preferredRepresentation: fullRepresentation
    toolTipMainText: Qt.formatTime(now, Plasmoid.configuration.use24h ? "HH:mm" : "h:mm AP")
    toolTipSubText: Qt.locale().toString(now, Qt.locale().dateFormat(Locale.LongFormat))

    property date now: new Date()

    Timer {
        running: true
        repeat: true
        triggeredOnStart: true
        interval: 1000
        onTriggered: {
            root.now = new Date();
            interval = 1000 - root.now.getMilliseconds() + 20;      // tick just after the second changes
        }
    }

    fullRepresentation: Face {
        Layout.minimumWidth: 160
        Layout.minimumHeight: 70
        Layout.preferredWidth: implicitWidth
        Layout.preferredHeight: implicitHeight
        now: root.now
        use24h: Plasmoid.configuration.use24h
        showSeconds: Plasmoid.configuration.showSeconds
        showDate: Plasmoid.configuration.showDate
        backgroundOpacity: Plasmoid.configuration.backgroundOpacity
    }
}
