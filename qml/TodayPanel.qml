import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ScheduleTime.js" as ScheduleTime
import "Theme.js" as Theme

Window {
    id: popup
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    signal openItem(var entry)
    signal openCalendar()
    property var entries: []
    property string selectedEntryId: ""
    property real wheelRemainder: 0
    property bool wheelUsesPixels: false
    property bool animateSelection: false
    readonly property int featuredIndex: Math.max(0, entries.findIndex(entry => entry.id === selectedEntryId))
    property real highlightPosition: featuredIndex
    readonly property int rowHeight: 36
    readonly property int featuredHeight: 80
    readonly property int rowSpacing: 3
    readonly property int rowStride: rowHeight + rowSpacing
    readonly property int extraHeight: featuredHeight - rowHeight
    readonly property int listHeight: entries.length === 0 ? 62
        : featuredHeight + Math.min(2, entries.length - 1) * rowStride
    readonly property var placement: {
        let height = heading.implicitHeight + listHeight + footer.implicitHeight
            + 2 * column.spacing + 2 * column.anchors.margins + 2 * card.anchors.margins
        return visible ? desk.previewGeometry(Math.ceil(height)) : {x: 0, y: 0, width: 296, height: height}
    }
    x: placement.x
    y: placement.y
    width: placement.width
    height: placement.height

    function cardBounds() {
        let point = card.mapToGlobal(0, 0)
        return Qt.rect(point.x, point.y, card.width, card.height)
    }

    function grabCard(callback) { return card.grabToImage(callback) }

    Behavior on highlightPosition {
        enabled: popup.animateSelection
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
    }
    onFeaturedIndexChanged: if (agenda) agenda.revealSelection()

    function refreshEntries() {
        let current = cal.todayPreview()
        if (JSON.stringify(current) === JSON.stringify(entries)) return
        entries = current
        if (selectedEntryId && !entries.some(entry => entry.id === selectedEntryId))
            selectedEntryId = ""
    }

    function stepFeatured(event) {
        let usesPixels = event.pixelDelta.y !== 0
        let delta = usesPixels ? event.pixelDelta.y : event.angleDelta.y
        if (!delta || entries.length < 2) return
        if (wheelUsesPixels !== usesPixels || wheelRemainder * delta < 0)
            wheelRemainder = 0
        wheelUsesPixels = usesPixels
        wheelRemainder += delta
        wheelReset.restart()
        let threshold = usesPixels ? 44 : 120
        let steps = Math.trunc(wheelRemainder / threshold)
        if (!steps) return
        wheelRemainder -= steps * threshold
        let next = Math.max(0, Math.min(entries.length - 1, featuredIndex - steps))
        if (next === featuredIndex) return
        selectedEntryId = entries[next].id
    }
    onVisibleChanged: {
        if (visible) {
            selectedEntryId = ""
            wheelRemainder = 0
            refreshEntries()
            animateSelection = desk.motionEnabled
            if (desk.motionEnabled) entrance.restart()
        } else {
            animateSelection = false
            agenda.scrollTarget = 0
            entrance.stop()
            card.reveal = 1
        }
    }
    Connections {
        target: cal
        enabled: popup.visible
        function onTodayChanged() { popup.refreshEntries() }
    }
    Timer { interval: 15000; running: popup.visible; repeat: true; onTriggered: popup.refreshEntries() }
    Timer { id: wheelReset; interval: 280; onTriggered: popup.wheelRemainder = 0 }
    Shortcut { sequence: "Escape"; onActivated: desk.hidePreview() }

    component PreviewEntry: Button {
        id: row
        property var entry
        readonly property bool expanded: height >= popup.featuredHeight - 12
        readonly property bool overdue: entry.previewStatus === "overdue"
        readonly property string badge: overdue ? "逾期" : entry.kind === "deadline" ? "截止" : ""
        readonly property string timeLabel: {
            let start = entry.start
            if (!start) return ""
            if (expanded) {
                if (overdue && start.slice(0, 10) !== cal.todayDate)
                    return ScheduleTime.range(start, entry.end, true)
                return ScheduleTime.dayRange(start, entry.end, cal.todayDate)
            }
            if (overdue && start.slice(0, 10) !== cal.todayDate)
                return Qt.formatDate(new Date(start.slice(0, 10) + "T12:00"), "M/d")
            if (start.slice(0, 10) !== cal.todayDate) return "跨夜"
            return start.slice(11) || "当日"
        }
        readonly property string statusLabel: entry.previewStatus === "ongoing" ? "进行中"
            : entry.previewStatus === "next" ? "接下来" : entry.done ? "已完成" : ""
        leftPadding: expanded ? 12 : 5
        rightPadding: 8
        hoverEnabled: true
        Accessible.name: timeLabel + " " + (entry.title || "") + " " + badge + " " + (entry.location || "")
        onClicked: popup.openItem(entry)
        background: Rectangle {
            radius: Theme.controlRadius
            color: row.hovered ? "#10246352" : "transparent"
            border.color: row.visualFocus ? Theme.pine : "transparent"
        }
        contentItem: RowLayout {
            spacing: 7
            Label {
                visible: !row.expanded
                Layout.preferredWidth: 40
                text: row.timeLabel; color: Theme.muted; font.pixelSize: 11
                elide: Text.ElideRight
            }
            Rectangle {
                objectName: "todayColorMark"
                Layout.preferredWidth: 6
                Layout.preferredHeight: 6
                radius: 3
                color: Theme.eventAccent(row.entry)
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Label {
                    visible: row.expanded
                    Layout.fillWidth: true
                    text: row.statusLabel ? row.statusLabel + "  ·  " + row.timeLabel : row.timeLabel
                    color: Theme.pine; font.pixelSize: 11; font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Label {
                    Layout.fillWidth: true
                    text: row.entry.title || ""; textFormat: Text.PlainText; elide: Text.ElideRight
                    color: row.entry.done ? Theme.muted : Theme.ink
                    font.pixelSize: row.expanded ? 15 : 12
                    font.weight: row.expanded ? Font.DemiBold : Font.Normal
                    font.strikeout: !!row.entry.done
                }
                Label {
                    visible: row.expanded && !!text
                    Layout.fillWidth: true
                    text: row.entry.location || ""; textFormat: Text.PlainText; elide: Text.ElideRight
                    color: Theme.muted; font.pixelSize: 11
                }
            }
            Label {
                visible: !!row.badge
                text: row.badge; color: Theme.warning; font.pixelSize: 10
                padding: 4
                background: Rectangle { color: Theme.warningSurface; radius: 4 }
            }
        }
    }

    Item {
        anchors.fill: parent
        HoverHandler {
            objectName: "todayHover"
            onHoveredChanged: desk.hoverPreview(hovered)
        }
        WheelHandler {
            target: null
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: event => popup.stepFeatured(event)
        }
        GlassSurface {
            id: card
            objectName: "todayGlass"
            anchors.fill: parent; anchors.margins: 8
            radius: Theme.sheetRadius
            topTint: "#e6fffefa"
            sheenTint: "#cef9fcf7"
            bottomTint: "#e0dcebe2"
            SurfaceShadow { radius: card.radius; spread: 5 }
            property real reveal: 1
            opacity: reveal
            transform: Translate {
                x: (1-card.reveal) * (desk.previewEdge === "left" ? -6 : desk.previewEdge === "right" ? 6 : 0)
                y: (1-card.reveal) * (desk.previewEdge === "top" ? -6 : desk.previewEdge === "bottom" ? 6 : 0)
            }
            NumberAnimation {
                id: entrance
                target: card; property: "reveal"; from: 0; to: 1; duration: 150
                easing.type: Easing.OutCubic
            }
            ColumnLayout {
                id: column
                anchors.fill: parent; anchors.margins: 12
                spacing: 8
                RowLayout {
                    id: heading
                    Layout.fillWidth: true
                    spacing: 9
                    Label { text: "今日"; color: Theme.ink; font.pixelSize: 19; font.weight: Font.DemiBold }
                    Label {
                        Layout.fillWidth: true
                        text: ScheduleTime.dateLabel(cal.todayDate)
                        color: Theme.muted; font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                }
                Item {
                    id: agenda
                    objectName: "todayList"
                    readonly property int count: popup.entries.length
                    readonly property int contentHeight: count > 0 ? count * popup.rowStride
                        - popup.rowSpacing + popup.extraHeight : 0
                    property real scrollTarget: 0
                    property real scrollOffset: scrollTarget
                    readonly property int firstRow: Math.max(0, Math.floor((scrollOffset - popup.extraHeight) / popup.rowStride))
                    readonly property int lastRow: Math.min(count - 1, Math.ceil((scrollOffset + height) / popup.rowStride))
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 0
                    clip: true
                    function revealSelection() {
                        let top = popup.featuredIndex * popup.rowStride
                        let bottom = top + Math.min(popup.featuredHeight, height)
                        let offset = Math.max(bottom - height, Math.min(scrollTarget, top))
                        scrollTarget = Math.max(0, Math.min(offset, contentHeight - height))
                    }
                    onHeightChanged: revealSelection()
                    onContentHeightChanged: revealSelection()
                    Behavior on scrollOffset {
                        enabled: popup.animateSelection
                        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
                    }
                    Label {
                        anchors.centerIn: parent
                        visible: agenda.count === 0
                        text: "今天暂无安排"
                        color: Theme.muted
                        font.pixelSize: 12
                    }
                    Item {
                        y: -agenda.scrollOffset
                        width: parent.width
                        height: agenda.contentHeight
                        Rectangle {
                            objectName: "todayHighlight"
                            visible: agenda.count > 0
                            width: parent.width
                            height: popup.featuredHeight
                            y: popup.highlightPosition * popup.rowStride
                            radius: Theme.controlRadius
                            color: Theme.tint
                            border.color: Theme.line
                            Rectangle {
                                anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 5 }
                                width: 2; radius: 1; color: Theme.pine
                            }
                        }
                        Repeater {
                            model: Math.max(0, agenda.lastRow - agenda.firstRow + 1)
                            delegate: PreviewEntry {
                                required property int index
                                readonly property int entryIndex: agenda.firstRow + index
                                readonly property real distance: entryIndex - popup.highlightPosition
                                objectName: "todayEntry"
                                width: agenda.width
                                y: entryIndex * popup.rowStride + popup.extraHeight * Math.max(0, Math.min(1, distance))
                                height: popup.rowHeight + popup.extraHeight * Math.max(0, 1 - Math.abs(distance))
                                entry: popup.entries[entryIndex] || ({})
                            }
                        }
                    }
                }
                ColumnLayout {
                    id: footer
                    Layout.fillWidth: true
                    spacing: 4
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.line }
                    RowLayout {
                        Layout.fillWidth: true
                        PlanButton {
                            objectName: "todayOpenWeek"
                            quiet: true
                            implicitHeight: 28
                            text: "打开周历  ›"
                            onClicked: popup.openCalendar()
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            visible: agenda.count > 1
                            text: (popup.featuredIndex + 1) + " / " + agenda.count
                            color: Theme.muted; font.pixelSize: 11
                        }
                    }
                }
            }
        }
    }
}
