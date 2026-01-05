"""
Session management utilities - helper functions for session management
"""

import json
from pathlib import Path
from datetime import datetime, timedelta


def get_next_session_id(sessions_dir: Path) -> str:
    """
    Get session ID - reuse existing session if created recently (< 5 mins)
    Otherwise create new session with incremented folder_N format
    """
    sessions_dir.mkdir(parents=True, exist_ok=True)
    existing = [d for d in sessions_dir.iterdir() if d.is_dir()]
    
    if not existing:
        return "folder_1"
    
    # Get metadata from most recent session to check timestamp
    most_recent = None
    most_recent_time = None
    
    for d in existing:
        try:
            metadata_file = d / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    if "created_at" in metadata:
                        created_at = datetime.fromisoformat(metadata["created_at"])
                        if most_recent_time is None or created_at > most_recent_time:
                            most_recent = d.name
                            most_recent_time = created_at
        except:
            pass
    
    # If most recent session created less than 5 minutes ago, reuse it
    if most_recent_time:
        time_diff = datetime.now() - most_recent_time
        if time_diff < timedelta(minutes=5):
            print(f"[*] Reusing recent session: {most_recent} (created {time_diff.total_seconds():.0f}s ago)")
            return most_recent
    
    # Otherwise create new session
    numbers = []
    for d in existing:
        try:
            num = int(d.name.split("_")[1])
            numbers.append(num)
        except:
            pass
    
    new_session = f"folder_{max(numbers) + 1 if numbers else 1}"
    print(f"[*] Creating new session: {new_session}")
    return new_session


def get_session_metadata(session_id: str, sessions_dir: Path) -> dict:
    """Load session metadata from JSON file"""
    metadata_file = sessions_dir / session_id / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, encoding='utf-8') as f:
            return json.load(f)
    return None


def save_session_metadata(session_id: str, metadata: dict, sessions_dir: Path):
    """Save session metadata to JSON file"""
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    with open(session_dir / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
