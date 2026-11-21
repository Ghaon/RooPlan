import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt, QUrl, QObject, QCoreApplication, QEvent, QMetaObject
from PySide6.QtQuick import QQuickWindow
from PySide6.QtGui import QGuiApplication, QImage, QMouseEvent, QWheelEvent
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QSignalSpy, QTest

from rooplan.calendar import Calendar
from rooplan.desktop import Desktop
from rooplan.inbox import Inbox
from rooplan.store import Store


def visual_items(item, name):
    found = [item] if item.objectName() == name else []
    for child in item.childItems():
        found.extend(visual_items(child, name))
    return found


class QmlInteractions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    @contextmanager
    def scene(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            desk = Desktop(folder)
            store = Store(folder / "test.db")
            calendar = Calendar(store, desk)
            inbox = Inbox(store, folder, calendar)
            engine = QQmlApplicationEngine()
            for name, obj in [("desk", desk), ("cal", calendar), ("inbox", inbox)]:
                engine.rootContext().setContextProperty(name, obj)
            engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / "qml/Main.qml")))
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            desk.attach(window)
            desk.timer.stop()
            try:
                yield window, desk, store, calendar
            finally:
                calendar.timer.stop()
                desk.preview_close.stop()
                desk.opening_timeout.stop()
                desk.hidePreview()
                desk.edge_window.close()
                window.close()
                self.app.removeEventFilter(desk)
                engine.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_week_label_and_border_mouse_drag(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(1000, 700)
            self.app.processEvents()
            label = window.findChild(QObject, "currentWeekLabel")
            self.assertTrue(label.property("visible"))
            desk.week(1)
            self.app.processEvents()
            self.assertFalse(label.property("visible"))
            desk.week(0)
            self.app.processEvents()
            self.assertTrue(label.property("visible"))
            with patch("rooplan.desktop.QCursor.pos", return_value=QPoint(500, 698)) as cursor:
                QTest.mousePress(window, Qt.MouseButton.LeftButton,
                                 Qt.KeyboardModifier.NoModifier, QPoint(500, 698))
                self.assertTrue(desk.resizing)
                cursor.return_value = QPoint(500, 598)
                QTest.mouseMove(window, QPoint(500, 598))
                self.assertEqual(window.height(), 600)
                QTest.mouseRelease(window, Qt.MouseButton.LeftButton,
                                   Qt.KeyboardModifier.NoModifier, QPoint(500, 598))
                self.assertFalse(desk.resizing)
                self.assertEqual(desk.settings["height"], 600)
            QTest.mousePress(window, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, QPoint(998, 598))
            QTest.mouseMove(window, QPoint(138, 88))
            QTest.mouseRelease(window, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier, QPoint(138, 88))
            self.app.processEvents()
            self.assertEqual((window.width(), window.height()), (380, 360))
            desk.fold()
            desk.expand()
            self.assertEqual((window.width(), window.height()), (380, 360))

    def test_compact_header_drags_from_empty_space_and_date(self):
        with self.scene() as (window, desk, store, calendar):
            distance = QPoint(22, 14)
            picker = window.findChild(QObject, "monthJump")
            title = window.findChild(QObject, "dateJumpButton")
            for day_view in (False, True):
                window.setProperty("compactDayOpen", day_view)
                window.setGeometry(50, 70, 380, 360)
                self.app.processEvents()
                center = title.mapToScene(QPointF(title.width()/2, title.height()/2)).toPoint()
                for start in (QPoint(50, 6), QPoint(window.width()-24, 6), center):
                    with self.subTest(day_view=day_view, start=start):
                        before = window.geometry()
                        end = window.mapToGlobal(start + distance)
                        with patch("rooplan.desktop.QCursor.pos", return_value=end):
                            QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
                            self.assertIsNotNone(desk.drag)
                            self.assertFalse(desk.resizing)
                            QTest.mouseMove(window, start + distance)
                            QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
                        self.assertEqual(window.geometry(), before.translated(distance))
                        self.assertFalse(picker.property("visible"))
                self.click_item(window, title)
                self.assertTrue(picker.property("visible"))
                picker.close()
                QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(50, 2))
                self.assertTrue(desk.resizing)
                self.assertIsNone(desk.drag)
                QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(50, 2))

    def test_responsive_week_keeps_all_days_and_previews(self):
        with self.scene() as (window, desk, store, calendar):
            key = store.new_draft("week preview")
            store.propose_changes(key, [dict(fields=dict(
                title="Activity "+str(index+1), start=day+"T10:00",
                end=day+"T11:00", location="Room 302"))
                for index, day in enumerate(desk.days)])
            store.confirm(key)
            calendar.changed.emit()
            grid = window.findChild(QObject, "weekGrid")
            for width, height in ((380, 360), (520, 480), (640, 480), (1000, 700), (1400, 900)):
                window.resize(width, height)
                QTest.qWait(30)
                compact = width < 640
                self.assertEqual(window.property("compact"), compact)
                self.assertTrue(grid.isVisible())
                layout = window.findChild(QObject, "calendarLayout")
                self.assertAlmostEqual(layout.width(), width-24)
                self.assertGreater(grid.height(), 100)
                self.assertAlmostEqual(grid.property("rangeStart"), 8)
                self.assertAlmostEqual(grid.property("rangeEnd"), 22)
                button = window.findChild(QObject, "floatingAddButton")
                self.assertLessEqual(button.mapToScene(QPointF(button.width(), 0)).x(), width-8)
                self.assertGreaterEqual(button.mapToScene(QPointF()).x(), 8)
                records = window.property("visibleRecords")
                if hasattr(records, "toVariant"):
                    records = records.toVariant()
                self.assertEqual({entry["day"] for entry in records}, set(range(7)))
            window.resize(380, 360)
            QTest.qWait(30)
            cards = visual_items(window.contentItem(), "weekEvent")
            self.assertEqual(len(cards), 7)
            for card in (cards[0], cards[-1]):
                point = card.mapToScene(QPointF(card.width()/2, card.height()/2)).toPoint()
                before = window.geometry()
                QTest.mouseMove(window, point)
                preview = window.findChild(QObject, "eventPreview")
                for _ in range(40):
                    QTest.qWait(25)
                    if preview.property("visible"):
                        break
                self.assertTrue(preview.property("visible"))
                entry = preview.property("entry").toVariant()
                self.assertEqual(entry["location"], "Room 302")
                self.assertGreaterEqual(preview.x(), 8)
                self.assertLessEqual(preview.x()+preview.width(), window.width()-8)
                self.assertGreaterEqual(preview.y(), 8)
                self.assertLessEqual(preview.y()+preview.height(), window.height()-8)
                self.assertEqual(window.geometry(), before)
                self.assertIsNone(desk.drag)
                QTest.mouseMove(window, preview.mapToScene(QPointF(20,20)).toPoint())
                QTest.qWait(300)
                self.assertTrue(preview.property("visible"))
                QTest.mouseMove(window, QPoint(10, 100))
                for _ in range(40):
                    QTest.qWait(25)
                    if not preview.property("visible"):
                        break
                self.assertFalse(preview.property("visible"))
            point = cards[-1].mapToScene(QPointF(cards[-1].width()/2, cards[-1].height()/2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, point)
            self.assertEqual(window.property("mode"), "detail")
            self.assertEqual(window.property("current").toVariant()["title"], "Activity 7")

    def test_all_corners_resize_from_global_pointer_without_feedback(self):
        with self.scene() as (window, desk, store, calendar):
            for left, top in ((True,True), (True,False), (False,True), (False,False)):
                with self.subTest(left=left, top=top):
                    window.setGeometry(100,100,900,650)
                    self.app.processEvents()
                    local = QPoint(3 if left else 897, 3 if top else 647)
                    origin = window.mapToGlobal(local)
                    QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local)
                    self.assertTrue(desk.resizing)
                    for dx, dy in ((-60,-40), (40,30), (0,0), (1200,900), (-90,-60), (0,0)):
                        width = max(380,900+(-dx if left else dx))
                        height = max(360,650+(-dy if top else dy))
                        expected = (100+900-width if left else 100,
                                    100+650-height if top else 100, width, height)
                        # Queued local coordinates may belong to an earlier window origin.
                        # Repeating the same global point must never change the geometry.
                        for local_position in (QPointF(3,3), QPointF(70,90), QPointF(1,1)):
                            event = QMouseEvent(QEvent.Type.MouseMove, local_position,
                                                QPointF(origin+QPoint(dx,dy)), Qt.MouseButton.NoButton,
                                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                            QCoreApplication.sendEvent(window,event)
                            self.app.processEvents()
                            self.assertEqual(window.geometry().getRect(), expected)
                            self.assertFalse(desk.collapsed)
                    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local)
                    self.assertFalse(desk.resizing)
                    self.assertEqual((desk.settings["width"],desk.settings["height"]), (900,650))

    def test_early_and_late_events_fold_and_fit_when_expanded(self):
        with self.scene() as (window, desk, store, calendar):
            key = store.new_draft("edge hours")
            store.propose_changes(key, [
                dict(fields=dict(title="Early", start=desk.days[0]+"T00:05", end=desk.days[0]+"T00:25")),
                dict(fields=dict(title="Late", start=desk.days[3]+"T23:45", end=desk.days[3]+"T23:59")),
                dict(fields=dict(title="Sunday night", start=desk.days[6]+"T22:30", end=desk.days[6]+"T23:00")),
                dict(fields=dict(title="Deadline", kind="deadline", start=desk.days[6]+"T23:55")),
            ])
            store.confirm(key)
            calendar.changed.emit()
            grid = window.findChild(QObject, "weekGrid")
            window.resize(380, 360)
            QTest.qWait(70)
            early, = visual_items(grid.parentItem(), "earlyPeriodDay0")
            late, = visual_items(grid.parentItem(), "latePeriodDay3")
            sunday, = visual_items(grid.parentItem(), "latePeriodDay6")
            empty, = visual_items(grid.parentItem(), "latePeriodDay5")
            self.assertIn("周一 00:05", early.property("text"))
            self.assertIn("周四 23:45", late.property("text"))
            self.assertIn("周日 22:30 · 1 项", sunday.property("text"))
            self.assertFalse(empty.isVisible())
            for width, height in ((380, 360), (1120, 740)):
                window.resize(width, height)
                QTest.qWait(60)
                gutter, day_width = grid.property("gutter"), grid.property("dayWidth")
                for chip, day in ((early, 0), (late, 3), (sunday, 6)):
                    self.assertTrue(chip.isVisible())
                    expected = grid.mapToScene(QPointF(gutter + (day + 0.5) * day_width, 0)).x()
                    self.assertAlmostEqual(chip.mapToScene(QPointF(chip.width() / 2, 0)).x(), expected)
                    self.assertLess(chip.width(), day_width)
                add_button = window.findChild(QObject, "floatingAddButton")
                self.assertLess(sunday.mapToScene(QPointF(0, sunday.height())).y(),
                                add_button.mapToScene(QPointF()).y())
            window.resize(380, 360)
            QTest.qWait(50)
            self.assertEqual((grid.property("rangeStart"), grid.property("rangeEnd")), (8, 22))
            self.assertEqual(visual_items(window.contentItem(), "weekEvent"), [])
            self.click_item(window, early)
            QTest.qWait(60)
            self.click_item(window, sunday)
            for width, height in ((380,360), (520,420), (1000,700), (1920,1080)):
                window.resize(width,height)
                QTest.qWait(40)
                self.assertEqual(grid.property("rangeStart"), 0)
                self.assertEqual(grid.property("rangeEnd"), 24)
                for chip, day in ((early, 0), (sunday, 6)):
                    self.assertTrue(chip.isVisible())
                    self.assertEqual(chip.property("text"), "收起")
                    x = grid.property("gutter") + (day + 0.5) * grid.property("dayWidth")
                    self.assertAlmostEqual(chip.mapToScene(QPointF(chip.width() / 2, 0)).x(),
                                           grid.mapToScene(QPointF(x, 0)).x())
                self.assertFalse(late.isVisible())
                cards = visual_items(window.contentItem(), "weekEvent")
                self.assertEqual(len(cards), 3)
                for card in cards:
                    self.assertGreaterEqual(card.y(), 0)
                    self.assertLessEqual(card.y()+card.height(), grid.height())
                    self.assertGreater(card.height(), 0)
                self.assertIsNone(grid.property("contentY"))
            self.click_item(window, sunday)
            self.assertEqual(grid.property("rangeEnd"), 22)
            self.assertTrue(sunday.isVisible())
            self.assertIn("22:30", sunday.property("text"))
            self.click_item(window, late)
            self.assertEqual(grid.property("rangeEnd"), 24)
            self.assertEqual(late.property("text"), "收起")
            self.assertFalse(sunday.isVisible())
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                             grid.mapToScene(QPointF(grid.width()*0.6, grid.height()*0.5)).toPoint())
            self.assertEqual(window.property("mode"), "edit")
            current = window.property("current").toVariant()
            self.assertEqual(current["start"][-5:], "12:00")

    def test_search_opens_cross_midnight_entry_on_filtered_day(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380, 360)
            target = date.fromisoformat(desk.days[0]) + timedelta(days=29)
            begin = (target - timedelta(days=1)).isoformat()
            self.assertTrue(calendar.manual("", json.dumps(dict(
                title="夜间参观", location="校史馆", start=begin+"T23:30", end=f"{target}T01:00"))))
            window.requestActivate()
            QTest.qWait(120)
            QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
            QTest.qWait(220)
            keyword = window.findChild(QObject, "calendarSearchInput")
            self.assertIsNotNone(keyword)
            self.assertTrue(keyword.property("activeFocus"))
            keyword.setProperty("text", "校史馆")
            window.findChild(QObject, "calendarSearchFrom").setProperty("text", str(target))
            window.findChild(QObject, "calendarSearchTo").setProperty("text", str(target))
            QTest.qWait(80)
            results = window.findChild(QObject, "calendarSearchResults")
            self.assertEqual(results.property("count"), 1)
            self.click_item(window, visual_items(results, "agendaEntry")[0])
            QTest.qWait(90)
            self.assertEqual(window.property("mode"), "detail")
            self.assertEqual(desk.days[window.property("selectedDay")], str(target))
            self.assertEqual(window.property("current").toVariant()["title"], "夜间参观")
            window.closeSheet()
            QTest.qWait(80)
            self.assertEqual(window.property("mode"), "search")
            self.assertEqual(window.findChild(QObject, "calendarSearchInput").property("text"), "校史馆")
            self.assertEqual(window.findChild(QObject, "calendarSearchFrom").property("text"), str(target))
            self.assertEqual(window.findChild(QObject, "calendarSearchTo").property("text"), str(target))
            self.assertEqual(window.findChild(QObject, "calendarSearchResults").property("count"), 1)
            window.closeSheet()
            QTest.qWait(60)
            QTest.keyClick(window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
            QTest.qWait(80)
            self.assertEqual(window.findChild(QObject, "calendarSearchInput").property("text"), "")

    def test_agenda_shows_dates_for_activity_spanning_several_days(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380, 480)
            QTest.qWait(40)
            window.selectDate("2026-12-31")
            self.assertTrue(calendar.manual("", json.dumps(dict(title="跨年观测",
                start="2026-12-29T20:00", end="2027-01-02T08:00"))))
            QTest.qWait(100)
            agenda = window.findChild(QObject, "dayAgenda")
            button, = visual_items(agenda, "agendaEntry")
            self.assertEqual(button.property("contentItem").property("summary"),
                             "2026-12-29 20:00–2027-01-02 08:00")
            window.resize(1100, 800)
            window.setProperty("earlyExpanded", True)
            window.setProperty("lateExpanded", True)
            QTest.qWait(80)
            cards = visual_items(window.contentItem(), "weekEvent")
            by_day = {card.property("ev").toVariant()["day"]: visual_items(card, "cardTime")[0].property("text")
                      for card in cards}
            self.assertEqual(by_day, {1: "20:00–24:00", 2: "00:00–24:00", 3: "00:00–24:00",
                                      4: "00:00–24:00", 5: "00:00–08:00"})

    def test_month_jump_marks_cross_midnight_entries_and_selects_day_across_years(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380, 360)
            desk.jumpToDate("2028-12-27")
            self.assertTrue(calendar.manual("", json.dumps(dict(
                title="夜班", start="2028-12-31T23:30", end="2029-01-01T00:30"))))
            self.assertTrue(calendar.manual("", json.dumps(dict(
                title="交材料", kind="deadline", start="2029-01-03T17:00"))))
            QTest.qWait(90)
            trigger = window.findChild(QObject, "dateJumpButton")
            picker = window.findChild(QObject, "monthJump")
            self.click_item(window, trigger)
            QTest.qWait(80)
            self.assertTrue(picker.property("visible"))
            self.assertEqual((picker.property("year"), picker.property("month")), (2028, 11))
            self.assertGreaterEqual(picker.property("x"), 8)
            self.assertLessEqual(picker.property("x") + picker.property("width"), window.width()-8)
            self.assertLessEqual(picker.property("y") + picker.property("height"), window.height()-8)

            def day_button(day):
                buttons = visual_items(picker.property("contentItem"), "monthJumpDay_" + day)
                self.assertEqual(len(buttons), 1)
                return buttons[0]

            self.assertTrue(day_button("2028-12-31").property("marked"))
            self.click_item(window, window.findChild(QObject, "monthJumpNext"))
            self.assertEqual((picker.property("year"), picker.property("month")), (2029, 0))
            self.assertTrue(day_button("2029-01-01").property("marked"))
            self.assertFalse(day_button("2029-01-02").property("marked"))
            self.assertTrue(day_button("2029-01-03").property("marked"))
            self.click_item(window, day_button("2029-01-01"))
            QTest.qWait(90)
            self.assertFalse(picker.property("visible"))
            self.assertEqual(desk.days[0], "2029-01-01")
            self.assertEqual(window.findChild(QObject, "dayAgenda").property("day"), "2029-01-01")

            window.resize(1000, 700)
            QTest.qWait(80)
            self.click_item(window, trigger)
            QTest.qWait(80)
            self.assertTrue(day_button("2029-01-01").property("selected"))
            self.click_item(window, day_button("2029-01-03"))
            QTest.qWait(80)
            header, = visual_items(window.contentItem(), "jumpedDayHeader")
            self.assertEqual(visual_items(header, "dateNumber")[0].property("text"), "3")
            self.click_item(window, trigger)
            QTest.qWait(80)
            QTest.keyClick(window, Qt.Key.Key_Escape)
            QTest.qWait(80)
            self.assertFalse(picker.property("visible"))
            self.assertEqual(desk.days[window.property("selectedDay")], "2029-01-03")
            self.click_item(window, trigger)
            QTest.qWait(80)
            self.click_item(window, window.findChild(QObject, "monthJumpPrevious"))
            self.assertEqual((picker.property("year"), picker.property("month")), (2028, 11))
            self.click_item(window, window.findChild(QObject, "monthJumpToday"))
            self.assertTrue(desk.currentWeek)
            self.assertEqual(desk.days[window.property("selectedDay")], calendar.todayDate)

    def test_draft_review_defers_linked_items_and_can_confirm_an_overlap(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(1120, 1050)
            friday, saturday = desk.days[4:6]
            store.apply_manual([dict(fields=dict(title="外出参观", start=saturday+"T09:00", end=saturday+"T11:00"))])
            key = store.new_draft("组会、PPT 和值班")
            meeting, deadline, prep, duty = store.propose_changes(key, [
                dict(ref="meeting", fields=dict(title="组会", start=saturday+"T09:30", end=saturday+"T10:30")),
                dict(ref="ppt", fields=dict(title="交 PPT", start=friday+"T18:00", kind="deadline", parent="meeting")),
                dict(fields=dict(title="准备 PPT", start=friday+"T16:00", end=friday+"T17:00", kind="prep", parent="ppt")),
                dict(fields=dict(title="值班", start=friday+"T14:00", end=friday+"T15:00")),
            ])["rows"]
            calendar.changed.emit()
            window.openDraft(key)
            QTest.qWait(220)
            self.click_text(window, "暂存待定")
            self.assertEqual([row["id"] for row in store.draft(key)["rows"] if row["selected"]], [duty["id"]])
            self.click_text(window, "确认 1 项")
            self.assertEqual(window.property("mode"), "review")
            reopened = Store(store.path)
            self.assertEqual([row["id"] for row in reopened.review(key)["confirmed"]], [duty["id"]])
            self.click_text(window, "查看已确认 1 项")
            for row in (meeting, deadline, prep):
                checkbox, = visual_items(window.contentItem(), "draftSelection_" + row["id"])
                self.click_item(window, checkbox)
            self.click_text(window, "仍按原时间添加")
            self.click_text(window, "确认勾选项")
            self.assertEqual(window.property("mode"), "")
            self.assertEqual(reopened.draft(key)["state"], "applied")
            self.assertEqual(len(reopened.all()), 5)
            QTest.qWait(90)
            saturday_cards = [card for card in visual_items(window.contentItem(), "weekEvent")
                              if card.property("ev").toVariant()["day"] == 5]
            self.assertEqual(len(saturday_cards), 2)
            self.assertNotEqual(saturday_cards[0].x(), saturday_cards[1].x())

    def test_legacy_missing_draft_link_can_be_repaired_without_reparsing(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(1120, 1050)
            friday, saturday = desk.days[4:6]
            store.apply_manual([dict(fields=dict(title="外出参观", start=saturday+"T09:00", end=saturday+"T11:00"))])
            key = store.new_draft("组会和截止事项")
            meeting, deadline, duty = store.propose_changes(key, [
                dict(ref="meeting", fields=dict(title="组会", start=saturday+"T09:30", end=saturday+"T10:30")),
                dict(fields=dict(title="交 PPT", start=friday+"T18:00", kind="deadline", parent="meeting")),
                dict(fields=dict(title="值班", start=friday+"T14:00", end=friday+"T15:00")),
            ])["rows"]
            store.edit(key, duty["id"], selected=False)
            store.edit(key, deadline["id"], fields={"parent": "obsolete-reference"})
            calendar.changed.emit()
            window.openDraft(key)
            QTest.qWait(220)
            self.click_text(window, "仍按原时间添加")
            self.assertIn("找不到原关联项", store.review(key)["dependencies"][deadline["id"]])
            with self.assertRaisesRegex(ValueError, "交 PPT.*找不到原关联项"):
                store.confirm(key, keep_remaining=True)

            edit, = visual_items(window.contentItem(), "draftEdit_" + deadline["id"])
            self.click_item(window, edit)
            QTest.qWait(210)
            links = window.findChild(QObject, "linkedEvent")
            self.assertIn("原关联不可用", links.property("currentText"))
            options = links.property("model")
            links.setProperty("currentIndex", next(i for i, option in enumerate(options)
                                                   if option["id"] == meeting["id"]))
            self.click_text(window, "保存")
            self.assertFalse(store.review(key)["dependencies"])
            self.click_text(window, "确认 2 项")
            self.assertEqual(store.all()[deadline["id"]]["parent"], meeting["id"])
            self.assertEqual([row["id"] for row in store.draft(key)["rows"]], [duty["id"]])

    def test_delete_linked_event_can_keep_or_delete_dependents_and_undo(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(460, 620)
            friday = desk.days[4]
            store.apply_manual([
                dict(ref="meeting", fields=dict(title="组会", start=friday+"T20:00")),
                dict(ref="deadline", fields=dict(title="提交组会PPT", start=friday+"T18:00",
                                                kind="deadline", parent="meeting", before_meeting=True)),
                dict(fields=dict(title="准备PPT", start=friday+"T16:00", end=friday+"T17:00",
                                 kind="prep", parent="deadline")),
            ])
            calendar.changed.emit()
            original = store.all()
            meeting, deadline, prep = (next(item for item in original.values() if item["kind"] == kind)
                                       for kind in ("event", "deadline", "prep"))
            window.openEntry(prep)
            QTest.qWait(200)
            self.assertTrue(visual_items(window.contentItem(), "detailLink_" + meeting["id"]))
            for target in (deadline, meeting):
                button, = visual_items(window.contentItem(), "detailLink_" + target["id"])
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                 button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
                QTest.qWait(30)
                self.assertEqual(window.property("current").toVariant()["id"], target["id"])
            self.click_text(window, "关闭")
            with store.session() as db:
                reminders = [tuple(row) for row in db.execute("SELECT * FROM reminders ORDER BY id")]

            def delete(entry, action):
                window.openEntry(entry)
                QTest.qWait(200)
                self.click_text(window, "删除")
                QTest.qWait(200)
                self.click_text(window, action)
                self.assertEqual(window.property("mode"), "")

            delete(deadline, "仅删除此项")
            self.assertNotIn(deadline["id"], store.all())
            self.assertIsNone(store.all()[prep["id"]]["parent"])
            self.assertTrue(calendar.undo())
            self.assertEqual(store.all(), original)

            delete(meeting, "仅删除此项")
            saved = store.all()
            self.assertIsNone(saved[deadline["id"]]["parent"])
            self.assertFalse(saved[deadline["id"]]["before_meeting"])
            self.assertEqual(saved[prep["id"]]["parent"], deadline["id"])
            self.assertTrue(calendar.undo())

            delete(meeting, "连同关联事项删除")
            self.assertFalse(store.all())
            with store.session() as db:
                self.assertFalse(db.execute("SELECT * FROM reminders").fetchall())
            self.assertTrue(calendar.undo())
            self.assertEqual(Store(store.path).all(), original)
            with store.session() as db:
                self.assertEqual([tuple(row) for row in db.execute("SELECT * FROM reminders ORDER BY id")], reminders)

    def test_recurring_form_saves_and_changes_only_one_occurrence(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(830, 820)
            first = date.fromisoformat(desk.days[4])
            last = first + timedelta(days=28)
            window.blankClicked.emit(f"{first}T10:00")
            QTest.qWait(220)
            window.findChild(QObject, "nameField").setProperty("text", "隔周组会")
            window.findChild(QObject, "repeatInterval").setProperty("currentIndex", 2)
            repeat_until = window.findChild(QObject, "repeatUntil")
            visual_items(repeat_until, "dateField")[0].setProperty("text", last.isoformat())
            QTest.qWait(70)
            self.click_text(window, "保存")
            self.assertEqual(window.property("mode"), "")
            original = Store(store.path).search_events("组会")
            self.assertEqual([e["start"] for e in original],
                             [f"{first + timedelta(days=offset)}T10:00" for offset in (0, 14, 28)])
            self.assertEqual(len({entry["series"]["id"] for entry in original}), 1)
            chosen = original[1]

            window.openEntry(chosen)
            QTest.qWait(220)
            self.click_text(window, "编辑本次")
            QTest.qWait(220)
            form_start = window.findChild(QObject, "eventBeginning")
            visual_items(form_start, "timeField")[0].setProperty("text", "14:00")
            self.click_text(window, "保存")
            updated = store.search_events("组会")
            self.assertEqual((updated[0], updated[2]), (original[0], original[2]))
            self.assertEqual(updated[1]["id"], chosen["id"])
            self.assertEqual(updated[1]["start"], f"{first + timedelta(days=14)}T14:00")
            with store.session() as db:
                at = db.execute("SELECT at FROM reminders WHERE id=?", (chosen["id"],)).fetchone()[0]
            self.assertEqual(at, f"{first + timedelta(days=14)}T13:50")

            window.openEntry(updated[1])
            QTest.qWait(220)
            self.click_text(window, "取消本次")
            QTest.qWait(220)
            self.click_text(window, "仅取消本次")
            self.assertEqual(store.search_events("组会"), [original[0], original[2]])
            with store.session() as db:
                self.assertIsNone(db.execute("SELECT at FROM reminders WHERE id=?", (chosen["id"],)).fetchone())
            self.assertTrue(calendar.undo())
            self.assertEqual(store.search_events("组会"), updated)
            self.assertTrue(calendar.undo())
            self.assertEqual(store.search_events("组会"), original)

    def test_date_only_deadline_can_be_saved_and_stays_due_until_midnight(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(830, 740)
            day = desk.days[4]
            window.blankClicked.emit(day + "T09:00")
            QTest.qWait(220)
            window.findChild(QObject, "nameField").setProperty("text", "交实验报告")
            window.findChild(QObject, "eventKind").setProperty("currentIndex", 1)
            form_start = window.findChild(QObject, "eventBeginning")
            visual_items(form_start, "timeField")[0].setProperty("text", "")
            self.app.processEvents()
            reminder = window.findChild(QObject, "dateOnlyReminder")
            self.assertTrue(reminder.isVisible())
            reminder.setProperty("text", "17:30")
            self.click_text(window, "保存")
            item, = store.all().values()
            self.assertEqual((item["start"], item["reminder_time"]), (day, "17:30"))
            self.assertFalse(calendar.overdue_at(datetime.fromisoformat(day + "T23:59")))
            self.assertEqual(calendar.overdue_at(datetime.fromisoformat(day) + timedelta(days=1)), [item])
            chip, = visual_items(window.contentItem(), "deadlineChip")
            self.assertEqual(chip.property("text"), "当日 截止 · 交实验报告")
            self.click_item(window, chip)
            self.assertEqual(window.property("mode"), "detail")

    def test_event_color_selected_in_form_matches_week_and_details(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(900, 740)
            window.blankClicked.emit(desk.days[1] + "T10:00")
            QTest.qWait(220)
            window.findChild(QObject, "nameField").setProperty("text", "数据核对")
            finish = window.findChild(QObject, "eventEnding")
            visual_items(finish, "timeField")[0].setProperty("text", "11:00")
            lilac, = visual_items(window.contentItem(), "eventColor_lilac")
            self.click_item(window, lilac)
            self.click_text(window, "保存")
            self.assertEqual(window.property("mode"), "")
            entry, = store.all().values()
            self.assertEqual(entry["color"], "lilac")
            card, = visual_items(window.contentItem(), "eventTimeSurface")
            self.assertEqual(card.property("color").name(), "#f0eaf7")

            window.openEntry(entry)
            QTest.qWait(220)
            mark = window.findChild(QObject, "detailColorMark")
            self.assertEqual(mark.property("color").name(), "#785da0")
            self.click_text(window, "编辑")
            QTest.qWait(220)
            lilac, = visual_items(window.contentItem(), "eventColor_lilac")
            self.assertTrue(lilac.property("selected"))
            automatic, = visual_items(window.contentItem(), "eventColor_auto")
            self.click_item(window, automatic)
            self.click_text(window, "保存")
            self.assertEqual(store.all()[entry["id"]]["color"], "auto")
            self.assertTrue(calendar.undo())
            self.assertEqual(store.all()[entry["id"]]["color"], "lilac")

    def test_notice_review_shows_before_after_and_unchanged_deadline(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(760, 760)
            friday, saturday = desk.days[4:6]
            store.apply_manual([
                dict(ref="meeting", fields=dict(title="组会", start=friday+"T20:00", location="物理楼 302")),
                dict(fields=dict(title="提交组会 PPT", start=friday+"T18:00", kind="deadline", parent="meeting")),
            ])
            original = store.all()
            meeting = next(item for item in original.values() if item["kind"] == "event")
            calendar.changed.emit()
            key = store.new_draft("组会改周六，PPT 截止照旧")
            store.propose_changes(key, [dict(id=meeting["id"], fields=dict(start=saturday+"T20:00"))])
            window.openDraft(key)
            QTest.qWait(200)

            def labels(item):
                if item.isVisible():
                    yield item.property("text")
                    for child in item.childItems():
                        yield from labels(child)

            text = set(labels(window.contentItem()))
            self.assertIn("原安排　"+friday+" 20:00", text)
            self.assertIn("变更后　"+saturday+" 20:00", text)
            self.assertIn("地点照旧 · 物理楼 302", text)
            self.assertIn("提交组会 PPT · 原安排照旧", text)
            self.click_text(window, "确认勾选项")
            self.assertEqual(set(store.all()), set(original))
            self.assertEqual(store.all()[meeting["id"]]["start"], saturday+"T20:00")
            self.assertTrue(calendar.undo())
            self.assertEqual(store.all(), original)

    def test_reminder_summary_and_snooze_survive_reopening(self):
        with self.scene() as (window, desk, store, calendar):
            past = calendar.today - timedelta(days=2)
            for index in (10, 12):
                self.assertTrue(calendar.manual("", json.dumps(dict(
                    title=f"材料 {index}", kind="deadline", start=f"{past}T{index}:00"))))
            received = []
            calendar.reminder.connect(received.append)
            calendar.deliver()
            calendar.deliver()
            self.assertEqual(len(received), 1)
            self.assertIn("2 条", received[0])
            window.showReminders()
            QTest.qWait(220)
            snoozed = store.pending_reminders()[0]
            self.click_text(window, "10 分钟后提醒")
            QTest.qWait(60)
            reopened = Store(store.path)
            still_pending, = reopened.pending_reminders()
            self.assertNotEqual(still_pending["id"], snoozed["id"])
            with reopened.session() as db:
                at = db.execute("SELECT snoozed_until FROM reminders WHERE id=?", (snoozed["id"],)).fetchone()[0]
            due = datetime.fromisoformat(at)
            self.assertFalse(reopened.due_reminders(due - timedelta(seconds=1)))
            self.assertEqual(reopened.due_reminders(due), [snoozed])
            self.assertFalse(reopened.due_reminders(due))
            self.assertEqual(reopened.all()[snoozed["id"]]["start"], snoozed["start"])
            reopened.handle_reminder(snoozed["id"])
            self.assertEqual(Store(store.path).pending_reminders(), [still_pending])

    def test_week_grid_drag_creates_checks_conflict_and_opens_linked_reschedule(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(1100, 800)
            grid = window.findChild(QObject, "weekGrid")
            friday, saturday = desk.days[4:6]

            def point(day, minute):
                x = grid.property("gutter") + (day + 0.5)*grid.property("dayWidth")
                y = grid.property("timePadding") + (minute/60-grid.property("rangeStart"))*grid.property("unit")
                return grid.mapToScene(QPointF(x, y)).toPoint()

            def drag(start, end):
                QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
                QTest.mouseMove(window, end)
                preview = window.findChild(QObject, "calendarDragPreview")
                self.assertTrue(preview.property("visible"))
                QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
                QTest.qWait(110)
                self.assertFalse(preview.property("visible"))

            QTest.qWait(100)
            drag(point(4, 14*60 + 4), point(4, 15*60))
            self.assertEqual(window.property("mode"), "edit")
            new = window.property("current").toVariant()
            self.assertEqual((new["start"], new["end"]), (friday+"T14:00", friday+"T15:00"))
            sheet = window.findChild(QObject, "sheetSurface")
            self.assertTrue(sheet.property("atAnchor"))
            self.assertLess(sheet.x() + sheet.width(), window.property("originX"))
            self.assertTrue(window.findChild(QObject, "nameField").hasActiveFocus())
            QTest.keyClick(window, Qt.Key.Key_Escape)
            QTest.qWait(90)

            for title, day in (("组会", friday), ("值班", saturday)):
                self.assertTrue(calendar.manual("", json.dumps(dict(title=title, start=day+"T14:00", end=day+"T15:00"))))
            event = next(entry for entry in store.all().values() if entry["title"] == "组会")
            QTest.qWait(60)
            original = store.all()
            drag(point(4, 14*60+30), point(5, 14*60+30))
            for text in ("时间冲突", "组会", "值班"):
                self.assertIn(text, window.property("message"))
            self.assertEqual(store.all(), original)
            drag(point(4, 14*60+30), point(5, 16*60+30))
            self.assertEqual(store.all()[event["id"]]["start"], saturday+"T16:00")
            self.assertTrue(calendar.undo())
            self.assertEqual(store.all(), original)
            self.assertTrue(calendar.manual("", json.dumps(dict(
                title="交材料", kind="deadline", start=friday+"T12:00", parent=event["id"]))))
            QTest.qWait(60)
            original = store.all()
            drag(point(4, 14*60+30), point(5, 16*60+30))
            self.assertEqual(window.property("mode"), "reschedule")
            QTest.qWait(135)
            begin, = visual_items(window.contentItem(), "groupStart0")
            self.assertEqual(visual_items(begin, "dateField")[0].property("text"), saturday)
            self.assertEqual(visual_items(begin, "timeField")[0].property("text"), "16:00")
            QTest.keyClick(window, Qt.Key.Key_Escape)
            self.assertEqual(window.property("mode"), "")
            self.assertEqual(store.all(), original)
            drag(point(4, 14*60+30), point(5, 16*60+30))
            QTest.qWait(135)
            self.click_text(window, "保存全部改期")
            self.assertEqual(window.property("mode"), "")
            self.assertEqual(store.all()[event["id"]]["start"], saturday+"T16:00")
            self.assertTrue(calendar.undo())
            self.assertEqual(store.all(), original)

    def test_window_menu_stays_inside_and_runs_actions(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380,360)
            QTest.qWait(30)
            button = window.findChild(QObject, "moreButton")
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                             button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint())
            QTest.qWait(180)
            menu = window.findChild(QObject, "windowMenu")
            self.assertTrue(menu.property("visible"))
            self.assertGreaterEqual(menu.property("x"), 8)
            self.assertLessEqual(menu.property("x")+menu.property("width"),window.width()-8)
            self.assertLessEqual(menu.property("y")+menu.property("height"),window.height()-8)
            QTest.keyClick(window, Qt.Key.Key_Escape)
            for _ in range(40):
                QTest.qWait(25)
                if not menu.property("visible"):
                    break
            self.assertFalse(menu.property("visible"))
            QMetaObject.invokeMethod(menu, "open")
            QTest.qWait(180)
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                             QPoint(60,300))
            for _ in range(40):
                QTest.qWait(25)
                if not menu.property("visible"):
                    break
            self.assertFalse(menu.property("visible"))
            self.assertEqual(window.property("mode"), "")
            QMetaObject.invokeMethod(menu, "open")
            QTest.qWait(180)
            reset = visual_items(menu.property("contentItem"), "menuAction_reset")[0]
            point = reset.mapToScene(QPointF(reset.width()/2,reset.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
            QTest.qWait(150)
            self.assertFalse(menu.property("visible"))
            self.assertEqual((window.width(), window.height()), (1120,740))

    def test_editor_reflows_inside_small_window(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380, 360)
            window.setProperty("current", calendar.blank(desk.days[0]+"T09:00"))
            window.setProperty("mode", "edit")
            QTest.qWait(200)
            options = window.findChild(QObject, "eventOptions")
            self.assertEqual(options.property("columns"), 2)
            self.assertIsNone(window.findChild(QObject, "eventKind_prep"))
            for item in (options, window.findChild(QObject, "nameField")):
                self.assertGreaterEqual(item.mapToScene(QPointF()).x(), 8)
                self.assertLessEqual(item.mapToScene(QPointF(item.width(), 0)).x(), window.width()-8)
            self.click_item(window, window.findChild(QObject, "datePickerButton"))
            QTest.qWait(140)
            picker = window.findChild(QObject, "datePicker")
            self.assertTrue(picker.property("visible"))
            QTest.keyClick(window, Qt.Key.Key_Escape)
            QTest.qWait(160)
            self.assertFalse(picker.property("visible"))
            self.assertEqual(window.property("mode"), "edit")
            window.resize(1000, 720)
            QTest.qWait(80)
            self.click_text(window, "截止任务")
            self.assertEqual(window.findChild(QObject, "eventKind").property("currentIndex"), 1)
            self.click_text(window, "更多选项")
            repeat = window.findChild(QObject, "repeatInterval")
            self.click_item(window, repeat)
            combo_popup = window.findChild(QObject, "repeatIntervalPopup")
            self.assertTrue(combo_popup.property("visible"))
            QTest.keyClick(window, Qt.Key.Key_Escape)
            QTest.qWait(100)
            self.assertFalse(combo_popup.property("visible"))
            self.assertEqual(window.property("mode"), "edit")
            self.click_item(window, repeat)
            self.click_text(window, "每周")
            self.assertEqual(repeat.property("currentIndex"), 1)
            self.assertTrue(window.findChild(QObject, "repeatUntil").property("visible"))

    def test_manual_linked_reschedule_rolls_back_conflict_and_undo_restores_batch(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(1000, 1000)
            friday, saturday = desk.days[4:6]

            def create(title, **fields):
                self.assertTrue(calendar.manual("", json.dumps(dict(title=title, **fields))))
                return next(e["id"] for e in store.all().values() if e["title"] == title)

            event_id = create("组会", start=friday+"T14:00", end=friday+"T15:00", location="物理楼 302")
            deadline_id = create("交 PPT", kind="deadline", start=friday+"T12:00")
            window.openEntry(store.all()[deadline_id])
            QTest.qWait(220)
            self.click_text(window, "编辑")
            QTest.qWait(220)
            window.findChild(QObject, "linkedEvent").setProperty("currentIndex", 1)
            window.findChild(QObject, "dueBeforeMeeting").setProperty("checked", True)
            self.click_text(window, "保存")
            self.assertEqual(store.all()[deadline_id]["parent"], event_id)
            self.assertTrue(store.all()[deadline_id]["before_meeting"])
            prep_id = create("准备 PPT", kind="prep", start=friday+"T10:00", end=friday+"T11:00",
                             parent=deadline_id)
            window.openEntry(store.all()[prep_id])
            QTest.qWait(220)
            self.click_text(window, "编辑")
            QTest.qWait(220)
            self.assertEqual(window.findChild(QObject, "eventKind").property("currentIndex"), 2)
            window.findChild(QObject, "nameField").setProperty("text", "修改 PPT")
            self.click_text(window, "保存")
            prep = store.all()[prep_id]
            self.assertEqual((prep["title"], prep["kind"], prep["parent"]), ("修改 PPT", "prep", deadline_id))
            create("周六值班", start=saturday+"T13:30", end=saturday+"T14:30")
            original = store.all()
            with store.session() as db:
                reminders = [tuple(row) for row in db.execute("SELECT * FROM reminders ORDER BY id")]
                draft_count = db.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]

            window.openEntry(original[event_id])
            QTest.qWait(240)
            self.click_text(window, "一起改期")
            self.assertEqual(window.property("mode"), "reschedule")
            QTest.qWait(220)
            for index in range(3):
                start_fields, = visual_items(window.contentItem(), f"groupStart{index}")
                date_field, = visual_items(start_fields, "dateField")
                date_field.setProperty("text", saturday)
            self.app.processEvents()
            finish_fields, = visual_items(window.contentItem(), "groupEnd0")
            end_date, = visual_items(finish_fields, "dateField")
            self.assertEqual(end_date.property("text"), saturday)
            self.click_text(window, "保存全部改期")
            self.assertEqual(window.property("mode"), "reschedule")
            self.assertIn("时间冲突", window.property("message"))
            self.assertEqual(store.all(), original)
            with store.session() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM drafts").fetchone()[0], draft_count)
                self.assertEqual([tuple(row) for row in db.execute("SELECT * FROM reminders ORDER BY id")], reminders)
            start_fields, = visual_items(window.contentItem(), "groupStart0")
            visual_items(start_fields, "timeField")[0].setProperty("text", "15:00")
            visual_items(finish_fields, "timeField")[0].setProperty("text", "16:00")
            QTest.qWait(70)
            self.click_text(window, "保存全部改期")
            self.assertEqual(window.property("mode"), "")
            restored = Store(store.path)
            saved = restored.all()
            self.assertEqual(saved[event_id]["start"], saturday+"T15:00")
            self.assertEqual(saved[event_id]["location"], "物理楼 302")
            self.assertEqual(saved[deadline_id]["start"], saturday+"T12:00")
            self.assertEqual(saved[prep_id]["end"], saturday+"T11:00")
            with restored.session() as db:
                self.assertEqual(dict(db.execute("SELECT id,at FROM reminders"))[event_id], saturday+"T14:50")
            self.assertTrue(calendar.undo())
            self.assertEqual(restored.all(), original)
            with restored.session() as db:
                self.assertEqual([tuple(row) for row in db.execute("SELECT * FROM reminders ORDER BY id")], reminders)

    def test_composer_keeps_text_when_screenshot_is_attached_and_shows_confirmed_agenda(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380, 360)
            QTest.qWait(80)
            menu_button = window.findChild(QObject, "floatingAddButton")
            self.click_item(window, menu_button)
            menu = window.findChild(QObject, "addMenu")
            QTest.qWait(160)
            self.assertTrue(menu.property("visible"))
            self.click_item(window, visual_items(menu.property("contentItem"), "menuAction_import")[0])
            self.assertEqual(window.property("mode"), "import")
            QTest.qWait(220)
            notice = window.findChild(QObject, "noticeInput")
            notice.setProperty("text", "本周六的组会")
            path = Path(store.path).parent / "notice.png"
            img = QImage(20, 20, QImage.Format.Format_RGB32)
            img.fill(Qt.GlobalColor.white)
            self.assertTrue(img.save(str(path)))
            self.assertTrue(window.attachNotice(QUrl.fromLocalFile(str(path)).toString()))
            self.assertEqual(notice.property("text"), "本周六的组会")
            self.assertTrue(window.findChild(QObject, "noticeAttachment").property("visible"))
            self.assertFalse(store.pending())
            QTest.qWait(50)
            self.click_text(window, "查看截图")
            self.assertTrue(window.findChild(QObject, "noticeImagePreview").property("visible"))
            QTest.keyClick(window, Qt.Key.Key_Escape)
            self.assertEqual(window.property("mode"), "import")
            self.assertFalse(window.findChild(QObject, "noticeImagePreview").property("visible"))
            self.click_text(window, "仅保存")
            saved, = store.pending()
            self.assertIn("本周六的组会", saved["source"])
            self.assertEqual(Path(saved["attachment"]).read_bytes(), path.read_bytes())
            self.assertFalse(store.all())
            day = desk.days[5]
            store.propose_changes(saved["id"], [
                dict(fields=dict(title="组会", start=day+"T15:00", end=day+"T16:00", location="物理楼 302")),
                *[dict(fields=dict(title="材料 " + str(i), kind="deadline", start=day+f"T1{i}:00"))
                  for i in range(3)],
            ])
            store.confirm(saved["id"])
            calendar.changed.emit()
            window.setProperty("mode", "")
            window.resize(380, 360)
            QTest.qWait(60)
            headers = window.findChild(QObject, "dayHeaders")
            gutter = headers.property("gutter")
            self.click_item(window, headers, gutter + (headers.width()-gutter)*5.5/7, 20)
            agenda = window.findChild(QObject, "dayAgenda")
            self.assertTrue(agenda.property("visible"))
            self.assertEqual(agenda.property("count"), 4)
            window.resize(900, 740)
            QTest.qWait(60)
            chips = visual_items(window.contentItem(), "deadlineChip")
            self.assertEqual(len(chips), 2)
            self.assertIn("10:00", chips[0].property("text"))
            grid = window.findChild(QObject, "weekGrid")
            saturday = grid.property("gutter") + 5 * grid.property("dayWidth")
            self.assertAlmostEqual(chips[0].mapToScene(QPointF()).x(), grid.mapToScene(QPointF(saturday, 0)).x())
            more = next(item for item in visual_items(window.contentItem(), "moreDeadlines") if item.isVisible())
            self.click_item(window, more)
            self.assertEqual(window.property("mode"), "deadlines")

    def click_item(self, window, item, x=None, y=None):
        point = item.mapToScene(QPointF(item.width()/2 if x is None else x,
                                       item.height()/2 if y is None else y)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        self.app.processEvents()

    def test_add_menu_tracks_the_visible_trigger_at_each_width(self):
        with self.scene() as (window, desk, store, calendar):
            for width, height in ((1024, 680), (380, 360)):
                window.resize(width, height)
                QTest.qWait(80)
                button = window.findChild(QObject, "floatingAddButton")
                top_left = button.mapToScene(QPointF())
                self.assertGreater(top_left.x(), width - 85)
                self.assertGreater(top_left.y(), height - 85)
                self.assertEqual(button.width(), button.height())
                self.click_item(window, button)
                menu = window.findChild(QObject, "addMenu")
                QTest.qWait(170)
                self.assertTrue(menu.property("visible"))
                content = menu.property("contentItem")
                menu_right = content.mapToScene(QPointF(content.width(), 0)).x()
                button_bottom_right = button.mapToScene(QPointF(button.width(), button.height()))
                self.assertAlmostEqual(menu_right + menu.property("rightPadding"), button_bottom_right.x(), delta=1)
                self.assertLess(content.mapToScene(QPointF(0, content.height())).y(), top_left.y())
                self.assertGreater(content.mapToScene(QPointF()).y(), 0)
                self.click_item(window, visual_items(content, "menuAction_create")[0])
                self.assertEqual(window.property("mode"), "edit")
                self.assertFalse(button.isVisible())
                window.closeSheet()
                QTest.qWait(130)

    def test_floating_add_leaves_late_sunday_cards_accessible(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(800, 520)
            QTest.qWait(80)
            grid = window.findChild(QObject, "weekGrid")
            height = grid.height()
            store.apply_manual([dict(fields=dict(title="周末记录", start=desk.days[6]+"T21:55"))])
            calendar.changed.emit()
            QTest.qWait(80)
            self.assertLess(grid.height(), height)
            button = window.findChild(QObject, "floatingAddButton")
            card, = visual_items(grid, "weekEvent")
            self.assertLess(card.mapToScene(QPointF(0, card.height())).y(), button.mapToScene(QPointF()).y())
            self.click_item(window, card)
            self.assertEqual(window.property("mode"), "detail")

    def test_today_badge_clears_on_other_dates_and_button_returns_to_today(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380,360)
            QTest.qWait(80)
            today = desk.days.index(calendar.todayDate)
            other = 4 if today != 4 else 5
            headers = window.findChild(QObject, "dayHeaders")
            agenda = window.findChild(QObject, "dayAgenda")
            back = window.findChild(QObject, "backTodayButton")
            self.assertFalse(back.isVisible())
            badge, = visual_items(headers, "todayBadge")
            label, = visual_items(badge, "dateNumber")
            self.assertEqual((label.x(), label.y(), label.width(), label.height()),
                             (0, 0, badge.width(), badge.height()))
            gutter = headers.property("gutter")
            self.click_item(window, headers, gutter + (headers.width()-gutter)*(other+0.5)/7, 20)
            QTest.qWait(70)
            self.assertEqual(agenda.property("day"), desk.days[other])
            self.assertFalse(visual_items(headers, "todayBadge"))
            self.assertTrue(back.isVisible())
            add = window.findChild(QObject, "floatingAddButton")
            self.assertLess(back.mapToScene(QPointF(back.width(), 0)).x(), add.mapToScene(QPointF()).x())
            self.assertGreater(agenda.mapToScene(QPointF(0, agenda.height())).y(),
                               back.mapToScene(QPointF()).y())
            self.assertAlmostEqual(agenda.mapToScene(QPointF(0, agenda.height()-agenda.property("trailingSpace"))).y(),
                                   back.mapToScene(QPointF()).y()-6)
            self.click_item(window, back)
            self.assertEqual(agenda.property("day"), calendar.todayDate)
            self.assertFalse(back.isVisible())
            desk.week(1)
            for width, height in ((1024, 680), (380, 360)):
                window.resize(width, height)
                QTest.qWait(80)
                self.assertTrue(back.isVisible())
                self.assertEqual((back.width(), back.height()), (add.width(), add.height()))
                self.assertAlmostEqual(back.mapToScene(QPointF()).y(), add.mapToScene(QPointF()).y())
            self.click_item(window, back)
            self.assertTrue(desk.currentWeek)
            self.assertEqual(agenda.property("day"), calendar.todayDate)

    def test_compact_views_keep_weekday_alignment_and_last_agenda_item_accessible(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380, 360)
            sunday = desk.days[6]
            store.apply_manual([
                dict(fields=dict(title=f"上午安排 {hour}", start=f"{sunday}T{hour:02d}:00"))
                for hour in range(8, 14)
            ] + [dict(fields=dict(title="明德楼801会议", location="明德楼 801", start=sunday+"T22:30"))])
            calendar.changed.emit()
            self.app.processEvents()
            headers = window.findChild(QObject, "dayHeaders")
            agenda = window.findChild(QObject, "dayAgenda")
            grid = window.findChild(QObject, "weekGrid")
            week_button = window.findChild(QObject, "backToWeekButton")
            self.assertTrue(grid.isVisible())
            self.assertFalse(agenda.isVisible())
            self.assertFalse(week_button.isVisible())
            day_labels = visual_items(headers, "dateNumber")
            sunday_label = day_labels[-1]
            sunday_x = sunday_label.mapToScene(QPointF(sunday_label.width()/2, 0)).x()
            self.click_item(window, sunday_label)
            self.assertTrue(agenda.isVisible())
            self.assertTrue(week_button.isVisible())
            self.assertAlmostEqual(week_button.mapToScene(QPointF(week_button.width(), 0)).x(),
                                   headers.mapToScene(QPointF(headers.property("gutter"), 0)).x())
            self.assertEqual(agenda.property("day"), sunday)
            agenda.positionViewAtEnd()
            QTest.qWait(60)
            last, = [entry for entry in visual_items(agenda, "agendaEntry")
                     if entry.property("contentItem").property("summary") == "22:30"]
            self.assertEqual(last.property("contentItem").property("location"), "")
            add_button = window.findChild(QObject, "floatingAddButton")
            self.assertLess(last.mapToScene(QPointF(0, last.height())).y(), add_button.mapToScene(QPointF()).y())
            self.click_item(window, week_button)
            QTest.qWait(50)
            self.assertFalse(agenda.isVisible())
            self.assertTrue(grid.isVisible())
            self.assertFalse(week_button.isVisible())
            self.assertAlmostEqual(sunday_label.mapToScene(QPointF(sunday_label.width()/2, 0)).x(), sunday_x)
            chip, = visual_items(window.contentItem(), "latePeriodDay6")
            self.assertAlmostEqual(chip.mapToScene(QPointF(chip.width()/2, 0)).x(), sunday_x, delta=1)
            self.click_item(window, chip)
            self.assertEqual(chip.property("text"), "收起")
            self.click_item(window, sunday_label)
            self.assertTrue(agenda.isVisible())
            self.assertEqual(agenda.property("day"), sunday)

    def test_short_events_render_side_by_side_when_minimum_heights_collide(self):
        with self.scene() as (window, desk, store, calendar):
            key = store.new_draft("短活动布局测试")
            day = desk.days[4]
            store.propose_changes(key, [
                dict(fields=dict(title="活动甲", start=day+"T21:00", end=day+"T21:04")),
                dict(fields=dict(title="活动乙", start=day+"T21:55", end=day+"T21:59")),
            ])
            store.confirm(key)
            calendar.changed.emit()
            window.resize(720, 360)
            QTest.qWait(90)
            first, second = visual_items(window.contentItem(), "weekEvent")
            self.assertGreater(first.y()+first.height(), second.y())
            self.assertLessEqual(first.x()+first.width(), second.x())
            surface, = visual_items(first, "eventTimeSurface")
            grid = window.findChild(QObject, "weekGrid")
            self.assertAlmostEqual(first.y() + surface.y(), grid.timeY(21 * 60))
            self.assertLess(surface.height(), first.height())
            window.resize(1000, 900)
            QTest.qWait(90)
            self.assertLessEqual(first.y()+first.height(), second.y())
            self.assertAlmostEqual(first.x(), second.x())

    def test_api_settings_menu_saves_encrypted_credentials(self):
        from rooplan.settings import AISettings
        with self.scene() as (window, desk, store, calendar):
            window.resize(700,700)
            menu = window.findChild(QObject, "windowMenu")
            QMetaObject.invokeMethod(menu, "open")
            QTest.qWait(180)
            action = visual_items(menu.property("contentItem"), "menuAction_api")[0]
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                             action.mapToScene(QPointF(action.width()/2,action.height()/2)).toPoint())
            QTest.qWait(200)
            self.assertEqual(window.property("mode"), "api")
            field = window.findChild(QObject, "apiKeyInput")
            field.setProperty("text", "test-saved-through-ui")
            button = window.findChild(QObject, "saveAPIButton")
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                             button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint())
            self.app.processEvents()
            self.assertEqual(window.property("mode"), "")
            settings = AISettings(Path(store.path).parent)
            self.assertEqual(settings.key, "test-saved-through-ui")
            self.assertNotIn(settings.key, settings.path.read_text(encoding="utf-8"))

    def click_text(self, window, label):
        def by_text(item):
            if item.property("text") == label:
                return item
            for child in item.childItems():
                match = by_text(child)
                if match is not None:
                    return match

        button = by_text(window.contentItem())
        self.assertIsNotNone(button)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
        self.app.processEvents()

    def test_missing_key_keeps_settings_open_for_import_and_retry(self):
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": ""}), self.scene() as (window, desk, store, calendar):
            window.resize(900, 700)
            window.setProperty("mode", "import")
            QTest.qWait(200)
            field = window.findChild(QObject, "noticeInput")
            field.setProperty("text", "组会通知")
            self.click_text(window, "解析成草稿")
            self.assertEqual(window.property("mode"), "api")
            QTest.qWait(200)
            self.click_text(window, "关闭")
            draft = store.draft(store.pending()[0]["id"])
            self.assertEqual(draft["source"], "组会通知")
            self.assertEqual(window.property("mode"), "review")
            self.assertEqual(window.property("draft").toVariant()["id"], draft["id"])
            QTest.qWait(200)
            self.click_text(window, "解析通知")
            self.assertEqual(window.property("mode"), "api")
            self.assertEqual(len(store.pending()), 1)
            self.assertFalse(store.all())

    def test_supplement_changes_draft_only_when_saved(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(900, 740)
            key = store.new_draft("会议通知")
            original = store.propose_changes(key, [dict(fields=dict(title="组会", start=desk.days[0]+"T10:00"))])
            window.setProperty("draft", original)
            window.setProperty("mode", "review")
            QTest.qWait(200)
            self.click_text(window, "手动补一项")
            QTest.qWait(200)
            self.click_text(window, "关闭")
            self.assertEqual(store.draft(key), original)
            QTest.qWait(200)
            self.click_text(window, "手动补一项")
            QTest.qWait(200)
            window.findChild(QObject, "nameField").setProperty("text", "整理记录")
            window.findChild(QObject, "dateField").setProperty("text", desk.days[0])
            window.findChild(QObject, "timeField").setProperty("text", "11:00")
            self.click_text(window, "保存")
            self.assertEqual(window.property("mode"), "review")
            self.assertEqual([r["after"]["title"] for r in store.draft(key)["rows"]], ["组会", "整理记录"])
            self.assertFalse(store.all())
            store.confirm(key)
            self.assertEqual(len(store.all()), 2)

    def test_first_key_save_resumes_pending_import_and_restart_remembers(self):
        with self.scene() as (window, desk, store, calendar):
            folder = Path(store.path).parent
            inbox = Inbox(store, folder, calendar)
            response = dict(tool_calls=[dict(id="one", function=dict(name="propose_changes",
                arguments='{"changes":[{"fields":{"title":"Meeting","start":"2026-11-21T09:15"}}]}'))])
            with patch("rooplan.agent.QwenClient.complete", return_value=response):
                key = inbox.submit("Meeting notification", "")
                self.assertIsNotNone(inbox.waiting)
                self.assertTrue(inbox.saveAPI("qwen", inbox.settings.base, "qwen3.8-flash", "saved-test"))
                for _ in range(100):
                    QTest.qWait(10)
                    if not inbox.busy:
                        break
                self.assertFalse(inbox.busy)
                self.assertIsNone(inbox.waiting)
                self.assertEqual(len(store.draft(key)["rows"]), 1)
            restored = Inbox(store, folder, calendar)
            self.assertEqual(restored.client.key, "saved-test")

    def test_glass_surfaces_reveal_background_and_support_solid_fallback(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(840, 580)
            toolbar = window.findChild(QObject, "weekToolbarGlass")
            toolbar.setProperty("glass", True)
            QTest.qWait(80)
            frame = window.grabWindow()
            center = frame.width() // 2
            self.assertLess(frame.pixelColor(center, 16).alpha(), 230)
            self.assertEqual(frame.pixelColor(center, frame.height() // 2).alpha(), 255)
            toolbar.setProperty("glass", False)
            self.assertEqual(window.grabWindow().pixelColor(center, 16).alpha(), 255)

            desk.fold()
            desk.showPreview()
            QTest.qWait(240)
            preview = window.findChild(QObject, "todayPanel")
            surface = preview.findChild(QObject, "todayGlass")
            surface.setProperty("glass", True)
            frame = preview.grabWindow()
            x, y = frame.width() - 26, frame.height() // 2
            self.assertLess(frame.pixelColor(x, y).alpha(), 230)
            surface.setProperty("glass", False)
            self.assertEqual(preview.grabWindow().pixelColor(x, y).alpha(), 255)

    def test_handle_hover_today_preview_and_open_item(self):
        with self.scene() as (window, desk, store, calendar):
            today = str(datetime.now().date())
            key = store.new_draft("今日安排")
            draft = store.propose_changes(key, [dict(fields=dict(
                title="今日会议", start=today+"T10:00", end=today+"T11:00"))])
            store.confirm(key)
            calendar.changed.emit()
            desk.settings.update(side="left", anchor=100)
            desk.geometry(True)
            self.app.processEvents()
            handle = window.findChild(QObject, "edgeHandle")
            idle_color = handle.property("color")
            if desk.transparencyEnabled:
                self.assertLessEqual(idle_color.alphaF(), 0.25)
            self.assertEqual((handle.width(), handle.height()), (20, 56))
            QTest.mouseMove(desk.edge_window, QPoint(12, 50))
            QTest.qWait(480)
            self.assertGreater(handle.property("color").alphaF(), 0.5)
            self.assertNotEqual(handle.property("color"), idle_color)
            self.assertTrue(desk.previewing)
            preview = window.findChild(QObject, "todayPanel")
            self.assertTrue(preview.property("visible"))
            self.assertEqual(preview.findChild(QObject, "todayList").property("count"), 1)
            self.assertEqual(desk.edge_window.width(), 24)
            desk.deferHidePreview()
            QTest.mouseMove(preview, QPoint(50, 60))
            self.app.processEvents()
            self.assertTrue(preview.findChild(QObject, "todayHover").property("hovered"))
            QTest.qWait(400)
            self.assertTrue(desk.previewing)
            row = visual_items(preview.contentItem(), "todayEntry")[0]
            center = row.mapToScene(QPointF(row.width() / 2, row.height() / 2)).toPoint()
            QTest.mouseClick(preview, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, center)
            self.app.processEvents()
            self.assertFalse(desk.previewing)
            self.assertFalse(desk.collapsed)
            self.assertEqual(window.property("mode"), "detail")
            current = window.property("current").toVariant()
            self.assertEqual(current["id"], draft["rows"][0]["id"])

    def test_today_preview_wheel_changes_featured_entry_without_moving_card(self):
        class Clock(datetime):
            @classmethod
            def now(cls):
                return cls(2026, 11, 20, 9)

        with patch("rooplan.calendar.datetime", Clock), self.scene() as (window, desk, store, calendar):
            key = store.new_draft("今日预览")
            draft = store.propose_changes(key, [dict(fields=dict(title=title, start=start, kind=kind)) for
                title, start, kind in (
                    ("晨会", "2026-11-20T10:00", "event"),
                    ("组会", "2026-11-20T11:00", "event"),
                    ("提交材料", "2026-11-20T12:00", "deadline"),
                    ("下午讨论", "2026-11-20T14:00", "event"),
                )])
            store.confirm(key)
            calendar.changed.emit()
            desk.settings.update(side="right", anchor=100)
            desk.geometry(True)
            desk.showPreview()
            QTest.qWait(200)
            preview = window.findChild(QObject, "todayPanel")
            geometry = preview.geometry()
            highlighter = preview.findChild(QObject, "todayHighlight")
            agenda = preview.findChild(QObject, "todayList")
            rows = visual_items(preview.contentItem(), "todayEntry")
            inside = rows[0].mapToScene(QPointF(rows[0].width() / 2, rows[0].height() / 2)).toPoint()

            def titles():
                return [row.property("entry").toVariant()["title"] for row in rows]

            def wheel(delta):
                QTest.wheelEvent(preview, inside, QPoint(0, delta))
                self.app.processEvents()

            def pixel_wheel(delta):
                event = QWheelEvent(QPointF(inside), QPointF(preview.mapToGlobal(inside)),
                                    QPoint(0, delta), QPoint(), Qt.MouseButton.NoButton,
                                    Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
                QCoreApplication.sendEvent(preview, event)
                self.app.processEvents()

            original_order = ["晨会", "组会", "提交材料", "下午讨论"]
            self.assertEqual(titles(), original_order)
            self.assertTrue(rows[0].property("expanded"))
            initial_highlight = highlighter.mapToScene(QPointF()).y()
            pixel_wheel(-22)
            self.assertEqual(preview.property("featuredIndex"), 0)
            pixel_wheel(-22)
            QTest.qWait(180)
            self.assertEqual(titles(), original_order)
            self.assertFalse(rows[0].property("expanded"))
            self.assertTrue(rows[1].property("expanded"))
            self.assertLess(rows[0].y(), rows[1].y())
            self.assertGreater(highlighter.mapToScene(QPointF()).y(), initial_highlight)
            self.assertAlmostEqual(highlighter.y(), rows[1].y())
            self.assertEqual(agenda.property("scrollOffset"), 0)
            wheel(-120)
            QTest.qWait(180)
            self.assertEqual(rows[2].property("badge"), "截止")
            self.assertTrue(rows[2].property("expanded"))
            wheel(-120)
            wheel(-120)
            QTest.qWait(180)
            self.assertTrue(rows[3].property("expanded"))
            self.assertGreater(agenda.property("scrollOffset"), 0)
            self.assertLessEqual(highlighter.mapToScene(QPointF(0, highlighter.height())).y(),
                                 agenda.mapToScene(QPointF(0, agenda.height())).y())
            self.assertEqual(preview.geometry(), geometry)
            wheel(120)
            self.assertEqual(preview.property("featuredIndex"), 2)
            desk.hidePreview()
            desk.showPreview()
            self.assertEqual(preview.property("featuredIndex"), 0)
            wheel(-120)
            QTest.qWait(200)
            featured = rows[1]
            center = featured.mapToScene(QPointF(featured.width() / 2, featured.height() / 2)).toPoint()
            QTest.mouseClick(preview, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
            self.assertEqual(window.property("current").toVariant()["id"], draft["rows"][1]["id"])
            self.assertFalse(desk.previewing)

    def test_mouse_hover_never_drags_or_resizes(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(1000, 700)
            self.app.processEvents()
            before = window.geometry()
            for point in (QPoint(100, 30), QPoint(200, 30), QPoint(3, 3),
                          QPoint(997, 300), QPoint(500, 697)):
                QTest.mouseMove(window, point)
                self.app.processEvents()
                self.assertEqual(window.geometry(), before)
                self.assertIsNone(desk.drag)
                self.assertFalse(desk.resizing)
            for edge in ("left", "right", "top", "bottom"):
                desk.settings.update(side=edge, anchor=100)
                desk.geometry(True)
                self.app.processEvents()
                edge_window = desk.edge_window
                before = edge_window.geometry()
                for delta in (0, 3, -3):
                    point = QPoint(edge_window.width()//2, edge_window.height()//2+delta)
                    QTest.mouseMove(edge_window, point)
                    self.app.processEvents()
                    self.assertEqual(edge_window.geometry(), before)
                    self.assertIsNone(desk.drag)
                    self.assertFalse(desk.resizing)
                mouse = window.findChild(QObject, "handleMouse")
                self.assertEqual(mouse.property("cursorShape"), Qt.CursorShape.PointingHandCursor)

    def test_pin_button_toggles_window_flag_without_moving_window(self):
        with self.scene() as (window, desk, store, calendar):
            window.resize(380,360)
            QTest.qWait(40)
            button = window.findChild(QObject, "pinButton")
            before = window.geometry()
            self.assertFalse(window.flags() & Qt.WindowType.WindowStaysOnTopHint)
            for pinned in (True, False):
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                 button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint())
                self.app.processEvents()
                self.assertEqual(desk.pinned, pinned)
                self.assertEqual(button.property("checked"), pinned)
                self.assertEqual(bool(window.flags() & Qt.WindowType.WindowStaysOnTopHint), pinned)
                self.assertTrue(window.isVisible())
                self.assertEqual(window.geometry(), before)

    def test_canceling_handle_press_does_not_expand(self):
        with self.scene() as (window, desk, store, calendar):
            desk.settings.update(side="left", anchor=100)
            desk.geometry(True)
            self.app.processEvents()
            edge_window = desk.edge_window
            before = edge_window.geometry()
            QTest.mousePress(edge_window, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier, QPoint(12, 50))
            self.assertIsNotNone(desk.drag)
            QMetaObject.invokeMethod(window.findChild(QObject, "handleMouse"), "canceled")
            self.assertIsNone(desk.drag)
            self.assertTrue(desk.collapsed)
            QTest.mouseRelease(edge_window, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier, QPoint(12, 50))
            QTest.mouseMove(edge_window, QPoint(12, 70))
            self.assertEqual(edge_window.geometry(), before)
            self.assertTrue(desk.collapsed)

    def test_calendar_opening_uses_clicked_source_and_waits_for_transparent_frames(self):
        with self.scene() as (window, desk, store, calendar):
            edge_window = desk.edge_window
            panel = window.findChild(QObject, "calendarPanel")
            handle = window.findChild(QObject, "edgeHandle")
            preview = window.findChild(QObject, "todayPanel")
            surface = window.findChild(QObject, "calendarOpeningSurface")
            source_copy = window.findChild(QObject, "calendarOpeningCopy")
            resizing_frames = []
            showing_frames = []
            handoff_frames = []
            animation_sizes = []
            handoffs = []
            set_geometry = window.setGeometry
            hide_edge = edge_window.hide
            main_handle = window.winId()
            frames = QSignalSpy(window.frameSwapped)

            def record_resize(*geometry):
                resizing_frames.append((window.isVisible(), window.opacity(), edge_window.isVisible(), preview.isVisible()))
                set_geometry(*geometry)

            def record_showing():
                if desk.opening_calendar and window.isVisible():
                    showing_frames.append((window.opacity(), panel.opacity()))

            def record_animation():
                if surface.isVisible():
                    animation_sizes.append((surface.width(), surface.height()))

            def record_handoff():
                handoff_frames.append((frames.count() - frames_before_open >= 2, edge_window.isVisible(),
                                       source_copy.isVisible(), panel.opacity(), window.opacity()))
                hide_edge()

            surface.widthChanged.connect(record_animation)
            window.visibleChanged.connect(record_showing)
            desk.calendarOpeningReady.connect(handoffs.append)
            for side, show_preview, click_preview in (("left", False, False), ("right", True, False),
                                                       ("top", True, True), ("bottom", True, True)):
                with self.subTest(side=side):
                    desk.settings.update(side=side, anchor=100, width=820, height=560)
                    desk.geometry(True)
                    if show_preview:
                        desk.showPreview()
                    QTest.qWait(175)
                    self.assertFalse(window.isVisible())
                    self.assertTrue(edge_window.isVisible())
                    self.assertIsNone(edge_window.transientParent())
                    edge_handle = edge_window.winId()
                    self.assertNotEqual(edge_handle, main_handle)
                    handle_geometry = edge_window.geometry()
                    source = preview.findChild(QObject, "todayGlass") if click_preview else handle
                    origin = source.mapToGlobal(QPointF())
                    source_size = (source.width(), source.height())
                    resizing_frames.clear()
                    showing_frames.clear()
                    handoff_frames.clear()
                    animation_sizes.clear()
                    handoffs.clear()

                    frames_before_open = frames.count()
                    with (patch.object(Desktop, "motionEnabled", True),
                          patch.object(window, "setGeometry", side_effect=record_resize),
                          patch.object(edge_window, "hide", side_effect=record_handoff)):
                        if click_preview:
                            button = preview.findChild(QObject, "todayOpenWeek")
                            self.click_item(preview, button)
                        else:
                            self.click_item(edge_window, handle)
                        self.assertTrue(edge_window.isVisible())
                        self.assertTrue(desk.opening_calendar)
                        for _ in range(40):
                            if handoffs and not surface.isVisible():
                                break
                            QTest.qWait(30)

                    self.assertFalse(desk.collapsed)
                    self.assertFalse(desk.previewing)
                    self.assertTrue(window.isVisible())
                    self.assertFalse(edge_window.isVisible())
                    self.assertEqual(edge_window.geometry(), handle_geometry)
                    self.assertEqual(edge_window.winId(), edge_handle)
                    self.assertEqual(window.winId(), main_handle)
                    self.assertTrue(panel.isVisible())
                    self.assertEqual(resizing_frames, [(False, 0.0, True, show_preview)])
                    self.assertEqual(showing_frames, [(0.0, 0.0)])
                    self.assertEqual(handoff_frames, [(True, True, True, 0.0, 1.0)])
                    self.assertEqual(handoffs, [True])
                    self.assertEqual(window.size().toTuple(), (820, 560))
                    start = window.property("calendarOpeningOrigin")
                    self.assertEqual(start.topLeft(), origin)
                    self.assertEqual((start.width(), start.height()), source_size)
                    self.assertTrue(any(start.width() < width < window.width() and
                                        start.height() < height < window.height()
                                        for width, height in animation_sizes))
                    self.assertFalse(surface.isVisible())
                    self.assertEqual(panel.opacity(), 1.0)
                    self.assertTrue(panel.isEnabled())

    def test_calendar_opening_respects_reduced_motion(self):
        with self.scene() as (window, desk, store, calendar):
            desk.fold()
            desk.showPreview()
            self.app.processEvents()
            with patch.object(Desktop, "motionEnabled", False):
                desk.expand(True)
            self.assertFalse(desk.collapsed)
            self.assertFalse(desk.previewing)
            panel = window.findChild(QObject, "calendarPanel")
            surface = window.findChild(QObject, "calendarOpeningSurface")
            self.assertTrue(panel.isVisible())
            self.assertFalse(surface.isVisible())
            self.assertEqual(panel.opacity(), 1.0)
