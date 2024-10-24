from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit,
                           QLabel, QFileDialog, QProgressBar, QSplitter, 
                           QMessageBox, QMenu, QSlider, QLineEdit, QToolBar,
                           QStatusBar)
from PyQt6.QtCore import Qt, QTimer, QFileSystemWatcher, QSettings, QThread
from PyQt6.QtGui import QAction
from datetime import timedelta
from pathlib import Path
import whisper
import os

# Change relative imports to absolute imports
from audio_manager.database import Database
from audio_manager.audio_player import AudioPlayer
from audio_manager.transcription import TranscriptionWorker
from audio_manager.utils.file_utils import get_audio_files

def main():
    # Enable high DPI scaling
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