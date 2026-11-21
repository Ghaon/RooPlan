import QtQuick
import QtQuick.Controls
import "Theme.js" as Theme

Row {
    id: strip
    required property var records
    required property real gutter
    required property string label
    required property int boundary
    property bool expanded: false
    property bool compact: false
    property int anchorDay: -1
    readonly property int collapseDay: anchorDay >= 0 ? anchorDay : (records.length > 0 ? records[0].day : 0)
    signal toggleRequested()
    onExpandedChanged: if (!expanded) anchorDay = -1

    readonly property int chipHeight: 26

    Item {
        width: strip.gutter
        height: strip.chipHeight
        Text {
            visible: !strip.compact
            anchors.verticalCenter: parent.verticalCenter
            text: strip.label
            color: Theme.muted
            font.pixelSize: 11
        }
    }

    Repeater {
        model: 7
        delegate: Item {
            id: cell
            required property int index
            width: (strip.width - strip.gutter) / 7
            height: strip.chipHeight
            readonly property var entries: strip.records.filter(entry => entry.day === index)

            Button {
                id: chip
                objectName: (strip.boundary === 0 ? "earlyPeriodDay" : "latePeriodDay") + cell.index
                anchors.fill: parent
                anchors.leftMargin: 2
                anchors.rightMargin: 2
                visible: strip.expanded ? cell.index === strip.collapseDay : cell.entries.length > 0
                hoverEnabled: true
                padding: 2
                leftPadding: strip.compact ? 1 : 4
                rightPadding: strip.compact ? 1 : 4
                readonly property string dayName: "周" + "一二三四五六日"[cell.index]
                readonly property string firstTime: {
                    let first = cell.entries.reduce((minute, entry) => Math.min(minute, entry.minute), 1440)
                    first = Math.max(strip.boundary, first)
                    return String(Math.floor(first / 60)).padStart(2, "0") + ":" + String(first % 60).padStart(2, "0")
                }
                readonly property string summary: firstTime + " · " + cell.entries.length + " 项"
                readonly property string fullLabel: dayName + " " + summary
                readonly property string hintText: strip.expanded ? "收起" + dayName + strip.label + "时段"
                    : fullLabel + "，展开" + strip.label + "时段"
                text: strip.expanded ? "收起" : fullLabel
                Accessible.name: hintText
                onClicked: {
                    if (!strip.expanded) strip.anchorDay = cell.index
                    strip.toggleRequested()
                }

                contentItem: Row {
                    spacing: strip.compact ? 1 : 2
                    TextMetrics { id: shortMetrics; font: chipLabel.font; text: strip.expanded ? chip.text : chip.firstTime }
                    TextMetrics { id: fullMetrics; font: chipLabel.font; text: chip.fullLabel }
                    TextMetrics { id: summaryMetrics; font: chipLabel.font; text: chip.summary }
                    Text {
                        id: chipLabel
                        width: Math.max(0, parent.width - (chevron.visible ? chevron.width + parent.spacing : 0))
                        anchors.verticalCenter: parent.verticalCenter
                        font.pixelSize: strip.compact ? 10 : 11
                        color: Theme.ink
                        text: strip.expanded ? chip.text : fullMetrics.advanceWidth <= width ? chip.fullLabel
                            : summaryMetrics.advanceWidth <= width ? chip.summary : chip.firstTime
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignHCenter
                    }
                    AppIcon {
                        id: chevron
                        visible: shortMetrics.advanceWidth + width + parent.spacing <= parent.width
                        anchors.verticalCenter: parent.verticalCenter
                        width: 10
                        height: width
                        name: "chevron-down"
                        rotation: strip.expanded ? 180 : 0
                        ink: Theme.pine
                    }
                }
                background: Rectangle {
                    radius: Theme.controlRadius
                    color: chip.down ? "#dbe7df" : chip.hovered ? Theme.tint : Theme.surface
                    border.color: chip.visualFocus ? Theme.pine : Theme.line
                    Behavior on color { ColorAnimation { duration: desk.motionEnabled ? Theme.feedback : 0 } }
                }
                Hint {
                    parent: chip
                    visible: chip.hovered && chip.visible
                    text: chip.hintText
                }
            }
        }
    }
}
