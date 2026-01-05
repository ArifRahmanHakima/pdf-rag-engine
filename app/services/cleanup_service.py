"""
Cleanup service - handles document and session deletion from PostgreSQL + Qdrant
"""

from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Thread pool untuk run sync DB operations
_executor = ThreadPoolExecutor(max_workers=2)

def _delete_document_sync(
    session_id: str,
    doc_id: str,
):
    """
    SYNCHRONOUS delete function - runs in thread pool
    Delete a document and ALL its associated data from PostgreSQL + Qdrant
    
    Returns:
        (success: bool, deleted_count: dict)
    """
    try:
        print(f"\n[*] _delete_document_sync: Deleting document: {doc_id} from session {session_id}")
        
        from app.services.database_service import get_database_service
        from app.db.models import SessionLocal, Document, Chunk, Embedding, Session
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
        
        db_service = get_database_service()
        db_session = SessionLocal()
        
        # === Step 1: Get all chunks for this document ===
        chunks = db_session.query(Chunk).filter(Chunk.document_id == doc_id).all()
        chunk_ids = [c.id for c in chunks]
        deleted_chunks = len(chunks)
        
        print(f"[*] Found {deleted_chunks} chunks to delete")
        print(f"[*] Chunk IDs: {chunk_ids}")
        
        # === Step 2: Delete embeddings FIRST (before chunks due to FK constraint) ===
        deleted_embeddings = 0
        if chunk_ids:
            # Query embeddings that reference these chunks
            embeddings_to_delete = db_session.query(Embedding).filter(
                Embedding.chunk_id.in_(chunk_ids)
            ).all()
            deleted_embeddings = len(embeddings_to_delete)
            print(f"[*] Found {deleted_embeddings} embeddings to delete")
            
            # Delete embeddings using bulk delete (more efficient and proper)
            if deleted_embeddings > 0:
                db_session.query(Embedding).filter(
                    Embedding.chunk_id.in_(chunk_ids)
                ).delete(synchronize_session=False)
                print(f"[✓] Deleted {deleted_embeddings} embeddings")
        
        # === Step 3: Delete chunks (after embeddings) ===
        print(f"[*] Deleting {deleted_chunks} chunks...")
        if deleted_chunks > 0:
            db_session.query(Chunk).filter(
                Chunk.document_id == doc_id
            ).delete(synchronize_session=False)
            print(f"[✓] Deleted {deleted_chunks} chunks")
        
        # === Step 4: Delete document ===
        doc = db_session.query(Document).filter(
            Document.id == doc_id,
            Document.session_id == session_id
        ).first()
        
        deleted_doc = 0
        if doc:
            deleted_doc = 1
            print(f"[*] Deleting document from PostgreSQL...")
            db_session.delete(doc)
        
        # === Step 5: Commit to PostgreSQL ===
        db_session.commit()
        print(f"[✓] PostgreSQL deleted: {deleted_doc} document, {deleted_chunks} chunks, {deleted_embeddings} embeddings")
        
        # === Step 6: Delete from Qdrant ===
        deleted_vectors = 0
        try:
            qdrant_client = QdrantClient(url="http://localhost:6333")
            
            # Delete from chunks collection
            for collection_name in ["chunks", "entities", "relationships"]:
                try:
                    # Get all points first
                    points, _ = qdrant_client.scroll(
                        collection_name,
                        limit=10000,
                        with_payload=True
                    )
                    
                    # Find points with matching doc_id
                    points_to_delete = [
                        p.id for p in points
                        if p.payload and p.payload.get('doc_id') == doc_id
                    ]
                    
                    if points_to_delete:
                        qdrant_client.delete(
                            collection_name,
                            points_selector=models.PointIdsList(points=points_to_delete)
                        )
                        deleted_vectors += len(points_to_delete)
                        print(f"[✓] Deleted {len(points_to_delete)} vectors from Qdrant {collection_name}")
                except Exception as e:
                    print(f"[!] Note: {collection_name} may not have matching points: {e}")
            
            print(f"[✓] Qdrant cleanup complete ({deleted_vectors} vectors deleted)")
        except Exception as e:
            print(f"[!] Error with Qdrant cleanup: {e}")
        
        # === Step 7: Check if session is now empty, delete if so ===
        remaining_docs = db_session.query(Document).filter(
            Document.session_id == session_id
        ).count()
        
        deleted_session = 0
        if remaining_docs == 0:
            print(f"[*] Session {session_id} now empty, deleting session...")
            session_obj = db_session.query(Session).filter(
                Session.id == session_id
            ).first()
            if session_obj:
                db_session.delete(session_obj)
                db_session.commit()
                deleted_session = 1
                print(f"[✓] Session {session_id} deleted")
        
        db_session.close()
        
        print(f"\n[✓] DELETION COMPLETE:")
        print(f"    - Documents: {deleted_doc}")
        print(f"    - Chunks: {deleted_chunks}")
        print(f"    - Embeddings: {deleted_embeddings}")
        print(f"    - Vectors (Qdrant): {deleted_vectors}")
        print(f"    - Sessions: {deleted_session}")
        
        return True, {
            "documents": deleted_doc,
            "chunks": deleted_chunks,
            "embeddings": deleted_embeddings,
            "vectors": deleted_vectors,
            "sessions": deleted_session
        }
        
    except Exception as e:
        print(f"\n[!] DELETE ERROR: {e}")
        import traceback
        traceback.print_exc()
        if 'db_session' in locals():
            try:
                db_session.close()
            except:
                pass
        return False, {"error": str(e)}


async def delete_document_service(
    session_id: str,
    doc_id: str,
    sessions_dir=None,  # DEPRECATED - not used
    working_dir=None,   # DEPRECATED - not used
    session_status=None # DEPRECATED - not used
):
    """
    ASYNC wrapper for delete_document_service
    Runs sync DB operations in thread pool
    
    Returns:
        (success: bool, deleted_count: dict)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _delete_document_sync,
        session_id,
        doc_id
    )


async def delete_session_service(session_id: str, sessions_dir: Path, working_dir: Path, session_status: dict):
    """
    Delete entire session with VDB cleanup
    
    Args:
        session_id: Session identifier
        sessions_dir: Sessions directory path
        working_dir: Working directory path
        session_status: Session status dictionary (to update)
    """
    try:
        session_dir = sessions_dir / session_id
        
        if session_id in session_status:
            del session_status[session_id]
        
        if session_dir.exists():
            import shutil
            shutil.rmtree(session_dir)
        
        # Clean up VDB files
        try:
            vdb_files = [
                Path(working_dir) / "vdb_chunks.json",
                Path(working_dir) / "vdb_entities.json",
                Path(working_dir) / "vdb_relationships.json"
            ]
            
            for vdb_file in vdb_files:
                if vdb_file.exists():
                    vdb_file.unlink()
                    print(f"[✓] Deleted {vdb_file.name}")
            
            print(f"[✓] Session {session_id} deleted with full VDB cleanup")
        except Exception as e:
            print(f"[!] Warning: Could not clean VDB files: {e}")
        
        return True
    
    except Exception as e:
        print(f"[!] Delete session error: {e}")
        return False
