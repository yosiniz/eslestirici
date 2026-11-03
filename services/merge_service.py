"""Birden fazla Excel/CSV kaynağını satır bazında alt alta birleştirir."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from services.excel_service import ExcelService, ExcelServiceError


class MergeServiceError(RuntimeError):
    """Kullanıcıya gösterilebilecek birleştirme hatası."""


@dataclass(frozen=True)
class MergeInput:
    path: str
    sheet_name: str | int = 0


@dataclass(frozen=True)
class MergeSourceSummary:
    path: str
    file_name: str
    sheet_name: str
    row_count: int
    column_count: int


@dataclass
class MergeResult:
    dataframe: pd.DataFrame
    sources: tuple[MergeSourceSummary, ...]
    align_mode: str
    source_columns: tuple[str, str, str] | None

    @property
    def total_rows(self) -> int:
        return len(self.dataframe)

    @property
    def total_columns(self) -> int:
        return len(self.dataframe.columns)

    def summary_rows(self) -> list[tuple[str, object]]:
        mode = (
            "Kolon adlarına göre hizala"
            if self.align_mode == "union"
            else "Aynı kolon yapısını zorunlu tut"
        )
        rows: list[tuple[str, object]] = [
            ("Birleştirilen dosya sayısı", len(self.sources)),
            ("Toplam kayıt sayısı", self.total_rows),
            ("Sonuç sütun sayısı", self.total_columns),
            ("Birleştirme yöntemi", mode),
            ("Kaynak bilgisi kolonları", "Evet" if self.source_columns else "Hayır"),
        ]
        for index, source in enumerate(self.sources, 1):
            rows.append(
                (
                    f"Kaynak {index}",
                    f"{source.file_name} | {source.sheet_name} | {source.row_count:,} satır",
                )
            )
        return rows


class MergeService:
    """Dosyaları seçilen sheet'lerden okuyup deterministik sırayla birleştirir."""

    ALIGN_UNION = "union"
    ALIGN_STRICT = "strict"

    @classmethod
    def merge(
        cls,
        inputs: Sequence[MergeInput],
        align_mode: str = ALIGN_UNION,
        add_source_columns: bool = True,
        progress: Callable[[int, str], None] | None = None,
    ) -> MergeResult:
        if len(inputs) < 2:
            raise MergeServiceError("Birleştirme için en az iki dosya seçin.")
        if align_mode not in {cls.ALIGN_UNION, cls.ALIGN_STRICT}:
            raise MergeServiceError("Geçersiz kolon hizalama yöntemi.")

        frames: list[pd.DataFrame] = []
        summaries: list[MergeSourceSummary] = []
        ordered_columns: list[str] = []
        first_columns: list[str] | None = None
        total_inputs = len(inputs)

        for index, source in enumerate(inputs):
            file_path = Path(source.path)
            start = 5 + int(55 * index / total_inputs)
            if progress:
                progress(
                    start,
                    f"{index + 1}/{total_inputs} okunuyor: {file_path.name}",
                )
            try:
                dataframe = ExcelService.read_dataframe(
                    source.path,
                    sheet_name=source.sheet_name,
                )
                sheet_name = cls._resolved_sheet_name(source)
            except ExcelServiceError as exc:
                raise MergeServiceError(str(exc)) from exc

            columns = [str(column).strip() for column in dataframe.columns]
            if any(not column for column in columns):
                raise MergeServiceError(
                    f"{file_path.name} / {sheet_name}: boş sütun başlığı bulundu."
                )
            duplicates = cls._duplicates(columns)
            if duplicates:
                raise MergeServiceError(
                    f"{file_path.name} / {sheet_name}: tekrarlanan sütun başlığı: "
                    + ", ".join(duplicates)
                )
            dataframe = dataframe.copy(deep=False)
            dataframe.columns = columns

            if first_columns is None:
                first_columns = columns
            elif align_mode == cls.ALIGN_STRICT and columns != first_columns:
                raise MergeServiceError(
                    f"{file_path.name} / {sheet_name} sütun yapısı ilk dosyayla aynı değil. "
                    "Kolon adlarına göre hizalama seçeneğini kullanabilirsiniz."
                )

            for column in columns:
                if column not in ordered_columns:
                    ordered_columns.append(column)
            frames.append(dataframe)
            summaries.append(
                MergeSourceSummary(
                    path=str(file_path),
                    file_name=file_path.name,
                    sheet_name=sheet_name,
                    row_count=len(dataframe),
                    column_count=len(columns),
                )
            )

        source_columns: tuple[str, str, str] | None = None
        if add_source_columns:
            source_file = cls._unique_column("Kaynak Dosya", ordered_columns)
            source_sheet = cls._unique_column(
                "Kaynak Sheet", ordered_columns + [source_file]
            )
            source_row = cls._unique_column(
                "Kaynak Satır", ordered_columns + [source_file, source_sheet]
            )
            source_columns = (source_file, source_sheet, source_row)
            for dataframe, summary in zip(frames, summaries, strict=True):
                dataframe[source_file] = summary.file_name
                dataframe[source_sheet] = summary.sheet_name
                dataframe[source_row] = np.arange(2, len(dataframe) + 2, dtype=np.int64)

        if progress:
            progress(65, "Kolonlar hizalanıyor...")
        output_columns = ordered_columns + (list(source_columns) if source_columns else [])
        try:
            merged = pd.concat(frames, ignore_index=True, sort=False)
            merged = merged.reindex(columns=output_columns)
        except Exception as exc:
            raise MergeServiceError(f"Dosyalar birleştirilemedi: {exc}") from exc

        if progress:
            progress(100, f"Birleştirme tamamlandı: {len(merged):,} satır")
        return MergeResult(
            dataframe=merged,
            sources=tuple(summaries),
            align_mode=align_mode,
            source_columns=source_columns,
        )

    @staticmethod
    def _resolved_sheet_name(source: MergeInput) -> str:
        if Path(source.path).suffix.lower() == ".csv":
            return "CSV"
        if isinstance(source.sheet_name, str):
            return source.sheet_name
        sheets = ExcelService.list_sheets(source.path)
        try:
            return sheets[source.sheet_name]
        except IndexError as exc:
            raise MergeServiceError("Seçilen sheet bulunamadı.") from exc

    @staticmethod
    def _duplicates(columns: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for column in columns:
            if column in seen and column not in duplicates:
                duplicates.append(column)
            seen.add(column)
        return duplicates

    @staticmethod
    def _unique_column(base: str, existing: Sequence[str]) -> str:
        if base not in existing:
            return base
        suffix = 2
        while f"{base} ({suffix})" in existing:
            suffix += 1
        return f"{base} ({suffix})"
