.pragma library

function dateLabel(value) {
    if (!value) return "选择日期"
    let day = new Date(value + "T12:00:00")
    if (isNaN(day.getTime())) return value
    let currentYear = new Date().getFullYear()
    return (day.getFullYear() === currentYear ? "" : day.getFullYear() + "年")
        + (day.getMonth() + 1) + "月" + day.getDate() + "日 周" + "日一二三四五六"[day.getDay()]
}

function range(start, end, showDate) {
    if (!start) return ""
    let startDay = start.slice(0, 10)
    if (start.length === 10) return showDate ? startDay : "当日"
    let spansDays = end && end.slice(0, 10) !== startDay
    let label = (showDate || spansDays ? startDay + " " : "") + start.slice(11)
    if (end) label += "–" + (spansDays ? end.replace("T", " ") : end.slice(11))
    return label
}

function dayRange(start, end, day) {
    if (!end || start.slice(0, 10) === end.slice(0, 10)) return range(start, end, false)
    let from = start.slice(0, 10) === day ? start.slice(11) : "00:00"
    let to = end.slice(0, 10) === day ? end.slice(11) : "24:00"
    return from + "–" + to
}
