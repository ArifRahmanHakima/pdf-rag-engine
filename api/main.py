import os
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import upload, chat
from api.services.rag_engine import clear_document_cache, clear_root_storage, reset_all_storage, list_documents

# ⭐ PENTING: Load .env DI AWAL!
load_dotenv()

# Debug: Print untuk cek apakah .env terload
print("=" * 50)
print("🔧 ENVIRONMENT VARIABLES CHECK:")
print(f"✓ LLM_MODEL: {os.getenv('LLM_MODEL')}")
print(f"✓ VISION_MODEL: {os.getenv('VISION_MODEL')}")
print(f"✓ OPENROUTER_API_KEY exists: {bool(os.getenv('OPENROUTER_API_KEY'))}")
print(f"✓ OPENROUTER_BASE_URL: {os.getenv('OPENROUTER_BASE_URL')}")
print("=" * 50)

app = FastAPI(title="Chatbot PDF RAGAnything")

# Aktifkan CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REGISTER ROUTES API
app.include_router(upload.router, prefix="/upload", tags=["Upload"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])

@app.get("/ping")
def ping():
    return {"status": "ok", "message": "Server aktif!"}

# ============ ADMIN ENDPOINTS ============
@app.get("/admin/documents")
def get_documents():
    """List all loaded document IDs"""
    docs = list_documents()
    return {"status": "ok", "documents": docs, "count": len(docs)}

@app.post("/admin/clear-cache")
def clear_cache(doc_id: str = Query(None)):
    """Clear RAG instance cache (in-memory)"""
    clear_document_cache(doc_id)
    return {
        "status": "ok", 
        "message": f"Cache cleared for: {doc_id if doc_id else 'all documents'}"
    }

@app.post("/admin/clear-root-storage")
def clean_root_storage():
    """Clean old storage files in root directory"""
    deleted = clear_root_storage()
    return {
        "status": "ok",
        "message": f"Deleted {len(deleted)} files",
        "deleted_files": deleted
    }

@app.post("/admin/reset-storage")
def reset_storage():
    """⚠️ DANGER: Reset ALL storage - deletes everything!"""
    reset_all_storage()
    return {
        "status": "ok",
        "message": "All storage has been reset. Please re-upload your PDFs."
    }

# Mount uploads folder untuk akses file PDF
upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

# TERAKHIR mount frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")