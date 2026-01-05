"""
DocString Upload Handler - API endpoint factory untuk /api/upload-docstring
"""

from fastapi import UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime
from pathlib import Path


def get_upload_handler_docstring(
    rag_instance_getter,
    sessions_dir: Path,
    session_status: dict,
    get_next_session_func,
    save_metadata_func,
    ingest_func,
    extract_with_docstring_func,
    docstring_api_key: str
):
    """
    Factory function untuk create /api/upload-docstring endpoint handler
    
    Implements identical pattern ke existing OCR upload, hanya dengan DocString extractor
    
    Args:
        rag_instance_getter: Callable yang return current RAG instance
        sessions_dir: Path ke pdf_sessions directory
        session_status: Dict untuk track session status
        get_next_session_func: Function untuk generate session ID
        save_metadata_func: Function untuk save session metadata
        ingest_func: Function untuk background PDF ingest (reused from existing)
        extract_with_docstring_func: DocString extraction function
        docstring_api_key: API key untuk DocString
    
    Returns:
        async function: upload_pdf_docstring handler
    """
    
    async def upload_pdf_docstring(
        file: UploadFile = File(...), 
        background_tasks: BackgroundTasks = None
    ):
        """
        Handle POST /api/upload-docstring requests
        
        Flow:
        1. Validate RAG instance ready
        2. Create session directory structure
        3. Save uploaded PDF
        4. Queue background ingest task
        5. Return session_id + doc_id to frontend
        
        Frontend will poll /api/status/{session_id} untuk wait sampai "ready"
        """
        try:
            # Initialize RAG instance on first use (same as OCR handler)
            from main_server import _initialize_rag_instance
            rag_instance = await _initialize_rag_instance()
            
            if rag_instance is None:
                return JSONResponse(
                    content={"success": False, "error": "RAG initialization failed"},
                    status_code=503
                )
            
            # Generate new session
            session_id = get_next_session_func(sessions_dir)
            
            # DISABLED: Local file storage
            # session_dir = sessions_dir / session_id
            # session_dir.mkdir(parents=True, exist_ok=True)
            # doc_upload_dir = session_dir / "documents" / doc_id
            # doc_upload_dir.mkdir(parents=True, exist_ok=True)
            # pdf_path = doc_upload_dir / file.filename
            # with open(pdf_path, 'wb') as f:
            #     f.write(await file.read())
            
            # Create document ID (same format as OCR - will use doc_type field to differentiate)
            doc_id = Path(file.filename).stem
            
            # Store PDF in memory for processing
            pdf_content = await file.read()
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_content)
                pdf_path = tmp.name
            
            print(f"[✓] PDF buffered in memory for processing", flush=True)
            
            # DISABLED: Local metadata file storage
            # save_metadata_func(session_id, {
            #     "session_id": session_id,
            #     "filename": file.filename,
            #     "upload_time": datetime.now().isoformat(),
            #     "status": "ingesting",
            #     "extractor": "docstring"
            # }, sessions_dir)
            
            # Update session status untuk frontend polling
            session_status[session_id] = {
                "status": "ingesting",
                "progress": "Processing with DocString API...",
                "selected_doc": doc_id
            }
            
            print(f"[*] Starting background ingest: session={session_id}, doc={doc_id}", flush=True)
            
            # Queue background ingest task (same function as OCR, just different extractor)
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
                    extract_with_docstring_func,  # Pass DocString extractor
                    docstring_api_key,  # Pass API key
                    pdf_content  # Pass PDF binary content (CRITICAL FIX)
                )
            
            return JSONResponse(content={
                "success": True,
                "session_id": session_id,
                "doc_id": doc_id,
                "filename": file.filename,
                "extractor": "docstring"
            })
        
        except Exception as e:
            error_msg = str(e)
            print(f"[!] DocString Upload error: {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            
            # Update session status with error message
            if session_id in locals():
                session_status[session_id] = {
                    "status": "error",
                    "error": error_msg
                }
            
            return JSONResponse(
                content={"success": False, "error": error_msg},
                status_code=500
            )
    
    return upload_pdf_docstring
