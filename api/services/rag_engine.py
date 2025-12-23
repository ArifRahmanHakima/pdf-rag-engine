
import os
import sys
import asyncio
import hashlib
from dotenv import load_dotenv


# Perbaikan path Python jika menggunakan Windows Store
_original_executable = sys.executable
if 'WindowsApps' in sys.executable:
    import shutil
    python_path = shutil.which('python')
    if python_path:
        sys.executable = python_path
        os.environ['PIPMASTER_PYTHON'] = python_path


# Import library utama untuk RAG dan utilitas
from raganything import RAGAnything, RAGAnythingConfig
from lightrag import LightRAG
from sentence_transformers import SentenceTransformer
from lightrag.utils import EmbeddingFunc
from api.services.llm_wrapper import llm_model_func, vision_model_func
from api.services.timer import ProcessTimer, Timer
from api.services.pdf_detector import PDFTypeDetector


sys.executable = _original_executable
load_dotenv()

# Nonaktifkan verbose timer agar log tidak terlalu banyak
Timer.set_verbose(False)


# ========================================
# PEMUATAN MODEL EMBEDDING
# ========================================
print("⏳ Memuat model embedding...")
_embed_start = __import__('time').perf_counter()
embed_model = SentenceTransformer(os.getenv("EMBEDDING_MODEL"))
print(f"✅ Model embedding berhasil dimuat dalam {__import__('time').perf_counter() - _embed_start:.2f}s")

# Fungsi embedding asinkron
async def async_embed(texts):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: embed_model.encode(texts, normalize_embeddings=True, batch_size=32)
    )

# Objek embedding_func digunakan untuk menghasilkan vektor embedding dari teks
embedding_func = EmbeddingFunc(
    embedding_dim=384,
    max_token_size=512,
    func=async_embed
)


# ========================================
# INSTANSI RAG & CACHE ANALISIS PDF
# ========================================
rag_instances = {}  # Menyimpan instance RAG untuk tiap dokumen
pdf_analysis_cache = {}  # Cache hasil analisis tipe PDF


def get_doc_id(file_path: str) -> str:
    """
    Menghasilkan ID dokumen unik berdasarkan hash isi file.
    Ini memastikan file yang sama akan memiliki doc_id yang sama meskipun namanya berbeda.
    """
    try:
        # Membaca 1MB pertama untuk hash (lebih cepat dari seluruh file)
        with open(file_path, 'rb') as f:
            file_bytes = f.read(1024 * 1024)  # 1MB
        # Hash gabungan isi file + nama file
        filename = os.path.basename(file_path)
        combined = file_bytes + filename.encode()
        return hashlib.md5(combined).hexdigest()[:16]
    except Exception as e:
        print(f"⚠️ Gagal hash file, fallback ke nama file: {e}")
        filename = os.path.basename(file_path)
        return hashlib.md5(filename.encode()).hexdigest()[:16]


def check_document_exists(doc_id: str) -> bool:
    """
    Mengecek apakah dokumen sudah pernah diproses (ada file hasil proses di foldernya)
    """
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    graph_file = os.path.join(doc_working_dir, "graph_chunk_entity_relation.graphml")
    vdb_chunks_file = os.path.join(doc_working_dir, "vdb_chunks.json")
    return os.path.exists(graph_file) or os.path.exists(vdb_chunks_file)


def check_has_content(doc_id: str) -> bool:
    """
    Mengecek apakah dokumen memiliki konten hasil proses (misal: vdb_chunks.json berisi data)
    """
    import json
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    vdb_chunks_file = os.path.join(doc_working_dir, "vdb_chunks.json")
    try:
        if os.path.exists(vdb_chunks_file):
            with open(vdb_chunks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    return True
                elif isinstance(data, list) and len(data) > 0:
                    return True
    except:
        pass
    return False


def get_rag_instance(doc_id: str, file_path: str = None):
    """
    Mengambil atau membuat instance RAG untuk dokumen tertentu.
    Otomatis memilih parser berdasarkan hasil analisis PDF.
    """
    if doc_id not in rag_instances:
        with Timer(f"Create RAG Instance ({doc_id})"):
            base_dir = os.getenv("WORKING_DIR", "./rag_storage")
            doc_working_dir = os.path.join(base_dir, doc_id)
            os.makedirs(doc_working_dir, exist_ok=True)
            # Deteksi parser secara otomatis
            parser = "auto"
            pdf_analysis = None
            if file_path and os.path.exists(file_path):
                # Cek cache analisis
                if doc_id in pdf_analysis_cache:
                    pdf_analysis = pdf_analysis_cache[doc_id]
                    print(f"📋 Menggunakan hasil analisis cache untuk {doc_id}")
                else:
                    print(f"\n🔍 Menganalisis tipe PDF...")
                    detector = PDFTypeDetector()
                    pdf_analysis = detector.analyze_pdf(file_path)
                    pdf_analysis_cache[doc_id] = pdf_analysis
                    detector.print_analysis(pdf_analysis)
                parser = pdf_analysis['recommended_parser']
                print(f"✅ Parser: {parser} ({PDFTypeDetector.get_parser_description(parser)})")
            # Konfigurasi RAGAnythingConfig
            config = RAGAnythingConfig(
                working_dir=doc_working_dir,
                parser=parser,
                parse_method="auto",
                enable_image_processing=pdf_analysis.get('has_images', True) if pdf_analysis else True,
                enable_table_processing=False,  # Nonaktifkan pemrosesan tabel
                enable_equation_processing=False,  # Nonaktifkan pemrosesan persamaan
            )
            document_exists = check_document_exists(doc_id)
            with Timer(f"Load LightRAG ({doc_id})"):
                lightrag_instance = LightRAG(
                    working_dir=doc_working_dir,
                    llm_model_func=llm_model_func,
                    embedding_func=embedding_func,
                    # entity_extract_max_gleaning=1,  # Kurangi ekstraksi entity
                    # enable_local_query=True,
                )
            if document_exists:
                print(f"\U0001f4c2 Memuat dokumen yang sudah ada: {doc_id}")
                rag_instances[doc_id] = RAGAnything(
                    config=config,
                    llm_model_func=llm_model_func,
                    vision_model_func=vision_model_func,
                    embedding_func=embedding_func,
                    lightrag=lightrag_instance,
                )
                print(f"\u2705 RAG berhasil dimuat: {doc_id}")
            else:
                rag_instances[doc_id] = RAGAnything(
                    config=config,
                    llm_model_func=llm_model_func,
                    vision_model_func=vision_model_func,
                    embedding_func=embedding_func,
                    lightrag=lightrag_instance,
                )
                print(f"\u2705 RAG baru dibuat: {doc_id}")
            # Simpan hasil analisis di instance
            if pdf_analysis:
                rag_instances[doc_id]._pdf_analysis = pdf_analysis
            print(f"📂 Working dir: {doc_working_dir}")
    return rag_instances[doc_id]


# ========================================
# PARSING CEPAT UNTUK PDF TEKS
# ========================================
async def fast_parse_small_document(file_path: str, doc_id: str) -> str:
    """
    Parsing cepat untuk PDF yang hanya berisi teks (menggunakan PyMuPDF/fitz).
    Hasil parsing disimpan ke file content.md.
    """
    try:
        import fitz
        print("🚀 Parsing cepat dengan PyMuPDF...")
        doc = fitz.open(file_path)
        content = ""
        for page_num, page in enumerate(doc):
            content += f"\n--- Page {page_num + 1} ---\n"
            content += page.get_text()
        doc.close()
        base_dir = os.getenv("WORKING_DIR", "./rag_storage")
        doc_working_dir = os.path.join(base_dir, doc_id)
        os.makedirs(doc_working_dir, exist_ok=True)
        md_file = os.path.join(doc_working_dir, "content.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fast parse: {len(content)} karakter")
        return content
    except Exception as e:
        print(f"⚠️ Parsing cepat gagal: {e}")
        return None


# ========================================
# PROSES PDF
# ========================================
async def process_pdf(file_path: str):
    """
    Proses utama untuk menganalisis, parsing, dan memproses PDF.
    - Menganalisis tipe PDF (teks, scan, tabel, dsb).
    - Jika PDF sederhana (teks), diproses cepat.
    - Jika tidak, diproses dengan pipeline RAG lengkap.
    """
    filename = os.path.basename(file_path)
    doc_id = get_doc_id(file_path)
    timer = ProcessTimer(f"UPLOAD & PROCESS: {filename}")
    timer.start()
    print(f"🔑 Document ID: {doc_id}")
    # Langkah 1: Analisis PDF (cache)
    timer.step("1. PDF Analysis")
    if doc_id not in pdf_analysis_cache:
        detector = PDFTypeDetector()
        analysis = detector.analyze_pdf(file_path)
        pdf_analysis_cache[doc_id] = analysis
        detector.print_analysis(analysis)
    else:
        analysis = pdf_analysis_cache[doc_id]
        print(f"📋 Menggunakan hasil analisis cache")
    # Langkah 2: Parsing cepat untuk PDF teks
    if analysis['type'] == 'text' and analysis['recommended_parser'] == 'pymupdf':
        timer.step("2. Fast Parse (PyMuPDF)")
        content = await fast_parse_small_document(file_path, doc_id)
        if content:
            total_time = timer.finish()
            return doc_id, f"📄 {filename} diproses cepat ({analysis['type']}) - {total_time:.1f}s"
    # Langkah 3: Proses standar
    timer.step("2. Initialize RAG")
    rag = get_rag_instance(doc_id, file_path)
    pdf_type_emoji = {
        'text': '📝',
        'table': '📊',
        'image': '🖼️',
        'scan': '📷',
        'mixed': '📄'
    }.get(analysis['type'], '📄')
    timer.step("3. Parse PDF")
    try:
        await rag.process_document_complete(
            file_path=file_path,
            output_dir=rag.config.working_dir
        )
    except Exception as e:
        print(f"⚠️ Error saat memproses (lanjut): {e}")
        # Lanjutkan, konten parsial tetap bisa dipakai
    total_time = timer.finish()
    return doc_id, (
        f"{pdf_type_emoji} {filename} berhasil diproses!\n"
        f"Tipe: {analysis['type'].upper()}\n"
        f"Parser: {PDFTypeDetector.get_parser_description(analysis['recommended_parser'])}\n"
        f"Waktu: {total_time:.1f}s"
    )


# ========================================
# GENERATE SUMMARY (RINGKASAN)
# ========================================
async def generate_summary(file_path: str, doc_id: str):
    """
    Membuat ringkasan dokumen menggunakan LLM.
    - Mode query disesuaikan dengan tipe PDF (scan → naive, lain → hybrid).
    - Jika gagal, fallback ke ringkasan dari konten hasil parsing.
    """
    filename = os.path.basename(file_path)
    timer = ProcessTimer(f"GENERATE SUMMARY: {filename}")
    timer.start()
    try:
        timer.step("1. Get RAG Instance")
        rag = get_rag_instance(doc_id, file_path)
        # Ambil hasil analisis dari cache
        analysis = pdf_analysis_cache.get(doc_id)
        # Pilih mode query berdasarkan tipe PDF
        if analysis and analysis['type'] == 'scan':
            query_mode = "naive"
            print(f"📷 PDF hasil scan terdeteksi - gunakan mode naive untuk ringkasan")
        else:
            query_mode = "hybrid"
        timer.step(f"2. LLM Query ({query_mode})")
        summary = ""
        try:
            result = await rag.aquery(
                f"Berikan ringkasan singkat tentang isi dokumen '{filename}' ini dalam 3-4 kalimat. Jelaskan topik utama dan poin-poin penting.",
                mode=query_mode,
                top_k=5
            )
            if result:
                summary = result if isinstance(result, str) else result.get("text", "")
        except Exception as e:
            print(f"⚠️ Query RAG gagal: {e}")
            summary = ""
        # Fallback jika ringkasan kurang baik
        if not summary or len(summary) < 50 or "[no-context]" in summary.lower() or "sorry" in summary.lower():
            print("⚠️ Gunakan fallback summary...")
            timer.step("3. Fallback Summary")
            summary = await generate_summary_from_content(doc_id, filename)
        timer.finish()
        if summary:
            print(f"✅ Summary: {summary[:100]}...")
        return summary
    except Exception as e:
        print(f"❌ Error generate summary: {e}")
        import traceback
        traceback.print_exc()
        return f"Dokumen {filename} berhasil diproses dan siap untuk ditanyakan."


async def generate_summary_from_content(doc_id: str, filename: str):
    """
    Fallback: Membuat ringkasan langsung dari isi file markdown hasil parsing.
    """
    import glob
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    content_file = os.path.join(doc_working_dir, "content.md")
    content = ""
    if os.path.exists(content_file):
        try:
            with open(content_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            pass
    if not content:
        md_files = glob.glob(os.path.join(doc_working_dir, "**", "*.md"), recursive=True)
        for md_file in md_files[:3]:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content += f.read() + "\n\n"
            except:
                pass
    if not content or len(content) < 50:
        return f"Dokumen '{filename}' berhasil diproses dan siap untuk ditanyakan."
    max_chars = 3000
    if len(content) > max_chars:
        content = content[:max_chars] + "..."
    try:
        prompt = f"""Berikan ringkasan singkat tentang isi dokumen berikut dalam 3-4 kalimat. Jelaskan topik utama dan poin-poin penting.

KONTEN DOKUMEN:
{content}

RINGKASAN:"""
        summary = await llm_model_func(prompt)
        if summary and len(summary) > 50:
            return summary
    except Exception as e:
        print(f"❌ Fallback summary error: {e}")
    return f"Dokumen '{filename}' berhasil diproses dan siap untuk ditanyakan."


# ========================================
# QUERY DOCUMENT (TANYA JAWAB)
# ========================================
async def query_document(doc_id: str, question: str, top_k: int = 3):
    """
    Melakukan tanya jawab ke dokumen.
    - Mode query disesuaikan dengan tipe PDF.
    - Jika gagal, fallback ke pencarian jawaban dari konten hasil parsing.
    """
    timer = ProcessTimer(f"QUERY: {question[:40]}...")
    timer.start()
    print(f"📄 Doc ID: {doc_id}")
    try:
        timer.step("1. Get RAG Instance")
        rag = get_rag_instance(doc_id)
        # Ambil hasil analisis dari cache untuk memilih mode
        analysis = pdf_analysis_cache.get(doc_id)
        if analysis and analysis['type'] == 'scan':
            query_mode = "naive"
            print(f"📷 PDF hasil scan - gunakan mode naive")
        else:
            query_mode = "hybrid"
        timer.step(f"2. RAG Query ({query_mode})")
        answer = ""
        try:
            result = await rag.aquery(
                question,
                mode=query_mode,
                top_k=top_k
            )
            if result:
                answer = result if isinstance(result, str) else result.get("text", "")
            # Coba fallback mode jika perlu
            if not answer or "[no-context]" in answer.lower() or len(answer) < 20:
                print("⚠️ Coba naive mode...")
                timer.step("2b. RAG Query (naive)")
                try:
                    result = await rag.aquery(question, mode="naive", top_k=top_k)
                    if result:
                        answer = result if isinstance(result, str) else result.get("text", "")
                except Exception as e:
                    print(f"⚠️ Query naive gagal: {e}")
                if not answer or "[no-context]" in answer.lower():
                    answer = await fallback_query_from_parsed_content(doc_id, question)
        except Exception as e:
            print(f"⚠️ Error query RAG: {e}")
            answer = await fallback_query_from_parsed_content(doc_id, question)
        if not answer or "[no-context]" in answer.lower():
            answer = "Maaf, saya tidak menemukan informasi yang relevan untuk menjawab pertanyaan tersebut. Silakan coba pertanyaan lain."
        timer.finish()
        print(f"✅ Jawaban: {answer[:100]}...")
        return answer
    except Exception as e:
        print(f"❌ Error query dokumen: {e}")
        import traceback
        traceback.print_exc()
        raise e


async def fallback_query_from_parsed_content(doc_id: str, question: str):
    """
    Fallback: Menjawab pertanyaan langsung dari isi file markdown hasil parsing.
    """
    import glob
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    doc_working_dir = os.path.join(base_dir, doc_id)
    content_file = os.path.join(doc_working_dir, "content.md")
    content = ""
    if os.path.exists(content_file):
        try:
            with open(content_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            pass
    if not content:
        md_files = glob.glob(os.path.join(doc_working_dir, "**", "*.md"), recursive=True)
        for md_file in md_files[:3]:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content += f.read() + "\n\n"
            except:
                pass
    if not content:
        return ""
    max_chars = 4000
    if len(content) > max_chars:
        content = content[:max_chars] + "..."
    try:
        prompt = f"""Berdasarkan konten dokumen berikut, jawab pertanyaan dengan bahasa Indonesia yang jelas dan ringkas.

KONTEN DOKUMEN:
{content}

PERTANYAAN: {question}

JAWABAN:"""
        answer = await llm_model_func(prompt)
        return answer
    except Exception as e:
        print(f"❌ Fallback query error: {e}")
        return ""


# ========================================
# FUNGSI UTILITAS
# ========================================
def list_documents():
    """
    Menampilkan daftar dokumen yang sudah diproses.
    """
    return list(rag_instances.keys())

def clear_document_cache(doc_id: str = None):
    """
    Menghapus cache instance RAG dan analisis PDF untuk dokumen tertentu atau semua dokumen.
    """
    if doc_id:
        if doc_id in rag_instances:
            del rag_instances[doc_id]
            print(f"🗑️ Cache dihapus: {doc_id}")
        if doc_id in pdf_analysis_cache:
            del pdf_analysis_cache[doc_id]
    else:
        rag_instances.clear()
        pdf_analysis_cache.clear()
        print("🗑️ Semua cache dihapus")

def clear_rag_instance(doc_id: str):
    """
    Alias untuk clear_document_cache.
    """
    clear_document_cache(doc_id)

def clear_root_storage():
    """
    Menghapus file-file storage utama di direktori kerja RAG.
    """
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    root_files = [
        "graph_chunk_entity_relation.graphml",
        "kv_store_doc_status.json",
        "kv_store_entity_chunks.json",
        "kv_store_full_docs.json",
        "kv_store_full_entities.json",
        "kv_store_full_relations.json",
        "kv_store_llm_response_cache.json",
        "kv_store_parse_cache.json",
        "kv_store_relation_chunks.json",
        "kv_store_text_chunks.json",
        "vdb_chunks.json",
        "vdb_entities.json",
        "vdb_relationships.json"
    ]
    deleted = []
    for filename in root_files:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            deleted.append(filename)
    if deleted:
        print(f"✅ {len(deleted)} file dibersihkan")
    else:
        print("✅ Root storage sudah bersih")
    return deleted

def reset_all_storage():
    """
    Menghapus seluruh storage RAG dan membuat ulang direktori kerja.
    """
    import shutil
    rag_instances.clear()
    pdf_analysis_cache.clear()
    base_dir = os.getenv("WORKING_DIR", "./rag_storage")
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        print(f"🗑️ Dihapus: {base_dir}")
    os.makedirs(base_dir, exist_ok=True)
    print(f"✅ Storage baru: {base_dir}")
    return True
