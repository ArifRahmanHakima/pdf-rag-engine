"""
Query processing logic - handles different types of queries and LLM interactions
"""

import asyncio
import time


async def process_query(
    question: str,
    context: str,
    is_summary_query: bool,
    is_table_query: bool,
    is_section_query: bool,
    question_lower: str,
    cleanup_func,
    format_section_func,
    format_table_func,
    llm_func,
    table_processor=None
):
    """
    Process different types of queries and generate appropriate responses
    
    Returns formatted answer based on query type
    """
    
    # Try table formatting first if it's a table question
    table_answer = format_table_func(context, question, table_processor)
    if table_answer:
        return table_answer
    
    # Detect if this is a point-specific query (e.g., "apa isi point c bagian menimbang?")
    import re
    point_patterns = [
        r'(?:poin|point|butir|ayat|pasal)\s+(?:ke\s+)?(?:bagian\s+)?([a-z]|\d+)',
        r'(?:poin|point|butir|ayat|pasal)\s*[:\.]\s*([a-z]|\d+)',
        r'bagian\s+(?:poin|point)\s+(?:ke\s+)?([a-z]|\d+)',
        r'(?:ke\s+)?(\d+)\s+(?:bagian|dalam)',
    ]
    is_point_query = any(re.search(pattern, question_lower) for pattern in point_patterns)
    
    # For section queries: use special formatting (not LLM, just text formatting)
    if is_section_query:
        section_name = next((kw.capitalize() for kw in ['menimbang', 'mengingat', 'menetapkan', 'memutuskan'] if kw in question_lower), "")
        return format_section_func(context, section_name)
    
    # For point queries: also use formatting (not LLM) since we extracted just that point
    if is_point_query:
        section_name = next((kw.capitalize() for kw in ['menimbang', 'mengingat', 'menetapkan', 'memutuskan'] if kw in question_lower), "")
        return format_section_func(context, section_name if section_name else "")
    
    # For short context: return directly (but still clean)
    if len(context) < 600:
        return cleanup_func(context)
    
    # Check for greeting-only questions
    if question.lower().strip() in ['hai', 'halo', 'hi', 'hello', 'assalamu\'alaikum', 'pagi', 'siang', 'sore', 'malam']:
        return "Halo! Ada yang bisa saya bantu tentang dokumen ini?"
    
    # Generate LLM response
    system_prompt, answer_prompt = _build_prompts(question, context, is_summary_query, is_table_query, question_lower)
    
    t_llm_start = time.time()
    answer = await asyncio.wait_for(
        llm_func(answer_prompt, sys_prompt=system_prompt),
        timeout=60.0
    )
    t_llm = time.time() - t_llm_start
    print(f"[OK] LLM: {t_llm:.2f}s")
    print(f"[DEBUG] LLM Raw Response ({len(answer)} chars): {answer[:200] if answer else '(EMPTY)'}", flush=True)
    
    # Clean up response formatting
    cleaned = cleanup_func(answer)
    print(f"[DEBUG] After Cleanup ({len(cleaned)} chars): {cleaned[:200] if cleaned else '(EMPTY)'}", flush=True)
    return cleaned


def _build_prompts(question: str, context: str, is_summary_query: bool, is_table_query: bool, question_lower: str):
    """Build system and user prompts based on query type"""
    
    if is_summary_query:
        system_prompt = """Kamu adalah assistant yang membuat RINGKASAN DOKUMEN yang singkat dan padat.

ATURAN RINGKASAN:
- Buat SUMMARY SINGKAT: max 5-7 poin utama SAJA
- Jelaskan tujuan/maksud utama dokumen dalam 1-2 kalimat
- Highlight bagian kunci: Menimbang, Mengingat, Memutuskan (jika ada)
- Gunakan bullet points (•) untuk clarity
- Format: • Poin 1\n• Poin 2\n• dll
- JANGAN copy-paste seluruh isi dokumen
- Target: 200-300 kata maksimal
- TIDAK BOLEH ada markdown atau simbol aneh"""

        answer_prompt = f"""Pertanyaan: {question}

Konteks dari dokumen:
{context}

RINGKASAN SINGKAT (max 5-7 poin, 200-300 kata):"""
    
    elif is_table_query:
        system_prompt = """Kamu adalah assistant yang menampilkan DATA TABEL dari dokumen dengan format yang RAPI DAN MUDAH DIBACA.

ATURAN TABEL:
- Format output HANYA dengan MARKDOWN TABLE (| header | header |)
- JANGAN gunakan bullet points atau penjelasan panjang
- Setiap baris tabel: | data1 | data2 | data3 |
- Gunakan PERSIS data dari dokumen, JANGAN mengarang
- Jika ada kolom: tampilkan SEMUA kolom yang ada
- Header adalah baris pertama, diikuti separator: |---|---|---|
- Data rows: setiap baris menjadi row di table
- HANYA output TABLE, tidak perlu intro atau kesimpulan"""

        answer_prompt = f"""Pertanyaan: {question}

DATA TABEL dari dokumen:
{context}

INSTRUKSI: Format sebagai MARKDOWN TABLE dengan pipe (|). Output HANYA table, tidak perlu penjelasan. Header | separator | rows."""
    
    else:
        # Regular question
        system_prompt = """Kamu adalah assistant yang FOKUS menjawab pertanyaan user dari dokumen.

ATURAN PEMFORMATAN - SANGAT PENTING:
- Gunakan line break yang cukup untuk readability
- Untuk list: gunakan format "• item" atau "1. item" dengan line break setelah setiap item
- Pisahkan poin-poin utama dengan line break kosong
- Jangan gunakan markdown seperti ** atau __
- Jangan pernah output JSON atau struktur data kompleks
- Gunakan spacing untuk visual hierarchy yang jelas

ATURAN KONTEN:
1. Jawab TEPAT apa yang ditanya, JANGAN tambah informasi
2. Jika ditanya tabel: LIST item dengan format "Nama | Kategori | Nilai" atau "• item"
3. Jika ditanya bagian spesifik (Menimbang/Mengingat): LIST SEMUA POIN dengan nomor atau bullet
4. Jika ditanya point spesifik (point 2, point a): HANYA jawab itu saja
5. Jawab dari dokumen SAJA, jangan tambah pengetahuan umum
6. JANGAN tambah kesimpulan atau summary tidak diminta"""

        answer_prompt = f"""Pertanyaan: {question}

Konteks dari dokumen:
{context}

Jawaban (format dengan jelas, gunakan line break untuk setiap poin):"""
    
    return system_prompt, answer_prompt
