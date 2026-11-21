"""Read foreground window geometry without capturing the screen."""
import ctypes
import os
from ctypes import wintypes


def covers_monitor(window, monitor, tolerance=2):
    return (window.left <= monitor.left+tolerance and window.top <= monitor.top+tolerance
            and window.right >= monitor.right-tolerance and window.bottom >= monitor.bottom-tolerance)


class FullscreenDetector:
    def __init__(self):
        self.api = None
        if os.name != "nt":
            return
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        signatures = {
            "GetForegroundWindow": ([], wintypes.HWND),
            "GetWindowThreadProcessId": ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            "IsWindowVisible": ([wintypes.HWND], wintypes.BOOL),
            "IsIconic": ([wintypes.HWND], wintypes.BOOL),
            "IsZoomed": ([wintypes.HWND], wintypes.BOOL),
            "GetWindowLongW": ([wintypes.HWND, ctypes.c_int], wintypes.LONG),
            "GetClassNameW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "GetWindowRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            "MonitorFromWindow": ([wintypes.HWND, wintypes.DWORD], wintypes.HANDLE),
            "GetMonitorInfoW": ([wintypes.HANDLE, ctypes.c_void_p], wintypes.BOOL),
        }
        for name, (args, result) in signatures.items():
            operation = getattr(self.api, name)
            operation.argtypes, operation.restype = args, result

    def active(self, own_handle):
        if not self.api:
            return False
        foreground = self.api.GetForegroundWindow()
        if not foreground:
            return None
        process = wintypes.DWORD()
        self.api.GetWindowThreadProcessId(foreground, ctypes.byref(process))
        if process.value == os.getpid() or not self.api.IsWindowVisible(foreground) or self.api.IsIconic(foreground):
            return False
        name = ctypes.create_unicode_buffer(256)
        self.api.GetClassNameW(foreground, name, len(name))
        if name.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            return False
        # Maximized captioned applications remain ordinary desktop windows.
        if self.api.IsZoomed(foreground) and self.api.GetWindowLongW(foreground, -16) & 0x00C00000:
            return False
        monitor = self.api.MonitorFromWindow(own_handle, 2)
        if not monitor or self.api.MonitorFromWindow(foreground, 2) != monitor:
            return False

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                        ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        rect = wintypes.RECT()
        if not self.api.GetMonitorInfoW(monitor, ctypes.byref(info)) or not self.api.GetWindowRect(foreground, ctypes.byref(rect)):
            return None
        return covers_monitor(rect, info.monitor)
