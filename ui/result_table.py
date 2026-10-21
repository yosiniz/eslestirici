"""Aranabilir, sıralanabilir ve sayfalı sonuç tablosu."""

from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from models.paged_dataframe_model import PagedDataFrameModel
from workers.process_worker import TableFilterWorker


class ResultTable(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = PagedDataFrameModel(500)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Sonuçlarda ara...")
        self.column = QComboBox()
        self.column.addItem("Tüm sütunlar", None)
        self.search_button = QPushButton("Ara")
        self.clear_button = QPushButton("Temizle")
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.previous = QPushButton("‹ Önceki")
        self.next = QPushButton("Sonraki ›")
        self.page = QLabel("Sayfa 1 / 1")
        self.count = QLabel("0 kayıt")
        self.page_size = QSpinBox()
        self.page_size.setRange(100, 5000)
        self.page_size.setSingleStep(100)
        self.page_size.setValue(500)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search, 3)
        search_layout.addWidget(self.column, 2)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.clear_button)
        pager = QHBoxLayout()
        pager.addWidget(self.count)
        pager.addStretch()
        pager.addWidget(QLabel("Sayfa başına:"))
        pager.addWidget(self.page_size)
        pager.addWidget(self.previous)
        pager.addWidget(self.page)
        pager.addWidget(self.next)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(search_layout)
        layout.addWidget(self.table)
        layout.addLayout(pager)

        self.previous.clicked.connect(self.model.previous_page)
        self.next.clicked.connect(self.model.next_page)
        self.page_size.valueChanged.connect(self.model.set_page_size)
        self.model.page_changed.connect(self._page_changed)
        self.search_button.clicked.connect(self._start_search)
        self.search.returnPressed.connect(self._start_search)
        self.clear_button.clicked.connect(self._clear_search)
        self._filter_thread: QThread | None = None

    def set_dataframe(self, dataframe: pd.DataFrame) -> None:
        self.model.set_dataframe(dataframe)
        self.column.clear()
        self.column.addItem("Tüm sütunlar", None)
        for name in dataframe.columns:
            self.column.addItem(str(name), name)

    def clear(self) -> None:
        self.search.clear()
        self.model.clear()

    def _start_search(self) -> None:
        if self._filter_thread and self._filter_thread.isRunning():
            return
        thread = QThread(self)
        worker = TableFilterWorker(
            self.model.dataframe,
            self.model.base_indices,
            self.search.text(),
            self.column.currentData(),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.model.set_filtered_indices)
        worker.finished.connect(thread.quit)
        worker.failed.connect(lambda _: thread.quit())
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_filter_thread", None))
        self._filter_thread = thread
        thread.start()

    def _clear_search(self) -> None:
        self.search.clear()
        self.model.reset_filter()

    def _page_changed(self, current: int, total: int, count: int) -> None:
        self.page.setText(f"Sayfa {current:,} / {total:,}")
        self.count.setText(f"{count:,} kayıt")
        self.previous.setEnabled(current > 1)
        self.next.setEnabled(current < total)
