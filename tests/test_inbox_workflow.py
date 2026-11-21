import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QUrl, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy

from rooplan.calendar import Calendar
from rooplan.desktop import Desktop
from rooplan.inbox import Inbox
from rooplan.store import Store, stamp


class InboxWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = QCoreApplication.instance() or QCoreApplication([])
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.store = Store(self.folder / "test.db")
        self.desk = Desktop(self.folder)
        self.calendar = Calendar(self.store, self.desk)
        self.calendar.timer.stop()

    def wait_for_idle(self, inbox):
        deadline = time.monotonic() + 5
        while inbox.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertFalse(inbox.busy)

    def test_three_notices_survive_failure_and_retry_without_duplicate_events(self):
        release = threading.Event()
        attempts = {}

        class Parser:
            def run(parser, key, **kwargs):
                source = self.store.draft(key)["source"]
                index = int(source[-1])
                attempts[key] = attempts.get(key, 0) + 1
                if index == 1 and not release.wait(5):
                    raise ValueError("测试超时")
                if index == 2 and attempts[key] == 1:
                    raise ValueError("模拟服务失败")
                self.store.propose_changes(key, [
                    dict(fields=dict(title=source, start=f"2026-11-21T1{index}:00"))
                ])

        inbox = Inbox(self.store, self.folder, self.calendar, factory=lambda store: Parser())
        notices = QSignalSpy(inbox.notice)
        try:
            keys = [inbox.submit(f"通知 {i}", "") for i in (1,2,3)]
            self.assertEqual({item["status"] for item in inbox.pending}, {"解析中", "排队中"})
            self.assertEqual(len(self.store.pending()), 3)
            self.assertFalse(inbox.run(keys[1], "", ""))
        finally:
            release.set()
            self.wait_for_idle(inbox)
        statuses = {item["id"]: item["status"] for item in inbox.pending}
        self.assertEqual([statuses[key] for key in keys], ["待确认", "解析失败", "待确认"])
        messages = [notices.at(i)[0] for i in range(notices.count())]
        self.assertEqual(sum("通知解析失败" in message for message in messages), 1)
        self.assertEqual(sum("通知已处理" in message for message in messages), 2)
        self.assertEqual(inbox.pendingCount, 3)
        self.assertEqual(inbox.draft(keys[1])["source"], "通知 2")
        self.assertTrue(inbox.confirm(keys[0]))
        self.assertTrue(inbox.confirm(keys[0]))
        self.assertTrue(inbox.run(keys[1], "", ""))
        self.wait_for_idle(inbox)
        self.assertTrue(inbox.confirm(keys[1]))
        self.assertTrue(inbox.confirm(keys[2]))
        self.assertEqual(inbox.pendingCount, 0)
        self.assertEqual({item["title"] for item in self.store.all().values()}, {"通知 1","通知 2","通知 3"})
        self.assertEqual(len(self.store.all()), 3)

    def test_reschedule_lists_linked_changes_and_alternatives_use_proposed_times(self):
        with patch("rooplan.inbox.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026,11,18,9,0)
            first = self.store.new_draft("原组会通知")
            self.store.propose_changes(first, [
                dict(ref="meeting", fields=dict(title="组会", start="2026-11-20T15:00")),
                dict(ref="deadline", fields=dict(title="交 PPT", kind="deadline", parent="meeting",
                                                start="2026-11-20T15:00", before_meeting=True)),
                dict(fields=dict(title="准备 PPT", kind="prep", parent="deadline",
                                 start="2026-11-20T13:00", end="2026-11-20T14:00")),
            ])
            self.store.confirm(first)
            ids = {item["kind"]: item["id"] for item in self.store.all().values()}
            change = self.store.new_draft("组会提前")
            self.store.propose_changes(change, [
                dict(id=ids["event"], fields=dict(start="2026-11-18T13:00")),
                dict(id=ids["deadline"], fields=dict(start="2026-11-18T13:00")),
                dict(fields=dict(title="答疑", start="2026-11-18T11:00", end="2026-11-18T12:00")),
            ])
            inbox = Inbox(self.store, self.folder, self.calendar)
            links = {item["kind"]: item for item in inbox.draft(change)["relatedReview"]}
            self.assertEqual(links["deadline"]["proposed"]["start"], "2026-11-18T13:00")
            self.assertIsNone(links["prep"]["proposed"])
            slots = inbox.alternatives(change, ids["prep"])
            self.assertTrue(slots)
            for slot in slots:
                self.assertLessEqual(slot["end"], "2026-11-18T13:00")
                self.assertTrue(slot["end"] <= "2026-11-18T11:00" or slot["start"] >= "2026-11-18T12:00")
                self.assertEqual(datetime.fromisoformat(slot["end"])-datetime.fromisoformat(slot["start"]), timedelta(hours=1))
            self.assertTrue(inbox.edit(change, ids["prep"], json.dumps(slots[-1])))
            self.assertTrue(inbox.confirm(change))
            self.assertEqual(self.store.all()[ids["prep"]]["start"], slots[-1]["start"])

    def test_replace_unreadable_screenshot_and_retry_in_same_draft(self):
        first = self.folder / "notice.png"
        clearer = self.folder / "clearer.png"
        image = QImage(32, 32, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        self.assertTrue(image.save(str(first)))
        image.fill(Qt.GlobalColor.darkGray)
        self.assertTrue(image.save(str(clearer)))
        attempts = []

        class Parser:
            def run(parser, key, *, image, supplement, **kwargs):
                attempts.append((Path(image).read_bytes(), supplement))
                if len(attempts) == 1:
                    self.store.annotate(key, "未能识读截图，请补充原文。")
                    return
                self.store.propose_changes(key, [
                    dict(fields=dict(title="读书会", start="2026-11-25T14:00", location="图书馆203"))
                ])

        inbox = Inbox(self.store, self.folder, self.calendar, factory=lambda store: Parser())
        key = inbox.submit("请加入日历", QUrl.fromLocalFile(str(first)).toString())
        self.wait_for_idle(inbox)
        self.assertEqual(inbox.draft(key)["status"], "待补充")
        supplement = "日期是下周三"
        self.assertTrue(inbox.replaceScreenshot(key, QUrl.fromLocalFile(str(clearer)).toString(), supplement))
        self.assertTrue(inbox.run(key, "", supplement))
        self.wait_for_idle(inbox)
        self.assertEqual(attempts, [(first.read_bytes(), ""), (clearer.read_bytes(), supplement)])
        self.assertEqual(inbox.pendingCount, 1)
        self.assertFalse(self.store.all())
        self.assertTrue(inbox.confirm(key))
        reopened = Store(self.store.path)
        self.assertEqual(len(reopened.all()), 1)
        saved = reopened.draft(key)
        self.assertIn("请加入日历", saved["source"])
        self.assertEqual(saved["supplement"], supplement)
        self.assertEqual(Path(saved["attachment"]).read_bytes(), clearer.read_bytes())

    def test_today_updates_for_overdue_items_without_refreshing_when_switching_week(self):
        with patch("rooplan.calendar.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2026,11,18,9)
            key = self.store.new_draft("截止测试")
            self.store.propose_changes(key, [
                dict(fields=dict(title="未提交", kind="deadline", start="2026-11-17T18:00")),
                dict(fields=dict(title="已提交", kind="deadline", start="2026-11-17T19:00", done=True)),
                dict(fields=dict(title="即将截止", kind="deadline", start="2026-11-18T10:00")),
            ])
            self.store.confirm(key)
            self.calendar.changed.emit()
            self.assertEqual([item["title"] for item in self.calendar.overdueRecords], ["未提交"])
            today = QSignalSpy(self.calendar.todayChanged)
            week = QSignalSpy(self.calendar.weekRecordsChanged)
            self.desk.week(1)
            self.assertEqual((today.count(), week.count()), (0,1))
            clock.now.return_value = datetime(2026,11,18,11)
            self.calendar.deliver()
            self.assertEqual(today.count(), 1)
            self.assertEqual([item["title"] for item in self.calendar.overdueRecords], ["未提交", "即将截止"])
