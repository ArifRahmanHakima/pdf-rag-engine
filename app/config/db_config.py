"""
Database Configuration untuk PostgreSQL dan Qdrant
"""

import os
from dataclasses import dataclass

@dataclass
class PostgreSQLConfig:
    """PostgreSQL Configuration"""
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    user: str = os.getenv("POSTGRES_USER", "rag_user")
    password: str = os.getenv("POSTGRES_PASSWORD", "rag_password")
    database: str = os.getenv("POSTGRES_DB", "rag_system")
    
    @property
    def connection_string(self) -> str:
        """Get SQLAlchemy connection string"""
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class QdrantConfig:
    """Qdrant Vector DB Configuration"""
    host: str = os.getenv("QDRANT_HOST", "localhost")
    port: int = int(os.getenv("QDRANT_PORT", "6333"))
    collection_chunks: str = os.getenv("QDRANT_COLLECTION_CHUNKS", "chunks")
    collection_entities: str = os.getenv("QDRANT_COLLECTION_ENTITIES", "entities")
    collection_relationships: str = os.getenv("QDRANT_COLLECTION_RELATIONSHIPS", "relationships")
    vector_size: int = int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))
    
    @property
    def url(self) -> str:
        """Get Qdrant URL"""
        return f"http://{self.host}:{self.port}"


# Instantiate configs
postgres_config = PostgreSQLConfig()
qdrant_config = QdrantConfig()
