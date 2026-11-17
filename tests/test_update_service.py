from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.update_service import UpdateInfo, UpdateService, version_key


class UpdateServiceTests(unittest.TestCase):
    def test_version_comparison_is_numeric(self) -> None:
        self.assertGreater(version_key("2.10.0"), version_key("2.9.9"))
        self.assertEqual(version_key("2.4"), version_key("2.4.0"))
        with self.assertRaises(ValueError):
            version_key("v2.4-beta")

    @patch("services.update_service.platform.system", return_value="Windows")
    def test_selects_highest_newer_setup_from_app_and_updates_folder(self, _system) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            updates = root / "updates"
            updates.mkdir()
            (root / "Eslestirici-v2.3.1-Setup-Windows-x64.exe").touch()
            (root / "Eslestirici-v2.4.1-Setup-Windows-x64.exe").touch()
            expected = updates / "Eslestirici-v2.10.0-Setup-Windows-x64.exe"
            expected.touch()
            (updates / "baska-program-v99.0.exe").touch()

            result = UpdateService("2.4.0", root).find_available_update()

            self.assertIsNotNone(result)
            self.assertEqual(result.version, "2.10.0")
            self.assertEqual(result.installer_path, expected.resolve())

    @patch("services.update_service.platform.system", return_value="Windows")
    def test_equal_older_and_malformed_files_are_ignored(self, _system) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Eslestirici-v2.4.0-Setup-Windows-x64.exe").touch()
            (root / "Eslestirici-v2.3.9-Setup-Windows-x64.exe").touch()
            (root / "Eslestirici-v2.5-beta-Setup-Windows-x64.exe").touch()
            self.assertIsNone(UpdateService("2.4.0", root).find_available_update())

    @patch("services.update_service.subprocess.Popen")
    @patch("services.update_service.platform.system", return_value="Windows")
    def test_launch_uses_setup_silent_update_switches(self, _system, popen) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installer = root / "Eslestirici-v2.4.1-Setup-Windows-x64.exe"
            installer.touch()
            service = UpdateService("2.4.0", root)

            service.launch_update(UpdateInfo("2.4.1", installer.resolve()))

            command = popen.call_args.args[0]
            self.assertEqual(command[0], str(installer.resolve()))
            self.assertIn("/SILENT", command)
            self.assertIn("/CLOSEAPPLICATIONS", command)
            self.assertIn("/RESTARTAPPLICATIONS", command)

    @patch("services.update_service.platform.system", return_value="Windows")
    def test_rejects_installer_outside_application_folder(self, _system) -> None:
        with tempfile.TemporaryDirectory() as app_dir, tempfile.TemporaryDirectory() as other:
            installer = Path(other) / "Eslestirici-v9.0.0-Setup-Windows-x64.exe"
            installer.touch()
            with self.assertRaises(ValueError):
                UpdateService("2.4.0", app_dir).launch_update(
                    UpdateInfo("9.0.0", installer)
                )


if __name__ == "__main__":
    unittest.main()
