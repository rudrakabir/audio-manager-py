import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, 
                           QTextEdit, QLabel, QFileDialog, QProgressBar, 
                           QSplitter, QMessageBox, QMenu, QSlider, QLineEdit,
                           QToolBar, QStatusBar)
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QSettings, QSize, QTimer,
                         QFileSystemWatcher, QMutex)
from PyQt6.QtGui import QAction, QFont, QKeySequence
import soundfile as sf
import sounddevice as sd
import numpy as np
import pygame
import whisper
import os
from datetime import datetime, timedelta
import json
import sqlite3
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor

class Database:
    def __init__(self, db_path='transcriptions.db'):
        self.db_path = db_path
        self.mutex = threading.Lock()
        self.setup_database()
    
    def setup_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transcriptions (
                    file_path TEXT PRIMARY KEY,
                    transcript TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_modified DATETIME,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_index (
                    file_path TEXT,
                    word TEXT,
                    position INTEGER,
                    FOREIGN KEY(file_path) REFERENCES transcriptions(file_path)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_word ON search_index(word)')
    
    def add_transcription(self, file_path, transcript):
        with self.mutex, sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO transcriptions 
                (file_path, transcript, last_modified, status) 
                VALUES (?, ?, ?, ?)
            ''', (file_path, transcript, 
                  datetime.fromtimestamp(os.path.getmtime(file_path)),
                  'completed'))
            
            # Update search index
            conn.execute('DELETE FROM search_index WHERE file_path = ?', 
                       (file_path,))
            words = transcript.lower().split()
            conn.executemany('''
                INSERT INTO search_index (file_path, word, position) 
                VALUES (?, ?, ?)
            ''', [(file_path, word, pos) for pos, word in enumerate(words)])
    
    def get_transcription(self, file_path):
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute('''
                SELECT transcript FROM transcriptions 
                WHERE file_path = ? AND status = 'completed'
            ''', (file_path,)).fetchone()
            return result[0] if result else None

    def search_transcripts(self, query):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute('''
                SELECT DISTINCT t.file_path, t.transcript 
                FROM transcriptions t
                JOIN search_index si ON t.file_path = si.file_path
                WHERE si.word LIKE ? AND t.status = 'completed'
                ORDER BY t.timestamp DESC
            ''', (f'%{query.lower()}%',)).fetchall()

class AudioPlayer:
    def __init__(self):
        self.current_file = None
        self.data = None
        self.samplerate = None
        self.position = 0
        self.playing = False
        self.stream = None
        self.lock = threading.Lock()
        
        # Create a stream with callback
        self.stream = sd.OutputStream(
            channels=2,
            callback=self.callback,
            finished_callback=self.finished_callback
        )
        self.stream.start()
    
    def load_file(self, file_path):
        with self.lock:
            try:
                self.data, self.samplerate = sf.read(file_path)
                if len(self.data.shape) == 1:  # Mono
                    self.data = np.column_stack((self.data, self.data))
                self.current_file = file_path
                self.position = 0
                return True, ""
            except Exception as e:
                return False, str(e)
    
    def play(self):
        with self.lock:
            self.playing = True
    
    def pause(self):
        with self.lock:
            self.playing = False
    
    def stop(self):
        with self.lock:
            self.playing = False
            self.position = 0
    
    def seek(self, position_seconds):
        with self.lock:
            if self.data is not None and self.samplerate is not None:
                self.position = int(position_seconds * self.samplerate)
                self.position = min(self.position, len(self.data))
    
    def get_position(self):
        with self.lock:
            if self.samplerate is not None:
                return self.position / self.samplerate
            return 0
    
    def get_duration(self):
        with self.lock:
            if self.data is not None and self.samplerate is not None:
                return len(self.data) / self.samplerate
            return 0
    
    def callback(self, outdata, frames, time, status):
        with self.lock:
            if self.data is None or not self.playing:
                outdata.fill(0)
                return
            
            if self.position >= len(self.data):
                self.playing = False
                outdata.fill(0)
                return
            
            # Calculate how many frames we can write
            remaining = len(self.data) - self.position
            valid_frames = min(frames, remaining)
            outdata[:valid_frames] = self.data[self.position:self.position + valid_frames]
            
            if valid_frames < frames:
                outdata[valid_frames:] = 0
            
            self.position += valid_frames
    
    def finished_callback(self):
        with self.lock:
            self.playing = False
            self.position = 0

class TranscriptionWorker(QThread):
    finished = pyqtSignal(str, str)  # file_path, transcript
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, model, file_path):
        super().__init__()
        self.model = model
        self.file_path = file_path

    def run(self):
        try:
            # Emit initial progress
            self.progress.emit(10)
            
            # Load audio
            self.progress.emit(30)
            
            # Perform transcription
            result = self.model.transcribe(self.file_path)
            
            # Complete
            self.progress.emit(100)
            
            self.finished.emit(self.file_path, result["text"])
        except Exception as e:
            self.error.emit(str(e))

class AudioManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Manager Pro")
        self.resize(1200, 800)
        
        # Initialize components
        self.settings = QSettings('AudioManager', 'AudioManagerPro')
        self.db = Database()
        self.audio_player = AudioPlayer()
        
        # State tracking
        self.current_audio = None
        self.is_playing = False
        self.directory = None
        self.current_transcription = None
        
        # Setup UI first
        self.setup_ui()
        
        # File watcher setup
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self.refresh_files)
        
        # Add position update timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.start(100)  # Update every 100ms
        
        # Load whisper model
        self.statusBar().showMessage("Loading Whisper model...")
        self.load_model_thread = QThread()
        self.load_model_thread.run = self.load_model
        self.load_model_thread.finished.connect(self.on_model_loaded)
        self.load_model_thread.start()
        
        # Restore previous session
        self.restore_settings()
        
        # Setup auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_files)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds

    def setup_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # Add folder selection action
        select_folder_action = QAction("Select Folder", self)
        select_folder_action.triggered.connect(self.select_directory)
        toolbar.addAction(select_folder_action)
        
        # Add search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search transcriptions...")
        self.search_bar.textChanged.connect(self.search_transcripts)
        toolbar.addWidget(self.search_bar)
        
        # Create splitter for main content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel (file tree)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Files", "Time"])
        self.tree.itemClicked.connect(self.on_item_selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        left_layout.addWidget(self.tree)
        
        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Audio controls
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_audio)
        controls_layout.addWidget(self.play_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_audio)
        controls_layout.addWidget(self.stop_button)
        
        # Add time labels and seeking slider
        self.time_label = QLabel("0:00 / 0:00")
        controls_layout.addWidget(self.time_label)
        
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setMaximum(1000)  # We'll convert to/from time
        self.seek_slider.sliderMoved.connect(self.seek_audio)
        self.seek_slider.sliderPressed.connect(self.slider_pressed)
        self.seek_slider.sliderReleased.connect(self.slider_released)
        controls_layout.addWidget(self.seek_slider)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_label = QLabel("Volume:")
        volume_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout.addWidget(self.volume_slider)
        controls_layout.addLayout(volume_layout)
        
        right_layout.addWidget(controls)
        
        # Transcription section
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.clicked.connect(self.transcribe_audio)
        right_layout.addWidget(self.transcribe_button)
        
        self.progress = QProgressBar()
        self.progress.hide()
        right_layout.addWidget(self.progress)
        
        self.transcription_text = QTextEdit()
        self.transcription_text.setReadOnly(True)
        right_layout.addWidget(self.transcription_text)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def play_audio(self):
        """Play or pause audio"""
        if not self.audio_player.current_file:
            item = self.tree.currentItem()
            if not item:
                return
            
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            if not file_path:
                return
            
            success, error = self.audio_player.load_file(file_path)
            if not success:
                QMessageBox.critical(self, "Error", f"Could not load audio file: {error}")
                return
        
        if self.audio_player.playing:
            self.audio_player.pause()
            self.play_button.setText("Play")
        else:
            self.audio_player.play()
            self.play_button.setText("Pause")
    
    def stop_audio(self):
        """Stop audio playback"""
        self.audio_player.stop()
        self.play_button.setText("Play")
    
    def set_volume(self, value):
        """Set audio volume"""
        sd.default.output_gain = value / 100.0

    def format_time(self, seconds):
        """Convert seconds to MM:SS format"""
        return str(timedelta(seconds=int(seconds)))[2:7]

    def update_position(self):
        """Update time label and slider position"""
        if self.audio_player.current_file:
            position = self.audio_player.get_position()
            duration = self.audio_player.get_duration()
            
            # Update time label
            position_str = self.format_time(position)
            duration_str = self.format_time(duration)
            self.time_label.setText(f"{position_str} / {duration_str}")
            
            # Update slider if it's not being dragged
            if not self.seek_slider.isSliderDown():
                self.seek_slider.setValue(int(position * 1000 / duration) if duration else 0)

    def slider_pressed(self):
        """Called when user starts dragging the slider"""
        self.position_timer.stop()

    def slider_released(self):
        """Called when user releases the slider"""
        self.position_timer.start()

    def seek_audio(self, value):
        """Seek to position in audio file"""
        if self.audio_player.current_file:
            duration = self.audio_player.get_duration()
            position = (value / 1000) * duration
            self.audio_player.seek(position)

    def select_directory(self):
        """Open directory selection dialog"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Audio Files Directory",
            self.directory or str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.directory = directory
            self.settings.setValue('last_directory', directory)
            if self.directory in self.file_watcher.directories():
                self.file_watcher.removePath(self.directory)
            self.file_watcher.addPath(directory)
            self.refresh_files()
    
    def refresh_files(self):
        """Refresh the file tree with audio files"""
        if not self.directory:
            return
        
        self.tree.clear()
        files = []
        
        for file in Path(self.directory).glob('*.mp3'):
            try:
                # Parse filename (format: YYMMDD_HHMM)
                date_str = file.stem[:6]
                time_str = file.stem[7:11]
                
                year = f"20{date_str[:2]}"
                month = date_str[2:4]
                day = date_str[4:6]
                hour = time_str[:2]
                minute = time_str[2:4]
                
                timestamp = datetime(int(year), int(month), int(day), 
                                  int(hour), int(minute))
                
                files.append({
                    'path': str(file),
                    'filename': file.name,
                    'timestamp': timestamp
                })
            except (ValueError, IndexError):
                continue
        
        # Sort files by timestamp
        files.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Build tree
        year_items = {}
        month_items = {}
        day_items = {}
        
        for file in files:
            timestamp = file['timestamp']
            
            # Create year node if needed
            year = str(timestamp.year)
            if year not in year_items:
                year_item = QTreeWidgetItem(self.tree, [year])
                year_items[year] = year_item
                year_item.setExpanded(True)
            
            # Create month node if needed
            month = timestamp.strftime('%B')
            month_key = f"{year}-{month}"
            if month_key not in month_items:
                month_item = QTreeWidgetItem(year_items[year], [month])
                month_items[month_key] = month_item
                month_item.setExpanded(True)
            
            # Create day node if needed
            day = str(timestamp.day)
            day_key = f"{month_key}-{day}"
            if day_key not in day_items:
                day_item = QTreeWidgetItem(month_items[month_key], [day])
                day_items[day_key] = day_item
                day_item.setExpanded(True)
            
            # Add file entry
            item = QTreeWidgetItem(day_items[day_key],
                                 [file['filename'],
                                  timestamp.strftime('%H:%M')])
            item.setData(0, Qt.ItemDataRole.UserRole, file['path'])
            
            # Check if transcription exists
            if self.db.get_transcription(file['path']):
                item.setForeground(0, Qt.GlobalColor.blue)
    
    def show_context_menu(self, position):
        """Show context menu for tree items"""
        item = self.tree.itemAt(position)
        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            return
        
        menu = QMenu()
        transcribe_action = menu.addAction("Transcribe")
        save_action = menu.addAction("Save Transcription")
        
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        if action == transcribe_action:
            self.transcribe_audio()
        elif action == save_action:
            self.save_transcription()
    
    def on_item_selected(self, item):
        """Handle tree item selection"""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        # Load existing transcription if available
        transcript = self.db.get_transcription(file_path)
        if transcript:
            self.transcription_text.setText(transcript)
        else:
            self.transcription_text.clear()
    
    def transcribe_audio(self):
        """Transcribe selected audio file"""
        item = self.tree.currentItem()
        if not item:
            return
        
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        self.transcribe_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.transcription_text.setText("Transcribing... This may take a few minutes.")
        
        self.current_transcription = TranscriptionWorker(self.model, file_path)
        self.current_transcription.finished.connect(self.on_transcription_complete)
        self.current_transcription.error.connect(self.on_transcription_error)
        self.current_transcription.progress.connect(self.progress.setValue)
        self.current_transcription.start()
    
    def on_transcription_complete(self, file_path, transcript):
        """Handle completed transcription"""
        self.transcription_text.setText(transcript)
        self.db.add_transcription(file_path, transcript)
        self.progress.hide()
        self.transcribe_button.setEnabled(True)
        self.statusBar().showMessage("Transcription completed", 3000)
        self.refresh_files()
    
    def on_transcription_error(self, error):
        """Handle transcription error"""
        self.transcription_text.setText(f"Error during transcription: {error}")
        self.progress.hide()
        self.transcribe_button.setEnabled(True)
        self.statusBar().showMessage("Transcription failed", 3000)
    
    def save_transcription(self):
        """Save transcription to file"""
        item = self.tree.currentItem()
        if not item:
            return
        
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        transcript = self.db.get_transcription(file_path)
        if not transcript:
            QMessageBox.warning(self, "No Transcription", 
                              "No transcription available for this file.")
            return
        
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Transcription",
            os.path.splitext(file_path)[0] + ".txt",
            "Text Files (*.txt)"
        )
        
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(transcript)
                self.statusBar().showMessage("Transcription saved successfully", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                   f"Could not save transcription: {str(e)}")
    
    def search_transcripts(self, query):
        """Search through transcriptions"""
        if len(query) < 3:  # Only search for queries with 3+ characters
            self.refresh_files()
            return
        
        results = self.db.search_transcripts(query)
        self.tree.clear()
        
        for file_path, transcript in results:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, os.path.basename(file_path))
            item.setText(1, transcript[:100] + "...")  # Show preview
            item.setData(0, Qt.ItemDataRole.UserRole, file_path)
            item.setForeground(0, Qt.GlobalColor.blue)
    
    def restore_settings(self):
        """Restore last used directory"""
        last_dir = self.settings.value('last_directory')
        if last_dir and os.path.exists(last_dir):
            self.directory = last_dir
            self.file_watcher.addPath(last_dir)
            self.refresh_files()
    
    def load_model(self):
        """Load the Whisper model"""
        self.model = whisper.load_model("base")
    
    def on_model_loaded(self):
        """Handle model loading completion"""
        self.statusBar().showMessage("Ready", 3000)
    
    def closeEvent(self, event):
        """Handle application closure"""
        if self.current_transcription and self.current_transcription.isRunning():
            reply = QMessageBox.question(
                self, 
                "Transcription in Progress",
                "A transcription is currently in progress. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        # Stop audio if playing
        if self.is_playing:
            self.stop_audio()
        
        if hasattr(self, 'audio_player') and hasattr(self.audio_player, 'stream'):
            self.audio_player.stream.stop()
            self.audio_player.stream.close()
        
        # Save settings
        self.settings.sync()
        event.accept()

def main():
    # Enable high DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set up stylesheet for modern look
    app.setStyleSheet("""
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
    """)
    
    window = AudioManager()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()