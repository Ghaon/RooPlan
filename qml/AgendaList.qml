import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "ScheduleTime.js" as ScheduleTime
import "Theme.js" as Theme

ListView {
    id: agenda
    property string day: ""
    property var overdue: []
    property var entries: []
    property string emptyText: "当天暂无安排"
    property bool showDates: false
    property bool hideRepeatedLocation: false
    property real trailingSpace: 0
    property string highlightId: ""
    signal openItem(var entry)
    model: overdue.concat(entries)
    clip: true
    spacing: 2
    footer: Item { height: agenda.trailingSpace }
    ScrollBar.vertical: ScrollBar {}
    Column {
        anchors.centerIn: parent
        visible: agenda.count === 0 && !!agenda.emptyText
        spacing: 9
        Label { anchors.horizontalCenter: parent.horizontalCenter; text: agenda.emptyText; color: Theme.muted; font.pixelSize: 12 }
    }
    delegate: Column {
        id: row
        required property var modelData
        required property int index
        property bool late: index < agenda.overdue.length
        width: ListView.view.width
        spacing: 6
        Label {
            visible: (row.late && row.index === 0) || (agenda.overdue.length > 0 && row.index === agenda.overdue.length)
            text: row.late ? "已过期未完成" : "今天"
            color: row.late ? "#8a532b" : "#516651"
            font.bold: true
        }
        Button {
            id: agendaButton
            objectName: "agendaEntry"
            width: parent.width
            implicitHeight: Math.max(46, details.implicitHeight + 16)
            padding: 9
            hoverEnabled: true
            Accessible.name: details.summary + " " + row.modelData.title + (details.location ? " " + details.location : "")
            onClicked: agenda.openItem(row.modelData)
            background: Rectangle {
                radius: Theme.controlRadius
                border.color: agendaButton.visualFocus ? Theme.pine : "transparent"
                color: agendaButton.hovered || agendaButton.visualFocus || row.modelData.id === agenda.highlightId
                    ? Theme.tint : row.late ? Theme.warningSurface
                    : agenda.showDates ? Theme.field : "transparent"
                Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
                Rectangle {
                    visible: !agendaButton.hovered && !agendaButton.visualFocus && !row.late
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 9; rightMargin: 9 }
                    height: 1
                    color: Theme.gridLine
                }
            }
            contentItem: RowLayout {
                id: details
                property var entry: row.modelData
                readonly property string location: {
                    let value = (entry.location || "").trim()
                    if (!agenda.hideRepeatedLocation || !value) return value
                    let title = entry.title.replace(/\s+/g, "").toLowerCase()
                    return title.includes(value.replace(/\s+/g, "").toLowerCase()) ? "" : value
                }
                property string summary: (entry.kind === "deadline" ? "截止 " : "")
                    + ScheduleTime.range(entry.start, entry.end, row.late || agenda.showDates)
                readonly property bool longRange: row.late || agenda.showDates
                    || (!!entry.end && entry.start.slice(0, 10) !== entry.end.slice(0, 10))
                spacing: 10
                Rectangle {
                    objectName: "agendaColorMark"
                    Layout.preferredWidth: 3
                    Layout.preferredHeight: 22
                    radius: 1.5
                    color: Theme.eventAccent(row.modelData)
                }
                Label {
                    visible: !details.longRange
                    Layout.preferredWidth: 78
                    Layout.alignment: Qt.AlignTop
                    text: details.summary
                    color: details.entry.kind === "deadline" ? Theme.warning : Theme.muted
                    font.pixelSize: 11
                    topPadding: 2
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    Label { Layout.fillWidth: true; text: row.modelData.title; textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere; font.pixelSize: 14; font.weight: Font.DemiBold; font.strikeout: row.modelData.done; color: Theme.ink }
                    Label { visible: details.longRange; Layout.fillWidth: true; text: details.summary; wrapMode: Text.Wrap; color: details.entry.kind === "deadline" ? Theme.warning : Theme.muted; font.pixelSize: 11 }
                    Label { Layout.fillWidth: true; text: details.location; textFormat: Text.PlainText; visible: !!text; wrapMode: Text.WrapAnywhere; color: Theme.muted; font.pixelSize: 11 }
                }
                AppIcon {
                    visible: agenda.showDates
                    Layout.preferredWidth: 14
                    Layout.preferredHeight: 14
                    name: "chevron-right"
                    ink: Theme.muted
                }
            }
        }
    }
}
