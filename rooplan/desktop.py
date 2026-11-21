import ctypes
import json
import sys
import time
from ctypes import wintypes
from datetime import date, timedelta

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Property, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCursor, QGuiApplication, QWindow
from PySide6.QtQuick import QQuickWindow
from .fullscreen import FullscreenDetector


class Desktop(QObject):
    MIN_WIDTH = 380
    MIN_HEIGHT = 360
    DOCK_DISTANCE = 12
    changed = Signal()
    weekChanged = Signal()
    previewChanged = Signal()
    openingCalendar = Signal(bool)
    calendarOpeningReady = Signal(bool)

    def __init__(self, folder):
        super().__init__()
        self.path = folder / 'desktop.json'
        try:
            self.settings = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.settings = {}
        self.window = None
        self.edge_window = None
        self.folded = False
        self.fullscreen_hidden = False
        self.fullscreen_detector = FullscreenDetector()
        self._previewing = False
        self.preview_hover = False
        self.preview_close = QTimer(self, interval=350, singleShot=True)
        self.preview_close.timeout.connect(self.hidePreview)
        self.opening_calendar = False
        self.opening_opacity = None
        self.opening_frames = 0
        self.opening_timeout = QTimer(self, interval=450, singleShot=True)
        self.opening_timeout.timeout.connect(self.opening_timed_out)
        self.drag = None
        self.resizing = False
        self.system_resizing = False
        self.paused = False
        self.offset = 0
        self.today = date.today()
        self.timer = QTimer(self, interval=500)
        self.timer.timeout.connect(self.tick)
        self.reset_clock()

    def attach(self, window, edge_window=None):
        self.window = window
        self.edge_window = edge_window if edge_window is not None else window.findChild(QWindow, "edgeWindow")
        self.window.setFlag(Qt.WindowType.WindowStaysOnTopHint, self.pinned)
        self.edge_window.setFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                                  | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.screen = next((s for s in QGuiApplication.screens()
                            if s.name() == self.settings.get('screen')),
                           QGuiApplication.primaryScreen())
        self.geometry(bool(self.settings.get('folded', False)))
        window.visibilityChanged.connect(self.changed)
        QGuiApplication.instance().installEventFilter(self)
        self.timer.start()

    @property
    def active_window(self):
        return self.edge_window if self.folded else self.window

    def reset_clock(self):
        self.last_input = time.monotonic()
        self.outside_since = None

    def eventFilter(self, obj, event):
        if obj is self.window and self.resizing:
            if event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
                point = event.globalPosition()
                self.moveResize(point.x(), point.y())
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self.endResize()
        if ((event.type() == QEvent.Type.MouseMove
             and not event.buttons() & Qt.MouseButton.LeftButton)
                or event.type() == QEvent.Type.ApplicationDeactivate
                or (event.type() == QEvent.Type.WindowDeactivate and obj is self.active_window)):
            self.cancelInteraction()
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
                            QEvent.Type.KeyPress, QEvent.Type.Wheel, QEvent.Type.TouchBegin):
            self.last_input = time.monotonic()
        return False

    @Slot()
    def cancelInteraction(self):
        recover_title = self.drag is not None and self.dragged and not self.folded
        self.drag = None
        if recover_title:
            self.keep_title_reachable(self.window.screen())
        self.endResize()
        self.reset_clock()

    def remember_size(self):
        if not self.folded and not self.maximized:
            self.settings.update(width=self.window.width(), height=self.window.height())

    def save(self):
        self.settings.update(folded=self.folded, screen=self.screen.name())
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.settings), encoding='utf-8')
        tmp.replace(self.path)

    @staticmethod
    def clamp_position(pos, size, area):
        return QPoint(max(area.left(), min(pos.x(), area.right() + 1 - size.width())),
                      max(area.top(), min(pos.y(), area.bottom() + 1 - size.height())))

    def keep_title_reachable(self, screen):
        # The toolbar begins inside the resize border and extends at least 52 px.
        rect = self.window.geometry()
        title = QRect(rect.x()+6, rect.y()+6, rect.width()-12, 46)
        grab_width, grab_height = 80, 24
        for display in QGuiApplication.screens():
            visible = title.intersected(display.availableGeometry())
            if visible.width() >= grab_width and visible.height() >= grab_height:
                return

        area = screen.availableGeometry()
        grab_width = min(grab_width, area.width())
        grab_height = min(grab_height, area.height())
        x = max(area.left()+grab_width-title.width(), min(title.x(), area.right()+1-grab_width))
        y = max(area.top()+grab_height-title.height(), min(title.y(), area.bottom()+1-grab_height))
        self.window.setPosition(rect.topLeft() + QPoint(x, y) - title.topLeft())

    def geometry(self, fold, keep_edge=False):
        self.cancelInteraction()
        target = self.edge_window if fold else self.window
        if fold:
            self.window.hide()
            if self.opening_calendar:
                self.finish_calendar_opening(False)
        else:
            if not keep_edge:
                self.hidePreview()
                self.edge_window.hide()
            self.fullscreen_hidden = False
        if self.screen not in QGuiApplication.screens():
            self.screen = QGuiApplication.primaryScreen()
        area = self.screen.availableGeometry()
        edge = self.settings.get('side', 'right')
        horizontal = edge in ('top', 'bottom')
        minimum = QSize(min(self.MIN_WIDTH, area.width()), min(self.MIN_HEIGHT, area.height()))
        width = min(area.width(), 100 if horizontal else 24) if fold else max(minimum.width(), self.settings.get('width', 1120))
        height = min(area.height(), 24 if horizontal else 100) if fold else max(minimum.height(), self.settings.get('height', 740))
        default_anchor = area.center().x() - 50 if horizontal else area.center().y() - 50
        anchor = self.settings.get('anchor', default_anchor)
        if horizontal:
            x = anchor if fold else anchor + 50 - width // 2
            y = area.top() if edge == 'top' else area.bottom() + 1 - height
        else:
            x = area.left() if edge == 'left' else area.right() + 1 - width
            y = anchor if fold else anchor + 50 - height // 2
        if not self.settings.get('side') and not fold:
            x = area.center().x() - width // 2
        pos = self.clamp_position(QPoint(x, y), QSize(width, height), area)
        target.setGeometry(pos.x(), pos.y(), width, height)
        if not fold:
            target.setMinimumSize(minimum)
        self.folded = fold
        self.changed.emit()
        if fold:
            self.update_fullscreen()
        if not self.fullscreen_hidden:
            target.show()
        self.reset_clock()

    def update_fullscreen(self):
        if not self.folded or self.opening_calendar:
            return
        active = False
        if QGuiApplication.platformName() != "offscreen":
            active = self.fullscreen_detector.active(int(self.edge_window.winId()))
        if active is None:
            return
        if active:
            self.hidePreview()
            if not self.fullscreen_hidden:
                self.cancelInteraction()
                self.fullscreen_hidden = True
                self.edge_window.hide()
                self.changed.emit()
        elif self.fullscreen_hidden:
            self.fullscreen_hidden = False
            self.edge_window.show()
            self.changed.emit()

    def tick(self):
        self.update_fullscreen()
        pressed = bool(QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        if self.system_resizing and QGuiApplication.platformName() == "windows":
            # Windows can consume the release while its native resize loop owns the mouse.
            pressed = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        if (self.drag is not None or self.resizing) and not pressed:
            self.cancelInteraction()
        if (self.folded or self.opening_calendar or self.paused or self.drag is not None
                or self.resizing or self.window.visibility() == QWindow.Visibility.Minimized):
            self.reset_clock()
            return
        now = time.monotonic()
        inside = self.window.geometry().contains(QCursor.pos())
        if inside:
            if self.outside_since is not None:
                self.last_input = now
            self.outside_since = None
        elif self.outside_since is None:
            self.outside_since = now
        if ((inside and now - self.last_input >= 90) or
                (not inside and now - self.outside_since >= 30)):
            self.fold()

    @Slot(bool)
    def pause(self, active):
        self.paused = active
        self.reset_clock()

    @staticmethod
    def edge_distances(rect, area):
        return dict(left=abs(rect.left()-area.left()), right=abs(area.right()-rect.right()),
                    top=abs(rect.top()-area.top()), bottom=abs(area.bottom()-rect.bottom()))

    def set_anchor(self, edge, point=None):
        if point is None:
            point = self.window.geometry().center()
        center = point.x() if edge in ('top', 'bottom') else point.y()
        self.settings.update(side=edge, anchor=center-50)

    @Slot()
    def fold(self):
        if not self.window or self.folded:
            return
        self.remember_size()
        self.screen = self.window.screen()
        if not self.settings.get('side'):
            distances = self.edge_distances(self.window.geometry(), self.screen.availableGeometry())
            self.set_anchor(min(distances, key=distances.get))
        if self.maximized:
            self.window.showNormal()
        self.geometry(True)
        self.save()

    @Slot()
    @Slot(bool)
    @Slot(bool, bool)
    def expand(self, animate=False, from_preview=False):
        if self.opening_calendar:
            if animate:
                return
            self.finish_calendar_opening(False)
        if (self.folded and animate and self.motionEnabled and self.edge_window.isVisible()
                and isinstance(self.window, QQuickWindow)):
            self.opening_calendar = True
            self.keepPreview()
            self.opening_timeout.start()
            self.openingCalendar.emit(from_preview)
            return
        self.geometry(False)
        self.save()
        self.window.requestActivate()

    @Slot()
    def stageCalendarOpening(self):
        if not self.opening_calendar or not self.folded:
            return
        # Windows can show the last presented buffer again when a hidden window is shown.
        self.opening_opacity = self.window.opacity()
        self.opening_frames = 0
        self.window.setOpacity(0)
        self.window.frameSwapped.connect(self.calendar_frame_swapped, Qt.ConnectionType.QueuedConnection)
        self.geometry(False, keep_edge=True)
        self.window.requestUpdate()
        self.opening_timeout.start()
        self.save()

    @Slot()
    def calendar_frame_swapped(self):
        if not self.opening_calendar or self.folded:
            return
        self.opening_frames += 1
        if self.opening_frames == 1:
            # Require a fresh present after the window has been exposed and staged.
            self.window.requestUpdate()
            return
        self.finish_calendar_opening(True)

    def opening_timed_out(self):
        if self.folded:
            self.stageCalendarOpening()
        else:
            self.finish_calendar_opening(False)

    def finish_calendar_opening(self, animate):
        self.opening_calendar = False
        self.opening_timeout.stop()
        opacity = self.opening_opacity
        self.opening_opacity = None
        if opacity is not None:
            self.window.frameSwapped.disconnect(self.calendar_frame_swapped)
            if animate:
                self.window.setOpacity(opacity)
        self.hidePreview()
        self.edge_window.hide()
        self.calendarOpeningReady.emit(animate)
        if opacity is not None and not animate:
            self.window.setOpacity(opacity)
        if not self.folded and self.window.isVisible():
            self.window.requestActivate()

    @Slot()
    def reveal(self):
        self.cancelInteraction()
        if self.opening_calendar:
            self.finish_calendar_opening(False)
        if self.window.visibility() == QWindow.Visibility.Minimized:
            self.window.showNormal()
        if self.folded:
            self.expand()
        elif not self.maximized:
            self.keep_title_reachable(self.window.screen())
        self.window.show()
        self.window.raise_()
        self.window.requestActivate()

    @Slot()
    def showPreview(self):
        self.update_fullscreen()
        if self.folded and not self.opening_calendar and not self.fullscreen_hidden and self.drag is None:
            self.preview_close.stop()
            if not self._previewing:
                self._previewing = True
                self.previewChanged.emit()

    @Slot()
    def keepPreview(self):
        self.preview_close.stop()

    @Slot()
    def deferHidePreview(self):
        if self._previewing and not self.preview_hover and not self.opening_calendar:
            self.preview_close.start()

    @Slot(bool)
    def hoverPreview(self, active):
        self.preview_hover = active
        if active:
            self.keepPreview()
        else:
            self.deferHidePreview()

    @Slot()
    def hidePreview(self):
        self.preview_close.stop()
        if self._previewing:
            self.preview_hover = False
            self._previewing = False
            self.previewChanged.emit()

    @Slot()
    def maximize(self):
        self.cancelInteraction()
        if self.folded:
            return
        if self.maximized:
            self.window.showNormal()
        else:
            self.remember_size()
            self.window.showMaximized()
        self.reset_clock()

    @Slot()
    def minimize(self):
        self.cancelInteraction()
        self.fullscreen_hidden = False
        self.window.showMinimized()

    @Property(bool, notify=changed)
    def pinned(self):
        return bool(self.settings.get("pinned", False))

    @Slot()
    def togglePinned(self):
        self.settings["pinned"] = not self.pinned
        self.window.setFlag(Qt.WindowType.WindowStaysOnTopHint, self.pinned)
        self.save()
        self.changed.emit()

    @Slot()
    def resetSize(self):
        self.settings.update(width=1120, height=740)
        if not self.folded:
            self.window.showNormal()
        self.geometry(False)
        self.save()
        self.reveal()

    @Slot(int)
    @Slot(int, float, float)
    def resize(self, edges, x=None, y=None):
        if not QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self.cancelInteraction()
            return
        if not self.folded and not self.maximized:
            self.cancelInteraction()
            self.resizing = True
            self.resize_edges = Qt.Edge(edges)
            self.resize_origin = QCursor.pos() if x is None else QPoint(round(x), round(y))
            self.resize_rect = self.window.geometry()
            self.reset_clock()
            if QGuiApplication.platformName() == "windows":
                self.system_resizing = True
                self.system_resizing = self.window.startSystemResize(self.resize_edges)

    @Slot()
    @Slot(float, float)
    def moveResize(self, x=None, y=None):
        if not QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self.cancelInteraction()
            return
        if not self.resizing or self.system_resizing:
            return
        pos = QCursor.pos() if x is None else QPoint(round(x), round(y))
        delta = pos - self.resize_origin
        rect = self.resize_rect
        left, top, right, bottom = rect.left(), rect.top(), rect.right()+1, rect.bottom()+1
        if self.resize_edges & Qt.Edge.LeftEdge:
            left = min(right-self.window.minimumWidth(), left+delta.x())
        if self.resize_edges & Qt.Edge.RightEdge:
            right = max(left+self.window.minimumWidth(), right+delta.x())
        if self.resize_edges & Qt.Edge.TopEdge:
            top = min(bottom-self.window.minimumHeight(), top+delta.y())
        if self.resize_edges & Qt.Edge.BottomEdge:
            bottom = max(top+self.window.minimumHeight(), bottom+delta.y())
        if (left, top, right-left, bottom-top) != self.window.geometry().getRect():
            self.window.setGeometry(left, top, right-left, bottom-top)

    @Slot()
    def cancelResizeGrab(self):
        # The native resize loop takes the mouse grab from the QML border.
        if not self.system_resizing:
            self.cancelInteraction()

    @Slot()
    def endResize(self):
        if self.resizing:
            self.resizing = False
            self.system_resizing = False
            self.remember_size()
            self.save()
            self.reset_clock()

    @Slot()
    @Slot(float, float)
    def dragStart(self, x=None, y=None):
        if not QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self.cancelInteraction()
            return
        if self.maximized or self.opening_calendar:
            return
        self.cancelInteraction()
        pos = QCursor.pos() if x is None else QPoint(round(x), round(y))
        self.drag = pos - self.active_window.position()
        self.drag_origin = pos
        self.dragged = False

    @Slot()
    @Slot(float, float)
    def dragMove(self, x=None, y=None):
        if not QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self.cancelInteraction()
            return
        if self.drag is not None:
            pos = QCursor.pos() if x is None else QPoint(round(x), round(y))
            if not self.dragged and (pos - self.drag_origin).manhattanLength() >= 4:
                self.dragged = True
                self.hidePreview()
            if self.dragged:
                self.active_window.setPosition(pos - self.drag)

    @Slot()
    def dragEnd(self):
        if self.drag is None:
            return
        self.drag = None
        if not self.dragged:
            if self.folded:
                self.expand(True)
            return
        pos = QCursor.pos()
        pointer_screen = QGuiApplication.screenAt(pos)
        self.screen = pointer_screen or self.active_window.screen()
        # Dock at the physical edge, including when the taskbar occupies that edge.
        bounds = self.screen.geometry()
        distances = dict(left=abs(pos.x()-bounds.left()), right=abs(bounds.right()-pos.x()),
                         top=abs(pos.y()-bounds.top()), bottom=abs(bounds.bottom()-pos.y()))
        edge = min(distances, key=distances.get)
        if self.folded or (pointer_screen is not None and distances[edge] <= self.DOCK_DISTANCE):
            self.remember_size()
            self.set_anchor(edge, pos)
            self.geometry(True)
        else:
            self.keep_title_reachable(self.screen)
            self.settings.pop('side', None)
            self.settings.pop('anchor', None)
        self.save()

    @Property(bool, notify=changed)
    def collapsed(self):
        return self.folded

    @Property(bool, notify=changed)
    def horizontal(self):
        return self.settings.get('side') in ('top', 'bottom')

    @Property(str, notify=changed)
    def previewEdge(self):
        return self.settings.get("side", "right")

    @Property(bool, constant=True)
    def transparencyEnabled(self):
        if sys.platform != "win32":
            return True
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return bool(winreg.QueryValueEx(key, "EnableTransparency")[0])
        except OSError:
            return True

    @Property(bool, constant=True)
    def motionEnabled(self):
        enabled = wintypes.BOOL(True)
        try:
            ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
        except AttributeError:
            pass
        return bool(enabled.value)

    @Property(bool, notify=changed)
    def maximized(self):
        return bool(self.window and self.window.visibility() == QWindow.Visibility.Maximized)

    @Property(bool, notify=previewChanged)
    def previewing(self):
        return self._previewing

    @Slot(int, result="QVariantMap")
    def previewGeometry(self, preferred_height):
        if not self.window:
            return dict(x=0, y=0, width=296, height=preferred_height)
        area = self.screen.availableGeometry()
        handle = self.edge_window.geometry()
        edge = self.previewEdge
        horizontal = edge in ("top", "bottom")
        width = min(296, max(1, area.width() - (0 if horizontal else handle.width())))
        height = min(preferred_height, max(1, area.height() - (handle.height() if horizontal else 0)))
        x = handle.center().x() - width // 2
        y = handle.center().y() - height // 2
        if edge == "left":
            x = handle.right() + 1
        elif edge == "right":
            x = handle.left() - width
        elif edge == "top":
            y = handle.bottom() + 1
        else:
            y = handle.top() - height
        x = max(area.left(), min(x, area.right()+1-width))
        y = max(area.top(), min(y, area.bottom()+1-height))
        return dict(x=x, y=y, width=width, height=height)

    @Property(bool, notify=weekChanged)
    def currentWeek(self):
        return self.offset == 0

    @Slot(int)
    def week(self, step):
        self.offset = self.offset + step if step else 0
        self.weekChanged.emit()

    @Slot(str)
    def jumpToDate(self, value):
        target = date.fromisoformat(value)
        monday = self.today - timedelta(days=self.today.weekday())
        offset = (target - monday).days // 7
        if self.offset != offset:
            self.offset = offset
            self.weekChanged.emit()

    def refresh_date(self, today):
        if today != self.today:
            self.today = today
            self.weekChanged.emit()

    @Property('QVariantList', notify=weekChanged)
    def days(self):
        today = self.today
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=self.offset)
        return [str(start + timedelta(days=i)) for i in range(7)]
