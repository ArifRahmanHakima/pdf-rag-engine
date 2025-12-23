"""
Table formatting utilities - parsing and formatting tables for display
"""

from app.utils.text_processing import extract_query_keywords


def parse_and_format_pipe_table(context: str, question: str = "") -> str:
    """
    Extract and beautifully format tables from context
    Supports multiple separate tables
    
    Args:
        context: Text containing tables
        question: User's question (used to extract filter keywords dynamically)
    """
    lines = context.split('\n')
    
    # Find all table blocks (continuous lines with |)
    table_blocks = []
    current_block = []
    
    for line in lines:
        if '|' in line and line.strip():
            current_block.append(line)
        elif current_block:
            # End of current table block
            if len(current_block) >= 2:
                table_blocks.append(current_block)
            current_block = []
    
    # Don't forget last block
    if current_block and len(current_block) >= 2:
        table_blocks.append(current_block)
    
    if not table_blocks:
        return None
    
    # Format each table separately
    results = []
    for block in table_blocks:
        result = format_pipe_table_html(block, question=question)
        if result:
            results.append(result)
    
    if not results:
        return None
    
    # Return all tables separated by divider
    return '\n\n---\n\n'.join(results)


def format_pipe_table_html(pipe_lines, question: str = ""):
    """Format pipe-delimited lines into markdown table - single table only
    
    Args:
        pipe_lines: Lines containing pipe-delimited table
        question: User's question (used to extract filter keywords dynamically)
    """
    # Extract cells from pipe lines
    all_cells = []
    for line in pipe_lines:
        # Remove leading/trailing pipes and split
        line = line.strip('| ')
        cells = [cell.strip() for cell in line.split('|')]
        cells = [c for c in cells if c]  # Remove empty cells
        if cells:
            all_cells.append(cells)
    
    if len(all_cells) < 2:
        return None
    
    # First row = headers
    headers = all_cells[0]
    rows = all_cells[1:]
    
    if not headers or not rows:
        return None
    
    # Extract filter keywords from USER QUESTION dynamically (NOT hardcoded)
    # This way, different PDFs with different table types can be handled
    query_keywords = extract_query_keywords(question)
    
    return build_markdown_table(headers, rows, query_keywords=query_keywords)


def build_markdown_table(headers, rows, query_keywords=None):
    """Build markdown table from headers and rows, optionally filter by query"""
    if not headers or not rows:
        return None
    
    # Standardize columns
    num_cols = len(headers)
    headers = headers[:num_cols]
    rows = [[row[i] if i < len(row) else '' for i in range(num_cols)] for row in rows]
    
    # Smart filtering: ONLY filter if keywords exist AND match well
    # If no match found (0% hit rate), show all rows (don't be too restrictive)
    if query_keywords:
        filtered_rows = []
        for row in rows:
            # Check if any keyword matches in any cell of the row
            row_text = ' '.join([str(cell).lower() for cell in row])
            if any(kw.lower() in row_text for kw in query_keywords):
                filtered_rows.append(row)
        
        # IMPORTANT: Only apply filter if we got meaningful results
        # If match rate is very low (< 20%), don't filter at all - show everything
        # This prevents case where user asks "posyandu" but document only has "kader"
        if filtered_rows:  # Even 1 match is ok, don't enforce percentage threshold
            rows = filtered_rows
    
    # Calculate column widths
    col_widths = []
    for col_idx in range(num_cols):
        max_width = max(len(headers[col_idx]), 12)
        for row in rows:
            max_width = max(max_width, len(str(row[col_idx])[:30]))
        col_widths.append(min(max_width, 30))
    
    # Build markdown table
    result = "📋 **TABEL**\n\n"
    
    # Header row
    header_row = "| " + " | ".join(h[:col_widths[i]].ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    result += header_row + "\n"
    
    # Separator
    sep_row = "|" + "|".join(["-" * (col_widths[i] + 2) for i in range(num_cols)]) + "|"
    result += sep_row + "\n"
    
    # Data rows
    for row in rows[:50]:
        row_str = "| " + " | ".join(str(row[i])[:col_widths[i]].ljust(col_widths[i]) for i in range(num_cols)) + " |"
        result += row_str + "\n"
    
    if len(rows) > 50:
        result += f"\n*(... dan {len(rows) - 50} baris lagi)*"
    
    return result


def format_section_response(context: str, section_name: str = "") -> str:
    """
    Format section-based response (Menimbang, Mengingat, Menetapkan) for better readability
    
    Args:
        context: Raw text from chunks
        section_name: Name of section (e.g., "Menimbang", "Mengingat") for header
    """
    import re
    
    if not context:
        return context
    
    # Remove OCR artifacts and fix spacing
    text = context.strip()
    
    # Fix common OCR spacing issues where words are concatenated
    # Pattern: lowercase followed by uppercase without space (e.g., "kalurahanbagian" -> "kalurahan bagian")
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # Fix multiple spaces (keep tables intact with 3+ spaces)
    # Only replace 2-space sequences, keep 3+
    text = re.sub(r'(?<!\s) {2}(?!\s)', ' ', text)
    
    # Add line breaks for better readability:
    # Break after "UU" followed by number (legislation references)
    text = re.sub(r'(UU\s+No\.\s+\d+[^\n]*?)(\s+(?:UU|PP|Peraturan))', r'\1\n\n\2', text)
    
    # Break after periods followed by capital letters (sentence breaks)
    text = re.sub(r'(\.\s+)([A-Z])', r'\1\n', text)
    
    # Break after numbered items
    text = re.sub(r'(\d+\.\s+[^\n]+?)(\s+\d+\.)', r'\1\n\2', text)
    
    # Add header if section name provided
    if section_name:
        text = f"**{section_name}:**\n\n{text}"
    
    # Clean up excessive whitespace
    text = re.sub(r'\n\n\n+', '\n\n', text)
    
    return text.strip()


def format_table_response(context: str, question: str, table_processor=None):
    """
    Try to format table response if context contains structured table data
    Returns formatted answer or None if no table found
    
    Args:
        context: Document context containing potential table
        question: User's question
        table_processor: Optional TableProcessor instance for advanced parsing
    """
    if not table_processor:
        # If no processor available, try pipe table parsing only
        pass
    
    # More comprehensive keyword detection
    table_keywords = ['tabel', 'daftar', 'table', 'kategori', 'kelompok', 'peringkat', 'isi tabel', 'jelaskan tabel']
    if not any(kw in question.lower() for kw in table_keywords):
        return None
    
    try:
        # Try new beautified pipe table parser first (faster, better output)
        # Pass question to enable dynamic keyword extraction for table filtering
        table_result = parse_and_format_pipe_table(context, question=question)
        if table_result:
            return table_result
        
        # Fallback: try TABLE_PROCESSOR detection (if available)
        if not table_processor:
            return None
        
        tables = table_processor.detect_table_region(context)
        
        if not tables:
            return None
        
        # If TABLE_PROCESSOR found tables, parse them
        start_pos, end_pos, table_type = tables[0]
        table_lines = context[start_pos:end_pos].split('\n')
        
        table_data = None
        
        # Try to parse based on type
        if table_type == "box":
            table_data = table_processor.parse_box_table(table_lines)
        elif table_type == "pipe":
            table_data = table_processor.parse_pipe_table(table_lines)
        else:
            table_data = table_processor.parse_text_table(table_lines)
        
        if table_data:
            # Format table for display - clean and readable
            headers = table_data.get('headers', [])
            rows = table_data.get('rows', [])
            
            if not headers or not rows:
                return None
            
            # Calculate column widths
            col_widths = []
            for col_idx in range(len(headers)):
                max_width = max(len(headers[col_idx]), 15)
                for row in rows:
                    if col_idx < len(row):
                        max_width = max(max_width, len(str(row[col_idx])[:40]))
                col_widths.append(min(max_width, 40))
            
            # Build markdown table
            result = f"📋 **TABEL** ({table_type}):\n\n"
            
            # Header row
            header_row = "| " + " | ".join(h[:col_widths[i]].ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
            result += header_row + "\n"
            
            # Separator row
            sep_row = "|" + "|".join(["-" * (col_widths[i] + 2) for i in range(len(headers))]) + "|"
            result += sep_row + "\n"
            
            # Data rows (limit to 100)
            for idx, row in enumerate(rows[:100], 1):
                row_str = "| " + " | ".join(str(row[i])[:col_widths[i]].ljust(col_widths[i]) if i < len(row) else "".ljust(col_widths[i]) for i in range(len(headers))) + " |"
                result += row_str + "\n"
            
            if len(rows) > 100:
                result += f"\n*(... dan {len(rows) - 100} baris lagi)*"
            
            return result
        
        return None
    
    except Exception as e:
        print(f"[!] Table formatting error: {e}")
        return None
