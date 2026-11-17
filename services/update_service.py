"""Uygulama klasöründeki yerel Windows kurulum paketlerini denetler."""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from utils.runtime_paths import application_directory


_INSTALLER_PATTERN = re.compile(
    r"^Eslestirici-v(?P<version>\d+(?:\.\d+){1,3})-Setup-Windows-x64\.exe$",
    re.IGNORECASE,
)


def version_key(version: str) -> tuple[int, int, int, int]:
    """Noktalı sayısal sürümü karşılaştırılabilir dört parçaya dönüştürür."""

    text = str(version).strip()
    if not re.fullmatch(r"\d+(?:\.\d+){1,3}", text):
        raise ValueError(f"Geçersiz sürüm: {version}")
    parts = [int(part) for part in text.split(".")]
    parts.extend([0] * (4 - len(parts)))
    return tuple(parts)  # type: ignore[return-value]


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    installer_path: Path


class UpdateService:
    """İnternete çıkmadan, yalnızca yerel Setup EXE dosyalarını kullanır."""

    def __init__(
        self,
        current_version: str,
        app_directory: str | Path | None = None,
    ) -> None:
        self.current_version = current_version
        self.app_directory = Path(app_directory or application_directory()).resolve()

    def find_available_update(self) -> UpdateInfo | None:
        if platform.system() != "Windows":
            return None

        current = version_key(self.current_version)
        candidates: list[UpdateInfo] = []
        for directory in (self.app_directory, self.app_directory / "updates"):
            if not directory.is_dir():
                continue
            for path in directory.iterdir():
                if not path.is_file():
                    continue
                match = _INSTALLER_PATTERN.fullmatch(path.name)
                if not match:
                    continue
                version = match.group("version")
                if version_key(version) > current:
                    candidates.append(UpdateInfo(version, path.resolve()))

        if not candidates:
            return None
        return max(candidates, key=lambda item: version_key(item.version))

    def launch_update(self, update: UpdateInfo) -> None:
        """Doğrulanmış yerel kurulumu başlatır; çağıran uygulamayı kapatmalıdır."""

        installer = update.installer_path.resolve()
        allowed_parents = {
            self.app_directory,
            (self.app_directory / "updates").resolve(),
        }
        if installer.parent not in allowed_parents:
            raise ValueError("Güncelleme paketi uygulama klasörünün dışında.")
        match = _INSTALLER_PATTERN.fullmatch(installer.name)
        if not installer.is_file() or not match:
            raise FileNotFoundError("Güncelleme paketi bulunamadı veya adı geçersiz.")
        if version_key(match.group("version")) <= version_key(self.current_version):
            raise ValueError("Seçilen paket mevcut sürümden yeni değil.")
        if platform.system() != "Windows":
            raise OSError("Yerel Setup EXE güncellemesi yalnızca Windows'ta kullanılabilir.")

        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        subprocess.Popen(
            [
                str(installer),
                "/SILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
                "/RESTARTAPPLICATIONS",
            ],
            cwd=str(installer.parent),
            close_fds=True,
            creationflags=creation_flags,
        )
