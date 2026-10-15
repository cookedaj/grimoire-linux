/*
    WidgetL Weather settings: find a place by name (Open-Meteo's geocoding, only when you press Search) or type its
    coordinates, and pick the units.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: page

    // Plasma hands every setting (and its default) to the page as cfg_<name>; each one needs a property here
    property alias cfg_placeName: placeName.text
    property alias cfg_latitude: latitude.text
    property alias cfg_longitude: longitude.text
    property string cfg_units
    property alias cfg_showForecast: showForecast.checked
    property alias cfg_backgroundOpacity: backgroundSlider.value
    property string cfg_placeNameDefault
    property string cfg_latitudeDefault
    property string cfg_longitudeDefault
    property string cfg_unitsDefault
    property bool cfg_showForecastDefault
    property int cfg_backgroundOpacityDefault

    property var results: []
    property string searchNote: ""
    property var pending: null            // the search in flight; an older one's answer is ignored

    // Open-Meteo's answer is untrusted and these labels detect rich text: no markup, no control characters, short
    function plain(v) {
        return String(v === undefined || v === null ? "" : v).replace(/[<>\u0000-\u001f\u007f]/g, "").slice(0, 80);
    }

    function search() {
        const q = query.text.trim();
        if (q.length < 2) {
            searchNote = i18n("Type at least two letters.");
            return;
        }
        searchNote = i18n("Searching…");
        results = [];
        if (pending) {
            const old = pending;
            pending = null;
            old.abort();
        }
        const req = new XMLHttpRequest();
        pending = req;
        req.onreadystatechange = function () {
            if (req.readyState !== XMLHttpRequest.DONE || req !== page.pending)
                return;
            page.pending = null;
            page.searchTimeout.stop();
            try {
                if (req.status !== 200)
                    throw new Error("HTTP " + req.status);
                const answer = JSON.parse(req.responseText).results || [];
                const found = (Array.isArray(answer) ? answer : []).filter(r => r && page.plain(r.name) !== ""
                    && isFinite(Number(r.latitude)) && Math.abs(Number(r.latitude)) <= 90
                    && isFinite(Number(r.longitude)) && Math.abs(Number(r.longitude)) <= 180).slice(0, 8);
                page.results = found.map(r => ({
                    name: page.plain(r.name),
                    where: [page.plain(r.admin1), page.plain(r.country)].filter(x => x).join(", "),
                    latitude: Number(r.latitude),
                    longitude: Number(r.longitude),
                }));
                page.searchNote = found.length ? "" : i18n("No place called \"%1\" found.", q);
            } catch (e) {
                page.searchNote = i18n("Couldn't search: %1", req.status === 0 ? i18n("no connection") : String(e.message || e));
            }
        };
        req.open("GET", "https://geocoding-api.open-meteo.com/v1/search?count=8&format=json&language="
                 + encodeURIComponent(Qt.locale().name.split("_")[0]) + "&name=" + encodeURIComponent(q.slice(0, 100)));
        req.send();
        page.searchTimeout.restart();
    }

    // QML's XMLHttpRequest has no timeout of its own (a property, so the page's content stays the FormLayout)
    property Timer searchTimeout: Timer {
        interval: 20 * 1000
        onTriggered: if (page.pending) page.pending.abort()
    }

    Kirigami.FormLayout {
        RowLayout {
            Kirigami.FormData.label: i18n("Find a place:")
            QQC2.TextField {
                id: query
                Layout.preferredWidth: Kirigami.Units.gridUnit * 14
                placeholderText: i18n("City or town")
                onAccepted: page.search()
            }
            QQC2.Button {
                text: i18n("Search")
                icon.name: "search"
                onClicked: page.search()
            }
        }
        QQC2.Label {
            visible: page.searchNote !== ""
            text: page.searchNote
            textFormat: Text.PlainText
            opacity: 0.7
        }
        ColumnLayout {
            visible: page.results.length > 0
            spacing: 0
            Repeater {
                model: page.results
                QQC2.ItemDelegate {
                    required property var modelData
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 20
                    text: modelData.where ? i18nc("place, region and country", "%1 · %2", modelData.name, modelData.where)
                                          : modelData.name
                    onClicked: {
                        placeName.text = modelData.where ? i18nc("place and country", "%1, %2", modelData.name,
                                                                 modelData.where.split(", ").pop())
                                                         : modelData.name;
                        latitude.text = Number(modelData.latitude).toFixed(4);
                        longitude.text = Number(modelData.longitude).toFixed(4);
                        page.results = [];
                        page.searchNote = "";
                    }
                }
            }
        }

        Item {
            Kirigami.FormData.isSection: true
        }
        QQC2.TextField {
            id: placeName
            Kirigami.FormData.label: i18n("Name on the widget:")
            Layout.preferredWidth: Kirigami.Units.gridUnit * 14
        }
        QQC2.TextField {
            id: latitude
            Kirigami.FormData.label: i18n("Latitude:")
            Layout.preferredWidth: Kirigami.Units.gridUnit * 8
            placeholderText: i18n("e.g. 38.7223")
            validator: DoubleValidator { bottom: -90; top: 90; notation: DoubleValidator.StandardNotation; locale: "C" }
        }
        QQC2.TextField {
            id: longitude
            Kirigami.FormData.label: i18n("Longitude:")
            Layout.preferredWidth: Kirigami.Units.gridUnit * 8
            placeholderText: i18n("e.g. -9.1393")
            validator: DoubleValidator { bottom: -180; top: 180; notation: DoubleValidator.StandardNotation; locale: "C" }
        }

        QQC2.RadioButton {
            Kirigami.FormData.label: i18n("Units:")
            text: i18n("°C and km/h")
            checked: cfg_units !== "imperial"
            onToggled: if (checked) cfg_units = "metric"
        }
        QQC2.RadioButton {
            text: i18n("°F and mph")
            checked: cfg_units === "imperial"
            onToggled: if (checked) cfg_units = "imperial"
        }
        QQC2.CheckBox {
            id: showForecast
            Kirigami.FormData.label: i18n("Show:")
            text: i18n("The next five days")
        }
        QQC2.Slider {
            id: backgroundSlider
            Kirigami.FormData.label: i18n("Background:")
            from: 0
            to: 100
            stepSize: 5
        }
        QQC2.Label {
            text: backgroundSlider.value > 0 ? i18n("%1% dark", backgroundSlider.value) : i18n("None, only the weather")
        }
        QQC2.Label {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            wrapMode: Text.WordWrap
            opacity: 0.7
            text: i18n("Weather data by Open-Meteo.com (CC BY 4.0). Only the place you search for and the coordinates you pick are sent; your location is never looked up.")
        }
    }
}
