.pragma library

var paper = "#f8f9f7"
var surface = "#ffffff"
var ink = "#202724"
var muted = "#59645f"
var line = "#dde3df"
var gridLine = "#ecefeb"
var field = "#f4f6f4"
var tint = "#eaf1ed"
var pine = "#246352"
var pineDark = "#194c42"
var warning = "#86501d"
var warningSurface = "#fff7eb"
var danger = "#a5433b"
var dangerDark = "#80332d"
var todayColumn = "#eef4ef"
var weekend = "#f6f7f4"
var glassTop = "#fffffc"
var glassBottom = "#e6eee7"
var glassRim = "#bfffffff"
var eventColors = [
    {key: "auto", name: "按类型默认"},
    {key: "pine", name: "松绿", fill: "#e1efe7", accent: "#327964"},
    {key: "blue", name: "雾蓝", fill: "#e7eef5", accent: "#50799a"},
    {key: "lilac", name: "丁香紫", fill: "#f0eaf7", accent: "#785da0"},
    {key: "amber", name: "沙金", fill: "#faedd8", accent: "#a66832"},
    {key: "rose", name: "玫瑰", fill: "#f7e7ea", accent: "#a34e64"},
    {key: "graphite", name: "石墨", fill: "#edeff1", accent: "#616a76"}
]
var eventPalette = ({
    pine: eventColors[1], blue: eventColors[2], lilac: eventColors[3],
    amber: eventColors[4], rose: eventColors[5], graphite: eventColors[6]
})

function eventStyle(entry) {
    entry = entry || {}
    let kind = entry.kind === "deadline" ? "amber" : entry.kind === "prep" ? "blue" : "pine"
    return eventPalette[entry.color] || eventPalette[kind]
}

function eventAccent(entry) {
    let accent = eventStyle(entry).accent
    return entry && entry.done ? Qt.lighter(accent, 1.24) : accent
}

function eventFill(entry) {
    return entry && entry.done ? "#edf0ee" : eventStyle(entry).fill
}
var cardRadius = 5
var controlRadius = 8
var popupRadius = 12
var sheetRadius = 16
var feedback = 100
var menuReveal = 140
var reveal = 180
