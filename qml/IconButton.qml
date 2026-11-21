import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Button {
    id: control
    property string symbol: ""
    property string hint: ""
    property bool accent: false
    implicitWidth: 32
    implicitHeight: 32
    padding: 6
    hoverEnabled: true
    Accessible.name: hint
    Hint {
        parent: control
        visible: control.hovered && control.hint.length > 0
        text: control.hint
    }
    contentItem: Item {
        scale: control.down && desk.motionEnabled ? 0.96 : 1
        Behavior on scale { NumberAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
        AppIcon {
            anchors.centerIn: parent
            width: 18; height: 18
            name: control.symbol
            ink: !control.enabled ? "#acb7a9" : control.accent ? "white" : control.checked ? Theme.pine : Theme.muted
            rotation: control.symbol === "pin" && !control.checked ? 35 : 0
            Behavior on rotation { NumberAnimation { duration: desk.motionEnabled ? Theme.menuReveal : 0 } }
        }
    }
    background: Rectangle {
        radius: Theme.controlRadius
        color: control.accent ? Theme.pine : control.down ? "#dce7df" : control.checked || control.hovered ? Theme.tint : "transparent"
        border.width: control.visualFocus ? 1 : 0
        border.color: Theme.pine
        Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    }
}
