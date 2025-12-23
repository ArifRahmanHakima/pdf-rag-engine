"""
Table Processing Module - Extract and format tables from text
Converts text tables to HTML tables for better display
"""

import re
from typing import List, Tuple, Dict, Optional
import json


class TableProcessor:
    """Extract and process tables from document text"""
    
    @staticmethod
    def detect_table_region(text: str) -> List[Tuple[int, int, str]]:
        """
        Detect table regions in text
        Returns list of (start_pos, end_pos, table_type)
        Only detect CLEAR tables with markers
        """
        tables = []
        lines = text.split('\n')
        
        in_table = False
        table_start = 0
        table_type = "unknown"
        consecutive_table_lines = 0
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                if in_table and consecutive_table_lines < 2:
                    # End table if we had too few lines
                    in_table = False
                    consecutive_table_lines = 0
                continue
            
            # Check for CLEAR table markers (box-drawing or pipe with multiple separators)
            has_box_markers = any(c in line for c in ['│', '├', '┤', '┼', '─', '┬', '┴'])
            
            # Pipe table: must have at least 3 pipes and no text outside pipes
            has_pipe_table = (
                '|' in line and 
                line.count('|') >= 3 and
                not line.startswith('//') and
                not line.startswith('#')
            )
            
            is_table_line = has_box_markers or has_pipe_table
            
            if is_table_line:
                if not in_table:
                    table_start = i
                    in_table = True
                    consecutive_table_lines = 1
                    # Detect table type
                    if has_box_markers:
                        table_type = "box"
                    else:
                        table_type = "pipe"
                else:
                    consecutive_table_lines += 1
            elif in_table:
                # Check if line looks like table data (numbered list or short text)
                is_table_data = (
                    (re.match(r'^\s*\d{1,3}\s*[\.\)]\s+', line_stripped) and len(line_stripped) < 100) or
                    (re.match(r'^\s*[a-z0-9]\s*[\.\)]\s+', line_stripped) and len(line_stripped) < 100) or
                    (len(line_stripped.split()) <= 10 and len(line_stripped) < 80)
                )
                
                if is_table_data and consecutive_table_lines >= 2:
                    consecutive_table_lines += 1
                else:
                    # End table
                    if consecutive_table_lines >= 2:
                        tables.append((table_start, i, table_type))
                    in_table = False
                    consecutive_table_lines = 0
        
        if in_table and consecutive_table_lines >= 2:
            tables.append((table_start, len(lines), table_type))
        
        return tables
    
    @staticmethod
    def parse_box_table(lines: List[str]) -> Optional[Dict]:
        """Parse box-style table (using │, ─, etc)"""
        try:
            # Find header separator
            header_sep_idx = None
            for i, line in enumerate(lines):
                if '├' in line or '┼' in line:
                    header_sep_idx = i
                    break
            
            if header_sep_idx is None or header_sep_idx == 0:
                return None
            
            # Extract headers
            header_line = lines[0]
            headers = [h.strip() for h in re.split(r'[│├┤]', header_line) if h.strip()]
            
            if not headers:
                return None
            
            # Extract rows
            rows = []
            for i in range(header_sep_idx + 1, len(lines)):
                line = lines[i]
                
                # Skip separator lines
                if any(c in line for c in ['├', '┤', '┼', '─']):
                    continue
                
                if '│' not in line:
                    break
                
                cells = [c.strip() for c in re.split(r'[│├┤]', line) if c.strip()]
                if len(cells) == len(headers):
                    rows.append(cells)
            
            if rows:
                return {
                    'headers': headers,
                    'rows': rows,
                    'type': 'box'
                }
        except Exception as e:
            print(f"[!] Box table parse error: {e}")
        
        return None
    
    @staticmethod
    def parse_pipe_table(lines: List[str]) -> Optional[Dict]:
        """Parse pipe-style table (using |) - IMPROVED"""
        try:
            if len(lines) < 2:
                return None
                
            # Find actual header line (must have | at start and end usually)
            header_line = None
            header_idx = 0
            
            for i, line in enumerate(lines):
                if '|' in line and line.count('|') >= 3:
                    header_line = line
                    header_idx = i
                    break
            
            if not header_line:
                return None
            
            # Extract headers - be strict about parsing
            headers_raw = header_line.split('|')
            headers = []
            for h in headers_raw:
                h_clean = h.strip()
                if h_clean and h_clean not in ['', '-', '---', ':', ':---', '---:']:
                    headers.append(h_clean)
            
            if not headers or len(headers) < 2:
                return None
            
            # Extract rows - skip separator lines
            rows = []
            for i in range(header_idx + 1, len(lines)):
                line = lines[i].strip()
                
                # Skip separator lines (all dashes and pipes)
                if not line or all(c in '-| :' for c in line.replace(' ', '')):
                    continue
                
                if '|' not in line:
                    break
                
                cells_raw = line.split('|')
                cells = []
                for c in cells_raw:
                    c_clean = c.strip()
                    if c_clean and c_clean not in ['-', '---', ':', ':---', '---:']:
                        cells.append(c_clean)
                
                # Only add if we have the same number of cells as headers
                if cells and len(cells) == len(headers):
                    rows.append(cells)
                elif cells and len(cells) > 0:
                    # Flexible: fill or truncate to match headers
                    while len(cells) < len(headers):
                        cells.append("")
                    cells = cells[:len(headers)]
                    rows.append(cells)
            
            if rows and len(rows) >= 1:
                return {
                    'headers': headers,
                    'rows': rows,
                    'type': 'pipe'
                }
        except Exception as e:
            print(f"[!] Pipe table parse error: {e}")
        
        return None
    
    @staticmethod
    def parse_text_table(lines: List[str]) -> Optional[Dict]:
        """Parse numbered list as table"""
        try:
            # Detect if first line is header
            rows = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Match numbered items: "1. item" or "1) item"
                match = re.match(r'^(?:NO\.|NO|NOMOR)\s*[:|]?\s*(.*?)$', line, re.IGNORECASE)
                if match:
                    # This is the header
                    continue
                
                match = re.match(r'^(\d+)\s*[\.\)]\s+(.*?)$', line)
                if match:
                    num, content = match.groups()
                    rows.append([num, content])
            
            if rows and len(rows) > 1:
                return {
                    'headers': ['NO.', 'Item'],
                    'rows': rows,
                    'type': 'numbered'
                }
        except Exception as e:
            print(f"[!] Text table parse error: {e}")
        
        return None
    
    @staticmethod
    def table_to_html(table_data: Dict) -> str:
        """Convert table dict to HTML table"""
        if not table_data:
            return ""
        
        html = '<table class="response-table">\n'
        
        # Headers
        html += '  <thead>\n    <tr>\n'
        for header in table_data['headers']:
            html += f'      <th>{header}</th>\n'
        html += '    </tr>\n  </thead>\n'
        
        # Rows
        html += '  <tbody>\n'
        for row in table_data['rows']:
            html += '    <tr>\n'
            for cell in row:
                html += f'      <td>{cell}</td>\n'
            html += '    </tr>\n'
        html += '  </tbody>\n'
        
        html += '</table>'
        return html
    
    @staticmethod
    def extract_and_convert_tables(text: str) -> str:
        """
        Extract tables from text and convert to HTML
        Returns text with HTML tables embedded
        """
        lines = text.split('\n')
        tables = TableProcessor.detect_table_region(text)
        
        if not tables:
            return text
        
        # Process tables from end to start (to preserve positions)
        result_lines = lines[:]
        
        for start, end, table_type in reversed(tables):
            table_lines = lines[start:end]
            
            # Try to parse table
            table_data = None
            
            if table_type == "box":
                table_data = TableProcessor.parse_box_table(table_lines)
            elif table_type == "pipe":
                table_data = TableProcessor.parse_pipe_table(table_lines)
            else:
                table_data = TableProcessor.parse_text_table(table_lines)
            
            if table_data:
                html_table = TableProcessor.table_to_html(table_data)
                # Replace lines with marker
                marker = f"\n<!-- TABLE START {table_type} -->\n{html_table}\n<!-- TABLE END -->\n"
                
                # Replace in result
                for i in range(start, end):
                    if i < len(result_lines):
                        result_lines[i] = ""
                
                result_lines[start] = marker
        
        return '\n'.join(result_lines)
    
    @staticmethod
    def format_table_json(table_data: Dict) -> str:
        """Format table as JSON for easier processing"""
        return json.dumps(table_data, ensure_ascii=False, indent=2)


# Test function
if __name__ == "__main__":
    test_text = """
    ┌──────┬─────────────┬────────┐
    │ NO.  │ NAMA        │ NILAI  │
    ├──────┼─────────────┼────────┤
    │ 1    │ Item Satu   │ 100    │
    │ 2    │ Item Dua    │ 200    │
    └──────┴─────────────┴────────┘
    """
    
    processor = TableProcessor()
    tables = processor.detect_table_region(test_text)
    print(f"Found {len(tables)} tables")
    
    for start, end, table_type in tables:
        lines = test_text.split('\n')[start:end]
        table_data = processor.parse_box_table(lines)
        if table_data:
            html = processor.table_to_html(table_data)
            print(html)
