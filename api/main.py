from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from api.routes import upload, chat

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

# Mount uploads folder untuk akses file PDF
uploads_dir = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# TERAKHIR mount frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
