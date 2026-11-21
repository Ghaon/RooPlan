import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

TextArea {
    id: field
    padding: 10
    font.pixelSize: 13
    color: Theme.ink
    placeholderTextColor: "#697971"
    selectionColor: Theme.pine
    wrapMode: TextEdit.Wrap
    selectByMouse: true
    background: Rectangle {
        radius: Theme.controlRadius
        color: field.activeFocus ? Theme.surface : Theme.field
        border.color: field.activeFocus ? Theme.pine : Theme.line
        Behavior on border.color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    }
}
