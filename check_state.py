#!/usr/bin/env python
"""Check current database and Qdrant state"""

from app.db.storage_manager import StorageManager
from app.db.models import Document, Chunk
from qdrant_client import QdrantClient

print("\n" + "="*70)
print("DATABASE STATE CHECK")
print("="*70)

db_manager = StorageManager()

try:
    # Check PostgreSQL
    print("\n[PostgreSQL]")
    sessions = db_manager.get_all_sessions()
    print(f"Sessions: {len(sessions)}")
    
    total_docs = 0
    total_chunks = 0
    for session in sessions:
        docs = db_manager.db.query(Document).filter(Document.session_id == session.id).all()
        chunks = db_manager.db.query(Chunk).filter(Chunk.session_id == session.id).all()
        total_docs += len(docs)
        total_chunks += len(chunks)
        print(f"  {session.id}: {len(docs)} docs, {len(chunks)} chunks")
        for doc in docs:
            has_pdf = doc.pdf_content is not None
            pdf_size = len(doc.pdf_content) if doc.pdf_content else 0
            print(f"    - {doc.filename}: pdf={pdf_size} bytes")
    
    print(f"\nTotal: {total_docs} documents, {total_chunks} chunks")
    
    # Check Qdrant
    print("\n[Qdrant Vectors]")
    client = QdrantClient(url="http://localhost:6333")
    collections = client.get_collections()
    
    for collection in collections.collections:
        points, _ = client.scroll(collection.name, limit=10000, with_payload=True)
        print(f"  {collection.name}: {len(points)} vectors")
        if points and len(points) < 20:
            for p in points[:5]:
                doc_id = p.payload.get('doc_id', 'unknown') if p.payload else 'unknown'
                print(f"    - Point {p.id}: doc_id={doc_id}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70 + "\n")
