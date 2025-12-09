from fastapi import APIRouter, UploadFile, File, HTTPException, Header
import os
import traceback
import uuid
from typing import Optional
from api.services.rag_engine import process_pdf
from api.services.memory import update_session_pdf

router = APIRouter()

@router.post("")
@router.post("/")
async def upload_pdf(
    file: UploadFile = File(...),
    x_session_id: Optional[str] = Header(None)
):
    # Validasi ekstensi
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang diizinkan.")

    # Validasi ukuran file
    size_limit = int(os.getenv("MAX_PDF_SIZE_MB", 10)) * 1024 * 1024
    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="File kosong.")

    if len(contents) > size_limit:
        raise HTTPException(status_code=400, detail="PDF terlalu besar.")

    # Simpan file
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    try:
        with open(file_path, "wb") as f:
            f.write(contents)

        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        file_url = f"/uploads/{file.filename}"

        # Save to Redis session if session_id provided
        if x_session_id:
            update_session_pdf(x_session_id, doc_id, file.filename, file_url)
            print(f"✅ Session updated: {x_session_id} -> {file.filename}")

        # Proses ke RAGAnything
        summary = await process_pdf(file_path)

        return {
            "status": "success",
            "filename": file.filename,
            "summary": summary,
            "doc_id": doc_id,
            "file_url": file_url
        }

    except Exception as e:
        print(f"\n[Upload Error] Gagal memproses: {file_path}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Gagal memproses PDF.")
