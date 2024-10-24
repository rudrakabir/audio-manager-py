import soundfile as sf
import sounddevice as sd
import numpy as np
import threading
import atexit
from typing import Tuple, Optional

class AudioPlayer:
    def __init__(self):
        """Initialize the audio player with necessary components."""
        # State variables
        self.current_file: Optional[str] = None
        self.data: Optional[np.ndarray] = None
        self.samplerate: Optional[int] = None
        self.position: int = 0
        self.playing: bool = False
        self.volume: float = 1.0
        
        # Threading
        self.lock = threading.Lock()
        
        # Initialize audio stream
        try:
            self.stream = sd.OutputStream(
                channels=2,
                callback=self.callback,
                finished_callback=self.finished_callback
            )
            self.stream.start()
        except Exception as e:
            print(f"Error initializing audio stream: {str(e)}")
            self.stream = None
        
        # Register cleanup
        atexit.register(self.cleanup)
    
    def load_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Load an audio file for playback.
        
        Args:
            file_path (str): Path to the audio file
            
        Returns:
            Tuple[bool, str]: (Success status, Error message if any)
        """
        with self.lock:
            try:
                # Load the audio file
                self.data, self.samplerate = sf.read(file_path)
                
                # Convert mono to stereo if needed
                if len(self.data.shape) == 1:
                    self.data = np.column_stack((self.data, self.data))
                
                self.current_file = file_path
                self.position = 0
                return True, ""
            except Exception as e:
                self.data = None
                self.samplerate = None
                self.current_file = None
                self.position = 0
                return False, str(e)
    
    def play(self):
        """Start or resume playback."""
        with self.lock:
            if self.data is not None:
                self.playing = True
    
    def pause(self):
        """Pause playback."""
        with self.lock:
            self.playing = False
    
    def stop(self):
        """Stop playback and reset position."""
        with self.lock:
            self.playing = False
            self.position = 0
    
    def seek(self, position_seconds: float):
        """
        Seek to a specific position in the audio file.
        
        Args:
            position_seconds (float): Position in seconds to seek to
        """
        with self.lock:
            if self.data is not None and self.samplerate is not None:
                self.position = int(position_seconds * self.samplerate)
                self.position = min(self.position, len(self.data))
    
    def get_position(self) -> float:
        """
        Get current playback position in seconds.
        
        Returns:
            float: Current position in seconds
        """
        with self.lock:
            if self.samplerate is not None:
                return self.position / self.samplerate
            return 0
    
    def get_duration(self) -> float:
        """
        Get total duration of loaded audio in seconds.
        
        Returns:
            float: Duration in seconds
        """
        with self.lock:
            if self.data is not None and self.samplerate is not None:
                return len(self.data) / self.samplerate
            return 0
    
    def set_volume(self, volume: float):
        """
        Set playback volume.
        
        Args:
            volume (float): Volume level between 0 and 1
        """
        with self.lock:
            self.volume = max(0.0, min(1.0, volume))
    
    def callback(self, outdata: np.ndarray, frames: int, 
                time: float, status: sd.CallbackFlags):
        """
        Audio stream callback function.
        
        Args:
            outdata (np.ndarray): Output buffer to fill with audio data
            frames (int): Number of frames to process
            time (float): Timestamp
            status (sd.CallbackFlags): Status flags
        """
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
            
            # Apply volume and write to output buffer
            output_data = self.data[self.position:self.position + valid_frames] * self.volume
            outdata[:valid_frames] = output_data
            
            if valid_frames < frames:
                outdata[valid_frames:] = 0
            
            self.position += valid_frames
    
    def finished_callback(self):
        """Handle playback completion."""
        with self.lock:
            self.playing = False
            self.position = 0
    
    def cleanup(self):
        """Clean up resources when the player is shut down."""
        try:
            if hasattr(self, 'stream') and self.stream is not None:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            if hasattr(self, 'lock'):
                self.lock = None
            
            # Clear audio data
            self.data = None
            self.samplerate = None
            self.current_file = None
            self.position = 0
            self.playing = False
        except Exception as e:
            print(f"Error during audio player cleanup: {str(e)}")

    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.
        
        Returns:
            bool: True if audio is playing, False otherwise
        """
        with self.lock:
            return self.playing
    
    def get_current_file(self) -> Optional[str]:
        """
        Get the path of currently loaded audio file.
        
        Returns:
            Optional[str]: Path to current audio file or None if no file is loaded
        """
        with self.lock:
            return self.current_file