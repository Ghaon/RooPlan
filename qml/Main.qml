import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ScheduleTime.js" as ScheduleTime
import "Theme.js" as Theme

ApplicationWindow {
    id: win
    title: "袋办 RooPlan"
    flags: Qt.Window | Qt.FramelessWindowHint
    width: 1120
    height: 740
    color: "transparent"
    font.family: "Microsoft YaHei UI"
    palette.window: Theme.paper
    palette.base: Theme.surface
    palette.text: Theme.ink
    palette.button: Theme.surface
    palette.buttonText: Theme.ink
    palette.highlight: Theme.pine
    palette.highlightedText: "white"
    property var days: desk.days
    property var records: cal ? cal.records : []
    property bool compact: width < 640
    readonly property int todayIndex: days.indexOf(cal.todayDate)
    property int selectedDay: Math.max(0, todayIndex)
    property bool dateJumpSelected: false
    property real weekBlend: 1
    property bool preparingCalendar: false
    property int openingRequest: 0
    property rect calendarOpeningOrigin
    property real calendarOpeningProgress: 1
    NumberAnimation {
        id: openCalendarAnimation
        target: win; property: "calendarOpeningProgress"; from: 0; to: 1
        duration: 300; easing.type: Easing.InOutCubic
        onFinished: openingCopy.source = ""
    }
    NumberAnimation { id: weekReveal; target: win; property: "weekBlend"; from: desk.motionEnabled ? 0.88 : 1; to: 1; duration: desk.motionEnabled ? Theme.reveal : 0; easing.type: Easing.OutCubic }
    readonly property bool viewingToday: todayIndex >= 0 && ((!compact && !dateJumpSelected) || selectedDay === todayIndex)
    function goToday() {
        if (!desk.currentWeek) desk.week(0)
        selectedDay = Math.max(0, todayIndex)
        dateJumpSelected = false
        compactDayOpen = true
        dayAgenda.positionViewAtBeginning()
    }
    property bool compactDayOpen: false
    readonly property bool agendaMode: compact && compactDayOpen
    readonly property var deadlines: days.map((day, index) => records.filter(e => e.day === index && e.kind === "deadline"))
    property int deadlineDay: 0
    property var visibleRecords: records.filter(e => e.kind !== "deadline")
    property bool earlyExpanded: false
    property bool lateExpanded: false
    readonly property var earlyRecords: visibleRecords.filter(e => e.minute < 480)
    readonly property var lateRecords: visibleRecords.filter(e => e.minute + e.duration > 1320)
    property string locatedId: ""
    property int locatedDay: -1
    property string detailReturnMode: ""
    property var searchFilters: ({})
    function openSearch() {
        searchFilters = ({})
        mode = "search"
    }
    function defaultStart() {
        let day = days[selectedDay]
        return day + "T09:00"
    }
    function openEntry(entry) { cardClicked(entry, width/2, height/2) }
    function selectDate(day) {
        desk.jumpToDate(day)
        selectedDay = days.indexOf(day)
        if (compact) compactDayOpen = true
    }
    function locateEntry(entry, day, returnMode) {
        selectDate(day)
        let segment = visibleRecords.find(e => e.id === entry.id && e.day === selectedDay)
        if (segment && segment.minute < 480) {
            earlyPeriod.anchorDay = selectedDay
            earlyExpanded = true
        }
        if (segment && segment.minute + segment.duration > 1320) {
            latePeriod.anchorDay = selectedDay
            lateExpanded = true
        }
        locatedId = entry.id
        locatedDay = selectedDay
        openEntry(entry)
        detailReturnMode = returnMode
        Qt.callLater(function() {
            let index = dayAgenda.entries.findIndex(e => e.id === entry.id)
            if (index >= 0 && dayAgenda.visible)
                dayAgenda.positionViewAtIndex(index, ListView.Contain)
        })
    }
    function showReminders() {
        desk.reveal()
        if (mode === "" || mode === "reminders") mode = "reminders"
    }
    function attachNotice(url) {
        if ((mode !== "" && mode !== "import") || addMenu.visible || toolsMenu.visible) return false
        if (!inbox.isScreenshot(url)) return false
        if (desk.collapsed) desk.expand()
        mode = "import"
        if (!workflowSheet.item) return false
        workflowSheet.item.attachment = url
        return true
    }
    property var clock: new Date()
    property var hoveredEvent: null
    property real previewX: 0
    property real previewY: 0
    function weekTitle() {
        let first = days[0], last = days[6]
        let month = Number(first.slice(5,7))
        let endMonth = Number(last.slice(5,7))
        let prefix = Number(first.slice(0,4)) !== clock.getFullYear() ? first.slice(0,4) + "年 " : ""
        return prefix + month + "月" + Number(first.slice(8)) + "–" + (month === endMonth ? "" : endMonth + "月") + Number(last.slice(8)) + "日"
    }
    function eventColor(entry) {
        return Theme.eventAccent(entry)
    }
    function previewEvent(entry, item) {
        let point = item.mapToItem(panel, 0, 0)
        previewX = point.x + item.width + 8
        if (previewX + eventPreview.width > panel.width - 12)
            previewX = point.x - eventPreview.width - 8
        previewY = point.y
        hoveredEvent = entry
        previewClose.stop()
    }
    function dismissPreview() { if (!previewHover.hovered) previewClose.restart() }
    Timer { interval: 30000; running: true; repeat: true; onTriggered: win.clock = new Date() }
    Timer { id: previewClose; interval: 220; onTriggered: win.hoveredEvent = null }
    property var draft: ({})
    property string apiDraft: ""
    function openDraft(key) { draft=inbox.draft(key); mode="review" }
    function saveDraftRow(fields) {
        let values = JSON.stringify(fields)
        let saved = current.id ? inbox.edit(draft.id, current.id, values)
                               : inbox.add(draft.id, values)
        if (saved) openDraft(draft.id)
    }
    Connections { target:inbox
        function onKeyRequired() {
            win.apiDraft = inbox.waitingDraftId
            win.mode = "api"
        }
        function onNotice(s) { win.showMessage(s, false) }
        function onReady(key) {
            if (win.mode === "review" && win.draft.id === key) win.openDraft(key)
            else if (win.mode === "" && !desk.collapsed && win.active) win.openDraft(key)
        }
    }
    property var current: ({})
    property real originX: width/2
    property real originY: height/2
    property var related: []
    property var rescheduleGroup: ({entries: [], snapshot: ""})
    property string message: ""
    property bool reminderMessage: false
    function showMessage(text, fromReminder) {
        reminderMessage = fromReminder
        message = text
        toast.restart()
    }
    function closeSheet() {
        if (mode === "api") {
            inbox.cancelKeyRequest()
            returnFromAPI()
            return
        }
        mode = mode === "rowEdit" ? "review" : mode === "reschedule" && !rescheduleGroup.proposed
            ? "detail" : mode === "delete" ? "detail" : mode === "detail" ? detailReturnMode : ""
    }
    function returnFromAPI() {
        let key = apiDraft
        apiDraft = ""
        if (key) openDraft(key)
        else mode = ""
    }
    Shortcut { sequence: "Escape"; enabled: win.mode !== "" && !toolsMenu.visible && !addMenu.visible && !win.eventPopupOpen && !win.noticePopupOpen; onActivated: win.closeSheet() }
    Shortcut { sequence: "Escape"; enabled: win.mode === "" && !toolsMenu.visible && !addMenu.visible && !monthJump.visible; onActivated: { grid.cancelGesture(); desk.cancelInteraction() } }
    property bool anchorEditor: false
    function createAt(start, end, point) {
        current = Object.assign(cal.blank(start), end ? {end: end} : {})
        anchorEditor = !!point
        originX = point ? point.x : width/2
        originY = point ? point.y : height/2
        mode = "edit"
    }
    onBlankClicked: stamp => createAt(stamp, "", null)
    onCardClicked: function(entry,px,py) {
        hoveredEvent = null
        detailReturnMode = ""
        anchorEditor = px !== width/2 || py !== height/2
        current=entry; related=cal.related(entry.id); originX=px; originY=py; mode="detail"
    }
    Connections { target: desk
        function onWeekChanged() {
            if (!desk.collapsed && win.mode === "") weekReveal.restart()
            grid.cancelGesture()
            win.hoveredEvent = null
            win.locatedId = ""
            win.dateJumpSelected = false
            win.selectedDay = Math.max(0, win.todayIndex)
        }
        function onChanged() {
            if (!desk.collapsed) return
            if (!win.preparingCalendar) {
                openCalendarAnimation.stop()
                win.calendarOpeningProgress = 1
                openingCopy.source = ""
            }
            monthJump.close()
            addMenu.close()
            grid.cancelGesture()
            win.hoveredEvent = null
        }
        function onOpeningCalendar(fromPreview) {
            win.preparingCalendar = true
            let request = ++win.openingRequest
            let usePreview = fromPreview && todayPanel.visible
            if (usePreview) {
                win.calendarOpeningOrigin = todayPanel.cardBounds()
                openingSurface.startColor = Theme.paper
                openingSurface.startRadius = Theme.sheetRadius
            } else {
                let point = handle.mapToGlobal(0, 0)
                win.calendarOpeningOrigin = Qt.rect(point.x, point.y, handle.width, handle.height)
                openingSurface.startColor = handle.color
                openingSurface.startRadius = handle.radius
            }
            win.calendarOpeningProgress = 0
            let receiveFrame = result => {
                if (win.preparingCalendar && request === win.openingRequest)
                    openingCopy.source = result.url
            }
            let started = usePreview ? todayPanel.grabCard(receiveFrame) : handle.grabToImage(receiveFrame)
            if (!started) Qt.callLater(desk.stageCalendarOpening)
        }
        function onCalendarOpeningReady(animate) {
            win.preparingCalendar = false
            if (animate) {
                openCalendarAnimation.start()
            } else {
                win.calendarOpeningProgress = 1
                openingCopy.source = ""
            }
        }
    }
    Connections { target: cal
        function onChanged() {
            if (win.mode === "review" && win.draft.id)
                win.draft = inbox.draft(win.draft.id)
        }
        function onNotice(s) { win.showMessage(s, false) }
        function onReminder(s) { win.showMessage(s, true) }
    }
    Timer { id:toast; interval:7000; onTriggered:win.message="" }
    property string mode: ""
    readonly property bool eventPopupOpen: !!(eventSheet.item && (eventSheet.item.datePickerOpen || eventSheet.item.dropdownOpen))
    readonly property bool noticePopupOpen: mode === "import" && !!(workflowSheet.item && workflowSheet.item.popupOpen)
    function updatePause() { desk.pause(mode !== "" || hoveredEvent !== null || toolsMenu.visible || addMenu.visible || monthJump.visible || grid.pressDay >= 0) }
    onModeChanged: { if (mode !== "") { monthJump.close(); addMenu.close() } grid.cancelGesture(); hoveredEvent = null; updatePause() }
    onHoveredEventChanged: {
        if (hoveredEvent) eventPreview.entry = hoveredEvent
        updatePause()
    }
    MonthJump {
        id: monthJump
        parent: Overlay.overlay
        trigger: dateJumpButton
        selectedDate: win.days[win.selectedDay]
        onVisibleChanged: { win.hoveredEvent = null; win.updatePause() }
        onDateChosen: day => {
            win.selectDate(day)
            win.dateJumpSelected = day !== cal.todayDate
        }
    }
    WindowMenu {
        id: toolsMenu
        objectName: "windowMenu"
        parent: Overlay.overlay
        x: win.width-width-12
        y: moreButton.mapToItem(Overlay.overlay, 0, moreButton.height + 6).y
        margins: 8
        maximized: desk.maximized
        reminderCount: cal.pendingReminders.length
        onVisibleChanged: { win.hoveredEvent = null; win.updatePause() }
        onChosen: function(action) {
            if (action === "maximize") desk.maximize()
            else if (action === "minimize") desk.minimize()
            else if (action === "reset") desk.resetSize()
            else if (action === "api") win.mode = "api"
            else if (action === "search") win.openSearch()
            else if (action === "reminders") win.mode = "reminders"
            else if (action === "undo") cal.undo()
            else if (action === "quit") Qt.quit()
        }
    }
    Shortcut { sequence: "Ctrl+0"; onActivated: desk.resetSize() }
    Shortcut {
        sequence: "Ctrl+F"
        enabled: !desk.collapsed && win.mode === "" && !toolsMenu.visible && !addMenu.visible && !monthJump.visible
        onActivated: win.openSearch()
    }
    signal blankClicked(string stamp)
    signal cardClicked(var entry, real px, real py)
    Window {
        id: edgeWindow
        objectName: "edgeWindow"
        transientParent: null
        color: "transparent"
        Rectangle {
            id: handle
            objectName: "edgeHandle"
            width: desk.horizontal ? Math.min(56, parent.width) : Math.min(20, parent.width)
            height: desk.horizontal ? Math.min(20, parent.height) : Math.min(56, parent.height)
            x: desk.horizontal ? (parent.width - width) / 2 : desk.previewEdge === "right" ? parent.width - width : 0
            y: desk.horizontal ? desk.previewEdge === "bottom" ? parent.height - height : 0 : (parent.height - height) / 2
            Accessible.role: Accessible.Button
            Accessible.name: "展开周历"
            Accessible.onPressAction: desk.expand(true)
            radius: 9
            color: desk.transparencyEnabled
                ? (handleMouse.containsMouse || desk.previewing ? "#d8246352" : "#3c246352")
                : (handleMouse.containsMouse || desk.previewing ? Theme.pineDark : Theme.pine)
            Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
            Rectangle { anchors.centerIn: parent; width: desk.horizontal ? 20 : 2; height: desk.horizontal ? 2 : 20; radius: 1; color: "#eaf0df" }
            MouseArea {
                id: handleMouse
                objectName: "handleMouse"
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton
                cursorShape: (pressedButtons & Qt.LeftButton) ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                onEntered: { desk.keepPreview(); if (!desk.previewing && !pressed) hoverDelay.restart() }
                onExited: { hoverDelay.stop(); desk.deferHidePreview() }
                onPressed: function(mouse) { if (mouse.button === Qt.LeftButton) { hoverDelay.stop(); desk.keepPreview(); let p = mapToGlobal(mouse.x, mouse.y); desk.dragStart(p.x, p.y) } }
                onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) { let p = mapToGlobal(mouse.x, mouse.y); desk.dragMove(p.x, p.y) } else desk.cancelInteraction() }
                onReleased: desk.dragEnd()
                onCanceled: desk.cancelInteraction()
            }
            Timer { id: hoverDelay; interval: 250; onTriggered: if (edgeWindow.visible && handleMouse.containsMouse && !handleMouse.pressed) desk.showPreview() }
        }
        NoticeDrop {}
    }
    TodayPanel {
        id: todayPanel
        objectName: "todayPanel"
        transientParent: edgeWindow
        visible: desk.previewing
        onOpenItem: function(entry) {
            desk.expand()
            win.cardClicked(entry, win.width/2, win.height/2)
        }
        onOpenCalendar: desk.expand(true, true)
    }
    Item {
        id: calendarFrame
        readonly property bool morphing: win.calendarOpeningProgress < 1
        readonly property real remaining: 1 - win.calendarOpeningProgress
        readonly property real inset: Math.min(openingSurface.radius * 0.3, Math.max(0, (width - 1) / 2),
                                                Math.max(0, (height - 1) / 2), remaining * 45)
        x: (win.calendarOpeningOrigin.x - win.x) * remaining
        y: (win.calendarOpeningOrigin.y - win.y) * remaining
        width: win.width + (win.calendarOpeningOrigin.width - win.width) * remaining
        height: win.height + (win.calendarOpeningOrigin.height - win.height) * remaining
        clip: morphing
        Rectangle {
            id: openingSurface
            objectName: "calendarOpeningSurface"
            readonly property real tone: Math.min(1, win.calendarOpeningProgress * 2.1)
            property color startColor: Theme.paper
            readonly property color endColor: Theme.paper
            property real startRadius: Theme.sheetRadius
            anchors.fill: parent
            visible: !desk.collapsed && calendarFrame.morphing
            radius: Theme.sheetRadius + (startRadius - Theme.sheetRadius) * calendarFrame.remaining
            opacity: Math.min(1, calendarFrame.remaining / 0.12,
                              openingCopy.status === Image.Ready ? win.calendarOpeningProgress * 14 : 1)
            color: Qt.rgba(startColor.r + (endColor.r - startColor.r) * tone,
                           startColor.g + (endColor.g - startColor.g) * tone,
                           startColor.b + (endColor.b - startColor.b) * tone,
                           startColor.a + (endColor.a - startColor.a) * tone)
            border.color: Theme.line
        }
        Image {
            id: openingCopy
            objectName: "calendarOpeningCopy"
            anchors.centerIn: parent
            width: win.calendarOpeningOrigin.width
            height: win.calendarOpeningOrigin.height
            visible: openingSurface.visible && status === Image.Ready && opacity > 0
            opacity: Math.max(0, 1 - win.calendarOpeningProgress * 2.2)
            onStatusChanged: {
                if (win.preparingCalendar && (status === Image.Ready || status === Image.Error))
                    Qt.callLater(desk.stageCalendarOpening)
            }
        }
    }
    Rectangle {
        id: panel
        objectName: "calendarPanel"
        parent: calendarFrame
        x: calendarFrame.inset
        y: calendarFrame.inset
        width: win.width
        height: win.height
        transform: Scale {
            xScale: (calendarFrame.width - 2 * calendarFrame.inset) / Math.max(1, panel.width)
            yScale: (calendarFrame.height - 2 * calendarFrame.inset) / Math.max(1, panel.height)
        }
        visible: !desk.collapsed
        opacity: Math.max(0, Math.min(1, (win.calendarOpeningProgress - 0.24) / 0.64))
        enabled: !calendarFrame.morphing
        color: "transparent"
        border.color: calendarFrame.morphing ? "transparent" : Theme.line
        radius: desk.maximized ? 0 : Theme.sheetRadius
        clip: true
        GlassSurface {
            id: toolbarSurface
            objectName: "weekToolbarGlass"
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: weekLayout.y + navigation.height + 4
            radius: 0
            topLeftRadius: panel.radius - (panel.radius ? 1 : 0)
            topRightRadius: topLeftRadius
            color: Theme.paper
            topTint: "#d8fafff8"
            sheenTint: "#c5f8fcf6"
            bottomTint: "#e0d4e5da"
            border.width: 0
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }
        Rectangle {
            anchors { left: toolbarSurface.left; right: toolbarSurface.right; top: toolbarSurface.bottom; bottom: parent.bottom; bottomMargin: 1 }
            color: Theme.paper
            bottomLeftRadius: toolbarSurface.topLeftRadius
            bottomRightRadius: bottomLeftRadius
        }
        MouseArea {
            id: titleMouse
            objectName: "titleMouse"
            width: panel.width
            height: weekLayout.y + (win.compact ? dayHeaders.y : navigation.y + navigation.height)
            enabled: win.mode === ""
            acceptedButtons: Qt.LeftButton
            hoverEnabled: true
            readonly property bool overDate: containsMouse && hitsDate(mouseX, mouseY)
            property bool pressedDate: false
            property point pressAt
            property bool dragged: false
            function hitsDate(x, y) {
                return dateJumpButton.contains(dateJumpButton.mapFromItem(titleMouse, x, y))
            }
            cursorShape: pressed && dragged ? Qt.ClosedHandCursor : overDate ? Qt.PointingHandCursor : Qt.ArrowCursor
            onPressed: mouse => {
                pressedDate = hitsDate(mouse.x, mouse.y)
                pressAt = mapToGlobal(mouse.x, mouse.y)
                dragged = false
                desk.dragStart(pressAt.x, pressAt.y)
            }
            onPositionChanged: mouse => {
                if (!pressed) return
                let point = mapToGlobal(mouse.x, mouse.y)
                dragged = dragged || Math.abs(point.x-pressAt.x) + Math.abs(point.y-pressAt.y) >= 4
                desk.dragMove(point.x, point.y)
            }
            onReleased: desk.dragEnd()
            onCanceled: desk.cancelInteraction()
            onClicked: {
                if (!dragged && pressedDate && !monthJump.visible) dateJumpButton.openPicker()
            }
            onDoubleClicked: mouse => { if (!hitsDate(mouse.x, mouse.y)) desk.maximize() }
        }
        ColumnLayout {
            id: weekLayout
            objectName: "calendarLayout"
            enabled: win.mode === ""
            anchors.fill: parent
            anchors.margins: 12
            anchors.bottomMargin: calendarActions.reserveSpace ? calendarActions.inset + calendarActions.height + 6 : 12
            spacing: win.compact ? 5 : 8
            RowLayout {
                id: navigation
                objectName: "weekNavigation"
                Layout.fillWidth: true
                Layout.preferredHeight: win.compact ? 40 : 50
                Layout.leftMargin: 2
                Layout.rightMargin: 0
                spacing: win.compact ? 1 : 5
                Image {
                    objectName: "brandIcon"
                    visible: !win.compact
                    Layout.preferredWidth: 34
                    Layout.preferredHeight: 34
                    source: "../assets/rooplan-mark.png"
                    fillMode: Image.PreserveAspectFit
                    mipmap: true
                }
                Item {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 76
                    Layout.preferredHeight: 36
                    Item {
                        id: dateJumpButton
                        objectName: "dateJumpButton"
                        anchors.verticalCenter: parent.verticalCenter
                        implicitWidth: dateLabel.implicitWidth + 8
                        width: Math.min(parent.width, implicitWidth)
                        height: 34
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: win.weekTitle() + "，选择日期"
                        Accessible.onPressAction: openPicker()
                        Keys.onPressed: event => {
                            if ([Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].includes(event.key)) {
                                openPicker()
                                event.accepted = true
                            }
                        }
                        function openPicker() { monthJump.showDate(win.days[win.selectedDay]) }
                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.controlRadius
                            color: monthJump.visible || dateJumpButton.activeFocus || titleMouse.overDate
                                ? Theme.tint : "transparent"
                            border.color: dateJumpButton.activeFocus ? Theme.pine : "transparent"
                        }
                        RowLayout {
                            id: dateLabel
                            anchors.fill: parent
                            anchors.leftMargin: 4
                            anchors.rightMargin: 4
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: win.weekTitle()
                                color: Theme.ink
                                font.pixelSize: win.compact ? 17 : 24
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            AppIcon {
                                Layout.preferredWidth: 14
                                Layout.preferredHeight: 14
                                name: "chevron-down"
                                ink: Theme.muted
                                rotation: monthJump.visible ? 180 : 0
                                Behavior on rotation { NumberAnimation { duration: desk.motionEnabled ? Theme.reveal : 0; easing.type: Easing.OutCubic } }
                            }
                        }
                    }
                }
                IconButton { symbol: "chevron-left"; hint: "上一周"; onClicked: desk.week(-1) }
                Label { objectName: "currentWeekLabel"; visible: desk.currentWeek; text: "本周"; color: Theme.muted; font.pixelSize: 11; leftPadding: 2; rightPadding: 2 }
                IconButton { symbol: "chevron-right"; hint: "下一周"; onClicked: desk.week(1) }
                Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 15; color: Theme.line }
                PlanButton {
                    id: draftButton
                    objectName: "draftButton"
                    readonly property int count: inbox.pendingCount
                    visible: count > 0
                    text: win.compact ? String(count) : "草稿 " + count
                    implicitWidth: win.compact ? 28 : 64
                    onClicked: win.mode = "inbox"
                    Hint { parent: draftButton; visible: draftButton.hovered; text: "待核对草稿" }
                }
                IconButton {
                    objectName: "pinButton"
                    symbol: "pin"
                    hint: desk.pinned ? "取消置顶" : "置顶窗口"
                    checkable: true
                    checked: desk.pinned
                    onClicked: desk.togglePinned()
                }
                IconButton { objectName: "foldButton"; symbol: "fold"; hint: "收回屏幕边缘"; onClicked: desk.fold() }
                IconButton { id: moreButton; objectName: "moreButton"; symbol: "more"; hint: "窗口菜单"; onClicked: toolsMenu.open() }
            }
            Label {
                visible: inbox.busy
                Layout.fillWidth: true
                text: inbox.progress
                color: "#73856c"; font.pixelSize: 11
                elide: Text.ElideRight
            }
            Row {
                id: dayHeaders
                objectName: "dayHeaders"
                Layout.fillWidth: true
                Layout.topMargin: win.compact ? 8 : 0
                readonly property real gutter: grid.gutter
                readonly property int dayHeight: win.compact ? 43 : 48
                Item {
                    width: dayHeaders.gutter
                    height: dayHeaders.dayHeight
                    IconButton {
                        objectName: "backToWeekButton"
                        anchors.centerIn: parent
                        width: parent.width
                        visible: win.agendaMode
                        symbol: "calendar"
                        hint: "返回周视图"
                        onClicked: win.compactDayOpen = false
                    }
                }
                Repeater {
                    model: win.days
                    Item {
                        id: dayCell
                        readonly property bool today: win.viewingToday && modelData === cal.todayDate
                        readonly property bool selected: (win.compact || win.dateJumpSelected) && win.selectedDay === index
                        objectName: win.dateJumpSelected && selected ? "jumpedDayHeader" : ""
                        width: (dayHeaders.width - dayHeaders.gutter) / 7
                        height: dayHeaders.dayHeight
                        function openDay() {
                            win.selectedDay = index
                            win.dateJumpSelected = index !== win.todayIndex
                            if (win.compact) win.compactDayOpen = true
                        }
                        HoverHandler { id: dayHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: dayCell.openDay() }
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData
                        Accessible.onPressAction: dayCell.openDay()
                        Column {
                            anchors.centerIn: parent
                            spacing: 3
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: (win.compact ? "" : "周") + "一二三四五六日"[index]
                                color: Theme.muted
                                font.pixelSize: 11
                            }
                            Rectangle {
                                objectName: dayCell.today ? "todayBadge" : ""
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: win.compact ? 25 : 28
                                height: width
                                radius: width/2
                                color: dayCell.today ? Theme.pine : dayCell.selected ? Theme.tint : "transparent"
                                Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
                                Text {
                                    objectName: "dateNumber"
                                    anchors.fill: parent
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    text: Number(modelData.slice(8))
                                    font.pixelSize: 13
                                    font.bold: dayCell.today || dayCell.selected
                                    font.underline: dayHover.hovered && !dayCell.selected && !dayCell.today
                                    color: dayCell.today ? "white" : dayHover.hovered ? Theme.pineDark : Theme.ink
                                }
                            }
                        }
                    }
                }
            }
            AgendaList {
                id: dayAgenda
                opacity: win.weekBlend
                objectName: "dayAgenda"
                visible: win.agendaMode
                Layout.fillWidth: true
                Layout.fillHeight: true
                trailingSpace: calendarActions.inset + calendarActions.height + 6 - weekLayout.anchors.bottomMargin
                hideRepeatedLocation: true
                day: win.days[win.selectedDay]
                highlightId: win.locatedDay === win.selectedDay ? win.locatedId : ""
                entries: win.records.filter(e => e.day === win.selectedDay).sort((a,b) => a.start.localeCompare(b.start))
                onDayChanged: {
                    positionViewAtBeginning()
                    if (win.visible && win.agendaMode && win.mode === "") weekReveal.restart()
                }
                onOpenItem: entry => win.openEntry(entry)
            }
            RowLayout {
                visible: !win.agendaMode && win.deadlines.some(day => day.length)
                Layout.fillWidth: true
                spacing: 0
                Label { Layout.preferredWidth: grid.gutter; text: "截止"; color: "#855329"; font.pixelSize: 11; Layout.alignment: Qt.AlignTop }
                DeadlineStrip {
                    Layout.fillWidth: true
                    days: win.deadlines
                    compact: win.compact
                    onOpenItem: entry => win.openEntry(entry)
                    onOpenDay: index => { win.deadlineDay = index; win.mode = "deadlines" }
                }
            }
            PeriodStrip {
                id: earlyPeriod
                objectName: "earlyPeriod"
                visible: !win.agendaMode && (win.earlyRecords.length > 0 || win.earlyExpanded)
                Layout.fillWidth: true
                records: win.earlyRecords
                gutter: grid.gutter
                label: "清晨"
                boundary: 0
                expanded: win.earlyExpanded
                onToggleRequested: win.earlyExpanded = !win.earlyExpanded
            }
            Item {
                id: grid
                opacity: win.weekBlend
                objectName: "weekGrid"
                visible: !win.agendaMode
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true
                property real gutter: win.compact ? 28 : 46
                property int rangeStart: win.earlyExpanded ? 0 : 8
                property int rangeEnd: win.lateExpanded ? 24 : 22
                property real timePadding: 8
                property real unit: Math.max(1, (height-2*timePadding) / (rangeEnd-rangeStart))
                property int labelStep: unit >= 30 ? 1 : unit >= 14 ? 2 : unit >= 5 ? 4 : 6
                property real dayWidth: (width - gutter) / 7
                readonly property var gridRecords: win.visibleRecords
                    .filter(e => e.minute < rangeEnd*60 && e.minute + e.duration > rangeStart*60)
                    .map(e => {
                        let minute = Math.max(e.minute, rangeStart*60)
                        return Object.assign({}, e, {minute: minute,
                            duration: Math.min(e.minute + e.duration, rangeEnd*60)-minute})
                    })
                readonly property var cardLayout: visible ? cal.layoutCards(gridRecords, rangeStart*60,
                                                                              unit/60, timePadding, height-timePadding,
                                                                              win.compact ? 9 : 24) : ({})
                function timeY(minute) { return timePadding + (minute/60-rangeStart)*unit }
                function hourMinute(minute) {
                    return String(Math.floor(minute/60)).padStart(2,"0") + ":" + String(minute%60).padStart(2,"0")
                }
                function stamp(day, minute) {
                    if (minute !== 1440) return day + "T" + hourMinute(minute)
                    let parts = day.split("-").map(Number)
                    return Qt.formatDate(new Date(parts[0], parts[1]-1, parts[2]+1, 12), "yyyy-MM-dd") + "T00:00"
                }
                function dayAt(x) { return Math.floor((x-gutter)/dayWidth) }
                function minuteAt(y) {
                    let slot = ((y-timePadding)/unit+rangeStart)*4
                    return Math.max(rangeStart*60, Math.min(rangeEnd*60, Math.round(slot)*15))
                }
                property point pressPoint: Qt.point(0, 0)
                property int pressDay: -1
                onPressDayChanged: win.updatePause()
                onVisibleChanged: if (!visible) cancelGesture()
                property int dropDay: -1
                property int startMinute: 0
                property int dragMinute: 0
                property bool dragging: false
                property var movingEntry: null
                function startGesture(x, y, entry) {
                    let day = entry ? entry.day : dayAt(x)
                    if (day < 0 || day >= 7) return
                    win.hoveredEvent = null
                    pressPoint = Qt.point(x, y)
                    pressDay = dropDay = day
                    startMinute = dragMinute = entry ? minuteAt(y) : Math.min(rangeEnd*60-15, minuteAt(y))
                    movingEntry = entry
                }
                function trackGesture(x, y) {
                    if (pressDay < 0 || win.compact) return
                    if (!dragging && Math.hypot(x-pressPoint.x, y-pressPoint.y) < 8) return
                    dragging = true
                    dropDay = movingEntry ? dayAt(x) : pressDay
                    dragMinute = minuteAt(y)
                }
                function cancelGesture() {
                    pressDay = dropDay = -1
                    dragging = false
                    movingEntry = null
                }
                function finishGesture(x, y) {
                    if (pressDay < 0) return
                    trackGesture(x, y)
                    let wasDrag = dragging
                    let entry = movingEntry
                    let fromDay = pressDay
                    let targetDay = dropDay
                    let from = startMinute
                    let to = dragMinute
                    cancelGesture()
                    if (wasDrag && (targetDay < 0 || targetDay >= 7 || x < gutter || x > width || y < 0 || y > height)) return
                    if (entry) {
                        if (!wasDrag) {
                            let p = mapToItem(panel, x, y)
                            win.cardClicked(entry, p.x, p.y)
                        }
                        else {
                            let minutes = (targetDay-fromDay)*1440 + to-from
                            if (!minutes) return
                            let group = cal.moveCard(entry.id, entry.start, entry.end || "", minutes)
                            if (group.proposed) {
                                win.rescheduleGroup = group
                                win.mode = "reschedule"
                            }
                        }
                    } else {
                        if (wasDrag && from === to) to += 15
                        let start = Math.min(rangeEnd*60 - 15, wasDrag ? Math.min(from, to) : from)
                        let end = stamp(win.days[fromDay], wasDrag ? Math.max(from, to)
                                        : Math.min(start + 60, rangeEnd*60))
                        win.createAt(stamp(win.days[fromDay], start), end,
                                     mapToItem(panel, grid.gutter + (fromDay + 0.5) * grid.dayWidth,
                                               timeY(start)))
                    }
                }
                Rectangle {
                    x: grid.gutter
                    y: grid.timePadding
                    width: grid.width - x
                    height: grid.height - 2 * y
                    color: Theme.surface
                    Rectangle {
                        x: 5 * grid.dayWidth
                        width: 2 * grid.dayWidth
                        height: parent.height
                        color: Theme.weekend
                    }
                    Rectangle {
                        visible: win.viewingToday
                        x: win.todayIndex * grid.dayWidth
                        width: grid.dayWidth
                        height: parent.height
                        color: Theme.todayColumn
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    onPressed: m => grid.startGesture(m.x, m.y, null)
                    onPositionChanged: m => grid.trackGesture(m.x, m.y)
                    onReleased: m => grid.finishGesture(m.x, m.y)
                    onCanceled: grid.cancelGesture()
                }
                Repeater { model: grid.rangeEnd-grid.rangeStart+1
                    Item {
                        property int hour: grid.rangeStart+index
                        property bool boundary: index === 0 || hour === grid.rangeEnd
                        property bool major: boundary || (hour % grid.labelStep === 0 && index * grid.unit >= 16)
                        property bool showLabel: major && (boundary || (grid.rangeEnd-hour) * grid.unit >= 16)
                        y: grid.timeY(hour*60); width: grid.width; height: 1
                        Text { x: 0; y: -height/2; visible: showLabel; text: win.compact ? String(hour).padStart(2,"0") : String(hour).padStart(2,"0")+":00"; color: Theme.muted; font.pixelSize: 10; font.family: "Consolas" }
                        Rectangle { x: grid.gutter; width: parent.width-x; height: 1; visible: major || grid.unit >= 15; color: major ? Theme.line : Theme.gridLine }
                    }
                }
                Repeater { model: 8
                    Rectangle { x: grid.gutter+index*grid.dayWidth; y: grid.timePadding; width: 1; height: grid.height-2*grid.timePadding; color: Theme.gridLine }
                }
                Repeater {
                    model: grid.gridRecords
                    Rectangle {
                        id: card
                        objectName: "weekEvent"
                        z: 1
                        property var ev: modelData
                        readonly property real durationTop: Math.max(grid.timePadding, grid.timeY(ev.minute))
                        readonly property real durationHeight: Math.max(2, Math.min(
                            grid.timeY(ev.minute + ev.duration), grid.timeY(grid.rangeEnd * 60)) - durationTop - 1)
                        readonly property bool tiny: width < 56 || durationHeight < 21
                        activeFocusOnTab: visible
                        Keys.onReturnPressed: openDetails()
                        Keys.onSpacePressed: openDetails()
                        onActiveFocusChanged: {
                            if (activeFocus && win.mode === "") win.previewEvent(ev, card)
                            else if (win.hoveredEvent === ev) win.dismissPreview()
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: ev.title + " " + ev.start.replace("T", " ")
                        Accessible.onPressAction: openDetails()
                        function openDetails() { let p = card.mapToItem(panel, 0, 0); win.cardClicked(ev, p.x, p.y) }
                        readonly property var placement: grid.cardLayout[ev.id + ":" + ev.day]
                        readonly property real laneWidth: (grid.dayWidth-5)/(placement ? placement.lanes : 1)
                        visible: !!placement
                        x: grid.gutter + 3 + ev.day * grid.dayWidth + (placement ? placement.lane : 0) * laneWidth
                        y: placement ? placement.cardY : 0
                        width: laneWidth - Math.min(2, laneWidth/4)
                        height: placement ? placement.cardHeight : 0
                        color: "transparent"
                        opacity: grid.dragging && grid.movingEntry && grid.movingEntry.id === ev.id ? 0.38 : 1
                        Behavior on opacity { NumberAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
                        Rectangle {
                            objectName: "eventTimeSurface"
                            y: card.durationTop - card.y
                            width: card.width
                            height: card.durationHeight
                            radius: Math.min(Theme.cardRadius, height/2)
                            color: card.tiny ? win.eventColor(ev) : Theme.eventFill(ev)
                            border.width: card.activeFocus || (win.locatedId === ev.id && win.locatedDay === ev.day)
                                ? 2 : cardMouse.containsMouse && !card.tiny ? 1 : 0
                            border.color: win.eventColor(ev)
                            clip: true
                            Rectangle {
                                visible: !card.tiny
                                x: 3; y: 4; width: 2; height: Math.max(0, parent.height - 8)
                                radius: 1; color: win.eventColor(ev)
                            }
                            Column {
                                visible: !card.tiny
                                x: 9; y: card.durationHeight >= 39 ? 5 : 2
                                width: parent.width-14
                                spacing: 1
                                Text { width: parent.width; text: ev.title; textFormat: Text.PlainText; font.pixelSize: card.width >= 115 ? 14 : 12; font.weight: Font.DemiBold; font.strikeout: ev.done; elide: Text.ElideRight; color: ev.done ? Theme.muted : Theme.ink }
                                Text { objectName: "cardTime"; visible: card.durationHeight >= 39; width: parent.width; text: ScheduleTime.dayRange(ev.start, ev.end, win.days[ev.day]); font.pixelSize: 11; color: Theme.muted; elide: Text.ElideRight }
                                Text { visible: card.durationHeight >= 58 && !!ev.location; width: parent.width; text: ev.location; textFormat: Text.PlainText; color: Theme.muted; font.pixelSize: 11; elide: Text.ElideRight }
                            }
                        }
                        MouseArea {
                            id: cardMouse
                            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton
                            onEntered: { previewClose.stop(); cardDelay.restart() }
                            onExited: { cardDelay.stop(); win.dismissPreview() }
                            onPressed: m => {
                                cardDelay.stop()
                                let p = mapToItem(grid, m.x, m.y)
                                grid.startGesture(p.x, p.y, card.ev)
                            }
                            onPositionChanged: m => {
                                if (!pressed) return
                                let p = mapToItem(grid, m.x, m.y)
                                grid.trackGesture(p.x, p.y)
                            }
                            onReleased: m => {
                                let p = mapToItem(grid, m.x, m.y)
                                grid.finishGesture(p.x, p.y)
                            }
                            onCanceled: { grid.cancelGesture(); cardDelay.stop(); win.dismissPreview() }
                        }
                        Timer { id: cardDelay; interval: 220; onTriggered: if (cardMouse.containsMouse && !cardMouse.pressed && grid.pressDay < 0) win.previewEvent(card.ev,card) }
                    }
                }
                Rectangle {
                    id: dragPreview
                    objectName: "calendarDragPreview"
                    z: 3
                    readonly property var entry: grid.movingEntry
                    readonly property real begin: entry ? entry.minute + grid.dragMinute-grid.startMinute : Math.min(grid.startMinute, grid.dragMinute)
                    readonly property real end: entry ? begin + entry.duration : Math.max(grid.startMinute+ (grid.startMinute === grid.dragMinute ? 15 : 0), grid.dragMinute)
                    visible: grid.dragging && grid.dropDay >= 0 && grid.dropDay < 7
                    x: grid.gutter + grid.dropDay * grid.dayWidth + 3
                    y: grid.timeY(Math.max(grid.rangeStart*60, Math.min(grid.rangeEnd*60-15, begin)))
                    width: grid.dayWidth - 6
                    height: Math.max(12, Math.min(grid.timeY(grid.rangeEnd*60), grid.timeY(end))-y)
                    radius: 5
                    color: "#cfe3d8"
                    border.color: "#4a8066"
                    Label {
                        anchors.fill: parent
                        anchors.margins: 4
                        text: dragPreview.entry ? dragPreview.entry.title : grid.hourMinute(dragPreview.begin) + "–" + grid.hourMinute(dragPreview.end)
                        elide: Text.ElideRight
                        font.pixelSize: 11
                        color: "#2e5e49"
                    }
                }
                Rectangle {
                    visible: win.viewingToday && win.clock.getHours()+win.clock.getMinutes()/60 >= grid.rangeStart && win.clock.getHours()+win.clock.getMinutes()/60 <= grid.rangeEnd
                    x: grid.gutter + win.todayIndex*grid.dayWidth
                    y: grid.timeY(win.clock.getHours()*60+win.clock.getMinutes())
                    width: grid.dayWidth; height: 1; color: "#c18b65"
                    Rectangle { x: -2; y: -2; width: 5; height: 5; radius: 3; color: parent.color }
                }
            }
            PeriodStrip {
                id: latePeriod
                objectName: "latePeriod"
                visible: !win.agendaMode && (win.lateRecords.length > 0 || win.lateExpanded)
                Layout.fillWidth: true
                Layout.topMargin: win.compact ? -weekLayout.spacing : 0
                records: win.lateRecords
                gutter: grid.gutter
                label: "晚间"
                compact: win.compact
                boundary: 1320
                expanded: win.lateExpanded
                onToggleRequested: win.lateExpanded = !win.lateExpanded
            }
        }
        RowLayout {
            id: calendarActions
            z: 46
            visible: win.mode === ""
            readonly property bool small: win.compact || panel.height < 480
            readonly property int buttonDiameter: small ? 40 : 48
            readonly property int inset: small ? 12 : Math.min(28, Math.round(panel.width * 0.02))
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: inset
            spacing: small ? 7 : 9
            // Check against the full-height grid so reserving space cannot toggle the decision.
            readonly property bool reserveSpace: {
                if (win.agendaMode) return false
                if (latePeriod.visible) return true
                let gridTop = weekLayout.y + grid.y
                let fullHeight = panel.height - 12 - gridTop - 2 * grid.timePadding
                let scale = fullHeight / ((grid.rangeEnd - grid.rangeStart) * 60)
                let firstDay = grid.dayAt(x - weekLayout.x)
                return grid.gridRecords.some(entry => {
                    if (entry.day < firstDay) return false
                    let top = gridTop + grid.timePadding + (entry.minute - grid.rangeStart * 60) * scale
                    return top + Math.max(win.compact ? 9 : 24, entry.duration * scale) >= y - 4
                })
            }
            FloatingAction {
                objectName: "backTodayButton"
                visible: !win.viewingToday
                diameter: calendarActions.buttonDiameter
                hint: "回到今日议程"
                text: "今"
                onClicked: win.goToday()
            }
            FloatingAction {
                id: addButton
                objectName: "floatingAddButton"
                symbol: "plus"
                diameter: calendarActions.buttonDiameter
                hint: "添加"
                expanded: addMenu.visible
                onClicked: addMenu.open()
            }
        }
        WindowMenu {
            id: addMenu
            objectName: "addMenu"
            parent: addButton
            x: parent.width - width
            y: -height - 8
            margins: 8
            transformOrigin: Popup.BottomRight
            opensUp: true
            width: 160
            actions: [{action: "import", label: "导入通知", icon: "inbox"}, {action: "create", label: "新建日程", icon: "calendar"}]
            onVisibleChanged: { win.hoveredEvent = null; win.updatePause() }
            onChosen: action => {
                if (action === "import") win.mode = "import"
                else win.createAt(win.defaultStart(), "", addButton.mapToItem(panel, 0, 0))
            }
        }
        GlassSurface {
            id: eventPreview
            objectName: "eventPreview"
            z: 45
            property var entry: ({title:"", start:"", end:"", location:""})
            width: Math.min(280, panel.width-24)
            height: Math.max(0, Math.min(previewContent.implicitHeight + 28, panel.height - 24))
            x: Math.max(12, Math.min(win.previewX, panel.width-width-12))
            y: Math.max(12, Math.min(win.previewY, panel.height-height-12))
            visible: opacity > 0
            enabled: win.hoveredEvent !== null
            opacity: win.hoveredEvent && win.mode === "" && !desk.collapsed ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: desk.motionEnabled ? Theme.menuReveal : 0 } }
            bottomTint: "#f5f7f3"
            color: Theme.surface
            SurfaceShadow { radius: eventPreview.radius }
            Rectangle { x: 5; y: 12; width: 3; height: parent.height-24; radius: 2; color: win.eventColor(eventPreview.entry) }
            ScrollView {
                anchors.fill: parent
                anchors.margins: 14
                clip: true
                contentWidth: availableWidth
                Column {
                    id: previewContent
                    width: parent.width
                    spacing: 8
                    Text { width: parent.width; text: eventPreview.entry.title; textFormat: Text.PlainText; color: Theme.ink; font.pixelSize: 14; font.bold: true; wrapMode: Text.WrapAnywhere }
                    Text { width: parent.width; text: ScheduleTime.range(eventPreview.entry.start, eventPreview.entry.end, true) + (eventPreview.entry.done ? " · 已完成" : ""); font.pixelSize: 11; color: Theme.muted; wrapMode: Text.Wrap }
                    Text { width: parent.width; visible: !!eventPreview.entry.location; text: eventPreview.entry.location; textFormat: Text.PlainText; font.pixelSize: 12; color: Theme.muted; wrapMode: Text.WrapAnywhere }
                }
            }
            HoverHandler { id: previewHover; onHoveredChanged: if (hovered) previewClose.stop(); else win.dismissPreview() }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: win.cardClicked(eventPreview.entry, eventPreview.x, eventPreview.y) }
        }
        Loader {
            anchors.fill: parent
            active: win.mode === "api"
            sourceComponent: Component {
                APISettings { onDismissed: win.closeSheet(); onSaved: win.returnFromAPI() }
            }
        }
        Loader {
            anchors.fill: parent
            id: eventSheet
            active: ["detail","edit","delete","rowEdit","reschedule"].includes(win.mode)
            sourceComponent: win.mode==="detail" ? details : win.mode==="delete" ? deletion : win.mode==="reschedule" ? rescheduling : editing
        }
        Component { id: details
            Sheet { id: detailSheet; heading: "日程详情"; sheetWidth: 660; originX:win.originX; originY:win.originY; onDismissed:win.closeSheet()
                EventDetails {
                    Layout.fillWidth: true
                    item: win.current
                    related: win.related
                    ancestors: cal.ancestors(win.current.id)
                    onOpenRelated: entry => {
                        win.locateEntry(entry, entry.start.slice(0, 10), win.detailReturnMode)
                        showSource = false
                        detailSheet.scrollToTop()
                    }
                }
                actions: Flow {
                    width: parent.width
                    spacing: 6
                    PlanButton { text:win.current.series ? "编辑本次" : "编辑"; accent:true; onClicked:win.mode="edit" }
                    PlanButton {
                        text: "一起改期"
                        visible: win.related.some(item => !item.done)
                        onClicked: {
                            win.rescheduleGroup = cal.scheduleGroup(win.current.id)
                            if (win.rescheduleGroup.entries.length > 1) win.mode = "reschedule"
                        }
                    }
                    PlanButton { text:win.current.done ? "恢复待办" : "标记完成"; onClicked:if(cal.manual(win.current.id,JSON.stringify({done:!win.current.done}),false))win.mode="" }
                    PlanButton { text:win.current.series ? "取消本次" : "删除"; onClicked:win.mode="delete" }
                }
            }
        }
        Component { id:deletion
            Sheet {
                id: deleteSheet
                property var plan: cal.deletionPlan(win.current.id)
                readonly property bool hasRelated: plan.related.length > 0
                readonly property bool isOccurrence: !!win.current.series
                heading: (isOccurrence ? "取消本次「" : "删除「") + (plan.title || win.current.title) + "」？"
                onDismissed: win.closeSheet()
                function save(deleteRelated) {
                    if (cal.deletePlanned(win.current.id, plan.snapshot, deleteRelated)) win.mode = ""
                    else plan = cal.deletionPlan(win.current.id)
                }
                Label {
                    visible: deleteSheet.isOccurrence
                    Layout.fillWidth: true
                    text: (deleteSheet.plan.start || win.current.start || "").replace("T", " ")
                    color: "#5a6f5d"
                }
                Label {
                    visible: deleteSheet.hasRelated
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: "#5a6f5d"
                    text: (deleteSheet.isOccurrence ? "仅取消本次" : "仅删除此项")
                          + "会保留以下事项。连同关联事项删除会将它们一并删除。"
                }
                Repeater {
                    model: deleteSheet.plan.related
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        textFormat: Text.PlainText
                        text: modelData.title + (modelData.parent === win.current.id
                              ? (deleteSheet.isOccurrence ? " · 仅取消本次时解除关联" : " · 仅删除此项时解除关联")
                              : " · 随所属任务保留")
                        color: "#294d3d"
                    }
                }
                actions: Flow {
                    width: parent.width
                    spacing: 6
                    PlanButton { text: "取消"; quiet: true; onClicked: win.closeSheet() }
                    PlanButton {
                        text: deleteSheet.isOccurrence ? "仅取消本次" : deleteSheet.hasRelated ? "仅删除此项" : "确认删除"
                        danger: !deleteSheet.hasRelated
                        enabled: !!deleteSheet.plan.snapshot
                        onClicked: deleteSheet.save(false)
                    }
                    PlanButton {
                        visible: deleteSheet.hasRelated
                        text: "连同关联事项删除"
                        danger: true
                        enabled: !!deleteSheet.plan.snapshot
                        onClicked: deleteSheet.save(true)
                    }
                }
            }
        }
        Component { id:rescheduling
            RescheduleSheet {
                entries: win.rescheduleGroup.entries
                snapshot: win.rescheduleGroup.snapshot
                proposed: win.rescheduleGroup.proposed || ({})
                onDismissed: win.closeSheet()
                onSaved: win.mode = ""
            }
        }
        Component { id:editing
            Sheet {
                heading: win.mode === "rowEdit" ? "编辑草稿项" : win.current.series ? "编辑本次日程" : win.current.id ? "编辑日程" : "新建日程"
                compactHeading: true
                anchored: win.mode === "edit" && win.anchorEditor
                sheetWidth: 520
                originX: win.originX
                originY: win.originY
                onDismissed: win.closeSheet()
                readonly property alias datePickerOpen: form.datePickerOpen
                readonly property alias dropdownOpen: form.dropdownOpen
                EventForm {
                    id: form
                    Layout.fillWidth: true
                    item: win.current
                    allowLinks: true
                    allowRepeat: win.mode === "edit" && !win.current.id
                    linkTargets: win.mode === "rowEdit" ? win.draft.linkTargets || [] : cal.linkTargets
                }
                actions: RowLayout {
                    Item { Layout.fillWidth: true }
                    PlanButton { text: "取消"; quiet: true; onClicked: win.closeSheet() }
                    PlanButton {
                        text: "保存"
                        accent: true
                        implicitWidth: 84
                        enabled: form.linkResolved
                        onClicked: {
                            if (!form.validateInput()) return
                            let fields = form.values()
                            if (win.mode === "rowEdit") win.saveDraftRow(fields)
                            else if (form.repeatWeeks > 0) {
                                if (cal.createSeries(JSON.stringify(fields), form.repeatWeeks, form.repeatEnd))
                                    win.mode = ""
                            }
                            else if (cal.manual(win.current.id, JSON.stringify(fields), false)) win.mode = ""
                        }
                    }
                }
            }
        }
        Loader {
            anchors.fill: parent
            active: win.mode === "search" || win.mode === "reminders"
            sourceComponent: win.mode === "search" ? searchPanel : remindersPanel
        }
        Component {
            id: searchPanel
            SearchSheet {
                initialFilters: win.searchFilters
                onDismissed: win.closeSheet()
                onOpenResult: (entry, day, filters) => {
                    win.searchFilters = filters
                    win.locateEntry(entry, day, "search")
                }
            }
        }
        Component {
            id: remindersPanel
            ReminderSheet {
                onDismissed: win.closeSheet()
                onOpenEntry: entry => win.locateEntry(entry, entry.start.slice(0, 10), "reminders")
            }
        }
        Loader {
            id: workflowSheet
            anchors.fill: parent
            sourceComponent: {
                switch (win.mode) {
                case "import": return inputSheet
                case "inbox": return inboxSheet
                case "review": return reviewSheet
                case "discard": return discardSheet
                case "deadlines": return deadlineSheet
                default: return null
                }
            }
        }
        Component { id:inputSheet
            NoticeComposer {
                draggingAttachment: noticeDrop.containsDrag
                onDismissed: win.closeSheet()
                onSubmitted: (key, parsing) => {
                    if (win.mode !== "import") return
                    if (parsing) win.openDraft(key)
                    else win.mode = "inbox"
                }
            }
        }
        Component { id: deadlineSheet
            Sheet {
                heading: "截止事项 · " + ScheduleTime.dateLabel(win.days[win.deadlineDay])
                onDismissed: win.closeSheet()
                AgendaList {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(360, Math.max(70, contentHeight))
                    day: win.days[win.deadlineDay]
                    entries: win.deadlines[win.deadlineDay]
                    onOpenItem: entry => win.openEntry(entry)
                }
            }
        }
        Component { id:inboxSheet
            Sheet { heading:"通知草稿"; onDismissed:win.closeSheet()
                Label { visible: inbox.pending.length === 0; text: "暂无通知草稿。"; color: Theme.muted }
                Repeater {
                    model: inbox.pending
                    Button {
                        id: draftCard
                        required property var modelData
                        readonly property bool attention: ["待补充", "解析失败", "待设置 API"].includes(modelData.status)
                        Layout.fillWidth: true
                        padding: 10
                        hoverEnabled: true
                        Accessible.name: modelData.status + " " + modelData.source
                        onClicked: win.openDraft(modelData.id)
                        background: Rectangle {
                            radius: Theme.controlRadius
                            color: draftCard.hovered ? Theme.tint : Theme.field
                            border.color: draftCard.visualFocus ? Theme.pine : Theme.line
                        }
                        contentItem: RowLayout {
                            spacing: 8
                            Label {
                                Layout.fillWidth: true
                                text: draftCard.modelData.source.replace(/\s+/g, " ").trim()
                                textFormat: Text.PlainText
                                color: Theme.ink
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Label {
                                text: draftCard.modelData.status
                                color: draftCard.attention ? Theme.warning : Theme.pineDark
                                font.pixelSize: 11
                                padding: 5
                                background: Rectangle {
                                    radius: 5
                                    color: draftCard.attention ? Theme.warningSurface : Theme.tint
                                }
                            }
                            AppIcon { name: "chevron-right"; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                        }
                    }
                }
            }
        }
        Component { id:reviewSheet
            Review { draft:win.draft; onDismissed:win.closeSheet(); onLeave:if (win.mode === "review") win.mode=""
                onEditItem:function(e){win.current=e;win.mode="rowEdit"}
                onReload:win.draft=inbox.draft(win.draft.id)
                onDiscardRequested:win.mode="discard"
            }
        }
        Component { id:discardSheet
            Sheet {
                id: discardForm
                readonly property bool partial: !!(win.draft.confirmed && win.draft.confirmed.length)
                heading: partial ? "放弃剩余草稿？" : "放弃这份草稿？"
                onDismissed: win.openDraft(win.draft.id)
                actions: RowLayout {
                    Item { Layout.fillWidth: true }
                    PlanButton { text: "取消"; quiet: true; onClicked: win.openDraft(win.draft.id) }
                    PlanButton {
                        text: discardForm.partial ? "放弃剩余草稿" : "放弃草稿"
                        danger: true
                        onClicked: { inbox.discard(win.draft.id); win.mode="" }
                    }
                }
            }
        }
        Rectangle { visible:win.message!==""; anchors.bottom:parent.bottom; anchors.horizontalCenter:parent.horizontalCenter; anchors.bottomMargin:calendarActions.visible && (parent.width+width)/2 >= calendarActions.x ? calendarActions.inset + calendarActions.height + 6 : 12; z:20; radius:8; color:"#f02b4939"; width:Math.min(parent.width-32,Math.max(200,msg.implicitWidth+28)); height:msg.implicitHeight+20
            Text { id:msg; anchors.centerIn:parent; width:parent.width-24; text:win.message; textFormat: Text.PlainText; wrapMode:Text.Wrap; color:"white" }
            MouseArea {
                anchors.fill: parent
                enabled: win.reminderMessage && win.mode === ""
                cursorShape: Qt.PointingHandCursor
                onClicked: { win.message = ""; win.showReminders() }
            }
        }
    }
    ResizeBorder { anchors.fill: parent; visible: !desk.collapsed && !desk.maximized && !openingSurface.visible; z: 90 }
    component NoticeDrop: DropArea {
        anchors.fill: parent
        z: 100
        onEntered: drag => { drag.accepted = drag.hasUrls && drag.urls.length === 1 && (win.mode === "" || win.mode === "import") }
        onDropped: drop => {
            if (drop.hasUrls && drop.urls.length && win.attachNotice(drop.urls[0].toString()))
                drop.acceptProposedAction()
        }
    }
    NoticeDrop {}
}
