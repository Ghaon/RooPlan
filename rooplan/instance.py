import getpass
import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    """Own one local pipe per user and notify the running app on another launch."""
    activated = Signal()

    def __init__(self, name=None):
        super().__init__()
        identity = str(Path.home()) + getpass.getuser()
        self.name = name or "RooPlan-" + hashlib.sha256(identity.encode()).hexdigest()[:24]
        self.lock = QLockFile(str(Path(tempfile.gettempdir()) / (self.name+".lock")))
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self.accept)

    def acquire(self):
        if self.lock.tryLock(0):
            if self.server.listen(self.name):
                return True
            self.lock.unlock()
            raise RuntimeError("无法建立 RooPlan 本地连接，请检查临时目录权限。")
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(2000):
            raise RuntimeError("无法连接已有 RooPlan 实例，请稍后重试。")
        socket.write(b"activate\n")
        socket.flush()
        if socket.bytesToWrite() and not socket.waitForBytesWritten(1000):
            raise RuntimeError("无法唤起已有 RooPlan 实例，请稍后重试。")
        socket.disconnectFromServer()
        return False

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.setProperty("message", b"")
            socket.readyRead.connect(lambda connection=socket: self.receive(connection))
            socket.disconnected.connect(socket.deleteLater)
            self.receive(socket)

    def receive(self, socket):
        message = bytes(socket.property("message")) + bytes(socket.readAll())
        if b"\n" in message:
            if message.split(b"\n", 1)[0] == b"activate":
                self.activated.emit()
            socket.disconnectFromServer()
        else:
            socket.setProperty("message", message)

    def close(self):
        self.server.close()
        self.lock.unlock()
