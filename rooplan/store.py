import json
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager, nullcontext
from datetime import date, datetime, time, timedelta


def uid():
    return uuid.uuid4().hex


def dump(value):
    return json.dumps(value, ensure_ascii=False)


def stamp(value):
    return value.isoformat(timespec="minutes")


def moment(value):
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M")
        if stamp(parsed) != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        raise ValueError("请填写本地日期和时间，例如 2026-11-19T10:00。") from None


DEFAULTS = dict(title="", kind="event", start="", end=None, location="", notes="",
                parent=None, done=False, reminder=10, source="手动录入", before_meeting=False)
EDITABLE = (set(DEFAULTS) - {"source"}) | {"reminder_time"}
EVENT_COLORS = ("auto", "pine", "blue", "lilac", "amber", "rose", "graphite")
EDITABLE.add("color")


def calendar_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        raise ValueError("请填写日期，格式为 YYYY-MM-DD。") from None


def date_only(item):
    start = item["start"]
    return item["kind"] == "deadline" and isinstance(start, str) and len(start) == 10


def cutoff(item):
    """A date-only deadline expires when the following day starts."""
    if date_only(item):
        return datetime.combine(calendar_date(item["start"]), time()) + timedelta(days=1)
    return moment(item["start"])


def reminder_at(item):
    if item["done"]:
        return None
    if date_only(item):
        clock = item.get("reminder_time")
        return moment(f'{item["start"]}T{clock}') if clock else None
    if item["reminder"] >= 0:
        return moment(item["start"]) - timedelta(minutes=item["reminder"])
    return None


def check_color(fields):
    if fields.get("color", "auto") not in EVENT_COLORS:
        raise ValueError("请选择有效的日程颜色。")


def check_item(item):
    check_color(item)
    if not isinstance(item["title"], str) or not item["title"].strip():
        raise ValueError("请填写名称。")
    if item["kind"] not in ("event", "deadline", "prep"):
        raise ValueError("请选择活动、截止任务或准备时段。")
    try:
        begin = cutoff(item)
    except OverflowError:
        raise ValueError("截止日期超出支持范围。") from None
    if item["kind"] == "prep" and not item["end"]:
        raise ValueError("准备时段需要结束时间。")
    if item["kind"] == "deadline" and item["end"]:
        raise ValueError("截止任务只需要一个截止时间。")
    if item["end"] and moment(item["end"]) <= begin:
        raise ValueError("结束时间必须晚于开始时间。")
    if not item["end"] and not date_only(item) and begin >= datetime.max - timedelta(minutes=1):
        raise ValueError("日程时间超出支持范围。")
    if type(item["reminder"]) is not int or not -1 <= item["reminder"] <= 43200:
        raise ValueError("提醒提前量应为 -1（关闭）至 43200 分钟的整数。")
    if not all(isinstance(item[k], str) for k in ("location", "notes", "source")):
        raise ValueError("地点、要求和来源应为文字。")
    if type(item["done"]) is not bool or type(item["before_meeting"]) is not bool:
        raise ValueError("状态字段必须是布尔值。")
    if item["parent"] is not None and not isinstance(item["parent"], str):
        raise ValueError("关联项无效，请重新选择。")
    if date_only(item) and item.get("reminder_time"):
        try:
            moment(f'{item["start"]}T{item["reminder_time"]}')
        except ValueError:
            raise ValueError("请填写有效的提醒时间，格式为 HH:mm。") from None
    if not date_only(item) and item["reminder"] >= 0:
        try:
            begin - timedelta(minutes=item["reminder"])
        except OverflowError:
            raise ValueError("提醒时间超出支持范围。") from None


def interval(item):
    if date_only(item):
        end = cutoff(item)
        return end - timedelta(days=1), end
    start = moment(item["start"])
    return start, moment(item["end"]) if item["end"] else start + timedelta(minutes=1)


def link_problem(item, parent):
    if not item["parent"]:
        return ""
    if parent is None:
        return "找不到原关联项，请在「编辑」中重新选择关联项，或设为「无关联」。"
    allowed = {"prep": ("event", "deadline"), "deadline": ("event",)}
    if item["id"] == parent["id"] or parent["kind"] not in allowed.get(item["kind"], ()):
        return "关联类型无效，请在「编辑」中重新选择关联项。"
    try:
        if (item["kind"] == "prep" and not item["done"] and item["end"] and parent["start"]
                and moment(item["end"]) > cutoff(parent)):
            return "准备时段必须在关联活动或提交期限前结束。"
        if (item["before_meeting"] and parent["start"] and item["start"] and cutoff(item) > cutoff(parent)):
            return "会前提交的任务不能晚于会议开始，请核对日期或填写明确的截止时间。"
    except (ValueError, OverflowError):
        return "请核对事项和关联项的日期与时间。"
    return ""


def matching_event(item, events):
    def normalized(value):
        return "".join(unicodedata.normalize("NFKC", value).casefold().split())

    if not item or not item["start"]:
        return None
    title, location = normalized(item["title"]), normalized(item["location"])
    return next((event for event in events.values()
                 if event["kind"] == item["kind"] and event["start"] == item["start"]
                 and (not event["end"] or not item["end"] or event["end"] == item["end"])
                 and normalized(event["title"]) == title
                 and (not event["location"] or not location or normalized(event["location"]) == location)), None)


class Store:
    """Use a connection per operation, also when called from the agent thread."""
    def __init__(self, path):
        self.path = path
        with self.session() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY, at TEXT NOT NULL, fired INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, body TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'open', receipt TEXT);
            """)

        with self.session(True) as db:
            cols = {r[1] for r in db.execute("PRAGMA table_info(drafts)")}
            for name, spec in (("attachment", "TEXT"), ("supplement", "TEXT DEFAULT ''"),
                               ("applied_order", "INTEGER"), ("origin", "TEXT")):
                if name not in cols:
                    db.execute(f"ALTER TABLE drafts ADD COLUMN {name} {spec}")
            if "snoozed_until" not in {r[1] for r in db.execute("PRAGMA table_info(reminders)")}:
                db.execute("ALTER TABLE reminders ADD COLUMN snoozed_until TEXT")
                # Legacy delivered reminders did not have an inbox or a dismiss action.
                db.execute("UPDATE reminders SET fired=2 WHERE fired=1")

    @contextmanager
    def session(self, write=False):
        db = sqlite3.connect(self.path, timeout=8)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        finally:
            db.close()

    @staticmethod
    def snapshot(db):
        return {r[0]: json.loads(r[1]) for r in db.execute("SELECT id, body FROM events")}

    def all(self):
        with self.session() as db:
            return self.snapshot(db)

    def search_events(self, keyword="", date_from=None, date_to=None):
        first = date.fromisoformat(date_from) if date_from else None
        last = date.fromisoformat(date_to) if date_to else None
        if first and last and first > last:
            raise ValueError("起始日期不能晚于结束日期。")
        lower = datetime.combine(first, time()) if first else None
        upper = last.isoformat() if last else None
        keyword = keyword.strip().casefold()
        return sorted((e for e in self.all().values()
                       if keyword in (e["title"] + " " + e["location"]).casefold()
                       and (lower is None or interval(e)[1] > lower)
                       and (upper is None or e["start"][:10] <= upper)),
                      key=lambda e: (e["start"], e["title"]))

    def get_related_items(self, event_id, events=None):
        events = self.all() if events is None else events
        if event_id not in events:
            raise ValueError("找不到原活动，请重新查询。")
        ids = {event_id}
        while True:
            expanded = ids | {e["id"] for e in events.values() if e["parent"] in ids}
            if expanded == ids:
                break
            ids = expanded
        return [e for e in events.values() if e["id"] in ids and e["id"] != event_id]

    def find_free_slots(self, earliest, deadline, duration=60, day_start="08:00",
                        day_end="21:00", exclude_ids=None, *, events=None):
        first, last = moment(earliest), moment(deadline)
        if not 1 <= duration <= 1440 or (last-first).days > 366:
            raise ValueError("请将时长设在 1–1440 分钟内，搜索范围设在一年以内。")
        a, b = time.fromisoformat(day_start), time.fromisoformat(day_end)
        if a >= b:
            raise ValueError("可安排时段的结束时间必须晚于开始时间。")
        busy = sorted(interval(e) for e in (self.all() if events is None else events).values()
                      if e["kind"] != "deadline" and e["id"] not in (exclude_ids or []))
        day, slots = first.date(), []
        length = timedelta(minutes=duration)
        while day <= last.date() and len(slots) < 32:
            cursor = max(first, datetime.combine(day, a))
            stop = min(last, datetime.combine(day, b))
            for start, end in busy + [(stop, stop)]:
                if start >= stop:
                    start = stop
                while cursor + length <= start and len(slots) < 32:
                    slots.append({"start": stamp(cursor), "end": stamp(cursor+length)})
                    cursor += length
                if start == stop:
                    break
                cursor = max(cursor, end)
            day += timedelta(days=1)
        return slots

    def new_draft(self, source, attachment=None, *, db=None):
        key = uid()
        with (self.session(True) if db is None else nullcontext(db)) as db:
            db.execute("INSERT INTO drafts(id,source,body,attachment) VALUES(?,?,?,?)",
                       (key, source, dump(dict(rows=[], note="", choices=[])), attachment))
        return key

    def draft(self, key, db=None):
        if db is None:
            with self.session() as conn:
                return self.draft(key, conn)
        row = db.execute("SELECT * FROM drafts WHERE id=?", (key,)).fetchone()
        if not row:
            raise ValueError("未找到草稿。")
        return self.decode_draft(row)

    @staticmethod
    def decode_draft(row):
        return dict(id=row["id"], state=row["state"], source=row["source"],
                    attachment=row["attachment"], supplement=row["supplement"], **json.loads(row["body"]))

    def set_context(self, key, attachment=None, supplement=None):
        with self.session(True) as db:
            db.execute("""UPDATE drafts SET attachment=COALESCE(?,attachment),
                       supplement=COALESCE(?,supplement) WHERE id=? AND state='open'""",
                       (attachment, supplement, key))

    def append_item(self, key, fields):
        if not isinstance(fields, dict) or fields.keys() - EDITABLE:
            raise ValueError("草稿含有未知字段。")
        with self.session(True) as db:
            d = self.draft(key, db)
            entry = dict(DEFAULTS, id=uid(), source=d["source"])
            entry.update(fields)
            check_item(entry)
            d["rows"].append(dict(id=entry["id"], before=None, after=entry, selected=True, suggested=False))
            self.save_body(db, key, self.review_body(d, choices=[], failed=False, already_recorded=False))
        return entry

    def pending(self):
        with self.session() as db:
            return [self.decode_draft(row) for row in db.execute(
                "SELECT * FROM drafts WHERE state='open' ORDER BY rowid DESC")]

    def pending_count(self):
        with self.session() as db:
            return db.execute("SELECT COUNT(*) FROM drafts WHERE state='open'").fetchone()[0]

    def save_body(self, db, key, body):
        if not db.execute("UPDATE drafts SET body=? WHERE id=? AND state='open'",
                          (dump(body), key)).rowcount:
            raise ValueError("草稿已处理，请重新打开。")

    @staticmethod
    def review_body(draft, **changes):
        body = {name: draft[name] for name in ("rows", "note", "choices", "approvals", "failed", "already_recorded")
                if name in draft}
        return dict(body, **changes)

    @staticmethod
    def confirmed_rows(key, db):
        batches = db.execute("""SELECT receipt FROM drafts WHERE origin=? AND state='applied'
                                ORDER BY applied_order""", (key,))
        return [row for batch in batches for row in json.loads(batch["receipt"])]

    def annotate(self, key, note, choices=None, failed=False):
        with self.session(True) as db:
            d = self.draft(key, db)
            self.save_body(db, key, self.review_body(d, note=note, choices=choices or [], failed=failed,
                                                     already_recorded=False))

    def propose_changes(self, key, changes, note="", *, searched=None, series=None, db=None):
        """Local refs can link rows in the same proposal without invented database IDs."""
        if db is None and len(changes) > 80:
            raise ValueError("一次最多处理 80 项。")
        with (self.session(True) if db is None else nullcontext(db)) as db:
            d = self.draft(key, db)
            if self.confirmed_rows(key, db):
                raise ValueError("这份通知已部分确认，请编辑剩余草稿项。")
            events, rows = self.snapshot(db), []
            if searched is not None and any(events.get(ident) != item for ident, item in searched.items()):
                raise ValueError("原日程或关联事项已变化，请重新查询。")
            refs = {}
            for c in changes:
                if c.get("ref"):
                    if c["ref"] in refs or c["ref"] in events:
                        raise ValueError("草稿引用重复。")
                    refs[c["ref"]] = c.get("id") or uid()
            seen = set()
            unchanged = False
            for c in changes:
                key_id = c.get("id") or refs.get(c.get("ref")) or uid()
                if key_id in seen or (c.get("id") and key_id not in events):
                    raise ValueError("活动 ID 不存在或重复。")
                seen.add(key_id)
                old = events.get(key_id)
                fields = c.get("fields", {})
                if not isinstance(fields, dict) or fields.keys() - EDITABLE:
                    raise ValueError("草稿含有未知字段。")
                check_color(fields)
                after = dict(old or dict(DEFAULTS, id=key_id))
                after.update(fields)
                if series is not None:
                    after["series"] = series
                parent = after["parent"]
                if parent is not None and not isinstance(parent, str):
                    raise ValueError("关联项无效，请重新选择。")
                after["parent"] = refs.get(parent, parent) or None
                if not old or d["source"] != "手动录入":
                    after["source"] = d["source"]
                if c.get("delete"):
                    if not old:
                        raise ValueError("找不到待删除的活动。")
                    after = None
                else:
                    if parent and parent not in refs and parent not in events:
                        raise ValueError(f'「{after["title"]}」的关联项不存在。parent 必须使用同一批条目已定义的 ref 或已有日程 ID。')
                    if after.get("start"):  # incomplete notices are editable until confirmation
                        check_item(after)
                    if searched is not None and old and all(after.get(field) == old.get(field) for field in EDITABLE):
                        unchanged = True
                        continue
                rows.append(dict(id=key_id, before=old, after=after, selected=True,
                                 suggested=bool(c.get("suggested"))))
            matches = {}
            if d["source"] != "手动录入":
                proposed = {row["id"]: row["after"] for row in rows if row["after"]}
                deferred = set()
                for row in rows:
                    match = matching_event(row["after"], events) if row["before"] is None else None
                    if match:
                        matches[row["id"]] = match
                        deferred.add(row["id"])
                        deferred.update(item["id"] for item in self.get_related_items(row["id"], proposed))
                for row in rows:
                    if row["id"] in deferred:
                        row["selected"] = False
            already_recorded = not note and (
                (unchanged and not rows) or
                (bool(rows) and len(matches) == len(rows) and all(
                    not row["suggested"]
                    and all(not row["after"].get(field) or row["after"][field] == matches[row["id"]].get(field)
                            for field in ("end", "location", "notes"))
                    and matches.get(row["after"]["parent"], {}).get("id", row["after"]["parent"])
                    == matches[row["id"]]["parent"]
                    for row in rows))
            )
            if already_recorded:
                note = "日历中已有这份安排，可直接关闭或放弃草稿。"
            self.save_body(db, key, dict(rows=rows, note=note, choices=[], already_recorded=already_recorded))
            return self.draft(key, db)

    @staticmethod
    def rescheduled_items(rows):
        return [row["id"] for row in rows if row["selected"] and row["before"] and row["after"]
                and row["before"]["kind"] in ("event", "deadline")
                and any(row["before"][field] != row["after"][field] for field in ("start", "end"))]

    def edit(self, key, row_id, fields=None, selected=None, *, allow_related=False):
        with self.session(True) as db:
            d = self.draft(key, db)
            row = next((r for r in d["rows"] if r["id"] == row_id), None)
            if row is None and allow_related and fields is not None:
                events = self.snapshot(db)
                original = events.get(row_id)
                if original and not original["done"] and any(
                    any(item["id"] == row_id for item in self.get_related_items(ident, events))
                    for ident in self.rescheduled_items(d["rows"]) if ident in events
                ):
                    row = dict(id=row_id, before=original, after=dict(original), selected=True, suggested=False)
                    d["rows"].append(row)
            if row is None:
                raise ValueError("草稿项已变动，请重新打开。")
            if fields is not None:
                if fields.keys() - EDITABLE or row["after"] is None:
                    raise ValueError("无法编辑此项。")
                check_color(fields)
                row["after"].update(fields)
                row.pop("duplicate_approval", None)
            if selected is not None:
                row["selected"] = selected
                row.pop("duplicate_approval", None)
                if selected and d["source"] != "手动录入" and row["before"] is None:
                    match = matching_event(row["after"], self.snapshot(db))
                    if match:
                        row["duplicate_approval"] = match["id"]
                if not selected and row["before"] is None:
                    deferred = {row_id}
                    for item in self.get_related_items(row_id, {
                        candidate["id"]: candidate["after"] for candidate in d["rows"]
                        if candidate["after"] is not None
                    }):
                        deferred.add(item["id"])
                    for candidate in d["rows"]:
                        if candidate["id"] in deferred:
                            candidate["selected"] = False
            self.save_body(db, key, self.review_body(d, failed=False, already_recorded=False,
                                                     note="" if d.get("already_recorded") else d["note"]))

    @staticmethod
    def project(events, rows, *, verify=False):
        updated = events.copy()
        for row in rows:
            ident = row["id"]
            if verify and events.get(ident) != row["before"]:
                raise ValueError("原活动已被编辑，请重新生成草稿。")
            if row["after"] is None:
                updated.pop(ident, None)
            else:
                updated[ident] = row["after"]
        return updated

    @staticmethod
    def time_conflicts(events, touched):
        occupied = []
        for event in events.values():
            if event["kind"] == "deadline":
                continue
            try:
                start, end = interval(event)
            except (ValueError, OverflowError):
                continue  # Incomplete rows are allowed in the review preview.
            if start < end:
                occupied.append((start, end, event["id"]))
        occupied.sort()
        for index, (first_start, first_end, first_id) in enumerate(occupied):
            for following in range(index+1, len(occupied)):
                second_start, second_end, second_id = occupied[following]
                if second_start >= first_end:
                    break
                if first_id in touched or second_id in touched:
                    token = dump(sorted(((first_id, stamp(first_start), stamp(first_end)),
                                         (second_id, stamp(second_start), stamp(second_end)))))
                    yield first_id, second_id, stamp(second_start), stamp(min(first_end, second_end)), token

    def review_conflicts(self, draft, events):
        rows = [row for row in draft["rows"] if row["selected"]]
        touched = {row["id"] for row in rows}
        projected = self.project(events, rows)
        approvals = set(draft.get("approvals", []))
        approvals.update(pair[-1] for pair in self.time_conflicts(events, touched))
        conflicts = {}
        for first, second, start, end, token in self.time_conflicts(projected, touched):
            for ident, other in ((first, second), (second, first)):
                if ident in touched:
                    conflicts.setdefault(ident, []).append(dict(
                        title=projected[other]["title"], start=start, end=end,
                        token=token, approved=token in approvals))
        return conflicts

    def review(self, key):
        with self.session() as db:
            draft = self.draft(key, db)
            events = self.snapshot(db)
            draft["confirmed"] = self.confirmed_rows(key, db)
            draft["conflicts"] = self.review_conflicts(draft, events)
            selected = [row for row in draft["rows"] if row["selected"]]
            selected_ids = {row["id"] for row in selected}
            projected = self.project(events, selected)
            pending = {row["id"]: row for row in draft["rows"]}
            dependencies = {}
            for item in projected.values():
                ident, parent = item["id"], item["parent"]
                if ident not in selected_ids and parent not in selected_ids:
                    continue
                target = projected.get(parent)
                problem = link_problem(item, target)
                if not problem:
                    continue
                parent_row = pending.get(parent)
                if target is None and parent_row and parent_row["after"] and not parent_row["selected"]:
                    problem = f'请一并勾选「{parent_row["after"]["title"]}」。'
                if ident in selected_ids:
                    dependencies[ident] = problem
                if parent in selected_ids and parent != ident:
                    dependencies.setdefault(parent, f'请先处理「{item["title"]}」。{problem}')
            for row in draft["rows"]:
                if not row["selected"] and row["after"]:
                    parent = pending.get(row["after"]["parent"])
                    if parent and parent["before"] is None and parent["after"] and not parent["selected"]:
                        dependencies[row["id"]] = f'请与「{parent["after"]["title"]}」一并确认。'
            draft["dependencies"] = dependencies
            draft["duplicates"] = {}
            if draft["source"] != "手动录入":
                for row in draft["rows"]:
                    match = matching_event(row["after"], events) if row["before"] is None else None
                    if match:
                        draft["duplicates"][row["id"]] = dict(
                            item=match, approved=row.get("duplicate_approval") == match["id"])
            related = {}
            for ident in self.rescheduled_items(draft["rows"]):
                if ident not in events:
                    continue
                for item in self.get_related_items(ident, events):
                    proposed_item = projected.get(item["id"])
                    dependency = link_problem(proposed_item, projected.get(proposed_item["parent"])) if proposed_item else ""
                    related[item["id"]] = dict(
                        item, proposed=proposed_item if item["id"] in selected_ids else None,
                        changed=item["id"] in selected_ids, problem=dependency)
            draft["relatedReview"] = sorted(related.values(), key=lambda item: (item["start"], item["title"]))
            targets = self.project(events, [row for row in draft["rows"] if row["selected"] or row["after"]])
            draft["linkTargets"] = sorted((item for item in targets.values() if item["kind"] in ("event", "deadline")),
                                          key=lambda item: (item["start"] or "", item["title"]))
            return draft

    def approve_conflicts(self, key, ident, tokens):
        with self.session(True) as db:
            draft = self.draft(key, db)
            conflicts = self.review_conflicts(draft, self.snapshot(db)).get(ident, [])
            required = {conflict["token"] for conflict in conflicts if not conflict["approved"]}
            if not required or set(tokens) != required:
                raise ValueError("冲突时段有变化，请核对后再保留。")
            approvals = sorted(set(draft.get("approvals", [])) | required)
            self.save_body(db, key, self.review_body(draft, approvals=approvals))

    def validate(self, events, touched, approvals=()):
        for e in events.values():
            check_item(e)
            if e["id"] not in touched and e["parent"] not in touched:
                continue
            problem = link_problem(e, events.get(e["parent"]))
            if problem:
                raise ValueError(f'「{e["title"]}」{problem}')
        for first, second, start, _, token in self.time_conflicts(events, touched):
            if token not in approvals:
                raise ValueError(f'时间冲突：{events[first]["title"]} / {events[second]["title"]}（{start.replace("T", " ")}）。请处理重叠时段后重试。')

    @staticmethod
    def write_event(db, key, item):
        if item is None:
            db.execute("DELETE FROM events WHERE id=?", (key,))
            db.execute("DELETE FROM reminders WHERE id=?", (key,))
            return
        db.execute("INSERT OR REPLACE INTO events VALUES(?,?)", (key, dump(item)))
        at = reminder_at(item)
        if at is None:
            db.execute("DELETE FROM reminders WHERE id=?", (key,))
        else:
            db.execute("""INSERT INTO reminders(id,at) VALUES(?,?) ON CONFLICT(id) DO
                       UPDATE SET at=excluded.at,fired=0,snoozed_until=NULL WHERE at<>excluded.at""",
                       (key, stamp(at)))

    def confirm(self, key, *, db=None, keep_remaining=False, supplement=None, retain_note=False):
        with (self.session(True) if db is None else nullcontext(db)) as db:
            d = self.draft(key, db)
            if d["state"] == "applied":
                return 0, None
            rows = [r for r in d["rows"] if r["selected"]]
            if d["state"] != "open" or not rows or d["choices"]:
                raise ValueError("请选择候选活动并至少勾选一项有效变更。")
            events = self.snapshot(db)
            if d["source"] != "手动录入":
                for row in rows:
                    match = matching_event(row["after"], events) if row["before"] is None else None
                    if match and row.get("duplicate_approval") != match["id"]:
                        raise ValueError(f'日历中已有「{match["title"]}」，请先核对重复项。')
            touched = {row["id"] for row in rows}
            previous = {pair[-1] for pair in self.time_conflicts(events, touched)}
            self.validate(self.project(events, rows, verify=True), touched,
                          previous | set(d.get("approvals", [])))
            if previous:
                rows[0]["prior_conflicts"] = sorted(previous)
            for r in rows:
                reminder = db.execute("SELECT * FROM reminders WHERE id=?", (r["id"],)).fetchone()
                r["old_reminder"] = dict(reminder) if reminder else None
                self.write_event(db, r["id"], r["after"])
            remaining = [row for row in d["rows"] if not row["selected"]] if keep_remaining else []
            stays_open = bool(remaining or (retain_note and d["note"]))
            if stays_open or self.confirmed_rows(key, db):
                batch = self.new_draft(d["source"], db=db)
                db.execute("UPDATE drafts SET origin=? WHERE id=?", (key, batch))
                if supplement is not None:
                    db.execute("UPDATE drafts SET supplement=? WHERE id=?", (supplement, key))
                self.save_body(db, key, self.review_body(d, rows=remaining, approvals=[]))
                if not stays_open:
                    db.execute("UPDATE drafts SET state='applied' WHERE id=?", (key,))
                key = batch
            db.execute("""UPDATE drafts SET state='applied', receipt=?, applied_order=
                       (SELECT COALESCE(MAX(applied_order),0)+1 FROM drafts) WHERE id=?""", (dump(rows), key))
            return len(rows), len(remaining) if stays_open else None

    def apply_manual(self, changes, originals=None, *, series=None, db=None):
        with (self.session(True) if db is None else nullcontext(db)) as db:
            if originals is not None:
                events = self.snapshot(db)
                for change in changes:
                    ident = change["id"]
                    if ident not in originals or events.get(ident) != originals[ident]:
                        raise ValueError("日程在编辑期间发生变化，请重新打开后再改期。")
            key = self.new_draft("手动录入", db=db)
            self.propose_changes(key, changes, series=series, db=db)
            self.confirm(key, db=db)

    def create_series(self, fields, weeks, until):
        if not isinstance(fields, dict) or fields.keys() - EDITABLE or type(weeks) is not int or weeks not in (1, 2):
            raise ValueError("请选择每周或隔周重复，并填写日程。")
        template = dict(DEFAULTS, **fields)
        check_item(template)
        if template["parent"]:
            raise ValueError("请先创建重复日程，再为具体某次添加关联事项。")
        first = calendar_date(template["start"][:10])
        last = calendar_date(until)
        step = weeks * 7
        count = (last - first).days // step + 1
        if count < 2:
            raise ValueError("结束日期至少应包含下一次日程。")
        if count > 520:
            raise ValueError("一个系列最多包含 520 次日程，请提前结束日期。")
        date_deadline = date_only(template)
        start_time = None if date_deadline else moment(template["start"])
        end_time = moment(template["end"]) if template["end"] else None
        changes = []
        try:
            for index in range(count):
                offset = timedelta(days=index * step)
                start = (first + offset).isoformat() if date_deadline else stamp(start_time + offset)
                end = stamp(end_time + offset) if end_time else None
                changes.append({"fields": dict(fields, start=start, end=end)})
        except OverflowError:
            raise ValueError("重复后的日程时间超出支持范围。") from None
        self.apply_manual(changes, series=dict(id=uid(), weeks=weeks, until=until))

    def delete_event(self, ident, expected, delete_related):
        with self.session(True) as db:
            events = self.snapshot(db)
            related = self.get_related_items(ident, events)
            current = {item["id"]: item for item in related}
            current[ident] = events[ident]
            if current != expected:
                raise ValueError("日程或关联事项已变动，请核对后再删除。")
            changes = [dict(id=ident, delete=True)]
            if delete_related:
                changes.extend(dict(id=item["id"], delete=True) for item in related)
            else:
                changes.extend(dict(id=item["id"], fields=dict(parent=None, before_meeting=False))
                               for item in related if item["parent"] == ident)
            self.apply_manual(changes, db=db)

    def undo(self, key=None):
        with self.session(True) as db:
            batch = db.execute("SELECT id,receipt,origin FROM drafts WHERE state='applied' AND receipt IS NOT NULL " +
                               ("AND (id=? OR origin=?) " if key else "") +
                               "ORDER BY (applied_order IS NOT NULL) DESC, COALESCE(applied_order,rowid) DESC LIMIT 1",
                               (key, key) if key else ()).fetchone()
            if not batch:
                raise ValueError("没有可以撤销的变更。")
            rows, events = json.loads(batch["receipt"]), self.snapshot(db)
            touched = {row["id"] for row in rows}
            approvals = set(rows[0].get("prior_conflicts", []))
            approvals.update(pair[-1] for pair in self.time_conflicts(events, touched))
            for r in rows:
                if events.get(r["id"]) != r["after"]:
                    raise ValueError("活动已被后续修改，请先撤销后续变更。")
                if r["before"]:
                    events[r["id"]] = r["before"]
                else:
                    events.pop(r["id"], None)
            self.validate(events, touched, approvals)
            for r in rows:
                self.write_event(db, r["id"], r["before"])
                # A title or location edit does not undo a later snooze or dismissal.
                if r["before"] and r["after"] and reminder_at(r["before"]) == reminder_at(r["after"]):
                    continue
                db.execute("DELETE FROM reminders WHERE id=?", (r["id"],))
                if r["old_reminder"]:
                    previous = {"snoozed_until": None, **r["old_reminder"]}
                    if "snoozed_until" not in r["old_reminder"] and previous["fired"] == 1:
                        previous["fired"] = 2
                    db.execute("""INSERT INTO reminders(id,at,fired,snoozed_until)
                                  VALUES(:id,:at,:fired,:snoozed_until)""",
                               previous)
            db.execute("UPDATE drafts SET state='undone' WHERE id=?", (batch["id"],))
            if batch["origin"]:
                origin = self.draft(batch["origin"], db)
                remaining = [] if origin["state"] == "discarded" else origin["rows"]
                restored = [dict(id=row["id"], before=row["before"], after=row["after"],
                                 suggested=row["suggested"], selected=False) for row in rows]
                # A later draft item for the same event needs the fresh baseline too.
                remaining = [row for row in remaining if row["id"] not in touched]
                db.execute("UPDATE drafts SET state='open' WHERE id=?", (origin["id"],))
                self.save_body(db, origin["id"], self.review_body(origin, rows=restored + remaining, approvals=[]))

    def discard(self, key):
        with self.session(True) as db:
            db.execute("UPDATE drafts SET state='discarded' WHERE state='open' AND id=?", (key,))

    def due_reminders(self, now):
        # A reminder moves from scheduled (0) to the persistent inbox (1)
        # until it is snoozed or dismissed (2).
        with self.session(True) as db:
            rows = db.execute("""SELECT e.id,e.body FROM events e JOIN reminders r ON e.id=r.id
                              WHERE r.fired=0 AND COALESCE(r.snoozed_until,r.at)<=?
                              ORDER BY COALESCE(r.snoozed_until,r.at),e.id""",
                              (now.isoformat(timespec="seconds"),)).fetchall()
            db.executemany("UPDATE reminders SET fired=1 WHERE id=?", [(r[0],) for r in rows])
            return [json.loads(r[1]) for r in rows]

    def pending_reminders(self):
        with self.session() as db:
            return [json.loads(row[0]) for row in db.execute(
                """SELECT e.body FROM events e JOIN reminders r ON e.id=r.id
                   WHERE r.fired=1 ORDER BY COALESCE(r.snoozed_until,r.at) DESC,e.id""")]

    def handle_reminder(self, ident, snoozed_until=None):
        with self.session(True) as db:
            db.execute("""UPDATE reminders SET fired=?,snoozed_until=?
                          WHERE id=? AND fired=1""",
                       (0 if snoozed_until else 2, snoozed_until, ident))

