import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from rooplan.calendar import Calendar
from rooplan.desktop import Desktop
from rooplan.store import Store


class FrozenDateTime(datetime):
    @classmethod
    def now(cls):
        return cls(2026, 11, 18, 12, 0)


class TodayTests(unittest.TestCase):
    def test_preview_prioritizes_active_event_and_orders_future_deadlines(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as temp, patch("rooplan.calendar.datetime", FrozenDateTime):
            folder = Path(temp)
            store = Store(folder / "test.db")
            key = store.new_draft("今日预览")
            store.propose_changes(key, [
                dict(fields=dict(title="上次截止", kind="deadline", start="2026-11-17T18:00")),
                dict(fields=dict(title="早会", start="2026-11-18T09:00", end="2026-11-18T10:00")),
                dict(fields=dict(title="午间会议", start="2026-11-18T11:30", end="2026-11-18T12:30")),
                dict(fields=dict(title="下午会议", start="2026-11-18T14:00")),
                dict(fields=dict(title="当日截止", kind="deadline", start="2026-11-18")),
            ])
            store.confirm(key)
            calendar = Calendar(store, Desktop(folder))
            calendar.timer.stop()
            preview = calendar.todayPreview()
            self.assertEqual([entry["title"] for entry in preview],
                             ["午间会议", "上次截止", "下午会议", "当日截止", "早会"])
            self.assertEqual(preview[0]["previewStatus"], "ongoing")
            self.assertEqual(preview[1]["previewStatus"], "overdue")
            self.assertNotIn("previewStatus", calendar.events[preview[0]["id"]])

    def test_today_includes_overnight_and_deadline_excludes_other_days(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as temp, patch("rooplan.calendar.datetime", FrozenDateTime):
            folder = Path(temp)
            store = Store(folder / "test.db")
            key = store.new_draft("测试安排")
            store.propose_changes(key, [
                dict(fields=dict(title="跨夜安排", start="2026-11-17T23:00", end="2026-11-18T08:00")),
                dict(fields=dict(title="今日会议", start="2026-11-18T10:00")),
                dict(fields=dict(title="今日截止", kind="deadline", start="2026-11-18T20:00")),
                dict(fields=dict(title="明日会议", start="2026-11-19T10:00")),
            ])
            store.confirm(key)
            calendar = Calendar(store, Desktop(folder))
            calendar.timer.stop()
            self.assertEqual([item["title"] for item in calendar.todayRecords],
                             ["跨夜安排", "今日会议", "今日截止"])
