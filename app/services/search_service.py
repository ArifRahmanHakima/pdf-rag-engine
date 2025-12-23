"""
Search service - handles document search and retrieval
"""

import re
from pathlib import Path


async def search_chunks_from_session(session_id: str, doc_id: str, query: str, sessions_dir: Path, working_dir: Path, search_func):
    """
    Search chunks using lenient algorithm
    
    Args:
        session_id: Session identifier
        doc_id: Document identifier
        query: Search query
        sessions_dir: Sessions directory path
        working_dir: Working directory path
        search_func: Search function from search_logic.py (search_chunks_strict)
    """
    try:
        # Call the optimized search function from search_logic
        best_chunks = await search_func(
            query=query,
            session_id=session_id,
            doc_id=doc_id,
            SESSIONS_DIR=sessions_dir,
            WORKING_DIR=working_dir
        )
        
        if not best_chunks:
            print(f"[!] No chunks found for query: {query[:50]}", flush=True)
            return []
        
        # Combine chunks with newline separator
        combined = "\n".join(best_chunks)
        
        # Clean up OCR artifacts and extra whitespace
        # Remove page markers
        combined = re.sub(r'=== Page \d+ ===', '', combined, flags=re.IGNORECASE)
        combined = re.sub(r'===\s*', '', combined)
        
        # Remove multiple spaces (but keep intentional spacing in tables)
        combined = re.sub(r' {3,}', '  ', combined)  # Triple+ -> double space
        
        # Remove multiple newlines
        combined = re.sub(r'\n\n\n+', '\n\n', combined)
        
        # Remove strange unicode characters and control chars
        combined = ''.join(c for c in combined if ord(c) >= 32 or c in '\n\t')
        
        # Fix common OCR artifacts
        combined = re.sub(r'([^\w])\|\|([^\w])', r'\1|\2', combined)  # Fix || artifacts
        
        # Clean up extra spaces at line start/end
        lines = combined.split('\n')
        lines = [line.strip() for line in lines]
        combined = '\n'.join(lines)
        
        combined = combined.strip()
        
        # Limit context length - INCREASED for better coverage
        # For section/table queries: up to 25000 chars (full section content)
        # For general queries: 8000 chars (enough for summary)
        if any(w in query.lower() for w in ['menimbang', 'mengingat', 'menetapkan', 'tabel', 'daftar']):
            max_context_len = 25000  # More for section/table queries
        else:
            max_context_len = 8000  # Reduced for general queries
        
        if len(combined) > max_context_len:
            combined = combined[:max_context_len]
            print(f"[*] Context truncated to {max_context_len} chars")
        
        print(f"[*] Found {len(best_chunks)} chunks, context: {len(combined)} chars", flush=True)
        return [{'content': combined}]
    
    except Exception as e:
        print(f"[!] Search error: {e}")
        import traceback
        traceback.print_exc()
        return []
