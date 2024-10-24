from datetime import datetime
from pathlib import Path

def parse_audio_filename(filename):
    """Parse filename in format YYMMDD_HHMM"""
    try:
        date_str = filename[:6]
        time_str = filename[7:11]
        
        year = f"20{date_str[:2]}"
        month = date_str[2:4]
        day = date_str[4:6]
        hour = time_str[:2]
        minute = time_str[2:4]
        
        return datetime(int(year), int(month), int(day), 
                       int(hour), int(minute))
    except (ValueError, IndexError):
        return None

def get_audio_files(directory):
    """Get list of audio files with timestamps"""
    files = []
    for file in Path(directory).glob('*.mp3'):
        timestamp = parse_audio_filename(file.stem)
        if timestamp:
            files.append({
                'path': str(file),
                'filename': file.name,
                'timestamp': timestamp
            })
    
    return sorted(files, key=lambda x: x['timestamp'], reverse=True)