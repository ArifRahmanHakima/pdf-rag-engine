import os
import asyncio
import hashlib
from dotenv import load_dotenv
from raganything import RAGAnything, RAGAnythingConfig
from lightrag import LightRAG
from sentence_transformers import SentenceTransformer
from lightrag.utils import EmbeddingFunc
from api.services.llm_wrapper import llm_model_func, vision_model_func

load_dotenv()

# === Load Embedding Model ===
embed_model = SentenceTransformer(os.getenv("EMBEDDING_MODEL"))

async def async_embed(texts):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: embed_model.encode(texts, normalize_embeddings=True, batch_size=32)
    )

embedding_func = EmbeddingFunc(
    embedding_dim=384,
    max_token_size=512,
    func=async_embed
)

# === Dictionary untuk menyimpan RAG instance per dokumen ===
rag_instances = {}

def get_doc_id(filename: str) -> str:
    """Generate unique document ID from filename"""
    # Gunakan hash untuk ID yang konsisten
    return hashlib.md5(filename.encode()).hexdigest()[:16]

def check_document_exists(doc_id: str) -> bool:
    """Check if document has been processed before (storage exists)"""
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    
    # Check if essential files exist
    graph_file = os.path.join(doc_working_dir, "graph_chunk_entity_relation.graphml")
    return os.path.exists(graph_file)

def get_rag_instance(doc_id: str):
    """Get or create RAG instance for specific document"""
    if doc_id not in rag_instances:
        # Buat working directory khusus untuk dokumen ini
        base_dir = os.getenv("WORKING_DIR", "./rag_storage")
        doc_working_dir = os.path.join(base_dir, doc_id)
        
        # Pastikan directory ada
        os.makedirs(doc_working_dir, exist_ok=True)
        
        config = RAGAnythingConfig(
            working_dir=doc_working_dir,
            parser="mineru",
            parse_method="auto",
            enable_image_processing=False,
            enable_table_processing=False,
            enable_equation_processing=False,
        )
        
        # Check if document was processed before
        document_exists = check_document_exists(doc_id)
        
        if document_exists:
            # Document exists, initialize with LightRAG so we can query
            print(f"📂 Loading existing document: {doc_id}")
            
            lightrag_instance = LightRAG(
                working_dir=doc_working_dir,
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
            )
            
            rag_instances[doc_id] = RAGAnything(
                config=config,
                llm_model_func=llm_model_func,
                vision_model_func=vision_model_func,
                embedding_func=embedding_func,
                lightrag=lightrag_instance,
            )
            print(f"✅ RAG instance loaded with LightRAG for doc_id: {doc_id}")
        else:
            # New document, create without LightRAG (will be initialized during processing)
            rag_instances[doc_id] = RAGAnything(
                config=config,
                llm_model_func=llm_model_func,
                vision_model_func=vision_model_func,
                embedding_func=embedding_func,
            )
            print(f"✅ RAG instance created for doc_id: {doc_id}")
        
        print(f"📂 Working directory: {doc_working_dir}")
    
    return rag_instances[doc_id]

# === WRAPPER PROCESS PDF ===
async def process_pdf(file_path: str):
    """Process PDF and store in isolated RAG system"""
    filename = os.path.basename(file_path)
    doc_id = get_doc_id(filename)
    
    print(f"📄 Processing PDF: {filename}")
    print(f"🔑 Generated doc_id: {doc_id}")
    
    # Get RAG instance untuk dokumen ini
    rag = get_rag_instance(doc_id)
    
    # Process document
    await rag.process_document_complete(
        file_path=file_path,
        output_dir=rag.config.working_dir
    )
    
    print(f"✅ PDF processed: {filename}")
    
    return doc_id, f"File {filename} berhasil diproses"

# === GENERATE SUMMARY ===
async def generate_summary(file_path: str, doc_id: str):
    """Generate summary from processed PDF"""
    try:
        filename = os.path.basename(file_path)
        print(f"📝 Generating summary for doc_id: {doc_id} ({filename})")
        
        # Get RAG instance untuk dokumen ini
        rag = get_rag_instance(doc_id)
        
        # Query untuk mendapatkan ringkasan - include filename untuk cache key unik
        result = await rag.aquery(
            f"Berikan ringkasan singkat tentang isi dokumen '{filename}' ini dalam 3-4 kalimat. Jelaskan topik utama dan poin-poin penting yang dibahas dalam dokumen ini.",
            mode="hybrid",
            top_k=5
        )
        
        summary = result if isinstance(result, str) else result.get("text", "")
        
        # Jika summary kosong atau terlalu pendek, buat fallback
        if not summary or len(summary) < 50:
            summary = f"Dokumen {filename} telah berhasil diproses dan siap untuk ditanyakan."
        
        print(f"✅ Summary generated: {summary[:100]}...")
        
        return summary
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")
        import traceback
        traceback.print_exc()
        return f"Dokumen {os.path.basename(file_path)} berhasil diproses."

# === QUERY SPECIFIC DOCUMENT ===
async def query_document(doc_id: str, question: str, top_k: int = 3):
    """Query specific document by doc_id"""
    try:
        print(f"\n🔍 Querying doc_id: {doc_id}")
        print(f"❓ Question: {question}")
        
        # Get RAG instance untuk dokumen ini
        rag = get_rag_instance(doc_id)
        
        # Query
        result = await rag.aquery(
            question,
            mode="hybrid",
            top_k=top_k
        )
        
        answer = result if isinstance(result, str) else result.get("text", "Tidak ada jawaban.")
        
        print(f"✅ Answer generated: {answer[:100]}...")
        
        return answer
        
    except Exception as e:
        print(f"❌ Error querying document {doc_id}: {e}")
        import traceback
        traceback.print_exc()
        raise e

# === LIST ALL DOCUMENTS ===
def list_documents():
    """List all processed documents"""
    return list(rag_instances.keys())

# === CLEAR DOCUMENT CACHE ===
def clear_document_cache(doc_id: str = None):
    """Clear RAG instance cache for specific or all documents"""
    if doc_id:
        if doc_id in rag_instances:
            del rag_instances[doc_id]
            print(f"🗑️ Cleared cache for doc_id: {doc_id}")
    else:
        rag_instances.clear()
        print("🗑️ Cleared all document caches")

def clear_root_storage():
    """Clear old storage files in root rag_storage directory (not in subdirectories)"""
    import shutil
    
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    
    # Files to remove from root (these are leftover from old unified storage)
    root_files = [
        "graph_chunk_entity_relation.graphml",
        "kv_store_doc_status.json",
        "kv_store_entity_chunks.json",
        "kv_store_full_docs.json",
        "kv_store_full_entities.json",
        "kv_store_full_relations.json",
        "kv_store_llm_response_cache.json",
        "kv_store_parse_cache.json",
        "kv_store_relation_chunks.json",
        "kv_store_text_chunks.json",
        "vdb_chunks.json",
        "vdb_entities.json",
        "vdb_relationships.json"
    ]
    
    deleted = []
    for filename in root_files:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            deleted.append(filename)
            print(f"🗑️ Deleted: {filepath}")
    
    if deleted:
        print(f"✅ Cleaned up {len(deleted)} old storage files from root directory")
    else:
        print("✅ Root storage is clean")
    
    return deleted

def reset_all_storage():
    """Reset all RAG storage - clear memory and delete all files"""
    import shutil
    
    # Clear memory cache first
    rag_instances.clear()
    
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    
    if os.path.exists(base_dir):
        # Remove entire directory
        shutil.rmtree(base_dir)
        print(f"🗑️ Deleted entire storage directory: {base_dir}")
    
    # Recreate empty directory
    os.makedirs(base_dir, exist_ok=True)
    print(f"✅ Created fresh storage directory: {base_dir}")
    
    return True