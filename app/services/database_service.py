"""
Database Integration Service - bridges LightRAG with PostgreSQL + Qdrant
Manages chunk persistence in PostgreSQL and vector embeddings in Qdrant
"""

from app.db.storage_manager import StorageManager
from app.db.models import SessionLocal
from typing import List, Dict, Optional
import logging
import hashlib

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service untuk manage database operations"""
    
    def __init__(self):
        self.storage = StorageManager()
    
    # ============ SESSION Management ============
    
    def create_session(self, session_id: str, metadata: Optional[Dict] = None):
        """Create session in PostgreSQL"""
        return self.storage.create_session(session_id, metadata)
    
    def get_session(self, session_id: str):
        """Get session from PostgreSQL"""
        return self.storage.get_session(session_id)
    
    # ============ DOCUMENT Management ============
    
    def store_document(
        self,
        session_id: str,
        doc_id: str,
        filename: str,
        doc_type: str,
        pages: int,
        size: int,
        extraction_time: float,
        full_doc_id: str = None,
        pdf_content: bytes = None
    ):
        """Store document metadata in PostgreSQL"""
        return self.storage.create_document(
            session_id=session_id,
            doc_id=doc_id,
            filename=filename,
            doc_type=doc_type,
            pages=pages,
            size=size,
            extraction_time=extraction_time,
            full_doc_id=full_doc_id,
            pdf_content=pdf_content
        )
    
    def get_document(self, doc_id: str):
        """Get document from PostgreSQL"""
        return self.storage.get_document(doc_id)
    
    def get_session_documents(self, session_id: str):
        """Get all documents in a session"""
        return self.storage.get_session_documents(session_id)
    
    # ============ CHUNK Management ============
    
    def store_chunks(self, session_id: str, document_id: str, chunks: List[str], embeddings: List[List[float]] = None):
        """Store multiple chunks in PostgreSQL + Qdrant"""
        return self.storage.save_chunks(
            session_id=session_id,
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings
        )
    
    def get_chunk(self, document_id: str):
        """Get chunks from a document"""
        return self.storage.get_chunks_by_document(document_id)
    
    def get_session_chunks(self, session_id: str):
        """Get all chunks in a session"""
        return self.storage.get_chunks_by_session(session_id)
    
    def search_chunks(self, query_embedding: List[float], session_id: str = None, limit: int = 10):
        """Search chunks by vector similarity"""
        return self.storage.search_chunks_by_embedding(
            embedding=query_embedding,
            session_id=session_id,
            limit=limit
        )
    
    # ============ CLEANUP ============
    
    def delete_document(self, doc_id: str):
        """Delete document and related chunks"""
        return self.storage.delete_document(doc_id)
    
    def delete_session(self, session_id: str):
        """Delete session and all related data"""
        return self.storage.delete_session(session_id)


# Global instance
_database_service = None


def get_database_service() -> DatabaseService:
    """Get or create database service singleton"""
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service
