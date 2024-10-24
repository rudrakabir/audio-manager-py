from PyQt6.QtCore import QThread, pyqtSignal
import whisper

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