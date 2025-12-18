"""
FastAPI Server - EXACT SAME LOGIC AS main_openrouter.py
Copy-paste flow: Create RAG → Initialize → Ingest → Query
"""

import os, json, time, asyncio, shutil, io, sys
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

# Set LightRAG timeout BEFORE imports - prevent long-running tasks
os.environ["LIGHTRAG_TIMEOUT"] = "300"  # 5 minutes for entity/relation extraction

# Same logging setup as main_openrouter.py
import logging
logging.getLogger("lightrag").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("easyocr").setLevel(logging.ERROR)

from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Same imports as main_openrouter.py
from raganything.config import RAGAnythingConfig
from embedding_qwen import load_embedding_model, get_embedding_func
from llm_openrouter import llm_model_func_openrouter
from lightrag import LightRAG
from search_logic import search_chunks_strict

# Import extraction - EXACT SAME from main_openrouter.py
from main_openrouter import extract_text_from_pdf_with_ocr

# Import table processor for formatting tables
try:
    from table_processor import TableProcessor
    TABLE_PROCESSOR = TableProcessor()
    print("[✓] Table processor loaded")
except Exception as e:
    print(f"[!] Table processor not available: {e}")
    TABLE_PROCESSOR = None

print("\n[*] Starting RAG Server (same logic as main_openrouter.py)...\n")

# Same config as main_openrouter.py
config = RAGAnythingConfig()
WORKING_DIR = config.working_dir
SESSIONS_DIR = Path(WORKING_DIR) / "pdf_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Global state
embedding_func = None
rag_instance = None
session_status = {}

class QueryRequest(BaseModel):
    session_id: str
    doc_id: str
    question: str

# ===== HELPERS - SAME AS main_openrouter.py =====
def _load_embedding_model():
    """Load embedding model - returns embedding_func"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    load_embedding_model()
    sys.stdout = old_stdout
    
    embedding_func = get_embedding_func()
    print("[✓] Qwen embedding model loaded\n")
    return embedding_func

def get_next_session_id() -> str:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    existing = [d for d in SESSIONS_DIR.iterdir() if d.is_dir()]
    if not existing:
        return "folder_1"
    
    numbers = []
    for d in existing:
        try:
            num = int(d.name.split("_")[1])
            numbers.append(num)
        except:
            pass
    
    return f"folder_{max(numbers) + 1 if numbers else 1}"

def get_session_metadata(session_id: str):
    metadata_file = SESSIONS_DIR / session_id / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            return json.load(f)
    return None

def save_session_metadata(session_id: str, metadata: dict):
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    with open(session_dir / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

# ===== INGEST - EXACT LOGIC FROM main_openrouter.py =====
async def ingest_pdf_async(session_id: str, pdf_path: str, filename: str, doc_id: str):
    """Ingest - SAME as main_openrouter.py but save chunks PER-DOCUMENT"""
    global rag_instance
    
    try:
        print(f"\n[*] Processing {filename}", flush=True)
        file_start = time.time()
        
        # Extract text with easyocr - EXACT SAME
        print(f"    Extracting text with OCR...", end='', flush=True)
        ocr_start = time.time()
        text = extract_text_from_pdf_with_ocr(pdf_path, use_ocr=True)
        ocr_time = time.time() - ocr_start
        print(f" [{ocr_time:.2f}s]", flush=True)
        
        if not text.strip():
            print(f"[!] No text extracted\n", flush=True)
            session_status[session_id]["status"] = "error"
            return False
        
        # Insert into RAG - EXACT SAME
        print(f"    Inserting into RAG (knowledge graph)...", end='', flush=True)
        rag_start = time.time()
        # Add document metadata to text for tracking
        text_with_doc_id = f"[DOC_ID:{doc_id}]\n{text}"
        await rag_instance.ainsert(text_with_doc_id)
        rag_time = time.time() - rag_start
        print(f" [{rag_time:.2f}s]", flush=True)
        
        file_time = time.time() - file_start
        
        # Save chunks PER-DOCUMENT (not mixed together!)
        session_dir = SESSIONS_DIR / session_id
        src_chunks = Path(WORKING_DIR) / "kv_store_text_chunks.json"
        
        # Create document-specific chunk directory
        doc_chunks_dir = session_dir / "documents" / doc_id
        doc_chunks_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy chunks file for THIS document ONLY
        # Note: LightRAG stores all chunks in global file, we copy for per-doc access
        if src_chunks.exists():
            dst_chunks = doc_chunks_dir / "chunks.json"
            # COPY the entire chunks file (same as global)
            # Each document gets reference to all chunks
            # Search function will handle filtering by relevance
            shutil.copy(src_chunks, dst_chunks)
            print(f"[✓] Chunks reference saved to document {doc_id}\n")
        
        num_pages = text.count("=== Page")
        
        # Update session document list
        session_docs_file = session_dir / "documents.json"
        docs = {}
        if session_docs_file.exists():
            with open(session_docs_file) as f:
                docs = json.load(f)
        
        docs[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "upload_time": datetime.now().isoformat(),
            "pages": num_pages,
            "size": len(text)
        }
        
        with open(session_docs_file, 'w') as f:
            json.dump(docs, f, indent=2)
        
        # Update status - mark first document as selected by default
        if session_id not in session_status:
            session_status[session_id] = {"status": "ready", "selected_doc": doc_id}
        else:
            session_status[session_id]["status"] = "ready"
            if "selected_doc" not in session_status[session_id]:
                session_status[session_id]["selected_doc"] = doc_id
        
        print(f"[✓] Ingested in {file_time:.2f}s total (OCR: {ocr_time:.2f}s, RAG: {rag_time:.2f}s)\n", flush=True)
        return True
    
    except Exception as e:
        print(f"[!] Error: {str(e)[:80]}\n", flush=True)
        import traceback
        traceback.print_exc()
        session_status[session_id]["status"] = "error"
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_func, rag_instance
    
    # Startup - EXACT SAME as main_openrouter.py main()
    print("[*] Initializing system...")
    
    # Load embedding model
    embedding_func = _load_embedding_model()
    
    # Create RAG - EXACT SAME
    rag_instance = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=llm_model_func_openrouter,
        embedding_func=embedding_func,
    )
    
    # Initialize storages - EXACT SAME
    await rag_instance.initialize_storages()
    try:
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()
    except:
        pass
    
    print("[✓] System ready\n")
    
    yield
    
    print("\n[*] Shutting down...")

# ===== FastAPI App =====
app = FastAPI(title="RAG Chatbot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("="*70)
print("[RAG CHATBOT SERVER]")
print("="*70)
print(f"[*] EXACT same logic as main_openrouter.py")
print("="*70 + "\n")

# ===== ENDPOINTS =====
@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    try:
        global rag_instance
        
        if rag_instance is None:
            return JSONResponse(content={"success": False, "error": "RAG not ready"})
        
        session_id = get_next_session_id()
        session_dir = SESSIONS_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unique doc_id from filename (remove extension)
        doc_id = Path(file.filename).stem
        doc_upload_dir = session_dir / "documents" / doc_id
        doc_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save PDF
        pdf_path = doc_upload_dir / file.filename
        with open(pdf_path, 'wb') as f:
            f.write(await file.read())
        
        # Save metadata
        save_session_metadata(session_id, {
            "session_id": session_id,
            "filename": file.filename,
            "upload_time": datetime.now().isoformat(),
            "status": "ingesting"
        })
        
        session_status[session_id] = {
            "status": "ingesting",
            "progress": "Processing...",
            "selected_doc": doc_id
        }
        
        # Background ingest - PASS doc_id
        if background_tasks:
            background_tasks.add_task(ingest_pdf_async, session_id, str(pdf_path), file.filename, doc_id)
        
        return JSONResponse(content={
            "success": True,
            "session_id": session_id,
            "doc_id": doc_id,
            "filename": file.filename
        })
    
    except Exception as e:
        print(f"[!] Upload error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})

@app.get("/api/documents/{session_id}")
async def get_documents(session_id: str):
    """Get list of documents in a session"""
    try:
        session_dir = SESSIONS_DIR / session_id
        docs_file = session_dir / "documents.json"
        
        if not docs_file.exists():
            return JSONResponse(content={"success": True, "documents": []})
        
        with open(docs_file) as f:
            docs = json.load(f)
        
        docs_list = list(docs.values())
        return JSONResponse(content={
            "success": True,
            "documents": docs_list,
            "selected_doc": session_status.get(session_id, {}).get("selected_doc", None)
        })
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

@app.post("/api/select-document/{session_id}")
async def select_document(session_id: str, doc_id: str):
    """Switch to a different document in the session"""
    try:
        session_status[session_id]["selected_doc"] = doc_id
        return JSONResponse(content={
            "success": True,
            "selected_doc": doc_id
        })
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

@app.get("/api/sessions")
async def list_sessions():
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for sd in SESSIONS_DIR.iterdir():
            if sd.is_dir():
                m = get_session_metadata(sd.name)
                if m:
                    sessions.append(m)
        
        return JSONResponse(content={
            "success": True,
            "sessions": sorted(sessions, key=lambda x: x.get("upload_time", ""), reverse=True)
        })
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    try:
        if session_id not in session_status:
            return JSONResponse(content={"success": False, "error": "Not found"})
        
        status = session_status[session_id]
        return JSONResponse(content={
            "success": True,
            "session_id": session_id,
            "status": status.get("status"),
            "progress": status.get("progress"),
            "summary": status.get("summary", "")
        })
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

@app.get("/api/pdf/{session_id}/{doc_id}")
async def get_pdf(session_id: str, doc_id: str):
    try:
        session_dir = SESSIONS_DIR / session_id
        doc_dir = session_dir / "documents" / doc_id
        pdfs = list(doc_dir.glob("*.pdf"))
        if not pdfs:
            return JSONResponse(content={"success": False, "error": "PDF not found"})
        
        return FileResponse(pdfs[0], media_type="application/pdf")
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

# Fallback endpoint untuk kompatibilitas (ambil PDF pertama dari session)
@app.get("/api/pdf/{session_id}")
async def get_pdf_fallback(session_id: str):
    try:
        session_dir = SESSIONS_DIR / session_id
        doc_dirs = [d for d in (session_dir / "documents").iterdir() if d.is_dir()]
        if doc_dirs:
            pdfs = list(doc_dirs[0].glob("*.pdf"))
            if pdfs:
                return FileResponse(pdfs[0], media_type="application/pdf")
        return JSONResponse(content={"success": False, "error": "PDF not found"})
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

@app.delete("/api/delete-document/{session_id}/{doc_id}")
async def delete_document(session_id: str, doc_id: str):
    """Delete a document and all its associated data"""
    try:
        session_dir = SESSIONS_DIR / session_id
        doc_dir = session_dir / "documents" / doc_id
        
        # Delete document directory (PDF + chunks)
        if doc_dir.exists():
            shutil.rmtree(doc_dir)
            print(f"[✓] Deleted document directory: {doc_dir}")
        
        # Remove from documents.json
        docs_file = session_dir / "documents.json"
        if docs_file.exists():
            with open(docs_file) as f:
                docs = json.load(f)
            
            if doc_id in docs:
                del docs[doc_id]
                with open(docs_file, 'w') as f:
                    json.dump(docs, f, indent=2)
        
        # Remove chat history for this document from localStorage (frontend will handle this)
        # Update selected_doc if it was the deleted one
        if session_id in session_status:
            if session_status[session_id].get("selected_doc") == doc_id:
                # Find another document to select
                if docs:
                    session_status[session_id]["selected_doc"] = next(iter(docs.keys()))
                else:
                    session_status[session_id]["selected_doc"] = None
        
        print(f"[✓] Deleted document: {doc_id}")
        return JSONResponse(content={"success": True, "message": "Document deleted"})
    
    except Exception as e:
        print(f"[!] Delete error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)})

def cleanup_llm_response(text: str) -> str:
    """Clean up LLM response - remove markdown artifacts and format nicely"""
    import re
    
    if not text:
        return text
    
    # Remove excessive asterisks and markdown formatting
    text = re.sub(r'\*{2,}', '', text)  # Remove ** markers
    text = re.sub(r'_{2,}', '', text)   # Remove __ markers
    text = re.sub(r'`+', '', text)      # Remove backticks
    
    # Clean up quotes and special formatting
    text = text.replace('""', '"').replace("''", "'")
    text = re.sub(r'"(\w+)":', r'\1:', text)  # Remove quotes around keys
    text = re.sub(r"'(\w+)':", r'\1:', text)
    
    # Remove JSON-like artifacts: **"key"**: -> key:
    text = re.sub(r'\*\*"([^"]+)"\*\*:\s*', r'\1: ', text)
    text = re.sub(r'\*\*([^*]+)\*\*:\s*', r'\1: ', text)
    
    # Clean up list markers - normalize to clean format
    # Convert various markers to consistent format
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines (but we'll add them back for spacing)
        if not stripped:
            cleaned_lines.append('')
            continue
        
        # Fix numbered items with various formats
        # "1. text" -> "1. text"
        # "1) text" -> "1. text"  
        # "1: text" -> "1. text"
        stripped = re.sub(r'^(\d+)[):](\s+)', r'\1. \2', stripped)
        
        # Fix lettered items
        # "a) text" -> "• text"
        # "a. text" -> "• text"
        stripped = re.sub(r'^([a-z])[):](\s+)', r'• \2', stripped)
        
        # Remove excessive hyphens/dashes at start (keep only one)
        while stripped.startswith('--'):
            stripped = stripped[1:]
        
        # Convert multiple markers to single bullet
        if stripped.startswith('- -'):
            stripped = '• ' + stripped[3:].lstrip()
        elif stripped.startswith('- '):
            stripped = '• ' + stripped[2:]
        elif stripped.startswith('• '):
            pass  # Keep as is
        
        cleaned_lines.append(stripped)
    
    # Join lines, but add spacing between logical sections
    text = '\n'.join(cleaned_lines)
    
    # Add paragraph breaks before numbered sections
    text = re.sub(r'\n(\d+\.)', r'\n\n\1', text)
    
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

async def search_chunks_from_session(session_id: str, doc_id: str, query: str):
    """Search chunks using lenient algorithm from search_logic.py"""
    try:
        # Call the optimized search function from search_logic
        best_chunks = await search_chunks_strict(
            query=query,
            session_id=session_id,
            doc_id=doc_id,
            SESSIONS_DIR=SESSIONS_DIR,
            WORKING_DIR=WORKING_DIR
        )
        
        if not best_chunks:
            print(f"[!] No chunks found for query: {query[:50]}", flush=True)
            return []
        
        # Combine chunks with newline separator
        combined = "\n".join(best_chunks)
        
        # Clean up OCR artifacts and extra whitespace
        import re as regex_module
        
        # Remove page markers
        combined = regex_module.sub(r'=== Page \d+ ===', '', combined, flags=regex_module.IGNORECASE)
        combined = regex_module.sub(r'===\s*', '', combined)
        
        # Remove multiple spaces (but keep intentional spacing in tables)
        combined = regex_module.sub(r' {3,}', '  ', combined)  # Triple+ -> double space
        
        # Remove multiple newlines
        combined = regex_module.sub(r'\n\n\n+', '\n\n', combined)
        
        # Remove strange unicode characters and control chars
        combined = ''.join(c for c in combined if ord(c) >= 32 or c in '\n\t')
        
        # Fix common OCR artifacts
        combined = regex_module.sub(r'([^\w])\|\|([^\w])', r'\1|\2', combined)  # Fix || artifacts
        
        # Clean up extra spaces at line start/end
        lines = combined.split('\n')
        lines = [line.strip() for line in lines]
        combined = '\n'.join(lines)
        
        combined = combined.strip()
        
        # Limit context length - INCREASED for better coverage
        # For section/table queries: up to 20000 chars
        # For general queries: 8000 chars (enough for summary, not overwhelming)
        if any(w in query.lower() for w in ['menimbang', 'mengingat', 'menetapkan', 'tabel', 'daftar']):
            max_context_len = 20000  # More for section/table queries - increased to capture all points
        else:
            max_context_len = 8000  # Reduced for general queries to avoid garbage
        
        if len(combined) > max_context_len:
            combined = combined[:max_context_len]
            print(f"[*] Context truncated to {max_context_len} chars")
        
        print(f"[*] Found {len(best_chunks)} chunks, context: {len(combined)} chars", flush=True)
        return [{'content': combined}]
    
    except Exception as e:
        print(f"[!] Search error: {e}")
        import traceback
        traceback.print_exc()
        return []

def format_table_response(context: str, question: str):
    """
    Try to format table response if context contains structured table data
    Returns formatted answer or None if no table found
    """
    if not TABLE_PROCESSOR:
        return None
    
    if not any(kw in question.lower() for kw in ['tabel', 'daftar', 'table', 'daftar nama', 'siapa', 'kelompok', 'kategori']):
        return None
    
    try:
        # Try to extract and format table
        tables = TABLE_PROCESSOR.detect_table_region(context)
        
        if not tables:
            return None
        
        # Extract first table found
        start_pos, end_pos, table_type = tables[0]
        table_lines = context[start_pos:end_pos].split('\n')
        
        table_data = None
        
        # Try to parse based on type
        if table_type == "box":
            table_data = TABLE_PROCESSOR.parse_box_table(table_lines)
        elif table_type == "pipe":
            table_data = TABLE_PROCESSOR.parse_pipe_table(table_lines)
        else:
            table_data = TABLE_PROCESSOR.parse_text_table(table_lines)
        
        if table_data:
            # Format table for display - clean and readable
            headers = table_data.get('headers', [])
            rows = table_data.get('rows', [])
            
            # Build readable table response
            result = f"📋 **Tabel** ({table_type}):\n\n"
            
            # Header line
            result += "| " + " | ".join(headers) + " |\n"
            result += "|" + "|".join(["-" * (len(h) + 2) for h in headers]) + "|\n"
            
            # Data rows (limit to 50)
            for idx, row in enumerate(rows[:50], 1):
                result += "| " + " | ".join(str(c).strip()[:50] for c in row) + " |\n"
            
            if len(rows) > 50:
                result += f"\n... dan {len(rows) - 50} baris lagi"
            
            return result
        
        return None
    
    except Exception as e:
        print(f"[!] Table formatting error: {e}")
        return None

@app.post("/api/query")
async def query_pdf(request: QueryRequest):
    try:
        session_id = request.session_id
        doc_id = request.doc_id
        question = request.question
        
        if not question or not question.strip():
            return JSONResponse(content={"success": False, "error": "Empty question"})
        
        if not doc_id:
            return JSONResponse(content={"success": False, "error": "No document selected"})
        
        if session_id not in session_status or session_status[session_id].get("status") != "ready":
            return JSONResponse(content={"success": False, "error": "Session not ready"})
        
        print(f"[*] Query (doc={doc_id}): {question[:50]}...", flush=True)
        
        try:
            t_total_start = time.time()
            
            # Search chunks from SELECTED DOCUMENT ONLY
            chunks = await search_chunks_from_session(session_id, doc_id, question)
            
            if not chunks:
                answer = "Konten dokumen tidak mencukupi untuk menjawab pertanyaan ini. Mohon tanyakan dengan kata kunci lain."
                print(f"[!] No chunks found for doc {doc_id}")
                return JSONResponse(content={"success": True, "answer": answer})
            
            context = chunks[0]['content']
            
            # Detect query type
            question_lower = question.lower()
            is_summary_query = any(kw in question_lower for kw in ['jelaskan isi dokumen', 'ringkas', 'summary', 'overview', 'ringkasan', 'apa isi dokumen', 'tentang dokumen'])
            
            # Try table formatting first if it's a table question
            table_answer = format_table_response(context, question)
            if table_answer:
                answer = table_answer
            # For short context: return directly (but still clean)
            elif len(context) < 600:
                answer = cleanup_llm_response(context)
            # Check for greeting-only questions
            elif question.lower().strip() in ['hai', 'halo', 'hi', 'hello', 'assalamu\'alaikum', 'pagi', 'siang', 'sore', 'malam']:
                answer = "Halo! Ada yang bisa saya bantu tentang dokumen ini?"
            else:
                # For summary queries: use special prompt
                if is_summary_query:
                    system_prompt = """Kamu adalah assistant yang membuat RINGKASAN DOKUMEN yang singkat dan padat.

ATURAN RINGKASAN:
- Buat SUMMARY SINGKAT: max 5-7 poin utama SAJA
- Jelaskan tujuan/maksud utama dokumen dalam 1-2 kalimat
- Highlight bagian kunci: Menimbang, Mengingat, Memutuskan (jika ada)
- Gunakan bullet points (•) untuk clarity
- Format: • Poin 1\n• Poin 2\n• dll
- JANGAN copy-paste seluruh isi dokumen
- Target: 200-300 kata maksimal
- TIDAK BOLEH ada markdown atau simbol aneh"""

                    answer_prompt = f"""Pertanyaan: {question}

Konteks dari dokumen:
{context}

RINGKASAN SINGKAT (max 5-7 poin, 200-300 kata):"""
                else:
                    # Regular question
                    system_prompt = """Kamu adalah assistant yang FOKUS menjawab pertanyaan user dari dokumen.

ATURAN PEMFORMATAN - SANGAT PENTING:
- Gunakan line break yang cukup untuk readability
- Untuk list: gunakan format "• item" atau "1. item" dengan line break setelah setiap item
- Pisahkan poin-poin utama dengan line break kosong
- Jangan gunakan markdown seperti ** atau __
- Jangan pernah output JSON atau struktur data kompleks
- Gunakan spacing untuk visual hierarchy yang jelas

ATURAN KONTEN:
1. Jawab TEPAT apa yang ditanya, JANGAN tambah informasi
2. Jika ditanya tabel: LIST item dengan format "Nama | Kategori | Nilai" atau "• item"
3. Jika ditanya bagian spesifik (Menimbang/Mengingat): LIST SEMUA POIN dengan nomor atau bullet
4. Jika ditanya point spesifik (point 2, point a): HANYA jawab itu saja
5. Jawab dari dokumen SAJA, jangan tambah pengetahuan umum
6. JANGAN tambah kesimpulan atau summary tidak diminta"""

                    answer_prompt = f"""Pertanyaan: {question}

Konteks dari dokumen:
{context}

Jawaban (format dengan jelas, gunakan line break untuk setiap poin):"""
                
                t_llm_start = time.time()
                answer = await asyncio.wait_for(
                    llm_model_func_openrouter(answer_prompt, sys_prompt=system_prompt),
                    timeout=60.0
                )
                t_llm = time.time() - t_llm_start
                print(f"[OK] LLM: {t_llm:.2f}s")
                
                # Clean up response formatting
                answer = cleanup_llm_response(answer)
            
            t_total = time.time() - t_total_start
            
            print(f"[OK] Query done: {len(answer)} chars in {t_total:.2f}s", flush=True)
            
            return JSONResponse(content={
                "success": True,
                "answer": answer,
                "timing": {"total_ms": int(t_total * 1000)}
            })
        
        except Exception as e:
            print(f"[!] Query error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return JSONResponse(content={"success": False, "error": str(e)})
    
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        session_dir = SESSIONS_DIR / session_id
        
        if session_id in session_status:
            del session_status[session_id]
        
        if session_dir.exists():
            shutil.rmtree(session_dir)
        
        return JSONResponse(content={"success": True})
    
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})

@app.get("/")
async def serve_ui():
    return FileResponse(Path(__file__).parent / "ui" / "index.html")

ui_dir = Path(__file__).parent / "ui"
if ui_dir.exists():
    app.mount("/static", StaticFiles(directory=str(ui_dir)), name="static")

# ===== MAIN =====
if __name__ == "__main__":
    print("[*] Server ready at http://localhost:8000\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning"
    )
