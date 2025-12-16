from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import json
import traceback
from api.services.rag_engine import process_pdf, generate_summary, get_doc_id, clear_rag_instance
from api.services.document_service import save_document, get_all_documents, get_document_by_id, get_chat_history, delete_document
import shutil

router = APIRouter()

# Path untuk menyimpan metadata dokumen (backup, utama di PostgreSQL)
DOCS_METADATA_FILE = "./rag_storage/documents_metadata.json"

def load_docs_metadata():
    """Load metadata dokumen dari file, auto-generate jika kosong"""
    metadata = {}
    
    # Load dari file jika ada
    if os.path.exists(DOCS_METADATA_FILE):
        try:
            with open(DOCS_METADATA_FILE, 'r') as f:
                metadata = json.load(f)
        except:
            metadata = {}
    
    # Auto-generate metadata untuk dokumen yang sudah ada tapi belum ada di metadata
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    rag_storage_dir = "./rag_storage"
    
    if os.path.exists(rag_storage_dir) and os.path.exists(upload_dir):
        # Scan semua folder doc_id di rag_storage
        for doc_id in os.listdir(rag_storage_dir):
            doc_storage_path = os.path.join(rag_storage_dir, doc_id)
            
            # Skip jika bukan folder atau sudah ada di metadata
            if not os.path.isdir(doc_storage_path) or doc_id in metadata:
                continue
            
            # Cari file PDF yang cocok berdasarkan doc_id
            for filename in os.listdir(upload_dir):
                if filename.endswith('.pdf'):
                    file_path = os.path.join(upload_dir, filename)
                    file_doc_id = get_doc_id(file_path)
                    
                    if file_doc_id == doc_id:
                        metadata[doc_id] = {
                            "fileName": filename,
                            "filePath": file_path,
                            "docId": doc_id
                        }
                        print(f"📝 Auto-generated metadata for: {filename} ({doc_id})")
                        break
        
        # Simpan jika ada perubahan
        if metadata:
            save_docs_metadata(metadata)
    
    return metadata

def save_docs_metadata(metadata):
    """Simpan metadata dokumen ke file"""
    os.makedirs(os.path.dirname(DOCS_METADATA_FILE), exist_ok=True)
    with open(DOCS_METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

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
        
        # Simpan ke PostgreSQL database
        save_document(doc_id, file.filename, file_path, summary)
        
        # Simpan metadata dokumen (backup ke file)
        metadata = load_docs_metadata()
        metadata[doc_id] = {
            "fileName": file.filename,
            "filePath": file_path,
            "docId": doc_id
        }
        save_docs_metadata(metadata)
        
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


@router.get("/documents")
async def list_documents():
    """
    Mendapatkan daftar semua dokumen yang sudah diupload.
    Utama dari PostgreSQL, fallback ke file metadata.
    """
    try:
        # Coba ambil dari database dulu
        db_documents = get_all_documents()
        
        if db_documents:
            documents = []
            rag_storage_dir = "./rag_storage"
            
            for doc in db_documents:
                doc_id = doc.get("doc_id")
                file_path = doc.get("file_path", "")
                doc_storage_path = os.path.join(rag_storage_dir, doc_id) if doc_id else ""
                
                # Verify dokumen masih ada
                if doc_id and os.path.isdir(doc_storage_path):
                    documents.append({
                        "fileName": doc.get("file_name"),
                        "docId": doc_id,
                        "filePath": file_path,
                        "summary": doc.get("summary")
                    })
            
            return {
                "status": "success",
                "source": "database",
                "documents": documents
            }
        
        # Fallback ke file metadata jika database kosong
        metadata = load_docs_metadata()
        
        documents = []
        rag_storage_dir = "./rag_storage"
        
        for doc_id, doc_info in metadata.items():
            doc_storage_path = os.path.join(rag_storage_dir, doc_id)
            
            if os.path.isdir(doc_storage_path) and os.path.exists(doc_info.get("filePath", "")):
                documents.append({
                    "fileName": doc_info["fileName"],
                    "docId": doc_id,
                    "filePath": doc_info.get("filePath", "")
                })
        
        return {
            "status": "success",
            "source": "file",
            "documents": documents
        }
        
    except Exception as e:
        print(f"[List Documents Error] {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Gagal mendapatkan daftar dokumen: {str(e)}")


@router.get("/documents/{doc_id}/history")
async def get_document_history(doc_id: str, user_id: str = None):
    """
    Mendapatkan chat history untuk dokumen tertentu.
    """
    try:
        history = get_chat_history(doc_id, user_id)
        doc = get_document_by_id(doc_id)
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "document": doc,
            "history": history
        }
    except Exception as e:
        print(f"[Get History Error] {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Gagal mendapatkan history: {str(e)}")


@router.delete("/documents/{doc_id}")
async def delete_document_endpoint(doc_id: str):
    """
    Menghapus dokumen beserta semua data terkait:
    - Database entry (documents & chat_messages)
    - RAG storage folder
    - File PDF asli
    - Metadata file
    """
    try:
        # Get document info first
        doc = get_document_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
        
        file_name = doc.get("file_name", "")
        file_path = doc.get("file_path", "")
        
        # 1. Clear RAG instance from memory
        try:
            clear_rag_instance(doc_id)
        except:
            pass
        
        # 2. Delete from database
        delete_document(doc_id)
        
        # 3. Delete RAG storage folder
        rag_storage_path = f"./rag_storage/{doc_id}"
        if os.path.exists(rag_storage_path):
            shutil.rmtree(rag_storage_path)
            print(f"🗑️ Deleted RAG storage: {rag_storage_path}")
        
        # 4. Delete PDF file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ Deleted PDF file: {file_path}")
        else:
            # Try alternative path
            upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
            alt_path = os.path.join(upload_dir, file_name)
            if os.path.exists(alt_path):
                os.remove(alt_path)
                print(f"🗑️ Deleted PDF file: {alt_path}")
        
        # 5. Update metadata file
        metadata = load_docs_metadata()
        if doc_id in metadata:
            del metadata[doc_id]
            save_docs_metadata(metadata)
            print(f"🗑️ Removed from metadata: {doc_id}")
        
        return {
            "status": "success",
            "message": f"Dokumen '{file_name}' berhasil dihapus",
            "doc_id": doc_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Delete Document Error] {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Gagal menghapus dokumen: {str(e)}")