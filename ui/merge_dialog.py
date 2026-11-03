"""Birden fazla Excel/CSV dosyasını alt alta birleştirme penceresi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from services.merge_service import MergeInput, MergeResult, MergeService
from ui.result_table import ResultTable
from workers.process_worker import MergeExportWorker, MergeMetadataWorker, MergeWorker


@dataclass
class MergeFileEntry:
    path: str
    sheets: list[str]
    selected_sheet: str


class MergeDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.entries: list[MergeFileEntry] = []
        self.result: MergeResult | None = None
        self._busy = False
        self._metadata_thread: QThread | None = None
        self._metadata_worker: MergeMetadataWorker | None = None
        self._merge_thread: QThread | None = None
        self._merge_worker: MergeWorker | None = None
        self._export_thread: QThread | None = None
        self._export_worker: MergeExportWorker | None = None

        self.setWindowTitle("Excel Dosyalarını Alt Alta Birleştir")
        self.resize(1260, 820)
        self.setMinimumSize(900, 650)
        self._build_ui()
        self._connect()
        self._update_actions()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel("Excel Birleştirme")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "İki veya daha fazla Excel/CSV seçin; her dosyanın sheet'ini belirleyip "
            "kayıtları seçtiğiniz sırayla alt alta ekleyin."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.add_button = QPushButton("+ Excel/CSV Ekle")
        self.add_button.setObjectName("primaryButton")
        self.remove_button = QPushButton("Seçileni Kaldır")
        self.up_button = QPushButton("Yukarı")
        self.down_button = QPushButton("Aşağı")
        self.clear_button = QPushButton("Listeyi Temizle")
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addWidget(self.up_button)
        toolbar.addWidget(self.down_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.files_table = QTableWidget(0, 3)
        self.files_table.setHorizontalHeaderLabels(["Sıra", "Dosya", "Sheet"])
        self.files_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.files_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setColumnWidth(0, 60)
        self.files_table.setColumnWidth(1, 690)
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.setMinimumHeight(170)
        layout.addWidget(self.files_table)

        options = QHBoxLayout()
        options.addWidget(QLabel("Kolon davranışı:"))
        self.align_combo = QComboBox()
        self.align_combo.addItem(
            "Kolon adlarına göre hizala; eksikleri boş bırak (Önerilen)",
            MergeService.ALIGN_UNION,
        )
        self.align_combo.addItem(
            "Bütün dosyalarda aynı kolon yapısını zorunlu tut",
            MergeService.ALIGN_STRICT,
        )
        self.align_combo.setMinimumWidth(430)
        self.source_checkbox = QCheckBox(
            "Kaynak Dosya, Kaynak Sheet ve Kaynak Satır kolonlarını ekle"
        )
        self.source_checkbox.setChecked(True)
        options.addWidget(self.align_combo)
        options.addSpacing(18)
        options.addWidget(self.source_checkbox)
        options.addStretch()
        layout.addLayout(options)

        summary = QHBoxLayout()
        self.file_count_label = QLabel("0 dosya")
        self.file_count_label.setObjectName("metricValue")
        self.row_count_label = QLabel("Sonuç: —")
        self.row_count_label.setObjectName("metricValue")
        summary.addWidget(self.file_count_label)
        summary.addSpacing(30)
        summary.addWidget(self.row_count_label)
        summary.addStretch()
        layout.addLayout(summary)

        self.preview = ResultTable()
        layout.addWidget(self.preview, 1)

        footer = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMinimumWidth(280)
        self.status_label = QLabel("Hazır")
        self.merge_button = QPushButton("Dosyaları Birleştir")
        self.merge_button.setObjectName("primaryButton")
        self.export_button = QPushButton("Birleşik Exceli Kaydet")
        self.export_button.setObjectName("successButton")
        self.close_button = QPushButton("Kapat")
        footer.addWidget(self.progress)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.merge_button)
        footer.addWidget(self.export_button)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

    def _connect(self) -> None:
        self.add_button.clicked.connect(self._select_files)
        self.remove_button.clicked.connect(self._remove_selected)
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        self.clear_button.clicked.connect(self._clear_files)
        self.files_table.itemSelectionChanged.connect(self._update_actions)
        self.align_combo.currentIndexChanged.connect(self._options_changed)
        self.source_checkbox.toggled.connect(self._options_changed)
        self.merge_button.clicked.connect(self._start_merge)
        self.export_button.clicked.connect(self._start_export)
        self.close_button.clicked.connect(self.close)

    def _select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Birleştirilecek Excel veya CSV Dosyalarını Seç",
            "",
            "Veri Dosyaları (*.xlsx *.xlsm *.xls *.csv)",
        )
        if not paths:
            return
        self._set_busy(True)
        thread = QThread(self)
        worker = MergeMetadataWorker(paths)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.finished.connect(self._metadata_finished)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._metadata_cleanup)
        self._metadata_thread, self._metadata_worker = thread, worker
        thread.start()

    def _metadata_finished(self, items: list[tuple[str, list[str]]]) -> None:
        for path, sheets in items:
            self.entries.append(MergeFileEntry(path, sheets, sheets[0]))
        self._render_entries()
        self._invalidate_result()
        self._set_busy(False)

    def _render_entries(self) -> None:
        self.files_table.setRowCount(0)
        for row, entry in enumerate(self.entries):
            self.files_table.insertRow(row)
            order_item = QTableWidgetItem(str(row + 1))
            order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.files_table.setItem(row, 0, order_item)
            file_item = QTableWidgetItem(Path(entry.path).name)
            file_item.setToolTip(entry.path)
            self.files_table.setItem(row, 1, file_item)
            combo = QComboBox()
            combo.addItems(entry.sheets)
            combo.setCurrentText(entry.selected_sheet)
            combo.currentTextChanged.connect(
                lambda text, index=row: self._sheet_changed(index, text)
            )
            self.files_table.setCellWidget(row, 2, combo)
        self.file_count_label.setText(f"{len(self.entries):,} dosya")
        self._update_actions()

    def _sheet_changed(self, index: int, sheet: str) -> None:
        if 0 <= index < len(self.entries) and sheet:
            self.entries[index].selected_sheet = sheet
            self._invalidate_result()

    def _remove_selected(self) -> None:
        rows = sorted({item.row() for item in self.files_table.selectedItems()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self.entries):
                self.entries.pop(row)
        if rows:
            self._render_entries()
            self._invalidate_result()

    def _move_selected(self, direction: int) -> None:
        row = self.files_table.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= len(self.entries):
            return
        self.entries[row], self.entries[target] = self.entries[target], self.entries[row]
        self._render_entries()
        self.files_table.selectRow(target)
        self._invalidate_result()

    def _clear_files(self) -> None:
        self.entries.clear()
        self._render_entries()
        self._invalidate_result()

    def _options_changed(self) -> None:
        if not self._busy:
            self._invalidate_result()

    def _start_merge(self) -> None:
        if len(self.entries) < 2:
            QMessageBox.warning(
                self, "Eksik Dosya", "Birleştirmek için en az iki dosya ekleyin."
            )
            return
        inputs = [
            MergeInput(entry.path, entry.selected_sheet) for entry in self.entries
        ]
        self._invalidate_result()
        self._set_busy(True)
        thread = QThread(self)
        worker = MergeWorker(
            inputs,
            str(self.align_combo.currentData()),
            self.source_checkbox.isChecked(),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.finished.connect(self._merge_finished)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._merge_cleanup)
        self._merge_thread, self._merge_worker = thread, worker
        thread.start()

    def _merge_finished(self, result: MergeResult) -> None:
        self.result = result
        self.preview.set_dataframe(result.dataframe)
        self.row_count_label.setText(
            f"Sonuç: {result.total_rows:,} satır • {result.total_columns:,} sütun"
        )
        self.progress.setValue(100)
        self.status_label.setText("Birleştirme tamamlandı.")
        self._set_busy(False)

    def _start_export(self) -> None:
        if self.result is None:
            QMessageBox.warning(self, "Sonuç Yok", "Önce dosyaları birleştirin.")
            return
        default = f"BirlesikExcel_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Birleşik Exceli Kaydet", default, "Excel Çalışma Kitabı (*.xlsx)"
        )
        if not path:
            return
        self._set_busy(True)
        thread = QThread(self)
        worker = MergeExportWorker(self.result, path)
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
        self.progress.setValue(100)
        self.status_label.setText("Excel kaydedildi.")
        self._set_busy(False)
        QMessageBox.information(
            self, "Birleştirme Tamamlandı", f"Birleşik Excel oluşturuldu:\n{path}"
        )

    def _show_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(value, 100)))
        self.status_label.setText(message)

    def _operation_failed(self, message: str, details: str) -> None:
        self._set_busy(False)
        self.progress.setValue(0)
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("Birleştirme Hatası")
        dialog.setText(message)
        dialog.setDetailedText(details)
        dialog.exec()

    def _invalidate_result(self) -> None:
        self.result = None
        self.preview.clear()
        self.row_count_label.setText("Sonuç: —")
        self.progress.setValue(0)
        self.status_label.setText("Hazır")
        self._update_actions()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_actions()

    def _update_actions(self) -> None:
        has_selection = bool(self.files_table.selectedItems())
        self.add_button.setEnabled(not self._busy)
        self.remove_button.setEnabled(not self._busy and has_selection)
        self.up_button.setEnabled(not self._busy and len(self.entries) > 1)
        self.down_button.setEnabled(not self._busy and len(self.entries) > 1)
        self.clear_button.setEnabled(not self._busy and bool(self.entries))
        self.files_table.setEnabled(not self._busy)
        self.align_combo.setEnabled(not self._busy)
        self.source_checkbox.setEnabled(not self._busy)
        self.merge_button.setEnabled(not self._busy and len(self.entries) >= 2)
        self.export_button.setEnabled(not self._busy and self.result is not None)
        self.close_button.setEnabled(not self._busy)

    def _metadata_cleanup(self) -> None:
        self._metadata_thread = None
        self._metadata_worker = None
        self._update_actions()

    def _merge_cleanup(self) -> None:
        self._merge_thread = None
        self._merge_worker = None
        self._update_actions()

    def _export_cleanup(self) -> None:
        self._export_thread = None
        self._export_worker = None
        self._update_actions()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._metadata_thread or self._merge_thread or self._export_thread:
            QMessageBox.warning(
                self,
                "İşlem Devam Ediyor",
                "Devam eden işlem tamamlanmadan pencere kapatılamaz.",
            )
            event.ignore()
            return
        event.accept()
