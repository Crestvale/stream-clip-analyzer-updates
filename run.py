from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from stream_clip_analyzer import __version__
from stream_clip_analyzer.ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Stream Clip Analyzer")
    app.setApplicationVersion(__version__)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
