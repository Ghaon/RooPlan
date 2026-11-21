import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

ComboBox {
    id: combo
    implicitHeight: 36
    leftPadding: 10
    rightPadding: 29
    hoverEnabled: true
    contentItem: Text {
        text: combo.displayText
        font.pixelSize: 13
        color: Theme.ink
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }
    indicator: AppIcon {
        anchors.right: parent.right
        anchors.rightMargin: 9
        anchors.verticalCenter: parent.verticalCenter
        width: 15
        height: 15
        name: "chevron-down"
        rotation: combo.popup.visible ? 180 : 0
        Behavior on rotation { NumberAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    }
    background: Rectangle {
        radius: Theme.controlRadius
        color: combo.hovered || combo.down ? Theme.tint : Theme.surface
        border.color: combo.visualFocus || combo.down ? Theme.pine : Theme.line
        Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    }
    delegate: ItemDelegate {
        id: option
        required property int index
        width: ListView.view.width
        height: 32
        highlighted: combo.highlightedIndex === index
        text: combo.textAt(index)
        contentItem: Text {
            text: option.text
            font.pixelSize: 13
            color: Theme.ink
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 6
            color: option.highlighted || option.hovered ? Theme.tint : "transparent"
        }
    }
    popup: Popup {
        objectName: combo.objectName + "Popup"
        y: combo.height + 4
        width: combo.width
        margins: 8
        padding: 4
        implicitHeight: Math.min(228, choices.contentHeight + topPadding + bottomPadding)
        contentItem: ListView {
            id: choices
            clip: true
            model: combo.delegateModel
            currentIndex: combo.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: GlassSurface {
            bottomTint: "#f5f7f3"
            SurfaceShadow { radius: Theme.popupRadius }
        }
    }
}
