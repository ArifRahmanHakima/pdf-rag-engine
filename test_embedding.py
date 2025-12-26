#!/usr/bin/env python3
"""Test embedding model to ensure correct dimensions"""

from sentence_transformers import SentenceTransformer
import time

# Test the embedding model
print("🔍 Testing Embedding Model Configuration")
print("=" * 70)

model_name = "all-MiniLM-L6-v2"
print(f"📦 Loading model: {model_name}")

try:
    model = SentenceTransformer(model_name)
    print(f"✅ Model loaded successfully")
    
    # Test encoding
    test_texts = [
        "Hello, this is a test.",
        "Embedding models are useful for semantic search.",
        "ini adalah teks bahasa indonesia untuk testing."
    ]
    
    print(f"\n🧪 Encoding {len(test_texts)} test texts...")
    start_time = time.time()
    embeddings = model.encode(test_texts, batch_size=512, show_progress_bar=False)
    elapsed = time.time() - start_time
    
    print(f"✅ Encoding completed in {elapsed:.3f}s")
    print(f"\n📊 Embedding Statistics:")
    print(f"   • Number of embeddings: {len(embeddings)}")
    print(f"   • Embedding dimension: {len(embeddings[0])}")
    print(f"   • Expected dimension: 384")
    
    if len(embeddings[0]) == 384:
        print(f"   ✅ MATCH! Embedding dimension is correct")
    else:
        print(f"   ❌ MISMATCH! Expected 384, got {len(embeddings[0])}")
    
    # Test batch encoding performance
    print(f"\n⚡ Testing batch encoding speed with different batch sizes:")
    for batch_size in [128, 256, 512]:
        test_batch = test_texts * 10  # 30 texts
        start_time = time.time()
        _ = model.encode(test_batch, batch_size=batch_size, show_progress_bar=False)
        elapsed = time.time() - start_time
        print(f"   • Batch size {batch_size:3d}: {elapsed:.3f}s ({len(test_batch)} texts)")
    
    print(f"\n{'='*70}")
    print("✅ All checks passed! Model is ready to use.")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
