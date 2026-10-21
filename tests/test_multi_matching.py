from __future__ import annotations

import unittest
from decimal import Decimal

import pandas as pd

from services.matching_service import (
    DuplicateMode,
    LogicMode,
    MatchRule,
    MatchingService,
    MultiMatchConfig,
)
from utils.value_normalizers import NormalizationOptions, ValueKind


def rule(left: str, right: str, kind: ValueKind, primary: bool = False) -> MatchRule:
    return MatchRule(left, right, normalization=NormalizationOptions(kind=kind), primary=primary)


class MultiMatchingTests(unittest.TestCase):
    def compare(self, left: pd.DataFrame, right: pd.DataFrame, rules: list[MatchRule]):
        return MatchingService.compare_multi(left, right, MultiMatchConfig(tuple(rules)))

    def test_plate_and_amount_equal_matches(self) -> None:
        result = self.compare(
            pd.DataFrame({"Plaka": ["06 DJU 250"], "Tutar": ["₺130,00"]}),
            pd.DataFrame({"Araç Plakası": ["06-dju-250"], "İşlem Tutarı": ["130.00"]}),
            [rule("Plaka", "Araç Plakası", ValueKind.PLATE), rule("Tutar", "İşlem Tutarı", ValueKind.DECIMAL)],
        )
        self.assertEqual(result.summary.matched_pairs, 1)

    def test_same_plate_different_amount_is_unmatched_and_partial(self) -> None:
        result = self.compare(
            pd.DataFrame({"Plaka": ["34ABC123"], "Tutar": [100]}),
            pd.DataFrame({"Plaka": ["34ABC123"], "Tutar": [200]}),
            [rule("Plaka", "Plaka", ValueKind.PLATE, True), rule("Tutar", "Tutar", ValueKind.DECIMAL)],
        )
        self.assertEqual(result.summary.matched_pairs, 0)
        self.assertEqual(result.summary.partial_candidates, 1)

    def test_different_plate_same_amount_is_unmatched(self) -> None:
        result = self.compare(
            pd.DataFrame({"Plaka": ["34ABC123"], "Tutar": [100]}),
            pd.DataFrame({"Plaka": ["06ABC123"], "Tutar": [100]}),
            [rule("Plaka", "Plaka", ValueKind.PLATE), rule("Tutar", "Tutar", ValueKind.DECIMAL)],
        )
        self.assertEqual(result.summary.matched_pairs, 0)

    def test_date_rule_blocks_different_date(self) -> None:
        result = self.compare(
            pd.DataFrame({"Plaka": ["34ABC123"], "Tutar": [100], "Tarih": ["18.02.2025"]}),
            pd.DataFrame({"Plaka": ["34ABC123"], "Tutar": [100], "Tarih": ["19/02/2025"]}),
            [rule("Plaka", "Plaka", ValueKind.PLATE), rule("Tutar", "Tutar", ValueKind.DECIMAL), rule("Tarih", "Tarih", ValueKind.DATE)],
        )
        self.assertEqual(result.summary.matched_pairs, 0)

    def test_duplicates_are_consumed_one_to_one(self) -> None:
        result = self.compare(
            pd.DataFrame({"Plaka": ["34ABC123", "34ABC123", "34XYZ789"], "Tutar": [150, 150, 200]}),
            pd.DataFrame({"Plaka": ["34ABC123", "34XYZ789"], "Tutar": [150, 200]}),
            [rule("Plaka", "Plaka", ValueKind.PLATE), rule("Tutar", "Tutar", ValueKind.DECIMAL)],
        )
        self.assertEqual(result.summary.matched_pairs, 2)
        self.assertEqual(result.summary.left_unmatched, 1)
        self.assertEqual(result.pair_indices, [(0, 0), (2, 1)])

    def test_three_vs_two_duplicates(self) -> None:
        left = pd.DataFrame({"Kod": ["A", "A", "A"]})
        right = pd.DataFrame({"Kod": ["A", "A"]})
        result = self.compare(left, right, [rule("Kod", "Kod", ValueKind.TEXT)])
        self.assertEqual((result.summary.matched_pairs, result.summary.left_unmatched), (2, 1))

    def test_turkish_money_formats(self) -> None:
        left = pd.DataFrame({"Tutar": ["165,00", "₺1.250,50"]})
        right = pd.DataFrame({"İşlem Tutarı": ["₺165.00", "1250.50"]})
        result = self.compare(left, right, [rule("Tutar", "İşlem Tutarı", ValueKind.DECIMAL)])
        self.assertEqual(result.summary.matched_pairs, 2)

    def test_different_column_names(self) -> None:
        result = self.compare(
            pd.DataFrame({"Araç": ["34 ABC 123"]}),
            pd.DataFrame({"Plaka No": ["34ABC123"]}),
            [rule("Araç", "Plaka No", ValueKind.PLATE)],
        )
        self.assertEqual(result.summary.matched_pairs, 1)

    def test_empty_values_do_not_match_by_default(self) -> None:
        result = self.compare(
            pd.DataFrame({"Kod": [None]}), pd.DataFrame({"Kod": [None]}),
            [rule("Kod", "Kod", ValueKind.TEXT)],
        )
        self.assertEqual(result.summary.matched_pairs, 0)

    def test_single_rule_preserves_simple_matching(self) -> None:
        result = self.compare(
            pd.DataFrame({"Plaka": ["34 ABC 123"]}),
            pd.DataFrame({"Plaka": ["34-abc-123"]}),
            [rule("Plaka", "Plaka", ValueKind.PLATE)],
        )
        self.assertEqual(result.summary.matched_pairs, 1)

    def test_or_mode(self) -> None:
        left = pd.DataFrame({"A": ["X"], "B": [1]})
        right = pd.DataFrame({"A": ["Y"], "B": [1]})
        config = MultiMatchConfig(
            (rule("A", "A", ValueKind.TEXT), rule("B", "B", ValueKind.DECIMAL)),
            LogicMode.OR,
        )
        result = MatchingService.compare_multi(left, right, config)
        self.assertEqual(result.summary.matched_pairs, 1)

    def test_all_matches_is_distinct_from_one_to_one(self) -> None:
        left = pd.DataFrame({"Kod": ["A", "A"]})
        right = pd.DataFrame({"Kod": ["A", "A"]})
        config = MultiMatchConfig(
            (rule("Kod", "Kod", ValueKind.TEXT),),
            duplicate_mode=DuplicateMode.ALL_MATCHES,
        )
        result = MatchingService.compare_multi(left, right, config)
        self.assertEqual(result.summary.matched_pairs, 4)


if __name__ == "__main__":
    unittest.main()
