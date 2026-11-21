import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

Sheet {
    id: searchSheet
    heading: "搜索日程"
    property var initialFilters: ({})
    signal openResult(var entry, string day, var filters)
    property var result: cal.search(keyword.text, fromDate.text, toDate.text)
    Component.onCompleted: keyword.forceActiveFocus()

    FormField {
        id: keyword
        objectName: "calendarSearchInput"
        text: searchSheet.initialFilters.keyword || ""
        Layout.fillWidth: true
        leftPadding: 30
        placeholderText: "输入日程名称或地点"
        Accessible.name: "日程名称或地点"
        selectByMouse: true
        onAccepted: if (results.count) searchSheet.select(searchSheet.result.entries[0])
        AppIcon {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 8 }
            width: 16; height: 16
            name: "search"; ink: Theme.muted
        }
    }
    RowLayout {
        Layout.fillWidth: true
        FormField {
            id: fromDate
            objectName: "calendarSearchFrom"
            text: searchSheet.initialFilters.fromDate || ""
            Layout.fillWidth: true
            placeholderText: "起始日期"
            Accessible.name: "起始日期 YYYY-MM-DD"
            selectByMouse: true
        }
        FormField {
            id: toDate
            objectName: "calendarSearchTo"
            text: searchSheet.initialFilters.toDate || ""
            Layout.fillWidth: true
            placeholderText: "结束日期"
            Accessible.name: "结束日期 YYYY-MM-DD"
            selectByMouse: true
        }
    }
    Label {
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        text: searchSheet.result.error || "日期可选，格式 YYYY-MM-DD"
        color: searchSheet.result.error ? Theme.danger : Theme.muted
        font.pixelSize: 11
    }
    function select(entry) {
        let day = entry.start.slice(0, 10)
        let first = fromDate.text.trim()
        if (first && entry.end && day < first) day = first
        openResult(entry, day, {keyword: keyword.text, fromDate: fromDate.text, toDate: toDate.text})
    }
    AgendaList {
        id: results
        objectName: "calendarSearchResults"
        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(76, Math.min(380, searchSheet.height - 200))
        entries: searchSheet.result.entries
        showDates: true
        emptyText: searchSheet.result.error ? "" : "没有找到日程"
        onOpenItem: entry => searchSheet.select(entry)
    }
}
