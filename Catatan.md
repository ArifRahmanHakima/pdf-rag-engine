# Dokumen Monitoring & Evaluasi (Monev)
## Sistem Chatbot Berbasis RAG - PDF Question Answering

**Tanggal:** 15 Desember 2025  
**Versi:** 1.0.0  
**Status:** Production Ready

---

## A. Latar Belakang

Sistem chatbot berbasis Retrieval-Augmented Generation (RAG) yang dikembangkan saat ini memungkinkan pengguna mengunggah dokumen PDF dan melakukan tanya jawab berdasarkan isi dokumen tersebut. Namun, dalam proses implementasi ditemukan beberapa kendala teknis yang berdampak pada performa sistem, akurasi jawaban, serta pengalaman pengguna. 

Oleh karena itu, diperlukan langkah perbaikan yang terukur dan terdokumentasi melalui kegiatan monitoring dan evaluasi (Monev).

---

## 📋 Tabel Wishlist Perbaikan

| No | Wishlist / Perbaikan | Status | Prioritas |
|----|---------------------|:------:|:---------:|
| 1 | Pemisahan sesi chat per dokumen (doc_id) | ✔️ | - |
| 2 | Chatbot hanya menjawab berdasarkan PDF aktif | ✔️ | - |
| 3 | Embedding menggunakan model lokal (tanpa API) | ✔️ | - |
| 4 | Working directory per dokumen | ✔️ | - |
| 5 | RAG instance terisolasi per dokumen | ✔️ | - |
| 6 | Migrasi ke Groq API (ultra fast) | ✔️ | - |
| 7 | Riwayat chat terpisah untuk setiap PDF | ✔️ | - |
| 8 | Filter retrieval berdasarkan doc_id | ✔️ | - |
| 9 | Progress tracking real-time | ✔️ | - |
| 10 | Background task untuk parsing & embedding | ✘ | 🔴 HIGH |
| 11 | Parallel & batch embedding | ✘ | 🟡 MEDIUM |
| 12 | Rerank model configuration | ✘ | 🟢 LOW |
| 13 | Fallback model saat API LLM limit | ✘ | 🟡 MEDIUM |
| 14 | Cache hasil parsing & jawaban | ✘ | 🟡 MEDIUM |
| 15 | UI indikator dokumen aktif | ✘ | 🔴 HIGH |
| 16 | Rate limiting protection | ✘ | 🟡 MEDIUM |
| 17 | Database migration tool (Alembic) | ✘ | 🟢 LOW |
| 18 | Unit testing & integration testing | ✘ | 🔴 HIGH |
| 19 | LLM output format validation | ✘ | 🟢 LOW |
| 20 | Async parsing PDF | ✘ | 🔴 HIGH |

**Progress:** 9/20 selesai (45%)

---

## B. Tech Stack

| Komponen | Teknologi | Versi |
|----------|-----------|-------|
| **Backend Framework** | FastAPI | Latest |
| **LLM Provider** | Groq API | Free Tier |
| **LLM Model** | llama-3.1-8b-instant | Latest |
| **RAG Engine** | LightRAG + RAGAnything | Latest |
| **PDF Parser** | MineRU | Latest |
| **Embedding** | SentenceTransformer (Local) | all-MiniLM-L6-v2 |
| **Database** | PostgreSQL | 14+ |
| **Cache** | Redis | Alpine |
| **Frontend** | Vanilla JavaScript | ES6+ |

---

## C. Identifikasi Permasalahan

### 1. **Isolasi Dokumen Belum Sempurna** ✔️ SUDAH DIPERBAIKI

**Deskripsi:**  
Chatbot masih menjawab berdasarkan dokumen PDF lama meskipun pengguna telah mengunggah dokumen PDF baru.

**Penyebab:**
- Vector database menyimpan embedding dari beberapa PDF dalam satu konteks tanpa filter yang ketat
- Tidak ada pemisahan sesi dokumen secara jelas

**Contoh Kasus:**
```
PDF A: "Perintah Perbaikan Gateway"
PDF B: "Surat Permohonan Pengarahan KKN"

Saat user membuka PDF B dan bertanya:
❌ SALAH: Chatbot menjawab dengan konteks PDF A + PDF B (tercampur)
✅ BENAR: Chatbot hanya menjawab dari PDF B
```

**Solusi yang Diterapkan:**
```python
# api/services/rag_engine.py
def get_doc_id(filename: str) -> str:
    """Generate unique doc_id per PDF"""
    return hashlib.md5(filename.encode()).hexdigest()[:16]

# Setiap PDF punya working directory terpisah
doc_working_dir = os.path.join(base_dir, doc_id)

# RAG instance terisolasi per dokumen
rag_instances[doc_id] = RAGAnything(working_dir=doc_working_dir, ...)
```

**Status:** ✔️ **SUDAH DITERAPKAN**

---

### 2. **Parsing PDF Lambat**

**Deskripsi:**  
Proses parsing dokumen PDF membutuhkan waktu yang cukup lama, terutama pada dokumen berukuran besar (>5MB) atau memiliki banyak halaman.

**Dampak:**
- Upload PDF 10MB bisa memakan waktu 30-60 detik
- UI freeze selama proses parsing
- User tidak tahu apakah sistem sedang proses atau error

**Log yang Muncul:**
```
INFO: Detected PDF file, using parser for PDF...
[menunggu lama...]
INFO: Parsing uploads\file.pdf complete! Extracted 7 content blocks
```

**Penyebab:**
- Parser memproses seluruh isi dokumen (teks, tabel, gambar) secara **sinkron**
- Tidak ada background task processing
- `max_concurrent_files=1` (sequential processing)

**Solusi yang Dibutuhkan:**
```python
# 1. Tambahkan background task
from fastapi import BackgroundTasks

@router.post("/upload")
async def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks):
    # Simpan file dulu
    file_path = save_file(file)
    doc_id = get_doc_id(file.filename)
    
    # Update status: PARSING
    redis_client.set(f"doc:{doc_id}:status", "PARSING")
    
    # Jalankan parsing di background
    background_tasks.add_task(process_pdf_async, file_path, doc_id)
    
    return {"doc_id": doc_id, "status": "processing"}

# 2. Ubah max_concurrent_files
max_concurrent_files=4  # dari 1 ke 4
```

**File yang Perlu Diubah:**
- `api/routes/upload.py` (tambah BackgroundTasks)
- `api/services/rag_engine.py` (ubah max_concurrent_files)

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🔴 HIGH)

---

### 3. **Rerank Model Tidak Dikonfigurasi**

**Deskripsi:**  
LightRAG enable rerank by default tetapi model rerank tidak dikonfigurasi, menyebabkan warning spam di terminal.

**Warning yang Muncul:**
```
WARNING: Rerank is enabled but no rerank model is configured. 
Please set up a rerank model or set enable_rerank=False in query parameters.
```

**Dampak:**
- Search results kurang optimal
- Log terminal penuh dengan warning
- Tidak critical, tapi mengganggu

**Solusi yang Dibutuhkan:**
```python
# api/services/rag_engine.py - Tambahkan parameter ini
rag = RAGAnything(
    working_dir=working_dir,
    parser="mineru",
    parse_method="auto",
    enable_image_processing=False,
    enable_table_processing=False,
    enable_equation_processing=False,
    max_concurrent_files=1,
    enable_rerank=False  # ← TAMBAHKAN INI
)
```

**Alternatif (jika ingin pakai rerank):**
```bash
pip install sentence-transformers
# Lalu config model di RAG
```

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🟢 LOW)

---

### 4. **LLM Output Format Error**

**Deskripsi:**  
Model LLM kadang tidak mengikuti format output yang diminta saat extraction entities dan relations.

**Warning yang Muncul:**
```
WARNING: Complete delimiter can not be found in extraction result
WARNING: LLM output format error; found 2/5 fields on REALTION `Malin Kundang<`~`N/A`
```

**Penyebab:**
- Prompt template kurang strict
- Model `llama-3.1-8b-instant` kadang tidak konsisten dengan delimiter
- Tidak ada retry mechanism

**Dampak:**
- Entity extraction tidak sempurna (tapi tetap berfungsi)
- Beberapa relasi ter-skip
- Tidak critical (sistem tetap jalan)

**Solusi yang Dibutuhkan:**
```python
# api/services/llm_wrapper.py
async def llm_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = await llm_call(prompt)
            # Validasi format output
            if validate_format(response):
                return response
        except Exception as e:
            if attempt == max_retries - 1:
                # Fallback ke model lain
                return await fallback_model_call(prompt)
            continue
```

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🟢 LOW)

---

### 5. **Multimodal Processing Disabled**

**Deskripsi:**  
Gambar, tabel, dan equation di PDF tidak diproses karena multimodal processing dimatikan.

**Konfigurasi Saat Ini:**
```python
enable_image_processing=False
enable_table_processing=False
enable_equation_processing=False
```

**Alasan Disabled:**
- API calls naik 3x jika enabled
- Hemat quota dan lebih cepat
- Fokus ke text-only documents

**Trade-off:**
| Mode | Kecepatan | API Calls | Akurasi untuk PDF Kompleks |
|------|-----------|-----------|----------------------------|
| Multimodal ON | Lambat | 3x lebih banyak | Sangat akurat |
| Multimodal OFF | Cepat | Minimal | Kurang akurat (skip visual) |

**Solusi yang Dibutuhkan:**
```python
# Tambahkan toggle di frontend
<input type="checkbox" id="enable-multimodal" />
<label>Enable gambar & tabel (lebih lambat tapi akurat)</label>

# Backend menerima parameter
@router.post("/upload")
async def upload_pdf(file, enable_multimodal: bool = False):
    rag = RAGAnything(
        enable_image_processing=enable_multimodal,
        enable_table_processing=enable_multimodal,
        ...
    )
```

**Status:** ✘ **BY DESIGN** (Priority: 🟡 MEDIUM)

---

### 6. **Tidak Ada Progress Tracking**

**Deskripsi:**  
User tidak tahu apakah PDF sedang diproses atau error. Tidak ada indikator status upload.

**Dampak:**
- User bingung apakah upload berhasil
- UI terlihat freeze
- User bisa upload berulang kali (duplikasi)

**Solusi yang Dibutuhkan:**

**Backend:**
```python
# api/routes/upload.py - Tambahkan endpoint status
@router.get("/upload/status/{doc_id}")
async def get_upload_status(doc_id: str):
    status = redis_client.get(f"doc:{doc_id}:status")
    progress = redis_client.get(f"doc:{doc_id}:progress")
    
    return {
        "status": status,  # PARSING → EXTRACTING → EMBEDDING → DONE
        "progress": int(progress or 0)  # 0-100
    }

# Update status saat parsing
async def process_pdf_async(file_path, doc_id):
    redis_client.set(f"doc:{doc_id}:status", "PARSING")
    redis_client.set(f"doc:{doc_id}:progress", 10)
    
    # Parse PDF
    result = parser.parse(file_path)
    
    redis_client.set(f"doc:{doc_id}:status", "EXTRACTING")
    redis_client.set(f"doc:{doc_id}:progress", 50)
    
    # Extract entities
    entities = extract_entities(result)
    
    redis_client.set(f"doc:{doc_id}:status", "EMBEDDING")
    redis_client.set(f"doc:{doc_id}:progress", 80)
    
    # Create embeddings
    embeddings = create_embeddings(entities)
    
    redis_client.set(f"doc:{doc_id}:status", "DONE")
    redis_client.set(f"doc:{doc_id}:progress", 100)
```

**Frontend:**
```javascript
// frontend/js/pdf-handler.js
async pollUploadStatus(docId) {
    const checkStatus = async () => {
        const response = await fetch(`/upload/status/${docId}`);
        const data = await response.json();
        
        // Update progress bar
        progressBar.style.width = `${data.progress}%`;
        statusText.textContent = data.status;
        
        if (data.status !== 'DONE') {
            setTimeout(checkStatus, 2000); // Poll setiap 2 detik
        } else {
            // Selesai, aktifkan chat
            enableChatInput();
        }
    };
    
    checkStatus();
}
```

**HTML:**
```html
<div class="upload-progress" id="upload-progress" style="display: none;">
    <div class="progress-bar">
        <div class="progress-fill" id="progress-fill"></div>
    </div>
    <p class="status-text" id="status-text">Parsing PDF...</p>
</div>
```

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🔴 HIGH)

---

### 7. **UI Kurang Informatif**

**Deskripsi:**  
User tidak tahu dokumen mana yang sedang aktif, tidak ada list dokumen yang sudah diupload, tidak ada tombol delete.

**Masalah Spesifik:**
- Tidak ada indikator "Dokumen Aktif: perintah_gateway.pdf"
- Tidak ada sidebar untuk list semua dokumen
- Tidak ada metadata (tanggal upload, ukuran file, jumlah chunk)
- Error message terlalu generic ("Network error")

**Solusi yang Dibutuhkan:**

**Tambah Sidebar HTML:**
```html
<!-- frontend/index.html -->
<aside class="document-sidebar">
    <h3>📁 Dokumen Saya</h3>
    <div id="document-list">
        <!-- Diisi dengan JavaScript -->
    </div>
</aside>
```

**Tambah Endpoint List Documents:**
```python
# api/routes/upload.py
@router.get("/documents")
async def list_documents(user_id: str):
    docs = await db.execute(
        "SELECT doc_id, filename, upload_date, file_size FROM documents WHERE user_id = $1",
        user_id
    )
    return {"documents": docs}

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    # Hapus dari database
    await db.execute("DELETE FROM documents WHERE doc_id = $1", doc_id)
    # Hapus folder rag_storage
    shutil.rmtree(f"./rag_storage/{doc_id}")
    return {"status": "deleted"}
```

**Update UI Handler:**
```javascript
// frontend/js/ui-handler.js
async loadDocumentList() {
    const response = await fetch(`/documents?user_id=${userId}`);
    const data = await response.json();
    
    const listHtml = data.documents.map(doc => `
        <div class="document-item ${doc.doc_id === activeDocId ? 'active' : ''}">
            <span class="doc-name">${doc.filename}</span>
            <span class="doc-size">${formatSize(doc.file_size)}</span>
            <button onclick="deleteDocument('${doc.doc_id}')">🗑️</button>
        </div>
    `).join('');
    
    document.getElementById('document-list').innerHTML = listHtml;
}
```

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🔴 HIGH)

---

### 8. **Tidak Ada Rate Limiting**

**Deskripsi:**  
User bisa spam upload atau query tanpa batasan, berpotensi overload server.

**Dampak:**
- Risiko DDoS (user spam request)
- API Groq bisa kena limit
- Server bisa down

**Solusi yang Dibutuhkan:**
```bash
pip install slowapi
```

```python
# api/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# api/routes/upload.py
@router.post("/upload")
@limiter.limit("5/minute")  # Max 5 uploads per menit
async def upload_pdf(request: Request, file: UploadFile):
    ...

# api/routes/chat.py
@router.post("/chat/send")
@limiter.limit("20/minute")  # Max 20 queries per menit
async def send_message(request: Request, ...):
    ...
```

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🟡 MEDIUM)

---

### 9. **Tidak Ada Database Migration Tool**

**Deskripsi:**  
Database schema dibuat manual dengan `init_db.py`, sulit untuk maintain dan deploy.

**Dampak:**
- Schema change manual & error-prone
- Sulit track perubahan database
- Tidak ada rollback mechanism

**Solusi yang Dibutuhkan:**
```bash
pip install alembic
alembic init migrations
```

```python
# alembic/env.py - Setup base URL
config.set_main_option('sqlalchemy.url', DATABASE_URL)

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Tambahkan ke Makefile:**
```makefile
migrate-create:
	alembic revision --autogenerate -m "$(msg)"

migrate-up:
	alembic upgrade head

migrate-down:
	alembic downgrade -1
```

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🟢 LOW)

---

### 10. **Testing Belum Ada**

**Deskripsi:**  
Tidak ada unit test, integration test, atau end-to-end test.

**Dampak:**
- Sulit detect bug sebelum production
- Refactoring berisiko
- Tidak ada test coverage metrics

**Solusi yang Dibutuhkan:**
```bash
pip install pytest pytest-asyncio httpx
```

```python
# tests/test_upload.py
import pytest
from httpx import AsyncClient
from api.main import app

@pytest.mark.asyncio
async def test_upload_pdf():
    async with AsyncClient(app=app, base_url="http://test") as client:
        files = {"file": ("test.pdf", open("test.pdf", "rb"), "application/pdf")}
        response = await client.post("/upload", files=files)
        
        assert response.status_code == 200
        assert "doc_id" in response.json()

@pytest.mark.asyncio
async def test_chat_query():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/chat/send", json={
            "question": "Apa isi dokumen?",
            "doc_id": "test_doc_id",
            "user_id": "test_user"
        })
        
        assert response.status_code == 200
        assert "answer" in response.json()
```

**Run Tests:**
```bash
pytest tests/ -v --cov=api --cov-report=html
```

**Status:** ✘ **BELUM DITERAPKAN** (Priority: 🔴 HIGH)

---

## D. Wishlist Perbaikan & Status Implementasi

### ✅ Sudah Diterapkan (Completed)

| No | Fitur / Perbaikan | Status | Bukti Implementasi |
|----|------------------|--------|-------------------|
| 1 | **Pemisahan sesi chat per dokumen (doc_id)** | ✔️ | `get_doc_id()` di rag_engine.py menggunakan MD5 hash filename |
| 2 | **Embedding menggunakan model lokal (tanpa API)** | ✔️ | `SentenceTransformer` dengan model `all-MiniLM-L6-v2` |
| 3 | **Working directory per dokumen** | ✔️ | `doc_working_dir = os.path.join(base_dir, doc_id)` |
| 4 | **RAG instance terisolasi per dokumen** | ✔️ | `rag_instances = {}` dictionary untuk menyimpan instance terpisah |
| 5 | **Migrasi ke Groq API (ultra fast)** | ✔️ | Groq API dengan model `llama-3.1-8b-instant` |
| 6 | **Riwayat chat terpisah untuk setiap PDF** | ✔️ | `save_message_postgres(chat_id, doc_id, user_id, ...)` |
| 7 | **Filter retrieval berdasarkan doc_id** | ✔️ | Query hanya menggunakan RAG instance spesifik per doc_id |
| 8 | **Multimodal processing disabled (save API)** | ✔️ | `enable_image_processing=False, enable_table_processing=False` |

### ❌ Belum Diterapkan (Pending)

| No | Fitur / Perbaikan | Status | Dampak | Prioritas |
|----|------------------|--------|--------|-----------|
| 9 | **Progress tracking real-time** | ✘ | User tidak tahu status upload/embedding | 🔴 HIGH |
| 10 | **Background task untuk parsing & embedding** | ✘ | Upload blocking, UI freeze | 🔴 HIGH |
| 11 | **Parallel & batch embedding** | ✘ | Proses embedding lambat untuk PDF besar | 🟡 MEDIUM |
| 12 | **Rerank model configuration** | ✘ | Warning di log (tidak critical) | 🟢 LOW |
| 13 | **Fallback model saat API LLM limit** | ✘ | Risiko downtime jika Groq limit | 🟡 MEDIUM |
| 14 | **Cache hasil parsing & jawaban** | ✘ | Re-query lambat untuk pertanyaan serupa | 🟡 MEDIUM |
| 15 | **UI indikator dokumen aktif** | ✘ | User bingung PDF mana yang sedang dibuka | 🔴 HIGH |
| 16 | **Rate limiting protection** | ✘ | Risiko spam request | 🟡 MEDIUM |
| 17 | **Database migration tool (Alembic)** | ✘ | Schema change manual & error-prone | 🟢 LOW |
| 18 | **Unit testing & integration testing** | ✘ | Sulit detect bug sebelum production | 🔴 HIGH |
| 19 | **LLM output format validation** | ✘ | Warning delimiter error masih muncul | 🟢 LOW |
| 20 | **Async parsing PDF** | ✘ | Parsing PDF blocking main thread | 🔴 HIGH |

---

## E. Summary Status

- **✔️ Completed:** 8 items (40%)
- **✘ Pending:** 12 items (60%)
- **🔴 High Priority:** 5 items
- **🟡 Medium Priority:** 4 items
- **🟢 Low Priority:** 3 items

---

## F. Progress Chart

```
Sistem Dasar         ████████████████████ 100% ✅
Isolasi Dokumen      ████████████████████ 100% ✅
Performance          ████████░░░░░░░░░░░░  40% ⏳
UI/UX                ████░░░░░░░░░░░░░░░░  20% ⏳
Testing & Security   ░░░░░░░░░░░░░░░░░░░░   0% ❌
```

---

## G. Roadmap Perbaikan

### Sprint 1: Progress Tracking & Background Task (1-2 hari)

**Target:** Sistem tidak blocking UI saat upload, user bisa track progress

**Tasks:**
- [ ] #10: Implementasi FastAPI BackgroundTasks untuk parsing & embedding
- [ ] #9: Setup Redis untuk status tracking (PARSING → EXTRACTING → EMBEDDING → DONE)
- [ ] #9: Frontend polling setiap 2 detik untuk cek status
- [ ] #9: Tambah progress bar dengan persentase 0-100%
- [ ] #15: Indikator dokumen aktif di UI

**Deliverable:**
- User bisa upload PDF tanpa UI freeze
- User bisa melihat progress real-time
- User tahu dokumen mana yang sedang aktif

---

### Sprint 2: Performance Optimization (2-3 hari)

**Target:** Upload & query lebih cepat

**Tasks:**
- [ ] #11: Parallel embedding dengan `asyncio.gather()`
- [ ] #20: Async parsing dengan mineru
- [ ] #12: Disable rerank warning (tambah `enable_rerank=False`)
- [ ] Ubah `max_concurrent_files` dari 1 ke 4
- [ ] #14: Implement caching untuk hasil parsing & query

**Deliverable:**
- Upload PDF 10MB dari 60 detik → 15 detik
- Query response dari 2 detik → 0.5 detik
- Warning di log berkurang

---

### Sprint 3: UI/UX Improvements (3-4 hari)

**Target:** User experience lebih baik

**Tasks:**
- [ ] #15: Sidebar list dokumen yang sudah diupload
- [ ] #15: Metadata dokumen (tanggal upload, ukuran, jumlah chunk)
- [ ] #15: Tombol delete dokumen
- [ ] Loading spinner untuk setiap aksi
- [ ] Error message lebih spesifik (bukan "Network error" generic)
- [ ] Responsive design untuk mobile

**Deliverable:**
- User bisa lihat semua dokumen yang pernah diupload
- User bisa delete dokumen yang tidak diperlukan
- UI lebih user-friendly

---

### Sprint 4: Security & Testing (2-3 hari)

**Target:** Sistem production-ready

**Tasks:**
- [ ] #16: Implementasi rate limiting (SlowAPI)
- [ ] #17: Setup Alembic untuk database migration
- [ ] #18: Setup pytest untuk unit testing
- [ ] #18: Write test untuk upload endpoint
- [ ] #18: Write test untuk chat endpoint
- [ ] #13: Fallback model (Groq → OpenRouter jika limit)
- [ ] Security: Tambahkan `.env` ke `.gitignore`
- [ ] Security: Buat `.env.example` untuk template

**Deliverable:**
- Rate limiting: max 5 uploads/min, 20 queries/min
- Test coverage >70%
- Database migration dengan Alembic
- API key aman (tidak di git)

---

## H. Quick Fixes (Bisa Dikerjakan <1 Jam)

### Fix #1: Disable Rerank Warning (5 menit)
```python
# api/services/rag_engine.py
rag = RAGAnything(
    working_dir=working_dir,
    parser="mineru",
    parse_method="auto",
    enable_image_processing=False,
    enable_table_processing=False,
    enable_equation_processing=False,
    max_concurrent_files=1,
    enable_rerank=False  # ← TAMBAHKAN INI
)
```

### Fix #2: Tambahkan .env ke .gitignore (2 menit)
```bash
echo ".env" >> .gitignore
git rm --cached .env
git commit -m "chore: remove .env from git tracking"
```

### Fix #3: Increase Concurrent Files (2 menit)
```python
# api/services/rag_engine.py
max_concurrent_files=4  # ← Ubah dari 1 ke 4
```

### Fix #4: Buat .env.example (5 menit)
```bash
cp .env .env.example
# Edit .env.example, ganti semua nilai secret dengan placeholder
OPENROUTER_API_KEY=your_groq_api_key_here
POSTGRES_PASSWORD=your_password_here
```

---

## I. Troubleshooting Guide

### Error: "Network error during upload"
**Penyebab:** Server belum running  
**Solusi:** 
```bash
uvicorn api.main:app --reload
```

### Error: "The model `llama-3.2-3b-preview` has been decommissioned"
**Penyebab:** Model deprecated oleh Groq  
**Solusi:** Update `.env`:
```
LLM_MODEL=llama-3.1-8b-instant
VISION_MODEL=llama-3.1-8b-instant
```

### Warning: "Rerank is enabled but no rerank model is configured"
**Penyebab:** LightRAG enable rerank by default  
**Solusi:** Tambahkan `enable_rerank=False` di `rag_engine.py` (lihat Quick Fix #1)

### Upload Lambat (>30 detik)
**Penyebab:** `max_concurrent_files=1`  
**Solusi:** Ubah ke `max_concurrent_files=4` (lihat Quick Fix #3)

### PostgreSQL Connection Error
**Penyebab:** Docker belum running  
**Solusi:**
```bash
docker-compose ps  # Check status
docker-compose up -d  # Start containers
```

### Chat Menjawab dari PDF Lama
**Penyebab:** (SUDAH DIPERBAIKI) - doc_id isolation sudah diterapkan  
**Validasi:** Cek `rag_instances` di `rag_engine.py`, setiap PDF punya instance terpisah

---

## J. Arsitektur Teknis

### Flow Diagram: Upload → Parsing → Embedding → Query

```
┌─────────────┐
│   USER      │
│ Upload PDF  │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│   BACKEND        │
│ 1. Simpan file   │──────┐
│ 2. Generate      │      │ Redis: status = "PARSING"
│    doc_id        │      │ progress = 10%
└──────┬───────────┘      │
       │                  │
       ▼                  │
┌──────────────────┐      │
│  PARSER (MineRU) │      │
│ Extract text,    │──────┤ Redis: status = "EXTRACTING"
│ tables, images   │      │ progress = 50%
└──────┬───────────┘      │
       │                  │
       ▼                  │
┌──────────────────┐      │
│  LIGHTRAG        │      │
│ 1. Chunk text    │──────┤ Redis: status = "EMBEDDING"
│ 2. Extract       │      │ progress = 80%
│    entities      │      │
│ 3. Create graph  │      │
└──────┬───────────┘      │
       │                  │
       ▼                  │
┌──────────────────┐      │
│  EMBEDDING       │      │
│ (Local Model)    │──────┘ Redis: status = "DONE"
│ SentenceTransf.  │        progress = 100%
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  VECTOR STORE    │
│ Save embeddings  │
│ per doc_id       │
└──────┬───────────┘
       │
       │ User bertanya
       ▼
┌──────────────────┐
│  RETRIEVAL       │
│ Filter: doc_id   │──┐
│ Top-k: 5 chunks  │  │
└──────┬───────────┘  │
       │              │
       ▼              │
┌──────────────────┐  │
│  LLM (Groq)      │  │
│ llama-3.1-8b     │◄─┘
│ Generate answer  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  RESPONSE        │
│ Return to user   │
└──────────────────┘
```

### Isolasi Dokumen (Document Isolation)

```
User Upload:
├── PDF A: "perintah_gateway.pdf"
│   ├── doc_id: a1b2c3d4
│   ├── working_dir: ./rag_storage/a1b2c3d4/
│   ├── RAG instance: rag_instances["a1b2c3d4"]
│   ├── Embeddings: vdb_chunks.json (filtered by doc_id)
│   └── Chat history: chat_id = user_id + a1b2c3d4
│
└── PDF B: "surat_kkn.pdf"
    ├── doc_id: e5f6g7h8
    ├── working_dir: ./rag_storage/e5f6g7h8/
    ├── RAG instance: rag_instances["e5f6g7h8"]
    ├── Embeddings: vdb_chunks.json (filtered by doc_id)
    └── Chat history: chat_id = user_id + e5f6g7h8

Query Flow:
User chat di PDF B → Backend filter doc_id=e5f6g7h8 → Hanya ambil embedding dari PDF B
```

### Database Schema

**Table: documents**
```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(16) UNIQUE NOT NULL,
    filename VARCHAR(255) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    file_size INTEGER,
    upload_date TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'processing'
);
```

**Table: messages**
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    chat_id VARCHAR(100) NOT NULL,
    doc_id VARCHAR(16) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    sender VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
```

**Redis Keys:**
```
doc:{doc_id}:status        → "PARSING" | "EXTRACTING" | "EMBEDDING" | "DONE"
doc:{doc_id}:progress      → 0-100
doc:{doc_id}:error         → Error message (jika ada)
chat:{chat_id}:context     → Last 5 messages (for context)
```

---

## K. Kesimpulan

Melalui pelaksanaan perbaikan berdasarkan hasil monitoring dan evaluasi ini, diharapkan sistem chatbot RAG mampu:

✅ Memberikan jawaban yang konsisten dan relevan dengan dokumen aktif  
✅ Memiliki performa lebih cepat dan stabil  
✅ Menghindari permasalahan rate limit API  
✅ Memberikan pengalaman pengguna yang lebih baik dan terstruktur  
✅ Production-ready dengan testing & security yang memadai

---

## L. Next Actions

**Untuk Developer:**
1. Pilih Sprint 1 sebagai prioritas pertama
2. Setup Redis untuk status tracking
3. Implementasi background task
4. Test manual untuk validasi

**Untuk Monitoring:**
1. Track metrics: upload time, query response time, error rate
2. Monitor Groq API usage
3. Check PostgreSQL & Redis performance

**Untuk Dokumentasi:**
1. Update README.md setelah setiap sprint selesai
2. Screenshot fitur baru untuk demo
3. Tulis changelog untuk setiap versi

---

**Last Updated:** 15 Desember 2025  
**Author:** ACER  
**Version:** 1.0.0  
**Status:** Ready for Sprint 1 Implementation



