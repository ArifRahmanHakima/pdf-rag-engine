import sys, os, json, asyncio, re, time
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

# Early feedback to user - print ASAP
print("\n[*] Starting RAG system...", flush=True)

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()
os.environ["LIGHTRAG_MAX_ASYNC_WORKERS"] = "2"
os.environ["LIGHTRAG_TIMEOUT"] = "30"
os.environ["TQDM_DISABLE"] = "1"
os.environ["PYTHONWARNINGS"] = "ignore"

import logging
logging.getLogger("lightrag").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("easyocr").setLevel(logging.ERROR)

from raganything.config import RAGAnythingConfig
from embedding_qwen import load_embedding_model, get_embedding_func
from llm_openrouter import llm_model_func_openrouter
# Defer LightRAG import - only load when main() is called
# from lightrag import LightRAG, QueryParam
# Defer numpy - only load when needed for search
# import numpy as np
# Defer heavy libraries - only load when needed
# import easyocr  # Will be imported in _load_ocr_model()
# from pdf2image import convert_from_path  # Will be imported when needed

config = RAGAnythingConfig()
WORKING_DIR = config.working_dir

# Lazy loading - initialize only when needed
ocr_reader = None
embedding_model = None
embedding_func = None
_ocr_loaded = False
_embedding_loaded = False

_chunk_embeddings_cache = {}

def _load_ocr_model():
    """Lazy load OCR model - only when needed"""
    global ocr_reader, _ocr_loaded
    if _ocr_loaded:
        return ocr_reader
    
    print("[*] Loading OCR model...")
    try:
        import warnings
        import easyocr  # Defer import - only load when OCR is needed
        warnings.filterwarnings("ignore")
        ocr_reader = easyocr.Reader(['id', 'en'], gpu=False, verbose=False)
        print("[✓] OCR model loaded\n")
        _ocr_loaded = True
        return ocr_reader
    except Exception as e:
        print(f"[!] OCR initialization warning (will use fallback): {e}")
        ocr_reader = None
        _ocr_loaded = True
        print()
        return None

def _load_embedding_model():
    """Lazy load embedding model - only when needed"""
    global embedding_model, embedding_func, _embedding_loaded
    if _embedding_loaded:
        return embedding_model, embedding_func
    
    print("[*] Loading Qwen embedding model...")
    # Suppress the internal print from embedding_qwen.load_embedding_model()
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    embedding_model = load_embedding_model()
    sys.stdout = old_stdout
    
    embedding_func = get_embedding_func()
    print("[✓] Qwen embedding model loaded\n")
    _embedding_loaded = True
    return embedding_model, embedding_func

def _process_single_page(args: Tuple[int, object]) -> Tuple[int, str]:
    """Process a single page with OCR - designed for parallel execution"""
    page_num, image = args
    
    # Get OCR reader (may load on first call)
    reader = _load_ocr_model()
    if not reader:
        return (page_num, f"=== Page {page_num} ===\n[OCR not available]")
    
    try:
        # Convert PIL image to numpy array
        import numpy as np
        image_np = np.array(image)
        
        # Run OCR - readtext returns list of [bbox, text, confidence]
        results = reader.readtext(image_np)
        
        if results:
            # Extract text from results, maintaining line breaks
            page_text = "\n".join([text[1] for text in results])
            page_content = f"=== Page {page_num} ===\n{page_text}"
            return (page_num, page_content)
        else:
            return (page_num, f"=== Page {page_num} ===\n(empty)")
    except Exception as e:
        return (page_num, f"=== Page {page_num} ===\n[Error: {str(e)}]")

def extract_text_from_pdf_with_ocr(pdf_path, use_ocr=True):
    """Extract text from PDF using parallel easyocr processing"""
    from pdf2image import convert_from_path  # Defer import - only load when needed
    reader = _load_ocr_model()
    if not use_ocr or not reader:
        return ""
    
    try:
        t_start = time.time()
        print(f"    Converting PDF to images...", end='', flush=True)
        
        # Get OCR workers configuration
        ocr_workers = int(os.getenv('OCR_WORKERS', '4'))
        pdf_dpi = int(os.getenv('PDF_DPI', '150'))
        
        images = convert_from_path(pdf_path, dpi=pdf_dpi)
        t_convert = time.time() - t_start
        print(f" {len(images)} pages [{t_convert:.2f}s]")
        
        # Prepare page list with indices
        page_list = list(enumerate(images, 1))
        
        text_content = {}
        t_ocr_start = time.time()
        
        # Parallel OCR processing using ThreadPoolExecutor
        print(f"    Running parallel OCR with {ocr_workers} workers...")
        with ThreadPoolExecutor(max_workers=ocr_workers) as executor:
            # Submit all pages to executor
            futures = [executor.submit(_process_single_page, (page_num, image)) 
                      for page_num, image in page_list]
            
            # Collect results as they complete
            completed = 0
            for future in futures:
                try:
                    page_num, page_content = future.result()
                    text_content[page_num] = page_content
                    completed += 1
                except Exception as e:
                    print(f"\n    [!] Error processing page: {e}")
        
        t_ocr = time.time() - t_ocr_start
        
        # Calculate per-page timing
        per_page_avg = t_ocr / len(images) if images else 0
        
        # Sort by page number and join
        if text_content:
            sorted_pages = [text_content[page_num] for page_num in sorted(text_content.keys())]
            final_text = "\n\n".join(sorted_pages)
            print(f"    ✓ Extracted {len(text_content)} pages [{t_ocr:.2f}s, {per_page_avg:.2f}s/page]")
            return final_text
        else:
            print(f"    No text found in PDF")
            return ""
    
    except Exception as e:
        print(f"\n[!] OCR error: {e}")
        return ""

async def ingest_documents(rag):
    """Ingest PDF documents from rag_storage/docs using parallel easyocr"""
    docs_dir = Path(WORKING_DIR) / "docs"
    
    if not docs_dir.exists():
        print("[*] No documents directory found")
        return
    
    pdf_files = list(docs_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("[*] No PDF files found")
        return
    
    ocr_workers = int(os.getenv('OCR_WORKERS', '4'))
    print(f"[*] Found {len(pdf_files)} PDF file(s) for ingestion")
    print(f"[*] Using {ocr_workers} parallel OCR workers\n")
    
    total_start = time.time()
    
    for pdf_path in pdf_files:
        try:
            print(f"[*] Processing {pdf_path.name}")
            file_start = time.time()
            
            # Extract text with easyocr
            text = extract_text_from_pdf_with_ocr(str(pdf_path), use_ocr=True)
            
            if not text.strip():
                print(f"[!] No text extracted\n")
                continue
            
            # Insert into RAG
            print(f"    Inserting into RAG...", end='', flush=True)
            rag_start = time.time()
            await rag.ainsert(text)
            rag_time = time.time() - rag_start
            
            file_time = time.time() - file_start
            print(f" [{rag_time:.2f}s]")
            print(f"[✓] Ingested in {file_time:.2f}s total\n")
            
        except Exception as e:
            print(f"[!] Error: {str(e)[:80]}\n")
    
    total_time = time.time() - total_start
    print(f"[✓] Ingest complete [{total_time:.2f}s total]\n")

_chunk_embeddings_cache = {}

def get_chunk_embeddings():
    """Get pre-computed chunk embeddings using embedding_model"""
    global _chunk_embeddings_cache, embedding_model
    
    # Ensure embedding_model is loaded if not already
    if embedding_model is None:
        emb_model, _ = _load_embedding_model()
        embedding_model = emb_model
    
    if not _chunk_embeddings_cache:
        kv_path = f"{WORKING_DIR}/kv_store_text_chunks.json"
        if os.path.exists(kv_path):
            with open(kv_path) as f:
                data = json.load(f)
                chunks = []
                for item in data.values():
                    if isinstance(item, dict) and 'content' in item:
                        chunks.append(item['content'])
            
            # Use embedding_model (synchronous SentenceTransformer) for direct embedding
            if embedding_model:
                for i, chunk in enumerate(chunks):
                    chunk_text = chunk[:500] if len(chunk) > 500 else chunk
                    # embedding_model.encode() returns a numpy array
                    _chunk_embeddings_cache[i] = embedding_model.encode(chunk_text, convert_to_numpy=True, show_progress_bar=False)
    
    return _chunk_embeddings_cache


async def search_chunks(query):
    """Search chunks with semantic similarity - improved retrieval"""
    t0 = time.time()
    global embedding_model, _chunk_embeddings_cache
    try:
        # Ensure embedding_model is loaded
        if embedding_model is None:
            embedding_model, _ = _load_embedding_model()
        
        kv_path = f"{WORKING_DIR}/kv_store_text_chunks.json"
        if not os.path.exists(kv_path):
            print(f"\n[!] Chunks file not found: {kv_path}")
            return []
        
        t1 = time.time()
        with open(kv_path) as f:
            data = json.load(f)
            chunks = []
            chunk_ids = []
            for chunk_id, item in data.items():
                if isinstance(item, dict) and 'content' in item:
                    chunks.append(item['content'])
                    chunk_ids.append(chunk_id)
        
        t_load = time.time() - t1
        
        if not chunks:
            print(f"\n[!] No chunks loaded from file")
            return []
        
        print(f" [{len(chunks)} chunks, {t_load:.2f}s]", end='', flush=True)
        
        query_lower = query.lower()
        scores = []
        chunk_embeddings = get_chunk_embeddings()
        
        t2 = time.time()
        
        if embedding_model and chunk_embeddings:
            # Import numpy only when needed (deferred)
            import numpy as np
            
            # embedding_model.encode() is synchronous and returns numpy array directly
            query_embedding = embedding_model.encode(query, convert_to_numpy=True, show_progress_bar=False)
            
            for i, chunk in enumerate(chunks):
                if i in chunk_embeddings:
                    # Semantic similarity
                    similarity = np.dot(query_embedding, chunk_embeddings[i]) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embeddings[i]) + 1e-8
                    )
                    
                    # Lexical boost: if query terms appear in chunk, increase score
                    query_terms = [w for w in query_lower.split() if len(w) > 3]
                    chunk_lower = chunk.lower()
                    lexical_boost = 1.0
                    for term in query_terms:
                        if term in chunk_lower:
                            lexical_boost += 0.15
                    
                    final_score = similarity * lexical_boost
                    scores.append(final_score)
                else:
                    scores.append(0)
        else:
            for chunk in chunks:
                chunk_lower = chunk.lower()
                query_words = set(query_lower.split())
                chunk_words = set(chunk_lower.split())
                overlap = len(query_words & chunk_words)
                scores.append(overlap)
        
        t_score = time.time() - t2
        
        # Get top K chunks with highest scores (from .env)
        import numpy as np
        top_k = int(os.getenv('TOP_K_SEARCH', '10'))
        top_indices = np.argsort(-np.array(scores))[:top_k]
        best_chunks = [chunks[i] for i in top_indices]
        best_scores = [scores[i] for i in top_indices]
        
        combined = "\n\n".join(best_chunks)
        combined = re.sub(r'===\s*Page\s+\d+\s*===', '', combined)
        
        t_total = time.time() - t0
        
        # Debug: show top chunks info
        print(f" [Top scores: {[f'{s:.2f}' for s in best_scores[:3]]}]", end='', flush=True)
        
        return [{'content': combined}]
        
    except Exception as e:
        print(f"\n[Search Error] {e}")
        import traceback
        traceback.print_exc()
        return []


async def main():
    print("\n" + "="*70)
    print("[RAG CHATBOT] - PDF Document Analysis")
    print("="*70 + "\n")
    
    global embedding_func, embedding_model
    try:
        print("[*] Initializing system...")
        
        # Deferred import of LightRAG - only load when needed
        from lightrag import LightRAG, QueryParam
        
        # Load embedding model & function (needed for LightRAG)
        if embedding_func is None:
            embedding_model, embedding_func = _load_embedding_model()
        
        rag = LightRAG(
            working_dir=WORKING_DIR,
            llm_model_func=llm_model_func_openrouter,
            embedding_func=embedding_func,
        )
        await rag.initialize_storages()
        from lightrag.kg.shared_storage import initialize_pipeline_status
        await initialize_pipeline_status()
        print("[✓] System ready\n")
        
        # Ingest documents
        await ingest_documents(rag)
        
    except Exception as e:
        print(f"[!] Error: {e}")
        return
    
    print("="*70)
    print("[READY FOR QUERIES]")
    print("="*70)
    print("💬 Ask questions | 📝 Type 'exit' to close\n")
    
    while True:
        try:
            t_loop_start = time.time()
            user_input = input("You: ").strip()
            if user_input.lower() in ['exit', 'quit', 'keluar']:
                print("\n[✓] Goodbye!\n")
                break
            if not user_input:
                continue
            
            # Check if debug mode requested
            debug_chunks = "?chunks" in user_input
            debug_query = user_input.replace("?chunks", "").strip()
            
            t_search_start = time.time()
            print("🔍 Searching...", end='', flush=True)
            
            chunks = await search_chunks(debug_query)
            t_search_time = time.time() - t_search_start
            
            if not chunks:
                print(" [No results]\n")
                continue
            
            # Show chunk debug if requested
            if debug_chunks:
                print(f" [{len(chunks)} chunks]")
                print("\n[DEBUG] Retrieved chunks:")
                for i, chunk in enumerate(chunks[:3], 1):
                    content_preview = chunk['content'][:150].replace('\n', ' ')
                    print(f"  {i}. {content_preview}...")
                print()
            else:
                print(f" [{len(chunks)} chunks, {t_search_time:.2f}s]", end='')
            
            # Combine chunks for context
            context = "\n\n".join([c['content'] for c in chunks])
            context = re.sub(r'===\s*Page\s+\d+\s*===', '', context)
            
            print(" 🤖 Bot: ", end='', flush=True)
            
            # Clean text
            def clean_text(text):
                lines = text.split('\n')
                cleaned = []
                for line in lines:
                    stripped = line.strip()
                    if stripped:
                        cleaned.append(stripped)
                return '\n'.join(cleaned)
            
            context = clean_text(context)
            
            # For short content: show directly
            if len(context) < 600:
                print(f"{context}\n")
            else:
                # For longer content: use LLM to answer
                system_prompt = "Kamu adalah assistant yang menjelaskan dokumen dengan jelas, akurat, dan berbasis konteks."
                answer_prompt = f"Pertanyaan: {user_input}\n\nKonteks dari dokumen:\n{context}\n\nBerdasarkan konteks dokumen di atas, jawab pertanyaan dengan ringkas dan akurat. Jika informasi tidak ada di konteks, katakan 'Informasi tidak tersedia dalam dokumen':\n"
                
                try:
                    t_llm_start = time.time()
                    answer = await asyncio.wait_for(
                        llm_model_func_openrouter(answer_prompt, sys_prompt=system_prompt),
                        timeout=60.0
                    )
                    t_llm_time = time.time() - t_llm_start
                    
                    print(f"{answer}")
                    
                    t_total = time.time() - t_loop_start
                    print(f"\n⏱️ Timing: Search={t_search_time:.2f}s, LLM={t_llm_time:.2f}s, Total={t_total:.2f}s\n")
                    
                except asyncio.TimeoutError:
                    print("[Timeout]\n")
                except Exception as e:
                    print(f"[Error: {str(e)[:40]}]\n")
        
        except KeyboardInterrupt:
            print("\n\n[✓] Interrupted\n")
            break
        except Exception as e:
            print(f"\n[Error: {str(e)[:80]}]\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[✓] Stopped")
    except Exception as e:
        print(f"[!] Error: {e}")
