// SPDX-License-Identifier: GPL-3.0-or-later
// Username + password line. Enter logs in; a wrong password shakes the line.
import QtQuick

Column {
    id: form
    property int fieldWidth: 300
    property int align: Text.AlignHCenter
    property string user: userModel.lastUser !== "" ? userModel.lastUser : ""
    property color ink: "white"
    property color muted: "#9a9a9a"
    property color faint: "#5a5a5a"
    property color rest: "#6a6a6a"             // the password line without focus
    property string family: "IBM Plex Sans"
    property string prompt: ""                  // e.g. "> " in front of the fields (the console layout)
    property bool boxed: false                  // fields in an outlined box instead of on a line
    spacing: 14
    width: fieldWidth

    Text {
        width: parent.width
        horizontalAlignment: form.align
        text: form.prompt !== "" ? (form.user !== "" ? "login: " + form.user : "login:")
                                 : (form.user !== "" ? form.user.toUpperCase() : "LOG IN")
        color: form.muted
        font.family: form.family; font.pixelSize: form.prompt !== "" ? 14 : 12
        font.letterSpacing: form.prompt !== "" ? 0 : 5
    }

    Item {
        id: userBox
        visible: form.user === ""
        width: parent.width; height: visible ? 40 : 0
        TextInput {
            id: userInput
            anchors.fill: parent
            verticalAlignment: TextInput.AlignVCenter
            leftPadding: form.boxed ? 14 : form.prompt !== "" ? promptW.width : 0
            horizontalAlignment: form.align === Text.AlignHCenter ? TextInput.AlignHCenter : TextInput.AlignLeft
            color: form.ink; font.family: form.family; font.pixelSize: 16
            focus: form.user === ""                 // no last user: start in the name field
            KeyNavigation.tab: pw
            onAccepted: pw.forceActiveFocus()
        }
        Text {
            anchors.fill: parent; verticalAlignment: Text.AlignVCenter; horizontalAlignment: form.align
            leftPadding: userInput.leftPadding
            visible: userInput.text === ""; text: "Username"; color: form.faint
            font.family: form.family; font.pixelSize: 16
        }
        Text { id: promptU; visible: form.prompt !== ""; anchors.verticalCenter: parent.verticalCenter
               text: form.prompt; color: form.muted; font.family: form.family; font.pixelSize: 16 }
        Rectangle { visible: !form.boxed; anchors.bottom: parent.bottom; width: parent.width; height: 1
                    color: form.faint }
        Rectangle { visible: form.boxed; anchors.fill: parent; color: "transparent"; radius: 4
                    border.color: form.faint; border.width: 1 }
    }

    Item {
        id: line
        width: parent.width; height: 40
        TextInput {
            id: pw
            anchors.fill: parent
            verticalAlignment: TextInput.AlignVCenter
            leftPadding: form.boxed ? 14 : form.prompt !== "" ? promptW.width : 0
            horizontalAlignment: form.align === Text.AlignHCenter ? TextInput.AlignHCenter : TextInput.AlignLeft
            echoMode: TextInput.Password
            passwordCharacter: form.prompt !== "" ? "*" : "•"
            color: form.ink; font.family: form.family; font.pixelSize: 18; font.letterSpacing: 4
            focus: form.user !== ""
            onAccepted: form.submit()
        }
        Text {
            anchors.fill: parent; verticalAlignment: Text.AlignVCenter; horizontalAlignment: form.align
            leftPadding: pw.leftPadding
            visible: pw.text === ""
            text: keyboard.capsLock ? "Password  ·  Caps Lock is on" : "Password"
            color: form.faint; font.family: form.family; font.pixelSize: 16
        }
        Text { id: promptW; visible: form.prompt !== ""; anchors.verticalCenter: parent.verticalCenter
               text: form.prompt; color: form.ink; font.family: form.family; font.pixelSize: 16 }
        Rectangle {
            visible: !form.boxed
            anchors.bottom: parent.bottom; width: parent.width; height: 1
            color: pw.activeFocus ? form.ink : form.rest
            Behavior on color { ColorAnimation { duration: 200 } }
        }
        Rectangle {
            visible: form.boxed; anchors.fill: parent; color: "transparent"; radius: 4
            border.color: pw.activeFocus ? form.ink : form.faint; border.width: 1
            Behavior on border.color { ColorAnimation { duration: 200 } }
        }
        SequentialAnimation {
            id: shake
            loops: 2
            NumberAnimation { target: line; property: "x"; to: -8; duration: 50 }
            NumberAnimation { target: line; property: "x"; to: 8; duration: 50 }
            NumberAnimation { target: line; property: "x"; to: 0; duration: 50 }
        }
    }

    Text {
        id: message
        width: parent.width
        horizontalAlignment: form.align
        color: form.muted; font.family: form.family; font.pixelSize: 12
        text: ""
    }

    function submit() {
        const name = form.user !== "" ? form.user : userInput.text;
        message.text = "";
        sddm.login(name, pw.text, sessionModel.lastIndex);
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            pw.text = "";
            message.text = "Wrong password";
            shake.start();
            pw.forceActiveFocus();
        }
    }
}
