#!/usr/bin/env python3
"""
FULL SYSTEM RESET - Database Only
Deletes ALL data from PostgreSQL and Qdrant
Does NOT touch rag_storage (will be cleaned up separately)
"""

import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.database_service import get_database_service
from app.db.models import SessionLocal, Session, Document, Chunk, Embedding

print("\n[*] FULL SYSTEM RESET - PostgreSQL & Qdrant")
print("=" * 70)

db_service = get_database_service()
session = SessionLocal()

try:
    # Get counts BEFORE deletion
    session_count = session.query(Session).count()
    doc_count = session.query(Document).count()
    chunk_count = session.query(Chunk).count()
    embedding_count = session.query(Embedding).count()
    
    print(f"\n[*] Current state:")
    print(f"    Sessions: {session_count}")
    print(f"    Documents: {doc_count}")
    print(f"    Chunks: {chunk_count}")
    print(f"    Embeddings: {embedding_count}")
    
    # Delete all
    print(f"\n[*] Deleting all embeddings...")
    session.query(Embedding).delete()
    
    print(f"[*] Deleting all chunks...")
    session.query(Chunk).delete()
    
    print(f"[*] Deleting all documents...")
    session.query(Document).delete()
    
    print(f"[*] Deleting all sessions...")
    session.query(Session).delete()
    
    session.commit()
    print(f"[✓] PostgreSQL cleaned!")
    
    # Clean Qdrant
    print(f"\n[*] Cleaning Qdrant vectors...")
    try:
        # Delete all points from chunks collection
        qdrant_client = db_service.qdrant_client
        qdrant_client.delete(
            collection_name="chunks",
            points_selector={"filter": {"must": []}},  # Delete ALL
        )
        print(f"[✓] Qdrant chunks collection cleaned!")
    except Exception as e:
        print(f"[!] Qdrant cleanup error: {e}")
    
    print(f"\n[✓] FULL RESET COMPLETE")
    print(f"[*] Ready for fresh start!")
    
except Exception as e:
    print(f"[!] Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
