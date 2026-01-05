#!/usr/bin/env python
"""Clear all documents from database"""

from app.db.storage_manager import StorageManager
from app.db.models import Document, Chunk, Embedding, Session

db_manager = StorageManager()

try:
    # Delete all embeddings
    embeddings = db_manager.db.query(Embedding).all()
    for emb in embeddings:
        db_manager.db.delete(emb)
    print(f"[✓] Deleted {len(embeddings)} embeddings")
    
    # Delete all chunks
    chunks = db_manager.db.query(Chunk).all()
    for chunk in chunks:
        db_manager.db.delete(chunk)
    print(f"[✓] Deleted {len(chunks)} chunks")
    
    # Delete all documents
    docs = db_manager.db.query(Document).all()
    for doc in docs:
        db_manager.db.delete(doc)
    print(f"[✓] Deleted {len(docs)} documents")
    
    # Delete all sessions
    sessions = db_manager.db.query(Session).all()
    for session in sessions:
        db_manager.db.delete(session)
    print(f"[✓] Deleted {len(sessions)} sessions")
    
    db_manager.db.commit()
    print("[✓] Database cleared successfully!")
    
except Exception as e:
    db_manager.db.rollback()
    print(f"[!] Error: {e}")
    import traceback
    traceback.print_exc()
