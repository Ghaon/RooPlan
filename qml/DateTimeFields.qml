import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "ScheduleTime.js" as ScheduleTime
import "Theme.js" as Theme

RowLayout {
    id: fields
    property string initialValue: ""
    property string defaultDate: ""
    property string originalStartDate: ""
    property string chosenDate: ""
    property bool dateEdited: false
    property bool showTime: true
    property bool allowDateOnly: false
    property bool calendarLabel: false
    property string timeLabel: "时间"
    readonly property string clockText: timeField.text.trim()
    readonly property bool dateOnly: allowDateOnly && !timeField.text.trim()
    readonly property string suggestedDate: {
        let original = initialValue.slice(0, 10)
        if (!original) return defaultDate
        if (!originalStartDate || !defaultDate) return original
        let start = Date.parse(originalStartDate + "T12:00:00Z")
        let end = Date.parse(original + "T12:00:00Z")
        let selected = Date.parse(defaultDate + "T12:00:00Z")
        let adjusted = new Date(selected + end - start)
        return isNaN(adjusted.getTime()) ? original : adjusted.toISOString().slice(0, 10)
    }
    property alias dateText: dateField.text
    readonly property bool pickerOpen: chooser.visible
    function value() {
        let day = dateField.text.trim()
        let clock = timeField.text.trim()
        if (!showTime || dateOnly) return day
        return clock ? day + "T" + clock : ""
    }
    function showCalendar(trigger) {
        let date = new Date(dateField.text + "T12:00")
        if (isNaN(date.getTime())) date = new Date()
        chooser.month = date.getMonth()
        chooser.year = date.getFullYear()
        let point = trigger.mapToItem(chooser.parent, 0, 0)
        chooser.x = Math.max(8, Math.min(point.x, chooser.parent.width - chooser.width - 8))
        chooser.y = point.y + trigger.height + chooser.height + 8 <= chooser.parent.height
            ? point.y + trigger.height + 4 : Math.max(8, point.y - chooser.height - 4)
        chooser.open()
    }
    FormField {
        id: dateField
        objectName: "dateField"
        visible: !fields.calendarLabel
        Layout.fillWidth: true
        Layout.minimumWidth: 98
        text: fields.dateEdited ? fields.chosenDate : fields.suggestedDate
        onTextEdited: { fields.chosenDate = text; fields.dateEdited = true }
        placeholderText: "YYYY-MM-DD"
        selectByMouse: true
    }
    PlanButton {
        objectName: fields.calendarLabel ? "datePickerButton" : ""
        visible: fields.calendarLabel
        Layout.fillWidth: true
        Layout.minimumWidth: 90
        text: ScheduleTime.dateLabel(fields.dateText)
        Accessible.name: fields.timeLabel + "日期，" + text
        onClicked: fields.showCalendar(this)
    }
    FormField {
        id: timeField
        objectName: "timeField"
        visible: fields.showTime
        Layout.preferredWidth: fields.allowDateOnly ? 78 : 65
        leftPadding: 7
        rightPadding: 7
        text: fields.initialValue.slice(11)
        placeholderText: fields.allowDateOnly ? "时间选填" : "HH:mm"
        Accessible.name: fields.timeLabel
        selectByMouse: true
    }
    IconButton {
        visible: !fields.calendarLabel
        objectName: visible ? "datePickerButton" : ""
        symbol: "calendar"
        hint: "选择日期"
        onClicked: fields.showCalendar(this)
    }
    Popup {
        id: chooser
        objectName: "datePicker"
        parent: Overlay.overlay
        property int month: 0
        property int year: 2026
        width: Math.min(292, parent.width-24)
        padding: 10
        margins: 8
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "transparent" }
        background: GlassSurface {
            bottomTint: "#f5f7f3"
            SurfaceShadow { radius: Theme.popupRadius }
        }
        function shiftMonth(delta) {
            let date = new Date(year, month + delta, 1)
            year = date.getFullYear()
            month = date.getMonth()
        }
        contentItem: ColumnLayout {
            RowLayout {
                Layout.fillWidth: true
                IconButton { symbol: "chevron-left"; hint: "上个月"; onClicked: chooser.shiftMonth(-1) }
                Label { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; text: chooser.year + "年" + (chooser.month+1) + "月"; font.bold: true }
                IconButton { symbol: "chevron-right"; hint: "下个月"; onClicked: chooser.shiftMonth(1) }
            }
            DayOfWeekRow { Layout.fillWidth: true; locale: Qt.locale("zh_CN") }
            MonthGrid {
                Layout.fillWidth: true
                Layout.preferredHeight: 180
                month: chooser.month
                year: chooser.year
                locale: Qt.locale("zh_CN")
                onClicked: date => {
                    fields.chosenDate = Qt.formatDate(date, "yyyy-MM-dd")
                    fields.dateEdited = true
                    chooser.close()
                }
            }
        }
    }
}
