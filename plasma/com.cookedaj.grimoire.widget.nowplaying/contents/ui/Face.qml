/*
    WidgetL Now Playing: what the widget draws, in plain QtQuick so Grimoire can render the same file as its preview.
    main.qml feeds it the current MPRIS player and turns the button signals into player calls.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Item {
    id: face

    property bool hasPlayer: false
    property string title: ""
    property string artist: ""
    property string album: ""
    property string playerName: ""
    property url artUrl
    property bool playing: false
    property bool canControl: true
    property bool canPrevious: true
    property bool canNext: true
    property real position: 0               // seconds
    property real length: 0                 // seconds; 0 for streams
    property bool grayscaleCover: true
    property int backgroundOpacity: 80
    // optional: a component that draws the cover in grayscale (main.qml passes one built on MultiEffect; the
    // preview has none and shows the cover, or the note, as is)
    property Component coverEffect: null

    signal previous()
    signal playPause()
    signal next()

    readonly property real designWidth: 380
    readonly property real designHeight: 144
    implicitWidth: designWidth
    implicitHeight: designHeight

    readonly property real u: Math.max(0.3, Math.min(width / designWidth, height / designHeight))
    readonly property string fontName: "IBM Plex Sans"

    function clock(sec) {
        sec = Math.max(0, Math.floor(sec));
        const m = Math.floor(sec / 60), s = sec % 60;
        return m + ":" + (s < 10 ? "0" : "") + s;
    }

    Rectangle {
        anchors.fill: parent
        radius: 16 * face.u
        color: "#0b0b0b"
        opacity: face.backgroundOpacity / 100
        border.color: "#2a2a2a"
        border.width: face.backgroundOpacity > 0 ? 1 : 0
    }

    Item {
        anchors.fill: parent
        anchors.margins: 18 * face.u

        // the cover, or a note on a dark square when there's none
        Rectangle {
            id: coverBox
            width: parent.height
            height: width
            radius: 8 * face.u
            color: "#141414"
            border.color: "#222222"
            border.width: 1
            clip: true

            Glyph {
                visible: cover.status !== Image.Ready
                anchors.centerIn: parent
                width: parent.width * 0.42
                height: width
                name: "note"
                ink: "#555555"
                stroke: 1.2
            }
            Image {
                id: cover
                anchors.fill: parent
                anchors.margins: 1
                source: face.hasPlayer ? face.artUrl : ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: 256
                sourceSize.height: 256
                visible: status === Image.Ready && !(face.grayscaleCover && face.coverEffect)
            }
            Loader {
                anchors.fill: cover
                active: cover.status === Image.Ready && face.grayscaleCover && face.coverEffect !== null
                sourceComponent: face.coverEffect
                onLoaded: item.source = cover
            }
        }

        Item {
            anchors.left: coverBox.right
            anchors.leftMargin: 16 * face.u
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom

            Column {
                width: parent.width
                spacing: 2 * face.u

                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: face.hasPlayer ? (face.title || face.playerName) : qsTr("Nothing playing")
                    color: face.hasPlayer ? "#f2f2f2" : "#8c8c8c"
                    font.family: face.fontName
                    font.pixelSize: 16 * face.u
                }
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    visible: text !== ""
                    text: face.hasPlayer ? [face.artist, face.album].filter(x => x).join(" · ")
                                         : qsTr("Start music or a video in any app")
                    color: "#8c8c8c"
                    font.family: face.fontName
                    font.pixelSize: 12 * face.u
                }
            }

            // position: a 2 px track, with the times underneath
            Item {
                id: progress
                visible: face.hasPlayer && face.length > 0
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: controls.top
                anchors.bottomMargin: 8 * face.u
                height: 18 * face.u

                Rectangle {
                    width: parent.width
                    height: Math.max(2, 2 * face.u)
                    radius: height / 2
                    color: "#262626"
                }
                Rectangle {
                    width: parent.width * Math.max(0, Math.min(1, face.position / Math.max(1, face.length)))
                    height: Math.max(2, 2 * face.u)
                    radius: height / 2
                    color: "#f2f2f2"
                }
                Text {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    text: face.clock(face.position)
                    color: "#6f6f6f"
                    font.family: face.fontName
                    font.pixelSize: 10 * face.u
                    font.features: { "tnum": 1 }
                }
                Text {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    text: face.clock(face.length)
                    color: "#6f6f6f"
                    font.family: face.fontName
                    font.pixelSize: 10 * face.u
                    font.features: { "tnum": 1 }
                }
            }

            Row {
                id: controls
                visible: face.hasPlayer
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 14 * face.u

                Button {
                    width: 32 * face.u
                    height: width
                    anchors.verticalCenter: parent.verticalCenter
                    glyph: "previous"
                    label: qsTr("Previous")
                    enabled: face.canControl && face.canPrevious
                    onClicked: face.previous()
                }
                Button {
                    width: 40 * face.u
                    height: width
                    primary: true
                    glyph: face.playing ? "pause" : "play"
                    label: face.playing ? qsTr("Pause") : qsTr("Play")
                    enabled: face.canControl
                    onClicked: face.playPause()
                }
                Button {
                    width: 32 * face.u
                    height: width
                    anchors.verticalCenter: parent.verticalCenter
                    glyph: "next"
                    label: qsTr("Next")
                    enabled: face.canControl && face.canNext
                    onClicked: face.next()
                }
            }
        }
    }
}
