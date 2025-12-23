"""
API endpoint handlers for PDF operations
"""

from pathlib import Path
from datetime import datetime
from fastapi import UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel


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
            rag_instance = rag_instance_getter()  # Call to get current instance
            if rag_instance is None:
                return JSONResponse(content={"success": False, "error": "RAG not ready"})
            
            session_id = get_next_session_func(sessions_dir)
            session_dir = sessions_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Create unique doc_id from filename (remove extension)
            doc_id = Path(file.filename).stem
            doc_upload_dir = session_dir / "documents" / doc_id
            doc_upload_dir.mkdir(parents=True, exist_ok=True)
            
            # Save PDF
            pdf_path = doc_upload_dir / file.filename
            with open(pdf_path, 'wb') as f:
                f.write(await file.read())
            
            # Save metadata
            save_metadata_func(session_id, {
                "session_id": session_id,
                "filename": file.filename,
                "upload_time": datetime.now().isoformat(),
                "status": "ingesting"
            }, sessions_dir)
            
            session_status[session_id] = {
                "status": "ingesting",
                "progress": "Processing...",
                "selected_doc": doc_id
            }
            
            # Background ingest
            if background_tasks:
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
                    extract_text_func
                )
            
            return JSONResponse(content={
                "success": True,
                "session_id": session_id,
                "doc_id": doc_id,
                "filename": file.filename
            })
        
        except Exception as e:
            print(f"[!] Upload error: {e}")
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return upload_pdf


def get_documents_handler(sessions_dir: Path, session_status: dict, get_metadata_func):
    """Factory for get documents endpoint handler"""
    
    async def get_documents(session_id: str):
        try:
            session_dir = sessions_dir / session_id
            docs_file = session_dir / "documents.json"
            
            if not docs_file.exists():
                return JSONResponse(content={"success": True, "documents": []})
            
            import json
            with open(docs_file) as f:
                docs = json.load(f)
            
            docs_list = list(docs.values())
            selected_doc = session_status.get(session_id, {}).get("selected_doc", None)
            
            doc_ids = [doc["doc_id"] for doc in docs_list]
            
            if selected_doc not in doc_ids:
                if docs_list:
                    selected_doc = docs_list[0]["doc_id"]
                    session_status[session_id]["selected_doc"] = selected_doc
                    print(f"[!] FIXED stale selected_doc - switched to: {selected_doc}", flush=True)
                else:
                    selected_doc = None
            
            return JSONResponse(content={
                "success": True,
                "documents": docs_list,
                "selected_doc": selected_doc
            })
        except Exception as e:
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
    """Factory for list sessions endpoint handler"""
    
    async def list_sessions():
        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
            sessions = []
            for sd in sessions_dir.iterdir():
                if sd.is_dir():
                    m = get_metadata_func(sd.name, sessions_dir)
                    if m:
                        sessions.append(m)
            
            return JSONResponse(content={
                "success": True,
                "sessions": sorted(sessions, key=lambda x: x.get("upload_time", ""), reverse=True)
            })
        except Exception as e:
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return list_sessions


def get_status_handler(session_status: dict):
    """Factory for get status endpoint handler"""
    
    async def get_status(session_id: str):
        try:
            if session_id not in session_status:
                return JSONResponse(content={"success": False, "error": "Not found"})
            
            status = session_status[session_id]
            return JSONResponse(content={
                "success": True,
                "session_id": session_id,
                "status": status.get("status"),
                "progress": status.get("progress"),
                "summary": status.get("summary", "")
            })
        except Exception as e:
            return JSONResponse(content={"success": False, "error": str(e)})
    
    return get_status


def get_pdf_handler(sessions_dir: Path):
    """Factory for get PDF endpoint handler"""
    
    async def get_pdf(session_id: str, doc_id: str):
        try:
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


def get_delete_document_handler(sessions_dir: Path, working_dir: Path, session_status: dict, delete_func):
    """Factory for delete document endpoint handler"""
    
    async def delete_document(session_id: str, doc_id: str):
        try:
            success = await delete_func(
                session_id=session_id,
                doc_id=doc_id,
                sessions_dir=sessions_dir,
                working_dir=working_dir,
                session_status=session_status
            )
            
            if success:
                return JSONResponse(content={"success": True, "message": "Document and all data deleted successfully"})
            else:
                return JSONResponse(content={"success": False, "error": "Failed to delete document"})
        
        except Exception as e:
            print(f"[!] Delete error: {e}")
            return JSONResponse(content={"success": False, "error": str(e)})
    
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
            
            if not question or not question.strip():
                return JSONResponse(content={"success": False, "error": "Empty question"})
            
            if not doc_id:
                return JSONResponse(content={"success": False, "error": "No document selected"})
            
            if session_id not in session_status or session_status[session_id].get("status") != "ready":
                return JSONResponse(content={"success": False, "error": "Session not ready"})
            
            print(f"[*] Query (doc={doc_id}): {question[:50]}...", flush=True)
            
            import time
            t_total_start = time.time()
            
            # Search chunks
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
