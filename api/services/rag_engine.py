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
    
    # Check if directory exists
    if not os.path.exists(doc_working_dir):
        return False
    
    # Check multiple possible files that indicate document was processed
    possible_files = [
        "graph_chunk_entity_relation.graphml",
        "kv_store_full_docs.json",
        "kv_store_doc_status.json",
        "vdb_entities.json"
    ]
    
    for filename in possible_files:
        filepath = os.path.join(doc_working_dir, filename)
        if os.path.exists(filepath):
            print(f"✅ Document exists check: Found {filename} for doc_id {doc_id}")
            return True
    
    return False

def get_rag_instance(doc_id: str, force_reload: bool = False):
    """Get or create RAG instance for specific document"""
    if doc_id not in rag_instances or force_reload:
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
            
            try:
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
            except Exception as e:
                print(f"⚠️ Error loading LightRAG, creating new instance: {e}")
                # Fallback: create RAGAnything tanpa lightrag, nanti akan diinit saat process
                rag_instances[doc_id] = RAGAnything(
                    config=config,
                    llm_model_func=llm_model_func,
                    vision_model_func=vision_model_func,
                    embedding_func=embedding_func,
                )
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
        
        # Cek apakah lightrag tersedia
        if not hasattr(rag, 'lightrag') or rag.lightrag is None:
            print(f"⚠️ LightRAG not initialized, trying to reload...")
            # Try to reload dengan force
            rag = get_rag_instance(doc_id, force_reload=True)
            
            # Jika masih tidak ada, coba init manual
            if not hasattr(rag, 'lightrag') or rag.lightrag is None:
                base_dir = os.getenv("WORKING_DIR", "./rag_storage")
                doc_working_dir = os.path.join(base_dir, doc_id)
                
                if check_document_exists(doc_id):
                    print(f"📂 Manually initializing LightRAG for: {doc_id}")
                    rag.lightrag = LightRAG(
                        working_dir=doc_working_dir,
                        llm_model_func=llm_model_func,
                        embedding_func=embedding_func,
                    )
                else:
                    raise Exception(f"Document {doc_id} has not been processed. Please upload and process the document first.")
        
        # Query
        result = await rag.aquery(
            question,
            mode="hybrid",
            top_k=top_k
        )
        
        answer = result if isinstance(result, str) else result.get("text", "Tidak ada jawaban.")
        
        # Jika jawaban kosong atau "[no-context]", coba fallback ke direct query
        if not answer or "[no-context]" in answer.lower() or "tidak ada jawaban" in answer.lower():
            print(f"⚠️ No context found, trying fallback with document content...")
            answer = await fallback_query_with_content(doc_id, question)
        
        print(f"✅ Answer generated: {answer[:100]}...")
        
        return answer
        
    except Exception as e:
        print(f"❌ Error querying document {doc_id}: {e}")
        import traceback
        traceback.print_exc()
        raise e

async def fallback_query_with_content(doc_id: str, question: str):
    """Fallback: Query using direct document content from kv_store"""
    import json
    
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    docs_file = os.path.join(doc_working_dir, "kv_store_full_docs.json")
    
    if not os.path.exists(docs_file):
        return "Maaf, tidak dapat menemukan konten dokumen."
    
    try:
        with open(docs_file, 'r', encoding='utf-8') as f:
            docs_data = json.load(f)
        
        # Ambil konten dari dokumen
        content_parts = []
        for key, value in docs_data.items():
            if isinstance(value, dict) and 'content' in value:
                content_parts.append(value['content'][:2000])  # Limit per chunk
            elif isinstance(value, str):
                content_parts.append(value[:2000])
        
        if not content_parts:
            return "Maaf, dokumen tidak memiliki konten yang dapat dibaca."
        
        # Gabung dan potong konten
        full_content = "\n\n".join(content_parts)[:6000]  # Limit total
        
        print(f"📄 Using fallback with {len(full_content)} chars of content")
        
        # Query langsung ke LLM dengan konten
        prompt = f"""Berdasarkan konten dokumen berikut, jawab pertanyaan pengguna dalam Bahasa Indonesia.

=== KONTEN DOKUMEN ===
{full_content}

=== PERTANYAAN ===
{question}

=== JAWABAN ===
Berikan jawaban yang jelas dan informatif berdasarkan konten dokumen di atas:"""

        answer = await llm_model_func(prompt)
        
        if answer:
            return answer
        else:
            return "Maaf, tidak dapat menghasilkan jawaban saat ini."
            
    except Exception as e:
        print(f"❌ Fallback query error: {e}")
        return f"Maaf, terjadi kesalahan saat membaca dokumen: {str(e)}"

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