/*
    One reading of WidgetL System: a label, the value, and a thin bar or a sparkline of the last minutes.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Item {
    id: metric

    property real u: 1
    property string label
    property real value: -1             // percent; below 0 = not available
    property string detail
    property var history: []
    property bool sparkline: false

    readonly property bool known: value >= 0 && !isNaN(value)
    readonly property real clamped: known ? Math.max(0, Math.min(100, value)) : 0

    Text {
        id: name
        text: metric.label
        color: "#6f6f6f"
        font.family: "IBM Plex Sans"
        font.pixelSize: 11 * metric.u
        font.letterSpacing: 2 * metric.u
        anchors.baseline: number.baseline
    }
    Text {
        text: metric.detail
        visible: metric.known && metric.detail !== ""
        color: "#6f6f6f"
        font.family: "IBM Plex Sans"
        font.pixelSize: 11 * metric.u
        anchors.baseline: number.baseline
        anchors.left: name.right
        anchors.leftMargin: 10 * metric.u
    }
    Text {
        id: number
        anchors.right: parent.right
        text: metric.known ? Math.round(metric.value) + "%" : "–"
        color: "#f2f2f2"
        font.family: "IBM Plex Sans"
        font.weight: Font.Light
        font.pixelSize: 17 * metric.u
        font.features: { "tnum": 1 }
    }

    // bars: a 2 px track with the value filled in white
    Item {
        visible: !metric.sparkline
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: number.bottom
        anchors.topMargin: 5 * metric.u
        height: Math.max(2, 2 * metric.u)

        Rectangle {
            anchors.fill: parent
            color: "#262626"
            radius: height / 2
        }
        Rectangle {
            width: parent.width * metric.clamped / 100
            height: parent.height
            color: "#f2f2f2"
            radius: height / 2
            Behavior on width {
                NumberAnimation { duration: 400; easing.type: Easing.OutCubic }
            }
        }
    }

    // sparkline: the history as a thin white line over a faint fill, newest on the right
    Canvas {
        id: spark
        visible: metric.sparkline
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: number.bottom
        anchors.topMargin: 4 * metric.u
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10 * metric.u

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            ctx.strokeStyle = "#262626";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(0, height - 0.5);
            ctx.lineTo(width, height - 0.5);
            ctx.stroke();
            const h = metric.history || [];
            if (h.length < 2)
                return;
            const keep = 60;
            const pts = h.slice(-keep);
            const step = width / (keep - 1);
            const x0 = width - (pts.length - 1) * step;
            const yOf = v => height - 1 - (Math.max(0, Math.min(100, v)) / 100) * (height - 2);
            ctx.beginPath();
            ctx.moveTo(x0, height);
            for (let i = 0; i < pts.length; i++)
                ctx.lineTo(x0 + i * step, yOf(pts[i]));
            ctx.lineTo(width, height);
            ctx.closePath();
            ctx.fillStyle = Qt.rgba(1, 1, 1, 0.07);
            ctx.fill();
            ctx.beginPath();
            for (let i = 0; i < pts.length; i++) {
                if (i === 0)
                    ctx.moveTo(x0, yOf(pts[0]));
                else
                    ctx.lineTo(x0 + i * step, yOf(pts[i]));
            }
            ctx.strokeStyle = "#f2f2f2";
            ctx.lineWidth = Math.max(1, 1.4 * metric.u);
            ctx.lineJoin = "round";
            ctx.stroke();
        }
    }

    onHistoryChanged: if (sparkline) spark.requestPaint()
    onSparklineChanged: if (sparkline) spark.requestPaint()
    onWidthChanged: if (sparkline) spark.requestPaint()
    onHeightChanged: if (sparkline) spark.requestPaint()
}
