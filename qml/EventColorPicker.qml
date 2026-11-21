import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

ColumnLayout {
    id: picker
    property string selected: "auto"
    property string kind: "event"
    spacing: 4
    Label { text: "日程颜色"; color: Theme.ink; font.pixelSize: 12 }
    Flow {
        Layout.fillWidth: true
        spacing: 5
        Repeater {
            model: Theme.eventColors
            Button {
                id: swatch
                required property var modelData
                readonly property bool automatic: modelData.key === "auto"
                readonly property bool selected: picker.selected === modelData.key
                objectName: "eventColor_" + modelData.key
                width: automatic ? 54 : 34
                height: 34
                padding: 0
                hoverEnabled: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.name
                Accessible.checked: selected
                onClicked: picker.selected = modelData.key
                Hint {
                    parent: swatch
                    visible: swatch.hovered || swatch.visualFocus
                    text: swatch.modelData.name
                }
                background: Rectangle {
                    color: swatch.hovered ? Theme.tint : "transparent"
                    radius: swatch.height / 2
                    border.color: swatch.visualFocus || swatch.selected ? Theme.pine : "transparent"
                }
                contentItem: Item {
                    Rectangle {
                        anchors.centerIn: parent
                        width: swatch.automatic ? 46 : 24
                        height: 24
                        radius: height / 2
                        color: swatch.automatic ? Theme.eventStyle({kind: picker.kind}).fill : swatch.modelData.accent
                        Row {
                            anchors.centerIn: parent
                            spacing: 2
                            Label {
                                visible: swatch.automatic
                                text: "默认"
                                color: Theme.ink
                                font.pixelSize: 11
                            }
                            AppIcon {
                                visible: swatch.selected
                                anchors.verticalCenter: parent.verticalCenter
                                width: swatch.automatic ? 12 : 16
                                height: width
                                name: "check"
                                ink: swatch.automatic ? Theme.pine : "white"
                            }
                        }
                    }
                }
            }
        }
    }
}
