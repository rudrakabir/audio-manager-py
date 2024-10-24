import sqlite3
import threading
from datetime import datetime
import os  # Add this import here
import atexit  # Add this for cleanup

class Database:
    def __init__(self, db_path='transcriptions.db'):
        self.db_path = db_path
        self.mutex = threading.Lock()
        self.setup_database()
        
        # Register cleanup function
        atexit.register(self.cleanup)
    
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
        try:
            with self.mutex, sqlite3.connect(self.db_path) as conn:
                # Get file modification time
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                conn.execute('''
                    INSERT OR REPLACE INTO transcriptions 
                    (file_path, transcript, last_modified, status) 
                    VALUES (?, ?, ?, ?)
                ''', (file_path, transcript, mod_time, 'completed'))
                
                # Update search index
                conn.execute('DELETE FROM search_index WHERE file_path = ?', 
                           (file_path,))
                words = transcript.lower().split()
                conn.executemany('''
                    INSERT INTO search_index (file_path, word, position) 
                    VALUES (?, ?, ?)
                ''', [(file_path, word, pos) for pos, word in enumerate(words)])
                
                conn.commit()
        except Exception as e:
            print(f"Error adding transcription: {str(e)}")
            raise
    
    def get_transcription(self, file_path):
        try:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute('''
                    SELECT transcript FROM transcriptions 
                    WHERE file_path = ? AND status = 'completed'
                ''', (file_path,)).fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Error getting transcription: {str(e)}")
            return None

    def search_transcripts(self, query):
        try:
            with sqlite3.connect(self.db_path) as conn:
                return conn.execute('''
                    SELECT DISTINCT t.file_path, t.transcript 
                    FROM transcriptions t
                    JOIN search_index si ON t.file_path = si.file_path
                    WHERE si.word LIKE ? AND t.status = 'completed'
                    ORDER BY t.timestamp DESC
                ''', (f'%{query.lower()}%',)).fetchall()
        except Exception as e:
            print(f"Error searching transcripts: {str(e)}")
            return []
    
    def cleanup(self):
        """Cleanup resources on shutdown"""
        try:
            if hasattr(self, 'mutex'):
                self.mutex = None
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")