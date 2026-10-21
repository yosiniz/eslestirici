from __future__ import annotations

import unittest

import pandas as pd

from services.matching_service import MatchingService, OutputMode
from utils.plate_utils import guess_plate_column, normalize_plate_series


class PlateUtilityTests(unittest.TestCase):
    def test_normalization_ignores_case_and_separators(self) -> None:
        source = pd.Series(["34 ABC 123", "34-abc-123", " 34.ABC/123 ", None])
        result = normalize_plate_series(source).tolist()
        self.assertEqual(result, ["34ABC123", "34ABC123", "34ABC123", ""])

    def test_column_guess(self) -> None:
        self.assertEqual(guess_plate_column(["Tarih", "Araç Plakası", "Ücret"]), 1)
        self.assertEqual(guess_plate_column(["Date", "Plate", "Price"]), 1)
        self.assertEqual(guess_plate_column(["A", "B"]), -1)


class MatchingServiceTests(unittest.TestCase):
    def test_compare_and_summary(self) -> None:
        reference = pd.DataFrame({"Plaka": ["34 ABC 123", "06XYZ06", ""]})
        parking = pd.DataFrame(
            {
                "PLAKA": ["34-abc-123", "06 XYZ 06", "35 TEST 35", None],
                "Ücret": [100, 200, 300, 0],
            }
        )
        result = MatchingService.compare(reference, "Plaka", parking, "PLAKA")
        self.assertEqual(result.match_mask.tolist(), [True, True, False, False])
        self.assertEqual(result.summary.total_records, 4)
        self.assertEqual(result.summary.reference_plate_count, 2)
        self.assertEqual(result.summary.matched_records, 2)
        self.assertEqual(result.summary.unmatched_records, 2)
        self.assertEqual(result.summary.matched_unique_plates, 2)
        self.assertEqual(result.summary.unmatched_unique_plates, 1)
        self.assertEqual(result.indices_for_mode(OutputMode.MATCHED).tolist(), [0, 1])
        self.assertEqual(result.indices_for_mode(OutputMode.UNMATCHED).tolist(), [2, 3])

    def test_empty_reference_plates_raise_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "karşılaştırılabilir"):
            MatchingService.compare(
                pd.DataFrame({"Plaka": [None, " "]}),
                "Plaka",
                pd.DataFrame({"Plaka": ["34ABC123"]}),
                "Plaka",
            )


if __name__ == "__main__":
    unittest.main()
