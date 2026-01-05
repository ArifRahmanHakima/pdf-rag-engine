"""
INTEGRATION GUIDE: Menggunakan Database Storage dalam Document Service

Ini adalah contoh bagaimana update document_service.py untuk gunakan
PostgreSQL + Qdrant storage manager
"""

# ============ EXAMPLE 1: Save Chunks ke Database ============

async def ingest_pdf_async_with_db(
    session_id: str,
    pdf_path: str,
    filename: str,
    doc_id: str,
    rag_instance,
    sessions_dir: Path,
    working_dir: Path,
    session_status: dict,
    extract_text_func,
    docstring_api_key: str = None,
    embedding_func = None,  # NEW: embedding function
):
    """
    Updated version menggunakan database storage
    """
    from app.db import storage_manager
    import hashlib
    
    try:
        # ... existing extraction code ...
        
        # Split text into chunks
        chunks = split_text_into_chunks(text)
        
        # Generate embeddings (jika ada)
        embeddings = None
        if embedding_func:
            print(f"    Generating embeddings...", end='', flush=True)
            embed_start = time.time()
            embeddings = [embedding_func(chunk) for chunk in chunks]
            embed_time = time.time() - embed_start
            print(f" [{embed_time:.2f}s]", flush=True)
        
        # Save ke database (menggantikan file-based save)
        print(f"    Saving to database...", end='', flush=True)
        save_start = time.time()
        
        doc_type = "docstring" if docstring_api_key and "docstring" in doc_id else "ocr"
        
        chunk_objects = storage_manager.save_chunks(
            session_id=session_id,
            document_id=doc_id,
            chunks=chunks,
            embeddings=embeddings,  # Automatic save ke Qdrant
            doc_type=doc_type
        )
        
        save_time = time.time() - save_start
        print(f" [{save_time:.2f}s]", flush=True)
        
        # Create document metadata in DB
        storage_manager.create_document(
            doc_id=doc_id,
            session_id=session_id,
            filename=filename,
            doc_type=doc_type,
            pages=text.count("=== Page"),
            size=len(text),
            extraction_time=ocr_time,
            full_doc_id=None  # Set nanti dari LightRAG jika ada
        )
        
        # Update session status
        session_status[session_id]["status"] = "ready"
        
        return True
        
    except Exception as e:
        session_status[session_id]["status"] = "error"
        session_status[session_id]["error"] = str(e)
        return False


# ============ EXAMPLE 2: Search Chunks dari Database ============

async def search_chunks_from_db(
    session_id: str,
    doc_id: str,
    query: str,
    embedding_func,
    limit: int = 10
):
    """
    Search chunks menggunakan database + vector search
    """
    from app.db import storage_manager
    
    try:
        # Generate query embedding
        query_embedding = embedding_func(query)
        
        # Search di Qdrant (dengan PostgreSQL enrichment)
        results = storage_manager.search_chunks_by_embedding(
            embedding=query_embedding,
            limit=limit,
            session_id=session_id,
            document_id=doc_id
        )
        
        # Return search results
        return [
            {
                'content': r['content'],
                'score': r['score'],
                'source': r['document_filename'],
                'chunk_id': r['chunk_id']
            }
            for r in results
        ]
        
    except Exception as e:
        print(f"[!] Search error: {e}")
        return []


# ============ EXAMPLE 3: Delete Session dari Database ============

def delete_session_from_db(session_id: str):
    """
    Delete session - automatically clean PostgreSQL dan Qdrant
    """
    from app.db import storage_manager
    
    try:
        success = storage_manager.delete_session(session_id)
        if success:
            print(f"[✓] Deleted session {session_id} from PostgreSQL dan Qdrant")
        return success
    except Exception as e:
        print(f"[!] Delete error: {e}")
        return False


# ============ EXAMPLE 4: List Sessions ============

def list_sessions_from_db():
    """
    Get all sessions from database
    """
    from app.db import SessionLocal, Session as SessionModel
    
    db = SessionLocal()
    try:
        sessions = db.query(SessionModel).all()
        return [
            {
                'id': s.id,
                'created_at': s.created_at.isoformat(),
                'documents_count': len(s.documents),
                'metadata': s.metadata
            }
            for s in sessions
        ]
    finally:
        db.close()


# ============ EXAMPLE 5: Get Chunks dari Database ============

def get_document_chunks_from_db(session_id: str, doc_id: str):
    """
    Get all chunks untuk dokumen
    """
    from app.db import storage_manager
    
    chunks = storage_manager.get_chunks_by_document(doc_id)
    return [
        {
            'chunk_id': c.id,
            'content': c.content,
            'index': c.chunk_index,
            'size': c.metadata.get('length') if c.metadata else 0
        }
        for c in chunks
    ]


# ============ INTEGRATION STEPS ============
"""
1. Update main_server.py:
   - Import storage_manager
   - Call init_db() pada startup
   
2. Update app/handlers/api_handlers.py:
   - Update upload handler untuk gunakan storage_manager
   - Update search handler untuk gunakan Qdrant
   - Update delete handler untuk cascade delete
   
3. Update app/services/document_service.py:
   - Replace file save logic dengan storage_manager.save_chunks()
   
4. Update app/services/search_logic.py:
   - Replace JSON load dengan storage_manager.search_chunks_by_embedding()
   
5. Testing:
   - Test ingest: verify data ada di PostgreSQL dan Qdrant
   - Test search: verify embeddings retrieved correctly
   - Test delete: verify cascade delete works
"""

# ============ QUERY EXAMPLES ============
"""
# Direct PostgreSQL queries (jika perlu):

# Get all documents dalam session
SELECT * FROM documents WHERE session_id = 'folder_1';

# Get chunk count per document
SELECT document_id, COUNT(*) as chunk_count 
FROM chunks 
GROUP BY document_id;

# Get largest documents
SELECT id, filename, size 
FROM documents 
ORDER BY size DESC 
LIMIT 10;

# Get documents by type
SELECT * FROM documents WHERE doc_type = 'ocr';

# Join chunks with document info
SELECT c.id as chunk_id, c.content, d.filename, d.doc_type
FROM chunks c
JOIN documents d ON c.document_id = d.id
WHERE d.session_id = 'folder_1'
LIMIT 5;
"""
