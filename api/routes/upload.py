from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
import os
import shutil
import traceback
import asyncio
from api.services.pdf_processor import (
    process_pdf_async, 
    generate_summary_async,
    generate_suggested_questions_async,
    get_process_status,
    get_doc_id,
    ProcessStatus,
    rag_instances
)
from api.routes.auth import get_current_user
from api.services.auth import (
    create_document_record, 
    update_document_status, 
    verify_document_access,
    delete_document_record,
    get_document_by_id
)

router = APIRouter()

# Background task untuk proses PDF
async def process_pdf_background(file_path: str, filename: str, doc_id: str):
    """Process PDF di background dan generate summary"""
    try:
        # Proses PDF
        result_doc_id, message = await process_pdf_async(file_path)
        
        # Generate summary
        summary = await generate_summary_async(file_path, doc_id)
        
        # Update document status to embedded
        update_document_status(doc_id, "embedded")
        
        print(f"✅ Background processing completed for {filename}")
        return doc_id, summary
        
    except Exception as e:
        print(f"❌ Background processing failed for {filename}: {str(e)}")
        # Update status to failed
        update_document_status(doc_id, "failed")
        raise

@router.post("")
@router.post("/")
async def upload_pdf(
    file: UploadFile = File(...), 
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user)
):
    """Upload PDF dengan autentikasi"""
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
        
        # Create document record in database
        doc_record = create_document_record(
            user_id=current_user["id"],
            doc_id=doc_id,
            filename=file.filename,
            status="processing"
        )
        
        if not doc_record:
            raise HTTPException(status_code=500, detail="Gagal menyimpan record dokumen")
        
        # Tambahkan background task untuk proses PDF
        background_tasks.add_task(
            process_pdf_background, 
            file_path, 
            file.filename,
            doc_id
        )
        
        # Return response langsung (jangan tunggu proses selesai)
        return {
            "status": "queued",
            "filename": file.filename,
            "doc_id": doc_id,
            "user_id": current_user["id"],
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

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a document and its associated data (hanya milik user sendiri)"""
    try:
        # Verify document access
        if not verify_document_access(current_user["id"], doc_id):
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke dokumen ini")
        
        # Delete document record from database
        delete_document_record(doc_id, current_user["id"])
        
        # Remove from RAG instances cache
        if doc_id in rag_instances:
            del rag_instances[doc_id]
            print(f"🗑️ Removed RAG instance for doc_id: {doc_id}")
        
        # Delete RAG storage folder
        rag_storage_dir = os.path.join(os.getenv("WORKING_DIR", "./rag_storage"), doc_id)
        if os.path.exists(rag_storage_dir):
            shutil.rmtree(rag_storage_dir)
            print(f"🗑️ Deleted RAG storage: {rag_storage_dir}")
        
        return {
            "status": "success",
            "message": f"Document {doc_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting document {doc_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Gagal menghapus dokumen: {str(e)}")

@router.get("/summary/{doc_id}")
async def get_document_summary(doc_id: str):
    """Get summary and suggested questions for a document"""
    try:
        # Check if document exists in RAG
        status = get_process_status(doc_id)
        
        if status["status"] == ProcessStatus.PROCESSING:
            return {
                "status": "processing",
                "message": "Dokumen masih diproses, mohon tunggu...",
                "summary": None,
                "suggested_questions": None
            }
        
        # Find the file path
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        file_path = None
        
        # Search for file with matching doc_id
        if os.path.exists(upload_dir):
            for filename in os.listdir(upload_dir):
                if get_doc_id(filename) == doc_id:
                    file_path = os.path.join(upload_dir, filename)
                    break
        
        # Generate summary
        summary = await generate_summary_async(file_path or "", doc_id)
        
        # Generate suggested questions
        suggested_questions = await generate_suggested_questions_async(doc_id)
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "summary": summary,
            "suggested_questions": suggested_questions
        }
        
    except Exception as e:
        print(f"❌ Error getting summary for {doc_id}: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "summary": "Dokumen berhasil diproses dan siap untuk pertanyaan.",
            "suggested_questions": [
                "Apa isi utama dari dokumen ini?",
                "Jelaskan poin-poin penting dalam dokumen ini",
                "Apakah ada data atau tabel dalam dokumen ini?"
            ]
        }