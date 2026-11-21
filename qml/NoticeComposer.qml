import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "Theme.js" as Theme

Sheet {
    id: composer
    heading: "导入通知"
    sheetWidth: 600
    property url attachment: ""
    property bool draggingAttachment: false
    readonly property bool hasAttachment: !!attachment.toString()
    readonly property bool canSubmit: noticeText.text.trim().length > 0 || hasAttachment
    readonly property bool popupOpen: imagePreview.visible
    signal submitted(string key, bool parsing)

    function submit(parsing) {
        let key = parsing ? inbox.submit(noticeText.text, attachment.toString())
                          : inbox.saveNotice(noticeText.text, attachment.toString())
        if (key) submitted(key, parsing)
    }

    Component.onCompleted: Qt.callLater(() => noticeText.forceActiveFocus())

    FileDialog {
        id: chooseImage
        nameFilters: ["截图 (*.png *.jpg *.jpeg)"]
        onAccepted: if (inbox.isScreenshot(selectedFile.toString())) composer.attachment = selectedFile
    }
    ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: composer.height < 450 ? 88 : 164
        clip: true
        contentWidth: availableWidth
        FormArea {
            id: noticeText
            objectName: "noticeInput"
            placeholderText: composer.draggingAttachment ? "松开鼠标添加截图" : "粘贴通知，或拖入截图"
            Accessible.name: "通知原文"
            padding: 12
            background: Rectangle {
                radius: Theme.controlRadius
                color: composer.draggingAttachment ? Theme.tint : Theme.field
                border.color: composer.draggingAttachment || noticeText.activeFocus ? Theme.pine : Theme.line
            }
        }
    }
    Button {
        id: addImage
        visible: !composer.hasAttachment
        text: "添加截图"
        hoverEnabled: true
        padding: 6
        leftPadding: 8
        rightPadding: 8
        onClicked: chooseImage.open()
        contentItem: RowLayout {
            spacing: 6
            AppIcon { Layout.preferredWidth: 17; Layout.preferredHeight: 17; name: "image"; ink: Theme.muted }
            Label { text: addImage.text; color: Theme.ink }
        }
        background: Rectangle {
            radius: Theme.controlRadius
            color: addImage.hovered ? Theme.tint : "transparent"
            border.color: addImage.visualFocus ? Theme.pine : "transparent"
        }
    }
    RowLayout {
        Layout.fillWidth: true
        visible: composer.hasAttachment
        spacing: 7
        Button {
            id: thumbnail
            Layout.fillWidth: true
            implicitHeight: 54
            padding: 6
            text: "查看截图"
            hoverEnabled: true
            onClicked: imagePreview.open()
            contentItem: RowLayout {
                spacing: 8
                Image {
                    objectName: "noticeAttachment"
                    Layout.preferredWidth: 48
                    Layout.fillHeight: true
                    source: composer.attachment
                    sourceSize.width: 144
                    sourceSize.height: 144
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
                Label { Layout.fillWidth: true; text: thumbnail.text; color: Theme.ink }
            }
            background: Rectangle {
                radius: Theme.controlRadius
                color: thumbnail.hovered ? Theme.tint : Theme.field
                border.color: thumbnail.visualFocus ? Theme.pine : "transparent"
            }
        }
        PlanButton { text: "更换"; quiet: true; Accessible.name: "更换截图"; onClicked: chooseImage.open() }
        IconButton { symbol: "close"; hint: "移除截图"; onClicked: composer.attachment = "" }
    }
    Popup {
        id: imagePreview
        objectName: "noticeImagePreview"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(parent.width - 24, 780)
        height: Math.min(parent.height - 24, 660)
        padding: 12
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#80202724" }
        background: GlassSurface { radius: Theme.sheetRadius; bottomTint: "#f5f7f3" }
        contentItem: ColumnLayout {
            RowLayout {
                Layout.fillWidth: true
                Label { Layout.fillWidth: true; text: "通知截图"; font.weight: Font.DemiBold; color: Theme.ink }
                IconButton { symbol: "close"; hint: "关闭截图"; onClicked: imagePreview.close() }
            }
            Image {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: imagePreview.visible ? composer.attachment : ""
                sourceSize.width: 1560
                sourceSize.height: 1320
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
        }
    }
    Label {
        Layout.fillWidth: true
        text: "解析时，通知会发送至已配置的 AI 服务。"
        wrapMode: Text.Wrap
        color: Theme.muted
        font.pixelSize: 11
    }
    actions: RowLayout {
        spacing: 8
        Item { Layout.fillWidth: true }
        PlanButton { text: "仅保存"; quiet: true; enabled: composer.canSubmit; onClicked: composer.submit(false) }
        PlanButton { text: "解析成草稿"; accent: true; enabled: composer.canSubmit; onClicked: composer.submit(true) }
    }
}
