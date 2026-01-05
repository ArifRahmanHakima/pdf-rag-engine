#!/usr/bin/env python
"""
Database Inspector - View all data stored in PostgreSQL + Qdrant
"""

import json
from tabulate import tabulate
from app.db import SessionLocal
from app.db.models import Session, Document, Chunk, Embedding
from app.db.qdrant_manager import qdrant_manager


def inspect_postgres():
    """Inspect PostgreSQL contents"""
    print("\n" + "="*80)
    print("PostgreSQL Database Contents")
    print("="*80)
    
    db = SessionLocal()
    
    # Sessions
    sessions = db.query(Session).all()
    print(f"\n📁 SESSIONS ({len(sessions)}):")
    if sessions:
        session_data = [
            [s.id, s.created_at.strftime("%Y-%m-%d %H:%M:%S"), len(s.documents)]
            for s in sessions
        ]
        print(tabulate(session_data, headers=["Session ID", "Created", "Docs"], tablefmt="grid"))
    else:
        print("  [empty]")
    
    # Documents
    documents = db.query(Document).all()
    print(f"\n📄 DOCUMENTS ({len(documents)}):")
    if documents:
        doc_data = [
            [d.id, d.filename, d.doc_type, d.pages, f"{d.size/1024:.1f}KB", d.session_id]
            for d in documents
        ]
        print(tabulate(doc_data, headers=["Doc ID", "Filename", "Type", "Pages", "Size", "Session"], tablefmt="grid"))
    else:
        print("  [empty]")
    
    # Chunks
    chunks = db.query(Chunk).all()
    print(f"\n📦 CHUNKS ({len(chunks)}):")
    if chunks:
        chunk_data = [
            [c.id[:8], c.document_id, c.session_id, len(c.content), c.chunk_index]
            for c in chunks[:20]  # Show first 20
        ]
        print(tabulate(chunk_data, headers=["Chunk ID", "Doc ID", "Session", "Content Len", "Index"], tablefmt="grid"))
        if len(chunks) > 20:
            print(f"  ... and {len(chunks) - 20} more chunks")
    else:
        print("  [empty]")
    
    # Embeddings
    embeddings = db.query(Embedding).all()
    print(f"\n🧠 EMBEDDINGS ({len(embeddings)}):")
    if embeddings:
        emb_data = [
            [e.id[:8], e.chunk_id[:8], e.qdrant_id, e.embedding_type, e.vector_dim]
            for e in embeddings[:10]
        ]
        print(tabulate(emb_data, headers=["ID", "Chunk ID", "Qdrant ID", "Type", "Dim"], tablefmt="grid"))
        if len(embeddings) > 10:
            print(f"  ... and {len(embeddings) - 10} more embeddings")
    else:
        print("  [empty]")
    
    db.close()


def inspect_qdrant():
    """Inspect Qdrant vector database"""
    print("\n" + "="*80)
    print("Qdrant Vector Database Contents")
    print("="*80)
    
    try:
        # Get collection info
        collections = qdrant_manager.client.get_collections()
        print(f"\n🔍 COLLECTIONS ({len(collections.collections)}):")
        
        for collection in collections.collections:
            col_name = collection.name
            try:
                # Get collection stats
                col_info = qdrant_manager.client.get_collection(col_name)
                points_count = col_info.points_count
                vector_size = col_info.config.params.vectors.size if col_info.config.params.vectors else "?"
                
                print(f"\n  📊 {col_name}:")
                print(f"     Points: {points_count}")
                print(f"     Vector Size: {vector_size}")
                
                # Sample some points
                if points_count > 0:
                    sample_points = qdrant_manager.client.scroll(
                        collection_name=col_name,
                        limit=3,
                        with_vectors=False,
                        with_payload=True
                    )
                    if sample_points[0]:
                        print(f"     Sample points:")
                        for pt in sample_points[0][:3]:
                            payload = pt.payload if pt.payload else {}
                            print(f"       - ID: {pt.id}, Payload: {payload}")
            except Exception as e:
                print(f"     [Error reading collection: {e}]")
    
    except Exception as e:
        print(f"[!] Error connecting to Qdrant: {e}")


def get_session_details(session_id: str):
    """Get detailed info for a specific session"""
    print(f"\n" + "="*80)
    print(f"Session Details: {session_id}")
    print("="*80)
    
    db = SessionLocal()
    
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        print(f"[!] Session not found: {session_id}")
        return
    
    print(f"\nSession: {session.id}")
    print(f"Created: {session.created_at}")
    print(f"Metadata: {json.dumps(session.meta_data, indent=2, ensure_ascii=False)}")
    
    # Documents in session
    docs = db.query(Document).filter(Document.session_id == session_id).all()
    print(f"\n📄 Documents ({len(docs)}):")
    for doc in docs:
        print(f"\n  {doc.id}")
        print(f"    Filename: {doc.filename}")
        print(f"    Type: {doc.doc_type}")
        print(f"    Pages: {doc.pages}, Size: {doc.size} bytes")
        print(f"    Extraction time: {doc.extraction_time:.2f}s")
        
        # Chunks in document
        chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).all()
        print(f"    Chunks: {len(chunks)}")
        for i, chunk in enumerate(chunks[:5]):
            print(f"      [{i}] {chunk.id[:8]}... ({len(chunk.content)} chars)")
        if len(chunks) > 5:
            print(f"      ... and {len(chunks) - 5} more")
    
    db.close()


if __name__ == "__main__":
    import sys
    
    print("\n" + "🔍 RAG Database Inspector".center(80))
    
    inspect_postgres()
    inspect_qdrant()
    
    # Show details for first session if exists
    db = SessionLocal()
    first_session = db.query(Session).first()
    db.close()
    
    if first_session:
        get_session_details(first_session.id)
    
    print("\n" + "="*80 + "\n")
