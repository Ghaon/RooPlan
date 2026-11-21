import json
import sqlite3
from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from .store import DEFAULTS, cutoff, interval, moment, stamp


def records_by_day(events, days):
    if not days:
        return []
    first, last = min(days), max(days)
    midnights = [datetime.combine(date.fromisoformat(day), time()) for day in days]
    buckets = [[] for day in days]
    for item in events:
        # Stored dates are canonical ISO strings. Skip history before parsing times.
        if item["start"][:10] > last or (item["end"] or item["start"])[:10] < first:
            continue
        start, end = interval(item)
        for bucket, midnight in zip(buckets, midnights):
            tomorrow = midnight + timedelta(days=1)
            if start >= tomorrow or end <= midnight:
                continue
            visible_start = max(start, midnight)
            bucket.append(dict(item, minute=(visible_start-midnight).total_seconds()/60,
                               duration=(min(tomorrow, end)-visible_start).total_seconds()/60))
    for bucket in buckets:
        bucket.sort(key=lambda item: (item["start"], item["title"]))
    return buckets


def day_records(events, day):
    return records_by_day(events, [day])[0]


def week_records(events, days):
    return [dict(item, day=index)
            for index, bucket in enumerate(records_by_day(events, list(days)))
            for item in bucket]


def layout_cards(records, first_minute, scale, top, bottom, minimum_height):
    """Assign lanes using the same pixel bounds the calendar actually draws."""
    if bottom <= top:
        return []

    cards = []
    for day in range(7):
        spans = []
        for item in records:
            if item["day"] != day:
                continue
            height = min(bottom-top, max(minimum_height, item["duration"]*scale-2))
            y = max(top, min(bottom-height, top+(item["minute"]-first_minute)*scale))
            spans.append(dict(item, cardY=y, cardHeight=height))

        spans.sort(key=lambda card: (card["cardY"], card["cardHeight"]))
        group, lane_ends = [], []
        for card in spans:
            y = card["cardY"]
            if lane_ends and y >= max(lane_ends):
                cards.extend(dict(previous, lanes=len(lane_ends)) for previous in group)
                group, lane_ends = [], []
            lane = next((i for i, end in enumerate(lane_ends) if end <= y), len(lane_ends))
            end = y + card["cardHeight"]
            if lane == len(lane_ends):
                lane_ends.append(end)
            else:
                lane_ends[lane] = end
            group.append(dict(card, lane=lane))
        cards.extend(dict(card, lanes=len(lane_ends)) for card in group)
    return cards


class Calendar(QObject):
    changed = Signal()
    weekRecordsChanged = Signal()
    todayChanged = Signal()
    notice = Signal(str)
    reminder = Signal(str)
    remindersChanged = Signal()

    def __init__(self, store, desk):
        super().__init__()
        self.store = store
        self.desk = desk
        self.today = datetime.now().date()
        self.events = store.all()
        self._overdue = self.overdue_at(datetime.now())
        self._reminders = store.pending_reminders()
        self.changed.connect(self.refresh)
        desk.weekChanged.connect(self.weekRecordsChanged)
        self.timer = QTimer(self, interval=15000)
        self.timer.timeout.connect(self.deliver)
        self.timer.start()

    def refresh(self):
        self.events = self.store.all()
        self._overdue = self.overdue_at(datetime.now())
        self.weekRecordsChanged.emit()
        self.todayChanged.emit()
        self.refresh_reminders()

    def refresh_reminders(self):
        reminders = self.store.pending_reminders()
        if reminders != self._reminders:
            self._reminders = reminders
            self.remindersChanged.emit()

    @Property("QVariantList", notify=remindersChanged)
    def pendingReminders(self):
        return self._reminders

    @Slot(str, bool)
    def handleReminder(self, ident, snooze):
        until = datetime.now() + timedelta(minutes=10) if snooze else None
        try:
            self.store.handle_reminder(ident, until.isoformat(timespec="seconds") if until else None)
            self.refresh_reminders()
        except sqlite3.Error:
            self.notice.emit("暂时无法更新提醒，请稍后再试。")

    @Slot(str, str, str, result="QVariantMap")
    def search(self, keyword, date_from, date_to):
        try:
            first, last = date_from.strip(), date_to.strip()
            if any(value and date.fromisoformat(value).isoformat() != value for value in (first, last)):
                raise ValueError
            return {"entries": self.store.search_events(keyword, first, last)}
        except ValueError:
            return {"entries": [], "error": "请输入有效日期（YYYY-MM-DD），起始日期应早于或等于结束日期。"}
        except sqlite3.Error:
            return {"entries": [], "error": "暂时无法搜索日程，请稍后再试。"}

    @Property("QVariantList", notify=weekRecordsChanged)
    def records(self):
        return week_records(self.events.values(), self.desk.days)

    @Slot(int, int, result="QVariantMap")
    def monthMarkers(self, year, month):
        first = date(year, month, 1).toordinal()
        # Include the adjacent dates that a six-row month grid can display.
        lower = max(date.min.toordinal(), first - 7)
        upper = min(date.max.toordinal(), first + 41)
        marked = {}
        for item in self.events.values():
            start, end = interval(item)
            last = (end - timedelta(microseconds=1)).date().toordinal()
            for day in range(max(lower, start.date().toordinal()), min(upper, last) + 1):
                marked[date.fromordinal(day).isoformat()] = True
        return marked

    @Slot("QVariantList", float, float, float, float, float, result="QVariantMap")
    def layoutCards(self, records, first_minute, scale, top, bottom, minimum_height):
        return {f'{card["id"]}:{card["day"]}': card
                for card in layout_cards(records, first_minute, scale, top, bottom, minimum_height)}

    @Property("QVariantList", notify=todayChanged)
    def todayRecords(self):
        return day_records(self.events.values(), self.todayDate)

    @Slot(result="QVariantList")
    def todayPreview(self):
        now = datetime.now()
        overdue = [dict(item, previewStatus="overdue")
                   for item in reversed(self.overdue_at(now))]
        overdue_ids = {item["id"] for item in overdue}
        ongoing, upcoming, past = [], [], []
        for item in day_records(self.events.values(), str(now.date())):
            if item["id"] in overdue_ids:
                continue
            start, end = interval(item)
            if item["done"]:
                past.append(item)
            elif item["kind"] == "deadline":
                upcoming.append((cutoff(item), item))
            elif start > now:
                upcoming.append((start, item))
            elif now < end:
                ongoing.append(dict(item, previewStatus="ongoing"))
            else:
                past.append(item)
        upcoming.sort(key=lambda pair: pair[0])
        priority = ongoing + [item for _, item in upcoming]
        if priority:
            if not ongoing:
                priority[0] = dict(priority[0], previewStatus="next")
            return priority[:1] + overdue[:1] + priority[1:] + overdue[1:] + past[::-1]
        return overdue + past[::-1]

    @Property("QVariantList", notify=todayChanged)
    def overdueRecords(self):
        return self._overdue

    @Property("QVariantList", notify=changed)
    def linkTargets(self):
        return sorted(({"id": entry["id"], "kind": entry["kind"], "title": entry["title"],
                        "start": entry["start"]} for entry in self.events.values()
                       if entry["kind"] != "prep"), key=lambda item: item["start"])

    def overdue_at(self, now):
        return sorted((item for item in self.events.values()
                       if item["kind"] == "deadline" and not item["done"] and cutoff(item) <= now),
                      key=lambda item: item["start"])

    @Property(str, notify=todayChanged)
    def todayDate(self):
        return str(self.today)

    @Slot(str, result="QVariantMap")
    def blank(self, start):
        return dict(DEFAULTS, id="", start=start)

    @Slot(str, result="QVariantList")
    def related(self, ident):
        return self.store.get_related_items(ident, self.events) if ident in self.events else []

    @Slot(str, result="QVariantList")
    def ancestors(self, ident):
        item = self.events.get(ident)
        ancestors, visited = [], {ident}
        while item and item["parent"] not in visited:
            item = self.events.get(item["parent"])
            if item:
                ancestors.append(item)
                visited.add(item["id"])
        return ancestors

    @Slot(str, result="QVariantMap")
    def deletionPlan(self, ident):
        try:
            events = self.store.all()
            related = self.store.get_related_items(ident, events)
            expected = {item["id"]: item for item in related}
            entry = events[ident]
            expected[ident] = entry
            return dict(title=entry["title"], start=entry["start"], related=related,
                        snapshot=json.dumps(expected, ensure_ascii=False))
        except ValueError as exc:
            self.notice.emit(str(exc))
        except sqlite3.Error:
            self.notice.emit("暂时无法读取关联事项，请稍后再试。")
        return dict(title="", start="", related=[], snapshot="")

    @Slot(str, str, bool, result=bool)
    def deletePlanned(self, ident, snapshot, delete_related):
        try:
            self.store.delete_event(ident, json.loads(snapshot), delete_related)
        except (ValueError, TypeError) as exc:
            self.notice.emit(str(exc))
            return False
        except sqlite3.Error:
            self.notice.emit("暂时无法删除日程，请稍后再试。")
            return False
        self.changed.emit()
        return True

    @Slot(str, str, bool, result=bool)
    def manual(self, ident, fields, delete=False):
        try:
            return self.apply_manual([dict(id=ident or None, fields=json.loads(fields), delete=delete)])
        except (ValueError, TypeError) as exc:
            self.notice.emit(str(exc))
            return False

    @Slot(str, int, str, result=bool)
    def createSeries(self, fields, weeks, until):
        try:
            self.store.create_series(json.loads(fields), weeks, until)
        except (ValueError, TypeError) as exc:
            self.notice.emit(str(exc))
            return False
        except sqlite3.Error:
            self.notice.emit("暂时无法保存重复日程，请稍后再试。")
            return False
        self.changed.emit()
        return True

    def apply_manual(self, changes, originals=None):
        try:
            self.store.apply_manual(changes, originals)
        except sqlite3.Error:
            self.notice.emit("暂时无法保存日程，请稍后再试。")
            return False
        self.changed.emit()
        return True

    @Slot(str, result="QVariantMap")
    def scheduleGroup(self, ident):
        try:
            events = self.store.all()
            related = self.store.get_related_items(ident, events)
            entries = [events[ident], *(item for item in related if not item["done"])]
            return dict(entries=entries, snapshot=json.dumps(entries, ensure_ascii=False))
        except ValueError as exc:
            self.notice.emit(str(exc))
        except sqlite3.Error:
            self.notice.emit("暂时无法读取关联日程，请稍后再试。")
        return dict(entries=[], snapshot="")

    @Slot(str, str, result=bool)
    def reschedule(self, original_json, changes_json):
        try:
            originals = {item["id"]: item for item in json.loads(original_json)}
            changes = json.loads(changes_json)
            if not changes or any(set(change["fields"]) - {"start", "end"} for change in changes):
                raise ValueError("请至少调整一项日程的时间。")
            return self.apply_manual(changes, originals)
        except (ValueError, TypeError, KeyError) as exc:
            self.notice.emit(str(exc))
            return False

    @Slot(str, str, str, int, result="QVariantMap")
    def moveCard(self, ident, original_start, original_end, minutes):
        group = self.scheduleGroup(ident)
        if not group["entries"]:
            return {}
        entry = group["entries"][0]
        if entry["start"] != original_start or (entry["end"] or "") != original_end:
            self.notice.emit("日程在拖动期间发生变化，请重新操作。")
            return {}
        try:
            fields = {name: stamp(moment(entry[name]) + timedelta(minutes=minutes))
                      for name in ("start", "end") if entry[name]}
            if len(group["entries"]) > 1:
                return dict(group, proposed=fields)
            self.apply_manual([dict(id=ident, fields=fields)], {ident: entry})
        except (ValueError, OverflowError) as exc:
            self.notice.emit(str(exc))
        return {}

    @Slot(result=bool)
    def undo(self):
        try:
            self.store.undo()
            self.changed.emit()
            self.notice.emit("已撤销整批变更。")
            return True
        except ValueError as exc:
            self.notice.emit(str(exc))
            return False

    def deliver(self):
        now = datetime.now()
        overdue = self.overdue_at(now)
        if now.date() != self.today or overdue != self._overdue:
            self.today = now.date()
            self._overdue = overdue
            self.todayChanged.emit()
            self.desk.refresh_date(self.today)
        try:
            due = self.store.due_reminders(now)
            self.refresh_reminders()
        except sqlite3.Error:
            return
        if due:
            expired = sum((cutoff(e) if e["kind"] == "deadline" else interval(e)[1]) <= now
                          for e in due)
            if len(due) == 1 and not expired:
                self.reminder.emit(due[0]["start"].replace("T", " ") + "  " + due[0]["title"])
            else:
                summary = f"有 {len(due)} 条日程提醒"
                if expired:
                    summary += f"，其中 {expired} 条已过时间"
                self.reminder.emit(summary + "。可在「日程提醒」中查看。")

