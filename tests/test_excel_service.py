from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from services.excel_service import ExcelService


class ExcelSheetSelectionTests(unittest.TestCase):
    def test_lists_sheets_and_reads_selected_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cok_sayfali.xlsx"
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame({"Plaka": ["34ABC123"]}).to_excel(
                    writer, sheet_name="Plakalar", index=False
                )
                pd.DataFrame({"İşlem Tutarı": [150], "Tarih": ["18.02.2025"]}).to_excel(
                    writer, sheet_name="Hareketler", index=False
                )

            self.assertEqual(ExcelService.list_sheets(path), ["Plakalar", "Hareketler"])
            selected, columns = ExcelService.read_columns(path, "Hareketler")
            self.assertEqual(selected, "Hareketler")
            self.assertEqual(columns, ["İşlem Tutarı", "Tarih"])
            dataframe = ExcelService.read_dataframe(path, sheet_name="Hareketler")
            self.assertEqual(dataframe.iloc[0]["İşlem Tutarı"], 150)

    def test_csv_has_single_virtual_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "veri.csv"
            path.write_text("Plaka;Tutar\n34ABC123;100\n", encoding="utf-8-sig")
            self.assertEqual(ExcelService.list_sheets(path), ["CSV"])
            selected, columns = ExcelService.read_columns(path, "CSV")
            self.assertEqual(selected, "CSV")
            self.assertEqual(columns, ["Plaka", "Tutar"])


if __name__ == "__main__":
    unittest.main()
