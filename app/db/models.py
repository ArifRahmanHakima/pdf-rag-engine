"""
SQLAlchemy Models untuk PostgreSQL
Menyimpan struktur folder-like dengan database hierarchy
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Index, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from app.config.db_config import postgres_config

Base = declarative_base()


class Session(Base):
    """Model untuk Session (folder rag_storage/pdf_sessions/folder_N)"""
    __tablename__ = "sessions"
    
    id = Column(String(50), primary_key=True)  # folder_1, folder_2, etc
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta_data = Column(JSON)  # metadata seperti selected_doc, status, dll
    
    # Relationships
    documents = relationship("Document", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Session(id={self.id})>"


class Document(Base):
    """Model untuk Document (rag_storage/pdf_sessions/folder_N/documents/doc_id)"""
    __tablename__ = "documents"
    
    id = Column(String(100), primary_key=True)  # unique doc_id
    session_id = Column(String(50), ForeignKey("sessions.id"), nullable=False)
    filename = Column(String(255))
    doc_type = Column(String(50))  # "ocr" atau "docstring"
    pages = Column(Integer)
    size = Column(Integer)  # size in bytes
    upload_time = Column(DateTime, default=datetime.utcnow)
    extraction_time = Column(Float)  # waktu ekstraksi dalam detik
    full_doc_id = Column(String(100))  # ID dari LightRAG
    pdf_content = Column(LargeBinary)  # Store PDF binary data
    
    # Relationships
    session = relationship("Session", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    
    # Indexes untuk search cepat
    __table_args__ = (
        Index('idx_doc_session_id', 'session_id'),
        Index('idx_doc_type', 'doc_type'),
    )
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename})>"


class Chunk(Base):
    """Model untuk Text Chunk (rag_storage/pdf_sessions/folder_N/documents/doc_id/chunks.json)"""
    __tablename__ = "chunks"
    
    id = Column(String(64), primary_key=True)  # MD5 hash dari content
    document_id = Column(String(100), ForeignKey("documents.id"), nullable=False)
    session_id = Column(String(50), nullable=False)  # Denormalized untuk query cepat
    
    content = Column(Text, nullable=False)  # Isi chunk text
    chunk_index = Column(Integer)  # Urutan chunk dalam dokumen
    embedding_id = Column(String(64))  # Reference ke Qdrant vector ID
    
    meta_data = Column(JSON)  # Extra metadata (page, length, dll)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    # Indexes
    __table_args__ = (
        Index('idx_chunk_document_id', 'document_id'),
        Index('idx_chunk_session_id', 'session_id'),
        Index('idx_chunk_embedding_id', 'embedding_id'),
    )
    
    def __repr__(self):
        return f"<Chunk(id={self.id[:8]}..., doc={self.document_id})>"


class Embedding(Base):
    """Model untuk tracking embeddings di Qdrant"""
    __tablename__ = "embeddings"
    
    id = Column(String(64), primary_key=True)  # Same as Chunk ID
    chunk_id = Column(String(64), ForeignKey("chunks.id"), nullable=False)
    session_id = Column(String(50), nullable=False)
    document_id = Column(String(100), nullable=False)
    
    qdrant_id = Column(Integer, unique=True)  # ID di Qdrant (untuk vector storage)
    embedding_type = Column(String(50))  # "chunk", "entity", atau "relationship"
    vector_dim = Column(Integer)  # Dimensi vektor
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_embedding_chunk_id', 'chunk_id'),
        Index('idx_embedding_session_id', 'session_id'),
        Index('idx_embedding_qdrant_id', 'qdrant_id'),
    )
    
    def __repr__(self):
        return f"<Embedding(chunk={self.chunk_id[:8]}..., qdrant={self.qdrant_id})>"


# Database Engine dan Session
engine = create_engine(postgres_config.connection_string)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create semua tables"""
    Base.metadata.create_all(engine)


def get_db():
    """Dependency untuk FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
