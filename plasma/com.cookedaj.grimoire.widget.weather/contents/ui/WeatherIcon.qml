/*
    Monochrome line icons for WidgetL Weather, drawn on a 24x24 grid from an Open-Meteo (WMO) weather code.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Canvas {
    id: icon

    property int code: 0
    property bool day: true
    property color ink: "#f2f2f2"
    property real stroke: 1.5             // in grid units

    // clear, partly, cloud, fog, drizzle, rain, snow, thunder
    readonly property string kind: {
        if (code <= 0) return "clear";
        if (code <= 2) return "partly";
        if (code === 3) return "cloud";
        if (code === 45 || code === 48) return "fog";
        if (code >= 51 && code <= 57) return "drizzle";
        if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "rain";
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow";
        if (code >= 95) return "thunder";
        return "cloud";
    }

    onKindChanged: requestPaint()
    onDayChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    function cloud(ctx) {
        ctx.beginPath();
        ctx.moveTo(7, 19);
        ctx.bezierCurveTo(4.6, 19, 3, 17.3, 3, 15.2);
        ctx.bezierCurveTo(3, 13.1, 4.7, 11.4, 6.9, 11.4);
        ctx.bezierCurveTo(7.6, 8.5, 10.1, 6.5, 13, 6.5);
        ctx.bezierCurveTo(16.4, 6.5, 19, 9.1, 19.1, 12.3);
        ctx.bezierCurveTo(20.6, 12.8, 21.5, 14.2, 21.5, 15.7);
        ctx.bezierCurveTo(21.5, 17.5, 20, 19, 18.2, 19);
        ctx.closePath();
    }

    function sun(ctx, cx, cy, r, rays) {
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, 2 * Math.PI);
        ctx.stroke();
        for (let i = 0; i < 8; i++) {
            const a = i * Math.PI / 4;
            ctx.beginPath();
            ctx.moveTo(cx + Math.cos(a) * (r + rays * 0.45), cy + Math.sin(a) * (r + rays * 0.45));
            ctx.lineTo(cx + Math.cos(a) * (r + rays), cy + Math.sin(a) * (r + rays));
            ctx.stroke();
        }
    }

    function moon(ctx, cx, cy, r) {
        // a crescent: the circle's outline with a smaller offset circle cut out, and that circle's edge inside
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, 2 * Math.PI);
        ctx.stroke();
        ctx.globalCompositeOperation = "destination-out";
        ctx.beginPath();
        ctx.arc(cx + r * 0.55, cy - r * 0.45, r * 0.8, 0, 2 * Math.PI);
        ctx.fill();
        ctx.restore();
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, 2 * Math.PI);
        ctx.clip();
        ctx.beginPath();
        ctx.arc(cx + r * 0.55, cy - r * 0.45, r * 0.8, 0, 2 * Math.PI);
        ctx.stroke();
        ctx.restore();
    }

    // the cloud, shrunk into the top of the grid to leave room for rain, snow or a bolt below
    function smallCloud(ctx) {
        ctx.save();
        ctx.translate(2.4, -2.2);
        ctx.scale(0.8, 0.8);
        ctx.lineWidth = icon.stroke / 0.8;
        cloud(ctx);
        ctx.stroke();
        ctx.restore();
    }

    onPaint: {
        const ctx = getContext("2d");
        ctx.reset();
        const s = Math.min(width, height) / 24;
        ctx.translate((width - 24 * s) / 2, (height - 24 * s) / 2);
        ctx.scale(s, s);
        ctx.strokeStyle = icon.ink;
        ctx.fillStyle = icon.ink;
        ctx.lineWidth = icon.stroke;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        switch (kind) {
        case "clear":
            if (day)
                sun(ctx, 12, 12, 4.2, 4.6);
            else
                moon(ctx, 12, 12.5, 7);
            break;
        case "partly":
            if (day)
                sun(ctx, 8.5, 8.5, 3, 3.2);
            else
                moon(ctx, 8.5, 8.5, 4.6);
            ctx.save();                                   // the cloud hides what's behind it
            ctx.translate(2.5, 2.2);
            ctx.scale(0.85, 0.85);
            ctx.lineWidth = icon.stroke / 0.85;
            ctx.globalCompositeOperation = "destination-out";
            cloud(ctx);
            ctx.fill();
            ctx.globalCompositeOperation = "source-over";
            cloud(ctx);
            ctx.stroke();
            ctx.restore();
            break;
        case "cloud":
            cloud(ctx);
            ctx.stroke();
            break;
        case "fog":
            smallCloud(ctx);
            for (const [x0, x1, y] of [[4, 20, 17.5], [6, 18, 20.5]]) {
                ctx.beginPath();
                ctx.moveTo(x0, y);
                ctx.lineTo(x1, y);
                ctx.stroke();
            }
            break;
        case "drizzle":
            smallCloud(ctx);
            for (const x of [8.5, 12.5, 16.5]) {
                ctx.beginPath();
                ctx.arc(x - 0.6, 19.5, 0.35, 0, 2 * Math.PI);
                ctx.fill();
                ctx.beginPath();
                ctx.arc(x - 1.4, 22, 0.35, 0, 2 * Math.PI);
                ctx.fill();
            }
            break;
        case "rain":
            smallCloud(ctx);
            for (const x of [8.5, 12.5, 16.5]) {
                ctx.beginPath();
                ctx.moveTo(x, 17.5);
                ctx.lineTo(x - 1.6, 21.5);
                ctx.stroke();
            }
            break;
        case "snow":
            smallCloud(ctx);
            for (const [x, y] of [[8, 18.5], [12.5, 20.5], [17, 18.5]]) {
                for (let i = 0; i < 3; i++) {
                    const a = i * Math.PI / 3;
                    ctx.beginPath();
                    ctx.moveTo(x - Math.cos(a) * 1.4, y - Math.sin(a) * 1.4);
                    ctx.lineTo(x + Math.cos(a) * 1.4, y + Math.sin(a) * 1.4);
                    ctx.stroke();
                }
            }
            break;
        case "thunder":
            smallCloud(ctx);
            ctx.beginPath();
            ctx.moveTo(13.2, 15.5);
            ctx.lineTo(10.5, 19.5);
            ctx.lineTo(13.5, 19.5);
            ctx.lineTo(11, 23);
            ctx.stroke();
            break;
        }
    }
}
