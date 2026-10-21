from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from services.matching_service import DuplicateMode, LogicMode, MatchRule, MultiMatchConfig
from services.template_service import TemplateService
from utils.value_normalizers import NormalizationOptions, ValueKind


class TemplateTests(unittest.TestCase):
    def test_roundtrip_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = TemplateService(Path(directory) / "templates.json")
            config = MultiMatchConfig(
                (
                    MatchRule(
                        "Tutar", "İşlem Tutarı",
                        normalization=NormalizationOptions(
                            kind=ValueKind.DECIMAL, tolerance=Decimal("0.01")
                        ),
                    ),
                ),
                LogicMode.AND,
                DuplicateMode.ONE_TO_ONE,
            )
            service.save("Plaka ve Tutar", config)
            loaded = service.get("Plaka ve Tutar")
            self.assertEqual(loaded.rules[0].right_column, "İşlem Tutarı")
            self.assertEqual(loaded.rules[0].normalization.tolerance, Decimal("0.01"))
            service.delete("Plaka ve Tutar")
            self.assertEqual(service.list_names(), [])


if __name__ == "__main__":
    unittest.main()
