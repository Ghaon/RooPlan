import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import "Theme.js" as Theme

Sheet {
    id: review
    property bool showSource: !!draft.failed
    property bool showSupplement: false
    property bool showConfirmed: false
    required property var draft
    readonly property var confirmed: draft.confirmed || []
    readonly property int selectedCount: draft.rows.filter(row => row.selected).length
    readonly property bool blocked: draft.rows.some(row => row.selected && (
        !!(draft.dependencies || {})[row.id] || unapproved(row.id).length > 0
        || (duplicate(row.id) && !duplicate(row.id).approved)))
    readonly property string status: {
        let pending = inbox.pending.find(d => d.id === draft.id)
        return pending ? pending.status : draft.status || ""
    }
    readonly property bool locked: ["解析中","排队中","待设置 API"].includes(status)
    property string slotItem: ""
    property var slotOptions: []
    function requestSlots(id) {
        slotItem = id
        slotOptions = inbox.alternatives(draft.id, id)
    }
    function applySlot(slot) {
        if (inbox.edit(draft.id, slotItem, JSON.stringify(slot))) {
            slotItem = ""
            slotOptions = []
            reload()
        }
    }
    signal editItem(var item)
    signal leave
    signal reload
    signal discardRequested
    heading: status ? "核对草稿 · " + status : "核对草稿"
    FileDialog {
        id: replaceImage
        nameFilters: ["截图 (*.png *.jpg *.jpeg)"]
        onAccepted: if (inbox.replaceScreenshot(review.draft.id, selectedFile.toString(), supplement.text)) {
            review.showSource = true
            review.reload()
        }
    }
    function conflicts(id) { return (draft.conflicts || {})[id] || [] }
    function duplicate(id) { return (draft.duplicates || {})[id] }
    function unapproved(id) { return conflicts(id).filter(conflict => !conflict.approved) }
    function acceptConflicts(id) {
        let tokens = unapproved(id).map(conflict => conflict.token)
        inbox.approveConflicts(draft.id, id, JSON.stringify(tokens))
        reload()
    }
    function choose(id, selected) {
        inbox.select(draft.id, id, selected)
        reload()
    }
    function overlap(conflict) {
        let start = conflict.start.replace("T", " ")
        let end = conflict.end.slice(0, 10) === conflict.start.slice(0, 10)
            ? conflict.end.slice(11) : conflict.end.replace("T", " ")
        return "与「" + conflict.title + "」重叠 " + start + "–" + end
            + (conflict.approved ? " · 已接受重叠" : "")
    }
    function summary(e) {
        if (!e) return ""
        return e.title + "　" + timing(e) + (e.location ? "　" + e.location : "")
    }
    function timing(entry) {
        let start = (entry.start || "时间待补充").replace("T", " ")
        if (entry.kind === "deadline" && (entry.start || "").length === 10)
            return start + " · 时间未注明"
        if (!entry.end) return start
        return start + " — " + (entry.end.slice(0, 10) === (entry.start || "").slice(0, 10)
                               ? entry.end.slice(11) : entry.end.replace("T", " "))
    }
    function fieldValue(field, value) {
        if (field === "kind") return ({"event":"活动", "deadline":"截止任务", "prep":"准备时段"})[value]
        if (field === "done") return value ? "已完成" : "未完成"
        if (field === "before_meeting") return value ? "是" : "否"
        if (field === "reminder") return value < 0 ? "关闭" : value === 0 ? "准时" : "提前 " + value + " 分钟"
        if (field === "parent") {
            if (!value) return "无关联"
            let item = (draft.linkTargets || []).find(entry => entry.id === value)
            return item ? item.title : "原关联事项不可用"
        }
        return value || "未填写"
    }
    function changes(row) {
        if (!row.before || !row.after) return []
        let result = []
        let oldTime = timing(row.before), newTime = timing(row.after)
        if (oldTime !== newTime) {
            result.push({label: row.after.kind === "deadline" ? "截止时间" : "活动时间",
                         before: oldTime, after: newTime})
        }
        let labels = {title:"名称", kind:"类型", location:"地点", notes:"要求", parent:"关联事项",
                      reminder:"提醒", reminder_time:"当天提醒时间", done:"完成状态", before_meeting:"会前提交"}
        for (let field in labels) {
            if ((row.before[field] ?? null) !== (row.after[field] ?? null))
                result.push({label: labels[field], before: fieldValue(field, row.before[field]),
                             after: fieldValue(field, row.after[field])})
        }
        return result
    }
    Component {
        id: slotsMenu
        ColumnLayout {
            Label { text: "可替换的准备时段"; font.bold: true }
            Label { visible: !review.slotOptions.length; text: "暂无其他空档"; color: "#60735f" }
            Repeater {
                model: review.slotOptions
                PlanButton {
                    Layout.fillWidth: true
                    text: modelData.start.replace("T"," ") + "–" + modelData.end.replace("T"," ")
                    enabled: !review.locked
                    onClicked: review.applySlot(modelData)
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 2
        PlanButton { text: review.showSource ? "收起原文" : "查看原文"; quiet: true; onClicked: review.showSource = !review.showSource }
        PlanButton {
            text: review.showSupplement ? "收起补充" : "补充说明"
            quiet: true
            visible: review.draft.rows.length > 0 && !review.draft.note && !review.draft.choices.length
            enabled: !review.locked
            onClicked: {
                review.showSupplement = !review.showSupplement
                if (review.showSupplement) supplement.forceActiveFocus()
            }
        }
        Item { Layout.fillWidth: true }
        PlanButton {
            text: review.confirmed.length ? "放弃剩余草稿" : "放弃草稿"
            quiet: true
            enabled: !review.locked
            onClicked: review.discardRequested()
        }
    }
    Label { visible: review.showSource; text:review.draft.source; textFormat: Text.PlainText; wrapMode:Text.WrapAnywhere; Layout.fillWidth:true }
    Image { visible:review.showSource && !!review.draft.preview; source:review.draft.preview || ""; Layout.fillWidth:true; Layout.preferredHeight:visible?150:0; fillMode:Image.PreserveAspectFit; sourceSize.width:1000 }
    Label {
        visible: !!text
        text: review.draft.note
        textFormat: Text.PlainText
        color: review.draft.already_recorded ? Theme.muted : Theme.warning
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }
    PlanButton {
        text: "更换截图"
        quiet: true
        visible: !!review.draft.preview && !review.draft.rows.length && !review.draft.choices.length
                 && !review.confirmed.length && !review.draft.already_recorded
        enabled: !review.locked
        onClicked: replaceImage.open()
    }
    Label {
        visible: review.status === "解析中"
        Layout.fillWidth: true
        text: inbox.progress
        color: Theme.muted
        wrapMode: Text.Wrap
    }
    FormField {
        id: supplement
        visible: review.showSupplement || (!review.draft.already_recorded
                 && (!review.draft.rows.length || !!review.draft.note || !!review.draft.choices.length))
        enabled: !review.locked
        Layout.fillWidth: true
        text: review.draft.supplement || ""
        placeholderText: review.draft.preview ? "补充日期，或粘贴截图中的文字" : "补充日期或说明"
        Accessible.name: "补充通知"
    }
    Repeater { model:review.draft.choices
        PlanButton { text:review.summary(modelData); Layout.fillWidth:true; enabled: !review.locked
            onClicked: inbox.run(review.draft.id, modelData.id, supplement.text)
        }
    }
    Component {
        id: relatedReview
        InfoBox {
            Layout.fillWidth: true
            heading: "改期涉及的关联事项"
            Repeater {
                model: review.draft.relatedReview || []
                ColumnLayout {
                    id: link
                    Layout.fillWidth: true
                    property var item: modelData
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        textFormat: Text.PlainText
                        color: link.item.problem ? "#935624" : "#4d6354"
                        text: link.item.title + " · " + (link.item.problem ? "需调整"
                              : link.item.changed ? "已列入变更" : "原安排照旧")
                              + (link.item.done ? " · 已完成" : "")
                    }
                    Label {
                        visible: !!text
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        textFormat: Text.PlainText
                        color: "#5a6f5d"
                        text: link.item.problem || (link.item.changed ? "" : review.timing(link.item))
                    }
                    Flow {
                        visible: !link.item.changed && !link.item.done
                        Layout.fillWidth: true
                        spacing: 6
                        PlanButton { text: "调整关联项"; enabled: !review.locked; onClicked: review.editItem(link.item) }
                        PlanButton { text: "可用时段"; visible: link.item.kind === "prep"; enabled: !review.locked; onClicked: review.requestSlots(link.item.id) }
                    }
                    Loader {
                        Layout.fillWidth: true
                        active: !link.item.changed && !link.item.done && review.slotItem === link.item.id
                        visible: active
                        sourceComponent: slotsMenu
                    }
                }
            }
        }
    }
    Repeater {
        model: ["update", "new", "suggested"]
        ColumnLayout {
            id: group
            property string category: modelData
            property bool suggested: category === "suggested"
            property var rows: review.draft.rows.filter(row =>
                category === "update" ? !!row.before : !row.before && row.suggested === suggested)
            visible: rows.length>0
            Layout.fillWidth:true
            Label {
                text: group.category === "update" ? "已有日程变更" :
                      group.suggested ? "建议的准备时间" : "通知要求与手动补充"
                font.weight: Font.DemiBold
                color: Theme.muted
            }
            Repeater {
                model:group.rows
                Rectangle {
                    id: draftRow
                    readonly property var row: modelData
                    readonly property var overlaps: review.conflicts(row.id)
                    readonly property bool conflicting: review.unapproved(row.id).length > 0
                    readonly property var duplicate: review.duplicate(row.id)
                    readonly property var item: row.after || row.before
                    Layout.fillWidth: true
                    implicitHeight: line.implicitHeight + 16
                    color: draftRow.conflicting ? Theme.warningSurface : draftRow.row.selected ? Theme.eventFill(draftRow.item) : Theme.field
                    radius: Theme.controlRadius
                    border.color: draftRow.conflicting ? "#e7c9a0" : Theme.line
                    Rectangle {
                        anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 4 }
                        width: 3; radius: 1.5
                        color: Theme.eventAccent(draftRow.item)
                    }
                    ColumnLayout { id:line; x:12; y:8; width:parent.width-21
                        RowLayout { Layout.fillWidth:true
                            CheckBox {
                                objectName: "draftSelection_" + draftRow.row.id
                                checked: draftRow.row.selected
                                enabled: !review.locked
                                Accessible.name: (draftRow.row.after || draftRow.row.before).title
                                onClicked: review.choose(draftRow.row.id, checked)
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Label {
                                    Layout.fillWidth: true; wrapMode: Text.WrapAnywhere
                                    textFormat: Text.PlainText
                                    font.pixelSize: 14; font.weight: Font.DemiBold; color: Theme.ink
                                    text: draftRow.item.title
                                }
                                Label {
                                    Layout.fillWidth: true; wrapMode: Text.WrapAnywhere
                                    textFormat: Text.PlainText; color: Theme.muted; font.pixelSize: 11
                                    text: (!draftRow.row.selected ? "待定 · " : "")
                                        + (draftRow.row.before ? draftRow.row.after ? "修改 · " : "删除 · " : "")
                                        + review.timing(draftRow.item)
                                        + (draftRow.item.location && !draftRow.row.before ? " · " + draftRow.item.location : "")
                                }
                            }
                            PlanButton {
                                objectName: "draftEdit_" + draftRow.row.id
                                text: draftRow.conflicting ? "调整时间" : "编辑"
                                quiet: true
                                enabled: !review.locked && !!draftRow.row.after
                                onClicked: review.editItem(draftRow.row.after)
                            }
                        }
                        Repeater {
                            model: review.changes(draftRow.row)
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3
                                Label { text: modelData.label; font.bold: true; font.pixelSize: 12; color: "#476450" }
                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    textFormat: Text.PlainText
                                    color: "#5a6f5d"
                                    text: "原安排　" + modelData.before
                                }
                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    textFormat: Text.PlainText
                                    font.bold: true
                                    color: "#21513d"
                                    text: "变更后　" + modelData.after
                                }
                            }
                        }
                        Label {
                            visible: !!text
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                            color: "#4d6354"
                            text: draftRow.row.before && draftRow.row.after && draftRow.row.after.location
                                  && draftRow.row.before.location === draftRow.row.after.location
                                  ? "地点照旧 · " + draftRow.row.after.location : ""
                        }
                        Label {
                            visible: !!draftRow.duplicate
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                            color: "#935624"
                            text: draftRow.duplicate ? "日历中已有类似安排 · " + review.summary(draftRow.duplicate.item)
                                  + (draftRow.duplicate.approved ? "\n已确认作为新日程添加" :
                                     !draftRow.row.selected ? "\n如需另建一项，可重新勾选" : "") : ""
                        }
                        PlanButton {
                            visible: !!draftRow.duplicate && !draftRow.duplicate.approved && draftRow.row.selected
                            enabled: !review.locked
                            text: "仍作为新日程添加"
                            onClicked: review.choose(draftRow.row.id, true)
                        }
                        Repeater {
                            model: draftRow.overlaps
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                                color: modelData.approved ? "#53725a" : "#935624"
                                text: review.overlap(modelData)
                            }
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: !!text
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: "#935624"
                            text: (review.draft.dependencies || {})[draftRow.row.id] || ""
                        }
                        Flow {
                            Layout.fillWidth: true
                            visible: draftRow.overlaps.length > 0
                            spacing: 6
                            PlanButton {
                                visible: draftRow.conflicting
                                text: draftRow.row.before ? "保留当前时间" : "仍按原时间添加"
                                enabled: !review.locked
                                onClicked: review.acceptConflicts(draftRow.row.id)
                            }
                            PlanButton {
                                text: "暂存待定"
                                enabled: !review.locked
                                onClicked: review.choose(draftRow.row.id, false)
                            }
                        }
                        PlanButton {
                            visible: modelData.after && modelData.after.kind === "prep"
                            enabled: !review.locked
                            text: "可用时段"
                            onClicked: review.requestSlots(modelData.id)
                        }
                        Loader {
                            Layout.fillWidth: true
                            active: review.slotItem === modelData.id
                            visible: active
                            sourceComponent: slotsMenu
                        }
                        Label {
                            visible: !!text
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                            text: !modelData.before && modelData.after && modelData.after.notes ? "要求　"+modelData.after.notes : ""
                        }
                    }
                }
            }
            Loader {
                Layout.fillWidth: true
                active: group.category === "update" && !!(review.draft.relatedReview || []).length
                visible: active
                sourceComponent: relatedReview
            }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: review.confirmed.length > 0
        PlanButton {
            text: (review.showConfirmed ? "收起已确认 " : "查看已确认 ") + review.confirmed.length + " 项"
            onClicked: review.showConfirmed = !review.showConfirmed
        }
        Repeater {
            model: review.showConfirmed ? review.confirmed : []
            Label {
                Layout.fillWidth: true
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                color: "#53725a"
                text: (modelData.after ? "已入历 · " : "已删除 · ") + review.summary(modelData.after || modelData.before)
            }
        }
    }
    CheckBox {
        id: keepNote
        visible: !!review.draft.note && !review.draft.failed && !review.draft.choices.length
            && review.selectedCount > 0
        enabled: !review.locked
        text: "将待补充说明留在草稿"
    }
    Label {
        visible: review.blocked
        Layout.fillWidth: true
        text: "请先核对已勾选事项的提示。"
        color: "#935624"
        wrapMode: Text.Wrap
    }
    actions: Flow { width: parent.width; spacing:6
        PlanButton {
            text: review.selectedCount && review.selectedCount < review.draft.rows.length
                ? "确认 " + review.selectedCount + " 项" : "确认勾选项"
            visible: review.draft.rows.length > 0
            accent: true
            enabled: !review.locked && review.selectedCount > 0 && !review.blocked && !review.draft.choices.length
            onClicked: {
                let saved = inbox.confirm(review.draft.id, supplement.text, keepNote.visible && keepNote.checked)
                review.reload()
                if (saved && review.draft.state === "applied") review.leave()
                else if (saved) keepNote.checked = false
            }
        }
        PlanButton { text:"手动补一项"; quiet: true; enabled: !review.locked; onClicked:review.editItem(cal.blank("")) }
        PlanButton {
            text: review.status === "待解析" ? "解析通知" : "重新解析"
            visible: !review.confirmed.length
            enabled: !review.locked
            accent: !review.draft.rows.length
            onClicked: inbox.run(review.draft.id, "", supplement.text)
        }
    }
}

