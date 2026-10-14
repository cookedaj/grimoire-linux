/*
    WidgetL Weather: the current weather and the next days from Open-Meteo (no account, no key), drawn in black and
    white with line icons. The place is one you pick in the settings (a city search or latitude/longitude); nothing
    looks up where you are on its own. It refreshes every 30 minutes, and 5 minutes after a failed try.
    The drawing is Face.qml.

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
    toolTipMainText: Plasmoid.configuration.placeName || i18n("Weather")
    toolTipSubText: note

    readonly property real latitude: parseFloat(Plasmoid.configuration.latitude)
    readonly property real longitude: parseFloat(Plasmoid.configuration.longitude)
    readonly property bool placeSet: !isNaN(latitude) && !isNaN(longitude)
                                     && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180
    readonly property bool imperial: Plasmoid.configuration.units === "imperial"

    property var current: null            // Open-Meteo's "current" block of the last good answer
    property var days: []
    property string note: ""
    property string error: ""
    property date fetched

    function url() {
        let u = "https://api.open-meteo.com/v1/forecast?latitude=" + latitude.toFixed(4)
            + "&longitude=" + longitude.toFixed(4)
            + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day"
            + "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=6";
        if (imperial)
            u += "&temperature_unit=fahrenheit&wind_speed_unit=mph";
        return u;
    }

    function dayName(iso) {
        const p = String(iso).split("-");
        return Qt.locale().toString(new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2])), "ddd");
    }

    function fetch() {
        if (!placeSet) {
            current = null;
            days = [];
            note = "";
            return;
        }
        const req = new XMLHttpRequest();
        const wanted = url();
        req.onreadystatechange = function () {
            if (req.readyState !== XMLHttpRequest.DONE)
                return;
            if (wanted !== url())
                return;                                   // the place or units changed meanwhile
            try {
                if (req.status !== 200)
                    throw new Error("HTTP " + req.status);
                const data = JSON.parse(req.responseText);
                const d = data.daily;
                const list = [];
                for (let i = 1; i < d.time.length && list.length < 5; i++)
                    list.push({name: dayName(d.time[i]), code: d.weather_code[i],
                               high: d.temperature_2m_max[i], low: d.temperature_2m_min[i]});
                current = data.current;
                days = list;
                error = "";
                fetched = new Date();
                note = i18n("Updated %1", Qt.formatTime(fetched, Qt.locale().timeFormat(Locale.ShortFormat)));
                refresh.interval = 30 * 60 * 1000;
            } catch (e) {
                error = req.status === 0 ? i18n("Can't reach Open-Meteo right now.")
                                         : i18n("Open-Meteo didn't answer as expected (%1).", String(e.message || e));
                note = current ? i18n("Offline · from %1", Qt.formatTime(fetched, Qt.locale().timeFormat(Locale.ShortFormat))) : "";
                refresh.interval = 5 * 60 * 1000;
            }
            refresh.restart();
        };
        req.open("GET", wanted);
        req.send();
    }

    Timer {
        id: refresh
        interval: 30 * 60 * 1000
        repeat: true
        running: root.placeSet
        onTriggered: root.fetch()
    }
    Timer {                                               // settings often change several keys at once
        id: soon
        interval: 300
        onTriggered: root.fetch()
    }
    Connections {
        target: Plasmoid.configuration
        function onLatitudeChanged() { soon.restart(); }
        function onLongitudeChanged() { soon.restart(); }
        function onUnitsChanged() { soon.restart(); }
    }
    Component.onCompleted: fetch()

    fullRepresentation: Face {
        Layout.minimumWidth: 170
        Layout.minimumHeight: 80
        Layout.preferredWidth: implicitWidth
        Layout.preferredHeight: implicitHeight
        hasData: root.current !== null
        message: !root.placeSet ? i18n("Pick a place in the widget's settings: right-click, Configure.")
                                : (root.error || i18n("Loading the weather…"))
        note: root.note
        place: Plasmoid.configuration.placeName
        temperature: root.current ? root.current.temperature_2m : 0
        feelsLike: root.current ? root.current.apparent_temperature : 0
        code: root.current ? root.current.weather_code : 0
        isDay: root.current ? root.current.is_day === 1 : true
        wind: root.current ? root.current.wind_speed_10m : 0
        windUnit: root.imperial ? i18nc("wind speed unit", "mph") : i18nc("wind speed unit", "km/h")
        humidity: root.current ? root.current.relative_humidity_2m : 0
        days: root.days
        showForecast: Plasmoid.configuration.showForecast
        backgroundOpacity: Plasmoid.configuration.backgroundOpacity
    }
}
