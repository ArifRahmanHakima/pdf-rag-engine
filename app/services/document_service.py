"""
Document processing service - handles PDF ingestion and RAG integration
"""

import json
import time
import shutil
import asyncio
from pathlib import Path
from datetime import datetime

from app.utils.text_processing import split_text_into_chunks, clean_docstring_markdown
from app.utils import save_session_metadata


async def ingest_pdf_async(
    session_id: str,
    pdf_path: str,
    filename: str,
    doc_id: str,
    rag_instance,
    sessions_dir: Path,
    working_dir: Path,
    session_status: dict,
    extract_text_func,
    docstring_api_key: str = None
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
        extract_text_func: Function to extract text from PDF
        docstring_api_key: Optional API key if using DocString extraction
    """
    try:
        print(f"\n[*] Processing {filename}", flush=True)
        file_start = time.time()
        
        # Extract text - support both OCR and DocString extractors
        extractor_type = "DocString" if docstring_api_key and "docstring" in doc_id else "OCR"
        print(f"    Extracting text with {extractor_type}...", end='', flush=True)
        ocr_start = time.time()
        
        if docstring_api_key and "docstring" in doc_id:
            # Use DocString extractor with API key
            # Note: extract_text_func may return a coroutine (async function)
            result = extract_text_func(pdf_path, docstring_api_key)
            # Check if result is a coroutine and await it
            import inspect
            if inspect.iscoroutine(result):
                text = await result
            else:
                text = result
            
            # Clean DocString markdown output (remove HTML tags, noise, etc)
            text = clean_docstring_markdown(text)
            
            # DEBUG: Save cleaned output to file for inspection
            session_dir = sessions_dir / session_id
            doc_chunks_dir = session_dir / "documents" / doc_id
            doc_chunks_dir.mkdir(parents=True, exist_ok=True)
            debug_output_file = doc_chunks_dir / "docstring_cleaned_output.md"
            with open(debug_output_file, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"\n[DEBUG] DocString cleaned output saved to {debug_output_file}", flush=True)
        else:
            # Use existing OCR extractor
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
        
        # DEBUG: Show first chunk to inspect structure
        if chunks:
            print(f"[DEBUG] First chunk ({len(chunks[0])} chars):\n{chunks[0][:500]}...\n", flush=True)
        
        # Insert into RAG with document tracking (PARALLEL/CONCURRENT)
        print(f"    Inserting into RAG (knowledge graph)...", end='', flush=True)
        rag_start = time.time()
        
        # Create tasks for parallel insertion
        insert_tasks = []
        for chunk_text in chunks:
            # Add document metadata to text for tracking
            chunk_with_doc_id = f"[DOC_ID:{doc_id}]\n{chunk_text}"
            # Create coroutine (don't await yet - collect all tasks)
            insert_tasks.append(rag_instance.ainsert(chunk_with_doc_id))
        
        # Execute all inserts concurrently (parallel)
        if insert_tasks:
            await asyncio.gather(*insert_tasks)
        
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
        
        # Save updated metadata to file (important: persists status change to disk)
        session_dir = sessions_dir / session_id
        metadata_file = session_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, encoding='utf-8') as f:
                metadata = json.load(f)
            metadata["status"] = "ready"  # Update status to ready
            metadata["ingested_at"] = datetime.now().isoformat()
            save_session_metadata(session_id, metadata, sessions_dir)
            print(f"[✓] Metadata saved with status=ready", flush=True)
        
        print(f"[✓] Ingested in {file_time:.2f}s total (OCR: {ocr_time:.2f}s, RAG: {rag_time:.2f}s)\n", flush=True)
        return True
    
    except Exception as e:
        print(f"[!] Error: {str(e)[:80]}\n", flush=True)
        import traceback
        traceback.print_exc()
        session_status[session_id]["status"] = "error"
        return False
