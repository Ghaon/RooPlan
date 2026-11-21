import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Button {
    id: control
    required property string hint
    property string symbol: ""
    property bool expanded: false
    property int diameter: 44
    readonly property bool emphasized: hovered || expanded
    implicitWidth: diameter
    implicitHeight: diameter
    padding: 0
    hoverEnabled: true
    Accessible.name: hint
    Hint {
        parent: control
        text: control.hint
        visible: control.hovered && !control.expanded && !control.down
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    scale: down && desk.motionEnabled ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    background: GlassSurface {
        radius: width / 2
        color: control.down ? "#dce9e0" : control.emphasized ? Theme.tint : Theme.surface
        topTint: control.down ? "#f4e4efe7" : control.emphasized ? "#f8f3f9f4" : "#fafffffd"
        bottomTint: control.down ? "#efd5e6da" : control.emphasized ? "#efe0ede3" : "#edeef4ef"
        rim: "transparent"
        border.width: control.visualFocus ? 2 : 1
        border.color: control.visualFocus ? Theme.pine : control.emphasized ? "#adc9bb" : "#cadbd1"
        SurfaceShadow { radius: parent.radius; spread: 3 }
        Behavior on topTint { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
        Behavior on bottomTint { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
    }
    contentItem: Item {
        AppIcon {
            visible: control.symbol !== ""
            anchors.centerIn: parent
            width: Math.round(control.diameter * 0.6)
            height: width
            name: control.symbol
            ink: Theme.pine
            rotation: control.expanded ? 45 : 0
            Behavior on rotation { NumberAnimation { duration: desk.motionEnabled ? Theme.menuReveal : 0; easing.type: Easing.OutCubic } }
        }
        Text {
            visible: control.symbol === ""
            anchors.fill: parent
            text: control.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: Theme.pine
            font.pixelSize: Math.round(control.diameter * 0.4)
            font.weight: Font.DemiBold
        }
    }
}
