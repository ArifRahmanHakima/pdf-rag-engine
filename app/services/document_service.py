"""
Document processing service - handles PDF ingestion and RAG integration
"""

import json
import time
import shutil
from pathlib import Path
from datetime import datetime

from app.utils.text_processing import split_text_into_chunks


async def ingest_pdf_async(
    session_id: str,
    pdf_path: str,
    filename: str,
    doc_id: str,
    rag_instance,
    sessions_dir: Path,
    working_dir: Path,
    session_status: dict,
    extract_text_func
):
    """
    Ingest PDF into RAG system with document isolation
    
    Args:
        session_id: Session identifier
        pdf_path: Path to PDF file
        filename: Original filename
        doc_id: Document identifier
        rag_instance: LightRAG instance
        sessions_dir: Sessions directory path
        working_dir: Working directory path
        session_status: Session status dictionary (to update)
        extract_text_func: Function to extract text from PDF (from main_openrouter.py)
    """
    try:
        print(f"\n[*] Processing {filename}", flush=True)
        file_start = time.time()
        
        # Extract text with OCR
        print(f"    Extracting text with OCR...", end='', flush=True)
        ocr_start = time.time()
        text = extract_text_func(pdf_path, use_ocr=True)
        ocr_time = time.time() - ocr_start
        print(f" [{ocr_time:.2f}s]", flush=True)
        
        if not text.strip():
            print(f"[!] No text extracted\n", flush=True)
            session_status[session_id]["status"] = "error"
            return False
        
        # Split text into chunks
        print(f"    Splitting text into chunks...", end='', flush=True)
        chunks = split_text_into_chunks(text)
        print(f" ({len(chunks)} chunks)", flush=True)
        
        # Insert into RAG with document tracking
        print(f"    Inserting into RAG (knowledge graph)...", end='', flush=True)
        rag_start = time.time()
        
        for chunk_text in chunks:
            # Add document metadata to text for tracking
            chunk_with_doc_id = f"[DOC_ID:{doc_id}]\n{chunk_text}"
            await rag_instance.ainsert(chunk_with_doc_id)
        
        rag_time = time.time() - rag_start
        print(f" [{rag_time:.2f}s]", flush=True)
        
        file_time = time.time() - file_start
        
        # Save chunks per document
        session_dir = sessions_dir / session_id
        src_chunks = Path(working_dir) / "kv_store_text_chunks.json"
        
        # Create document-specific chunk directory
        doc_chunks_dir = session_dir / "documents" / doc_id
        doc_chunks_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy chunks file for THIS document ONLY
        if src_chunks.exists():
            dst_chunks = doc_chunks_dir / "chunks.json"
            shutil.copy(src_chunks, dst_chunks)
            print(f"[✓] Chunks reference saved to document {doc_id}\n")
        
        num_pages = text.count("=== Page")
        
        # Extract full_doc_id from newly created chunks
        full_doc_id = None
        try:
            src_chunks = Path(working_dir) / "kv_store_text_chunks.json"
            if src_chunks.exists():
                with open(src_chunks, encoding='utf-8', errors='ignore') as f:
                    all_chunks = json.load(f)
                    # Find first chunk with full_doc_id
                    for chunk_id, chunk_data in all_chunks.items():
                        if isinstance(chunk_data, dict) and 'full_doc_id' in chunk_data:
                            full_doc_id = chunk_data['full_doc_id']
                            break
        except Exception as e:
            print(f"[!] Error extracting full_doc_id: {e}")
        
        # Update session document list
        session_docs_file = session_dir / "documents.json"
        docs = {}
        if session_docs_file.exists():
            with open(session_docs_file) as f:
                docs = json.load(f)
        
        docs[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "upload_time": datetime.now().isoformat(),
            "pages": num_pages,
            "size": len(text),
            "full_doc_id": full_doc_id
        }
        
        with open(session_docs_file, 'w') as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)
        
        # Update status
        if session_id not in session_status:
            session_status[session_id] = {"status": "ready", "selected_doc": doc_id}
        else:
            session_status[session_id]["status"] = "ready"
            if "selected_doc" not in session_status[session_id]:
                session_status[session_id]["selected_doc"] = doc_id
        
        print(f"[✓] Ingested in {file_time:.2f}s total (OCR: {ocr_time:.2f}s, RAG: {rag_time:.2f}s)\n", flush=True)
        return True
    
    except Exception as e:
        print(f"[!] Error: {str(e)[:80]}\n", flush=True)
        import traceback
        traceback.print_exc()
        session_status[session_id]["status"] = "error"
        return False
