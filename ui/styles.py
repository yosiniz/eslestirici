"""Uygulamanın sade ve modern Qt stil tanımları."""

APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #F4F7FB;
    color: #1F2937;
}
QLabel#titleLabel {
    color: #17365D;
    font-size: 24px;
    font-weight: 700;
}
QLabel#subtitleLabel {
    color: #64748B;
    font-size: 11px;
}
QFrame#card, QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #DCE3EC;
    border-radius: 8px;
}
QGroupBox {
    font-weight: 600;
    padding-top: 18px;
    margin-top: 9px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #17365D;
}
QPushButton {
    min-height: 34px;
    padding: 0 14px;
    border-radius: 6px;
    border: 1px solid #B9C6D6;
    background-color: #FFFFFF;
    color: #17365D;
    font-weight: 600;
}
QPushButton:hover { background-color: #EEF4FA; }
QPushButton:pressed { background-color: #DFEAF5; }
QPushButton:disabled { color: #94A3B8; background-color: #F1F5F9; }
QPushButton#primaryButton {
    background-color: #1F5A94;
    color: #FFFFFF;
    border-color: #1F5A94;
}
QPushButton#primaryButton:hover { background-color: #174A7A; }
QPushButton#successButton {
    background-color: #176B4D;
    color: #FFFFFF;
    border-color: #176B4D;
}
QPushButton#successButton:hover { background-color: #12573E; }
QComboBox, QLineEdit {
    min-height: 34px;
    border: 1px solid #C7D2DF;
    border-radius: 6px;
    background-color: #FFFFFF;
    padding: 0 9px;
    selection-background-color: #CFE1F3;
}
QComboBox:focus, QLineEdit:focus { border-color: #1F5A94; }
QTableView {
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #DCE3EC;
    border-radius: 6px;
    gridline-color: #E8EDF3;
    selection-background-color: #CFE1F3;
    selection-color: #172033;
}
QHeaderView::section {
    background-color: #17365D;
    color: #FFFFFF;
    border: 0;
    border-right: 1px solid #315477;
    padding: 8px;
    font-weight: 600;
}
QProgressBar {
    min-height: 14px;
    max-height: 14px;
    border: 1px solid #C7D2DF;
    border-radius: 7px;
    background: #EAF0F6;
    text-align: center;
}
QProgressBar::chunk { background-color: #1F5A94; border-radius: 6px; }
QStatusBar { background-color: #FFFFFF; border-top: 1px solid #DCE3EC; }
QCheckBox, QRadioButton { spacing: 7px; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
QLabel#pathLabel {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 5px;
    color: #475569;
    padding: 8px;
}
QLabel#metricValue { color: #17365D; font-size: 18px; font-weight: 700; }
QLabel#metricName { color: #64748B; font-size: 10px; }
"""
