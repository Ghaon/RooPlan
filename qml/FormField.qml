import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

TextField {
    id: field
    implicitHeight: 36
    leftPadding: 10
    rightPadding: 10
    font.pixelSize: 13
    color: Theme.ink
    placeholderTextColor: "#697971"
    selectionColor: Theme.pine
    selectByMouse: true
    hoverEnabled: true
    background: Rectangle {
        radius: Theme.controlRadius
        color: field.activeFocus ? Theme.surface : Theme.field
        border.color: field.activeFocus ? Theme.pine : field.hovered ? "#bccdc4" : Theme.line
        Behavior on border.color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    }
}
