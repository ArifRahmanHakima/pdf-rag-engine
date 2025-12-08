from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

# REGISTER ROUTES API DULU
app.include_router(upload.router, tags=["Upload"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])

@app.get("/ping")
def ping():
    return {"status": "ok", "message": "Server aktif!"}

# TERAKHIR mount frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
