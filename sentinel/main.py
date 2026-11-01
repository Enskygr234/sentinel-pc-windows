"""Sentinel PC giriş noktası."""
from __future__ import annotations

import os
import sys


def resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    self_test = None
    for a in argv[1:]:
        if a == "--self-test":
            self_test = ""
        elif a.startswith("--self-test="):
            self_test = a.split("=", 1)[1]
        elif a in ("--version", "-v"):
            from . import __version__
            print(__version__)
            return 0

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SentinelPC.Monitor.1")
        except Exception:  # noqa: BLE001
            pass

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from . import APP_NAME
    from .ui.theme import QSS

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(QSS)
    icon = resource_path("assets", "icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))

    if self_test is not None:
        from .selftest import run_self_test
        return run_self_test(app, self_test)

    from .core.history import HistoryStore
    from .ui.main_window import MainWindow

    try:
        store = HistoryStore()
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, APP_NAME, f"Geçmiş veritabanı açılamadı:\n{e}")
        return 1
    win = MainWindow(store)
    win.show()
    code = app.exec()
    store.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
