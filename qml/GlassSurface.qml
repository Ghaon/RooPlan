import QtQuick
import "Theme.js" as Theme

Rectangle {
    id: surface
    property bool glass: desk.transparencyEnabled
    property color topTint: Theme.glassTop
    property color sheenTint: topTint
    property color bottomTint: Theme.glassBottom
    property color rim: Theme.glassRim
    radius: Theme.popupRadius
    color: Theme.paper
    border.color: Theme.line
    gradient: glass ? material : null
    Gradient {
        id: material
        GradientStop { position: 0; color: surface.topTint }
        GradientStop { position: 0.16; color: surface.sheenTint }
        GradientStop { position: 1; color: surface.bottomTint }
    }
    Rectangle {
        visible: surface.glass
        anchors.fill: parent
        anchors.margins: 1
        color: "transparent"
        border.color: surface.rim
        radius: Math.max(0, surface.radius - 1)
        topLeftRadius: Math.max(0, surface.topLeftRadius - 1)
        topRightRadius: Math.max(0, surface.topRightRadius - 1)
        bottomLeftRadius: Math.max(0, surface.bottomLeftRadius - 1)
        bottomRightRadius: Math.max(0, surface.bottomRightRadius - 1)
    }
}
