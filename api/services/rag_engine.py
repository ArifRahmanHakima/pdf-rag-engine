import os
import asyncio
import hashlib
import time
from datetime import datetime
from dotenv import load_dotenv
from api.services.pdf_processor import (
    query_document_async,
    get_doc_id,
    remove_references,
    get_rag_instance_sync,
    get_rag_instance_async,
    rag_instances
)

load_dotenv()

# === BACKWARD COMPATIBILITY - Wrapper functions untuk kompatibilitas dengan chat.py ===

async def process_pdf(file_path: str):
    """Process PDF - wrapper untuk backward compatibility"""
    from api.services.pdf_processor import process_pdf_async
    return await process_pdf_async(file_path)

async def generate_summary(file_path: str, doc_id: str):
    """Generate summary - wrapper untuk backward compatibility"""
    from api.services.pdf_processor import generate_summary_async
    return await generate_summary_async(file_path, doc_id)

async def query_document(doc_id: str, question: str, top_k: int = 3):
    """Query document - wrapper untuk backward compatibility"""
    return await query_document_async(doc_id, question, top_k)

def list_documents():
    """List all processed documents"""
    return list(rag_instances.keys())

def clear_document_cache(doc_id: str = None):
    """Clear RAG instance cache for specific or all documents"""
    if doc_id:
        if doc_id in rag_instances:
            del rag_instances[doc_id]
            print(f"🗑️ Cleared cache for doc_id: {doc_id}")
    else:
        rag_instances.clear()
        print("🗑️ Cleared all document caches")

    
async def process_pdf(file_path: str):
    """Process PDF - wrapper untuk backward compatibility"""
    from api.services.pdf_processor import process_pdf_async
    return await process_pdf_async(file_path)