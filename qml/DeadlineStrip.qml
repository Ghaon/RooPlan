import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Row {
    id: strip
    property var days: []
    property bool compact: false
    signal openItem(var entry)
    signal openDay(int index)
    Repeater {
        model: strip.days
        Column {
            id: cell
            required property int index
            required property var modelData
            width: strip.width/7
            height: Math.max(1, implicitHeight)
            spacing: 2
            Repeater {
                model: cell.modelData.slice(0, strip.compact ? 1 : 2)
                delegate: Button {
                    required property var modelData
                    id: deadlineButton
                    objectName: "deadlineChip"
                    width: Math.max(1, cell.width-4)
                    height: 22
                    padding: 3
                    leftPadding: 11
                    hoverEnabled: true
                    readonly property string timeLabel: modelData.start.slice(11) || "当日"
                    text: timeLabel + " 截止 · " + modelData.title
                    Accessible.name: text
                    Hint {
                        parent: deadlineButton
                        visible: deadlineButton.hovered
                        text: deadlineButton.text
                    }
                    contentItem: Text {
                        text: strip.compact ? deadlineButton.timeLabel : deadlineButton.text
                        textFormat: Text.PlainText
                        color: Theme.warning
                        elide: Text.ElideRight
                        font.pixelSize: 11
                        font.strikeout: deadlineButton.modelData.done
                        horizontalAlignment: strip.compact ? Text.AlignHCenter : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: Theme.cardRadius
                        color: deadlineButton.hovered ? "#f4e8d8" : Theme.warningSurface
                        border.color: deadlineButton.visualFocus ? Theme.warning : "transparent"
                        Rectangle {
                            objectName: "deadlineColorMark"
                            anchors.left: parent.left
                            anchors.leftMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            width: 4; height: 4; radius: 2
                            color: Theme.eventAccent(deadlineButton.modelData)
                        }
                    }
                    onClicked: strip.openItem(modelData)
                }
            }
            PlanButton {
                objectName: "moreDeadlines"
                visible: cell.modelData.length > (strip.compact ? 1 : 2)
                width: Math.max(1, cell.width-4)
                height: 23
                text: (strip.compact ? "+" : "另有 ") + (cell.modelData.length-(strip.compact ? 1 : 2))
                Accessible.name: "查看当天所有截止事项"
                onClicked: strip.openDay(cell.index)
            }
        }
    }
}
