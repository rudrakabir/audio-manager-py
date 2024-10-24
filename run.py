import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from audio_manager.ui.main_window import MainWindow
from audio_manager.ui.styles import MAIN_STYLE

def main():
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(MAIN_STYLE)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()