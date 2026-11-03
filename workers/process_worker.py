"""Uzun süren işlemleri Qt ana iş parçacığının dışında çalıştırır."""

from __future__ import annotations

import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal, Slot

from services.excel_service import ExcelService
from services.export_service import ExportService
from services.data_operation_service import (
    DataOperationService,
    FilterCondition,
    OperationResult,
)
from services.matching_service import (
    MatchResult,
    MatchingService,
    MultiMatchConfig,
    MultiMatchResult,
    OutputMode,
)
from services.merge_service import MergeInput, MergeResult, MergeService


class HeaderWorker(QObject):
    """Seçilen dosyanın kolon başlıklarını arka planda okur."""

    finished = Signal(str, str, str, object, object)
    failed = Signal(str, str, str)

    def __init__(self, role: str, path: str, sheet_name: str | None = None) -> None:
        super().__init__()
        self.role = role
        self.path = path
        self.sheet_name = sheet_name

    @Slot()
    def run(self) -> None:
        try:
            sheet_names = ExcelService.list_sheets(self.path)
            sheet_name, columns = ExcelService.read_columns(self.path, self.sheet_name)
            self.finished.emit(self.role, self.path, sheet_name, columns, sheet_names)
        except Exception as exc:
            self.failed.emit(self.role, self.path, str(exc))


class ProcessWorker(QObject):
    """İki Excel dosyasını okur ve eşleştirme sonucunu üretir."""

    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str, str)

    def __init__(
        self,
        reference_path: str,
        reference_column: str,
        parking_path: str,
        parking_column: str,
    ) -> None:
        super().__init__()
        self.reference_path = reference_path
        self.reference_column = reference_column
        self.parking_path = parking_path
        self.parking_column = parking_column

    def _report(self, value: int, message: str) -> None:
        self.progress.emit(value, message)

    @Slot()
    def run(self) -> None:
        try:
            reference_data = ExcelService.read_dataframe(
                self.reference_path,
                progress=self._report,
                progress_value=5,
                message="Plaka listesi okunuyor...",
            )
            self._report(20, f"Plaka listesi okundu: {len(reference_data):,} satır")
            parking_data = ExcelService.read_dataframe(
                self.parking_path,
                progress=self._report,
                progress_value=25,
                message="Otopark Exceli okunuyor...",
            )
            self._report(50, f"Otopark Exceli okundu: {len(parking_data):,} satır")
            result = MatchingService.compare(
                reference_data,
                self.reference_column,
                parking_data,
                self.parking_column,
                progress=self._report,
            )
            self._report(100, "Karşılaştırma tamamlandı.")
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class ExportWorker(QObject):
    """XLSX dışa aktarma işlemini arka planda yürütür."""

    progress = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str, str)

    def __init__(
        self,
        result: MatchResult,
        output_path: str,
        mode: OutputMode,
        split_sheets: bool,
    ) -> None:
        super().__init__()
        self.result = result
        self.output_path = output_path
        self.mode = mode
        self.split_sheets = split_sheets

    def _report(self, value: int, message: str) -> None:
        self.progress.emit(value, message)

    @Slot()
    def run(self) -> None:
        try:
            destination = ExportService.export(
                self.result,
                self.output_path,
                self.mode,
                self.split_sheets,
                progress=self._report,
            )
            self.finished.emit(str(destination))
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class MultiProcessWorker(QObject):
    """İki Excel/CSV dosyasını dinamik kurallarla karşılaştırır."""

    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str, str)

    def __init__(
        self,
        left_path: str,
        right_path: str,
        config: MultiMatchConfig,
        left_sheet: str | int = 0,
        right_sheet: str | int = 0,
    ) -> None:
        super().__init__()
        self.left_path = left_path
        self.right_path = right_path
        self.config = config
        self.left_sheet = left_sheet
        self.right_sheet = right_sheet

    def _report(self, value: int, message: str) -> None:
        self.progress.emit(value, message)

    @Slot()
    def run(self) -> None:
        try:
            left = ExcelService.read_dataframe(
                self.left_path,
                self._report,
                5,
                "Dosya 1 okunuyor...",
                sheet_name=self.left_sheet,
            )
            self._report(23, f"Dosya 1 okundu: {len(left):,} satır")
            right = ExcelService.read_dataframe(
                self.right_path,
                self._report,
                27,
                "Dosya 2 okunuyor...",
                sheet_name=self.right_sheet,
            )
            self._report(50, f"Dosya 2 okundu: {len(right):,} satır")
            result = MatchingService.compare_multi(
                left,
                right,
                self.config,
                left_name="Dosya 1",
                right_name="Dosya 2",
                progress=self._report,
            )
            self._report(100, "Karşılaştırma tamamlandı.")
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class MultiExportWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str, str)

    def __init__(self, result: MultiMatchResult, output_path: str) -> None:
        super().__init__()
        self.result = result
        self.output_path = output_path

    def _report(self, value: int, message: str) -> None:
        self.progress.emit(value, message)

    @Slot()
    def run(self) -> None:
        try:
            destination = ExportService.export_multi(
                self.result, self.output_path, progress=self._report
            )
            self.finished.emit(str(destination))
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class MergeMetadataWorker(QObject):
    """Birden fazla kaynağın sheet listesini arayüzü kilitlemeden okur."""

    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str, str)

    def __init__(self, paths: list[str]) -> None:
        super().__init__()
        self.paths = paths

    @Slot()
    def run(self) -> None:
        try:
            items: list[tuple[str, list[str]]] = []
            total = len(self.paths)
            for index, path in enumerate(self.paths, 1):
                self.progress.emit(
                    int(100 * (index - 1) / max(total, 1)),
                    f"Sheet bilgisi okunuyor: {Path(path).name}",
                )
                items.append((path, ExcelService.list_sheets(path)))
            self.progress.emit(100, f"{len(items)} dosya eklendi.")
            self.finished.emit(items)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class MergeWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str, str)

    def __init__(
        self,
        inputs: list[MergeInput],
        align_mode: str,
        add_source_columns: bool,
    ) -> None:
        super().__init__()
        self.inputs = inputs
        self.align_mode = align_mode
        self.add_source_columns = add_source_columns

    @Slot()
    def run(self) -> None:
        try:
            result = MergeService.merge(
                self.inputs,
                self.align_mode,
                self.add_source_columns,
                progress=lambda value, message: self.progress.emit(value, message),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class MergeExportWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str, str)

    def __init__(self, result: MergeResult, output_path: str) -> None:
        super().__init__()
        self.result = result
        self.output_path = output_path

    @Slot()
    def run(self) -> None:
        try:
            destination = ExportService.export_dataframe(
                self.result.dataframe,
                self.output_path,
                sheet_title="Birleştirilmiş Veriler",
                summary_rows=self.result.summary_rows(),
                summary_title="Birleştirme Özeti",
                progress=lambda value, message: self.progress.emit(value, message),
            )
            self.finished.emit(str(destination))
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class DataToolsLoadWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str, str, object, object, object)
    failed = Signal(str, str)

    def __init__(self, path: str, sheet_name: str | None = None) -> None:
        super().__init__()
        self.path = path
        self.sheet_name = sheet_name

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit(5, "Sheet listesi okunuyor...")
            sheets = ExcelService.list_sheets(self.path)
            selected = self.sheet_name or sheets[0]
            self.progress.emit(20, f"{Path(self.path).name} okunuyor...")
            dataframe = ExcelService.read_dataframe(
                self.path,
                sheet_name=selected,
            )
            columns = [str(column).strip() for column in dataframe.columns]
            if len(columns) != len(set(columns)):
                raise ValueError(
                    "Başlıklar temizlendikten sonra aynı isimde birden fazla sütun bulundu."
                )
            dataframe.columns = columns
            self.progress.emit(100, f"{len(dataframe):,} kayıt yüklendi.")
            self.finished.emit(self.path, str(selected), sheets, columns, dataframe)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class DataOperationWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str, str)

    def __init__(self, dataframe: pd.DataFrame, operation: str, options: dict) -> None:
        super().__init__()
        self.dataframe = dataframe
        self.operation = operation
        self.options = options

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit(10, "Veri işleniyor...")
            service = DataOperationService
            if self.operation == "filter":
                result = service.filter(
                    self.dataframe,
                    self.options["conditions"],
                    self.options["logic"],
                )
            elif self.operation == "aggregate":
                result = service.aggregate(
                    self.dataframe,
                    self.options["column"],
                    self.options["function"],
                )
            elif self.operation == "sort":
                result = service.sort(
                    self.dataframe,
                    self.options["column"],
                    self.options["ascending"],
                )
            elif self.operation == "drop_missing":
                result = service.drop_missing(
                    self.dataframe, self.options["column"]
                )
            elif self.operation == "fill_missing":
                result = service.fill_missing(
                    self.dataframe,
                    self.options["column"],
                    self.options["value"],
                )
            elif self.operation == "remove_duplicates":
                result = service.remove_duplicates(
                    self.dataframe,
                    self.options.get("columns"),
                    self.options.get("keep", "first"),
                )
            elif self.operation == "transform_text":
                result = service.transform_text(
                    self.dataframe,
                    self.options["column"],
                    self.options["text_operation"],
                )
            elif self.operation == "calculated_column":
                result = service.calculated_column(self.dataframe, **self.options)
            else:
                raise ValueError("Bilinmeyen veri işlemi.")
            self.progress.emit(100, result.message)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class DataToolsExportWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str, str)

    def __init__(self, dataframe: pd.DataFrame, output_path: str) -> None:
        super().__init__()
        self.dataframe = dataframe
        self.output_path = output_path

    @Slot()
    def run(self) -> None:
        try:
            destination = ExportService.export_dataframe(
                self.dataframe,
                self.output_path,
                sheet_title="İşlenmiş Veriler",
                summary_rows=[
                    ("Kayıt sayısı", len(self.dataframe)),
                    ("Sütun sayısı", len(self.dataframe.columns)),
                ],
                summary_title="İşlem Özeti",
                progress=lambda value, message: self.progress.emit(value, message),
            )
            self.finished.emit(str(destination))
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())


class TableFilterWorker(QObject):
    """Büyük tablolarda arama işlemini ana iş parçacığı dışında yapar."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        dataframe: pd.DataFrame,
        base_indices: np.ndarray,
        query: str,
        column_name: str | None,
    ) -> None:
        super().__init__()
        self.dataframe = dataframe
        self.base_indices = base_indices
        self.query = query.strip()
        self.column_name = column_name

    @Slot()
    def run(self) -> None:
        try:
            if not self.query:
                self.finished.emit(self.base_indices.copy())
                return

            subset = self.dataframe.iloc[self.base_indices]
            if self.column_name is not None:
                series = subset[self.column_name].astype("string")
                mask = series.str.contains(
                    self.query, case=False, regex=False, na=False
                ).to_numpy(dtype=bool)
            else:
                mask = np.zeros(len(subset), dtype=bool)
                for column in subset.columns:
                    series = subset[column].astype("string")
                    mask |= series.str.contains(
                        self.query, case=False, regex=False, na=False
                    ).to_numpy(dtype=bool)
                    if mask.all():
                        break
            self.finished.emit(self.base_indices[mask])
        except Exception as exc:
            self.failed.emit(str(exc))
