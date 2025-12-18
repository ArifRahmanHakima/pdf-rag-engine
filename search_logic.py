# Dedicated search logic - COMPLETE section retrieval
import re
import numpy as np
from pathlib import Path
import json
import os
import time

async def search_chunks_strict(query: str, session_id: str, doc_id: str, SESSIONS_DIR, WORKING_DIR, embedding_func=None):
    """
    AGGRESSIVE SEARCH - Designed to retrieve relevant chunks from selected document
    Priority: Section > Table > Term frequency
    """
    import asyncio
    
    t0 = time.time()
    try:
        # Load chunks from selected document only
        session_dir = Path(SESSIONS_DIR) / session_id
        doc_chunks_path = session_dir / "documents" / doc_id / "chunks.json"
        
        if not doc_chunks_path.exists():
            print(f"[!] Chunks not found for doc={doc_id}", flush=True)
            return []
        
        with open(doc_chunks_path, encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            chunks = []
            doc_id_marker = f"[DOC_ID:{doc_id}]"
            
            for chunk_id, item in data.items():
                if isinstance(item, dict) and 'content' in item:
                    content = item['content']
                    
                    # Load ALL chunks from the document
                    # (Marker might not be on all chunks if LightRAG split them)
                    chunks.append(content)
        
        if not chunks:
            print(f"[!] No chunks found for doc={doc_id}", flush=True)
            return []
        
        print(f"[*] Searching {len(chunks)} chunks from doc {doc_id}: '{query[:60]}'", flush=True)
        
        query_lower = query.lower()
        
        # ========== DETECT QUERY TYPE ==========
        section_keywords = ['menimbang', 'mengingat', 'menetapkan', 'mempertimbangkan', 'konsiderasi', 'dasar', 'pertimbangan']
        table_keywords = ['tabel', 'daftar', 'table', 'nama', 'list', 'siapa', 'data', 'kategori', 'kelompok']
        
        requested_section = None
        is_table_query = False
        
        for sec in section_keywords:
            if sec in query_lower:
                requested_section = sec
                break
        
        if any(kw in query_lower for kw in table_keywords):
            is_table_query = True
        
        if requested_section:
            print(f"[*] TYPE: SECTION QUERY ('{requested_section}')", flush=True)
        elif is_table_query:
            print(f"[*] TYPE: TABLE QUERY", flush=True)
        else:
            print(f"[*] TYPE: GENERAL QUERY", flush=True)
        
        # ========== SCORE CHUNKS ==========
        scores = []
        
        # For section queries: find ALL chunks that belong to that section
        section_chunk_indices = set()
        if requested_section:
            section_started = False
            for idx, chunk in enumerate(chunks):
                chunk_lower = chunk.lower()
                
                # Check if this chunk starts the requested section
                if re.search(rf'^\s*{requested_section}\s*[:.]', chunk_lower, re.MULTILINE | re.IGNORECASE):
                    section_started = True
                    section_chunk_indices.add(idx)
                    print(f"[*] Section '{requested_section}' STARTS at chunk {idx}", flush=True)
                # While section is active, add chunks until next major section
                elif section_started:
                    # Check if a DIFFERENT section starts (means our section ended)
                    different_section_found = False
                    for other_sec in section_keywords:
                        if other_sec != requested_section:
                            if re.search(rf'^\s*{other_sec}\s*[:.]', chunk_lower, re.MULTILINE | re.IGNORECASE):
                                different_section_found = True
                                section_started = False
                                print(f"[*] Section '{requested_section}' ENDS before chunk {idx} (found '{other_sec}')", flush=True)
                                break
                    
                    if not different_section_found:
                        # Still in same section
                        section_chunk_indices.add(idx)
            
            print(f"[*] Found {len(section_chunk_indices)} chunks in section '{requested_section}'", flush=True)
        
        for chunk_idx, chunk in enumerate(chunks):
            chunk_lower = chunk.lower()
            score = 0.0
            
            # ===== SECTION MATCHING - HIGHEST PRIORITY =====
            if requested_section:
                if chunk_idx in section_chunk_indices:
                    # INSIDE the requested section
                    score += 500.0  # High score for being in correct section
                    
                    # Check if chunk is header or content
                    if re.search(rf'^\s*{requested_section}\s*[:.]', chunk_lower, re.MULTILINE | re.IGNORECASE):
                        score += 300.0  # Extra bonus for section header
                    
                    # BOOST for chunks with numbered/lettered points (high chance of valuable content)
                    point_count = len(re.findall(r'^\s*[0-9a-z][\.)\:]', chunk_lower, re.MULTILINE))
                    if point_count > 0:
                        score += point_count * 50.0  # Points are valuable in sections
                else:
                    # NOT in requested section -> strong penalty
                    score -= 500.0
                    
                    # Check if contains DIFFERENT section -> extra penalty
                    for other_sec in section_keywords:
                        if other_sec != requested_section:
                            if re.search(rf'^\s*{other_sec}\s*[:.]', chunk_lower, re.MULTILINE | re.IGNORECASE):
                                score -= 200.0  # Extra penalty
                                break
            
            # ===== TABLE DETECTION - HIGH PRIORITY =====
            if is_table_query:
                # Pattern 1: Box drawing characters
                table_chars = ['│', '|', '─', '├', '┤', '┬', '┴', '┼', '┌', '┐', '└', '┘', '║', '╔', '╗', '╚', '╝', '═']
                if any(ch in chunk for ch in table_chars):
                    score += 300.0  # Strong boost for table markers
                    print(f"[*] Chunk {chunk_idx}: TABLE MARKER found", flush=True)
                
                # Pattern 2: Column alignment (multiple spaces between words)
                lines = chunk.split('\n')
                aligned_lines = sum(1 for line in lines if re.search(r'\w+\s{2,}\w+\s{2,}', line))
                if aligned_lines >= 2:
                    score += 200.0  # Columnar table
                    print(f"[*] Chunk {chunk_idx}: COLUMNAR table ({aligned_lines} aligned lines)", flush=True)
                
                # Pattern 3: Common table headers
                table_headers = ['no\.|no\.|nomor', 'nama\s', 'kategori', 'kelompok', 'jumlah', 'peringkat', 'kolom', 'baris']
                header_matches = sum(1 for hdr in table_headers if re.search(hdr, chunk_lower))
                score += header_matches * 80.0  # Per header match
                
                # Pattern 4: Structured data (lots of numbers, punctuation)
                num_count = len(re.findall(r'\d', chunk))
                punct_count = chunk.count('|') + chunk.count('-')
                if num_count > 5 and punct_count > 5:
                    score += 150.0
            
            # ===== POINT MATCHING =====
            point_patterns = [
                r'point\s+(?:ke-)?\s*([a-z0-9]+)',
                r'item\s+(?:ke-)?\s*([a-z0-9]+)',
                r'poin\s+(?:ke-)?\s*([a-z0-9]+)',
                r'bagian\s+([a-z0-9]+)'
            ]
            
            for pattern in point_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    target = match.group(1)
                    is_digit = target.isdigit()
                    
                    # Look for "2." or "2 )" in chunk (digit points)
                    if is_digit:
                        if re.search(rf'^\s*{re.escape(target)}[\.\)]\s', chunk_lower, re.MULTILINE):
                            score += 250.0
                    else:
                        # Look for "a." or "a )" in chunk (letter points)
                        if re.search(rf'^\s*{re.escape(target)}[\.\)]\s', chunk_lower, re.MULTILINE):
                            score += 250.0
                    break
            
            # ===== TERM FREQUENCY - BASE SCORING =====
            query_words = [w for w in query_lower.split() if len(w) > 3 and w not in section_keywords + table_keywords]
            for word in query_words:
                count = chunk_lower.count(word)
                if count > 0:
                    score += count * 5.0  # Higher multiplier
            
            scores.append(score)
        
        # ========== SELECT TOP CHUNKS ==========
        scores_array = np.array(scores)
        
        if requested_section:
            # For section queries: ONLY return chunks from that specific section
            # section_chunk_indices already has the correct chunks - don't filter further!
            # Just get them in order
            section_indices_list = sorted(list(section_chunk_indices))
            best_chunks = [chunks[i] for i in section_indices_list]
            
            if not best_chunks:
                # Fallback if no section chunks found
                print(f"[!] No chunks found for section, taking top chunks", flush=True)
                top_indices = np.argsort(-scores_array)[:20]
                best_chunks = [chunks[i] for i in top_indices]
            
        elif is_table_query:
            # For table queries: return chunks with table indicators
            top_k = 999
            threshold = -100
            top_indices = np.argsort(-scores_array)[:top_k]
            best_chunks = [chunks[i] for i in top_indices if scores_array[i] >= threshold]
        else:
            # For general queries: normal ranking
            top_k = 50
            threshold = 0  # Need positive score
            top_indices = np.argsort(-scores_array)[:top_k]
            best_chunks = [chunks[i] for i in top_indices if scores_array[i] >= threshold]
        
        if not best_chunks:
            # Fallback: take top chunks anyway
            print(f"[!] No chunks above threshold, taking top chunks", flush=True)
            best_chunks = [chunks[i] for i in np.argsort(-scores_array)[:20]]
        
        # Print diagnostics - use top_indices if available, otherwise calculate
        if 'top_indices' not in locals():
            top_indices = np.argsort(-scores_array)[:15]
        top_scores = [scores_array[i] for i in top_indices[:15]]
        print(f"[✓] Selected {len(best_chunks)} chunks from {len(chunks)} total", flush=True)
        print(f"[*] Top scores: {[f'{s:.0f}' for s in top_scores[:10]]}", flush=True)
        
        t_total = time.time() - t0
        print(f"[✓] Search completed in {t_total:.3f}s", flush=True)
        
        return best_chunks
        
    except Exception as e:
        print(f"[!] Search error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return []
