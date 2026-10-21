"""Büyük DataFrame'leri sayfalayarak gösteren Qt tablo modeli."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor


class PagedDataFrameModel(QAbstractTableModel):
    """Her seferinde yalnızca etkin sayfadaki satırları Qt'ye sunar."""

    page_changed = Signal(int, int, int)

    def __init__(self, page_size: int = 500) -> None:
        super().__init__()
        self._dataframe = pd.DataFrame()
        self._match_mask = np.array([], dtype=bool)
        self._base_indices = np.array([], dtype=np.int64)
        self._active_indices = np.array([], dtype=np.int64)
        self._include_status = False
        self._status_header = "Eşleşme Durumu"
        self._page_size = page_size
        self._current_page = 0

    def set_source(
        self,
        dataframe: pd.DataFrame,
        indices: np.ndarray,
        match_mask: np.ndarray,
        include_status: bool,
    ) -> None:
        self.beginResetModel()
        self._dataframe = dataframe
        self._match_mask = match_mask
        self._base_indices = indices.astype(np.int64, copy=True)
        self._active_indices = self._base_indices.copy()
        self._include_status = include_status
        self._status_header = self._make_status_header()
        self._current_page = 0
        self.endResetModel()
        self._emit_page_changed()

    def set_dataframe(self, dataframe: pd.DataFrame) -> None:
        """Durum kolonu zaten DataFrame içindeyken doğrudan sonuç gösterir."""
        self.set_source(
            dataframe,
            np.arange(len(dataframe), dtype=np.int64),
            np.zeros(len(dataframe), dtype=bool),
            False,
        )

    def clear(self) -> None:
        self.set_source(
            pd.DataFrame(),
            np.array([], dtype=np.int64),
            np.array([], dtype=bool),
            False,
        )

    def set_filtered_indices(self, indices: np.ndarray) -> None:
        self.beginResetModel()
        self._active_indices = indices.astype(np.int64, copy=False)
        self._current_page = 0
        self.endResetModel()
        self._emit_page_changed()

    def reset_filter(self) -> None:
        self.set_filtered_indices(self._base_indices.copy())

    @property
    def dataframe(self) -> pd.DataFrame:
        return self._dataframe

    @property
    def base_indices(self) -> np.ndarray:
        return self._base_indices

    @property
    def filtered_count(self) -> int:
        return len(self._active_indices)

    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def page_count(self) -> int:
        if not len(self._active_indices):
            return 1
        return (len(self._active_indices) + self._page_size - 1) // self._page_size

    @property
    def current_page(self) -> int:
        return self._current_page

    def set_page_size(self, value: int) -> None:
        value = max(1, int(value))
        if value == self._page_size:
            return
        first_visible_offset = self._current_page * self._page_size
        self.beginResetModel()
        self._page_size = value
        self._current_page = min(
            first_visible_offset // self._page_size, self.page_count - 1
        )
        self.endResetModel()
        self._emit_page_changed()

    def next_page(self) -> None:
        self.set_page(self._current_page + 1)

    def previous_page(self) -> None:
        self.set_page(self._current_page - 1)

    def set_page(self, page: int) -> None:
        page = max(0, min(int(page), self.page_count - 1))
        if page == self._current_page:
            return
        self.beginResetModel()
        self._current_page = page
        self.endResetModel()
        self._emit_page_changed()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        start = self._current_page * self._page_size
        return max(0, min(self._page_size, len(self._active_indices) - start))

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._dataframe.columns) + int(self._include_status)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        source_position = self._source_position(index.row())
        if source_position is None:
            return None

        is_status_column = (
            self._include_status and index.column() == len(self._dataframe.columns)
        )
        if is_status_column:
            matched = bool(self._match_mask[source_position])
            if role == Qt.ItemDataRole.DisplayRole:
                return "Eşleşti" if matched else "Eşleşmedi"
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor("#176B4D") if matched else QColor("#5D6470")
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignCenter)
            return None

        value = self._dataframe.iat[source_position, index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_value(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and self._is_number(value):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._format_value(value)
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if self._include_status and section == len(self._dataframe.columns):
                return self._status_header
            if 0 <= section < len(self._dataframe.columns):
                return str(self._dataframe.columns[section])
        else:
            source_position = self._source_position(section)
            if source_position is not None:
                return str(source_position + 2)
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if not len(self._active_indices):
            return
        ascending = order == Qt.SortOrder.AscendingOrder
        self.layoutAboutToBeChanged.emit()
        try:
            if self._include_status and column == len(self._dataframe.columns):
                keys = self._match_mask[self._active_indices]
                sorter = np.argsort(keys, kind="stable")
                if not ascending:
                    sorter = sorter[::-1]
                self._active_indices = self._active_indices[sorter]
            elif 0 <= column < len(self._dataframe.columns):
                positions = pd.Series(
                    self._active_indices,
                    index=self._active_indices,
                    dtype="int64",
                )
                values = self._dataframe.iloc[self._active_indices, column]
                values.index = self._active_indices
                try:
                    ordered = values.sort_values(
                        ascending=ascending, na_position="last", kind="mergesort"
                    ).index.to_numpy(dtype=np.int64)
                except (TypeError, ValueError):
                    ordered = values.astype("string").sort_values(
                        ascending=ascending,
                        na_position="last",
                        kind="mergesort",
                        key=lambda series: series.str.casefold(),
                    ).index.to_numpy(dtype=np.int64)
                self._active_indices = positions.loc[ordered].to_numpy(dtype=np.int64)
            self._current_page = 0
        finally:
            self.layoutChanged.emit()
            self._emit_page_changed()

    def _source_position(self, page_row: int) -> int | None:
        offset = self._current_page * self._page_size + page_row
        if 0 <= offset < len(self._active_indices):
            return int(self._active_indices[offset])
        return None

    def _emit_page_changed(self) -> None:
        self.page_changed.emit(
            self._current_page + 1,
            self.page_count,
            len(self._active_indices),
        )

    def _make_status_header(self) -> str:
        base = "Eşleşme Durumu"
        headers = {str(column) for column in self._dataframe.columns}
        if base not in headers:
            return base
        suffix = 2
        while f"{base} ({suffix})" in headers:
            suffix += 1
        return f"{base} ({suffix})"

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(
            value, bool
        )

    @staticmethod
    def _format_value(value: Any) -> str:
        if value is None or value is pd.NA or value is pd.NaT:
            return ""
        is_missing = False
        try:
            if not isinstance(value, (str, bytes)):
                is_missing = bool(pd.isna(value))
        except (TypeError, ValueError):
            is_missing = False
        if is_missing:
            return ""
        if isinstance(value, (pd.Timestamp, datetime)):
            if value.hour == 0 and value.minute == 0 and value.second == 0:
                return value.strftime("%d.%m.%Y")
            return value.strftime("%d.%m.%Y %H:%M:%S")
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        return str(value)
