from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import os
import traceback
import redis
from api.services.rag_engine import process_pdf

router = APIRouter()

# Inisialisasi Redis
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
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

        # Tambahkan status ke Redis
        redis_client.set(file.filename, "uploading")

        # Tambahkan tugas latar belakang untuk memproses file
        background_tasks.add_task(process_and_update_status, file.filename, file_path)

        return {
            "status": "success",
            "filename": file.filename,
            "message": "File berhasil diunggah dan sedang diproses."
        }

    except Exception as e:
        print(f"\n[Upload Error] Gagal memproses: {file_path}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Gagal memproses PDF.")

async def process_and_update_status(filename: str, file_path: str):
    try:
        # Perbarui status di Redis
        redis_client.set(filename, "processing")

        # Proses file PDF
        summary = await process_pdf(file_path)

        # Simpan hasil ke Redis
        redis_client.set(filename, "completed")
        redis_client.set(f"{filename}_summary", summary)

    except Exception as e:
        print(f"\n[Processing Error] Gagal memproses: {file_path}")
        print(traceback.format_exc())
        redis_client.set(filename, "failed")

@router.get("/status/{filename}")
async def get_status(filename: str):
    status = redis_client.get(filename)
    if not status:
        raise HTTPException(status_code=404, detail="Status tidak ditemukan untuk file tersebut.")

    summary = redis_client.get(f"{filename}_summary")
    return {
        "filename": filename,
        "status": status,
        "summary": summary if summary else None
    }