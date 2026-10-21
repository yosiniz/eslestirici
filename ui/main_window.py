"""Dinamik çoklu sütun eşleştirme ana penceresi."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.matching_service import MultiMatchResult
from services.template_service import TemplateService
from ui.matching_rules_widget import MatchingRulesWidget
from ui.result_table import ResultTable
from ui.styles import APP_STYLESHEET
from workers.process_worker import HeaderWorker, MultiExportWorker, MultiProcessWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.left_path: str | None = None
        self.right_path: str | None = None
        self.left_sheet: str | None = None
        self.right_sheet: str | None = None
        self.left_columns: list[str] = []
        self.right_columns: list[str] = []
        self.result: MultiMatchResult | None = None
        self.templates = TemplateService()
        self._busy = False
        self._header_threads: dict[str, QThread] = {}
        self._header_workers: dict[str, HeaderWorker] = {}
        self._process_thread: QThread | None = None
        self._process_worker: MultiProcessWorker | None = None
        self._export_thread: QThread | None = None
        self._export_worker: MultiExportWorker | None = None

        self.setWindowTitle("Otopark Plaka Karşılaştırma Sistemi — Çoklu Sütun")
        self.resize(1480, 920)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._connect()
        self._refresh_templates()
        self._update_actions()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 10)
        title = QLabel("Otopark Plaka Karşılaştırma Sistemi")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "Excel/CSV dosyalarını tek veya çok sayıda sütunla, bire bir kayıt güvenliğiyle karşılaştırın."
        )
        subtitle.setObjectName("subtitleLabel")
        root.addWidget(title)
        root.addWidget(subtitle)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._controls())
        splitter.addWidget(self._results())
        splitter.setSizes([335, 560])
        root.addWidget(splitter, 1)
        self.setCentralWidget(central)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedWidth(300)
        self.statusBar().showMessage("Hazır")
        self.statusBar().addPermanentWidget(self.progress)

    def _controls(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        file_grid = QGridLayout()
        self.left_button = QPushButton("Dosya 1 Seç")
        self.right_button = QPushButton("Dosya 2 Seç")
        self.left_label = self._path_label("Dosya seçilmedi")
        self.right_label = self._path_label("Dosya seçilmedi")
        self.left_sheet_combo = QComboBox()
        self.right_sheet_combo = QComboBox()
        self.left_sheet_combo.setMinimumWidth(180)
        self.right_sheet_combo.setMinimumWidth(180)
        self.left_sheet_combo.setEnabled(False)
        self.right_sheet_combo.setEnabled(False)
        file_grid.addWidget(self.left_button, 0, 0)
        file_grid.addWidget(self.left_label, 0, 1)
        file_grid.addWidget(QLabel("Sheet:"), 0, 2)
        file_grid.addWidget(self.left_sheet_combo, 0, 3)
        file_grid.addWidget(self.right_button, 1, 0)
        file_grid.addWidget(self.right_label, 1, 1)
        file_grid.addWidget(QLabel("Sheet:"), 1, 2)
        file_grid.addWidget(self.right_sheet_combo, 1, 3)
        file_grid.setColumnStretch(1, 1)
        layout.addLayout(file_grid)
        rules_title = QLabel("Eşleştirme Kuralları")
        rules_title.setStyleSheet("font-weight:700; color:#17365D; padding-top:5px;")
        layout.addWidget(rules_title)
        self.rules = MatchingRulesWidget()
        layout.addWidget(self.rules)
        action = QHBoxLayout()
        self.compare_button = QPushButton("Karşılaştır")
        self.compare_button.setObjectName("primaryButton")
        self.clear_button = QPushButton("Temizle")
        self.export_button = QPushButton("Excel Olarak Kaydet")
        self.export_button.setObjectName("successButton")
        self.exit_button = QPushButton("Çıkış")
        action.addWidget(self.compare_button)
        action.addWidget(self.clear_button)
        action.addStretch()
        action.addWidget(self.export_button)
        action.addWidget(self.exit_button)
        layout.addLayout(action)
        return panel

    def _results(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        metrics = QHBoxLayout()
        definitions = [
            ("left_total", "Dosya 1 Toplam"),
            ("right_total", "Dosya 2 Toplam"),
            ("matched_pairs", "Eşleşen Çift"),
            ("left_unmatched", "Dosya 1 Eşleşmeyen"),
            ("right_unmatched", "Dosya 2 Eşleşmeyen"),
            ("partial_candidates", "Kısmi Aday"),
        ]
        self.metric_labels: dict[str, QLabel] = {}
        for key, name in definitions:
            card, value = self._metric_card(name)
            self.metric_labels[key] = value
            metrics.addWidget(card)
        layout.addLayout(metrics)
        self.tabs = QTabWidget()
        self.matched_table = ResultTable()
        self.left_unmatched_table = ResultTable()
        self.right_unmatched_table = ResultTable()
        self.partial_table = ResultTable()
        self.tabs.addTab(self.matched_table, "Eşleşenler")
        self.tabs.addTab(self.left_unmatched_table, "Dosya 1 Eşleşmeyenler")
        self.tabs.addTab(self.right_unmatched_table, "Dosya 2 Eşleşmeyenler")
        self.tabs.addTab(self.partial_table, "Kısmi Eşleşenler")
        layout.addWidget(self.tabs, 1)
        return panel

    def _connect(self) -> None:
        self.left_button.clicked.connect(lambda: self._select_file("left"))
        self.right_button.clicked.connect(lambda: self._select_file("right"))
        self.left_sheet_combo.currentTextChanged.connect(
            lambda sheet: self._sheet_changed("left", sheet)
        )
        self.right_sheet_combo.currentTextChanged.connect(
            lambda sheet: self._sheet_changed("right", sheet)
        )
        self.compare_button.clicked.connect(self._start_comparison)
        self.export_button.clicked.connect(self._start_export)
        self.clear_button.clicked.connect(self._clear)
        self.exit_button.clicked.connect(self.close)
        self.rules.changed.connect(self._rules_changed)
        self.rules.save_template_requested.connect(self._save_template)
        self.rules.load_template_requested.connect(self._load_template)
        self.rules.delete_template_requested.connect(self._delete_template)

    def _select_file(self, role: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Excel veya CSV Dosyası Seç", "",
            "Veri Dosyaları (*.xlsx *.xlsm *.xls *.csv)"
        )
        if not path:
            return
        self._invalidate_result()
        label = self.left_label if role == "left" else self.right_label
        label.setText(f"Başlıklar okunuyor... {Path(path).name}")
        label.setToolTip(path)
        self._start_header(role, path)

    def _start_header(
        self, role: str, path: str, sheet_name: str | None = None
    ) -> None:
        if role in self._header_threads:
            return
        thread = QThread(self)
        worker = HeaderWorker(role, path, sheet_name)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._header_loaded)
        worker.failed.connect(self._header_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda role=role: self._header_cleanup(role))
        self._header_threads[role] = thread
        self._header_workers[role] = worker
        self._update_actions()
        thread.start()

    def _header_loaded(
        self,
        role: str,
        path: str,
        sheet: str,
        columns: list[str],
        sheet_names: list[str],
    ) -> None:
        label = self.left_label if role == "left" else self.right_label
        sheet_combo = self.left_sheet_combo if role == "left" else self.right_sheet_combo
        sheet_combo.blockSignals(True)
        sheet_combo.clear()
        sheet_combo.addItems(sheet_names)
        selected_index = sheet_combo.findText(sheet)
        sheet_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        sheet_combo.setEnabled(len(sheet_names) > 1)
        sheet_combo.blockSignals(False)
        if role == "left":
            self.left_path, self.left_sheet, self.left_columns = path, sheet, columns
        else:
            self.right_path, self.right_sheet, self.right_columns = path, sheet, columns
        label.setText(f"{Path(path).name}  •  {sheet}  •  {len(columns)} sütun")
        label.setToolTip(path)
        self.rules.set_columns(self.left_columns, self.right_columns)
        self.statusBar().showMessage(f"{Path(path).name} başlıkları yüklendi.", 4000)
        self._update_actions()

    def _header_failed(self, role: str, path: str, message: str) -> None:
        if role == "left":
            self.left_path, self.left_sheet, self.left_columns = None, None, []
            self.left_label.setText("Dosya seçilemedi")
            self.left_sheet_combo.clear()
            self.left_sheet_combo.setEnabled(False)
        else:
            self.right_path, self.right_sheet, self.right_columns = None, None, []
            self.right_label.setText("Dosya seçilemedi")
            self.right_sheet_combo.clear()
            self.right_sheet_combo.setEnabled(False)
        self.rules.set_columns(self.left_columns, self.right_columns)
        QMessageBox.critical(self, "Dosya Okuma Hatası", message)

    def _header_cleanup(self, role: str) -> None:
        self._header_threads.pop(role, None)
        self._header_workers.pop(role, None)
        self._update_actions()

    def _start_comparison(self) -> None:
        if not self.left_path or not self.right_path:
            QMessageBox.warning(self, "Eksik Dosya", "Lütfen iki dosyayı da seçin.")
            return
        try:
            config = self.rules.config()
        except ValueError as exc:
            QMessageBox.warning(self, "Eksik Kural", str(exc))
            return
        self._invalidate_result()
        self._set_busy(True)
        thread = QThread(self)
        worker = MultiProcessWorker(
            self.left_path,
            self.right_path,
            config,
            self.left_sheet or 0,
            self.right_sheet or 0,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.finished.connect(self._comparison_finished)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._process_cleanup)
        self._process_thread, self._process_worker = thread, worker
        thread.start()

    def _comparison_finished(self, result: MultiMatchResult) -> None:
        self.result = result
        for key, label in self.metric_labels.items():
            label.setText(self._count(getattr(result.summary, key)))
        self.matched_table.set_dataframe(result.matched_pairs)
        self.left_unmatched_table.set_dataframe(result.left_unmatched)
        self.right_unmatched_table.set_dataframe(result.right_unmatched)
        self.partial_table.set_dataframe(result.partial_matches)
        self.tabs.setTabText(0, f"Eşleşenler ({len(result.matched_pairs):,})")
        self.tabs.setTabText(1, f"Dosya 1 Eşleşmeyenler ({len(result.left_unmatched):,})")
        self.tabs.setTabText(2, f"Dosya 2 Eşleşmeyenler ({len(result.right_unmatched):,})")
        self.tabs.setTabText(3, f"Kısmi Eşleşenler ({len(result.partial_matches):,})")
        self.progress.setValue(100)
        self.statusBar().showMessage("Karşılaştırma tamamlandı.", 7000)
        self._set_busy(False)

    def _start_export(self) -> None:
        if self.result is None:
            QMessageBox.warning(self, "Sonuç Yok", "Önce karşılaştırmayı çalıştırın.")
            return
        default = f"CokluEslesmeSonucu_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", default, "Excel Çalışma Kitabı (*.xlsx)"
        )
        if not path:
            return
        self._set_busy(True)
        thread = QThread(self)
        worker = MultiExportWorker(self.result, path)
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
        QMessageBox.information(self, "Dışa Aktarma Tamamlandı", f"Excel oluşturuldu:\n{path}")

    def _operation_failed(self, message: str, details: str) -> None:
        self._set_busy(False)
        self.progress.setValue(0)
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("İşlem Hatası")
        dialog.setText(message)
        dialog.setDetailedText(details)
        dialog.exec()

    def _process_cleanup(self) -> None:
        self._process_thread = None
        self._process_worker = None
        self._update_actions()

    def _export_cleanup(self) -> None:
        self._export_thread = None
        self._export_worker = None
        self._update_actions()

    def _rules_changed(self) -> None:
        if self.result is not None and not self._busy:
            self._invalidate_result()
            self.statusBar().showMessage("Kurallar değişti; karşılaştırmayı yeniden çalıştırın.", 5000)
        self._update_actions()

    def _sheet_changed(self, role: str, sheet: str) -> None:
        if not sheet or self._busy or role in self._header_threads:
            return
        path = self.left_path if role == "left" else self.right_path
        current = self.left_sheet if role == "left" else self.right_sheet
        if not path or sheet == current:
            return
        self._invalidate_result()
        self.statusBar().showMessage(f"{sheet} sayfasının sütunları okunuyor...")
        self._start_header(role, path, sheet)

    def _save_template(self) -> None:
        try:
            config = self.rules.config()
        except ValueError as exc:
            QMessageBox.warning(self, "Şablon", str(exc))
            return
        name, ok = QInputDialog.getText(self, "Şablonu Kaydet", "Şablon adı:")
        if ok and name.strip():
            self.templates.save(name, config)
            self._refresh_templates(name.strip())
            self.statusBar().showMessage("Eşleştirme şablonu kaydedildi.", 4000)

    def _load_template(self, name: str) -> None:
        if not name:
            return
        try:
            config = self.templates.get(name)
            missing_left = sorted({r.left_column for r in config.rules if r.left_column not in self.left_columns})
            missing_right = sorted({r.right_column for r in config.rules if r.right_column not in self.right_columns})
            if missing_left or missing_right:
                details = []
                if missing_left:
                    details.append("Dosya 1: " + ", ".join(missing_left))
                if missing_right:
                    details.append("Dosya 2: " + ", ".join(missing_right))
                raise ValueError("Şablondaki bazı sütunlar açık dosyalarda yok:\n" + "\n".join(details))
            self.rules.load_config(config)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Şablon Yüklenemedi", str(exc))

    def _delete_template(self, name: str) -> None:
        if not name:
            return
        answer = QMessageBox.question(self, "Şablonu Sil", f"'{name}' şablonu silinsin mi?")
        if answer == QMessageBox.StandardButton.Yes:
            self.templates.delete(name)
            self._refresh_templates()

    def _refresh_templates(self, selected: str = "") -> None:
        self.rules.set_template_names(self.templates.list_names(), selected)

    def _invalidate_result(self) -> None:
        self.result = None
        for table in (
            self.matched_table, self.left_unmatched_table,
            self.right_unmatched_table, self.partial_table,
        ):
            table.clear()
        for label in self.metric_labels.values():
            label.setText("—")
        self.progress.setValue(0)
        self._update_actions()

    def _clear(self) -> None:
        self.left_path = self.right_path = None
        self.left_sheet = self.right_sheet = None
        self.left_columns = []
        self.right_columns = []
        self.left_label.setText("Dosya seçilmedi")
        self.right_label.setText("Dosya seçilmedi")
        self.left_sheet_combo.clear()
        self.right_sheet_combo.clear()
        self.left_sheet_combo.setEnabled(False)
        self.right_sheet_combo.setEnabled(False)
        self.rules.set_columns([], [])
        self._invalidate_result()

    def _show_progress(self, value: int, message: str) -> None:
        self.progress.setValue(max(0, min(value, 100)))
        self.statusBar().showMessage(message)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_actions()

    def _update_actions(self) -> None:
        ready = bool(self.left_path and self.right_path and self.rules.rows)
        self.left_button.setEnabled(not self._busy and "left" not in self._header_threads)
        self.right_button.setEnabled(not self._busy and "right" not in self._header_threads)
        self.left_sheet_combo.setEnabled(
            not self._busy
            and "left" not in self._header_threads
            and self.left_sheet_combo.count() > 1
        )
        self.right_sheet_combo.setEnabled(
            not self._busy
            and "right" not in self._header_threads
            and self.right_sheet_combo.count() > 1
        )
        self.compare_button.setEnabled(not self._busy and ready)
        self.export_button.setEnabled(not self._busy and self.result is not None)
        self.clear_button.setEnabled(not self._busy)

    @staticmethod
    def _path_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("pathLabel")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return label

    @staticmethod
    def _metric_card(name: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 7, 8, 7)
        value = QLabel("—")
        value.setObjectName("metricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(name)
        label.setObjectName("metricName")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value)
        layout.addWidget(label)
        return card, value

    @staticmethod
    def _count(value: int) -> str:
        return f"{int(value):,}".replace(",", ".")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._process_thread or self._export_thread or self._header_threads:
            QMessageBox.warning(self, "İşlem Devam Ediyor", "Devam eden işlem tamamlanmadan kapatılamaz.")
            event.ignore()
            return
        event.accept()
