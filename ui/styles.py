DARK_STYLE = """
QWidget {
    background-color: #1a1b26;
    color: #c0caf5;
    font-family: 'Ubuntu', 'Segoe UI', sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #24283b;
    background: #16161e;
    border-radius: 8px;
}
QTabBar::tab {
    background: #1f2335;
    color: #7aa2f7;
    padding: 8px 12px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #24283b;
    color: #7dcfff;
    font-weight: bold;
    border-bottom: 2px solid #7aa2f7;
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
QLineEdit, QComboBox, QSpinBox {
    background-color: #24283b;
    border: 1px solid #414868;
    border-radius: 4px;
    padding: 5px;
    color: #c0caf5;
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
    border-radius: 4px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3b4261;
    border-color: #7aa2f7;
}
QPushButton#startBtn {
    background-color: #9ece6a;
    color: #15161e;
    font-weight: bold;
    border: none;
}
QPushButton#stopBtn {
    background-color: #f7768e;
    color: #15161e;
    font-weight: bold;
    border: none;
}
"""
