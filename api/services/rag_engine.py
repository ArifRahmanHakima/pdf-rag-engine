import os
import sys
import asyncio
import hashlib
from dotenv import load_dotenv

# Fix Windows Store Python path issue with pipmaster
# We need to set a fake executable path that exists
# This must be done BEFORE importing lightrag/raganything
_original_executable = sys.executable
if 'WindowsApps' in sys.executable:
    # Find actual python.exe
    import shutil
    python_path = shutil.which('python')
    if python_path:
        sys.executable = python_path
        os.environ['PIPMASTER_PYTHON'] = python_path

# Now safe to import
from raganything import RAGAnything, RAGAnythingConfig
from lightrag import LightRAG
from sentence_transformers import SentenceTransformer
from lightrag.utils import EmbeddingFunc
from api.services.llm_wrapper import llm_model_func, vision_model_func
from api.services.timer import ProcessTimer, Timer

# Restore original executable
sys.executable = _original_executable

load_dotenv()

# Disable verbose timing for embedding (terlalu banyak noise)
Timer.set_verbose(False)

# === Load Embedding Model ===
print("⏳ Loading embedding model...")
_embed_start = __import__('time').perf_counter()
embed_model = SentenceTransformer(os.getenv("EMBEDDING_MODEL"))
print(f"✅ Embedding model loaded in {__import__('time').perf_counter() - _embed_start:.2f}s")

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

def get_doc_id(file_path: str) -> str:
    """Generate unique document ID from filename only (not full path)"""
    # Ambil nama file saja, bukan full path
    filename = os.path.basename(file_path)
    # Gunakan hash untuk ID yang konsisten
    return hashlib.md5(filename.encode()).hexdigest()[:16]

def check_document_exists(doc_id: str) -> bool:
    """Check if document has been processed before (storage exists)"""
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    
    # Check if essential files exist
    graph_file = os.path.join(doc_working_dir, "graph_chunk_entity_relation.graphml")
    vdb_chunks_file = os.path.join(doc_working_dir, "vdb_chunks.json")
    
    # Dokumen dianggap ada jika ada graph file ATAU vdb_chunks
    return os.path.exists(graph_file) or os.path.exists(vdb_chunks_file)

def check_has_content(doc_id: str) -> bool:
    """Check if document has actual content (entities/chunks)"""
    import json
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    
    vdb_chunks_file = os.path.join(doc_working_dir, "vdb_chunks.json")
    
    try:
        if os.path.exists(vdb_chunks_file):
            with open(vdb_chunks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Check if there are any chunks
                if isinstance(data, dict) and len(data) > 0:
                    return True
                elif isinstance(data, list) and len(data) > 0:
                    return True
    except:
        pass
    
    return False

def get_rag_instance(doc_id: str):
    """Get or create RAG instance for specific document"""
    if doc_id not in rag_instances:
        with Timer(f"Create RAG Instance ({doc_id})"):
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
                
                with Timer(f"Load LightRAG ({doc_id})"):
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
    """Process PDF and store in isolated RAG system with detailed timing"""
    filename = os.path.basename(file_path)
    doc_id = get_doc_id(filename)
    
    # Initialize timer
    timer = ProcessTimer(f"UPLOAD & PROCESS: {filename}")
    timer.start()
    
    print(f"🔑 Document ID: {doc_id}")
    
    # Step 1: Initialize RAG Instance
    timer.step("1. Initialize RAG Instance")
    rag = get_rag_instance(doc_id)
    
    # Step 2: Parse PDF with MinerU
    timer.step("2. Parse PDF (MinerU)")
    # Note: process_document_complete includes parsing
    await rag.process_document_complete(
        file_path=file_path,
        output_dir=rag.config.working_dir
    )
    
    # Finish and get total time
    total_time = timer.finish()
    
    return doc_id, f"File {filename} berhasil diproses dalam {total_time:.1f} detik"

# === GENERATE SUMMARY ===
async def generate_summary(file_path: str, doc_id: str):
    """Generate summary from processed PDF with timing"""
    filename = os.path.basename(file_path)
    
    # Initialize timer
    timer = ProcessTimer(f"GENERATE SUMMARY: {filename}")
    timer.start()
    
    try:
        # Step 1: Get RAG instance
        timer.step("3. Get RAG Instance")
        rag = get_rag_instance(doc_id)
        
        # Step 2: Query LLM for summary
        timer.step("4. LLM Query (Summary)")
        
        summary = ""
        
        try:
            result = await rag.aquery(
                f"Berikan ringkasan singkat tentang isi dokumen '{filename}' ini dalam 3-4 kalimat. Jelaskan topik utama dan poin-poin penting yang dibahas dalam dokumen ini.",
                mode="hybrid",
                top_k=5
            )
            
            summary = result if isinstance(result, str) else result.get("text", "")
        except ValueError:
            # No LightRAG - fallback
            pass
        
        # Handle no-context atau summary yang terlalu pendek/gagal
        if not summary or len(summary) < 50 or "[no-context]" in summary.lower() or "sorry" in summary.lower():
            # Fallback: generate summary dari parsed content
            print("⚠️ RAG summary failed, using fallback from parsed content...")
            timer.step("4b. Fallback Summary")
            summary = await generate_summary_from_content(doc_id, filename)
        
        # Finish timer
        timer.finish()
        
        print(f"✅ Summary: {summary[:100]}...")
        
        return summary
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")
        import traceback
        traceback.print_exc()
        return f"Dokumen {os.path.basename(file_path)} berhasil diproses."

async def generate_summary_from_content(doc_id: str, filename: str):
    """Generate summary directly from parsed markdown content"""
    import glob
    
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    
    # Cari file markdown hasil parsing
    md_files = glob.glob(os.path.join(doc_working_dir, "**", "*.md"), recursive=True)
    
    if not md_files:
        return f"Dokumen '{filename}' berhasil diproses dan siap untuk ditanyakan."
    
    # Baca konten markdown
    content = ""
    for md_file in md_files[:3]:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content += f.read() + "\n\n"
        except:
            pass
    
    if not content or len(content) < 50:
        return f"Dokumen '{filename}' berhasil diproses dan siap untuk ditanyakan."
    
    # Truncate if too long
    max_chars = 3000
    if len(content) > max_chars:
        content = content[:max_chars] + "..."
    
    try:
        from api.services.llm_wrapper import llm_model_func
        
        prompt = f"""Berikan ringkasan singkat tentang isi dokumen berikut dalam 3-4 kalimat. Jelaskan topik utama dan poin-poin penting.

KONTEN DOKUMEN:
{content}

RINGKASAN:"""
        
        summary = await llm_model_func(prompt)
        
        if summary and len(summary) > 50 and "[no-context]" not in summary.lower():
            return summary
            
    except Exception as e:
        print(f"❌ Fallback summary error: {e}")
    
    return f"Dokumen '{filename}' berhasil diproses dan siap untuk ditanyakan. Silakan ajukan pertanyaan tentang isi dokumen ini."

# === QUERY SPECIFIC DOCUMENT ===
async def query_document(doc_id: str, question: str, top_k: int = 3):
    """Query specific document by doc_id with timing"""
    
    # Initialize timer
    timer = ProcessTimer(f"QUERY: {question[:40]}...")
    timer.start()
    
    print(f"📄 Doc ID: {doc_id}")
    
    try:
        # Step 1: Get RAG instance
        timer.step("1. Get RAG Instance")
        rag = get_rag_instance(doc_id)
        
        # Step 2: RAG Query
        timer.step("2. RAG Query (hybrid)")
        
        try:
            result = await rag.aquery(
                question,
                mode="hybrid",
                top_k=top_k
            )
            
            answer = result if isinstance(result, str) else result.get("text", "")
            
            # Check if answer is empty or no-context
            if not answer or "[no-context]" in answer.lower() or len(answer) < 20:
                # Fallback: coba query dengan mode naive (text only)
                print("⚠️ Hybrid query returned no context, trying naive mode...")
                timer.step("2b. RAG Query (naive fallback)")
                
                try:
                    result = await rag.aquery(
                        question,
                        mode="naive",
                        top_k=top_k
                    )
                    answer = result if isinstance(result, str) else result.get("text", "")
                except:
                    pass
                
                # Jika masih gagal, coba baca langsung dari parsed content
                if not answer or "[no-context]" in answer.lower() or len(answer) < 20:
                    answer = await fallback_query_from_parsed_content(doc_id, question)
            
        except ValueError as ve:
            # No LightRAG instance - fallback to parsed content
            print(f"⚠️ LightRAG not available, using fallback: {ve}")
            answer = await fallback_query_from_parsed_content(doc_id, question)
        
        # Final check
        if not answer or "[no-context]" in answer.lower():
            answer = "Maaf, saya tidak menemukan informasi yang relevan untuk menjawab pertanyaan tersebut dalam dokumen ini. Silakan coba pertanyaan lain."
        
        # Finish timer
        timer.finish()
        
        print(f"✅ Answer: {answer[:100]}...")
        
        return answer
        
    except Exception as e:
        print(f"❌ Error querying document {doc_id}: {e}")
        import traceback
        traceback.print_exc()
        raise e

async def fallback_query_from_parsed_content(doc_id: str, question: str):
    """Fallback: query using parsed markdown content directly"""
    import os
    import glob
    
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    
    # Cari file markdown hasil parsing
    md_files = glob.glob(os.path.join(doc_working_dir, "**", "*.md"), recursive=True)
    
    if not md_files:
        return ""
    
    # Baca konten markdown
    content = ""
    for md_file in md_files[:3]:  # Limit to first 3 files
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content += f.read() + "\n\n"
        except:
            pass
    
    if not content:
        return ""
    
    # Truncate content if too long
    max_chars = 4000
    if len(content) > max_chars:
        content = content[:max_chars] + "..."
    
    # Query LLM directly with the content
    try:
        from api.services.llm_wrapper import llm_model_func
        
        prompt = f"""Berdasarkan konten dokumen berikut, jawab pertanyaan dengan bahasa Indonesia yang jelas dan ringkas.

KONTEN DOKUMEN:
{content}

PERTANYAAN: {question}

JAWABAN:"""
        
        answer = await llm_model_func(prompt)
        return answer
    except Exception as e:
        print(f"❌ Fallback query error: {e}")
        return ""

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

# Alias for backward compatibility
def clear_rag_instance(doc_id: str):
    """Alias for clear_document_cache"""
    clear_document_cache(doc_id)

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