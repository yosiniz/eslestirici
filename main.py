"""Otopark Plaka Karşılaştırma Sistemi uygulama giriş noktası."""

from __future__ import annotations

import multiprocessing
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils.runtime_paths import bundled_resource


def main() -> int:
    """Qt uygulamasını başlatır."""
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    app.setApplicationName("Otopark Plaka Karşılaştırma Sistemi")
    app.setApplicationVersion("2.1.0")
    app.setOrganizationName("Otopark Plaka Kontrol")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    icon_path = bundled_resource("assets/app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
