import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme.js" as Theme

Sheet {
    id: settingsSheet
    heading: "AI 服务设置"
    sheetWidth: 480
    property var config: inbox.apiSettings
    signal saved()
    Label { text: "服务"; color: Theme.muted }
    FormSelect {
        id: provider
        Layout.fillWidth: true
        model: ["千问 · 阿里云百炼", "OpenAI 兼容服务"]
        currentIndex: settingsSheet.config.provider === "compatible" ? 1 : 0
        onActivated: {
            endpoint.text = currentIndex === 0 ? "https://dashscope.aliyuncs.com/compatible-mode/v1" : ""
            modelName.text = currentIndex === 0 ? "qwen3.8-flash" : ""
            apiKey.clear()
        }
    }
    Label { text: "模型名称"; color: Theme.muted }
    FormField { id: modelName; objectName: "modelInput"; Layout.fillWidth: true; text: settingsSheet.config.model }
    Label { text: "API 基础地址"; color: Theme.muted }
    FormField { id: endpoint; Layout.fillWidth: true; text: settingsSheet.config.base; placeholderText: "https://…/v1" }
    Label { text: "API Key"; color: Theme.muted }
    FormField {
        id: apiKey
        objectName: "apiKeyInput"
        Layout.fillWidth: true
        placeholderText: settingsSheet.config.hasKey ? "已保存密钥，留空继续使用" : "填写服务对应的 API Key"
        echoMode: TextInput.Password
        inputMethodHints: Qt.ImhHiddenText | Qt.ImhNoPredictiveText
        selectByMouse: true
    }
    Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: "密钥由 Windows 当前用户加密保存，重启后自动读取。"; color: Theme.muted; font.pixelSize: 11 }
    Label { visible: !!settingsSheet.config.error; text: settingsSheet.config.error; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.danger }
    actions: RowLayout {
        Item { Layout.fillWidth: true }
        PlanButton { text: "清除密钥"; quiet: true; visible: settingsSheet.config.hasKey; enabled: !inbox.busy; onClicked: if (inbox.clearAPIKey()) apiKey.clear() }
        PlanButton {
            objectName: "saveAPIButton"
            text: "保存设置"; accent: true; enabled: !inbox.busy
            onClicked: if (inbox.saveAPI(provider.currentIndex === 0 ? "qwen" : "compatible", endpoint.text, modelName.text, apiKey.text)) {
                apiKey.clear()
                settingsSheet.saved()
            }
        }
    }
}
