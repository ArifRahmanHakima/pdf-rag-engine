"""
FastAPI RAG Chatbot Server - Main entry point
Modular architecture with services and handlers separated
"""

import os, sys, io, json, tempfile
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
from app.services.docstring_service import extract_with_docstring_sync

# Database imports
from app.services.database_service import get_database_service
from app.db.models import SessionLocal

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
    get_docstring_upload_handler,
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

# Use TEMPORARY directory for RAG working files (NOT persistent storage)
# This prevents rag_storage folder from accumulating files
TEMP_WORKING_DIR = tempfile.mkdtemp(prefix="lightrag_", suffix="_tmp")
print(f"[*] RAG working directory (temp): {TEMP_WORKING_DIR}")

SESSIONS_DIR = Path(config.working_dir) / "pdf_sessions"
# DO NOT create SESSIONS_DIR - use database only
# SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Global state
embedding_func = None
rag_instance = None
session_status = {}
db_service = None


def _load_embedding_model():
    """Load embedding model"""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    load_embedding_model()
    sys.stdout = old_stdout
    embedding_func = get_embedding_func()
    print("[✓] Qwen embedding model loaded\n")
    return embedding_func




async def _initialize_rag_instance():
    """Lazy initialize RAG instance on first use"""
    global embedding_func, rag_instance
    
    if rag_instance is not None:
        return rag_instance
    
    print("\n[*] Initializing RAG instance on first use...")
    print(f"[*] Using temporary working directory: {TEMP_WORKING_DIR}")
    
    # Load embedding model if not loaded
    if embedding_func is None:
        embedding_func = _load_embedding_model()
        globals()['embedding_func'] = embedding_func
    
    # Create RAG instance with TEMPORARY working directory
    rag_instance = LightRAG(
        working_dir=TEMP_WORKING_DIR,  # Use temp dir - NOT persistent
        llm_model_func=llm_model_func_openrouter,
        embedding_func=embedding_func,
    )
    globals()['rag_instance'] = rag_instance
    
    # Initialize storages
    await rag_instance.initialize_storages()
    try:
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()
    except:
        pass
    
    print("[✓] RAG instance initialized\n")
    return rag_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_func, rag_instance, db_service
    
    print("[*] Initializing system...")
    
    # Initialize database service (REQUIRED)
    db_service = get_database_service()
    print("[✓] Database service initialized (PostgreSQL + Qdrant)")
    
    # Load embedding model immediately (needed for embeddings)
    embedding_func = _load_embedding_model()
    globals()['embedding_func'] = embedding_func
    
    # RAG instance will be lazily initialized on first upload
    print("[✓] System ready (RAG will initialize on first upload)\n")
    
    # Restore sessions from disk (DISABLED - using DB only)
    # _restore_sessions()
    
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

# DocString upload endpoint
docstring_api_key = os.getenv("DOCSTRING_API_KEY")
if docstring_api_key:
    app.post("/api/upload-docstring")(
        get_docstring_upload_handler(
            lambda: rag_instance,
            SESSIONS_DIR,
            session_status,
            get_next_session_id,
            save_session_metadata,
            ingest_pdf_async,
            extract_with_docstring_sync,
            docstring_api_key
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
        delete_func=delete_document_service
    )
)

# Query endpoint
app.post("/api/query")(
    get_query_handler(
        SESSIONS_DIR,
        SESSIONS_DIR,
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
        SESSIONS_DIR,
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
