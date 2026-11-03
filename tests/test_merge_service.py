from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from services.export_service import ExportService
from services.merge_service import MergeInput, MergeService, MergeServiceError


class MergeServiceTests(unittest.TestCase):
    def test_union_aligns_columns_and_preserves_source_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "ocak.xlsx"
            second = root / "subat.xlsx"
            pd.DataFrame(
                {"Plaka": ["06ABC001", "34XYZ002"], "Tutar": [100, 200]}
            ).to_excel(first, sheet_name="Ocak", index=False)
            pd.DataFrame(
                {"Plaka": ["35AAA003"], "Açıklama": ["Yeni"]}
            ).to_excel(second, sheet_name="Şubat", index=False)

            result = MergeService.merge(
                [MergeInput(str(first), "Ocak"), MergeInput(str(second), "Şubat")]
            )

            self.assertEqual(result.total_rows, 3)
            self.assertEqual(
                list(result.dataframe.columns),
                [
                    "Plaka",
                    "Tutar",
                    "Açıklama",
                    "Kaynak Dosya",
                    "Kaynak Sheet",
                    "Kaynak Satır",
                ],
            )
            self.assertEqual(result.dataframe["Plaka"].tolist(), ["06ABC001", "34XYZ002", "35AAA003"])
            self.assertEqual(result.dataframe["Kaynak Satır"].tolist(), [2, 3, 2])
            self.assertTrue(pd.isna(result.dataframe.loc[2, "Tutar"]))
            self.assertTrue(pd.isna(result.dataframe.loc[0, "Açıklama"]))

    def test_selected_sheets_from_same_workbook_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "donemler.xlsx"
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame({"Kod": [1]}).to_excel(writer, sheet_name="Ocak", index=False)
                pd.DataFrame({"Kod": [2]}).to_excel(writer, sheet_name="Şubat", index=False)

            result = MergeService.merge(
                [MergeInput(str(path), "Ocak"), MergeInput(str(path), "Şubat")],
                add_source_columns=False,
            )
            self.assertEqual(result.dataframe["Kod"].tolist(), [1, 2])
            self.assertIsNone(result.source_columns)

    def test_strict_mode_rejects_different_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "bir.xlsx"
            second = root / "iki.xlsx"
            pd.DataFrame({"A": [1], "B": [2]}).to_excel(first, index=False)
            pd.DataFrame({"A": [3], "C": [4]}).to_excel(second, index=False)

            with self.assertRaisesRegex(MergeServiceError, "sütun yapısı"):
                MergeService.merge(
                    [MergeInput(str(first)), MergeInput(str(second))],
                    align_mode=MergeService.ALIGN_STRICT,
                )

    def test_source_column_names_do_not_overwrite_original_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths: list[str] = []
            for index in range(2):
                path = root / f"kaynak{index}.xlsx"
                pd.DataFrame({"Kaynak Dosya": [f"orijinal-{index}"], "A": [index]}).to_excel(
                    path, index=False
                )
                paths.append(str(path))
            result = MergeService.merge([MergeInput(path) for path in paths])
            self.assertIn("Kaynak Dosya", result.dataframe.columns)
            self.assertIn("Kaynak Dosya (2)", result.dataframe.columns)
            self.assertEqual(
                result.dataframe["Kaynak Dosya"].tolist(),
                ["orijinal-0", "orijinal-1"],
            )

    def test_export_creates_data_and_summary_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "bir.xlsx"
            second = root / "iki.xlsx"
            output = root / "birlesik.xlsx"
            pd.DataFrame({"A": [1]}).to_excel(first, index=False)
            pd.DataFrame({"A": [2]}).to_excel(second, index=False)
            result = MergeService.merge([MergeInput(str(first)), MergeInput(str(second))])

            ExportService.export_dataframe(
                result.dataframe,
                output,
                sheet_title="Birleştirilmiş Veriler",
                summary_rows=result.summary_rows(),
                summary_title="Birleştirme Özeti",
            )

            workbook = load_workbook(output, read_only=False, data_only=False)
            try:
                self.assertEqual(
                    workbook.sheetnames,
                    ["Birleştirme Özeti", "Birleştirilmiş Veriler"],
                )
                data_sheet = workbook["Birleştirilmiş Veriler"]
                self.assertEqual(data_sheet.max_row, 3)
                self.assertEqual(data_sheet.freeze_panes, "A2")
                self.assertIsNotNone(data_sheet.auto_filter.ref)
            finally:
                workbook.close()


if __name__ == "__main__":
    unittest.main()
