# Dedicated search logic - COMPLETE section retrieval
import re
import numpy as np
from pathlib import Path
import json
import os
import time


def _extract_point_content(chunk: str, point: str) -> str:
    """
    Extract ONLY the requested point from a chunk that contains multiple points.
    
    GENERIC for both letter points (a, b, c) and number points (1, 2, 3, etc)
    Supports both OCR format and DocString markdown format
    
    For point query "c", extract from "c. ..." to "d. ..." (or end of chunk)
    For point query "5", extract from "5. ..." to "6. ..." (or end of chunk)
    
    Also handles markdown headers:
    - ### c. Content
    - ## a) Content
    
    Args:
        chunk: Full chunk text containing multiple points
        point: Requested point (single char like 'a', 'b', 'c' or digit string like '1', '2', '5')
    
    Returns:
        Extracted content for that point only
    """
    lines = chunk.split('\n')
    result_lines = []
    capturing = False
    found_start = False
    
    # Pattern to match point start: "a.", "b)", "1.", "5)", "(a)", "(5)", etc
    # GENERIC: works for both letters and numbers (including multi-digit)
    point_escaped = re.escape(point)
    point_patterns = [
        rf'^\s*{point_escaped}[\.\)\:]',      # "a." or "a)" or "a:" or "5." or "5)" at line start
        rf'^\s*\({point_escaped}\)',           # "(a)" or "(5)" format
        rf'^#+\s+{point_escaped}[\.\)\:]',    # "## a." or "### 5)" markdown format
    ]
    
    # Pattern for ANY point marker (to detect next point)
    # Match: single letter (a-z) or 1-2 digit numbers (1-99), followed by . ) or :
    # Also include markdown headers
    next_point_pattern = r'^\s*([a-z]|\d{1,2})[\.\)\:]'  # Generic point marker
    next_point_markdown_pattern = r'^#+\s+([a-z]|\d{1,2})[\.\)\:]'  # Markdown format
    
    # For number points, also prepare next number
    if point.isdigit():
        # point is numeric, so next point is next number
        try:
            next_num = str(int(point) + 1)
            # More specific pattern for numeric: look for exact next number
            next_num_pattern = rf'^\s*{re.escape(next_num)}[\.\)\:]'
            next_num_markdown_pattern = rf'^#+\s+{re.escape(next_num)}[\.\)\:]'
        except:
            next_num_pattern = None
            next_num_markdown_pattern = None
    else:
        # Letter points - use generic detection
        next_num_pattern = None
        next_num_markdown_pattern = None
    
    for i, line in enumerate(lines):
        # Check if this line starts the requested point
        matches_point = any(re.match(pattern, line, re.IGNORECASE) for pattern in point_patterns)
        
        if matches_point:
            if not found_start:
                # First time finding this point
                found_start = True
                capturing = True
                print(f"[*] Extract: Found point '{point}' at line {i}: {line[:70]}...", flush=True)
            result_lines.append(line)
            continue
        
        # If we're capturing, check for next point (different point)
        if capturing:
            # For numeric points: check if this line is the next number
            if next_num_pattern and re.match(next_num_pattern, line, re.IGNORECASE):
                print(f"[*] Extract: Found next point (numeric) at line {i}, stopping", flush=True)
                break
            if next_num_markdown_pattern and re.match(next_num_markdown_pattern, line, re.IGNORECASE):
                print(f"[*] Extract: Found next point (markdown numeric) at line {i}, stopping", flush=True)
                break
            
            # For letter or generic: check if any different point marker exists
            match = re.match(next_point_pattern, line, re.IGNORECASE)
            match_markdown = re.match(next_point_markdown_pattern, line, re.IGNORECASE)
            
            if match or match_markdown:
                found_point = (match or match_markdown).group(1).lower()
                if found_point != point.lower():
                    # Different point found - stop capturing here
                    print(f"[*] Extract: Found different point '{found_point}' at line {i}, stopping", flush=True)
                    break
            
            result_lines.append(line)
    
    if result_lines:
        extracted = '\n'.join(result_lines).strip()
        if len(extracted) > 30:  # Only return if meaningful
            print(f"[*] Extract: Successfully extracted {len(extracted)} chars for point '{point}'", flush=True)
            return extracted
    
    # Fallback: return empty string if extraction failed (strict mode)
    print(f"[!] Extract: Failed to extract point '{point}', returning empty string", flush=True)
    return ""


def _contains_point_marker(text: str, point: str) -> bool:
    """
    Check if text contains the requested point marker
    Supports both OCR and DocString markdown formats
    """
    point_escaped = re.escape(point)
    patterns = [
        rf'^\s*{point_escaped}[\.\)\:]',      # OCR: "a." or "a)" or "a:"
        rf'^\s*\({point_escaped}\)',          # OCR: "(a)"
        rf'^#+\s+{point_escaped}[\.\)\:]',    # Markdown: "## a." or "### 1)"
    ]
    return any(re.search(pattern, text, re.MULTILINE | re.IGNORECASE) for pattern in patterns)



async def search_chunks_strict(query: str, session_id: str, doc_id: str, SESSIONS_DIR, WORKING_DIR, embedding_func=None):
    """
    AGGRESSIVE SEARCH - Designed to retrieve relevant chunks from selected document
    Priority: Section > Table > Term frequency
    """
    import asyncio
    
    t0 = time.time()
    print(f"\n[SEARCH] Query: '{query[:60]}' | Session: {session_id} | Doc: {doc_id}", flush=True)
    
    try:
        # Load chunks from selected document only
        session_dir = Path(SESSIONS_DIR) / session_id
        doc_chunks_path = session_dir / "documents" / doc_id / "chunks.json"
        
        print(f"[SEARCH] Looking for chunks at: {doc_chunks_path}", flush=True)
        
        if not doc_chunks_path.exists():
            print(f"[!] Chunks not found for doc={doc_id} (path: {doc_chunks_path})", flush=True)
            return []
        
        with open(doc_chunks_path, encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            chunks = []
            doc_id_marker = f"[DOC_ID:{doc_id}]"
            
            print(f"[SEARCH] Total chunks in file: {len(data)}, looking for marker: {doc_id_marker}", flush=True)
            
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
        requested_point = None  # NEW: Track requested point (a, b, c, 1, 2, 3, etc)
        
        # ========== NEW: DETECT REQUESTED POINT ==========
        # Pattern: "poin b", "point 6", "butir a", "ayat 2", "bagian b", "point ke 5", etc
        point_patterns = [
            r'(?:poin|point|butir|ayat|pasal)\s+(?:ke\s+)?(?:bagian\s+)?([a-z]|\d+)',  # "point b", "point ke 5", "poin bagian b"
            r'(?:poin|point|butir|ayat|pasal)\s*[:\.]\s*([a-z]|\d+)',  # "point: b", "poin. a"
            r'bagian\s+(?:poin|point)\s+(?:ke\s+)?([a-z]|\d+)',  # "bagian point b", "bagian point ke 5"
            r'(?:ke\s+)?(\d+)\s+(?:bagian|dalam)',  # "ke 5 bagian" or "5 dalam"
        ]
        for pattern in point_patterns:
            match = re.search(pattern, query_lower)
            if match:
                requested_point = match.group(1).strip().lower()  # Normalize to lowercase
                print(f"[SEARCH] Detected requested point: '{requested_point}'", flush=True)
                break
        
        # Check for section keywords with fuzzy matching (handle suffixes like -kan, -i, -an)
        for sec in section_keywords:
            # Try exact match first
            if sec in query_lower:
                requested_section = sec
                print(f"[SEARCH] Detected section: '{sec}' (exact match)", flush=True)
                break
            # Try with -kan suffix
            elif sec + 'kan' in query_lower:
                requested_section = sec
                print(f"[SEARCH] Detected section: '{sec}' (suffix -kan match)", flush=True)
                break
            # Try with -an suffix
            elif sec + 'an' in query_lower:
                requested_section = sec
                print(f"[SEARCH] Detected section: '{sec}' (suffix -an match)", flush=True)
                break
            # Try with -i suffix
            elif sec + 'i' in query_lower:
                requested_section = sec
                print(f"[SEARCH] Detected section: '{sec}' (suffix -i match)", flush=True)
                break
        
        if any(kw in query_lower for kw in table_keywords):
            is_table_query = True
            table_keywords_in_query = [kw for kw in table_keywords if kw in query_lower]
        
        if requested_point:
            print(f"[*] TYPE: POINT-SPECIFIC QUERY (point: '{requested_point}')", flush=True)
        elif requested_section:
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
                # Support both formats:
                # 1. OCR format: "Menimbang:" or "Menimbang ." at line start
                # 2. DocString markdown format: "## Menimbang" or "### Menimbang" at line start
                section_text_patterns = [
                    rf'^\s*{requested_section}\s*[:.]',  # "Menimbang:" or "Menimbang."
                    rf'^#+\s+{requested_section}',       # "## Menimbang" or "### Menimbang"
                ]
                
                section_match = any(
                    re.search(pattern, chunk_lower, re.MULTILINE | re.IGNORECASE)
                    for pattern in section_text_patterns
                )
                
                if section_match:
                    section_started = True
                    section_chunk_indices.add(idx)
                    print(f"[*] Section '{requested_section}' STARTS at chunk {idx}", flush=True)
                # While section is active, check if a DIFFERENT section starts
                elif section_started:
                    # Check if a DIFFERENT section starts (means our section ended)
                    different_section_found = False
                    for other_sec in section_keywords:
                        if other_sec != requested_section:
                            # Support both OCR and DocString markdown formats
                            other_patterns = [
                                rf'^\s*{other_sec}\s*[:.]',  # "Mengingat:" format
                                rf'^#+\s+{other_sec}',       # "## Mengingat" format
                            ]
                            if any(re.search(p, chunk_lower, re.MULTILINE | re.IGNORECASE) for p in other_patterns):
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
            
            # ===== POINT-SPECIFIC MATCHING - HIGHEST PRIORITY =====
            if requested_point:
                # Check if this chunk contains the requested point (a, b, c, 1, 2, 3, etc)
                # Support both OCR and DocString markdown formats
                
                # Multiple patterns to try (each more lenient)
                # GENERIC: match both letter and number points with . ) or : separator
                # Also support markdown headers like "## a." or "### 1)"
                patterns_exact = [
                    rf'^\s*{re.escape(requested_point)}[\.\)\:]',  # "a." or "a)" or "a:" at line start (OCR)
                    rf'^\s*\({re.escape(requested_point)}\)',      # "(a)" format (OCR)
                    rf'^#+\s+{re.escape(requested_point)}[\.\)\:]',  # "## a." or "### 1)" markdown format
                ]
                
                # Try exact matches first
                has_requested_point = any(
                    bool(re.search(pattern, chunk_lower, re.MULTILINE))
                    for pattern in patterns_exact
                )
                
                # Also check what points are in this chunk (for debug)
                # GENERIC: match single letter (a-z) or one/two digit numbers (1-99)
                # Both OCR and markdown formats
                found_points = re.findall(r'^\s*([a-z]|\d{1,2})[\.\)\:]', chunk_lower, re.MULTILINE)
                found_points += re.findall(r'^#+\s+([a-z]|\d{1,2})[\.\)\:]', chunk_lower, re.MULTILINE)
                found_points = list(set(found_points))  # Remove duplicates
                
                if has_requested_point:
                    score += 800.0  # VERY high score
                    print(f"[*] Chunk {chunk_idx}: EXACT point '{requested_point}' FOUND - score +800", flush=True)
                elif requested_point in found_points:
                    # Point is in chunk but pattern didn't match - unlikely but handle it
                    score += 800.0
                    print(f"[*] Chunk {chunk_idx}: Found '{requested_point}' in list {set(found_points)} - score +800 (pattern fallback)", flush=True)
                elif found_points:
                    # Has some points, but not the one we want
                    score -= 600.0  # Penalty for wrong points
                    print(f"[*] Chunk {chunk_idx}: Has points {set(found_points)}, NOT '{requested_point}' - score -600", flush=True)
                else:
                    # No points in this chunk at all
                    print(f"[*] Chunk {chunk_idx}: NO points found (looking for '{requested_point}') - score stays 0", flush=True)
            
            # ===== SECTION MATCHING - HIGH PRIORITY =====
            elif requested_section:
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
            
            # ===== TABLE DETECTION - HIGHEST PRIORITY (if is_table_query) =====
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
                
                # STRONG BOOST for table chunks (HIGHEST PRIORITY when searching for tables)
                if has_table_markers or has_many_pipes:
                    score += 1000.0  # VERY STRONG signal - pipes are definitive table marker
                    print(f"[*] Chunk {chunk_idx}: STRONG TABLE MARKER (pipes/box chars) - score += 1000", flush=True)
                elif has_aligned_cols or has_structure:
                    score += 500.0  # MEDIUM-HIGH signal
                    print(f"[*] Chunk {chunk_idx}: MEDIUM TABLE SIGNAL (aligned cols/structure) - score += 500", flush=True)
                
                # Boost chunks sandwiched between table chunks (definitely part of table!)
                if chunk_idx > 0 and chunk_idx < len(chunks) - 1:
                    prev_has_table = any(ch in chunks[chunk_idx - 1] for ch in table_chars)
                    next_has_table = any(ch in chunks[chunk_idx + 1] for ch in table_chars)
                    
                    if prev_has_table and next_has_table:
                        score += 400.0  # HIGH boost - this IS table data
                        print(f"[*] Chunk {chunk_idx}: SANDWICHED BETWEEN TABLES - score += 400", flush=True)
                
                # Common table headers - flexible regex patterns
                table_headers = [r'no[\s\.]', r'nomor', r'nama', r'kategori', r'kelompok', r'jumlah', r'peringkat', r'kolom', r'baris', r'asal', r'wilayah', r'sekolah']
                header_matches = sum(1 for hdr in table_headers if re.search(hdr, chunk_lower))
                score += header_matches * 150.0  # BOOSTED - header is strong indicator
                
                # Structured data with multiple rows (lots of numbers and columns)
                if num_count > 5 and punct_count > 5:
                    score += 300.0  # STRONG boost
                
                # Match query keywords in table content (user asking about specific table)
                for table_kw in table_keywords_in_query:
                    if table_kw in chunk_lower:
                        score += 200.0  # BOOSTED - table keyword match is strong
            
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
        
        # ===== SPECIAL HANDLING FOR POINT-SPECIFIC QUERIES =====
        # HIGHEST PRIORITY: Point query takes absolute precedence
        # BUT: If point + section both requested, first filter by section, then extract point
        if requested_point:
            print(f"[*] POINT QUERY active - filtering ONLY for point '{requested_point}'", flush=True)
            
            # Check if we also have section constraint
            if requested_section and section_chunk_indices:
                print(f"[*] ALSO filtering by section '{requested_section}' (point + section combined)", flush=True)
                # Filter to chunks in the requested section, that also have the point
                point_chunk_indices = [
                    i for i in section_chunk_indices 
                    if i < len(scores_array) and scores_array[i] >= 800.0
                ]
                
                if not point_chunk_indices:
                    # Point NOT found in the specified section
                    print(f"[!] POINT+SECTION QUERY: Point '{requested_point}' NOT in section '{requested_section}'", flush=True)
                    # Set to None to indicate mismatch - will return empty later
                    best_chunks = []
                    point_chunk_indices = []
                else:
                    # Sort by score descending
                    point_chunks_with_scores = [(i, scores_array[i]) for i in point_chunk_indices]
                    point_chunks_with_scores.sort(key=lambda x: -x[1])
                    best_chunks = [chunks[i] for i, _ in point_chunks_with_scores[:3]]  # Max 3 chunks
                    print(f"[✓] POINT+SECTION QUERY: Found {len(best_chunks)} chunks with point '{requested_point}' in section '{requested_section}'", flush=True)
                    print(f"[*] Point chunk scores: {[f'{scores_array[i]:.0f}' for i in point_chunk_indices[:5]]}", flush=True)
            else:
                # Point-only query: find all chunks with this point
                point_chunk_indices = [i for i, score in enumerate(scores_array) if score >= 800.0]
                
                if point_chunk_indices:
                    # Sort by score descending
                    point_chunks_with_scores = [(i, scores_array[i]) for i in point_chunk_indices]
                    point_chunks_with_scores.sort(key=lambda x: -x[1])
                    best_chunks = [chunks[i] for i, _ in point_chunks_with_scores[:1]]  # Take only best match
                    print(f"[✓] POINT QUERY: Found {len(best_chunks)} chunks with exact point match (score >= 800)", flush=True)
                    print(f"[*] Point chunk scores: {[f'{scores_array[i]:.0f}' for i in point_chunk_indices[:5]]}", flush=True)
                else:
                    # No exact match found - search in all chunks for the point
                    print(f"[!] POINT QUERY: NO exact matches found (score >= 800)", flush=True)
                    print(f"[*] Top chunk scores: {sorted(scores_array, reverse=True)[:10]}", flush=True)
                    
                    # Find chunks that contain the point pattern (even if low score)
                    point_chunks_fallback = []
                    for i, chunk in enumerate(chunks):
                        if _contains_point_marker(chunk, requested_point):
                            point_chunks_fallback.append(i)
                    
                    if point_chunks_fallback:
                        # Use fallback chunks (chunk containing the point)
                        best_chunks = [chunks[point_chunks_fallback[0]]]
                        print(f"[*] POINT QUERY: Found point '{requested_point}' in fallback search (chunk {point_chunks_fallback[0]})", flush=True)
                    else:
                        # Point not found anywhere
                        print(f"[!] POINT QUERY: Point '{requested_point}' NOT found in any chunk", flush=True)
                        best_chunks = []
        
        # ===== SPECIAL HANDLING FOR SECTION QUERIES =====
        elif requested_section and section_chunk_indices:
            # For section queries: return ALL chunks from the section (in order)
            print(f"[*] SECTION QUERY active - returning all chunks from section '{requested_section}'", flush=True)
            section_indices_sorted = sorted(section_chunk_indices)
            best_chunks = [chunks[i] for i in section_indices_sorted]
            print(f"[✓] SECTION QUERY: Returning ALL {len(best_chunks)} chunks from section '{requested_section}'", flush=True)
        
        if not best_chunks:
            # Fallback: take top chunks anyway
            print(f"[!] No chunks above threshold, taking top chunks", flush=True)
            best_chunks = [chunks[i] for i in np.argsort(-scores_array)[:20]]
        
        # ===== EXTRACT ONLY REQUESTED POINT FROM CHUNKS =====
        # If point query, extract ONLY that point from each chunk
        if requested_point and best_chunks:
            print(f"[*] POINT QUERY: Extracting ONLY point '{requested_point}' from {len(best_chunks)} chunks", flush=True)
            extracted_chunks = []
            for i, chunk in enumerate(best_chunks):
                extracted = _extract_point_content(chunk, requested_point)
                extracted_chunks.append(extracted)
                print(f"[*]   Chunk {i}: {len(chunk)} chars → {len(extracted)} chars", flush=True)
            
            # CRITICAL: For point queries, keep ONLY the extracted point, discard rest
            # Filter out chunks that are too short or don't clearly contain the point
            valid_extracted = []
            for ex in extracted_chunks:
                if len(ex) > 40 and _contains_point_marker(ex, requested_point):
                    valid_extracted.append(ex)
            
            if valid_extracted:
                best_chunks = [valid_extracted[0]]  # Take ONLY the first (best) extracted point
                print(f"[✓] Point extraction successful: returning 1 chunk with point '{requested_point}' ({len(best_chunks[0])} chars)", flush=True)
            else:
                # If extraction failed completely, return empty (don't fallback to full chunks)
                best_chunks = []
                print(f"[!] Point extraction returned no valid results for point '{requested_point}'", flush=True)
        
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
