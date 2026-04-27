from __future__ import annotations

import sys
from typing import Sequence

from pyscout.resources import app_icon_path


def launch_gui(argv: Sequence[str] | None = None) -> int:
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication

        from .main_window import MainWindow
    except ImportError as exc:
        print(_format_pyside_error(exc), file=sys.stderr)
        return 2

    app = QApplication.instance()
    if app is None:
        app = QApplication(list(sys.argv if argv is None else argv))

    _set_windows_app_user_model_id()
    icon_path = app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    return app.exec()


def _format_pyside_error(exc: ImportError) -> str:
    return (
        "Error: PySide6 is required to launch the GUI. "
        "Install it with: python -m pip install PySide6"
    )


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        app_id = "PyScout.PyScout.App"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        return
