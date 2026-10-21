"""Kaynak, portable ve kurulu çalışma modları için veri yolları."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


APP_DIRECTORY_NAME = "OtoparkPlakaKontrol"


def bundled_resource(relative_path: str | Path) -> Path:
    """Kaynak dosyasını geliştirme ve PyInstaller paketinde çözümler."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    base = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[1]
    return base / Path(relative_path)


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def is_portable_mode() -> bool:
    app_dir = application_directory()
    markers = [app_dir / "portable.mode"]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        markers.append(Path(bundle_dir) / "portable.mode")
    return any(marker.exists() for marker in markers)


def user_data_directory() -> Path:
    """Portable pakette uygulama yanı; kurulu pakette işletim sistemi alanı."""
    if is_portable_mode():
        return application_directory() / "data"

    system = platform.system()
    if system == "Windows":
        root = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / APP_DIRECTORY_NAME
