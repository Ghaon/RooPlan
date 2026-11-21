import os
import unittest
from unittest.mock import Mock

from rooplan.fullscreen import FullscreenDetector


class FullscreenTests(unittest.TestCase):
    def setUp(self):
        self.detector = FullscreenDetector()
        self.api = Mock()
        self.detector.api = self.api
        self.api.GetForegroundWindow.return_value = 20
        self.api.GetWindowThreadProcessId.side_effect = lambda handle, process: setattr(process._obj, "value", os.getpid()+100)
        self.api.IsWindowVisible.return_value = True
        self.api.IsIconic.return_value = False
        self.api.IsZoomed.return_value = False
        self.api.GetWindowLongW.return_value = 0
        self.api.GetClassNameW.side_effect = lambda handle, name, size: setattr(name, "value", "VideoPlayer")
        self.api.MonitorFromWindow.return_value = 5
        self.rect = (0,0,1920,1080)

        def monitor_info(handle, info):
            rect = info._obj.monitor
            rect.left, rect.top, rect.right, rect.bottom = (0,0,1920,1080)
            return True

        def window_rect(handle, value):
            value._obj.left, value._obj.top, value._obj.right, value._obj.bottom = self.rect
            return True

        self.api.GetMonitorInfoW.side_effect = monitor_info
        self.api.GetWindowRect.side_effect = window_rect

    def test_fullscreen_video_and_normal_maximized_window(self):
        self.assertTrue(self.detector.active(10))
        self.rect = (0,0,1920,1040)
        self.assertFalse(self.detector.active(10))
        self.rect = (-8,-8,1928,1088)
        self.api.IsZoomed.return_value = True
        self.api.GetWindowLongW.return_value = 0x00C00000
        self.assertFalse(self.detector.active(10))

    def test_other_monitor_desktop_own_process_and_transition(self):
        self.api.MonitorFromWindow.side_effect = lambda handle, flags: 5 if handle == 10 else 6
        self.assertFalse(self.detector.active(10))
        self.api.MonitorFromWindow.side_effect = None
        self.api.GetClassNameW.side_effect = lambda handle, name, size: setattr(name, "value", "WorkerW")
        self.assertFalse(self.detector.active(10))
        self.api.GetWindowThreadProcessId.side_effect = lambda handle, process: setattr(process._obj, "value", os.getpid())
        self.assertFalse(self.detector.active(10))
        self.api.GetForegroundWindow.return_value = 0
        self.assertIsNone(self.detector.active(10))
