import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

ColumnLayout {
    id: form
    property var item: ({})
    property bool allowLinks: false
    property bool allowRepeat: false
    property var linkTargets: cal.linkTargets
    readonly property var kinds: item.kind === "prep" ? ["event", "deadline", "prep"] : ["event", "deadline"]
    readonly property var kindLabels: ({event: "固定活动", deadline: "截止任务", prep: "准备时段"})
    spacing: 10
    property bool moreOptions: false
    property bool attempted: false
    readonly property bool repeatVisible: allowRepeat && (moreOptions || repeatWeeks > 0)
    readonly property bool notesVisible: moreOptions || !!item.notes
    readonly property string titleError: attempted && !name.text.trim() ? "请填写日程名称。" : ""
    readonly property string startError: attempted && (!begin.dateText
        || (!begin.dateOnly && !validClock(begin.clockText))) ? "请选择日期并填写有效时间（HH:mm）。" : ""
    readonly property string endError: {
        if (!attempted || type.currentIndex === 1) return ""
        if (!finish.clockText) return type.currentIndex === 2 ? "请填写结束时间。" : ""
        if (!finish.dateText || !validClock(finish.clockText)) return "请填写有效的结束时间（HH:mm）。"
        return !startError && finish.value() <= begin.value() ? "结束时间必须晚于开始时间。" : ""
    }
    function validClock(value) { return /^([01]\d|2[0-3]):[0-5]\d$/.test(value) }
    function validateInput() {
        attempted = true
        if (titleError) name.forceActiveFocus()
        return !(titleError || startError || endError)
    }
    Component.onCompleted: Qt.callLater(() => name.forceActiveFocus())
    readonly property var reminderOptions: [-1,0,10]
    readonly property bool datePickerOpen: begin.pickerOpen || finish.pickerOpen || repeatUntil.pickerOpen
    readonly property bool dropdownOpen: remMode.popup.visible || repeat.popup.visible || linked.popup.visible
    readonly property int repeatWeeks: allowRepeat ? repeat.currentIndex : 0
    readonly property string repeatEnd: repeatUntil.value()
    readonly property bool linkResolved: !linked.visible || !linked.currentValue
        || linked.eligible.some(entry => entry.id === linked.currentValue)
    function values() {
        let fields = {title: name.text.trim(), kind: kinds[type.currentIndex], start: begin.value(),
                end: type.currentIndex === 1 ? null : finish.value() || null,
                location: place.text.trim(), color: palette.selected, notes: notes.text,
                reminder: begin.dateOnly ? -1 : (remMode.currentIndex === 3 ? Number(rem.text || -2)
                                                                           : reminderOptions[remMode.currentIndex])}
        if (begin.dateOnly || form.item.reminder_time)
            fields.reminder_time = begin.dateOnly ? reminderClock.text.trim() || null : null
        if (allowLinks) {
            fields.parent = linked.currentValue || null
            fields.before_meeting = fields.kind === "deadline" && !!fields.parent && dueBefore.checked
        }
        return fields
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        FormField {
            id: name
            objectName: "nameField"
            Layout.fillWidth: true
            implicitHeight: 44
            font.pixelSize: 22
            font.weight: Font.DemiBold
            leftPadding: 4
            text: form.item.title || ""
            placeholderText: "日程名称"
            Accessible.name: "名称"
            background: Rectangle {
                color: "transparent"
                Rectangle {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: name.activeFocus ? 2 : 1
                    color: form.titleError ? Theme.warning : name.activeFocus ? Theme.pine : Theme.line
                }
            }
        }
        Label { visible: !!form.titleError; text: form.titleError; color: Theme.warning }
    }
    Control {
        id: type
        objectName: "eventKind"
        Accessible.name: "日程类型"
        property int currentIndex: Math.max(0, form.kinds.indexOf(form.item.kind))
        Layout.fillWidth: true
        implicitHeight: 34
        padding: 3
        background: Rectangle { radius: Theme.controlRadius; color: Theme.field }
        contentItem: RowLayout {
            spacing: 3
            Repeater {
                model: form.kinds
                Button {
                    id: option
                    required property int index
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    objectName: "eventKind_" + modelData
                    text: form.kindLabels[modelData]
                    padding: 0
                    hoverEnabled: true
                    Accessible.role: Accessible.RadioButton
                    Accessible.checked: type.currentIndex === index
                    onClicked: type.currentIndex = index
                    contentItem: Text {
                        text: option.text
                        color: type.currentIndex === option.index ? Theme.pineDark : Theme.muted
                        font.pixelSize: 13
                        font.weight: type.currentIndex === option.index ? Font.DemiBold : Font.Normal
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignHCenter
                    }
                    background: Rectangle {
                        radius: Theme.controlRadius - 2
                        color: type.currentIndex === option.index ? Theme.surface : option.hovered ? "#dfeae4" : "transparent"
                        border.color: option.visualFocus ? Theme.pine : "transparent"
                        Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
                    }
                }
            }
        }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: form.width >= 410 && type.currentIndex !== 1 ? 2 : 1
        columnSpacing: 12
        rowSpacing: 7
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Label { text: type.currentIndex === 1 ? "截止于" : "开始"; color: Theme.muted }
            DateTimeFields {
                id: begin
                objectName: "eventBeginning"
                Layout.fillWidth: true
                initialValue: form.item.start || ""
                allowDateOnly: type.currentIndex === 1
                calendarLabel: true
                timeLabel: type.currentIndex === 1 ? "截止时间" : "开始时间"
            }
            Label { visible: !!form.startError; Layout.fillWidth: true; wrapMode: Text.Wrap; text: form.startError; color: Theme.warning }
        }
        ColumnLayout {
            visible: type.currentIndex !== 1
            Layout.fillWidth: true
            spacing: 4
            Label { text: type.currentIndex === 0 ? "结束（选填）" : "结束"; color: Theme.muted }
            DateTimeFields {
                id: finish
                objectName: "eventEnding"
                Layout.fillWidth: true
                initialValue: form.item.end || ""
                defaultDate: begin.dateText
                originalStartDate: (form.item.start || "").slice(0, 10)
                calendarLabel: true
                timeLabel: "结束时间"
            }
            Label { visible: !!form.endError; Layout.fillWidth: true; wrapMode: Text.Wrap; text: form.endError; color: Theme.warning }
        }
    }
    FormField {
        id: place
        Layout.fillWidth: true
        text: form.item.location || ""
        placeholderText: "添加地点（选填）"
        Accessible.name: "地点"
    }
    EventColorPicker {
        id: palette
        Layout.fillWidth: true
        selected: form.item.color || "auto"
        kind: form.kinds[type.currentIndex]
    }
    GridLayout {
        objectName: "eventOptions"
        Layout.fillWidth: true
        columns: 2
        columnSpacing: 10
        rowSpacing: 8
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.columnSpan: form.repeatVisible ? 1 : 2
            Layout.alignment: Qt.AlignTop
            spacing: 4
            Label { text: begin.dateOnly ? "当天提醒" : "提醒"; color: Theme.ink }
            FormSelect {
                id: remMode
                visible: !begin.dateOnly
                Layout.fillWidth: true
                Accessible.name: "提醒方式"
                model: ["关闭", "准时", "提前 10 分钟", "自定义"]
                currentIndex: {
                    let index = form.reminderOptions.indexOf(form.item.reminder ?? 10)
                    return index < 0 ? 3 : index
                }
            }
            FormField {
                id: reminderClock
                objectName: "dateOnlyReminder"
                visible: begin.dateOnly
                Layout.fillWidth: true
                text: form.item.reminder_time || ""
                placeholderText: "HH:mm（选填）"
                Accessible.name: "当天提醒时间"
            }
            FormField {
                id: rem
                visible: remMode.visible && remMode.currentIndex === 3
                Layout.fillWidth: true
                text: (form.item.reminder ?? 10) > 0 ? String(form.item.reminder ?? 10) : ""
                placeholderText: "提前多少分钟"
                Accessible.name: "提前提醒分钟数"
                validator: IntValidator { bottom: 1; top: 43200 }
            }
        }
        ColumnLayout {
            visible: form.repeatVisible
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 4
            Label { text: "重复"; color: Theme.ink }
            FormSelect {
                id: repeat
                objectName: "repeatInterval"
                Layout.fillWidth: true
                Accessible.name: "重复频率"
                model: ["不重复", "每周", "隔周"]
            }
        }
    }
    Label { visible: form.repeatWeeks > 0; text: "重复至（含当天）" }
    DateTimeFields {
        id: repeatUntil
        objectName: "repeatUntil"
        visible: form.repeatWeeks > 0
        showTime: false
        Layout.fillWidth: true
    }
    Label { visible: linked.visible; text: "关联到" }
    FormSelect {
        id: linked
        objectName: "linkedEvent"
        visible: form.allowLinks && (type.currentIndex > 0 || !!form.item.parent)
        Layout.fillWidth: true
        textRole: "label"
        valueRole: "id"
        readonly property var eligible: form.linkTargets.filter(entry => entry.id !== form.item.id
            && (entry.kind === "event" && type.currentIndex > 0
                || entry.kind === "deadline" && type.currentIndex === 2))
        model: {
            let options = [{id: "", label: "无关联"}]
            if (form.item.parent && !eligible.some(entry => entry.id === form.item.parent))
                options.push({id: form.item.parent, label: "原关联不可用 · 请重新选择"})
            for (let entry of eligible) {
                let date = (entry.start || "").slice(5).replace("T", " ")
                options.push({id: entry.id, label: date ? date + "  " + entry.title : entry.title})
            }
            return options
        }
        currentIndex: Math.max(0, model.findIndex(entry => entry.id === form.item.parent))
    }
    CheckBox {
        id: dueBefore
        objectName: "dueBeforeMeeting"
        visible: linked.visible && type.currentIndex === 1 && !!linked.currentValue && form.linkResolved
        text: "截止时间不得晚于活动开始"
        checked: !!form.item.before_meeting
    }
    FormArea {
        id: notes
        visible: form.notesVisible
        Layout.fillWidth: true
        Layout.minimumHeight: 52
        text: form.item.notes || ""
        placeholderText: "要求与备注（选填）"
        Accessible.name: "要求与备注"
    }
    PlanButton {
        text: form.moreOptions ? "收起选项" : "更多选项"
        quiet: true
        onClicked: form.moreOptions = !form.moreOptions
    }
}

