"""Excel filtreleme, hesaplama ve veri temizleme penceresi."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.data_operation_service import (
    FILTER_LABELS,
    DataOperationService,
    FilterCondition,
    FilterOperator,
    OperationResult,
)
from ui.result_table import ResultTable
from workers.process_worker import (
    DataOperationWorker,
    DataToolsExportWorker,
    DataToolsLoadWorker,
)


class DataToolsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.path: str | None = None
        self.sheet: str | None = None
        self.original = pd.DataFrame()
        self.current = pd.DataFrame()
        self.conditions: list[FilterCondition] = []
        self._busy = False
        self._load_thread: QThread | None = None
        self._load_worker: DataToolsLoadWorker | None = None
        self._operation_thread: QThread | None = None
        self._operation_worker: DataOperationWorker | None = None
        self._export_thread: QThread | None = None
        self._export_worker: DataToolsExportWorker | None = None

        self.setWindowTitle("Excel İşlemleri ve Filtreler")
        self.resize(1380, 900)
        self.setMinimumSize(1050, 720)
        self._build_ui()
        self._connect()
        self._update_actions()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        title = QLabel("Excel İşlemleri ve Filtreler")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "Filtreleri ve hesaplamaları çalışma kopyasına uygulayın; kaynak dosya hiçbir zaman değiştirilmez."
        )
        subtitle.setObjectName("subtitleLabel")
        root.addWidget(title)
        root.addWidget(subtitle)

        file_row = QHBoxLayout()
        self.file_button = QPushButton("Excel/CSV Seç")
        self.file_button.setObjectName("primaryButton")
        self.file_label = QLabel("Dosya seçilmedi")
        self.file_label.setObjectName("pathLabel")
        self.sheet_combo = QComboBox()
        self.sheet_combo.setMinimumWidth(190)
        file_row.addWidget(self.file_button)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(QLabel("Sheet:"))
        file_row.addWidget(self.sheet_combo)
        root.addLayout(file_row)

        self.tools_tabs = QTabWidget()
        self.tools_tabs.addTab(self._filter_tab(), "Filtreleme")
        self.tools_tabs.addTab(self._calculation_tab(), "Hesaplama ve Sıralama")
        self.tools_tabs.addTab(self._cleaning_tab(), "Boşlar, Tekrarlar ve Metin")
        self.tools_tabs.setMaximumHeight(315)
        root.addWidget(self.tools_tabs)

        metrics = QHBoxLayout()
        self.record_label = QLabel("Kayıt: —")
        self.record_label.setObjectName("metricValue")
        self.column_count_label = QLabel("Sütun: —")
        self.column_count_label.setObjectName("metricValue")
        self.scalar_label = QLabel("Hesaplama sonucu: —")
        self.scalar_label.setObjectName("metricValue")
        metrics.addWidget(self.record_label)
        metrics.addSpacing(24)
        metrics.addWidget(self.column_count_label)
        metrics.addSpacing(24)
        metrics.addWidget(self.scalar_label, 1)
        root.addLayout(metrics)

        self.preview = ResultTable()
        root.addWidget(self.preview, 1)

        footer = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMinimumWidth(260)
        self.status_label = QLabel("Hazır")
        self.reset_button = QPushButton("Orijinal Veriye Dön")
        self.export_button = QPushButton("İşlenmiş Exceli Kaydet")
        self.export_button.setObjectName("successButton")
        self.close_button = QPushButton("Kapat")
        footer.addWidget(self.progress)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.reset_button)
        footer.addWidget(self.export_button)
        footer.addWidget(self.close_button)
        root.addLayout(footer)

    def _filter_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        rule = QHBoxLayout()
        self.filter_column = QComboBox()
        self.filter_operator = QComboBox()
        for operator, label in FILTER_LABELS.items():
            self.filter_operator.addItem(label, operator)
        self.filter_value = QLineEdit()
        self.filter_value.setPlaceholderText("Değer")
        self.filter_second = QLineEdit()
        self.filter_second.setPlaceholderText("İkinci değer")
        self.add_filter_button = QPushButton("+ Filtre Ekle")
        rule.addWidget(QLabel("Sütun:"))
        rule.addWidget(self.filter_column, 2)
        rule.addWidget(QLabel("Koşul:"))
        rule.addWidget(self.filter_operator, 2)
        rule.addWidget(self.filter_value, 2)
        rule.addWidget(self.filter_second, 2)
        rule.addWidget(self.add_filter_button)
        layout.addLayout(rule)

        self.filter_table = QTableWidget(0, 4)
        self.filter_table.setHorizontalHeaderLabels(
            ["Sütun", "Koşul", "Değer", "İkinci Değer"]
        )
        self.filter_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.filter_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.filter_table.verticalHeader().setVisible(False)
        self.filter_table.horizontalHeader().setStretchLastSection(True)
        self.filter_table.setMaximumHeight(130)
        layout.addWidget(self.filter_table)

        actions = QHBoxLayout()
        self.filter_logic = QComboBox()
        self.filter_logic.addItem("VE — bütün kurallar", "and")
        self.filter_logic.addItem("VEYA — kurallardan biri", "or")
        self.remove_filter_button = QPushButton("Seçili Filtreyi Sil")
        self.clear_filters_button = QPushButton("Filtreleri Temizle")
        self.apply_filters_button = QPushButton("Filtreleri Uygula")
        self.apply_filters_button.setObjectName("primaryButton")
        actions.addWidget(QLabel("Mantık:"))
        actions.addWidget(self.filter_logic)
        actions.addStretch()
        actions.addWidget(self.remove_filter_button)
        actions.addWidget(self.clear_filters_button)
        actions.addWidget(self.apply_filters_button)
        layout.addLayout(actions)
        return tab

    def _calculation_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        top = QHBoxLayout()

        aggregate = QGroupBox("Özet hesaplama")
        aggregate_form = QFormLayout(aggregate)
        self.aggregate_column = QComboBox()
        self.aggregate_function = QComboBox()
        for key, label in DataOperationService.AGGREGATIONS.items():
            self.aggregate_function.addItem(label, key)
        self.aggregate_button = QPushButton("Hesapla")
        aggregate_form.addRow("Sütun:", self.aggregate_column)
        aggregate_form.addRow("İşlem:", self.aggregate_function)
        aggregate_form.addRow(self.aggregate_button)
        top.addWidget(aggregate, 1)

        sorting = QGroupBox("Sıralama")
        sorting_form = QFormLayout(sorting)
        self.sort_column = QComboBox()
        self.sort_direction = QComboBox()
        self.sort_direction.addItem("Küçükten büyüğe / A-Z", True)
        self.sort_direction.addItem("Büyükten küçüğe / Z-A", False)
        self.sort_button = QPushButton("Sırala")
        sorting_form.addRow("Sütun:", self.sort_column)
        sorting_form.addRow("Yön:", self.sort_direction)
        sorting_form.addRow(self.sort_button)
        top.addWidget(sorting, 1)
        layout.addLayout(top)

        calculated = QGroupBox("Hesaplanmış yeni sütun")
        grid = QGridLayout(calculated)
        self.calc_left = QComboBox()
        self.calc_operation = QComboBox()
        for label, value in (
            ("Topla (+)", "add"),
            ("Çıkar (-)", "subtract"),
            ("Çarp (×)", "multiply"),
            ("Böl (÷)", "divide"),
            ("Yüzdesini hesapla", "percent"),
            ("Yüzde değişim", "percent_change"),
            ("Metinleri birleştir", "concat"),
        ):
            self.calc_operation.addItem(label, value)
        self.calc_right_mode = QComboBox()
        self.calc_right_mode.addItem("İkinci sütun", "column")
        self.calc_right_mode.addItem("Sabit sayı", "constant")
        self.calc_right_column = QComboBox()
        self.calc_constant = QLineEdit()
        self.calc_constant.setPlaceholderText("Örn. 20")
        self.calc_output = QLineEdit()
        self.calc_output.setPlaceholderText("Yeni sütun adı")
        self.calc_button = QPushButton("Yeni Sütunu Oluştur")
        self.calc_button.setObjectName("primaryButton")
        grid.addWidget(QLabel("Birinci sütun:"), 0, 0)
        grid.addWidget(self.calc_left, 0, 1)
        grid.addWidget(QLabel("İşlem:"), 0, 2)
        grid.addWidget(self.calc_operation, 0, 3)
        grid.addWidget(self.calc_right_mode, 1, 0)
        grid.addWidget(self.calc_right_column, 1, 1)
        grid.addWidget(self.calc_constant, 1, 2)
        grid.addWidget(self.calc_output, 1, 3)
        grid.addWidget(self.calc_button, 1, 4)
        layout.addWidget(calculated)
        return tab

    def _cleaning_tab(self) -> QWidget:
        tab = QWidget()
        layout = QGridLayout(tab)
        missing = QGroupBox("Boş değerler")
        form = QFormLayout(missing)
        self.missing_column = QComboBox()
        self.fill_value = QLineEdit()
        self.fill_value.setPlaceholderText("Doldurulacak değer")
        missing_actions = QHBoxLayout()
        self.drop_missing_button = QPushButton("Boş Satırları Kaldır")
        self.fill_missing_button = QPushButton("Boşları Doldur")
        missing_actions.addWidget(self.drop_missing_button)
        missing_actions.addWidget(self.fill_missing_button)
        form.addRow("Sütun:", self.missing_column)
        form.addRow("Değer:", self.fill_value)
        form.addRow(missing_actions)
        layout.addWidget(missing, 0, 0)

        duplicates = QGroupBox("Tekrar eden kayıtlar")
        duplicate_form = QFormLayout(duplicates)
        self.duplicate_scope = QComboBox()
        self.duplicate_scope.addItem("Tamamen aynı satırlar", "all")
        self.duplicate_scope.addItem("Seçilen sütuna göre", "column")
        self.duplicate_column = QComboBox()
        self.duplicate_keep = QComboBox()
        self.duplicate_keep.addItem("İlk kaydı bırak", "first")
        self.duplicate_keep.addItem("Son kaydı bırak", "last")
        self.remove_duplicates_button = QPushButton("Tekrarları Kaldır")
        duplicate_form.addRow("Kapsam:", self.duplicate_scope)
        duplicate_form.addRow("Sütun:", self.duplicate_column)
        duplicate_form.addRow("Sakla:", self.duplicate_keep)
        duplicate_form.addRow(self.remove_duplicates_button)
        layout.addWidget(duplicates, 0, 1)

        text = QGroupBox("Metin düzenleme")
        text_form = QFormLayout(text)
        self.text_column = QComboBox()
        self.text_operation = QComboBox()
        self.text_operation.addItem("Baştaki/sondaki boşlukları temizle", "trim")
        self.text_operation.addItem("BÜYÜK HARF", "upper")
        self.text_operation.addItem("küçük harf", "lower")
        self.text_operation.addItem("Başlık Biçimi", "title")
        self.text_button = QPushButton("Metin İşlemini Uygula")
        text_form.addRow("Sütun:", self.text_column)
        text_form.addRow("İşlem:", self.text_operation)
        text_form.addRow(self.text_button)
        layout.addWidget(text, 1, 0, 1, 2)
        return tab

    def _connect(self) -> None:
        self.file_button.clicked.connect(self._select_file)
        self.sheet_combo.currentTextChanged.connect(self._sheet_changed)
        self.filter_operator.currentIndexChanged.connect(self._filter_operator_changed)
        self.add_filter_button.clicked.connect(self._add_filter)
        self.remove_filter_button.clicked.connect(self._remove_filter)
        self.clear_filters_button.clicked.connect(self._clear_filters)
        self.apply_filters_button.clicked.connect(self._apply_filters)
        self.aggregate_button.clicked.connect(self._calculate)
        self.sort_button.clicked.connect(self._sort)
        self.calc_right_mode.currentIndexChanged.connect(self._calc_mode_changed)
        self.calc_operation.currentIndexChanged.connect(self._calc_operation_changed)
        self.calc_button.clicked.connect(self._create_calculated_column)
        self.drop_missing_button.clicked.connect(self._drop_missing)
        self.fill_missing_button.clicked.connect(self._fill_missing)
        self.duplicate_scope.currentIndexChanged.connect(self._duplicate_scope_changed)
        self.remove_duplicates_button.clicked.connect(self._remove_duplicates)
        self.text_button.clicked.connect(self._transform_text)
        self.reset_button.clicked.connect(self._reset_original)
        self.export_button.clicked.connect(self._start_export)
        self.close_button.clicked.connect(self.close)
        self._filter_operator_changed()
        self._calc_mode_changed()
        self._duplicate_scope_changed()

    def _select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "İşlenecek Excel veya CSV Dosyasını Seç",
            "",
            "Veri Dosyaları (*.xlsx *.xlsm *.xls *.csv)",
        )
        if path:
            self._start_load(path)

    def _start_load(self, path: str, sheet: str | None = None) -> None:
        self._set_busy(True)
        thread = QThread(self)
        worker = DataToolsLoadWorker(path, sheet)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.finished.connect(self._load_finished)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._load_cleanup)
        self._load_thread, self._load_worker = thread, worker
        thread.start()

    def _load_finished(
        self,
        path: str,
        sheet: str,
        sheets: list[str],
        columns: list[str],
        dataframe: pd.DataFrame,
    ) -> None:
        self.path, self.sheet = path, sheet
        self.original = dataframe.copy()
        self.current = dataframe.copy()
        self.file_label.setText(f"{Path(path).name} • {sheet}")
        self.file_label.setToolTip(path)
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(sheets)
        self.sheet_combo.setCurrentText(sheet)
        self.sheet_combo.blockSignals(False)
        self._set_columns(columns)
        self.conditions.clear()
        self._render_filters()
        self.scalar_label.setText("Hesaplama sonucu: —")
        self._show_dataframe("Dosya yüklendi.")
        self._set_busy(False)

    def _sheet_changed(self, sheet: str) -> None:
        if self.path and sheet and sheet != self.sheet and not self._busy:
            self._start_load(self.path, sheet)

    def _set_columns(self, columns: list[str]) -> None:
        combos = (
            self.filter_column,
            self.aggregate_column,
            self.sort_column,
            self.calc_left,
            self.calc_right_column,
            self.missing_column,
            self.duplicate_column,
            self.text_column,
        )
        for combo in combos:
            current = combo.currentText()
            combo.clear()
            combo.addItems(columns)
            if current in columns:
                combo.setCurrentText(current)

    def _filter_operator_changed(self) -> None:
        operator = self.filter_operator.currentData()
        needs_value = operator not in {FilterOperator.EMPTY, FilterOperator.NOT_EMPTY}
        self.filter_value.setEnabled(needs_value)
        self.filter_second.setEnabled(operator == FilterOperator.BETWEEN)
        if not needs_value:
            self.filter_value.clear()
        if operator != FilterOperator.BETWEEN:
            self.filter_second.clear()

    def _add_filter(self) -> None:
        if self.current.empty and not len(self.current.columns):
            return
        operator = FilterOperator(self.filter_operator.currentData())
        if operator not in {FilterOperator.EMPTY, FilterOperator.NOT_EMPTY} and not self.filter_value.text().strip():
            QMessageBox.warning(self, "Filtre", "Filtre değerini yazın.")
            return
        if operator == FilterOperator.BETWEEN and not self.filter_second.text().strip():
            QMessageBox.warning(self, "Filtre", "Aralığın ikinci değerini yazın.")
            return
        self.conditions.append(
            FilterCondition(
                self.filter_column.currentText(),
                operator,
                self.filter_value.text(),
                self.filter_second.text(),
            )
        )
        self.filter_value.clear()
        self.filter_second.clear()
        self._render_filters()

    def _render_filters(self) -> None:
        self.filter_table.setRowCount(0)
        for row, condition in enumerate(self.conditions):
            self.filter_table.insertRow(row)
            values = (
                condition.column,
                FILTER_LABELS[condition.operator],
                condition.value,
                condition.second_value,
            )
            for column, value in enumerate(values):
                self.filter_table.setItem(row, column, QTableWidgetItem(value))
        self._update_actions()

    def _remove_filter(self) -> None:
        rows = sorted({item.row() for item in self.filter_table.selectedItems()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self.conditions):
                self.conditions.pop(row)
        self._render_filters()

    def _clear_filters(self) -> None:
        self.conditions.clear()
        self._render_filters()

    def _apply_filters(self) -> None:
        self._start_operation(
            "filter",
            {"conditions": list(self.conditions), "logic": self.filter_logic.currentData()},
        )

    def _calculate(self) -> None:
        self._start_operation(
            "aggregate",
            {
                "column": self.aggregate_column.currentText(),
                "function": self.aggregate_function.currentData(),
            },
        )

    def _sort(self) -> None:
        self._start_operation(
            "sort",
            {
                "column": self.sort_column.currentText(),
                "ascending": bool(self.sort_direction.currentData()),
            },
        )

    def _calc_mode_changed(self) -> None:
        column_mode = self.calc_right_mode.currentData() == "column"
        self.calc_right_column.setEnabled(column_mode)
        self.calc_constant.setEnabled(not column_mode)

    def _calc_operation_changed(self) -> None:
        if self.calc_operation.currentData() == "concat":
            self.calc_right_mode.setCurrentIndex(0)
            self.calc_right_mode.setEnabled(False)
        else:
            self.calc_right_mode.setEnabled(True)
        self._calc_mode_changed()

    def _create_calculated_column(self) -> None:
        column_mode = self.calc_right_mode.currentData() == "column"
        self._start_operation(
            "calculated_column",
            {
                "left_column": self.calc_left.currentText(),
                "operation": self.calc_operation.currentData(),
                "output_name": self.calc_output.text(),
                "right_column": self.calc_right_column.currentText() if column_mode else None,
                "constant": None if column_mode else self.calc_constant.text(),
            },
        )

    def _drop_missing(self) -> None:
        self._start_operation(
            "drop_missing", {"column": self.missing_column.currentText()}
        )

    def _fill_missing(self) -> None:
        self._start_operation(
            "fill_missing",
            {"column": self.missing_column.currentText(), "value": self.fill_value.text()},
        )

    def _duplicate_scope_changed(self) -> None:
        self.duplicate_column.setEnabled(self.duplicate_scope.currentData() == "column")

    def _remove_duplicates(self) -> None:
        columns = (
            [self.duplicate_column.currentText()]
            if self.duplicate_scope.currentData() == "column"
            else None
        )
        self._start_operation(
            "remove_duplicates",
            {"columns": columns, "keep": self.duplicate_keep.currentData()},
        )

    def _transform_text(self) -> None:
        self._start_operation(
            "transform_text",
            {
                "column": self.text_column.currentText(),
                "text_operation": self.text_operation.currentData(),
            },
        )

    def _start_operation(self, operation: str, options: dict) -> None:
        if self.current.empty and not len(self.current.columns):
            QMessageBox.warning(self, "Dosya Yok", "Önce bir Excel veya CSV seçin.")
            return
        self._set_busy(True)
        thread = QThread(self)
        worker = DataOperationWorker(self.current, operation, options)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.finished.connect(self._operation_finished)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._operation_cleanup)
        self._operation_thread, self._operation_worker = thread, worker
        thread.start()

    def _operation_finished(self, result: OperationResult) -> None:
        if result.scalar_label is not None:
            self.scalar_label.setText(
                f"{result.scalar_label}: {self._format_scalar(result.scalar_value)}"
            )
        else:
            self.current = result.dataframe
            self._set_columns([str(column) for column in self.current.columns])
            self.preview.set_dataframe(self.current)
        self._show_dataframe(result.message, refresh_preview=False)
        self._set_busy(False)

    def _reset_original(self) -> None:
        if self.original.empty and not len(self.original.columns):
            return
        self.current = self.original.copy()
        self._set_columns([str(column) for column in self.current.columns])
        self.scalar_label.setText("Hesaplama sonucu: —")
        self._show_dataframe("Orijinal çalışma kopyasına dönüldü.")

    def _show_dataframe(self, message: str, refresh_preview: bool = True) -> None:
        if refresh_preview:
            self.preview.set_dataframe(self.current)
        self.record_label.setText(f"Kayıt: {len(self.current):,}")
        self.column_count_label.setText(f"Sütun: {len(self.current.columns):,}")
        self.status_label.setText(message)
        self.progress.setValue(100)
        self._update_actions()

    def _start_export(self) -> None:
        if self.current.empty and not len(self.current.columns):
            return
        default = f"IslenmisExcel_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "İşlenmiş Exceli Kaydet", default, "Excel Çalışma Kitabı (*.xlsx)"
        )
        if not path:
            return
        self._set_busy(True)
        thread = QThread(self)
        worker = DataToolsExportWorker(self.current, path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.finished.connect(self._export_finished)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._export_cleanup)
        self._export_thread, self._export_worker = thread, worker
        thread.start()

    def _export_finished(self, path: str) -> None:
        self._set_busy(False)
        self.progress.setValue(100)
        self.status_label.setText("İşlenmiş Excel kaydedildi.")
        QMessageBox.information(self, "Excel Oluşturuldu", f"Dosya kaydedildi:\n{path}")

    def _show_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(value, 100)))
        self.status_label.setText(message)

    def _operation_failed(self, message: str, details: str) -> None:
        self._set_busy(False)
        self.progress.setValue(0)
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("Excel İşlemi Hatası")
        dialog.setText(message)
        dialog.setDetailedText(details)
        dialog.exec()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_actions()

    def _update_actions(self) -> None:
        loaded = bool(len(self.current.columns))
        self.file_button.setEnabled(not self._busy)
        self.sheet_combo.setEnabled(not self._busy and self.sheet_combo.count() > 1)
        self.tools_tabs.setEnabled(not self._busy and loaded)
        self.close_button.setEnabled(not self._busy)
        self.reset_button.setEnabled(not self._busy and loaded)
        self.export_button.setEnabled(not self._busy and loaded)
        self.apply_filters_button.setEnabled(not self._busy and loaded and bool(self.conditions))
        self.remove_filter_button.setEnabled(not self._busy and bool(self.conditions))
        self.clear_filters_button.setEnabled(not self._busy and bool(self.conditions))

    def _load_cleanup(self) -> None:
        self._load_thread = None
        self._load_worker = None
        self._update_actions()

    def _operation_cleanup(self) -> None:
        self._operation_thread = None
        self._operation_worker = None
        self._update_actions()

    def _export_cleanup(self) -> None:
        self._export_thread = None
        self._export_worker = None
        self._update_actions()

    @staticmethod
    def _format_scalar(value: object) -> str:
        if isinstance(value, Decimal):
            text = format(value, "f")
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            return text
        return str(value)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._load_thread or self._operation_thread or self._export_thread:
            QMessageBox.warning(
                self, "İşlem Devam Ediyor", "İşlem tamamlanmadan pencere kapatılamaz."
            )
            event.ignore()
            return
        event.accept()
