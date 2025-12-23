"""
FastAPI RAG Chatbot Server - Main entry point
Modular architecture with services and handlers separated
"""

import os, sys, io, json
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

# Suppress library logging
os.environ["LIGHTRAG_TIMEOUT"] = "300"
import logging
logging.getLogger("lightrag").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("easyocr").setLevel(logging.ERROR)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Core imports
from raganything.config import RAGAnythingConfig
from app.services.embedding_service import load_embedding_model, get_embedding_func
from app.services.llm_service import llm_model_func_openrouter
from lightrag import LightRAG
from app.services.search_logic import search_chunks_strict
from main_openrouter import extract_text_from_pdf_with_ocr

# Modular imports
from app.utils import (
    get_next_session_id,
    get_session_metadata,
    save_session_metadata,
    cleanup_llm_response,
    format_section_response,
    format_table_response,
)

from app.services import (
    ingest_pdf_async,
    search_chunks_from_session,
    delete_document_service,
    delete_session_service,
    process_query,
)

from app.handlers import (
    QueryRequest,
    get_upload_handler,
    get_documents_handler,
    get_select_document_handler,
    get_list_sessions_handler,
    get_status_handler,
    get_pdf_handler,
    get_pdf_fallback_handler,
    get_delete_document_handler,
    get_query_handler,
    get_delete_session_handler,
    get_ui_handler,
)

# Optional table processor
try:
    from app.utils.table_processor import TableProcessor
    TABLE_PROCESSOR = TableProcessor()
    print("[✓] Table processor loaded")
except Exception as e:
    print(f"[!] Table processor not available: {e}")
    TABLE_PROCESSOR = None

print("\n[*] Starting RAG Server (modular architecture)...\n")

# Configuration
config = RAGAnythingConfig()
WORKING_DIR = config.working_dir
SESSIONS_DIR = Path(WORKING_DIR) / "pdf_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Global state
embedding_func = None
rag_instance = None
session_status = {}


def _load_embedding_model():
    """Load embedding model"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    load_embedding_model()
    sys.stdout = old_stdout
    embedding_func = get_embedding_func()
    print("[✓] Qwen embedding model loaded\n")
    return embedding_func


def _restore_sessions():
    """Restore session state from disk on startup"""
    global session_status
    
    if not SESSIONS_DIR.exists():
        return
    
    # Load all session metadata
    for session_dir in SESSIONS_DIR.iterdir():
        if session_dir.is_dir():
            session_id = session_dir.name
            metadata_file = session_dir / "metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    # Restore session status
                    session_status[session_id] = {
                        "status": "ready",
                        "progress": "Restored",
                        "selected_doc": metadata.get("selected_doc", "")
                    }
                    print(f"[✓] Restored session: {session_id}")
                except Exception as e:
                    print(f"[!] Error restoring session {session_id}: {e}")
    
    if session_status:
        print(f"[✓] Restored {len(session_status)} sessions\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_func, rag_instance
    
    print("[*] Initializing system...")
    
    # Load embedding model
    embedding_func = _load_embedding_model()
    globals()['embedding_func'] = embedding_func  # Ensure global assignment
    
    # Create RAG instance
    rag_instance = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=llm_model_func_openrouter,
        embedding_func=embedding_func,
    )
    globals()['rag_instance'] = rag_instance  # Ensure global assignment
    
    # Initialize storages
    await rag_instance.initialize_storages()
    try:
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()
    except:
        pass
    
    # Restore sessions from disk
    _restore_sessions()
    
    print("[✓] System ready\n")
    
    yield
    
    print("\n[*] Shutting down...")


# FastAPI App
app = FastAPI(title="RAG Chatbot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("="*70)
print("[RAG CHATBOT SERVER - MODULAR ARCHITECTURE]")
print("="*70 + "\n")

# ===== ENDPOINTS SETUP =====

# Upload endpoint
app.post("/api/upload")(
    get_upload_handler(
        lambda: rag_instance,
        SESSIONS_DIR,
        session_status,
        get_next_session_id,
        save_session_metadata,
        ingest_pdf_async,
        extract_text_from_pdf_with_ocr
    )
)

# Document management endpoints
app.get("/api/documents/{session_id}")(
    get_documents_handler(SESSIONS_DIR, session_status, get_session_metadata)
)

app.post("/api/select-document/{session_id}")(
    get_select_document_handler(session_status)
)

# Session management endpoints
app.get("/api/sessions")(
    get_list_sessions_handler(SESSIONS_DIR, get_session_metadata)
)

app.get("/api/status/{session_id}")(
    get_status_handler(session_status)
)

# PDF endpoints
app.get("/api/pdf/{session_id}/{doc_id}")(
    get_pdf_handler(SESSIONS_DIR)
)

app.get("/api/pdf/{session_id}")(
    get_pdf_fallback_handler(SESSIONS_DIR)
)

# Delete endpoints
app.delete("/api/delete-document/{session_id}/{doc_id}")(
    get_delete_document_handler(
        SESSIONS_DIR,
        Path(WORKING_DIR),
        session_status,
        delete_document_service
    )
)

# Query endpoint
app.post("/api/query")(
    get_query_handler(
        SESSIONS_DIR,
        Path(WORKING_DIR),
        session_status,
        search_chunks_from_session,
        search_chunks_strict,
        process_query,
        cleanup_llm_response,
        format_section_response,
        format_table_response,
        llm_model_func_openrouter,
        TABLE_PROCESSOR
    )
)

# Session deletion endpoint
app.delete("/api/sessions/{session_id}")(
    get_delete_session_handler(
        SESSIONS_DIR,
        Path(WORKING_DIR),
        session_status,
        delete_session_service
    )
)

# UI endpoints
@app.get("/")
async def home():
    """Serve home page"""
    return FileResponse(Path(__file__).parent / "ui" / "home.html")

@app.get("/chat")
async def chat():
    """Serve chat page"""
    return FileResponse(Path(__file__).parent / "ui" / "index.html")

# Static files
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
