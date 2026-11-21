import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme
import "ScheduleTime.js" as ScheduleTime

Sheet {
    id: group
    property var entries: []
    property string snapshot: ""
    property var proposed: ({})
    property bool saving: false
    property string validationMessage: ""
    signal saved
    heading: "一起改期"
    sheetWidth: 530
    readonly property bool datePickerOpen: {
        for (let i = 0; i < forms.count; i++) {
            let form = forms.itemAt(i)
            if (form && form.pickerOpen) return true
        }
        return false
    }
    function save() {
        let changes = []
        for (let i = 0; i < forms.count; i++) {
            let form = forms.itemAt(i)
            let fields = form.changes()
            if (Object.keys(fields).length) changes.push({id: form.entry.id, fields: fields})
        }
        validationMessage = ""
        saving = true
        let success = cal.reschedule(snapshot, JSON.stringify(changes))
        saving = false
        if (success) saved()
    }
    Connections {
        target: cal
        function onNotice(message) { if (group.saving) group.validationMessage = message }
    }
    Label {
        Layout.fillWidth: true
        text: "可分别修改活动和未完成的关联任务，确认后一起保存。"
        wrapMode: Text.Wrap
        color: Theme.muted
    }
    Repeater {
        id: forms
        model: group.entries
        delegate: InfoBox {
            id: row
            required property int index
            required property var modelData
            readonly property var entry: modelData
            readonly property bool pickerOpen: begin.pickerOpen || finish.pickerOpen
            heading: entry.title
            accentColor: Theme.eventAccent(entry)
            function changes() {
                let updates = {}
                let start = begin.value()
                let end = finish.value() || null
                if (start !== entry.start) updates.start = start
                if (entry.kind !== "deadline" && end !== (entry.end || null)) updates.end = end
                return updates
            }
            Label {
                Layout.fillWidth: true
                text: "原安排  " + ScheduleTime.range(row.entry.start, row.entry.end, true)
                wrapMode: Text.WrapAnywhere
                color: Theme.muted; font.pixelSize: 11
            }
            Label { text: row.entry.kind === "deadline" ? "截止时间" : "开始时间"; color: Theme.muted }
            DateTimeFields {
                id: begin
                objectName: "groupStart" + row.index
                Layout.fillWidth: true
                initialValue: row.index === 0 && group.proposed.start ? group.proposed.start : row.entry.start
                allowDateOnly: row.entry.kind === "deadline"
            }
            Label { visible: row.entry.kind !== "deadline"; text: "结束时间"; color: Theme.muted }
            DateTimeFields {
                id: finish
                objectName: "groupEnd" + row.index
                visible: row.entry.kind !== "deadline"
                Layout.fillWidth: true
                initialValue: row.index === 0 && group.proposed.end ? group.proposed.end : row.entry.end || ""
                defaultDate: begin.dateText
                originalStartDate: begin.initialValue.slice(0, 10)
            }
        }
    }
    actions: ColumnLayout {
        width: parent.width
        Label {
            visible: !!group.validationMessage
            Layout.fillWidth: true
            text: group.validationMessage
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            color: Theme.warning
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            PlanButton { text: "取消"; quiet: true; onClicked: group.dismissed() }
            PlanButton { text: "保存全部改期"; accent: true; onClicked: group.save() }
        }
    }
}
