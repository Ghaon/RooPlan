import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

Item {
    id: sheet
    property string heading
    property Component actions
    property real originX: width/2
    property real originY: height/2
    property real sheetWidth: 570
    property bool anchored: false
    property bool compactHeading: false
    default property alias contents: body.data
    signal dismissed
    function scrollToTop() { scroll.contentItem.contentY = 0 }
    anchors.fill: parent
    Rectangle {
        anchors.fill: parent
        color: box.atAnchor ? "#14202724" : "#40202724"
        opacity: box.progress
        MouseArea { anchors.fill: parent; onClicked: sheet.dismissed() }
    }
    Rectangle {
        id: box
        objectName: "sheetSurface"
        readonly property int margin: sheet.width < 500 ? 12 : 20
        readonly property int inset: sheet.width < 500 ? 14 : 22
        readonly property bool atAnchor: sheet.anchored && sheet.width >= 760 && sheet.height >= 480
        readonly property real anchorX: Math.max(margin, Math.min(sheet.originX, sheet.width-margin))
        readonly property real rightSpace: sheet.width - anchorX - margin
        readonly property real leftSpace: anchorX - margin
        readonly property bool opensRight: rightSpace >= leftSpace || rightSpace >= sheet.sheetWidth + 12
        width: Math.max(1, Math.min(sheet.width - 2*margin, sheet.sheetWidth,
            atAnchor ? (opensRight ? rightSpace : leftSpace)-12 : sheet.sheetWidth))
        height: Math.max(1, Math.min(sheet.height - 2*margin, sheetLayout.implicitHeight + 2*inset))
        property real progress: 0
        x: atAnchor ? (opensRight ? anchorX + 12 : anchorX - width - 12) : (sheet.width-width)/2
        y: (atAnchor ? Math.max(margin, Math.min(sheet.originY-28, sheet.height-height-margin))
            : (sheet.height-height)/2) + (desk.motionEnabled ? (1-progress) * 6 : 0)
        opacity: progress
        NumberAnimation on progress { from: 0; to: 1; duration: desk.motionEnabled ? Theme.reveal : 0; easing.type: Easing.OutCubic }
        radius: Theme.sheetRadius; color: Theme.surface; border.color: Theme.line
        SurfaceShadow { radius: box.radius; spread: 12 }
        GlassSurface {
            objectName: "sheetHeaderGlass"
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: box.inset + header.height + 4
            radius: 0
            topLeftRadius: box.radius - 1
            topRightRadius: topLeftRadius
            bottomTint: "#edf2ed"
            color: Theme.field
            border.width: 0
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        }
        MouseArea { anchors.fill: parent }
        ColumnLayout {
            id: sheetLayout
            anchors.fill: parent; anchors.margins: box.inset
            spacing: 10
            RowLayout { id: header; Layout.fillWidth: true
                spacing: 9
                Label { Layout.fillWidth: true; text: sheet.heading; elide: Text.ElideRight; color: Theme.ink; font.pixelSize: sheet.compactHeading ? 18 : 20; font.weight: Font.DemiBold }
                IconButton { text: "关闭"; symbol: "close"; hint: text; onClicked: sheet.dismissed() }
            }
            ScrollView {
                id: scroll
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: availableWidth
                Layout.preferredHeight: body.implicitHeight
                ColumnLayout { id: body; width: parent.width; spacing: 12 }
            }
            Rectangle { visible: actionBar.active; Layout.fillWidth: true; implicitHeight: 1; color: Theme.line }
            Loader {
                id: actionBar
                visible: active
                active: !!sheet.actions
                Layout.fillWidth: true
                sourceComponent: sheet.actions
            }
        }
    }
}

