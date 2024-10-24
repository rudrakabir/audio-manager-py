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

from audio_manager.database import Database
from audio_manager.audio_player import AudioPlayer
from audio_manager.transcription import TranscriptionWorker
from audio_manager.utils.file_utils import get_audio_files

class MainWindow(QMainWindow):
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
        self.position_timer.start(100)
        
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
    
    # UI Event Handlers
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
    
    # UI Setup
    def setup_ui(self):
        """Setup the user interface"""
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
        self.seek_slider.setMaximum(1000)
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

    # ... (rest of the methods remain the same)

    # Audio Control Methods
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
        self.audio_player.set_volume(value / 100.0)

    def format_time(self, seconds):
        """Convert seconds to MM:SS format"""
        return str(timedelta(seconds=int(seconds)))[2:7]

    def update_position(self):
        """Update time label and slider position"""
        if self.audio_player.current_file:
            position = self.audio_player.get_position()
            duration = self.audio_player.get_duration()
            
            position_str = self.format_time(position)
            duration_str = self.format_time(duration)
            self.time_label.setText(f"{position_str} / {duration_str}")
            
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

    # File Management Methods
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
        audio_files = get_audio_files(self.directory)
        
        # Build tree structure
        year_items = {}
        month_items = {}
        day_items = {}
        
        for file in audio_files:
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

    # Transcription Methods
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

    # Search Methods
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

    # Model and Settings Methods
    def load_model(self):
        """Load the Whisper model"""
        self.model = whisper.load_model("base")

    def on_model_loaded(self):
        """Handle model loading completion"""
        self.statusBar().showMessage("Ready", 3000)

    def restore_settings(self):
        """Restore last used directory"""
        last_dir = self.settings.value('last_directory')
        if last_dir and os.path.exists(last_dir):
            self.directory = last_dir
            self.file_watcher.addPath(last_dir)
            self.refresh_files()

    # Event Handlers
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
        if self.audio_player:
            if self.is_playing:
                self.stop_audio()
            self.audio_player.cleanup()
        
        # Save settings
        self.settings.sync()
        event.accept()