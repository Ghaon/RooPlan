import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "ScheduleTime.js" as ScheduleTime
import "Theme.js" as Theme

ColumnLayout {
    id: details
    property var item: ({})
    property var related: []
    property var ancestors: []
    readonly property var links: ancestors.concat(related)
    readonly property bool dateOnly: item.kind === "deadline" && (item.start || "").length === 10
    readonly property string reminderLabel: dateOnly
        ? (item.reminder_time ? "当天 " + item.reminder_time + " 提醒" : "提醒已关闭")
        : (item.reminder < 0 ? "提醒已关闭" : item.reminder === 0 ? "准时提醒" : "提前 " + item.reminder + " 分钟提醒")
    signal openRelated(var entry)
    property bool showSource: false
    property var requirements: (item.notes || "").split(/\n|[；;]/).map(s => s.trim()).filter(s => s.length)
    spacing: 12
    RowLayout {
        Layout.fillWidth: true
        spacing: 9
        Rectangle {
            objectName: "detailColorMark"
            Layout.preferredWidth: 4
            Layout.preferredHeight: 23
            radius: 2
            color: Theme.eventAccent(details.item)
        }
        Label {
            Layout.fillWidth: true
            text: details.item.title || ""
            wrapMode: Text.WrapAnywhere
            textFormat: Text.PlainText
            font.pixelSize: 22; font.weight: Font.DemiBold; color: Theme.ink
        }
    }
    Label {
        Layout.fillWidth: true; wrapMode: Text.Wrap
        text: ({"event":"固定活动", "prep":"准备时段", "deadline":"截止任务"})[details.item.kind]
              + (details.item.done ? " · 已完成" : "")
              + " · " + details.reminderLabel
        color: Theme.muted; font.pixelSize: 12
    }
    InfoBox {
        heading: details.item.kind === "deadline" ? "提交期限" : "时间与地点"
        Label {
            Layout.fillWidth: true; wrapMode: Text.Wrap
            text: ScheduleTime.range(details.item.start, details.item.end, true)
                  + (details.dateOnly ? " · 时间未注明" : !details.item.end && details.item.kind === "event" ? " · 结束待定" : "")
            font.pixelSize: 15; font.bold: true; color: "#2e4436"
        }
        Label {
            visible: !!details.item.location; Layout.fillWidth: true
            text: details.item.location || ""; wrapMode: Text.Wrap; color: "#4e6053"
        }
        Label {
            visible: !!details.item.series
            Layout.fillWidth: true
            text: details.item.series
                ? (details.item.series.weeks === 1 ? "每周重复" : "隔周重复") + " · 系列截至 " + details.item.series.until
                : ""
            wrapMode: Text.Wrap
            color: "#53685b"
        }
    }
    InfoBox {
        heading: "要求与备注"
        visible: details.requirements.length > 0
        Repeater {
            model: details.requirements
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Label { text: "•"; color: "#78967c"; Layout.alignment: Qt.AlignTop }
                Label {
                    Layout.fillWidth: true; text: modelData
                    wrapMode: Text.Wrap; lineHeight: 1.25; color: "#344c3c"
                }
            }
        }
    }
    InfoBox {
        heading: "关联事项"
        visible: details.links.length > 0 || !!details.item.parent
        Label {
            Layout.fillWidth: true
            visible: !!details.item.parent && !details.ancestors.length
            text: "找不到原关联事项，可在编辑时重新选择。"
            wrapMode: Text.Wrap
            color: "#935624"
        }
        Repeater {
            model: details.links
            Button {
                id: relatedButton
                objectName: "detailLink_" + modelData.id
                readonly property bool ancestor: index < details.ancestors.length
                readonly property string kindLabel: ({"event":"活动", "deadline":"截止任务", "prep":"准备时段"})[modelData.kind]
                text: modelData.title
                Layout.fillWidth: true
                padding: 8
                onClicked: details.openRelated(modelData)
                background: Rectangle {
                    radius: 6
                    color: relatedButton.hovered || relatedButton.activeFocus ? Theme.tint : Theme.surface
                    border.color: relatedButton.visualFocus ? Theme.pine : Theme.line
                }
                contentItem: RowLayout {
                    Rectangle {
                        Layout.preferredWidth: 3
                        Layout.preferredHeight: 22
                        radius: 1.5
                        color: Theme.eventAccent(modelData)
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Label {
                            Layout.fillWidth: true
                            text: (relatedButton.ancestor ? "所属" : "关联") + relatedButton.kindLabel
                                  + (modelData.done ? " · 已完成" : "")
                            font.pixelSize: 11
                            color: "#53685b"
                            wrapMode: Text.Wrap
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.title
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: "#264839"
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.start.replace("T", " ")
                            font.pixelSize: 12
                            color: "#53685b"
                            wrapMode: Text.Wrap
                        }
                    }
                    Label { text: "›"; color: "#476450"; font.pixelSize: 19 }
                }
            }
        }
    }
    PlanButton {
        visible: !!details.item.source && details.item.source !== "手动录入"
        text: details.showSource ? "收起通知原文" : "查看通知原文"
        onClicked: details.showSource = !details.showSource
    }
    InfoBox {
        visible: details.showSource
        heading: "通知原文"
        TextEdit {
            Layout.fillWidth: true
            text: details.item.source || ""
            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
            color: "#5c6e60"; font.pixelSize: 12
        }
    }
}
