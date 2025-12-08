import os
import asyncio
import hashlib
from dotenv import load_dotenv
from raganything import RAGAnything, RAGAnythingConfig
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
            enable_image_processing=True,
            enable_table_processing=True,
            enable_equation_processing=True,
        )
        
        rag_instances[doc_id] = RAGAnything(
            config=config,
            llm_model_func=llm_model_func,
            vision_model_func=vision_model_func,
            embedding_func=embedding_func,
        )
        
        print(f"✅ RAG instance created for doc_id: {doc_id}")
    
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
        print(f"📝 Generating summary for doc_id: {doc_id}")
        
        # Get RAG instance untuk dokumen ini
        rag = get_rag_instance(doc_id)
        
        # Query untuk mendapatkan ringkasan
        result = await rag.aquery(
            "Berikan ringkasan singkat tentang isi dokumen ini dalam 3-4 kalimat. Jelaskan topik utama dan poin-poin penting yang dibahas.",
            mode="hybrid",
            top_k=5
        )
        
        summary = result if isinstance(result, str) else result.get("text", "")
        
        # Jika summary kosong atau terlalu pendek, buat fallback
        if not summary or len(summary) < 50:
            summary = f"Dokumen {os.path.basename(file_path)} telah berhasil diproses dan siap untuk ditanyakan."
        
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