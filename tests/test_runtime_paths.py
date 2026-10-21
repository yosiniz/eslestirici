from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import runtime_paths


class RuntimePathTests(unittest.TestCase):
    def test_frozen_portable_uses_data_next_to_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app_dir = Path(directory)
            executable = app_dir / "OtoparkPlakaKontrol.exe"
            (app_dir / "portable.mode").write_text("portable", encoding="utf-8")
            with (
                patch.object(runtime_paths.sys, "frozen", True, create=True),
                patch.object(runtime_paths.sys, "executable", str(executable)),
            ):
                self.assertTrue(runtime_paths.is_portable_mode())
                self.assertEqual(
                    runtime_paths.user_data_directory(), app_dir.resolve() / "data"
                )

    def test_macos_installed_mode_uses_application_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_home = Path(directory)
            with (
                patch.object(runtime_paths.sys, "frozen", False, create=True),
                patch.object(runtime_paths.platform, "system", return_value="Darwin"),
                patch.object(Path, "home", return_value=fake_home),
                patch.object(runtime_paths, "is_portable_mode", return_value=False),
            ):
                expected = fake_home / "Library" / "Application Support" / "OtoparkPlakaKontrol"
                self.assertEqual(runtime_paths.user_data_directory(), expected)


if __name__ == "__main__":
    unittest.main()
