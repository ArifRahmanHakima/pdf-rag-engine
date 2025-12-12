"""
Qwen Embedding - Using Qwen3-embedding-0.6B model
"""

import numpy as np
import os

# Suppress progress bars BEFORE importing SentenceTransformer
os.environ["TQDM_DISABLE"] = "1"

QWEN_AVAILABLE = False
embedding_model = None

try:
    from sentence_transformers import SentenceTransformer
    QWEN_AVAILABLE = True
except ImportError:
    pass

def load_embedding_model():
    """Load Qwen embedding model (lazy init)"""
    global embedding_model
    if embedding_model is None and QWEN_AVAILABLE:
        print("[*] Loading Qwen embedding model...")
        embedding_model = SentenceTransformer("Qwen/Qwen3-embedding-0.6B")
        print("[✓] Qwen embedding model loaded\n")
    return embedding_model

async def batch_embed_texts(texts, batch_size=1):
    """Embed texts using Qwen model"""
    model = load_embedding_model()
    if model is None:
        return None
    
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
        embeddings.extend(batch_embeddings.tolist())
    return embeddings

def get_embedding_func():
    """Get embedding function for LightRAG"""
    from lightrag.utils import EmbeddingFunc
    
    embedding_func = EmbeddingFunc(
        embedding_dim=1024,  # Qwen3-embedding-0.6B uses 1024 dimensions
        max_token_size=8192,
        func=batch_embed_texts,
    )
    return embedding_func
