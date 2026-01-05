"""
Qdrant Vector Storage Manager
Handles all vector embeddings untuk chunks, entities, dan relationships
"""

import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.config.db_config import qdrant_config
from typing import List, Dict, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manager untuk Qdrant vector storage"""
    
    def __init__(self):
        # Determine connection mode
        qdrant_mode = os.getenv("QDRANT_MODE", "memory")  # "memory" or "server"
        
        if qdrant_mode == "server":
            # Connect to Qdrant server (HTTP API)
            # Requires: qdrant.exe running on localhost:6333
            url = os.getenv("QDRANT_URL", "http://localhost:6333")
            try:
                self.client = QdrantClient(url=url)
                logger.info(f"[✓] Connected to Qdrant server at {url}")
            except Exception as e:
                logger.error(f"[!] Failed to connect to Qdrant server at {url}: {e}")
                logger.info("    Falling back to in-memory Qdrant")
                self.client = QdrantClient(":memory:")
        else:
            # Use in-memory Qdrant untuk development (avoids Docker/server dependency)
            self.client = QdrantClient(":memory:")
            logger.info("[✓] Using in-memory Qdrant (no server needed)")
        
        self.vector_size = qdrant_config.vector_size
        self._initialize_collections()
    
    def _initialize_collections(self):
        """Initialize atau verify collections exist"""
        collections = [
            qdrant_config.collection_chunks,
            qdrant_config.collection_entities,
            qdrant_config.collection_relationships
        ]
        
        for collection_name in collections:
            try:
                self.client.get_collection(collection_name)
                logger.info(f"[✓] Collection '{collection_name}' exists")
            except Exception:
                # Collection tidak ada, create baru
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"[✓] Created collection '{collection_name}'")
    
    def add_chunk_vector(
        self,
        chunk_id: str,
        embedding: List[float],
        session_id: str,
        document_id: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Add chunk embedding to Qdrant
        
        Args:
            chunk_id: Unique chunk ID (dari PostgreSQL)
            embedding: Vector embedding (1024-dimensional)
            session_id: Session folder ID
            document_id: Document ID
            metadata: Additional metadata
        
        Returns:
            Qdrant point ID (integer)
        """
        try:
            # Convert chunk_id to integer for Qdrant (Qdrant uses integer IDs)
            qdrant_id = self._hash_to_int(chunk_id)
            
            # Prepare payload
            payload = {
                "chunk_id": chunk_id,
                "session_id": session_id,
                "document_id": document_id,
                "type": "chunk"
            }
            
            if metadata:
                payload.update(metadata)
            
            # Create point
            point = PointStruct(
                id=qdrant_id,
                vector=embedding,
                payload=payload
            )
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=qdrant_config.collection_chunks,
                points=[point]
            )
            
            logger.info(f"[✓] Added chunk embedding: {chunk_id[:8]}... (Qdrant ID: {qdrant_id})")
            return qdrant_id
            
        except Exception as e:
            logger.error(f"[!] Failed to add chunk vector: {e}")
            raise
    
    def search_chunks(
        self,
        embedding: List[float],
        limit: int = 10,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Search similar chunks by embedding
        
        Args:
            embedding: Query embedding vector
            limit: Number of results
            session_id: Filter by session (optional)
            document_id: Filter by document (optional)
        
        Returns:
            List of similar chunks with metadata
        """
        try:
            # Build filter jika diperlukan
            query_filter = None
            if session_id or document_id:
                conditions = []
                if session_id:
                    conditions.append({
                        "key": "session_id",
                        "match": {"value": session_id}
                    })
                if document_id:
                    conditions.append({
                        "key": "document_id",
                        "match": {"value": document_id}
                    })
                
                if len(conditions) == 1:
                    query_filter = conditions[0]
                else:
                    query_filter = {"must": conditions}
            
            # Search
            search_result = self.client.search(
                collection_name=qdrant_config.collection_chunks,
                query_vector=embedding,
                query_filter=query_filter,
                limit=limit,
                with_payload=True
            )
            
            results = []
            for hit in search_result:
                results.append({
                    "chunk_id": hit.payload["chunk_id"],
                    "session_id": hit.payload["session_id"],
                    "document_id": hit.payload["document_id"],
                    "score": hit.score,
                    "metadata": {k: v for k, v in hit.payload.items() 
                               if k not in ["chunk_id", "session_id", "document_id", "type"]}
                })
            
            return results
            
        except Exception as e:
            logger.error(f"[!] Search failed: {e}")
            raise
    
    def add_entity_vector(
        self,
        entity_id: str,
        embedding: List[float],
        entity_name: str,
        session_id: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """Add entity embedding"""
        qdrant_id = self._hash_to_int(entity_id)
        
        payload = {
            "entity_id": entity_id,
            "entity_name": entity_name,
            "session_id": session_id,
            "type": "entity"
        }
        
        if metadata:
            payload.update(metadata)
        
        point = PointStruct(
            id=qdrant_id,
            vector=embedding,
            payload=payload
        )
        
        self.client.upsert(
            collection_name=qdrant_config.collection_entities,
            points=[point]
        )
        
        return qdrant_id
    
    def add_relationship_vector(
        self,
        rel_id: str,
        embedding: List[float],
        rel_type: str,
        source: str,
        target: str,
        session_id: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """Add relationship embedding"""
        qdrant_id = self._hash_to_int(rel_id)
        
        payload = {
            "rel_id": rel_id,
            "rel_type": rel_type,
            "source": source,
            "target": target,
            "session_id": session_id,
            "type": "relationship"
        }
        
        if metadata:
            payload.update(metadata)
        
        point = PointStruct(
            id=qdrant_id,
            vector=embedding,
            payload=payload
        )
        
        self.client.upsert(
            collection_name=qdrant_config.collection_relationships,
            points=[point]
        )
        
        return qdrant_id
    
    @staticmethod
    def _hash_to_int(hash_str: str) -> int:
        """Convert hex hash string to positive integer"""
        return abs(int(hash_str[:16], 16)) % (2**31 - 1)


# Singleton instance
qdrant_manager = QdrantManager()
