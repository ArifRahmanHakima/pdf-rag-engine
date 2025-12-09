from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import upload, chat, session
import os

app = FastAPI(title="Chatbot PDF RAGAnything")

# Aktifkan CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REGISTER ROUTES API DULU
app.include_router(upload.router, prefix="/upload", tags=["Upload"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(session.router, prefix="/session", tags=["Session"])

@app.get("/ping")
def ping():
    return {"status": "ok", "message": "Server aktif!"}

# Mount uploads directory untuk serve PDF files
upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

# TERAKHIR mount frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
