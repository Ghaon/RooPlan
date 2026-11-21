import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

Sheet {
    id: reminders
    heading: "日程提醒"
    property var entries: cal.pendingReminders
    signal openEntry(var entry)

    Label {
        visible: reminders.entries.length === 0
        Layout.fillWidth: true
        text: "暂无待处理提醒"
        color: Theme.muted
    }
    Repeater {
        model: reminders.entries
        InfoBox {
            id: row
            required property var modelData
            Layout.fillWidth: true
            heading: modelData.title
            accentColor: Theme.eventAccent(modelData)
            Label {
                Layout.fillWidth: true
                text: (row.modelData.kind === "deadline" ? "截止 " : "") + row.modelData.start.replace("T", "  ")
                color: row.modelData.kind === "deadline" ? Theme.warning : Theme.muted
            }
            Flow {
                Layout.fillWidth: true
                spacing: 6
                PlanButton { text: "查看日程"; onClicked: reminders.openEntry(row.modelData) }
                PlanButton { text: "10 分钟后提醒"; onClicked: cal.handleReminder(row.modelData.id, true) }
                PlanButton { text: "关闭提醒"; onClicked: cal.handleReminder(row.modelData.id, false) }
            }
        }
    }
}
