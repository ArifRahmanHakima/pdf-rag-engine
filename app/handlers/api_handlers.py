"""
API endpoint handlers for PDF operations
"""

import io
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# Database imports
from app.services.database_service import get_database_service


class QueryRequest(BaseModel):
    session_id: str
    doc_id: str
    question: str


def get_upload_handler(
    rag_instance_getter,
    sessions_dir: Path,
    session_status: dict,
    get_next_session_func,
    save_metadata_func,
    ingest_func,
    extract_text_func
):
    """Factory for upload endpoint handler"""
    
    async def upload_pdf(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
        try:
            print(f"\n[*] Upload handler called for: {file.filename}", flush=True)
            
            # Import initialize function from main_server
            from main_server import _initialize_rag_instance
            rag_instance = await _initialize_rag_instance()
            
            if rag_instance is None:
                print("[!] RAG instance initialization failed", flush=True)
                return JSONResponse(content={"success": False, "error": "RAG initialization failed"})
            
            print(f"[*] Getting session ID...", flush=True)
            session_id = get_next_session_func(sessions_dir)
            print(f"[✓] Session ID: {session_id}", flush=True)
            
            # Create unique doc_id from filename (remove extension)
            doc_id = Path(file.filename).stem
            print(f"[*] Doc ID: {doc_id}", flush=True)
            
            # Store PDF content in memory for processing
            print(f"[*] Reading PDF file...", flush=True)
            pdf_content = await file.read()
            print(f"[✓] PDF read: {len(pdf_content)} bytes", flush=True)
            
            import tempfile
            print(f"[*] Creating temporary file...", flush=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_content)
                pdf_path = tmp.name
            print(f"[✓] Temp file: {pdf_path}", flush=True)
            
            session_status[session_id] = {
                "status": "ingesting",
                "progress": "Processing...",
                "selected_doc": doc_id
            }
            print(f"[*] Session status initialized", flush=True)
            
            # Background ingest
            if background_tasks:
                print(f"[*] Adding background task for ingestion...", flush=True)
                background_tasks.add_task(
                    ingest_func,
                    session_id,
                    str(pdf_path),
                    file.filename,
                    doc_id,
                    rag_instance,
                    sessions_dir,
                    Path(sessions_dir.parent),
                    session_status,
                    extract_text_func,
                    None,  # docstring_api_key
                    pdf_content  # Add PDF binary content
                )
                print(f"[✓] Background task added", flush=True)
            else:
                print(f"[!] No background_tasks available", flush=True)
            
            print(f"[✓] Upload successful, returning response", flush=True)
            return JSONResponse(content={
                "success": True,
                "session_id": session_id,
                "doc_id": doc_id,
                "filename": file.filename
            })
        
        except Exception as e:
            print(f"[!] Upload error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": str(e)}
            )
    
    return upload_pdf


def get_documents_handler(sessions_dir: Path, session_status: dict, get_metadata_func):
    """Factory for get documents endpoint handler - queries PostgreSQL database"""
    
    async def get_documents(session_id: str):
        try:
            from app.services.database_service import get_database_service
            db_service = get_database_service()
            
            # Initialize session_status if not exists
            if session_id not in session_status:
                session_status[session_id] = {"status": "ready", "selected_doc": None}
            
            # Get documents from PostgreSQL database (NOT local files)
            docs_db = db_service.storage.get_session_documents(session_id)
            
            if not docs_db:
                return JSONResponse(content={"success": True, "documents": []})
            
            # Convert DB objects to dict for API response
            docs_list = []
            for doc in docs_db:
                docs_list.append({
                    "doc_id": doc.id,  # Use 'id' not 'doc_id'
                    "filename": doc.filename,
                    "doc_type": doc.doc_type,
                    "pages": doc.pages,
                    "size": doc.size,
                    "upload_time": doc.upload_time.isoformat() if hasattr(doc.upload_time, 'isoformat') else str(doc.upload_time)
                })
            
            selected_doc = session_status.get(session_id, {}).get("selected_doc", None)
            doc_ids = [doc["doc_id"] for doc in docs_list]
            
            if selected_doc not in doc_ids:
                if docs_list:
                    selected_doc = docs_list[0]["doc_id"]
                    session_status[session_id]["selected_doc"] = selected_doc
                    print(f"[✓] Selected first document from DB: {selected_doc}", flush=True)
                else:
                    selected_doc = None
            
            return JSONResponse(content={
                "success": True,
                "documents": docs_list,
                "selected_doc": selected_doc
            })
        except Exception as e:
            print(f"[!] Error getting documents: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return get_documents


def get_select_document_handler(session_status: dict):
    """Factory for select document endpoint handler"""
    
    async def select_document(session_id: str, doc_id: str):
        try:
            session_status[session_id]["selected_doc"] = doc_id
            return JSONResponse(content={
                "success": True,
                "selected_doc": doc_id
            })
        except Exception as e:
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return select_document


def get_list_sessions_handler(sessions_dir: Path, get_metadata_func):
    """Factory for list sessions endpoint handler - queries PostgreSQL database"""
    
    async def list_sessions():
        try:
            from app.services.database_service import get_database_service
            db_service = get_database_service()
            
            # Get all sessions from PostgreSQL database
            sessions_db = db_service.storage.get_all_sessions()
            
            if not sessions_db:
                return JSONResponse(content={"success": True, "sessions": []})
            
            sessions = []
            for session in sessions_db:
                # Get first document's filename as session display name
                docs = session.documents
                filename = docs[0].filename if docs else f"Session {session.id}"
                upload_time = docs[0].upload_time.isoformat() if docs and hasattr(docs[0].upload_time, 'isoformat') else str(docs[0].upload_time) if docs else session.id
                
                sessions.append({
                    "session_id": session.id,
                    "filename": filename,
                    "upload_time": upload_time,
                    "status": "ready"
                })
            
            return JSONResponse(content={
                "success": True,
                "sessions": sorted(sessions, key=lambda x: x.get("upload_time", ""), reverse=True)
            })
        except Exception as e:
            print(f"[!] Error listing sessions: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return list_sessions


def get_status_handler(session_status: dict):
    """Factory for get status endpoint handler"""
    
    async def get_status(session_id: str):
        try:
            if session_id not in session_status:
                return JSONResponse(content={"success": False, "error": "Not found"})
            
            status = session_status[session_id]
            response = {
                "success": True,
                "session_id": session_id,
                "status": status.get("status"),
                "progress": status.get("progress"),
                "summary": status.get("summary", "")
            }
            
            # Include error message if status is error
            if status.get("status") == "error":
                response["error"] = status.get("error", "Unknown error")
            
            return JSONResponse(content=response)
        except Exception as e:
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return get_status


def get_pdf_handler(sessions_dir: Path):
    """Factory for get PDF endpoint handler"""
    
    async def get_pdf(session_id: str, doc_id: str):
        try:
            from app.db.models import Document
            from starlette.responses import StreamingResponse
            
            db_service = get_database_service()
            
            # Try to get PDF from database first
            document = db_service.storage.db.query(Document).filter(
                Document.id == doc_id,
                Document.session_id == session_id
            ).first()
            
            if document and document.pdf_content:
                # Use StreamingResponse to return PDF binary from database
                # Use inline disposition to display in browser, not download
                return StreamingResponse(
                    iter([document.pdf_content]),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={document.filename}"}
                )
            
            # Fallback to local file if database PDF not found
            session_dir = sessions_dir / session_id
            doc_dir = session_dir / "documents" / doc_id
            pdfs = list(doc_dir.glob("*.pdf"))
            if not pdfs:
                return JSONResponse(content={"success": False, "error": "PDF not found"})
            
            return FileResponse(pdfs[0], media_type="application/pdf")
        except Exception as e:
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return get_pdf


def get_pdf_fallback_handler(sessions_dir: Path):
    """Factory for fallback get PDF endpoint handler"""
    
    async def get_pdf_fallback(session_id: str):
        try:
            session_dir = sessions_dir / session_id
            doc_dirs = [d for d in (session_dir / "documents").iterdir() if d.is_dir()]
            if doc_dirs:
                pdfs = list(doc_dirs[0].glob("*.pdf"))
                if pdfs:
                    return FileResponse(pdfs[0], media_type="application/pdf")
            return JSONResponse(content={"success": False, "error": "PDF not found"})
        except Exception as e:
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return get_pdf_fallback


def get_delete_document_handler(sessions_dir: Path = None, working_dir: Path = None, session_status: dict = None, delete_func=None):
    """Factory for delete document endpoint handler - DATABASE ONLY"""
    
    async def delete_document(session_id: str, doc_id: str):
        try:
            print(f"\n[*] API Handler: delete_document called for {session_id}/{doc_id}", flush=True)
            
            # Call delete function
            result = await delete_func(
                session_id=session_id,
                doc_id=doc_id
            )
            
            print(f"[*] Delete function returned: {result}", flush=True)
            
            # Check if result is tuple (success, data) or just boolean
            if isinstance(result, tuple):
                success, data = result
            else:
                success = result
                data = {}
            
            if success:
                print(f"[✓] Delete successful", flush=True)
                return JSONResponse(content={
                    "success": True,
                    "message": "Document and all data deleted successfully",
                    "deleted": data if isinstance(data, dict) else {}
                })
            else:
                error_msg = data.get("error", "Failed to delete") if isinstance(data, dict) else "Failed to delete document"
                print(f"[!] Delete failed: {error_msg}", flush=True)
                return JSONResponse(content={
                    "success": False,
                    "error": error_msg
                }, status_code=400)
        
        except Exception as e:
            print(f"[!] Delete handler exception: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return JSONResponse(content={
                "success": False,
                "error": str(e)
            }, status_code=500)
    
    return delete_document


def get_query_handler(
    sessions_dir: Path,
    working_dir: Path,
    session_status: dict,
    search_func,
    search_chunks_strict,
    process_query_func,
    cleanup_func,
    format_section_func,
    format_table_func,
    llm_func,
    table_processor=None
):
    """Factory for query endpoint handler"""
    
    async def query_pdf(request: QueryRequest):
        try:
            session_id = request.session_id
            doc_id = request.doc_id
            question = request.question
            
            print(f"\n[*] Query received: session={session_id}, doc={doc_id}, q={question[:30]}...", flush=True)
            
            # Validate question
            if not question or not question.strip():
                print(f"[!] Empty question", flush=True)
                return JSONResponse(content={"success": False, "error": "Empty question"})
            
            # Validate document is selected
            if not doc_id or doc_id.strip() == "":
                print(f"[!] No document selected", flush=True)
                return JSONResponse(content={"success": False, "error": "No document selected. Please select a PDF first."})
            
            # Validate session exists and is ready
            if session_id not in session_status:
                print(f"[!] Session {session_id} not in session_status", flush=True)
                return JSONResponse(content={"success": False, "error": f"Session {session_id} not found"})
            
            if session_status[session_id].get("status") != "ready":
                print(f"[!] Session {session_id} status: {session_status[session_id].get('status')}", flush=True)
                return JSONResponse(content={"success": False, "error": f"Session not ready. Status: {session_status[session_id].get('status')}"})
            
            print(f"[✓] Validation passed, proceeding with query", flush=True)
            
            import time
            t_total_start = time.time()
            
            # Try database search first
            try:
                db_service = get_database_service()
                db_chunks = db_service.get_chunk(doc_id)  # Get chunks from PostgreSQL
                
                if db_chunks:
                    # Use database chunks
                    chunks = [{"content": chunk.content, "id": chunk.id} for chunk in db_chunks]
                    print(f"[✓] Using {len(chunks)} chunks from PostgreSQL database")
                else:
                    # Fallback to file-based search
                    chunks = await search_func(
                        session_id, doc_id, question,
                        sessions_dir, working_dir,
                        search_chunks_strict
                    )
                    print(f"[!] Database chunks empty, using file-based search")
            except Exception as db_err:
                print(f"[!] Database search failed: {db_err}, using file-based search")
                chunks = await search_func(
                    session_id, doc_id, question,
                    sessions_dir, working_dir,
                    search_chunks_strict
                )
            
            if not chunks:
                answer = "Konten dokumen tidak mencukupi untuk menjawab pertanyaan ini. Mohon tanyakan dengan kata kunci lain."
                print(f"[!] No chunks found for doc {doc_id}")
                return JSONResponse(content={"success": True, "answer": answer})
            
            context = chunks[0]['content']
            
            # Detect query type
            question_lower = question.lower()
            is_summary_query = any(kw in question_lower for kw in ['jelaskan isi dokumen', 'ringkas', 'summary', 'overview', 'ringkasan', 'apa isi dokumen', 'tentang dokumen'])
            is_table_query = any(kw in question_lower for kw in ['tabel', 'daftar', 'table', 'kategori', 'kelompok', 'peringkat', 'isi tabel', 'jelaskan tabel'])
            is_section_query = any(kw in question_lower for kw in ['menimbang', 'mengingat', 'menetapkan', 'memutuskan'])
            
            # Process query
            answer = await process_query_func(
                question, context,
                is_summary_query, is_table_query, is_section_query,
                question_lower,
                cleanup_func, format_section_func, format_table_func,
                llm_func,
                table_processor
            )
            
            t_total = time.time() - t_total_start
            print(f"[OK] Query done: {len(answer)} chars in {t_total:.2f}s", flush=True)
            
            return JSONResponse(content={
                "success": True,
                "answer": answer,
                "timing": {"total_ms": int(t_total * 1000)}
            })
        
        except Exception as e:
            print(f"[!] Query error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return query_pdf


def get_delete_session_handler(sessions_dir: Path, working_dir: Path, session_status: dict, delete_func):
    """Factory for delete session endpoint handler"""
    
    async def delete_session(session_id: str):
        try:
            success = await delete_func(
                session_id=session_id,
                sessions_dir=sessions_dir,
                working_dir=working_dir,
                session_status=session_status
            )
            
            if success:
                return JSONResponse(content={"success": True})
            else:
                return JSONResponse(content={"success": False, "error": "Failed to delete session"})
        
        except Exception as e:
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return delete_session


def get_ui_handler():
    """Factory for UI serving endpoint handler"""
    
    async def serve_ui():
        return FileResponse(Path(__file__).parent.parent.parent / "ui" / "index.html")
    
    return serve_ui
