/*
    Line glyphs for WidgetL Now Playing (previous, play, pause, next, a note), drawn on a 24x24 grid.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Canvas {
    id: glyph

    property string name: "play"
    property color ink: "#f2f2f2"
    property real stroke: 1.5

    onNameChanged: requestPaint()
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        const ctx = getContext("2d");
        ctx.reset();
        const s = Math.min(width, height) / 24;
        ctx.translate((width - 24 * s) / 2, (height - 24 * s) / 2);
        ctx.scale(s, s);
        ctx.strokeStyle = glyph.ink;
        ctx.lineWidth = glyph.stroke;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.beginPath();
        switch (name) {
        case "play":
            ctx.moveTo(8, 5.5);
            ctx.lineTo(18.5, 12);
            ctx.lineTo(8, 18.5);
            ctx.closePath();
            break;
        case "pause":
            ctx.moveTo(9, 6);
            ctx.lineTo(9, 18);
            ctx.moveTo(15, 6);
            ctx.lineTo(15, 18);
            break;
        case "next":
            ctx.moveTo(6.5, 6.5);
            ctx.lineTo(14.5, 12);
            ctx.lineTo(6.5, 17.5);
            ctx.closePath();
            ctx.moveTo(17.5, 6.5);
            ctx.lineTo(17.5, 17.5);
            break;
        case "previous":
            ctx.moveTo(17.5, 6.5);
            ctx.lineTo(9.5, 12);
            ctx.lineTo(17.5, 17.5);
            ctx.closePath();
            ctx.moveTo(6.5, 6.5);
            ctx.lineTo(6.5, 17.5);
            break;
        case "note":
            ctx.moveTo(9.5, 17);
            ctx.lineTo(9.5, 5.5);
            ctx.lineTo(18.5, 4);
            ctx.lineTo(18.5, 15.5);
            ctx.moveTo(9.5, 9);
            ctx.lineTo(18.5, 7.5);
            ctx.stroke();
            ctx.beginPath();
            ctx.ellipse(4.5, 15, 5, 4);
            ctx.stroke();
            ctx.beginPath();
            ctx.ellipse(13.5, 13.5, 5, 4);
            break;
        }
        ctx.stroke();
    }
}
