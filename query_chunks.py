#!/usr/bin/env python
"""
Query specific session data - view chunks and content in detail
"""

import sys
from app.db import SessionLocal
from app.db.models import Session, Document, Chunk


def show_all_sessions():
    """Show all available sessions"""
    db = SessionLocal()
    sessions = db.query(Session).all()
    
    print("\n📋 Available Sessions:")
    session_list = []
    
    if not sessions:
        print("  [No sessions found]")
        db.close()
        return []
    
    for i, s in enumerate(sessions, 1):
        # Count docs while session is still bound
        doc_count = db.query(Document).filter(Document.session_id == s.id).count()
        session_list.append({"id": s.id, "created": s.created_at, "docs": doc_count})
        print(f"  {i}. {s.id:<20} ({doc_count} docs, created {s.created_at.strftime('%Y-%m-%d %H:%M')})")
    
    db.close()
    return session_list


def show_session_chunks(session_id: str):
    """Display all chunks from a session"""
    db = SessionLocal()
    
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        print(f"\n[!] Session not found: {session_id}")
        db.close()
        return
    
    print(f"\n" + "="*100)
    print(f"📊 Session: {session_id}")
    print("="*100)
    
    # Get documents
    docs = db.query(Document).filter(Document.session_id == session_id).all()
    print(f"\n📄 Documents ({len(docs)}):")
    
    total_chunks = 0
    for doc in docs:
        chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).order_by(Chunk.chunk_index).all()
        total_chunks += len(chunks)
        
        print(f"\n  Document: {doc.id}")
        print(f"    Filename: {doc.filename}")
        print(f"    Type: {doc.doc_type}")
        print(f"    Pages: {doc.pages}, Size: {doc.size} bytes")
        print(f"    Chunks: {len(chunks)}")
        
        # Show each chunk
        for chunk in chunks:
            print(f"\n    └─ Chunk [{chunk.chunk_index}] ID: {chunk.id[:16]}...")
            print(f"       Length: {len(chunk.content)} chars")
            print(f"       Content (first 200 chars):")
            content_preview = chunk.content.replace('\n', ' ')[:200]
            print(f"       {content_preview}...")
    
    print(f"\n" + "="*100)
    print(f"Summary: {len(docs)} documents, {total_chunks} total chunks")
    print("="*100)
    
    db.close()


def export_session_chunks_to_json(session_id: str, output_file: str):
    """Export all chunks from session to JSON"""
    import json
    
    db = SessionLocal()
    session = db.query(Session).filter(Session.id == session_id).first()
    
    if not session:
        print(f"[!] Session not found: {session_id}")
        return
    
    docs = db.query(Document).filter(Document.session_id == session_id).all()
    
    export_data = {
        "session_id": session_id,
        "documents": []
    }
    
    for doc in docs:
        chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).order_by(Chunk.chunk_index).all()
        
        doc_data = {
            "id": doc.id,
            "filename": doc.filename,
            "type": doc.doc_type,
            "pages": doc.pages,
            "size": doc.size,
            "chunks": [
                {
                    "id": chunk.id,
                    "index": chunk.chunk_index,
                    "length": len(chunk.content),
                    "content": chunk.content
                }
                for chunk in chunks
            ]
        }
        export_data["documents"].append(doc_data)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"[✓] Exported to {output_file}")
    db.close()


if __name__ == "__main__":
    
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        
        if len(sys.argv) > 2 and sys.argv[2] == "--export":
            output_file = sys.argv[3] if len(sys.argv) > 3 else f"export_{session_id}.json"
            export_session_chunks_to_json(session_id, output_file)
        else:
            show_session_chunks(session_id)
    else:
        # Show all sessions
        sessions = show_all_sessions()
        
        if sessions:
            print("\n💡 Usage:")
            print(f"  python query_chunks.py <session_id>              # Show chunks")
            print(f"  python query_chunks.py <session_id> --export [file]  # Export to JSON")
