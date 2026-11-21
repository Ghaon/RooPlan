import subprocess
import sys
import time
import unittest
import uuid

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy, QTest

from rooplan.instance import SingleInstance


class InstanceTests(unittest.TestCase):
    def test_process_crash_does_not_block_restart(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        name = "RooPlan-crash-test-" + uuid.uuid4().hex
        script = (
            "import sys;"
            "from PySide6.QtCore import QCoreApplication;"
            "from rooplan.instance import SingleInstance;"
            "app=QCoreApplication([]);"
            f"guard=SingleInstance({name!r});"
            "assert guard.acquire();print('ready',flush=True);sys.stdin.read()"
        )
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "ready")
        finally:
            child.kill()
            child.communicate(timeout=2)
        replacement = SingleInstance(name)
        self.addCleanup(replacement.close)
        self.assertTrue(replacement.acquire())

    def test_second_process_notifies_first_and_exit_releases_lock(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        name = "RooPlan-test-" + uuid.uuid4().hex
        primary = SingleInstance(name)
        self.addCleanup(primary.close)
        self.assertTrue(primary.acquire())
        activated = QSignalSpy(primary.activated)
        script = (
            "from PySide6.QtCore import QCoreApplication;"
            "from rooplan.instance import SingleInstance;"
            "app=QCoreApplication([]);"
            f"guard=SingleInstance({name!r});"
            "print('primary' if guard.acquire() else 'secondary')"
        )
        child = subprocess.Popen([sys.executable, "-c", script],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic()+10
        while child.poll() is None and time.monotonic() < deadline:
            QTest.qWait(20)
        if child.poll() is None:
            child.kill()
        output, error = child.communicate(timeout=2)
        self.assertEqual(child.returncode, 0, error)
        self.assertEqual(output.strip(), "secondary")
        QTest.qWait(100)
        self.assertEqual(activated.count(), 1)
        primary.close()
        replacement = SingleInstance(name)
        self.addCleanup(replacement.close)
        self.assertTrue(replacement.acquire())
