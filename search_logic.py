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
                    
                    # CRITICAL: Filter chunks by DOC_ID marker
                    # Only include chunks that belong to the requested document
                    if doc_id_marker in content:
                        # Remove the marker for cleaner processing
                        content = content.replace(doc_id_marker, '').strip()
                        chunks.append(content)
        
        if not chunks:
            print(f"[!] No chunks found for doc={doc_id} (or all chunks have different DOC_ID)", flush=True)
            return []
        
        print(f"[*] Searching {len(chunks)} chunks from doc {doc_id}: '{query[:60]}'", flush=True)
        
        query_lower = query.lower()
        
        # ========== DETECT QUERY TYPE ==========
        section_keywords = ['menimbang', 'mengingat', 'menetapkan', 'mempertimbangkan', 'konsiderasi', 'dasar', 'pertimbangan']
        table_keywords = ['tabel', 'daftar', 'table', 'kategori', 'kelompok']  # Core table keywords only
        
        requested_section = None
        is_table_query = False
        table_keywords_in_query = []
        
        for sec in section_keywords:
            if sec in query_lower:
                requested_section = sec
                break
        
        if any(kw in query_lower for kw in table_keywords):
            is_table_query = True
            table_keywords_in_query = [kw for kw in table_keywords if kw in query_lower]
        
        if requested_section:
            print(f"[*] TYPE: SECTION QUERY ('{requested_section}')", flush=True)
        elif is_table_query:
            print(f"[*] TYPE: TABLE QUERY (keywords: {table_keywords_in_query})", flush=True)
        else:
            print(f"[*] TYPE: GENERAL QUERY", flush=True)
        
        # ========== SCORE CHUNKS ==========
        scores = []
        
        # For section queries: find ALL chunks that belong to that section
        section_chunk_indices = set()
        if requested_section:
            section_started = False
            section_end_idx = len(chunks)  # Default: goes to end
            
            for idx, chunk in enumerate(chunks):
                chunk_lower = chunk.lower()
                
                # Check if this chunk starts the requested section
                if re.search(rf'^\s*{requested_section}\s*[:.]', chunk_lower, re.MULTILINE | re.IGNORECASE):
                    section_started = True
                    section_chunk_indices.add(idx)
                    print(f"[*] Section '{requested_section}' STARTS at chunk {idx}", flush=True)
                # While section is active, check if a DIFFERENT section starts
                elif section_started:
                    # Check if a DIFFERENT section starts (means our section ended)
                    different_section_found = False
                    for other_sec in section_keywords:
                        if other_sec != requested_section:
                            if re.search(rf'^\s*{other_sec}\s*[:.]', chunk_lower, re.MULTILINE | re.IGNORECASE):
                                different_section_found = True
                                section_end_idx = idx  # Section ends here
                                section_started = False
                                print(f"[*] Section '{requested_section}' ENDS before chunk {idx} (found '{other_sec}')", flush=True)
                                break
                    
                    if not different_section_found:
                        # Still in same section - add this chunk
                        section_chunk_indices.add(idx)
                    else:
                        # Different section found, stop looking
                        break
            
            # If section never ended, collect all remaining chunks after section start
            if section_started:
                # We're still in the section, add all chunks from start to end
                start_idx = min(section_chunk_indices) if section_chunk_indices else 0
                for idx in range(start_idx, len(chunks)):
                    section_chunk_indices.add(idx)
            
            print(f"[*] Found {len(section_chunk_indices)} chunks in section '{requested_section}' (indices: {sorted(section_chunk_indices)})", flush=True)
        
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
                # GENERIC: Detect if chunk contains table structure markers
                table_chars = ['│', '|', '─', '├', '┤', '┬', '┴', '┼', '┌', '┐', '└', '┘', '║', '╔', '╗', '╚', '╝', '═']
                has_table_markers = any(ch in chunk for ch in table_chars)
                
                # Count number of pipe-delimited lines (universal for tables)
                lines = chunk.split('\n')
                pipe_lines = sum(1 for line in lines if line.count('|') >= 2)  # At least 2 pipes = table row
                has_many_pipes = pipe_lines >= 2
                
                # Count alignment patterns (spaces between tokens)
                aligned_lines = sum(1 for line in lines if re.search(r'\w+\s{2,}\w+\s{2,}', line))
                has_aligned_cols = aligned_lines >= 2
                
                # Check for structured data: lots of numbers and separators
                num_count = len(re.findall(r'\d+', chunk))
                punct_count = chunk.count('|') + chunk.count('-') + chunk.count('+')
                has_structure = (num_count > 3 and punct_count > 5)
                
                # Score generically: if it HAS any table structure, it's likely table content
                if has_table_markers or has_many_pipes:
                    score += 350.0  # Strong signal for table
                elif has_aligned_cols or has_structure:
                    score += 200.0  # Medium signal
                
                # CRITICAL: Penalize chunks that are BETWEEN table chunks
                # If prev and next chunks have tables but this doesn't, boost this chunk too
                # (it's likely table data that got split across chunks)
                if chunk_idx > 0 and chunk_idx < len(chunks) - 1:
                    prev_chunk_lower = chunks[chunk_idx - 1].lower()
                    next_chunk_lower = chunks[chunk_idx + 1].lower()
                    
                    prev_has_table = any(ch in chunks[chunk_idx - 1] for ch in table_chars)
                    next_has_table = any(ch in chunks[chunk_idx + 1] for ch in table_chars)
                    
                    # If sandwiched between tables, boost this chunk too (it's part of the table!)
                    if prev_has_table and next_has_table:
                        score += 200.0  # Boost chunks between table chunks
                        print(f"[*] Chunk {chunk_idx}: SANDWICHED BETWEEN TABLES - boosting", flush=True)
                
                # CRITICAL: Penalize chunks that are BETWEEN table chunks
                # If prev and next chunks have tables but this doesn't, boost this chunk too
                # (it's likely table data that got split across chunks)
                if chunk_idx > 0 and chunk_idx < len(chunks) - 1:
                    prev_chunk_lower = chunks[chunk_idx - 1].lower()
                    next_chunk_lower = chunks[chunk_idx + 1].lower()
                    
                    prev_has_table = any(ch in chunks[chunk_idx - 1] for ch in table_chars)
                    next_has_table = any(ch in chunks[chunk_idx + 1] for ch in table_chars)
                    
                    # If sandwiched between tables, boost this chunk too (it's part of the table!)
                    if prev_has_table and next_has_table:
                        score += 200.0  # Boost chunks between table chunks
                        print(f"[*] Chunk {chunk_idx}: SANDWICHED BETWEEN TABLES - boosting", flush=True)
                
                # Pattern 2: Common table headers (flexible untuk berbagai format tabel)
                table_headers = ['no\\.', 'no\\s', 'nomor', 'nama', 'kategori', 'kelompok', 'jumlah', 'peringkat', 'kolom', 'baris', 'asal', 'wilayah', 'sekolah']
                header_matches = sum(1 for hdr in table_headers if re.search(hdr, chunk_lower))
                score += header_matches * 80.0  # Per header match
                
                # Pattern 4: Structured data (lots of numbers, punctuation)
                num_count = len(re.findall(r'\d', chunk))
                punct_count = chunk.count('|') + chunk.count('-')
                if num_count > 5 and punct_count > 5:
                    score += 150.0
                
                # Pattern 5: Match query keywords in table content
                for table_kw in table_keywords_in_query:
                    if table_kw in chunk_lower:
                        score += 100.0  # Boost chunks mentioning specific table keywords
            
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
            
            # For general queries: look for first meaningful chunk (usually title/intro)
            # Chunks at the start are usually more relevant for "jelaskan isi dokumen"
            is_early_chunk = chunk_idx < 3  # First 3 chunks
            if is_early_chunk:
                score += 100.0  # Boost for early chunks (likely intro)
            
            # Length heuristic: very short chunks usually not content
            chunk_len = len(chunk)
            if chunk_len < 200:
                score -= 50.0  # Penalty for very short chunks
            elif chunk_len > 3000:
                score += 20.0  # Prefer longer chunks (more content)
            
            for word in query_words:
                count = chunk_lower.count(word)
                if count > 0:
                    score += count * 10.0  # Increased multiplier
            
            # If chunk starts with title-like patterns, boost it
            if re.match(r'^[A-Z][A-Z\s\d\-]+$', chunk[:50]):  # ALL CAPS title
                score += 150.0
            
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
            # For table queries: get table chunks but PRESERVE CONTINUITY
            # Don't randomly jump between chunks - keep consecutive chunks together
            top_k = 20
            threshold = 0.0  # More lenient
            
            top_indices = np.argsort(-scores_array)[:top_k]
            candidate_indices = [i for i in top_indices if scores_array[i] >= threshold]
            
            # Sort indices to preserve order (tables should be consecutive)
            candidate_indices = sorted(candidate_indices)
            
            # Group consecutive indices together (table should be in 1-3 consecutive chunks)
            if candidate_indices:
                # Find the longest consecutive sequence
                best_sequence = [candidate_indices[0]]
                current_sequence = [candidate_indices[0]]
                
                for idx in candidate_indices[1:]:
                    if idx - current_sequence[-1] <= 2:  # Allow max 2-chunk gap
                        current_sequence.append(idx)
                    else:
                        # Reset sequence if gap too large
                        if len(current_sequence) > len(best_sequence):
                            best_sequence = current_sequence
                        current_sequence = [idx]
                
                # Use best sequence found
                if len(current_sequence) > len(best_sequence):
                    best_sequence = current_sequence
                
                best_chunks = [chunks[i] for i in best_sequence]
            else:
                best_chunks = []
            
            # Fallback: if no chunks found, take any top chunks
            if not best_chunks:
                top_indices = np.argsort(-scores_array)[:10]
                best_chunks = [chunks[i] for i in top_indices]
        else:
            # For general queries: take top relevant chunks only
            # For large documents: be more selective
            if len(chunks) > 20:
                # Large document: take only top 10-15 most relevant
                top_k = 15
                threshold = 50.0  # Strict threshold to avoid garbage chunks
            else:
                # Smaller document: more lenient
                top_k = 30
                threshold = 0.0
            
            top_indices = np.argsort(-scores_array)[:top_k]
            best_chunks = [chunks[i] for i in top_indices if scores_array[i] >= threshold]
            
            # If too few chunks found, relax threshold but keep top_k limit
            if len(best_chunks) < 5 and top_k > 10:
                best_chunks = [chunks[i] for i in top_indices[:min(10, len(chunks))]]
        
        # ===== SPECIAL HANDLING FOR SECTION QUERIES =====
        if requested_section and section_chunk_indices:
            # For section queries: return ALL chunks from the section (in order)
            section_indices_sorted = sorted(section_chunk_indices)
            best_chunks = [chunks[i] for i in section_indices_sorted]
            print(f"[✓] SECTION QUERY: Returning ALL {len(best_chunks)} chunks from section '{requested_section}'", flush=True)
        
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
