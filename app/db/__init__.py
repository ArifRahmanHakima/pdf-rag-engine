"""
Database package
PostgreSQL + Qdrant storage management
"""

from app.db.models import Session, Document, Chunk, Embedding, init_db, get_db, engine, SessionLocal
from app.db.qdrant_manager import qdrant_manager
from app.db.storage_manager import storage_manager
from app.config.db_config import postgres_config, qdrant_config

__all__ = [
    # Models
    'Session',
    'Document', 
    'Chunk',
    'Embedding',
    
    # Managers
    'storage_manager',
    'qdrant_manager',
    
    # Config
    'postgres_config',
    'qdrant_config',
    
    # DB functions
    'init_db',
    'get_db',
    'engine',
    'SessionLocal',
]
