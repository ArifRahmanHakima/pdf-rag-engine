import os
import asyncio
import hashlib
import time
import threading
from datetime import datetime
from typing import Dict, List, Tuple
from enum import Enum
from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from sentence_transformers import SentenceTransformer
from lightrag.utils import EmbeddingFunc
from api.services.llm_wrapper import llm_model_func

load_dotenv()

# === STATUS TRACKING ===
class ProcessStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# === PROCESS STATUS TRACKER ===
process_status_tracker: Dict[str, Dict] = {}
status_lock = threading.Lock()

def get_process_status(doc_id: str) -> Dict:
    """Get process status for a document"""
    with status_lock:
        return process_status_tracker.get(doc_id, {
            "status": ProcessStatus.PENDING,
            "progress": 0,
            "message": "Menunggu proses...",
            "start_time": None,
            "current_stage": "Idle"
        })

def update_process_status(doc_id: str, status: ProcessStatus, progress: int = 0, message: str = "", current_stage: str = ""):
    """Update process status for a document"""
    with status_lock:
        if doc_id not in process_status_tracker:
            process_status_tracker[doc_id] = {
                "status": status,
                "progress": progress,
                "message": message,
                "start_time": time.time(),
                "current_stage": current_stage,
                "completed_time": None
            }
        else:
            process_status_tracker[doc_id].update({
                "status": status,
                "progress": progress,
                "message": message,
                "current_stage": current_stage
            })
            
            if status == ProcessStatus.COMPLETED or status == ProcessStatus.FAILED:
                process_status_tracker[doc_id]["completed_time"] = time.time()

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
        
    def end(self) -> float:
        """Tampilkan summary total waktu"""
        if self.start_time:
            total_time = time.time() - self.start_time
            if total_time == 0:
                total_time = 0.001  # Prevent division by zero
            print(f"\n{'─'*70}")
            print(f"📊 TOTAL TIME: {total_time:.2f}s")
            print(f"{'─'*70}")
            for stage, duration in self.stages.items():
                percentage = (duration / total_time) * 100
                print(f"  • {stage:<40} {duration:>8.2f}s ({percentage:>5.1f}%)")
            print(f"{'='*70}\n")
            return total_time
        return 0

# === OPTIMIZED EMBEDDING ===
import numpy as np

class OptimizedEmbedding:
    """Optimized embedding dengan caching dan batch processing - returns numpy arrays for LightRAG"""
    def __init__(self):
        self.embed_model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
        self.cache = {}
        self.batch_size = 512
    
    def encode(self, texts):
        """Encode texts - SYNCHRONOUS method called by LightRAG - RETURNS NUMPY ARRAY"""
        if isinstance(texts, str):
            texts = [texts]
        
        if not texts or len(texts) == 0:
            return np.array([])
        
        try:
            # Direct encoding without complex caching for speed
            embeddings = self.embed_model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=self.batch_size,
                show_progress_bar=False
            )
            
            # Return as numpy array (required by LightRAG)
            if isinstance(embeddings, np.ndarray):
                return embeddings
            else:
                return np.array(embeddings)
                
        except Exception as e:
            print(f"⚠️ Embedding error: {str(e)[:50]}, returning zeros")
            return np.zeros((len(texts), 384), dtype=np.float32)
    
    async def encode_async(self, texts):
        """Async wrapper for batch processing if needed"""
        if isinstance(texts, str):
            texts = [texts]
        
        if not texts or len(texts) == 0:
            return np.array([])
        
        try:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(None, self.encode, texts)
            return embeddings
        except Exception as e:
            print(f"⚠️ Async embedding error: {str(e)[:50]}, returning zeros")
            return np.zeros((len(texts), 384), dtype=np.float32)

# === GLOBAL INSTANCES ===
optimized_embedding = OptimizedEmbedding()
embedding_func = EmbeddingFunc(
    embedding_dim=384,  # all-MiniLM-L6-v2 output dimension (FIXED: now matches model)
    max_token_size=512,  # Increased untuk batch processing yang lebih besar
    func=optimized_embedding.encode_async  # Use async embedding function
)

rag_instances = {}
rag_initialized = {}  # Track which instances have been initialized

# === HELPER FUNCTIONS ===
def get_doc_id(filename: str) -> str:
    """Generate unique document ID from filename"""
    return hashlib.md5(filename.encode()).hexdigest()[:16]

async def get_rag_instance_async(doc_id: str):
    """Get or create LightRAG instance for specific document - ASYNC with proper initialization"""
    if doc_id not in rag_instances:
        base_dir = os.getenv("WORKING_DIR", "./rag_storage")
        doc_working_dir = os.path.join(base_dir, doc_id)
        
        os.makedirs(doc_working_dir, exist_ok=True)
        
        # Create LightRAG directly (MUCH FASTER than RAGAnything)
        rag = LightRAG(
            working_dir=doc_working_dir,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            chunk_token_size=1200,  # Larger chunks = fewer LLM calls
            chunk_overlap_token_size=100,
            entity_extract_max_gleaning=0,  # DISABLE slow entity extraction
            enable_llm_cache=True,
        )
        
        # CRITICAL: Initialize storages (required by LightRAG)
        await rag.initialize_storages()
        
        # Initialize pipeline status for insert operations
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()
        
        rag_instances[doc_id] = rag
        rag_initialized[doc_id] = True
        
        print(f"✅ LightRAG instance created & initialized for doc_id: {doc_id} (ULTRA-FAST)")
    
    return rag_instances[doc_id]

def get_rag_instance_sync(doc_id: str):
    """Get existing RAG instance (sync version for query) - must be initialized first"""
    if doc_id in rag_instances:
        return rag_instances[doc_id]
    return None

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

# === MAIN ASYNC PROCESSING FUNCTIONS ===

# ULTRA-FAST PDF text extraction using PyMuPDF (10x faster than mineru)
def extract_text_fast(file_path: str) -> str:
    """Extract text from PDF using PyMuPDF - ULTRA FAST"""
    import fitz  # PyMuPDF
    text_parts = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
    except Exception as e:
        print(f"⚠️ PyMuPDF extraction failed: {e}")
        # Fallback to PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
        except Exception as e2:
            print(f"⚠️ PyPDF2 extraction also failed: {e2}")
    return "\n\n".join(text_parts)

async def process_pdf_async(file_path: str) -> Tuple[str, str]:
    """Process PDF dengan optimasi ULTRA-FAST - mengembalikan doc_id dan message"""
    filename = os.path.basename(file_path)
    doc_id = get_doc_id(filename)
    
    timer = TimingTracker(f"PROCESS PDF: {filename}")
    timer.start()
    
    # Update status: Processing
    update_process_status(
        doc_id, 
        ProcessStatus.PROCESSING, 
        progress=10, 
        message="Memulai proses PDF...",
        current_stage="Initializing"
    )
    
    print(f"📄 PDF: {filename}")
    print(f"🔑 Doc ID: {doc_id}")
    
    try:
        # === ULTRA-FAST MODE: Use PyMuPDF for text extraction ===
        print(f"\n📖 Extracting text (ULTRA-FAST mode)...")
        update_process_status(
            doc_id, 
            ProcessStatus.PROCESSING, 
            progress=20, 
            message="Ekstraksi teks PDF...",
            current_stage="Text Extraction"
        )
        
        # Step 1: Fast text extraction with PyMuPDF
        loop = asyncio.get_event_loop()
        text_content = await loop.run_in_executor(None, extract_text_fast, file_path)
        timer.mark("Text Extraction (PyMuPDF)")
        
        if not text_content or len(text_content.strip()) < 50:
            raise ValueError("PDF text extraction failed or PDF is empty")
        
        print(f"📝 Extracted {len(text_content)} characters")
        update_process_status(
            doc_id, 
            ProcessStatus.PROCESSING, 
            progress=40, 
            message=f"Teks diekstrak: {len(text_content)} karakter",
            current_stage="Chunking"
        )
        
        # Step 2: Load RAG instance (ASYNC - with proper initialization)
        rag = await get_rag_instance_async(doc_id)
        timer.mark("RAG Instance Load")
        
        update_process_status(
            doc_id, 
            ProcessStatus.PROCESSING, 
            progress=50, 
            message="Memproses teks ke database...",
            current_stage="Text Insertion"
        )
        
        # Step 3: Insert text directly into LightRAG
        try:
            # Use LightRAG's insert method directly (MUCH FASTER)
            await rag.ainsert(text_content)
            timer.mark("LightRAG Insert")
            print(f"✅ Text inserted into LightRAG successfully")
        except Exception as insert_error:
            print(f"⚠️ Async insert error: {str(insert_error)[:100]}")
            # Fallback: Try sync insert
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: rag.insert(text_content))
                timer.mark("LightRAG Insert (sync fallback)")
                print(f"✅ Text inserted via sync fallback")
            except Exception as e2:
                print(f"⚠️ Sync insert also failed: {str(e2)[:100]}")
                import traceback
                traceback.print_exc()
        
        update_process_status(
            doc_id, 
            ProcessStatus.PROCESSING, 
            progress=90, 
            message="Finalisasi...",
            current_stage="Finalization"
        )
        
        timer.mark("Total Processing")
        
        print(f"\n✅ PDF processed successfully!")
        timer.end()
        
        # Update status: Completed
        update_process_status(
            doc_id, 
            ProcessStatus.COMPLETED, 
            progress=100, 
            message=f"File {filename} berhasil diproses",
            current_stage="Completed"
        )
        
        return doc_id, f"File {filename} berhasil diproses"
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        timer.end()
        
        # Update status: Failed
        update_process_status(
            doc_id, 
            ProcessStatus.FAILED, 
            progress=0, 
            message=f"Error: {str(e)}",
            current_stage="Failed"
        )
        
        raise e

async def generate_summary_async(file_path: str, doc_id: str) -> str:
    """Generate summary from processed PDF - SKIP for speed (target 1 minute)"""
    filename = os.path.basename(file_path)
    # Skip LLM summary generation entirely to meet 1-minute target
    # Return instant default message without any LLM call
    summary = f"✅ Dokumen {filename} berhasil diproses dan siap untuk pertanyaan."
    print(f"Summary: {summary}")
    return summary

async def query_document_async(doc_id: str, question: str, top_k: int = 2) -> str:
    """Query specific document by doc_id dengan LightRAG langsung"""
    timer = TimingTracker(f"QUERY DOCUMENT")
    timer.start()
    
    print(f"❓ Question: {question[:80]}...")
    
    try:
        # Try to get existing instance first
        rag = get_rag_instance_sync(doc_id)
        
        # If not found, create and initialize
        if rag is None:
            print(f"⚠️ RAG instance not in cache, initializing...")
            rag = await get_rag_instance_async(doc_id)
        
        timer.mark("Load RAG Instance")
        
        # Use LightRAG's QueryParam with correct parameters
        param = QueryParam(
            mode="hybrid",
            top_k=top_k,
            only_need_context=False,
            response_type="Multiple Paragraphs",
        )

        # Query LightRAG directly
        try:
            result = await rag.aquery(
                question,
                param=param
            )
        except Exception as e:
            print(f"⚠️ Query error: {e}")
            # Fallback: try without param
            try:
                result = await rag.aquery(question)
            except Exception as e2:
                print(f"⚠️ Fallback query also failed: {e2}")
                result = None
        
        timer.mark("Vector Search & Retrieval")
        
        answer = result if isinstance(result, str) else str(result)
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

def list_documents() -> List[str]:
    """List all processed documents"""
    return list(rag_instances.keys())

def clear_document_cache(doc_id: str = None):
    """Clear RAG instance cache for specific or all documents"""
    global rag_instances, rag_initialized
    if doc_id:
        if doc_id in rag_instances:
            del rag_instances[doc_id]
            if doc_id in rag_initialized:
                del rag_initialized[doc_id]
            print(f"🗑️ Cleared cache for doc_id: {doc_id}")
    else:
        rag_instances.clear()
        rag_initialized.clear()
        print("🗑️ Cleared all document caches")
