/*
    WidgetL System: CPU, memory, graphics card and temperatures in black and white, as thin bars or sparklines.
    Readings come from Plasma's own sensor service (ksystemstats, org.kde.ksysguard.sensors), the same one System
    Monitor uses, so the widget costs next to nothing. The drawing is Face.qml.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.ksysguard.sensors as Sensors

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground      // Face draws its own black panel
    preferredRepresentation: fullRepresentation
    toolTipMainText: i18n("System")
    toolTipSubText: i18n("CPU %1% · RAM %2%", Math.round(num(cpuSensor.value)), Math.round(num(ramSensor.value)))

    readonly property int rate: 2000
    readonly property int keep: 60                     // two minutes of history at one sample every 2 s

    property var cpuHistory: []
    property var ramHistory: []
    property var gpuHistory: []

    function num(v) {
        const n = Number(v);
        return v === undefined || v === null || v === "" || isNaN(n) ? -1 : n;
    }
    // the first sensor in the list that reports a number
    function first(list) {
        for (let i = 0; i < list.length; i++) {
            const n = num(list[i].value);
            if (n >= 0)
                return n;
        }
        return -1;
    }
    // the hottest of the cards that report a temperature
    function hottest(list) {
        let best = -1;
        for (let i = 0; i < list.length; i++)
            best = Math.max(best, num(list[i].value));
        return best;
    }
    function pushed(list, value) {
        const out = list.slice(-(keep - 1));
        out.push(Math.max(0, value));
        return out;
    }

    Sensors.Sensor { id: cpuSensor; sensorId: "cpu/all/usage"; updateRateLimit: root.rate }
    Sensors.Sensor { id: ramSensor; sensorId: "memory/physical/usedPercent"; updateRateLimit: root.rate }
    Sensors.Sensor { id: ramUsedSensor; sensorId: "memory/physical/used"; updateRateLimit: root.rate }
    Sensors.Sensor { id: ramTotalSensor; sensorId: "memory/physical/total"; updateRateLimit: 60000 }
    Sensors.Sensor { id: gpuSensor; sensorId: "gpu/all/usage"; updateRateLimit: root.rate }
    Sensors.Sensor { id: cpuTempAverage; sensorId: "cpu/all/averageTemperature"; updateRateLimit: root.rate }
    Sensors.Sensor { id: cpuTempMax; sensorId: "cpu/all/maximumTemperature"; updateRateLimit: root.rate }
    Sensors.Sensor { id: gpu0Temp; sensorId: "gpu/gpu0/temperature"; updateRateLimit: root.rate }
    Sensors.Sensor { id: gpu1Temp; sensorId: "gpu/gpu1/temperature"; updateRateLimit: root.rate }
    Sensors.Sensor { id: gpu2Temp; sensorId: "gpu/gpu2/temperature"; updateRateLimit: root.rate }
    Sensors.Sensor { id: gpu3Temp; sensorId: "gpu/gpu3/temperature"; updateRateLimit: root.rate }

    readonly property real ramUsedGb: num(ramUsedSensor.value) / 1073741824
    readonly property real ramTotalGb: num(ramTotalSensor.value) / 1073741824

    Timer {
        interval: root.rate
        running: Plasmoid.configuration.style === "sparkline"
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            root.cpuHistory = root.pushed(root.cpuHistory, root.num(cpuSensor.value));
            root.ramHistory = root.pushed(root.ramHistory, root.num(ramSensor.value));
            root.gpuHistory = root.pushed(root.gpuHistory, root.num(gpuSensor.value));
        }
    }

    fullRepresentation: Face {
        Layout.minimumWidth: 150
        Layout.minimumHeight: 90
        Layout.preferredWidth: implicitWidth
        Layout.preferredHeight: implicitHeight
        cpu: root.num(cpuSensor.value)
        ram: root.num(ramSensor.value)
        gpu: root.num(gpuSensor.value)
        ramDetail: root.ramUsedGb >= 0 && root.ramTotalGb > 0
                   ? i18nc("memory used of total", "%1 of %2 GB", root.ramUsedGb.toFixed(1), Math.round(root.ramTotalGb))
                   : ""
        cpuTemp: root.first([cpuTempAverage, cpuTempMax])
        gpuTemp: root.hottest([gpu0Temp, gpu1Temp, gpu2Temp, gpu3Temp])
        cpuHistory: root.cpuHistory
        ramHistory: root.ramHistory
        gpuHistory: root.gpuHistory
        style: Plasmoid.configuration.style
        showGpu: Plasmoid.configuration.showGpu
        showTemps: Plasmoid.configuration.showTemps
        fahrenheit: Plasmoid.configuration.fahrenheit
        backgroundOpacity: Plasmoid.configuration.backgroundOpacity
    }
}
