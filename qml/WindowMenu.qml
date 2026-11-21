import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Popup {
    id: menu
    property bool maximized: false
    property bool opensUp: false
    property var actions: [
        {action: "maximize", label: menu.maximized ? "还原窗口" : "最大化", shortcut: ""},
        {action: "minimize", label: "最小化到任务栏", shortcut: ""},
        {action: "reset", label: "恢复默认大小", shortcut: "Ctrl+0"},
        {action: "separator"},
        {action: "search", label: "搜索日程", icon: "search", shortcut: "Ctrl+F"},
        {action: "reminders", label: menu.reminderCount ? "日程提醒  ·  " + menu.reminderCount : "日程提醒", icon: "bell", shortcut: ""},
        {action: "api", label: "AI 服务设置", icon: "settings", shortcut: ""},
        {action: "undo", label: "撤销上次变更", shortcut: ""},
        {action: "separator"},
        {action: "quit", label: "退出袋办", icon: "exit", shortcut: ""}
    ]
    signal chosen(string action)
    property int reminderCount: 0
    width: 220
    padding: 7
    focus: true
    modal: true
    Overlay.modal: Rectangle { color: "transparent" }
    popupType: Popup.Item
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: GlassSurface {
        bottomTint: "#f5f7f3"
        SurfaceShadow { radius: Theme.popupRadius }
        transform: Translate { y: menu.opensUp && desk.motionEnabled ? (1-menu.opacity) * 5 : 0 }
    }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: desk.motionEnabled ? Theme.menuReveal : 0 }
    }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: desk.motionEnabled ? 90 : 0 } }
    contentItem: Column {
        spacing: 2
        transform: Translate { y: menu.opensUp && desk.motionEnabled ? (1-menu.opacity) * 5 : 0 }
        Repeater {
            model: menu.actions
            delegate: Item {
                width: parent.width
                height: modelData.action === "separator" ? 9 : 34
                Rectangle {
                    visible: modelData.action === "separator"
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 8 }
                    height: 1; color: Theme.line
                }
                Button {
                    id: actionButton
                    objectName: "menuAction_" + modelData.action
                    anchors.fill: parent
                    visible: modelData.action !== "separator"
                    hoverEnabled: true
                    leftPadding: 11; rightPadding: 11
                    text: modelData.label || ""
                    Accessible.name: modelData.label || ""
                    contentItem: Item {
                        AppIcon {
                            id: actionIcon
                            visible: !!modelData.icon
                            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                            width: 16; height: 16
                            name: modelData.icon || ""
                            ink: modelData.action === "quit" ? Theme.danger : Theme.pine
                        }
                        Text {
                            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                            anchors.leftMargin: actionIcon.visible ? 25 : 0
                            text: modelData.label || ""
                            font.family: "Microsoft YaHei UI"; font.pixelSize: 12
                            color: modelData.action === "quit" ? Theme.danger : Theme.ink
                        }
                        Text {
                            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                            text: modelData.shortcut || ""
                            font.pixelSize: 10; color: Theme.muted
                        }
                    }
                    background: Rectangle {
                        radius: 7
                        color: actionButton.down ? "#dce7df" : actionButton.hovered || actionButton.visualFocus ? Theme.tint : "transparent"
                        border.color: actionButton.visualFocus ? Theme.pine : "transparent"
                        Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
                    }
                    onClicked: { menu.close(); menu.chosen(modelData.action) }
                }
            }
        }
    }
}
