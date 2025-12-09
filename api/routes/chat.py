from fastapi import APIRouter, Query, Header
from typing import Optional
from api.services.rag_engine import rag
from api.services.memory import (
    get_chat_history, save_message_redis, save_message_postgres,
    add_session_message
)

import uuid

router = APIRouter()

@router.get("/history")
async def get_history(chat_id: str):
    return {"messages": get_chat_history(chat_id)}

@router.post("/send")
async def send_message(
    question: str = Query(...),
    doc_id: str = Query(...),
    user_id: str = Query(...),
    chat_id: str = Query(None),
    x_session_id: Optional[str] = Header(None)
):
    # Buat chat_id baru jika belum ada
    if not chat_id:
        chat_id = str(uuid.uuid4())

    # Simpan pertanyaan ke Redis + Postgres
    save_message_redis(chat_id, "user", question)
    save_message_postgres(chat_id, doc_id, user_id, "user", question)
    
    # Save to session if session_id provided
    if x_session_id:
        add_session_message(x_session_id, "user", question)

    # Ambil history terakhir (untuk memory)
    history = get_chat_history(chat_id)

    # Kirim ke LLM
    try:
        print(f"Sending query to RAG: {question}")
        if not question or not isinstance(question, str):
            raise ValueError("Question must be a non-empty string")
        
        result = await rag.aquery(
            str(question).strip(),
            mode="hybrid",
            top_k=3
        )
        answer = result if isinstance(result, str) else result.get("text", "Tidak ada jawaban.")
    except Exception as e:
        print(f"RAG Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Cek jika rate limit
        if "429" in str(e) or "Rate limit" in str(e):
            answer = "Maaf, kuota API gratis sudah habis. Silakan tambahkan kredit di OpenRouter atau tunggu hingga reset besok."
        else:
            answer = "Maaf, terjadi kesalahan saat memproses jawaban. Silakan coba lagi dengan pertanyaan yang berbeda."

    # Simpan jawaban juga
    save_message_redis(chat_id, "bot", answer)
    save_message_postgres(chat_id, doc_id, user_id, "bot", answer)
    
    # Save to session if session_id provided
    if x_session_id:
        add_session_message(x_session_id, "bot", answer)

    return {"chat_id": chat_id, "answer": answer}
