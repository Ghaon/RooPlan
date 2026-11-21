import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

ToolTip {
    id: hint
    delay: 500
    timeout: 3000
    horizontalPadding: 10
    verticalPadding: 6
    width: Math.min(290, implicitWidth)
    contentItem: Text {
        text: hint.text
        textFormat: Text.PlainText
        wrapMode: Text.WrapAnywhere
        color: "#ffffff"; font.pixelSize: 11
    }
    background: Rectangle { radius: 7; color: Theme.ink }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: desk.motionEnabled ? Theme.feedback : 0 } }
}
