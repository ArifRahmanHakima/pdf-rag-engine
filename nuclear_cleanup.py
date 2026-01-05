#!/usr/bin/env python
"""Complete database and Qdrant cleanup"""

from app.db.storage_manager import StorageManager
from app.db.models import Session, Document, Chunk, Embedding
from qdrant_client import QdrantClient
from qdrant_client.http import models

print("\n" + "="*70)
print("COMPLETE DATABASE CLEANUP - NUCLEAR OPTION")
print("="*70)

# PostgreSQL cleanup
print("\n[PostgreSQL Cleanup]")
db_manager = StorageManager()

try:
    # Delete in order of dependencies
    print("  Deleting embeddings...", end='', flush=True)
    embeddings = db_manager.db.query(Embedding).all()
    for emb in embeddings:
        db_manager.db.delete(emb)
    print(f" ({len(embeddings)} deleted)")
    
    print("  Deleting chunks...", end='', flush=True)
    chunks = db_manager.db.query(Chunk).all()
    for chunk in chunks:
        db_manager.db.delete(chunk)
    print(f" ({len(chunks)} deleted)")
    
    print("  Deleting documents...", end='', flush=True)
    docs = db_manager.db.query(Document).all()
    for doc in docs:
        db_manager.db.delete(doc)
    print(f" ({len(docs)} deleted)")
    
    print("  Deleting sessions...", end='', flush=True)
    sessions = db_manager.db.query(Session).all()
    for session in sessions:
        db_manager.db.delete(session)
    print(f" ({len(sessions)} deleted)")
    
    db_manager.db.commit()
    print("\n[✓] PostgreSQL completely cleaned!")
    
except Exception as e:
    db_manager.db.rollback()
    print(f"\n[!] Error: {e}")

# Qdrant cleanup
print("\n[Qdrant Cleanup]")
try:
    client = QdrantClient(url="http://localhost:6333")
    collections = client.get_collections()
    
    total_deleted = 0
    for collection in collections.collections:
        collection_name = collection.name
        # Get all points
        points, _ = client.scroll(collection_name, limit=100000, with_payload=True)
        point_ids = [p.id for p in points]
        
        if point_ids:
            # Delete all points
            client.delete(
                collection_name,
                points_selector=models.PointIdsList(points=point_ids)
            )
            total_deleted += len(point_ids)
            print(f"  {collection_name}: {len(point_ids)} vectors deleted")
        else:
            print(f"  {collection_name}: already empty")
    
    print(f"\n[✓] Qdrant completely cleaned! (Total: {total_deleted} vectors deleted)")
    
except Exception as e:
    print(f"[!] Error: {e}")

print("\n" + "="*70)
print("✅ DATABASE COMPLETELY EMPTY - READY FOR FRESH START!")
print("="*70 + "\n")
