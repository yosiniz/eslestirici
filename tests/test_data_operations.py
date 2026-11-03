from __future__ import annotations

import unittest
from decimal import Decimal

import pandas as pd

from services.data_operation_service import (
    DataOperationService,
    FilterCondition,
    FilterOperator,
)


class DataOperationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = pd.DataFrame(
            {
                "Firma": [" ABC ", "Beta", "abc lojistik", None, "Delta"],
                "Ücret": ["₺1.250,50", "500", "2.000,00", None, "100"],
                "Tarih": ["01.01.2026", "15.02.2026", "10.03.2025", None, "20.03.2026"],
                "Kod": [1, 2, 2, 4, 5],
            }
        )

    def test_empty_and_not_empty_filters(self) -> None:
        empty = DataOperationService.filter(
            self.data, [FilterCondition("Firma", FilterOperator.EMPTY)]
        )
        not_empty = DataOperationService.filter(
            self.data, [FilterCondition("Firma", FilterOperator.NOT_EMPTY)]
        )
        self.assertEqual(len(empty.dataframe), 1)
        self.assertEqual(len(not_empty.dataframe), 4)

    def test_numeric_and_date_filters(self) -> None:
        numeric = DataOperationService.filter(
            self.data,
            [FilterCondition("Ücret", FilterOperator.GREATER, "1000")],
        )
        dates = DataOperationService.filter(
            self.data,
            [
                FilterCondition(
                    "Tarih", FilterOperator.BETWEEN, "01.01.2026", "28.02.2026"
                )
            ],
        )
        self.assertEqual(len(numeric.dataframe), 2)
        self.assertEqual(len(dates.dataframe), 2)

    def test_text_contains_and_multiple_logic(self) -> None:
        contains = DataOperationService.filter(
            self.data,
            [FilterCondition("Firma", FilterOperator.CONTAINS, "ABC")],
        )
        combined = DataOperationService.filter(
            self.data,
            [
                FilterCondition("Firma", FilterOperator.CONTAINS, "abc"),
                FilterCondition("Ücret", FilterOperator.GREATER, "1500"),
            ],
            logic="and",
        )
        alternative = DataOperationService.filter(
            self.data,
            [
                FilterCondition("Firma", FilterOperator.EQUALS, "Beta"),
                FilterCondition("Kod", FilterOperator.EQUALS, "5"),
            ],
            logic="or",
        )
        self.assertEqual(len(contains.dataframe), 2)
        self.assertEqual(len(combined.dataframe), 1)
        self.assertEqual(len(alternative.dataframe), 2)

    def test_aggregations(self) -> None:
        total = DataOperationService.aggregate(self.data, "Ücret", "sum")
        average = DataOperationService.aggregate(self.data, "Ücret", "mean")
        unique = DataOperationService.aggregate(self.data, "Kod", "nunique")
        self.assertEqual(total.scalar_value, Decimal("3850.50"))
        self.assertEqual(average.scalar_value, Decimal("962.625"))
        self.assertEqual(unique.scalar_value, 4)

    def test_sort_missing_and_duplicates(self) -> None:
        sorted_result = DataOperationService.sort(self.data, "Kod", ascending=False)
        dropped = DataOperationService.drop_missing(self.data, "Firma")
        filled = DataOperationService.fill_missing(self.data, "Firma", "Bilinmiyor")
        duplicates = DataOperationService.remove_duplicates(
            self.data, ["Kod"], keep="first"
        )
        self.assertEqual(sorted_result.dataframe.iloc[0]["Kod"], 5)
        self.assertEqual(len(dropped.dataframe), 4)
        self.assertEqual(filled.dataframe.loc[3, "Firma"], "Bilinmiyor")
        self.assertEqual(len(duplicates.dataframe), 4)

    def test_numeric_text_sort_uses_numeric_order(self) -> None:
        data = pd.DataFrame({"Ücret": ["100", "20", "₺1.000,00"]})
        result = DataOperationService.sort(data, "Ücret", ascending=True)
        self.assertEqual(result.dataframe["Ücret"].tolist(), ["20", "100", "₺1.000,00"])

    def test_text_transform(self) -> None:
        trimmed = DataOperationService.transform_text(self.data, "Firma", "trim")
        upper = DataOperationService.transform_text(self.data, "Firma", "upper")
        self.assertEqual(trimmed.dataframe.loc[0, "Firma"], "ABC")
        self.assertEqual(upper.dataframe.loc[1, "Firma"], "BETA")
        self.assertTrue(pd.isna(upper.dataframe.loc[3, "Firma"]))

    def test_calculated_columns(self) -> None:
        data = pd.DataFrame({"Net": [100, 200, None], "Adet": [2, 4, 1], "Ad": ["Ali", "Ayşe", "Can"], "Soyad": ["Yılmaz", "Kaya", "Demir"]})
        multiplied = DataOperationService.calculated_column(
            data, "Net", "multiply", "Toplam", right_column="Adet"
        )
        tax = DataOperationService.calculated_column(
            data, "Net", "percent", "KDV", constant="20"
        )
        full_name = DataOperationService.calculated_column(
            data, "Ad", "concat", "Tam Ad", right_column="Soyad"
        )
        self.assertEqual(multiplied.dataframe.loc[0, "Toplam"], Decimal("200"))
        self.assertEqual(tax.dataframe.loc[1, "KDV"], Decimal("40"))
        self.assertEqual(full_name.dataframe.loc[0, "Tam Ad"], "Ali Yılmaz")


if __name__ == "__main__":
    unittest.main()
