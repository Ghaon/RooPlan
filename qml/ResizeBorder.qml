import QtQuick

Item {
    id: border
    readonly property int cornerSize: 8
    readonly property int topSize: 4
    Repeater {
        model: [
            {edges: Qt.LeftEdge, cursor: Qt.SizeHorCursor},
            {edges: Qt.RightEdge, cursor: Qt.SizeHorCursor},
            {edges: Qt.TopEdge, cursor: Qt.SizeVerCursor},
            {edges: Qt.BottomEdge, cursor: Qt.SizeVerCursor},
            {edges: Qt.TopEdge | Qt.LeftEdge, cursor: Qt.SizeFDiagCursor},
            {edges: Qt.BottomEdge | Qt.RightEdge, cursor: Qt.SizeFDiagCursor},
            {edges: Qt.TopEdge | Qt.RightEdge, cursor: Qt.SizeBDiagCursor},
            {edges: Qt.BottomEdge | Qt.LeftEdge, cursor: Qt.SizeBDiagCursor}
        ]
        MouseArea {
            property bool leftSide: !!(modelData.edges & Qt.LeftEdge)
            property bool rightSide: !!(modelData.edges & Qt.RightEdge)
            property bool topSide: !!(modelData.edges & Qt.TopEdge)
            property bool bottomSide: !!(modelData.edges & Qt.BottomEdge)
            property bool corner: (leftSide || rightSide) && (topSide || bottomSide)
            x: rightSide ? border.width-width : leftSide ? 0 : border.cornerSize
            y: bottomSide ? border.height-height : topSide ? 0 : border.cornerSize
            width: leftSide || rightSide ? border.cornerSize : border.width-2*border.cornerSize
            height: topSide && !corner ? border.topSize
                : topSide || bottomSide ? border.cornerSize : border.height-2*border.cornerSize
            hoverEnabled: true
            cursorShape: modelData.cursor
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                let p = mapToGlobal(mouse.x, mouse.y)
                desk.resize(modelData.edges, p.x, p.y)
            }
            onReleased: desk.endResize()
            onCanceled: desk.cancelResizeGrab()
        }
    }
}
