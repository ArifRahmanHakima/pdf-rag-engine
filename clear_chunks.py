#!/usr/bin/env python
"""Clear all chunks and embeddings from PostgreSQL and Qdrant"""

from app.db.storage_manager import StorageManager
from app.db.models import Chunk, Embedding
from qdrant_client import QdrantClient
from qdrant_client.http import models

print("\n" + "="*70)
print("CLEARING ALL CHUNKS AND EMBEDDINGS")
print("="*70)

# Clear PostgreSQL
print("\n[PostgreSQL]")
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
    
    db_manager.db.commit()
    
except Exception as e:
    db_manager.db.rollback()
    print(f"[!] Error: {e}")

# Clear Qdrant
print("\n[Qdrant]")
try:
    client = QdrantClient(url="http://localhost:6333")
    collections = client.get_collections()
    
    for collection in collections.collections:
        collection_name = collection.name
        # Get all points
        points, _ = client.scroll(collection_name, limit=10000, with_payload=True)
        point_ids = [p.id for p in points]
        
        if point_ids:
            # Delete all points
            client.delete(
                collection_name,
                points_selector=models.PointIdsList(points=point_ids)
            )
            print(f"[✓] Cleared {collection_name}: {len(point_ids)} vectors deleted")
        else:
            print(f"[✓] {collection_name}: already empty")
    
except Exception as e:
    print(f"[!] Error: {e}")

print("\n" + "="*70)
print("✓ ALL CHUNKS AND EMBEDDINGS CLEARED!")
print("="*70 + "\n")
