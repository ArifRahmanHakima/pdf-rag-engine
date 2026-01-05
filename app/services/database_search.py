"""
Database-aware search logic - retrieve chunks from PostgreSQL + Qdrant
"""

from app.services.database_service import get_database_service
from app.db.qdrant_manager import qdrant_manager
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def search_chunks_from_database(
    query_embedding: List[float],
    session_id: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Search chunks using Qdrant vector similarity + PostgreSQL filtering
    
    Args:
        query_embedding: Query vector embedding
        session_id: Optional session filter
        limit: Number of results to return
    
    Returns:
        List of chunk dictionaries with content and metadata
    """
    try:
        db_service = get_database_service()
        
        # Search in Qdrant
        results = db_service.search_chunks(
            query_embedding=query_embedding,
            session_id=session_id,
            limit=limit
        )
        
        logger.info(f"[✓] Found {len(results)} chunks from database search")
        return results
        
    except Exception as e:
        logger.error(f"[!] Database search failed: {e}")
        return []


def get_session_context(session_id: str) -> Dict:
    """Get all chunks from a session for context"""
    try:
        db_service = get_database_service()
        chunks = db_service.get_session_chunks(session_id)
        
        context = {
            "session_id": session_id,
            "chunks": chunks,
            "total_chunks": len(chunks)
        }
        
        logger.info(f"[✓] Loaded {len(chunks)} chunks from session {session_id}")
        return context
        
    except Exception as e:
        logger.error(f"[!] Failed to load session context: {e}")
        return {"session_id": session_id, "chunks": [], "total_chunks": 0}
