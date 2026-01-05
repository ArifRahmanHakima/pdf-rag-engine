"""
Storage Abstraction Layer
Unified interface untuk menyimpan dan retrieve chunks/embeddings
Menggantikan file-based storage (JSON) dengan database storage
"""

from sqlalchemy.orm import Session as DBSession
from app.db.models import Session, Document, Chunk, Embedding, SessionLocal
from app.db.qdrant_manager import qdrant_manager
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
import hashlib
import logging
import json

logger = logging.getLogger(__name__)


class StorageManager:
    """Unified storage manager untuk PostgreSQL + Qdrant"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    # ============ SESSION Management ============
    
    def create_session(self, session_id: str, metadata: Optional[Dict] = None) -> Session:
        """Create atau get session"""
        try:
            # Try to get existing
            session = self.db.query(Session).filter(Session.id == session_id).first()
            if session:
                return session
            
            # Create new
            session = Session(id=session_id, metadata=metadata or {})
            self.db.add(session)
            self.db.commit()
            logger.info(f"[✓] Created session: {session_id}")
            return session
        except Exception as e:
            self.db.rollback()
            logger.error(f"[!] Failed to create session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        return self.db.query(Session).filter(Session.id == session_id).first()
    
    def get_all_sessions(self) -> List[Session]:
        """Get all sessions from database"""
        return self.db.query(Session).all()
    
    def update_session_metadata(self, session_id: str, metadata: Dict):
        """Update session metadata"""
        session = self.get_session(session_id)
        if session:
            session.meta_data = metadata
            session.updated_at = datetime.utcnow()
            self.db.commit()
    
    # ============ DOCUMENT Management ============
    
    def create_document(
        self,
        doc_id: str,
        session_id: str,
        filename: str,
        doc_type: str,
        pages: int,
        size: int,
        extraction_time: float,
        full_doc_id: Optional[str] = None,
        pdf_content: Optional[bytes] = None
    ) -> Document:
        """Create or update document entry (upsert)"""
        try:
            pdf_content_size = len(pdf_content) if pdf_content else 0
            logger.info(f"[*] Storing PDF binary: {filename}, size={pdf_content_size} bytes")
            
            # Try to get existing document
            existing_doc = self.db.query(Document).filter(Document.id == doc_id).first()
            
            if existing_doc:
                # Update existing document
                logger.info(f"[*] Updating existing document: {doc_id}")
                existing_doc.session_id = session_id
                existing_doc.filename = filename
                existing_doc.doc_type = doc_type
                existing_doc.pages = pages
                existing_doc.size = size
                existing_doc.extraction_time = extraction_time
                existing_doc.full_doc_id = full_doc_id
                existing_doc.pdf_content = pdf_content
                self.db.commit()
                logger.info(f"[✓] Updated document: {doc_id} with PDF={pdf_content_size > 0}")
                return existing_doc
            else:
                # Create new document
                doc = Document(
                    id=doc_id,
                    session_id=session_id,
                    filename=filename,
                    doc_type=doc_type,
                    pages=pages,
                    size=size,
                    extraction_time=extraction_time,
                    full_doc_id=full_doc_id,
                    pdf_content=pdf_content
                )
                self.db.add(doc)
                self.db.commit()
                logger.info(f"[✓] Created document: {doc_id} with PDF={pdf_content_size > 0}")
                return doc
        except Exception as e:
            self.db.rollback()
            logger.error(f"[!] Failed to create document: {e}")
            raise
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get document by ID"""
        return self.db.query(Document).filter(Document.id == doc_id).first()
    
    def get_session_documents(self, session_id: str) -> List[Document]:
        """Get all documents in a session"""
        return self.db.query(Document).filter(Document.session_id == session_id).all()
    
    # ============ CHUNK Management ============
    
    def save_chunks(
        self,
        session_id: str,
        document_id: str,
        chunks: List[str],
        embeddings: List[List[float]] = None,
        doc_type: str = "ocr"
    ) -> List[Chunk]:
        """
        Save chunks dan embeddings ke database
        Menggantikan kv_store_text_chunks.json
        
        Args:
            session_id: Session folder ID
            document_id: Document ID
            chunks: List of text chunks
            embeddings: List of embedding vectors (optional, jika sudah ada)
            doc_type: Type of document (ocr atau docstring)
        
        Returns:
            List of created Chunk objects
        """
        try:
            chunk_objects = []
            
            for idx, chunk_text in enumerate(chunks):
                # Generate chunk ID (MD5 hash dari content)
                chunk_id = hashlib.md5(chunk_text.encode()).hexdigest()
                
                # Check if already exists
                existing = self.db.query(Chunk).filter(Chunk.id == chunk_id).first()
                if existing:
                    logger.warning(f"[!] Chunk already exists: {chunk_id[:8]}...")
                    chunk_objects.append(existing)
                    continue
                
                # Create chunk
                chunk = Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    session_id=session_id,
                    content=chunk_text,
                    chunk_index=idx,
                    metadata={
                        "length": len(chunk_text),
                        "doc_type": doc_type,
                        "created_at": datetime.utcnow().isoformat()
                    }
                )
                self.db.add(chunk)
                chunk_objects.append(chunk)
            
            self.db.commit()
            logger.info(f"[✓] Saved {len(chunk_objects)} chunks to PostgreSQL")
            
            # Save embeddings jika ada
            if embeddings and len(embeddings) == len(chunks):
                for chunk, embedding in zip(chunk_objects, embeddings):
                    qdrant_id = qdrant_manager.add_chunk_vector(
                        chunk_id=chunk.id,
                        embedding=embedding,
                        session_id=session_id,
                        document_id=document_id,
                        metadata={"chunk_index": chunk.chunk_index}
                    )
                    
                    # Link embeddings
                    chunk.embedding_id = chunk.id
                    emb = Embedding(
                        id=chunk.id,
                        chunk_id=chunk.id,
                        session_id=session_id,
                        document_id=document_id,
                        qdrant_id=qdrant_id,
                        embedding_type="chunk",
                        vector_dim=len(embedding)
                    )
                    self.db.add(emb)
                
                self.db.commit()
                logger.info(f"[✓] Saved {len(embeddings)} embeddings to Qdrant")
            
            return chunk_objects
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"[!] Failed to save chunks: {e}")
            raise
    
    def get_chunks_by_document(self, document_id: str) -> List[Chunk]:
        """Get all chunks for a document"""
        return self.db.query(Chunk)\
            .filter(Chunk.document_id == document_id)\
            .order_by(Chunk.chunk_index)\
            .all()
    
    def get_chunks_by_session(self, session_id: str) -> List[Chunk]:
        """Get all chunks in a session"""
        return self.db.query(Chunk)\
            .filter(Chunk.session_id == session_id)\
            .all()
    
    def search_chunks_by_embedding(
        self,
        embedding: List[float],
        limit: int = 10,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Search chunks by embedding similarity
        Combines Qdrant vector search dengan PostgreSQL metadata
        """
        try:
            # Search di Qdrant
            results = qdrant_manager.search_chunks(
                embedding=embedding,
                limit=limit,
                session_id=session_id,
                document_id=document_id
            )
            
            # Enrich dengan data dari PostgreSQL
            enriched_results = []
            for result in results:
                chunk = self.db.query(Chunk).filter(
                    Chunk.id == result["chunk_id"]
                ).first()
                
                if chunk:
                    enriched_results.append({
                        **result,
                        "content": chunk.content,
                        "document_filename": chunk.document.filename if chunk.document else None,
                    })
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"[!] Search failed: {e}")
            raise
    
    # ============ CLEANUP ============
    
    def delete_session(self, session_id: str) -> bool:
        """Delete entire session dengan semua documents dan chunks"""
        try:
            session = self.get_session(session_id)
            if not session:
                return False
            
            # Delete all chunks (Qdrant vectors akan ter-handle by Qdrant cascade)
            chunks = self.get_chunks_by_session(session_id)
            for chunk in chunks:
                if chunk.embedding_id:
                    # Delete dari Qdrant
                    qdrant_manager.client.delete(
                        collection_name="chunks",
                        points_selector={"ids": [int(chunk.embedding_id[:16], 16)]}
                    )
            
            # Delete session (cascade delete documents dan chunks)
            self.db.delete(session)
            self.db.commit()
            
            logger.info(f"[✓] Deleted session: {session_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"[!] Failed to delete session: {e}")
            raise
    
    def delete_document(self, document_id: str) -> bool:
        """Delete document dengan semua chunks"""
        try:
            doc = self.get_document(document_id)
            if not doc:
                return False
            
            # Delete chunks dari Qdrant
            chunks = self.get_chunks_by_document(document_id)
            for chunk in chunks:
                if chunk.embedding_id:
                    qdrant_manager.client.delete(
                        collection_name="chunks",
                        points_selector={"ids": [int(chunk.embedding_id[:16], 16)]}
                    )
            
            # Delete document (cascade delete chunks)
            self.db.delete(doc)
            self.db.commit()
            
            logger.info(f"[✓] Deleted document: {document_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"[!] Failed to delete document: {e}")
            raise
    
    def __del__(self):
        """Cleanup DB connection"""
        try:
            self.db.close()
        except:
            pass


# Singleton instance
storage_manager = StorageManager()
