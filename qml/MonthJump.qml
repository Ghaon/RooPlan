import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

Popup {
    id: picker
    objectName: "monthJump"
    property Item trigger
    property string selectedDate
    property int year: 2000
    property int month: 0
    property var markers: ({})
    signal dateChosen(string day)

    width: Math.min(296, parent.width - 24)
    x: trigger ? Math.max(12, Math.min(trigger.mapToItem(parent, 0, 0).x, parent.width - width - 12)) : 12
    y: trigger ? trigger.mapToItem(parent, 0, trigger.height + 5).y : 50
    margins: 10
    padding: 10
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: "#18243830" }
    background: GlassSurface {
        bottomTint: "#f5f7f3"
        SurfaceShadow { radius: Theme.popupRadius }
    }
    transformOrigin: Popup.TopLeft
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: desk.motionEnabled ? Theme.menuReveal : 0 }
    }

    function showDate(day) {
        year = Number(day.slice(0, 4))
        month = Number(day.slice(5, 7)) - 1
        refreshMarkers()
        open()
    }
    function shiftMonth(delta) {
        let next = month + delta
        if (next < 0) year -= 1
        if (next > 11) year += 1
        month = (next + 12) % 12
        refreshMarkers()
    }
    function refreshMarkers() {
        markers = cal.monthMarkers(year, month + 1)
    }
    function choose(day) {
        close()
        dateChosen(day)
    }
    Connections {
        target: cal
        function onChanged() { if (picker.visible) picker.refreshMarkers() }
    }

    contentItem: ColumnLayout {
        spacing: 5
        RowLayout {
            Layout.fillWidth: true
            IconButton {
                objectName: "monthJumpPrevious"
                symbol: "chevron-left"; hint: "上个月"
                enabled: picker.year > 1 || picker.month > 0
                onClicked: picker.shiftMonth(-1)
            }
            Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: picker.year + "年" + (picker.month + 1) + "月"
                color: "#294d3d"
                font.bold: true
            }
            IconButton {
                objectName: "monthJumpNext"
                symbol: "chevron-right"; hint: "下个月"
                enabled: picker.year < 9999 || picker.month < 11
                onClicked: picker.shiftMonth(1)
            }
        }
        DayOfWeekRow {
            Layout.fillWidth: true
            locale: Qt.locale("zh_CN")
        }
        MonthGrid {
            Layout.fillWidth: true
            Layout.preferredHeight: 192
            locale: Qt.locale("zh_CN")
            month: picker.month
            year: picker.year
            delegate: Button {
                id: dateButton
                required property var model
                readonly property string day: String(model.year).padStart(4, "0") + "-"
                    + String(model.month + 1).padStart(2, "0") + "-" + String(model.day).padStart(2, "0")
                readonly property bool marked: !!picker.markers[day]
                readonly property bool selected: day === picker.selectedDate
                readonly property bool today: day === cal.todayDate
                objectName: "monthJumpDay_" + day
                enabled: model.year >= 1 && model.year <= 9999
                padding: 0
                hoverEnabled: true
                Accessible.name: day + (marked ? "，有日程" : "") + (today ? "，今天" : "")
                onClicked: picker.choose(day)
                background: Rectangle {
                    radius: 6
                    color: dateButton.selected ? "#326e55"
                        : dateButton.down ? "#dce7d8" : dateButton.hovered ? "#edf2e8" : "transparent"
                    border.width: dateButton.visualFocus || (dateButton.today && !dateButton.selected) ? 1 : 0
                    border.color: "#83a489"
                }
                contentItem: Item {
                    Text {
                        anchors.centerIn: parent
                        anchors.verticalCenterOffset: dateButton.marked ? -2 : 0
                        text: dateButton.model.day
                        font.pixelSize: 12
                        font.bold: dateButton.today || dateButton.selected
                        color: dateButton.selected ? "white"
                            : dateButton.model.month === picker.month ? "#294d3d" : "#6c7d71"
                    }
                    Rectangle {
                        visible: dateButton.marked
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 3
                        width: 4
                        height: 4
                        radius: 2
                        color: dateButton.selected ? "#ffffff" : "#508261"
                    }
                }
            }
        }
        PlanButton {
            objectName: "monthJumpToday"
            Layout.alignment: Qt.AlignHCenter
            text: "回到今天"
            onClicked: picker.choose(cal.todayDate)
        }
    }
}
