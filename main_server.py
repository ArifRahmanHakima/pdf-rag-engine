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

# Import extraction - EXACT SAME from main_openrouter.py
from main_openrouter import extract_text_from_pdf_with_ocr

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
    """Load embedding model - returns tuple (model, func) EXACT as main_openrouter.py"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    embedding_model = load_embedding_model()
    sys.stdout = old_stdout
    
    embedding_func = get_embedding_func()
    print("[✓] Qwen embedding model loaded\n")
    return embedding_model, embedding_func

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
        summary = f"File: {filename}\nPages: {num_pages}\nSize: {len(text)} chars"
        
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
    
    # Load embedding model - EXACT SAME
    embedding_model, embedding_func = _load_embedding_model()
    
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

async def search_chunks_from_session(session_id: str, doc_id: str, query: str):
    """Search chunks - ONLY from the selected document"""
    session_dir = SESSIONS_DIR / session_id
    doc_chunks_path = session_dir / "documents" / doc_id / "chunks.json"
    
    if not doc_chunks_path.exists():
        print(f"[!] Chunks file not found for doc {doc_id}: {doc_chunks_path}")
        return []
    
    try:
        with open(doc_chunks_path) as f:
            data = json.load(f)
            # FILTER chunks by doc_id marker - STRICT filtering
            chunks = []
            total_chunks = len(data)
            for chunk_id, item in data.items():
                if isinstance(item, dict) and 'content' in item:
                    content = item['content']
                    # Only include chunks from THIS document
                    if f"[DOC_ID:{doc_id}]" in content:
                        # Remove the doc_id marker before returning
                        content = content.replace(f"[DOC_ID:{doc_id}]\n", "")
                        chunks.append(content)
        
        if not chunks:
            print(f"[!] No chunks found for document {doc_id} (checked {total_chunks} total chunks)")
            print(f"[!] Looking for marker: [DOC_ID:{doc_id}]")
            return []
        
        print(f"[*] Searching {len(chunks)} chunks (of {total_chunks} total) in document {doc_id}...", end='', flush=True)
        
        # Semantic search - USE AWAIT for async embedding function
        import numpy as np
        query_embeddings = await embedding_func.func([query])
        query_embedding = query_embeddings[0]
        
        scores = []
        query_lower = query.lower()
        query_terms = [w for w in query_lower.split() if len(w) > 3]
        
        # Embed all chunks at once for efficiency
        chunk_samples = [c[:500] for c in chunks]
        chunk_embeddings_list = await embedding_func.func(chunk_samples)
        
        for i, chunk in enumerate(chunks):
            try:
                chunk_embedding = chunk_embeddings_list[i]
                
                # Semantic similarity
                similarity = np.dot(query_embedding, chunk_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding) + 1e-8
                )
                
                # Lexical boost
                chunk_lower = chunk.lower()
                lexical_boost = 1.0
                for term in query_terms:
                    if term in chunk_lower:
                        lexical_boost += 0.15
                
                final_score = similarity * lexical_boost
                scores.append(final_score)
            except Exception as e:
                scores.append(0)
        
        # Get top chunks with filtering
        import numpy as np
        scores_array = np.array(scores)
        
        # Filter: only keep chunks with score > 0.10 (slightly more lenient for better coverage)
        valid_indices = np.where(scores_array > 0.10)[0]
        
        if len(valid_indices) > 0:
            # Sort valid chunks by score, take top 10 (increased from 5 for better context)
            valid_scores = [(idx, scores_array[idx]) for idx in valid_indices]
            valid_scores.sort(key=lambda x: x[1], reverse=True)
            top_indices = [idx for idx, _ in valid_scores[:10]]
        else:
            # Fallback: if no good matches, take top 10 chunks by score (increased from 5)
            top_indices = np.argsort(-scores_array)[:10]
        
        best_chunks = [chunks[i] for i in top_indices if i < len(chunks)]
        best_scores = [scores[i] for i in top_indices if i < len(scores)]
        
        print(f" Found {len(best_chunks)} chunks, scores: {[f'{s:.2f}' for s in best_scores]}", flush=True)
        
        if not best_chunks:
            return []
        
        # Combine chunks with newline separator (not double newline to avoid padding)
        combined = "\n".join(best_chunks)
        combined = combined.replace('=== Page', '').replace('===', '').strip()
        
        # IMPORTANT: Limit context length to avoid overwhelming LLM
        # Increased to 3000 chars for better multi-page/table coverage
        max_context_len = 3000
        if len(combined) > max_context_len:
            combined = combined[:max_context_len]
            print(f"[*] Context truncated to {max_context_len} chars")
        
        return [{'content': combined}]
    
    except Exception as e:
        print(f"[!] Search error: {e}")
        import traceback
        traceback.print_exc()
        return []

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
            t_search_start = time.time()
            chunks = await search_chunks_from_session(session_id, doc_id, question)
            t_search = time.time() - t_search_start
            
            if not chunks:
                answer = "Konten dokumen tidak mencukupi untuk menjawab pertanyaan ini. Mohon tanyakan dengan kata kunci lain."
                print(f"[!] No chunks found for doc {doc_id}")
                return JSONResponse(content={"success": True, "answer": answer})
            
            context = chunks[0]['content']
            
            # For short context: return directly
            if len(context) < 600:
                answer = context
            else:
                # For longer context: use LLM with STRICTER prompt
                system_prompt = """Kamu adalah assistant yang HANYA menjawab berdasarkan dokumen yang diberikan. 
PENTING: 
- Jangan tambah informasi dari pengetahuan umum
- Jawab TEPAT dan AKURAT sesuai dokumen
- Jika ada TABEL dalam dokumen, PRESERVE struktur tabel dengan format yang jelas (gunakan markdown table atau text)
- Jika ditanyakan point/item spesifik (A, B, C, dll), jawab HANYA point yang diminta, bukan yang lain
- Jawab ringkas namun lengkap"""

                answer_prompt = f"""Pertanyaan: {question}

Konteks dari dokumen:
{context}

INSTRUKSI JAWABAN:
- Jawab HANYA berdasarkan konteks di atas
- Jika ada TABEL, format dengan baik (markdown atau text table)
- Jika ditanyakan point/item spesifik, jawab TEPAT point tersebut
- Jangan tambah informasi dari pengetahuan umum
- Jika jawaban tidak ada di konteks, katakan "Informasi tidak tersedia dalam dokumen"
- Jawab dengan singkat dan jelas

Jawaban:"""
                
                t_llm_start = time.time()
                answer = await asyncio.wait_for(
                    llm_model_func_openrouter(answer_prompt, sys_prompt=system_prompt),
                    timeout=60.0
                )
                t_llm = time.time() - t_llm_start
                print(f"[OK] LLM: {t_llm:.2f}s")
            
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
