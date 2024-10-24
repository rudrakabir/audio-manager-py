MAIN_STYLE = """
    QMainWindow {
        background-color: #f5f5f5;
    }
    QTreeWidget {
        border: 1px solid #cccccc;
        border-radius: 8px;
        background-color: white;
        padding: 5px;
    }
    QTreeWidget::item {
        height: 25px;
        padding: 2px;
        margin: 2px;
    }
    QTreeWidget::item:selected {
        background-color: #e3f2fd;
        color: #1976d2;
        border-radius: 4px;
    }
    QPushButton {
        background-color: #1976d2;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: bold;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: #1565c0;
    }
    QPushButton:pressed {
        background-color: #0d47a1;
    }
    QPushButton:disabled {
        background-color: #bbdefb;
    }
    QTextEdit {
        border: 1px solid #cccccc;
        border-radius: 8px;
        background-color: white;
        padding: 8px;
    }
    QProgressBar {
        border: none;
        border-radius: 6px;
        background-color: #e0e0e0;
        text-align: center;
        color: black;
        height: 12px;
    }
    QProgressBar::chunk {
        background-color: #1976d2;
        border-radius: 6px;
    }
    QLineEdit {
        padding: 6px;
        border: 1px solid #cccccc;
        border-radius: 6px;
        background-color: white;
    }
    QSlider::groove:horizontal {
        border: none;
        height: 6px;
        background: #e0e0e0;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #1976d2;
        border: none;
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }
    QStatusBar {
        background-color: white;
        border-top: 1px solid #e0e0e0;
        padding: 4px;
        color: #666666;
    }
    QToolBar {
        background-color: white;
        border-bottom: 1px solid #e0e0e0;
        spacing: 10px;
        padding: 4px;
    }
"""