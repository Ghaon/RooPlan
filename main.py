import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from rooplan.desktop import Desktop
from rooplan.calendar import Calendar
from rooplan.store import Store
from rooplan.inbox import Inbox
from rooplan.instance import SingleInstance


def main():
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    if sys.platform == "win32":
        from ctypes import OleDLL, c_wchar_p

        # Give the taskbar a stable identity independent of the Python launcher.
        set_app_id = OleDLL("shell32").SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [c_wchar_p]
        set_app_id("RooPlan.Desktop")
    app = QApplication(sys.argv)
    app.setApplicationName("袋办 RooPlan")
    instance = SingleInstance()
    if not instance.acquire():
        return 0
    app.aboutToQuit.connect(instance.close)
    project_dir = Path(__file__).resolve().parent
    app_icon = QIcon(str(project_dir / "assets" / "rooplan-taskbar.png"))
    app.setWindowIcon(app_icon)
    folder = Path(os.getenv("ROOPLAN_DATA_DIR") or
                  (Path(os.getenv("LOCALAPPDATA") or Path.home()) / "RooPlan"))
    try:
        folder.mkdir(parents=True, exist_ok=True)
        store = Store(folder / "rooplan.sqlite3")
    except (PermissionError, OSError, __import__("sqlite3").OperationalError):
        if os.getenv("ROOPLAN_DATA_DIR"):
            raise
        folder = Path(sys.executable if getattr(sys,"frozen",False) else __file__).resolve().parent / "data"
        folder.mkdir(parents=True, exist_ok=True)
        store = Store(folder / "rooplan.sqlite3")
    desktop = Desktop(folder)
    calendar = Calendar(store, desktop)
    tray = QSystemTrayIcon(app_icon, app)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.setToolTip("袋办 RooPlan")
        tray.show()
    calendar.reminder.connect(lambda message: tray.showMessage("袋办 · 日程提醒", message) if tray.isVisible() else None)
    inbox = Inbox(store, folder, calendar)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("inbox", inbox)
    engine.rootContext().setContextProperty("cal", calendar)
    engine.rootContext().setContextProperty("desk", desktop)
    engine.load(QUrl.fromLocalFile(str(project_dir / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    window.setIcon(app_icon)
    desktop.attach(window)
    instance.activated.connect(desktop.reveal)
    tray_menu = QMenu()
    tray_menu.setStyleSheet("""
        QMenu {
            background: #f8f9f7;
            color: #202724;
            border: 1px solid #dde3df;
            padding: 6px;
        }
        QMenu::item { padding: 7px 20px 7px 9px; border-radius: 6px; }
        QMenu::item:selected { background: #eaf1ed; color: #194c42; }
        QMenu::separator { height: 1px; background: #dde3df; margin: 3px 5px; }
    """)
    tray_menu.addAction("打开周历", desktop.reveal)
    tray_menu.addAction("日程提醒", window.showReminders)
    tray_menu.addAction("恢复默认大小", desktop.resetSize)
    tray_menu.addSeparator()
    tray_menu.addAction("退出", app.quit)
    tray.setContextMenu(tray_menu)
    tray.messageClicked.connect(window.showReminders)
    tray.activated.connect(lambda reason: desktop.reveal()
                           if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                                         QSystemTrayIcon.ActivationReason.DoubleClick) else None)
    QTimer.singleShot(0, calendar.deliver)
    if "--smoke" in sys.argv:
        def smoke():
            assert len(desktop.days) == 7
            desktop.fold()
            edge_window = desktop.edge_window
            assert edge_window.isVisible() and not window.isVisible()
            assert (edge_window.height() if desktop.horizontal else edge_window.width()) == 24
            desktop.expand()
            assert window.isVisible() and not edge_window.isVisible()
            print("QML week / fold / expand OK", flush=True)
            app.quit()
        QTimer.singleShot(500, smoke)
    code = app.exec()
    del window
    del engine
    return code


if __name__ == "__main__":
    sys.exit(main())
