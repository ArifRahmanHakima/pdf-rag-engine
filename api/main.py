import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import upload, chat

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

# TERAKHIR mount frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")