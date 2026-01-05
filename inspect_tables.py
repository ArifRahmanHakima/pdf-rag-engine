#!/usr/bin/env python3
"""
Inspect PostgreSQL tables - view all data in database
Cara mudah untuk melihat isi tabel di database
"""

import sys
from pathlib import Path
from sqlalchemy import text

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.models import SessionLocal, Session, Document, Chunk, Embedding


def print_separator(title=""):
    """Print a separator line"""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    else:
        print(f"\n{'-'*80}\n")


def inspect_sessions():
    """Inspect sessions table"""
    db = SessionLocal()
    try:
        sessions = db.query(Session).all()
        
        print_separator("SESSIONS TABLE")
        
        if not sessions:
            print("❌ Tidak ada session di database")
        else:
            print(f"✅ Total sessions: {len(sessions)}\n")
            for session in sessions:
                print(f"  📁 Session ID: {session.id}")
                print(f"     Created: {session.created_at}")
                print(f"     Updated: {session.updated_at}")
                print(f"     Metadata: {session.meta_data}")
                print()
    finally:
        db.close()


def inspect_documents():
    """Inspect documents table"""
    db = SessionLocal()
    try:
        documents = db.query(Document).all()
        
        print_separator("DOCUMENTS TABLE")
        
        if not documents:
            print("❌ Tidak ada dokumen di database")
        else:
            print(f"✅ Total documents: {len(documents)}\n")
            for doc in documents:
                print(f"  📄 Doc ID: {doc.id}")
                print(f"     Session: {doc.session_id}")
                print(f"     Filename: {doc.filename}")
                print(f"     Type: {doc.doc_type}")  # 'ocr' atau 'docstring'
                print(f"     Pages: {doc.pages}")
                print(f"     Size: {doc.size} bytes")
                print(f"     Upload Time: {doc.upload_time}")
                print(f"     Extraction Time: {doc.extraction_time}s")
                print(f"     PDF Content: {'✅ Ada' if doc.pdf_content else '❌ Kosong'}")
                print(f"     Chunks Count: {len(doc.chunks) if doc.chunks else 0}")
                print()
    finally:
        db.close()


def inspect_chunks():
    """Inspect chunks table"""
    db = SessionLocal()
    try:
        chunks = db.query(Chunk).all()
        
        print_separator("CHUNKS TABLE")
        
        if not chunks:
            print("❌ Tidak ada chunks di database")
        else:
            print(f"✅ Total chunks: {len(chunks)}\n")
            
            # Kelompokkan per dokumen
            chunks_by_doc = {}
            for chunk in chunks:
                if chunk.document_id not in chunks_by_doc:
                    chunks_by_doc[chunk.document_id] = []
                chunks_by_doc[chunk.document_id].append(chunk)
            
            for doc_id, doc_chunks in chunks_by_doc.items():
                print(f"  📋 Document: {doc_id} ({len(doc_chunks)} chunks)")
                for chunk in doc_chunks[:3]:  # Show first 3 chunks only
                    preview = chunk.content[:100].replace('\n', ' ')
                    print(f"     • Chunk {chunk.chunk_index}: {preview}...")
                if len(doc_chunks) > 3:
                    print(f"     ... dan {len(doc_chunks) - 3} chunks lagi")
                print()
    finally:
        db.close()


def inspect_embeddings():
    """Inspect embeddings table"""
    db = SessionLocal()
    try:
        embeddings = db.query(Embedding).all()
        
        print_separator("EMBEDDINGS TABLE")
        
        if not embeddings:
            print("❌ Tidak ada embeddings di database")
        else:
            print(f"✅ Total embeddings: {len(embeddings)}\n")
            
            # Group by document
            embeddings_by_doc = {}
            for emb in embeddings:
                if emb.document_id not in embeddings_by_doc:
                    embeddings_by_doc[emb.document_id] = []
                embeddings_by_doc[emb.document_id].append(emb)
            
            for doc_id, doc_embeddings in embeddings_by_doc.items():
                print(f"  🔢 Document: {doc_id} ({len(doc_embeddings)} embeddings)")
                for emb in doc_embeddings[:2]:  # Show first 2
                    print(f"     • Chunk ID: {emb.chunk_id[:8]}...")
                    print(f"       Qdrant ID: {emb.qdrant_id}")
                    print(f"       Dimension: {emb.vector_dim}")
                if len(doc_embeddings) > 2:
                    print(f"     ... dan {len(doc_embeddings) - 2} embeddings lagi")
                print()
    finally:
        db.close()


def count_all():
    """Quick count of all tables"""
    db = SessionLocal()
    try:
        sessions_count = db.query(Session).count()
        documents_count = db.query(Document).count()
        chunks_count = db.query(Chunk).count()
        embeddings_count = db.query(Embedding).count()
        
        print_separator("DATABASE SUMMARY")
        print(f"  Sessions:   {sessions_count}")
        print(f"  Documents:  {documents_count}")
        print(f"  Chunks:     {chunks_count}")
        print(f"  Embeddings: {embeddings_count}")
        print()
    finally:
        db.close()


def raw_query(sql: str):
    """Execute raw SQL query"""
    db = SessionLocal()
    try:
        result = db.execute(text(sql))
        rows = result.fetchall()
        
        print_separator("RAW QUERY RESULT")
        print(f"SQL: {sql}\n")
        
        if not rows:
            print("❌ Tidak ada hasil")
        else:
            print(f"✅ Total rows: {len(rows)}\n")
            for row in rows:
                print(f"  {row}")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("  PostgreSQL Database Inspector")
    print("="*80)
    
    # Show all data
    count_all()
    inspect_sessions()
    inspect_documents()
    inspect_chunks()
    inspect_embeddings()
    
    print("\n" + "="*80)
    print("✅ Inspeksi selesai")
    print("="*80 + "\n")
