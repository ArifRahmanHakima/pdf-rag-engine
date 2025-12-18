# Search logic v3 - COMPLETE section retrieval using intelligent filtering
import re
import json
from pathlib import Path

async def search_chunks_strict(query: str, session_id: str, doc_id: str, SESSIONS_DIR, WORKING_DIR):
    """
    Search strategy:
    1. Load ALL chunks from document
    2. Detect query type (section, table, general)
    3. For section queries: retrieve ALL chunks from that section
    4. For table queries: retrieve ALL chunks with table markers
    5. For general: retrieve relevant chunks by keyword matching
    """
    
    try:
        # Load chunks
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
                    if doc_id_marker in content:
                        content = content.replace(f"{doc_id_marker}\n", "").strip()
                        if content:
                            chunks.append(content)
        
        if not chunks:
            print(f"[!] No chunks found", flush=True)
            return []
        
        print(f"[*] Searching {len(chunks)} chunks: '{query[:50]}'", flush=True)
        
        query_lower = query.lower()
        
        # ===== DETECT SECTION QUERY =====
        section_keywords = {
            'menimbang': ['menimbang'],
            'mengingat': ['mengingat'],
            'menetapkan': ['menetapkan'],
            'pertimbangan': ['pertimbangan', 'dasar', 'konsiderasi']
        }
        
        requested_section = None
        for sec_name, keywords in section_keywords.items():
            if any(kw in query_lower for kw in keywords):
                requested_section = sec_name
                break
        
        # ===== DETECT TABLE QUERY =====
        table_keywords = ['tabel', 'daftar', 'tabel', 'table', 'nama', 'siapa', 'kategori', 'list', 'data']
        is_table_query = any(kw in query_lower for kw in table_keywords)
        
        # ===== DETECT POINT QUERY =====
        point_match = re.search(r'point\s+([0-9]+|[a-z])|poin\s+([0-9]+|[a-z])', query_lower)
        requested_point = None
        if point_match:
            requested_point = point_match.group(1) or point_match.group(2)
        
        print(f"[*] Query type: section={requested_section}, table={is_table_query}, point={requested_point}", flush=True)
        
        # ===== RETRIEVE CHUNKS =====
        result_chunks = []
        
        if requested_section:
            # SECTION QUERY: Get ALL chunks from this section
            print(f"[*] Mode: Section retrieval for '{requested_section}'", flush=True)
            section_chunks = []
            in_section = False
            
            for chunk in chunks:
                chunk_start = chunk.lower().strip()[:200]
                
                # Start of section?
                if requested_section in chunk_start:
                    in_section = True
                    section_chunks.append(chunk)
                # End of section (another section started)?
                elif in_section and any(sec in chunk_start for sec in section_keywords.keys() if sec != requested_section):
                    in_section = False
                # Inside section?
                elif in_section:
                    section_chunks.append(chunk)
            
            if section_chunks:
                print(f"[✓] Found {len(section_chunks)} chunks for section '{requested_section}'", flush=True)
                result_chunks = section_chunks
            else:
                # Fallback: keyword matching
                result_chunks = [c for c in chunks if requested_section in c.lower()]
        
        elif is_table_query:
            # TABLE QUERY: Get ALL chunks with table markers OR data-like content
            print(f"[*] Mode: Table retrieval", flush=True)
            table_markers = ['│', '|', '─', '├', '┤', '┬', '┴', '┼', '┌', '┐', '└', '┘', '║', '╔', '╗', '╚', '╝', '═', 'TABEL', 'DAFTAR', 'NO.', 'Nama', 'Kategori']
            
            table_chunks = []
            for chunk in chunks:
                has_table_marker = any(marker in chunk for marker in table_markers)
                has_table_structure = chunk.count('|') >= 4 or chunk.count('─') >= 3
                
                if has_table_marker or has_table_structure:
                    table_chunks.append(chunk)
            
            if table_chunks:
                print(f"[✓] Found {len(table_chunks)} chunks with table markers", flush=True)
                result_chunks = table_chunks
            else:
                # Fallback: keyword matching
                result_chunks = [c for c in chunks if any(kw in c.lower() for kw in table_keywords)]
        
        else:
            # GENERAL QUERY: Keyword matching (take top relevant)
            print(f"[*] Mode: General retrieval", flush=True)
            query_terms = [w for w in query_lower.split() if len(w) > 3]
            
            scored_chunks = []
            for chunk in chunks:
                chunk_lower = chunk.lower()
                score = sum(chunk_lower.count(term) for term in query_terms)
                if score > 0:
                    scored_chunks.append((score, chunk))
            
            if scored_chunks:
                scored_chunks.sort(reverse=True, key=lambda x: x[0])
                result_chunks = [c for _, c in scored_chunks[:20]]
                print(f"[✓] Found {len(result_chunks)} relevant chunks", flush=True)
        
        if not result_chunks:
            print(f"[!] No chunks matched, using fallback", flush=True)
            # Ultimate fallback: return top chunks by query term frequency
            scored = []
            for i, chunk in enumerate(chunks):
                score = sum(chunk.lower().count(term) for term in query_lower.split() if len(term) > 2)
                scored.append((score, chunk))
            scored.sort(reverse=True, key=lambda x: x[0])
            result_chunks = [c for _, c in scored[:15]]
        
        print(f"[✓] Returning {len(result_chunks)} chunks", flush=True)
        return result_chunks
    
    except Exception as e:
        print(f"[!] Search error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return []
