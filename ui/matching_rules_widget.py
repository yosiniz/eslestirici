"""Kullanıcı tarafından dinamik olarak düzenlenen eşleştirme kuralları."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from services.matching_service import (
    DuplicateMode,
    LogicMode,
    MatchOperator,
    MatchRule,
    MultiMatchConfig,
)
from utils.value_normalizers import NormalizationOptions, ValueKind


KIND_ITEMS = [
    ("Otomatik", ValueKind.AUTO),
    ("Metin", ValueKind.TEXT),
    ("Plaka", ValueKind.PLATE),
    ("Parasal / Sayısal", ValueKind.DECIMAL),
    ("Tarih", ValueKind.DATE),
    ("Tarih + Saat", ValueKind.DATETIME),
]
OPERATOR_ITEMS = [
    ("Eşittir", MatchOperator.EQUALS),
    ("Sayısal Tolerans", MatchOperator.NUMERIC_TOLERANCE),
    ("Tarih Toleransı", MatchOperator.DATE_TOLERANCE),
]


class NormalizationDialog(QDialog):
    def __init__(self, options: NormalizationOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Karşılaştırma Ayarları")
        self.trim = QCheckBox("Baştaki ve sondaki boşlukları temizle")
        self.trim.setChecked(options.trim)
        self.case = QCheckBox("Büyük / küçük harfi yok say")
        self.case.setChecked(options.case_insensitive)
        self.spaces = QCheckBox("Metin içindeki boşlukları kaldır")
        self.spaces.setChecked(options.remove_internal_spaces)
        self.empty = QCheckBox("İki boş hücreyi eşleşmiş kabul et")
        self.empty.setChecked(options.empty_matches_empty)
        self.tolerance = QDoubleSpinBox()
        self.tolerance.setRange(0, 999_999_999)
        self.tolerance.setDecimals(6)
        self.tolerance.setValue(float(options.tolerance))
        self.date_tolerance = QSpinBox()
        self.date_tolerance.setRange(0, 31_536_000)
        self.date_tolerance.setSuffix(" saniye")
        self.date_tolerance.setValue(options.date_tolerance_seconds)
        form = QFormLayout(self)
        form.addRow(self.trim)
        form.addRow(self.case)
        form.addRow(self.spaces)
        form.addRow(self.empty)
        form.addRow("Sayısal tolerans:", self.tolerance)
        form.addRow("Tarih/saat toleransı:", self.date_tolerance)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def options(self, kind: ValueKind) -> NormalizationOptions:
        try:
            tolerance = Decimal(str(self.tolerance.value()))
        except InvalidOperation:
            tolerance = Decimal("0")
        return NormalizationOptions(
            kind=kind,
            trim=self.trim.isChecked(),
            case_insensitive=self.case.isChecked(),
            remove_internal_spaces=self.spaces.isChecked(),
            empty_matches_empty=self.empty.isChecked(),
            tolerance=tolerance,
            date_tolerance_seconds=self.date_tolerance.value(),
        )


class RuleRow(QFrame):
    remove_requested = Signal(object)
    changed = Signal()

    def __init__(
        self,
        left_columns: list[str],
        right_columns: list[str],
        rule: MatchRule | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.left = QComboBox()
        self.left.addItems(left_columns)
        self.operator = QComboBox()
        for label, value in OPERATOR_ITEMS:
            self.operator.addItem(label, value)
        self.right = QComboBox()
        self.right.addItems(right_columns)
        self.kind = QComboBox()
        for label, value in KIND_ITEMS:
            self.kind.addItem(label, value)
        self.primary = QCheckBox("Birincil")
        self.settings_button = QPushButton("Ayarlar")
        self.remove_button = QPushButton("Sil")
        self._options = NormalizationOptions()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        for widget, stretch in (
            (self.left, 3), (self.operator, 2), (self.right, 3),
            (self.kind, 2), (self.primary, 0), (self.settings_button, 0),
            (self.remove_button, 0),
        ):
            layout.addWidget(widget, stretch)

        self.settings_button.clicked.connect(self._edit_settings)
        self.remove_button.clicked.connect(lambda _checked=False: self.remove_requested.emit(self))
        for combo in (self.left, self.operator, self.right, self.kind):
            combo.currentIndexChanged.connect(lambda _index: self.changed.emit())
        self.primary.toggled.connect(lambda _checked: self.changed.emit())
        if rule:
            self.load_rule(rule)

    def load_rule(self, rule: MatchRule) -> None:
        self._select_text(self.left, rule.left_column)
        self._select_data(self.operator, rule.operator)
        self._select_text(self.right, rule.right_column)
        self._select_data(self.kind, rule.normalization.kind)
        self.primary.setChecked(rule.primary)
        self._options = rule.normalization

    def to_rule(self) -> MatchRule:
        options = NormalizationOptions(
            kind=ValueKind(self.kind.currentData()),
            trim=self._options.trim,
            case_insensitive=self._options.case_insensitive,
            remove_internal_spaces=self._options.remove_internal_spaces,
            empty_matches_empty=self._options.empty_matches_empty,
            tolerance=self._options.tolerance,
            date_tolerance_seconds=self._options.date_tolerance_seconds,
        )
        return MatchRule(
            self.left.currentText(), self.right.currentText(),
            MatchOperator(self.operator.currentData()), options, self.primary.isChecked()
        )

    def _edit_settings(self) -> None:
        dialog = NormalizationDialog(self._options, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._options = dialog.options(ValueKind(self.kind.currentData()))
            self.changed.emit()

    @staticmethod
    def _select_text(combo: QComboBox, value: str) -> None:
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _select_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class MatchingRulesWidget(QWidget):
    changed = Signal()
    save_template_requested = Signal()
    load_template_requested = Signal(str)
    delete_template_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.left_columns: list[str] = []
        self.right_columns: list[str] = []
        self.rows: list[RuleRow] = []
        self.logic = QComboBox()
        self.logic.addItem("VE — tüm kurallar sağlanmalı", LogicMode.AND)
        self.logic.addItem("VEYA — en az bir kural sağlanmalı", LogicMode.OR)
        self.duplicates = QComboBox()
        self.duplicates.addItem("Bire bir (önerilen)", DuplicateMode.ONE_TO_ONE)
        self.duplicates.addItem("Tüm uygun eşleşmeler", DuplicateMode.ALL_MATCHES)
        self.duplicates.addItem("Yalnız benzersiz eşleşmeler", DuplicateMode.UNIQUE_ONLY)
        self.template = QComboBox()
        self.template.setMinimumWidth(190)
        self.save_template = QPushButton("Şablonu Kaydet")
        self.load_template = QPushButton("Şablonu Yükle")
        self.delete_template = QPushButton("Sil")
        self.add_button = QPushButton("+ Yeni Eşleştirme Kuralı Ekle")

        top = QHBoxLayout()
        top.addWidget(QLabel("Mantık:"))
        top.addWidget(self.logic)
        top.addWidget(QLabel("Tekrarlar:"))
        top.addWidget(self.duplicates)
        top.addStretch()
        top.addWidget(QLabel("Şablon:"))
        top.addWidget(self.template)
        top.addWidget(self.load_template)
        top.addWidget(self.save_template)
        top.addWidget(self.delete_template)
        self.container = QWidget()
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(125)
        scroll.setMaximumHeight(230)
        scroll.setWidget(self.container)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(scroll)
        layout.addWidget(self.add_button)

        self.add_button.clicked.connect(self.add_rule)
        self.logic.currentIndexChanged.connect(lambda _index: self.changed.emit())
        self.duplicates.currentIndexChanged.connect(lambda _index: self.changed.emit())
        self.save_template.clicked.connect(lambda _checked=False: self.save_template_requested.emit())
        self.load_template.clicked.connect(
            lambda _checked=False: self.load_template_requested.emit(self.template.currentText())
        )
        self.delete_template.clicked.connect(
            lambda _checked=False: self.delete_template_requested.emit(self.template.currentText())
        )
        self._update_enabled()

    def set_columns(self, left: list[str], right: list[str]) -> None:
        self.left_columns = left
        self.right_columns = right
        for row in list(self.rows):
            self._remove_row(row, allow_empty=True)
        if left and right:
            self.add_rule(self._default_rule(left, right))
        self._update_enabled()

    def add_rule(self, rule: MatchRule | None = None) -> None:
        if not self.left_columns or not self.right_columns:
            return
        row = RuleRow(self.left_columns, self.right_columns, rule, self)
        row.remove_requested.connect(self._remove_row)
        row.changed.connect(self.changed.emit)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
        self.rows.append(row)
        self.changed.emit()

    def config(self) -> MultiMatchConfig:
        if not self.rows:
            raise ValueError("En az bir eşleştirme kuralı ekleyin.")
        return MultiMatchConfig(
            tuple(row.to_rule() for row in self.rows),
            LogicMode(self.logic.currentData()),
            DuplicateMode(self.duplicates.currentData()),
        )

    def load_config(self, config: MultiMatchConfig) -> None:
        for row in list(self.rows):
            self._remove_row(row, allow_empty=True)
        self._select_data(self.logic, config.logic)
        self._select_data(self.duplicates, config.duplicate_mode)
        for rule in config.rules:
            self.add_rule(rule)
        self.changed.emit()

    def set_template_names(self, names: list[str], selected: str = "") -> None:
        self.template.clear()
        self.template.addItems(names)
        index = self.template.findText(selected)
        if index >= 0:
            self.template.setCurrentIndex(index)

    def _remove_row(self, row: RuleRow, allow_empty: bool = False) -> None:
        if len(self.rows) <= 1 and not allow_empty:
            QMessageBox.information(self, "Kural Gerekli", "En az bir kural bulunmalıdır.")
            return
        if row in self.rows:
            self.rows.remove(row)
            self.rows_layout.removeWidget(row)
            row.deleteLater()
            self.changed.emit()

    def _update_enabled(self) -> None:
        enabled = bool(self.left_columns and self.right_columns)
        self.add_button.setEnabled(enabled)
        self.save_template.setEnabled(enabled)

    @staticmethod
    def _select_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _default_rule(left: list[str], right: list[str]) -> MatchRule:
        def best(columns: list[str]) -> str:
            for column in columns:
                if any(token in column.casefold() for token in ("plaka", "plate")):
                    return column
            return columns[0]
        return MatchRule(
            best(left), best(right), normalization=NormalizationOptions(kind=ValueKind.PLATE), primary=True
        )
