import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Button {
    id: control
    property bool accent: false
    property bool danger: false
    property bool quiet: false
    hoverEnabled: true
    opacity: enabled ? 1 : 0.5
    implicitHeight: 34
    implicitWidth: Math.max(36, implicitContentWidth + 22)
    font.pixelSize: 13
    font.weight: accent || danger ? Font.DemiBold : Font.Medium
    contentItem: Text {
        text: control.text
        elide: Text.ElideRight
        font: control.font
        color: control.accent || control.danger ? "white" : Theme.ink
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
    }
    background: Rectangle {
        radius: Theme.controlRadius
        color: control.danger ? (control.down || control.hovered ? Theme.dangerDark : Theme.danger)
            : control.accent ? (control.down || control.hovered ? Theme.pineDark : Theme.pine)
            : control.down ? "#dbe7df" : control.hovered ? Theme.tint : control.quiet ? "transparent" : Theme.surface
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.pine : control.accent || control.danger ? color : control.quiet ? "transparent" : Theme.line
        Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    }
}
