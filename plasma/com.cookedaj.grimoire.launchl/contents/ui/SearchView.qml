/*
    Search results: Grimoire's own entries (spells, quick actions, ">command") on top, then KRunner's merged
    results (apps, settings, files, calculator, unit conversion, ...) grouped by runner. One cursor runs through
    both so the arrow keys and Enter treat them as a single list.

    SPDX-FileCopyrightText: 2026 cookedaj
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick

Item {
    id: sv

    property var extras: []                  // [{name, description, icon, mask, run(), calc?, number?}]
    property int cursor: 0                   // < extraCount: that extra; otherwise the results list's current row
    readonly property int extraCount: extras.length
    readonly property int total: extraCount + results.count
    readonly property alias list: results
    // the calculator's answer: KRunner's own calculator row showing the same number is hidden under it
    readonly property real calcNumber: extraCount > 0 && extras[0].calc === true ? extras[0].number : NaN

    signal triggerExtra(var extra)
    signal triggerResult(int row)
    signal menuFor(int row, Item item, real x, real y)

    onExtrasChanged: {
        cursor = 0
        Qt.callLater(reset)                  // once the rows have seen the new calculator answer (hidden or not)
    }

    function reset() {                       // a new query: back to the top
        cursor = 0
        results.currentIndex = results.count > 0 ? Math.max(0, firstRow()) : -1
        sync()
    }

    // the first row that shows (not a hidden duplicate), or -1
    function firstRow(): int {
        for (let i = 0; i < results.count; i++) {
            if (!results.isSeparator(i)) {
                return i
            }
        }
        return -1
    }

    function sync() {
        if (cursor >= extraCount && results.count > 0) {
            if (results.currentIndex < 0 || results.currentIndex >= results.count
                    || results.isSeparator(results.currentIndex)) {
                results.currentIndex = Math.max(0, firstRow())
            }
            results.positionViewAtIndex(results.currentIndex, ListView.Contain)
        } else {
            if (extraCount > 0 || results.count === 0) {
                cursor = Math.min(cursor, Math.max(0, extraCount - 1))
            }
            results.currentIndex = results.count > 0 ? Math.max(0, firstRow()) : -1
            results.positionViewAtBeginning()
        }
    }

    function move(step: int) {
        if (total === 0) {
            return
        }
        results.keyboardNav = true
        const one = step > 0 ? 1 : -1
        for (let left = Math.abs(step); left > 0; left--) {
            if (cursor < extraCount) {
                if (one < 0 && cursor > 0) {
                    cursor--
                } else if (one > 0 && cursor + 1 < extraCount) {
                    cursor++
                } else if (one > 0 && firstRow() >= 0) {
                    cursor = extraCount
                    results.moveTo(firstRow())
                } else {
                    break
                }
            } else if (!results.move(one)) {         // at an end of the results
                if (one < 0 && extraCount > 0) {
                    cursor = extraCount - 1
                    results.positionViewAtBeginning()
                } else {
                    break
                }
            }
        }
    }

    function activate() {
        if (cursor < extraCount) {
            triggerExtra(extras[cursor])
        } else if (results.count > 0 && results.currentIndex >= 0) {
            triggerResult(results.currentIndex)
        }
    }

    EntryList {
        id: results
        anchors.fill: parent
        twoLine: true
        showCurrent: sv.cursor >= sv.extraCount
        model: launchl.runnerModel.count ? launchl.runnerModel.modelForRow(0) : null
        emptyText: sv.extraCount === 0 && !launchl.runnerModel.querying ? i18n("No matches") : ""
        hideNumber: sv.calcNumber
        onCountChanged: sv.sync()
        onActivated: i => sv.triggerResult(i)
        onHovered: i => sv.cursor = sv.extraCount        // the mouse moves the shared cursor too (the row is current)
        onMenuRequested: (i, item, x, y) => sv.menuFor(i, item, x, y)

        header: Column {
            width: results.width
            Item {
                width: parent.width
                height: sv.extraCount > 0 ? 30 : 0
                Text {
                    visible: sv.extraCount > 0
                    anchors.left: parent.left
                    anchors.leftMargin: 18
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 6
                    text: "GRIMOIRE"
                    color: launchl.ink.faint
                    font.family: launchl.ink.font
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 2
                }
            }
            Repeater {
                model: sv.extras
                delegate: EntryRow {
                    required property int index
                    required property var modelData
                    width: results.width
                    height: implicitHeight
                    icon: modelData.icon
                    maskIcon: modelData.mask === true
                    title: modelData.name
                    subtitle: modelData.description ?? ""
                    isCurrent: sv.cursor === index
                    outlined: results.keyboardNav
                    onEntered: {
                        results.keyboardNav = false
                        sv.cursor = index
                    }
                    onClicked: sv.triggerExtra(modelData)
                }
            }
        }
    }
}
