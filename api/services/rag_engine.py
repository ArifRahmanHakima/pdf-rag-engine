import os
import asyncio
import hashlib
import time
from datetime import datetime
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
        lambda: embed_model.encode(
            texts, normalize_embeddings=True, 
            batch_size=16
        )
    )

embedding_func = EmbeddingFunc(
    embedding_dim=384,
    max_token_size=512,
    func=async_embed
)

# === Dictionary untuk menyimpan RAG instance per dokumen ===
rag_instances = {}

# === TIMING TRACKER ===
class TimingTracker:
    """Track timing untuk setiap tahap proses"""
    def __init__(self, process_name: str):
        self.process_name = process_name
        self.start_time = None
        self.stages = {}
        
    def start(self):
        self.start_time = time.time()
        print(f"\n{'='*70}")
        print(f"🚀 START: {self.process_name}")
        print(f"{'='*70}")
        
    def mark(self, stage_name: str):
        """Mark waktu untuk tahap tertentu"""
        current_time = time.time()
        if self.start_time:
            elapsed = current_time - self.start_time
            self.stages[stage_name] = elapsed
            print(f"⏱️  [{stage_name}] {elapsed:.2f}s")
        
    def end(self):
        """Tampilkan summary total waktu"""
        if self.start_time:
            total_time = time.time() - self.start_time
            print(f"\n{'─'*70}")
            print(f"📊 TOTAL TIME: {total_time:.2f}s")
            print(f"{'─'*70}")
            for stage, duration in self.stages.items():
                percentage = (duration / total_time) * 100
                print(f"  • {stage:<40} {duration:>8.2f}s ({percentage:>5.1f}%)")
            print(f"{'='*70}\n")
            return total_time

def get_doc_id(filename: str) -> str:
    """Generate unique document ID from filename"""
    return hashlib.md5(filename.encode()).hexdigest()[:16]

def get_rag_instance(doc_id: str):
    """Get or create RAG instance for specific document"""
    if doc_id not in rag_instances:
        base_dir = os.getenv("WORKING_DIR", "./rag_storage")
        doc_working_dir = os.path.join(base_dir, doc_id)
        
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
    
    timer = TimingTracker(f"PROCESS PDF: {filename}")
    timer.start()
    
    print(f"📄 PDF: {filename}")
    print(f"🔑 Doc ID: {doc_id}")
    
    try:
        # Tahap 1: Load RAG instance
        rag = get_rag_instance(doc_id)
        timer.mark("RAG Instance Load")
        
        # Tahap 2: Parse PDF
        parse_start = time.time()
        print(f"\n📖 Parsing PDF...")
        await rag.process_document_complete(
            file_path=file_path,
            output_dir=rag.config.working_dir
        )
        timer.mark("PDF Parsing & Chunking")
        
        # Tahap 3: Embedding
        timer.mark("Embedding & Vector Storage")
        
        print(f"\n✅ PDF processed successfully!")
        timer.end()
        
        return doc_id, f"File {filename} berhasil diproses"
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        timer.end()
        raise e

# === GENERATE SUMMARY ===
async def generate_summary(file_path: str, doc_id: str):
    """Generate summary from processed PDF"""
    filename = os.path.basename(file_path)
    timer = TimingTracker(f"GENERATE SUMMARY: {filename}")
    timer.start()
    
    try:
        print(f"📝 Generating summary...")
        
        rag = get_rag_instance(doc_id)
        timer.mark("Load RAG Instance")
        
        # Retrieve relevant content
        query_start = time.time()
        result = await rag.aquery(
            "Berikan ringkasan singkat tentang isi dokumen ini dalam 3-4 kalimat. Jelaskan topik utama dan poin-poin penting yang dibahas.",
            mode="hybrid",
            top_k=3
        )
        query_duration = time.time() - query_start
        timer.mark("Vector Search & Retrieval")
        
        summary = result if isinstance(result, str) else result.get("text", "")
        timer.mark("LLM Generation")
        
        # Remove references
        summary = remove_references(summary)
        timer.mark("Post-processing")
        
        if not summary or len(summary) < 50:
            summary = f"Dokumen {filename} telah berhasil diproses dan siap untuk ditanyakan."
        
        print(f"\n✅ Summary: {summary[:100]}...")
        timer.end()
        
        return summary
        
    except Exception as e:
        print(f"\n❌ ERROR generating summary: {str(e)}")
        import traceback
        traceback.print_exc()
        timer.end()
        return f"Dokumen {filename} berhasil diproses."

# === HELPER: Remove References from Answer ===
def remove_references(text: str) -> str:
    """Remove References section from answer text"""
    import re
    
    text = re.sub(
        r'\n*(?:References?|Referensi)[\s\n]*(?:\*|\-|\d+\.)?.*?(?=\n\n|\Z)',
        '',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    text = re.sub(r'\s*\[\d+\]\s*(?:[A-Za-z]|\()', r'\g<0>', text)
    
    text = re.sub(
        r'\s*\[.*?\.pdf\]\(.*?\.pdf\)',
        '',
        text,
        flags=re.IGNORECASE
    )
    
    text = re.sub(r'\n\n+', '\n\n', text)
    text = text.strip()
    
    return text

# === QUERY SPECIFIC DOCUMENT ===
async def query_document(doc_id: str, question: str, top_k: int = 3):
    """Query specific document by doc_id"""
    timer = TimingTracker(f"QUERY DOCUMENT")
    timer.start()
    
    print(f"❓ Question: {question[:80]}...")
    
    try:
        rag = get_rag_instance(doc_id)
        timer.mark("Load RAG Instance")
        
        # Vector search & retrieval
        search_start = time.time()
        result = await rag.aquery(
            question,
            mode="hybrid",
            top_k=top_k
        )
        timer.mark("Vector Search & Retrieval")
        
        answer = result if isinstance(result, str) else result.get("text", "Tidak ada jawaban.")
        timer.mark("LLM Generation")
        
        answer = remove_references(answer)
        timer.mark("Post-processing & Remove References")
        
        print(f"\n✅ Answer: {answer[:100]}...")
        timer.end()
        
        return answer
        
    except Exception as e:
        print(f"\n❌ ERROR querying: {str(e)}")
        import traceback
        traceback.print_exc()
        timer.end()
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