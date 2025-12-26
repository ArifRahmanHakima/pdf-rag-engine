from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import traceback
import asyncio
from api.services.pdf_processor import (
    process_pdf_async, 
    generate_summary_async,
    get_process_status,
    get_doc_id,
    ProcessStatus
)

router = APIRouter()

# Background task untuk proses PDF
async def process_pdf_background(file_path: str, filename: str):
    """Process PDF di background dan generate summary"""
    try:
        # Proses PDF
        doc_id, message = await process_pdf_async(file_path)
        
        # Generate summary
        summary = await generate_summary_async(file_path, doc_id)
        
        print(f"✅ Background processing completed for {filename}")
        return doc_id, summary
        
    except Exception as e:
        print(f"❌ Background processing failed for {filename}: {str(e)}")
        raise

@router.post("")
@router.post("/")
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
        raise HTTPException(
            status_code=400, 
            detail=f"PDF terlalu besar. Maksimal {os.getenv('MAX_PDF_SIZE_MB', 10)}MB."
        )
    
    # Simpan file
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    
    try:
        # Simpan file terlebih dahulu
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Generate doc_id langsung
        doc_id = get_doc_id(file.filename)
        
        # Tambahkan background task untuk proses PDF
        background_tasks.add_task(
            process_pdf_background, 
            file_path, 
            file.filename
        )
        
        # Return response langsung (jangan tunggu proses selesai)
        return {
            "status": "queued",
            "filename": file.filename,
            "doc_id": doc_id,
            "message": f"File {file.filename} diterima dan sedang diproses di background. Gunakan doc_id ini untuk melihat status atau bertanya.",
            "note": "Proses PDF memakan waktu beberapa saat. Cek status menggunakan endpoint /status/{doc_id}"
        }
        
    except Exception as e:
        print(f"\n[Upload Error] Gagal memproses: {file_path}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Gagal memproses PDF: {str(e)}")

@router.get("/status/{doc_id}")
async def get_upload_status(doc_id: str):
    """Get status of PDF processing"""
    status = get_process_status(doc_id)
    return {
        "doc_id": doc_id,
        "status": status["status"],
        "progress": status["progress"],
        "message": status["message"],
        "current_stage": status["current_stage"],
        "start_time": status["start_time"],
        "completed_time": status.get("completed_time")
    }