import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

Rectangle {
    id: box
    property string heading
    property color accentColor: "transparent"
    default property alias contents: body.data
    Layout.fillWidth: true
    implicitHeight: body.implicitHeight + 24
    color: Theme.field
    radius: Theme.controlRadius
    border.color: Theme.line
    ColumnLayout {
        id: body
        x: 12; y: 12; width: parent.width-24
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Rectangle {
                visible: box.accentColor.a > 0
                Layout.preferredWidth: 4
                Layout.preferredHeight: 15
                radius: 2
                color: box.accentColor
            }
            Label {
                Layout.fillWidth: true
                text: box.heading
                textFormat: Text.PlainText
                wrapMode: Text.WrapAnywhere
                font.weight: Font.DemiBold
                color: Theme.ink
                font.pixelSize: 13
            }
        }
    }
}
