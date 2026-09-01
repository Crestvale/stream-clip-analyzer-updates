import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QThread, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from stream_clip_analyzer import __version__
    from stream_clip_analyzer.ui import MainWindow
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class UiThreadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_worker_success_callback_runs_on_main_thread(self):
        window = MainWindow()
        dialog_threads = []
        original = QMessageBox.information

        def fake_information(*_args, **_kwargs):
            dialog_threads.append(QThread.currentThread())
            return QMessageBox.StandardButton.Ok

        QMessageBox.information = staticmethod(fake_information)
        try:
            manifest = {"version": __version__, "download_url": "https://example.invalid/update.zip"}
            window._run_worker(
                lambda _status: manifest,
                lambda result: window.update_manifest_ready(result, True),
            )
            loop = QEventLoop()
            poll = QTimer()
            poll.setInterval(10)
            poll.timeout.connect(lambda: loop.quit() if window.thread is None else None)
            poll.start()
            QTimer.singleShot(3000, loop.quit)
            loop.exec()
            self.assertIsNone(window.thread)
            self.assertEqual(dialog_threads, [self.app.thread()])
        finally:
            QMessageBox.information = original
            window.close()


if __name__ == "__main__":
    unittest.main()
