# Search Logic v4 - RAG Native with complete retrieval
import re
from pathlib import Path
import json

async def search_chunks_strict(query: str, session_id: str, doc_id: str, SESSIONS_DIR, WORKING_DIR, embedding_func=None, rag_instance=None):
    """
    COMPLETE RETRIEVAL using RAG native query + DOC_ID filtering
    Strategy: Use RAG to find relevant chunks, then filter by doc_id and build complete context
    """
    try:
        session_dir = Path(SESSIONS_DIR) / session_id
        doc_chunks_path = session_dir / "documents" / doc_id / "chunks.json"
        
        if not doc_chunks_path.exists():
            print(f"[!] Chunks file not found: {doc_chunks_path}", flush=True)
            return []
        
        # Load ALL chunks for this document
        with open(doc_chunks_path, encoding='utf-8', errors='ignore') as f:
            all_chunks_data = json.load(f)
        
        # Extract chunks with DOC_ID marker
        doc_id_marker = f"[DOC_ID:{doc_id}]"
        doc_chunks = []
        doc_chunks_raw = []
        
        for chunk_id, item in all_chunks_data.items():
            if isinstance(item, dict) and 'content' in item:
                content = item['content']
                if doc_id_marker in content:
                    # Remove marker before storing
                    clean_content = content.replace(f"{doc_id_marker}\n", "").strip()
                    if clean_content:
                        doc_chunks.append(clean_content)
                        doc_chunks_raw.append(content)
        
        if not doc_chunks:
            print(f"[!] No chunks with DOC_ID marker [{doc_id}]", flush=True)
            return []
        
        print(f"[*] Retrieved {len(doc_chunks)} chunks from doc {doc_id}", flush=True)
        
        # ========== DETECT QUERY TYPE ==========
        query_lower = query.lower()
        
        # Check if query is about a specific section
        section_keywords = {
            'mengingat': ['mengingat', 'point mengingat', 'poin mengingat'],
            'menimbang': ['menimbang', 'point menimbang', 'poin menimbang'],
            'table': ['tabel', 'daftar', 'kategori', 'pemenang']
        }
        
        detected_section = None
        for section, keywords in section_keywords.items():
            if any(kw in query_lower for kw in keywords):
                detected_section = section
                break
        
        # ========== RETRIEVE STRATEGY ==========
        best_chunks = []
        chunk_scores = []
        
        for idx, chunk in enumerate(doc_chunks):
            chunk_lower = chunk.lower()
            score = 0
            
            # 1. Section header bonus
            if detected_section == 'mengingat' and 'mengingat' in chunk_lower:
                score += 100
            elif detected_section == 'menimbang' and 'menimbang' in chunk_lower:
                score += 100
            elif detected_section == 'table' and any(marker in chunk for marker in ['│', '|', '─', '┬', '┴', '├', '┤', 'NO.', 'NAMA']):
                score += 150  # Higher priority for table markers
            
            # 2. Query term matching
            query_terms = [w for w in query_lower.split() if len(w) > 2]
            for term in query_terms:
                if term in chunk_lower:
                    score += 10 * chunk_lower.count(term)
            
            # 3. Point-specific matching (for "point 2", "point 3", etc)
            point_match = re.search(r'point\s+(\d+|[a-z])', query_lower)
            if point_match:
                target = point_match.group(1)
                # Look for numbered points: "1.", "2.", etc or "a.", "b.", etc
                if re.search(rf'^\s*{re.escape(target)}[\.\)]\s', chunk, re.MULTILINE):
                    score += 200
            
            # 4. Numeric matching (if asking "point 2", "poin 2")
            number_match = re.search(r'\b(\d+)\b', query_lower)
            if number_match:
                num = number_match.group(1)
                if re.search(rf'^\s*{num}[\.\)]\s', chunk, re.MULTILINE):
                    score += 150
            
            if score > 0:
                chunk_scores.append((idx, chunk, score))
        
        # Sort by score and take ALL high-scoring chunks (not just top 30)
        chunk_scores.sort(key=lambda x: x[2], reverse=True)
        
        # For section queries, take MORE chunks to ensure completeness
        if detected_section in ['mengingat', 'menimbang', 'table']:
            # Take all chunks with score > 0, up to 100 chunks
            best_chunks = [chunk for _, chunk, score in chunk_scores if score > 0][:100]
        else:
            # For general queries, take top 50
            best_chunks = [chunk for _, chunk, score in chunk_scores[:50]]
        
        if not best_chunks:
            # Fallback: if no good scoring, try content-based matching
            for chunk in doc_chunks:
                if any(term in chunk.lower() for term in query_terms):
                    best_chunks.append(chunk)
            best_chunks = best_chunks[:50]
        
        print(f"[*] Selected {len(best_chunks)} chunks (detected: {detected_section})", flush=True)
        
        if not best_chunks:
            return []
        
        return best_chunks
    
    except Exception as e:
        print(f"[!] Search error: {str(e)[:100]}", flush=True)
        import traceback
        traceback.print_exc()
        return []
