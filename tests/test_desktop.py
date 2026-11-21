import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QPoint, QRect, Qt, QEvent
from PySide6.QtGui import QGuiApplication, QWindow

from rooplan.desktop import Desktop


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.window = QWindow()
        self.window.setFlags(Qt.WindowType.FramelessWindowHint)
        self.edge_window = QWindow()
        self.desk = Desktop(self.folder)
        self.desk.attach(self.window, self.edge_window)
        self.desk.timer.stop()

    def tearDown(self):
        self.app.removeEventFilter(self.desk)
        self.edge_window.close()
        self.window.close()

    def test_current_week(self):
        self.assertTrue(self.desk.currentWeek)
        first = self.desk.days
        self.desk.week(1)
        self.assertFalse(self.desk.currentWeek)
        self.assertNotEqual(first, self.desk.days)
        self.desk.week(0)
        self.assertEqual(first, self.desk.days)

    def test_pinned_preference_survives_fold_and_restart(self):
        self.assertFalse(self.desk.pinned)
        self.assertFalse(self.window.flags() & Qt.WindowType.WindowStaysOnTopHint)
        self.desk.togglePinned()
        self.assertTrue(self.window.flags() & Qt.WindowType.WindowStaysOnTopHint)
        self.assertTrue(Desktop(self.folder).pinned)
        self.desk.fold()
        self.desk.expand()
        self.assertTrue(self.window.flags() & Qt.WindowType.WindowStaysOnTopHint)
        self.desk.togglePinned()
        self.desk.fold()
        self.assertTrue(self.edge_window.flags() & Qt.WindowType.WindowStaysOnTopHint)
        self.desk.expand()
        self.assertFalse(self.window.flags() & Qt.WindowType.WindowStaysOnTopHint)
        self.assertFalse(self.window.flags() & Qt.WindowType.WindowDoesNotAcceptFocus)

    def test_fullscreen_hides_handle_and_preview_and_restores_without_expanding(self):
        self.window.show()
        self.desk.fold()
        self.desk.showPreview()
        before = self.edge_window.geometry()
        with patch("rooplan.desktop.QGuiApplication.platformName", return_value="windows"), patch.object(self.desk.fullscreen_detector, "active", return_value=True) as detect:
            self.desk.tick()
            self.assertTrue(self.desk.fullscreen_hidden)
            self.assertFalse(self.edge_window.isVisible())
            self.assertFalse(self.desk.previewing)
            self.desk.showPreview()
            self.assertFalse(self.desk.previewing)
            detect.return_value = None
            self.desk.tick()
            self.assertFalse(self.edge_window.isVisible())
            detect.return_value = False
            self.desk.tick()
            self.assertTrue(self.edge_window.isVisible())
            self.assertTrue(self.desk.collapsed)
            self.assertEqual(self.edge_window.geometry(), before)
            self.assertTrue(self.edge_window.flags() & Qt.WindowType.WindowDoesNotAcceptFocus)
            detect.return_value = True
            self.desk.tick()
            self.desk.reveal()
            self.assertFalse(self.desk.collapsed)
            self.assertTrue(self.window.isVisible())
            self.desk.tick()
            self.assertTrue(self.window.isVisible())

    def test_four_edges_and_restart(self):
        area = self.desk.screen.availableGeometry()
        for edge in ("left", "right", "top", "bottom"):
            with self.subTest(edge=edge):
                self.desk.settings.update(side=edge, anchor=100000)
                self.desk.geometry(True)
                rect = self.edge_window.geometry()
                self.assertTrue(area.contains(rect))
                self.assertEqual((rect.width(), rect.height()),
                                 (100, 24) if edge in ("top", "bottom") else (24, 100))
                self.assertEqual(self.desk.edge_distances(rect, area)[edge], 0)
                self.desk.save()
                restored = Desktop(self.folder)
                other = QWindow()
                other_edge = QWindow()
                restored.attach(other, other_edge)
                restored.timer.stop()
                self.assertEqual(other_edge.geometry(), rect)
                self.assertTrue(restored.collapsed)
                self.assertFalse(other.isVisible())
                self.assertTrue(other_edge.isVisible())
                self.app.removeEventFilter(restored)
                other_edge.close()
                other.close()

    def test_prepare_size_survives_fold(self):
        self.window.resize(820, 560)
        self.desk.settings["side"] = "top"
        self.desk.fold()
        self.desk.expand()
        self.assertEqual((self.window.width(), self.window.height()),
                         (820, 560))

    def test_resize_keeps_opposite_corner_and_usable_minimum(self):
        self.window.setGeometry(100, 100, 900, 650)
        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton), patch("rooplan.desktop.QCursor.pos", return_value=QPoint(1000, 750)) as cursor:
            self.desk.resize(int(Qt.Edge.RightEdge.value | Qt.Edge.BottomEdge.value))
            cursor.return_value = QPoint(1100, 800)
            self.desk.moveResize()
            self.assertEqual((self.window.width(), self.window.height()), (1000, 700))
            self.assertEqual(self.window.position(), QPoint(100, 100))
            cursor.return_value = QPoint(300, 200)
            self.desk.moveResize()
            self.assertEqual((self.window.width(), self.window.height()), (380, 360))
            self.desk.endResize()
            self.assertFalse(self.desk.resizing)
            self.assertEqual(Desktop(self.folder).settings["width"], 380)

    def test_preview_fits_all_edges_and_restores_handle(self):
        for edge in ("left", "right", "top", "bottom"):
            self.desk.settings.update(side=edge, anchor=100)
            self.desk.geometry(True)
            handle = self.edge_window.geometry()
            self.desk.showPreview()
            self.assertTrue(self.desk.previewing)
            self.assertEqual(self.edge_window.geometry(), handle)
            rect = self.desk.previewGeometry(257)
            area = self.desk.screen.availableGeometry()
            preview = QRect(rect["x"], rect["y"], rect["width"], rect["height"])
            self.assertTrue(area.contains(preview))
            self.assertFalse(handle.intersects(preview))
            self.assertEqual((preview.width(), preview.height()), (296, 257))
            self.desk.deferHidePreview()
            self.assertTrue(self.desk.preview_close.isActive())
            self.desk.keepPreview()
            self.assertFalse(self.desk.preview_close.isActive())
            self.desk.expand()
            self.assertFalse(self.desk.previewing)

    def test_native_resize_keeps_ownership_and_saves_final_geometry(self):
        self.window.setGeometry(100,100,900,650)
        edges = Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        def transfer_grab(edges):
            self.desk.cancelResizeGrab()
            return True

        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton), patch("rooplan.desktop.QGuiApplication.platformName", return_value="windows"), patch.object(self.window,"startSystemResize",side_effect=transfer_grab) as native:
            self.desk.resize(edges.value, 103,103)
            native.assert_called_once_with(edges)
            self.assertTrue(self.desk.system_resizing)
            self.desk.cancelResizeGrab()
            self.assertTrue(self.desk.resizing)
            self.desk.moveResize(50,50)
            self.assertEqual(self.window.geometry().getRect(), (100,100,900,650))
            self.window.setGeometry(50,50,950,700)
        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton), patch("rooplan.desktop.QGuiApplication.platformName", return_value="windows"), patch("rooplan.desktop.ctypes.windll.user32.GetAsyncKeyState", return_value=0):
            self.desk.tick()
        self.assertFalse(self.desk.resizing)
        self.assertFalse(self.desk.system_resizing)
        self.assertEqual((self.desk.settings["width"],self.desk.settings["height"]), (950,700))

    def test_saved_tiny_window_recovers_usable_size(self):
        for size in ((160, 100), (2400, 1500)):
            self.window.resize(*size)
            self.desk.fold()
            self.desk.expand()
            self.assertEqual((self.window.width(), self.window.height()),
                             (max(380, size[0]), max(360, size[1])))

    def test_drag_handle_across_edges_and_click_expand(self):
        area = self.desk.screen.availableGeometry()
        self.desk.settings.update(side="left", anchor=area.top()+80)
        self.desk.geometry(True)
        start = self.edge_window.position() + QPoint(12, 50)
        end = QPoint(area.center().x(), area.top()+12)
        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton), patch("rooplan.desktop.QCursor.pos", return_value=start) as cursor:
            self.desk.dragStart()
            cursor.return_value = end
            self.desk.dragMove()
            self.desk.dragEnd()
            self.assertTrue(self.desk.collapsed)
            self.assertEqual(self.desk.settings["side"], "top")
            self.assertEqual(self.edge_window.height(), 24)
            cursor.return_value = self.edge_window.geometry().center()
            self.desk.dragStart()
            self.desk.dragEnd()
            self.assertFalse(self.desk.collapsed)

    def test_expanded_drag_docks_at_pointer_edge_on_release(self):
        area = self.desk.screen.availableGeometry()
        bounds = self.desk.screen.geometry()
        center = area.center()
        targets = {
            "left": QPoint(bounds.left()+10, center.y()),
            "right": QPoint(bounds.right()-10, center.y()),
            "top": QPoint(center.x(), bounds.top()+10),
            "bottom": QPoint(center.x(), bounds.bottom()-10),
        }
        for edge, end in targets.items():
            with self.subTest(edge=edge):
                self.desk.geometry(False)
                start = self.window.position() + QPoint(140, 35)
                with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton), patch("rooplan.desktop.QCursor.pos", return_value=end):
                    self.desk.dragStart(start.x(), start.y())
                    self.desk.dragMove(end.x(), end.y())
                    self.assertFalse(self.desk.collapsed)
                    self.desk.dragEnd()
                self.assertTrue(self.desk.collapsed)
                self.assertEqual(self.desk.settings["side"], edge)
                self.assertEqual(self.desk.edge_distances(self.edge_window.geometry(), area)[edge], 0)

    def test_window_can_stay_partly_outside_any_work_area_edge(self):
        area = self.desk.screen.availableGeometry()
        center = area.center()
        targets = {
            "left": QPoint(area.left()+70, center.y()),
            "right": QPoint(area.right()-70, center.y()),
            "top": QPoint(center.x(), area.top()+20),
            "bottom": QPoint(center.x(), area.bottom()-70),
        }
        for edge, end in targets.items():
            with self.subTest(edge=edge):
                self.window.setGeometry(QRect(center-QPoint(190, 180), self.window.minimumSize()))
                start = self.window.position() + QPoint(190, 35)
                with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton), patch("rooplan.desktop.QCursor.pos", return_value=end):
                    self.desk.dragStart(start.x(), start.y())
                    self.desk.dragMove(end.x(), end.y())
                    dragged = self.window.geometry()
                    self.assertTrue(area.intersects(dragged))
                    self.assertFalse(area.contains(dragged))
                    self.desk.dragEnd()
                self.assertFalse(self.desk.collapsed)
                self.assertEqual(self.window.geometry(), dragged)

    def test_taskbar_drag_recovers_only_hidden_title_and_docks_at_screen_edge(self):
        bounds = self.desk.screen.geometry()
        area = bounds.adjusted(0, 0, 0, -48)
        screen = Mock(name="screen")
        screen.name.return_value = "test display"
        screen.geometry.return_value = bounds
        screen.availableGeometry.return_value = area
        with patch("rooplan.desktop.QGuiApplication.screenAt", return_value=screen), patch("rooplan.desktop.QGuiApplication.screens", return_value=[screen]), patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton):
            for y, docked in ((area.bottom(), False), (area.bottom()+24, False), (bounds.bottom(), True)):
                with self.subTest(y=y):
                    self.window.setGeometry(QRect(area.topLeft(), self.window.minimumSize()))
                    start = self.window.position() + QPoint(180, 35)
                    end = QPoint(area.center().x(), y)
                    self.desk.dragStart(start.x(), start.y())
                    self.desk.dragMove(end.x(), end.y())
                    dragged = self.window.geometry()
                    self.assertEqual(dragged.topLeft(), end - QPoint(180, 35))
                    self.assertGreater(dragged.bottom(), area.bottom())
                    with patch("rooplan.desktop.QCursor.pos", return_value=end):
                        self.desk.dragEnd()
                    self.assertEqual(self.desk.collapsed, docked)
                    if docked:
                        self.assertTrue(area.contains(self.edge_window.geometry()))
                    elif y == area.bottom():
                        self.assertEqual(self.window.geometry(), dragged)
                    else:
                        self.assertLess(self.window.y(), dragged.y())
                        self.assertEqual(self.window.x(), dragged.x())
                        self.assertLessEqual(self.window.y(), area.bottom()-29)
                        self.assertGreater(self.window.geometry().bottom(), area.bottom())
            self.assertEqual(self.desk.previewEdge, "bottom")
            self.assertAlmostEqual(self.edge_window.geometry().center().x(), area.center().x(), delta=1)

    def test_reveal_recovers_unreachable_title_without_repositioning_usable_window(self):
        area = self.desk.screen.availableGeometry()
        self.window.resize(380, 360)
        usable = QPoint(area.left()-120, area.bottom()-120)
        self.window.setPosition(usable)
        self.desk.reveal()
        self.assertEqual(self.window.position(), usable)
        self.window.setPosition(area.left()+50, area.bottom()+10)
        self.desk.reveal()
        self.assertTrue(self.window.isVisible())
        self.assertLessEqual(self.window.y(), area.bottom()-29)
        self.assertGreater(self.window.geometry().bottom(), area.bottom())
        self.assertFalse(self.desk.collapsed)

    def test_lost_release_and_deactivation_cancel_without_expanding(self):
        self.desk.settings.update(side="left", anchor=100)
        self.desk.geometry(True)
        start = self.edge_window.geometry().center()
        before = self.edge_window.geometry()
        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton):
            self.desk.dragStart(start.x(), start.y())
            self.assertIsNotNone(self.desk.drag)
            self.desk.eventFilter(self.edge_window, QEvent(QEvent.Type.WindowDeactivate))
            self.assertIsNone(self.desk.drag)
            self.assertTrue(self.desk.collapsed)
            self.desk.dragStart(start.x(), start.y())
        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.NoButton):
            self.desk.dragMove(start.x()+100, start.y()+100)
            self.assertIsNone(self.desk.drag)
            self.assertEqual(self.edge_window.geometry(), before)
            self.desk.dragStart(start.x(), start.y())
            self.assertIsNone(self.desk.drag)

    def test_timer_clears_stale_drag_after_release_outside_app(self):
        self.desk.settings.update(side="right", anchor=100)
        self.desk.geometry(True)
        before = self.edge_window.geometry()
        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.LeftButton):
            self.desk.dragStart()
        with patch("rooplan.desktop.QGuiApplication.mouseButtons", return_value=Qt.MouseButton.NoButton):
            self.desk.tick()
        self.assertIsNone(self.desk.drag)
        self.assertEqual(self.edge_window.geometry(), before)

    def test_idle_collapse_and_pause(self):
        self.window.show()
        inside = self.window.geometry().center()
        with patch("rooplan.desktop.QCursor.pos", return_value=inside), patch("rooplan.desktop.time.monotonic", return_value=1000):
            self.desk.last_input = 909
            self.desk.tick()
            self.assertTrue(self.desk.collapsed)
            self.desk.expand()
            self.desk.pause(True)
            self.desk.last_input = 0
            self.desk.tick()
            self.assertFalse(self.desk.collapsed)
            self.desk.pause(False)
        outside = QPoint(self.window.x()-20, self.window.y()-20)
        with patch("rooplan.desktop.QCursor.pos", return_value=outside), patch("rooplan.desktop.time.monotonic", return_value=1000):
            self.desk.outside_since = 969
            self.desk.tick()
            self.assertTrue(self.desk.collapsed)
