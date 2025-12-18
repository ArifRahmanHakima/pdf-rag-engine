"""
IMPROVED SEARCH LOGIC - Multi-pass retrieval with fallback
Strategy: Retrieve MORE chunks, let LLM decide relevance
"""
import re
import json
from pathlib import Path

async def search_chunks_strict(query: str, session_id: str, doc_id: str, SESSIONS_DIR, WORKING_DIR):
    """
    IMPROVED retrieval - Retrieve 50+ chunks and combine intelligently
    Focus: Get ALL relevant chunks, don't filter too aggressively
    """
    try:
        # Load chunks
        session_dir = Path(SESSIONS_DIR) / session_id
        doc_chunks_path = session_dir / "documents" / doc_id / "chunks.json"
        
        if not doc_chunks_path.exists():
            print(f"[!] Chunks file not found", flush=True)
            return []
        
        with open(doc_chunks_path, encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            chunks = []
            doc_id_marker = f"[DOC_ID:{doc_id}]"
            
            for chunk_id, item in data.items():
                if isinstance(item, dict) and 'content' in item:
                    content = item['content']
                    if doc_id_marker in content:
                        content = content.replace(f"{doc_id_marker}\n", "").strip()
                        if content and len(content) > 50:  # Minimum length
                            chunks.append(content)
        
        if not chunks:
            print(f"[!] No chunks found for doc {doc_id}", flush=True)
            return []
        
        print(f"[*] Total chunks: {len(chunks)}", flush=True)
        
        # ========== SIMPLE BUT EFFECTIVE SCORING ==========
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        
        # Detect section queries
        sections = ['menimbang', 'mengingat', 'menetapkan', 'dasar', 'pertimbangan']
        target_section = None
        for sec in sections:
            if sec in query_lower:
                target_section = sec.upper()
                break
        
        scores = []
        
        for chunk_idx, chunk in enumerate(chunks):
            chunk_lower = chunk.lower()
            chunk_upper = chunk.upper()
            score = 0.0
            
            # ===== EXACT MATCHES (HIGHEST PRIORITY) =====
            # Direct section match
            if target_section and target_section in chunk_upper:
                score += 1000  # MASSIVE boost
            
            # Query words match
            word_matches = sum(1 for w in query_words if w in chunk_lower)
            score += word_matches * 100  # 100 per word match
            
            # ===== TABLE/DAFTAR DETECTION =====
            if any(kw in query_lower for kw in ['tabel', 'daftar', 'kategori', 'list']):
                table_markers = ['│', '|', '─', 'DAFTAR', 'Nama', 'Kategori']
                if any(m in chunk for m in table_markers):
                    score += 500  # Table boost
            
            # ===== SECTION HEADERS =====
            section_patterns = [
                r'^MENIMBANG\s*:', 
                r'^MENGINGAT\s*:',
                r'^MENETAPKAN\s*:',
                r'^Dasar Hukum',
                r'^\d+\.\s+[A-Z]'  # Numbered items
            ]
            
            for pattern in section_patterns:
                if re.search(pattern, chunk, re.MULTILINE | re.IGNORECASE):
                    score += 300
            
            # ===== FALLBACK: Any content match =====
            if word_matches > 0:
                score += 10  # Ensure non-zero for matches
            
            scores.append((chunk_idx, score))
        
        # ========== RETRIEVE CHUNKS ==========
        # Sort by score descending
        sorted_chunks = sorted(scores, key=lambda x: x[1], reverse=True)
        
        # STRATEGY:
        # 1. If high scores, take top 30-50
        # 2. If low scores, take top 40 ANYWAY (don't be too strict)
        # 3. Combine all
        
        max_score = sorted_chunks[0][1] if sorted_chunks else 0
        
        if max_score > 100:  # Good matches found
            num_to_take = min(50, len(sorted_chunks))
        else:  # Poor matches, take more anyway
            num_to_take = min(40, len(sorted_chunks))
        
        selected_indices = [idx for idx, _ in sorted_chunks[:num_to_take]]
        selected_chunks = [chunks[i] for i in selected_indices]
        
        print(f"[*] Selected {len(selected_chunks)} chunks (max_score={max_score:.0f})", flush=True)
        
        # ========== RETURN CHUNKS ==========
        # Return as list so main_server.py can join
        return selected_chunks
    
    except Exception as e:
        print(f"[!] Search error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return []
