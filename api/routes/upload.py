from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import traceback
from api.services.rag_engine import process_pdf, generate_summary

router = APIRouter()

@router.post("")
@router.post("/")
async def upload_pdf(file: UploadFile = File(...)):
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
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Proses ke RAGAnything dan dapatkan doc_id
        doc_id, message = await process_pdf(file_path)
        
        # Generate summary dari file yang sudah diproses
        summary = await generate_summary(file_path, doc_id)
        
        return {
            "status": "success",
            "filename": file.filename,
            "doc_id": doc_id,  
            "summary": summary,
            "message": message
        }
        
    except Exception as e:
        print(f"\n[Upload Error] Gagal memproses: {file_path}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Gagal memproses PDF: {str(e)}")