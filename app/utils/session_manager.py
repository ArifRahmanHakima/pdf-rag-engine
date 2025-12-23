"""
Session management utilities - helper functions for session management
"""

import json
from pathlib import Path


def get_next_session_id(sessions_dir: Path) -> str:
    """Generate next session ID by incrementing folder_N format"""
    sessions_dir.mkdir(parents=True, exist_ok=True)
    existing = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not existing:
        return "folder_1"
    
    numbers = []
    for d in existing:
        try:
            num = int(d.name.split("_")[1])
            numbers.append(num)
        except:
            pass
    
    return f"folder_{max(numbers) + 1 if numbers else 1}"


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
