#!/usr/bin/env python
"""Check database state"""

from app.db.storage_manager import StorageManager
from app.db.models import Document

db_manager = StorageManager()
try:
    sessions = db_manager.get_all_sessions()
    print(f"Found {len(sessions)} sessions")
    for ses in sessions:
        print(f"\nSession: {ses.id}")
        docs = db_manager.db.query(Document).filter(Document.session_id == ses.id).all()
        print(f"  Documents: {len(docs)}")
        for doc in docs:
            has_pdf = doc.pdf_content is not None
            pdf_size = len(doc.pdf_content) if doc.pdf_content else 0
            print(f"    - {doc.filename}: has_pdf={has_pdf}, pdf_size={pdf_size} bytes, doc_size={doc.size}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
