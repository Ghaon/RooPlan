import QtQuick

Item {
    id: shadow
    anchors.fill: parent
    z: -1
    property real radius: 12
    property real spread: 7
    Repeater {
        model: 6
        Rectangle {
            required property int index
            readonly property real reach: shadow.spread * (index + 1) / 6
            x: -reach
            y: -reach / 2
            width: shadow.width + 2 * reach
            height: shadow.height + 2 * reach
            radius: shadow.radius + reach
            color: "#04202724"
            antialiasing: true
        }
    }
}
