from fastapi import APIRouter, Query, HTTPException
from api.services.rag_engine import query_document
from api.services.memory import get_chat_history, save_message_redis, save_message_postgres
import uuid

router = APIRouter()

@router.get("/history")
async def get_history(chat_id: str):
    """Get chat history from Redis"""
    try:
        messages = get_chat_history(chat_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil history: {str(e)}")

@router.post("/send")
async def send_message(
    question: str = Query(...),
    doc_id: str = Query(...),
    user_id: str = Query(...),
    chat_id: str = Query(None),
):
    """Send message and get response from specific document"""
    
    # Validasi input
    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="Pertanyaan tidak boleh kosong")
    
    if not doc_id:
        raise HTTPException(status_code=400, detail="Document ID tidak boleh kosong")
    
    # Buat chat_id baru jika belum ada
    if not chat_id:
        chat_id = str(uuid.uuid4())

    try:
        # Simpan pertanyaan ke Redis + Postgres
        save_message_redis(chat_id, "user", question)
        save_message_postgres(chat_id, doc_id, user_id, "user", question)

        # Ambil history terakhir (untuk context)
        history = get_chat_history(chat_id)
        
        # Bangun context dari history (ambil 3 pesan terakhir)
        context = ""
        if len(history) > 1:  # Lebih dari 1 berarti ada history sebelumnya
            recent_history = history[-6:-1]  # Ambil 3 pasang terakhir (user + bot), exclude pertanyaan terbaru
            context_parts = []
            for msg in recent_history:
                role = "Pengguna" if msg["role"] == "user" else "Asisten"
                context_parts.append(f"{role}: {msg['content']}")
            
            if context_parts:
                context = "\n".join(context_parts)
                # Tambahkan context ke pertanyaan
                enhanced_question = f"""Berdasarkan percakapan sebelumnya:
{context}

Pertanyaan baru: {question}

Jawab pertanyaan baru dengan mempertimbangkan konteks percakapan di atas."""
            else:
                enhanced_question = question
        else:
            enhanced_question = question

        # Tambahkan instruksi format untuk tabel
        format_instruction = """

PENTING: Jika jawaban mengandung data tabular atau tabel:
- Gunakan format tabel Markdown dengan header dan separator
- Contoh format:
| Kolom1 | Kolom2 | Kolom3 |
|--------|--------|--------|
| Data1  | Data2  | Data3  |

Pastikan tabel rapi dan lengkap."""

        enhanced_question = enhanced_question + format_instruction

        # Query dokumen spesifik menggunakan doc_id
        answer = await query_document(
            doc_id=doc_id, 
            question=enhanced_question, 
            top_k=3
        )

        # Simpan jawaban juga
        save_message_redis(chat_id, "bot", answer)
        save_message_postgres(chat_id, doc_id, user_id, "bot", answer)

        return {
            "chat_id": chat_id, 
            "answer": answer,
            "status": "success"
        }
    
    except Exception as e:
        print(f"[Chat Error] {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Jangan simpan error ke database
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal memproses pertanyaan: {str(e)}"
        )