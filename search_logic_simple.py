# SIMPLE & ROBUST search logic
import json
import re
from pathlib import Path

async def search_chunks_strict(query: str, session_id: str, doc_id: str, SESSIONS_DIR, WORKING_DIR, embedding_func=None):
    """
    ULTRA-SIMPLE SEARCH - Return ALL chunks for complete coverage
    """
    try:
        # Load chunks from selected document
        session_dir = Path(SESSIONS_DIR) / session_id
        doc_chunks_path = session_dir / "documents" / doc_id / "chunks.json"
        
        if not doc_chunks_path.exists():
            print(f"[!] Chunks file not found: {doc_chunks_path}", flush=True)
            return []
        
        with open(doc_chunks_path, encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            
            # Extract ALL chunks - no filtering by marker
            all_chunks = []
            
            for chunk_id, item in data.items():
                if isinstance(item, dict) and 'content' in item:
                    content = item['content']
                    
                    # Remove any DOC_ID markers that might exist
                    content = re.sub(r'\[DOC_ID:[^\]]+\]\s*', '', content)
                    content = content.strip()
                    
                    if content and len(content) > 20:  # Only include meaningful chunks
                        all_chunks.append(content)
            
            if not all_chunks:
                print(f"[!] No chunks found in: {doc_chunks_path}", flush=True)
                return []
            
            print(f"[*] Retrieved {len(all_chunks)} chunks from doc {doc_id}", flush=True)
            
            # Sort by relevance to query
            query_lower = query.lower()
            query_terms = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]
            
            scored_chunks = []
            for chunk in all_chunks:
                chunk_lower = chunk.lower()
                score = 0
                
                # Score based on term matches
                for term in query_terms:
                    score += chunk_lower.count(term) * 2
                
                # Bonus for section headers
                if re.search(r'^\s*(menimbang|mengingat|dasar|pertimbangan)\s*[:.]', chunk_lower, re.MULTILINE | re.IGNORECASE):
                    score += 50
                
                # Bonus for numbered items (1., 2., 3., etc)
                if re.search(r'^\s*\d+[\.\)]\s', chunk_lower, re.MULTILINE):
                    score += 20
                
                # Bonus for table markers
                if any(marker in chunk_lower for marker in ['│', '|', '─', '┌', '└', 'daftar', 'tabel', 'kategori']):
                    score += 30
                
                scored_chunks.append((chunk, score))
            
            # Sort by score, but ALWAYS return all chunks if score is low
            scored_chunks.sort(key=lambda x: x[1], reverse=True)
            
            # Return chunks sorted by score (best first)
            result_chunks = [chunk for chunk, _ in scored_chunks]
            
            print(f"[*] Returning all {len(result_chunks)} chunks sorted by relevance", flush=True)
            return result_chunks
    
    except Exception as e:
        print(f"[!] Search error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return []
