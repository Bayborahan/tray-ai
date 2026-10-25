DARK_STYLE = """
QWidget {
    background-color: #1a1b26;
    color: #c0caf5;
    font-family: 'Ubuntu', 'Segoe UI', sans-serif;
    font-size: 13px;
}
QToolTip {
    background-color: #1f2335;
    color: #c0caf5;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}
QTabWidget::pane {
    border: 1px solid #24283b;
    background: #16161e;
    border-radius: 8px;
}
QTabBar::tab {
    background: #1f2335;
    color: #7aa2f7;
    padding: 8px 14px;
    margin-right: 3px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: #24283b;
    color: #7dcfff;
    font-weight: bold;
    border-bottom: 2px solid #7aa2f7;
}
QTabBar::tab:hover:!selected {
    background: #292e42;
    color: #c0caf5;
}

/* Modern Kart Şeklinde QGroupBox */
QGroupBox {
    background-color: #1a1e2d;
    border: 1px solid #292e42;
    border-left: 3px solid #7aa2f7;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 2px;
    padding: 2px 8px;
    color: #7dcfff;
    font-size: 11px;
    font-weight: bold;
    background-color: #16161e;
    border: 1px solid #3b4261;
    border-radius: 4px;
}

QListWidget {
    background-color: #1f2335;
    border: 1px solid #292e42;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    background-color: #24283b;
    border-radius: 6px;
    margin-bottom: 5px;
    padding: 0px;
}
QListWidget::item:selected {
    background-color: #3b4261;
    border: 1px solid #7aa2f7;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #24283b;
    border: 1px solid #414868;
    border-radius: 6px;
    padding: 5px 8px;
    color: #c0caf5;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #7aa2f7;
    background-color: #1f2335;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #24283b;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #7aa2f7;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #bb9af7;
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QPushButton {
    background-color: #24283b;
    border: 1px solid #414868;
    color: #c0caf5;
    padding: 6px 12px;
    border-radius: 6px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3b4261;
    border-color: #7aa2f7;
}

/* Minimalist Koyu Tema Kaydırma Çubuğu (Scrollbar) */
QScrollBar:vertical {
    border: none;
    background: #16161e;
    width: 6px;
    border-radius: 3px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #3b4261;
    min-height: 25px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #7aa2f7;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: #16161e;
    height: 6px;
    border-radius: 3px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #3b4261;
    min-width: 25px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: #7aa2f7;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""
