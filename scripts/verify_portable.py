"""CI paketinin temel dosya ve portable veri yolu doğrulaması."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.runtime_paths import application_directory, user_data_directory


if __name__ == "__main__":
    print(f"Uygulama dizini: {application_directory()}")
    print(f"Veri dizini: {user_data_directory()}")
    assert Path("portable.mode").exists(), "portable.mode proje kökünde bulunamadı"
