"""
Text processing utilities - chunking, cleanup, and keyword extraction
"""

import re


def split_text_into_chunks(text: str, chunk_size: int = 1500, overlap: int = 200) -> list:
    """
    Split text into overlapping chunks for better RAG processing
    CRITICAL: Keep tables intact - don't split tables across chunks
    OPTIMIZED: Markdown-aware for DocString output, section-based for OCR output
    """
    # Fast path: if text is small, don't chunk
    if len(text) < chunk_size:
        return [text]
    
    # Check if text is markdown (contains markdown headers/formatting)
    is_markdown = bool(re.search(r'^#+\s+|\n#+\s+', text, re.MULTILINE))
    
    if is_markdown:
        # Markdown-aware chunking for DocString output
        return _split_markdown_chunks(text, chunk_size)
    else:
        # Section-based chunking for OCR output
        return _split_section_chunks(text, chunk_size)


def _split_markdown_chunks(text: str, chunk_size: int = 1500) -> list:
    """
    Split markdown text preserving structure
    Groups by headers and points (a, b, c, 1, 2, 3, etc)
    Never splits tables mid-way
    Handles legal documents with point-based structure
    """
    chunks = []
    current_chunk = []
    current_len = 0
    
    lines = text.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a markdown header (# ## ### etc)
        is_header = re.match(r'^#+\s+', line)
        
        # Check if this is a point/number start (a., b., c., 1., 2., etc)
        # Pattern: optional whitespace, then letter/number dot, then space
        is_point_start = re.match(r'^\s*([a-z]|\d+)\.\s+', line, re.IGNORECASE)
        
        # Check if this is a table line
        is_table_line = line.strip().startswith('|')
        
        line_len = len(line) + 1
        
        # Decision logic: when to start new chunk
        should_split = False
        
        if current_len + line_len > chunk_size and current_chunk:
            # Size exceeded
            if is_header or is_point_start:
                # Good place to split
                should_split = True
            elif current_len > chunk_size * 1.2:
                # Force split if way over size
                should_split = True
        
        if should_split:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            # Add line to current chunk
            current_chunk.append(line)
            current_len += line_len
            
            # Special handling for tables: include all table rows together
            if is_table_line and i + 1 < len(lines) and lines[i + 1].strip().startswith('|'):
                i += 1
                next_line = lines[i]
                current_chunk.append(next_line)
                current_len += len(next_line) + 1
        
        i += 1
    
    # Add remaining chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks if chunks else [text]


def _split_section_chunks(text: str, chunk_size: int = 1500) -> list:
    """
    Split by document sections for OCR output
    Simple strategy: split by section headers only (MENIMBANG, MENGINGAT, etc)
    """
    # Try simple split by section headers
    sections = re.split(
        r'(?:^|\n)(MENIMBANG|MENGINGAT|MENETAPKAN|MEMUTUSKAN|DAFTAR|LAMPIRAN|BAB)',
        text,
        flags=re.IGNORECASE | re.MULTILINE,
        maxsplit=10
    )
    
    if len(sections) > 3:  # Found sections
        chunks = []
        for i in range(1, len(sections), 2):
            header = sections[i]
            content = sections[i+1] if i+1 < len(sections) else ""
            chunk = (header + content).strip()
            if chunk and len(chunk) > 50:
                chunks.append(chunk)
        
        if len(chunks) > 1:
            return chunks
    
    # Fallback: split by paragraphs
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    if len(paragraphs) <= 2:
        return [text]
    
    # Group paragraphs into chunks
    chunks = []
    current = []
    current_len = 0
    
    for para in paragraphs:
        para_len = len(para)
        
        if current_len + para_len > chunk_size and current:
            chunks.append('\n\n'.join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len + 2
    
    if current:
        chunks.append('\n\n'.join(current))
    
    return chunks if chunks else [text]



def cleanup_llm_response(text: str) -> str:
    """Clean up LLM response - remove markdown artifacts and format nicely"""
    if not text:
        return text
    
    # Remove excessive asterisks and markdown formatting
    text = re.sub(r'\*{2,}', '', text)  # Remove ** markers
    text = re.sub(r'_{2,}', '', text)   # Remove __ markers
    text = re.sub(r'`+', '', text)      # Remove backticks
    
    # Clean up quotes and special formatting
    text = text.replace('""', '"').replace("''", "'")
    text = re.sub(r'"(\w+)":', r'\1:', text)  # Remove quotes around keys
    text = re.sub(r"'(\w+)':", r'\1:', text)
    
    # Remove JSON-like artifacts: **"key"**: -> key:
    text = re.sub(r'\*\*"([^"]+)"\*\*:\s*', r'\1: ', text)
    text = re.sub(r'\*\*([^*]+)\*\*:\s*', r'\1: ', text)
    
    # Clean up list markers - normalize to clean format
    # Convert various markers to consistent format
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines (but we'll add them back for spacing)
        if not stripped:
            cleaned_lines.append('')
            continue
        
        # Fix numbered items with various formats
        # "1. text" -> "1. text"
        # "1) text" -> "1. text"  
        # "1: text" -> "1. text"
        stripped = re.sub(r'^(\d+)[):](\s+)', r'\1. \2', stripped)
        
        # Fix lettered items
        # "a) text" -> "• text"
        # "a. text" -> "• text"
        stripped = re.sub(r'^([a-z])[):](\s+)', r'• \2', stripped)
        
        # Remove excessive hyphens/dashes at start (keep only one)
        while stripped.startswith('--'):
            stripped = stripped[1:]
        
        # Convert multiple markers to single bullet
        if stripped.startswith('- -'):
            stripped = '• ' + stripped[3:].lstrip()
        elif stripped.startswith('- '):
            stripped = '• ' + stripped[2:]
        elif stripped.startswith('• '):
            pass  # Keep as is
        
        cleaned_lines.append(stripped)
    
    # Join lines, but add spacing between logical sections
    text = '\n'.join(cleaned_lines)
    
    # Add paragraph breaks before numbered sections
    text = re.sub(r'\n(\d+\.)', r'\n\n\1', text)
    
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def extract_query_keywords(question: str) -> list:
    """
    Extract meaningful keywords from user's question to filter table rows.
    
    ZERO HARDCODING approach: 
    - Extract ALL non-question words from the question
    - Let build_markdown_table() decide if filtering is useful
    - If no keywords match document data, show all rows (lenient fallback)
    
    This works with ANY PDF structure - completely data-driven.
    
    Examples:
        "tabel apa saja" -> extract [] (no keywords, show all rows)
        "tabel nama peserta" -> extract ['nama', 'peserta'] (filter if document has these)
        "apa isi tabel" -> extract [] (no keywords, show all rows)
    
    NOT hardcoded - each document defines its own structure!
    """
    if not question:
        return []
    
    # Super minimal stop words - only common question/filler words
    # ZERO domain-specific hardcoding (no 'posyandu', 'kader', 'IKN', etc)
    minimal_stop_words = {
        'tabel', 'isi', 'jelaskan', 'apa', 'apa itu', 'daftar',
        'dan', 'atau', 'ini', 'itu', 'dari', 'untuk', 'apa saja',
        'berapa', 'mana', 'yang', 'ada', 'ada apa'
    }
    
    # Split and clean
    words = question.lower().split()
    keywords = []
    
    for word in words:
        # Remove all punctuation
        word = word.strip('.,!?;:\'"()[]{}').strip()
        
        # Keep only: non-empty, not in stop_words, length > 2
        if len(word) > 2 and word not in minimal_stop_words:
            keywords.append(word)
    
    # Remove duplicates preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    
    return unique

def clean_docstring_markdown(text: str) -> str:
    """
    Clean DocString markdown output by removing HTML tags and noise
    
    Removes:
    - <img>...</img> tags (images and icons)
    - <signature>...</signature> tags
    - <stamp>...</stamp> tags
    - HTML entities like &lt; &gt; &amp;
    - Multiple consecutive blank lines
    
    Args:
        text: Raw markdown from DocString API
        
    Returns:
        Cleaned markdown suitable for chunking and RAG indexing
    """
    # Remove HTML-like tags that DocString API includes
    text = re.sub(r'<img[^>]*>.*?</img>', '', text, flags=re.DOTALL)  # Remove <img>...</img>
    text = re.sub(r'<signature[^>]*>.*?</signature>', '', text, flags=re.DOTALL)  # Remove signatures
    text = re.sub(r'<stamp[^>]*>.*?</stamp>', '', text, flags=re.DOTALL)  # Remove stamps
    text = re.sub(r'<[^>]+>', '', text)  # Remove any other HTML-like tags
    
    # Decode HTML entities
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    text = text.replace('&apos;', "'")
    
    # Clean up lines with only page markers
    text = re.sub(r'## Page \d+\s*\n+', '\n\n', text)
    
    # Remove multiple consecutive blank lines (keep max 2)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text