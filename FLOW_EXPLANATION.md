# 🚀 Penjelasan Alur RAG_Anything

Dokumen ini menjelaskan bagaimana sistem RAG_Anything bekerja dari awal hingga akhir.

---

## 📋 Daftar Isi
1. [Arsitektur Umum](#arsitektur-umum)
2. [Alur Upload PDF](#alur-upload-pdf)
3. [Alur Upload dengan DocString](#alur-upload-dengan-docstring)
4. [Perbandingan OCR vs DocString](#perbandingan-ocr-vs-docstring)
5. [Alur Query / Tanya](#alur-query--tanya)
6. [File-File Penting](#file-file-penting)
7. [Teknologi yang Digunakan](#teknologi-yang-digunakan)

---

## 🏗️ Arsitektur Umum

### Komponen Utama

```
┌─────────────────┐
│   FRONTEND      │
│  (Browser UI)   │
└────────┬────────┘
         │
    [HTTP Request]
         │
         ▼
┌─────────────────────────────┐
│   FASTAPI SERVER            │
│  (main_server.py)           │
│  - Upload endpoint          │
│  - Query endpoint           │
│  - Status endpoint          │
└────────┬────────────────────┘
         │
    ┌────┴─────────────┐
    │                  │
    ▼                  ▼
┌──────────────┐  ┌──────────────┐
│ PROCESSING   │  │  STORAGE     │
│ - Extract    │  │ - PostgreSQL │
│ - Chunk      │  │ - Qdrant     │
│ - Embed      │  │ - RAG Graph  │
└──────────────┘  └──────────────┘
```

---

## 📤 Alur Upload PDF

### Step by Step

```
1️⃣ USER UPLOAD PDF
   └─ Click "Upload PDF" di browser
   └─ Pilih file PDF
   └─ Kirim ke server

2️⃣ SERVER TERIMA
   └─ main_server.py terima file
   └─ Panggil api_handlers.py (upload handler)
   └─ Inisialisasi RAG instance

3️⃣ EXTRACT TEXT
   └─ Panggil main_openrouter.py
   └─ Gunakan OCR (Tesseract)
   └─ Extract text dari PDF
   └─ Hasil: Raw text dokumen

4️⃣ CLEAN & SPLIT
   └─ text_processing.py bersihkan text
   └─ Split jadi chunks (bagian kecil)
   └─ Setiap chunk ~500-1000 karakter
   └─ Hasil: List of chunks

5️⃣ GENERATE EMBEDDINGS
   └─ embedding_service.py proses chunks
   └─ Gunakan Sentence Transformers (Qwen)
   └─ Convert setiap chunk jadi vector 768D
   └─ Hasil: Vector embeddings

6️⃣ STORE DI DATABASE
   └─ PostgreSQL:
      ├─ Session table (session ID)
      ├─ Document table (filename, size, type)
      └─ Chunk table (content, metadata)
   
   └─ Qdrant (Vector DB):
      ├─ Store embeddings vectors
      └─ Index untuk fast search
   
   └─ LightRAG (Knowledge Graph):
      ├─ Extract entities (nama, tipe)
      ├─ Extract relations (verb, connection)
      └─ Store di knowledge graph

7️⃣ SELESAI
   └─ Return status "ready" ke frontend
   └─ PDF siap di-query
```

### Visualisasi Proses

```
PDF File (Gubernur-Yogya.pdf)
    ↓
    ├─→ OCR Extract → "GUBERNUR DAERAH ISTIMEWA YOGYAKARTA..."
    ↓
    ├─→ Clean & Split → [
    │                      "Menimbang: a. bahwa...",
    │                      "b. bahwa dengan...",
    │                      "Menetapkan: ..."
    │                    ]
    ↓
    ├─→ Embed Each → [
    │                  [0.21, 0.45, -0.12, ...],
    │                  [0.33, -0.21, 0.54, ...],
    │                  [0.12, 0.09, -0.44, ...]
    │                ]
    ↓
    ├─→ Store:
    │   ├─ PostgreSQL: Chunks + Metadata
    │   ├─ Qdrant: Vectors for search
    │   └─ LightRAG: Relations & Entities
    ↓
SIAP UNTUK DI-QUERY! ✅
```

---

## 📤 Alur Upload dengan DocString

### Apa itu DocString?

DocString adalah **API eksternal dari Nanonets** yang spesialisasi dalam extract text dari PDF dengan **kualitas lebih tinggi** daripada OCR biasa. DocString menggunakan machine learning untuk:
- Extract text lebih akurat
- Preserve formatting (tabel, list)
- Detect structure dokumen
- Handle scanned PDF lebih baik

### Kapan Gunakan DocString?

| Situasi | Gunakan DocString | Gunakan OCR Biasa |
|---------|-------------------|-------------------|
| PDF scanned (foto) | ✅ Lebih akurat | ❌ Sering salah |
| PDF native digital | ⚠️ OK tapi boros | ✅ Cukup |
| Dokumen formal/hukum | ✅ Lebih presisi | ⚠️ Kurang presisi |
| Kecepatan penting | ❌ Lambat (API call) | ✅ Cepat (local) |
| Internet terbatas | ❌ Butuh internet | ✅ Offline |
| Biaya penting | ❌ Ada cost API | ✅ Gratis |

### Step by Step (dengan DocString)

```
1️⃣ USER UPLOAD dengan "DocString" Button
   └─ Click "DocString" di browser (bukan "Upload PDF")
   └─ Pilih file PDF
   └─ Kirim ke server

2️⃣ SERVER TERIMA
   └─ main_server.py terima file
   └─ Panggil docstring_handlers.py (special handler)
   └─ Inisialisasi RAG instance

3️⃣ EXTRACT TEXT via DOCSTRING API
   └─ docstring_service.py proses:
      ├─ Kirim PDF ke Nanonets DocString API
      ├─ Tunggu API response (bisa beberapa detik)
      ├─ Dapat text dengan struktur lebih baik
      └─ Hasil: Cleaner text dari OCR biasa

   ▼ Kalo DocString gagal (502 error):
      Fallback otomatis ke OCR (main_openrouter.py)
      Tidak gagal, hanya dengan kualitas lebih rendah

4️⃣ CLEAN MARKDOWN OUTPUT
   └─ text_processing.py process:
      ├─ Remove HTML tags (DocString output markdown)
      ├─ Clean extra whitespace
      ├─ Normalize formatting
      └─ Hasil: Clean text ready to split

5️⃣ SPLIT INTO CHUNKS
   └─ text_processing.py split chunks
   └─ Setiap chunk ~500-1000 karakter
   └─ Hasil: List of chunks

6️⃣ GENERATE EMBEDDINGS
   └─ embedding_service.py proses chunks
   └─ Gunakan Sentence Transformers (Qwen)
   └─ Convert setiap chunk jadi vector 768D
   └─ Hasil: Vector embeddings

7️⃣ STORE DI DATABASE
   └─ PostgreSQL:
      ├─ Document table: doc_type = "docstring" (mark ini dari DocString)
      ├─ Chunk table (same as OCR)
      └─ Metadata: extraction time, size
   
   └─ Qdrant (Vector DB):
      ├─ Store embeddings vectors (same as OCR)
      └─ Index untuk fast search
   
   └─ LightRAG (Knowledge Graph):
      ├─ Extract entities (sama)
      ├─ Extract relations (sama)
      └─ Store di knowledge graph

8️⃣ SELESAI
   └─ Return status "ready" ke frontend
   └─ PDF siap di-query
```

### Visualisasi Proses DocString

```
PDF File (Dokumen-Formal.pdf)
    ↓
    ├─→ Upload ke Nanonets DocString API → "DOKUMEN FORMAL..."
    │   (Better quality extraction)
    ↓
    ├─→ Clean Markdown → Remove tags, normalize
    ↓
    ├─→ Split Chunks → [
    │                     "Pasal 1: Ketentuan Umum...",
    │                     "Pasal 2: Objek...",
    │                     "Pasal 3: ..."
    │                   ]
    ↓
    ├─→ Embed Each → [
    │                  [0.15, 0.52, -0.08, ...],
    │                  [0.27, -0.18, 0.61, ...],
    │                  [0.09, 0.12, -0.38, ...]
    │                ]
    ↓
    ├─→ Store:
    │   ├─ PostgreSQL: doc_type = "docstring"
    │   ├─ Qdrant: Vectors for search
    │   └─ LightRAG: Relations & Entities
    ↓
SIAP UNTUK DI-QUERY! ✅ (dengan quality lebih baik)
```

---

## 🔄 Perbandingan OCR vs DocString

### Flow Perbandingan

| Aspek | OCR Biasa | DocString |
|-------|-----------|-----------|
| **Metode Extract** | Local (Tesseract) | API eksternal (Nanonets) |
| **Kecepatan** | 2-5 detik | 5-15 detik |
| **Akurasi** | 70-85% | 85-95% |
| **Formatting** | Sering hilang | Preserved |
| **Tabel** | Berantakan | Struktural |
| **Cost** | FREE | Ada API cost |
| **Internet** | Tidak perlu | Perlu |
| **Fallback** | Ada (EasyOCR) | Ada (fallback ke OCR) |

### Kapan Database Menunjukkan Perbedaan

**PostgreSQL doc_type field:**
```sql
-- OCR biasa
SELECT * FROM documents WHERE doc_type = 'ocr'

-- DocString
SELECT * FROM documents WHERE doc_type = 'docstring'
```

**Frontend UI:**
```javascript
// Bisa show icon berbeda berdasarkan doc_type
if (doc.doc_type === 'docstring') {
    badge = '🟢 DocString (High Quality)';
} else {
    badge = '🟡 OCR (Standard)';
}
```

### Query Behavior (Same)

**PENTING: Baik OCR maupun DocString, query behavior SAMA:**
```
Upload dengan OCR
    ↓
Query: "Apa isi pasal 1?"
    ↓
Search chunks + LLM → Answer ✅

Upload dengan DocString
    ↓
Query: "Apa isi pasal 1?" (SAME QUERY)
    ↓
Search chunks + LLM → Answer ✅ (LEBIH AKURAT)
```

**Perbedaannya hanya di extraction quality, bukan query logic.**

---

## ❓ Alur Query / Tanya

### Step by Step

```
1️⃣ USER TANYA
   └─ Ketik: "Apa isi poin a bagian menimbang?"
   └─ Click Send

2️⃣ SERVER TERIMA QUERY
   └─ api_handlers.py (query handler)
   └─ Dapat: session_id, doc_id, question

3️⃣ SEARCH CHUNKS RELEVAN
   └─ search_logic.py proses:
      ├─ Embed query (convert ke vector)
      ├─ Search di Qdrant (vector similarity)
      ├─ Dapat top-N chunks yang relevan
      └─ Combine semua chunks jadi context

   ▼ Contoh hasil search:
      Chunk 1: "Menimbang: a. bahwa dengan terlaksananya..."
      Chunk 2: "Poin a: bahwa pertimbangan didasarkan..."

4️⃣ PREPARE CONTEXT
   └─ Gabung semua chunks
   └─ Clean markdown
   └─ Limit ~8000 karakter
   └─ Hasil: Rich context untuk LLM

5️⃣ BUILD PROMPT
   └─ query_processor.py buat prompt:
      ├─ System prompt (instruksi untuk LLM)
      ├─ User prompt (question + context)
      └─ Optimize untuk answer generation

   ▼ Contoh prompt:
      System: "Kamu assistant yang menjawab dari dokumen"
      User: "Pertanyaan: Apa isi poin a?
             Context: [chunks yang relevan]
             Jawab:"

6️⃣ CALL LLM API
   └─ llm_service.py panggil OpenRouter
   └─ Kirim prompt ke LLM (e.g., Claude, GPT-4)
   └─ LLM generate jawaban
   └─ Dapat: Jawaban lengkap + formatted

7️⃣ CLEANUP & FORMAT
   └─ cleanup_llm_response() format jawaban
   └─ Remove weird characters
   └─ Add proper spacing
   └─ Hasil: Clean answer

8️⃣ RETURN KE FRONTEND
   └─ API return JSON:
      {
        "success": true,
        "answer": "Poin a: bahwa dengan terlaksananya...",
        "timing": {"total_ms": 2341}
      }

9️⃣ DISPLAY DI UI
   └─ Browser tampilkan jawaban
   └─ User bisa baca & scroll
```

### Visualisasi Query Process

```
User Question: "Apa isi poin a?"
    ↓
    ├─→ Embed Query → [0.15, -0.32, 0.44, ...]
    ↓
    ├─→ Search Qdrant (Vector DB)
    │   Similarity: [Chunk1: 0.89, Chunk2: 0.76, Chunk3: 0.45]
    ↓
    ├─→ Get Top Chunks:
    │   ├─ Chunk1: "Menimbang: a. bahwa dengan..."
    │   └─ Chunk2: "pertimbangan berdasarkan..."
    ↓
    ├─→ Build Prompt:
    │   System: "Answer from document"
    │   Context: [Combined chunks]
    │   Question: "Apa isi poin a?"
    ↓
    ├─→ Call LLM API (OpenRouter)
    │   Kirim prompt → Tunggu response
    ↓
    ├─→ Get Answer:
    │   "Poin a berbicara tentang bahwa dengan..."
    ↓
    ├─→ Format & Cleanup
    ↓
    └─→ Return to Frontend ✅
```

---

## 📁 File-File Penting

### Core Server
| File | Fungsi |
|------|--------|
| **main_server.py** | 🚀 Server utama, terima semua request |
| **main_openrouter.py** | 📄 Extract text pakai OCR |

### Handlers (Menerima Request)
| File | Fungsi |
|------|--------|
| **app/handlers/api_handlers.py** | 🔌 Handle upload, query, delete |
| **app/handlers/docstring_handlers.py** | 🔌 Handle DocString API upload |

### Services (Logic Aplikasi)
| File | Fungsi |
|------|--------|
| **app/services/document_service.py** | 📦 Process upload (extract → chunk → store) |
| **app/services/query_processor.py** | ❓ Process query (build prompt → call LLM) |
| **app/services/search_logic.py** | 🔍 Search chunks relevan |
| **app/services/embedding_service.py** | 🧠 Generate embeddings vectors |
| **app/services/llm_service.py** | 💬 Call OpenRouter LLM API |
| **app/services/docstring_service.py** | 📄 Call Nanonets DocString API |

### Database
| File | Fungsi |
|------|--------|
| **app/db/models.py** | 📊 Define table structure |
| **app/db/storage_manager.py** | 💾 Akses PostgreSQL & Qdrant |

### Utilities
| File | Fungsi |
|------|--------|
| **app/utils/text_processing.py** | ✂️ Clean & split text |
| **app/utils/table_processor.py** | 📋 Format tabel answers |

### Frontend
| Folder | Fungsi |
|--------|--------|
| **ui/index.html** | 🖥️ Chat interface |
| **ui/js/app.js** | ⚙️ Frontend logic |
| **ui/css/style.css** | 🎨 Styling |

### Helpers
| File | Fungsi |
|------|--------|
| **inspect_tables.py** | 👀 View database content |
| **full_reset.py** | 🔄 Reset semua data |

---

## 🛠️ Teknologi yang Digunakan

### Backend Framework
- **FastAPI** - Web server framework (Python)

### Database & Storage
- **PostgreSQL** - Simpan documents, chunks, metadata
- **Qdrant** - Vector database untuk embeddings
- **LightRAG** - Knowledge graph untuk relations

### Text Processing
- **Tesseract OCR** - Extract text dari PDF (scanned)
- **EasyOCR** - Backup OCR engine
- **Sentence Transformers (Qwen)** - Generate embeddings

### LLM & APIs
- **OpenRouter API** - Call berbagai LLM models
- **Nanonets DocString API** - Alternative text extraction

### Frontend
- **HTML5 + CSS3** - UI structure
- **JavaScript** - Frontend logic & API calls

---

## 🔄 Request-Response Flow

### Upload Flow
```
Browser                  Server                  Database
   │                       │                        │
   ├─ POST /upload ──────→ │                        │
   │  (PDF file)           │                        │
   │                       ├─ Extract text ────────→│
   │                       │ (OCR)                  │
   │                       │                        │
   │                       ├─ Split chunks ────────→│
   │                       │                        │
   │                       ├─ Generate embed ──────→│
   │                       │ (Embeddings)           │
   │                       │                        │
   │                       ├─ Store data:           │
   │                       │  ├─ PostgreSQL        │
   │                       │  ├─ Qdrant            │
   │                       │  └─ RAG Graph         │
   │                       │                        │
   │ ← Response (OK) ──────┤                        │
   │   {success: true}     │                        │
```

### Query Flow
```
Browser                  Server                  Database
   │                       │                        │
   ├─ POST /query ───────→ │                        │
   │  (question)           │                        │
   │                       ├─ Search chunks ──────→│
   │                       │ (Vector search)       │
   │                       │                        │
   │                       ← Get top chunks ──────┤
   │                       │                        │
   │                       ├─ Build prompt         │
   │                       │                        │
   │                       ├─ Call LLM API ───────→│ (OpenRouter)
   │                       │                        │
   │ ← Response ───────────┤                        │
   │  {answer: "..."}      │                        │
```

---

## 💡 Tips untuk Memahami

### Ingat 3 Bagian Utama:

1. **UPLOAD (Input)**
   - PDF masuk
   - Extract text
   - Split chunks
   - Store di 3 tempat (PostgreSQL, Qdrant, RAG)

2. **QUERY (Process)**
   - Search chunks relevan
   - Build prompt
   - Call LLM
   - Format answer

3. **STORAGE (Database)**
   - PostgreSQL: Text & metadata
   - Qdrant: Vectors untuk search cepat
   - RAG Graph: Relations antar entity

### Debug Tips:
```bash
# Lihat apa yang ada di database
python inspect_tables.py

# Reset semua data (hati-hati!)
python full_reset.py

# Lihat logs dari server
# Buka terminal server → lihat output
```

---

## 📊 Contoh Kasus Real

### Skenario: Upload & Query Dokumen Gubernur

**Upload:**
```
File: Gubernur-Yogya-2025.pdf (4 halaman)
                ↓
OCR Extract: 3500+ karakter text
                ↓
Split: 7 chunks
    Chunk 1: "Menimbang: a. bahwa dengan terlaksananya..."
    Chunk 2: "b. bahwa berdasarkan pertimbangan..."
    Chunk 3: "Mengingat: 1. UU No. 23 Tahun 2014"
    ... dst
                ↓
Embed: 7 vectors (768D each)
                ↓
Store:
    PostgreSQL: doc_id=gubernur-2025, 7 chunks
    Qdrant: 7 vectors indexed
    RAG: Entity=[Gubernur, SK], Relation=[menandatangani]
```

**Query 1:**
```
Q: "Apa isi poin a bagian menimbang?"
                ↓
Search: Find relevant chunks
    Chunk 1: similarity 0.95 ✅
    Chunk 2: similarity 0.87 ✅
    Chunk 4: similarity 0.32 ❌
                ↓
Context: Combine Chunk 1 + Chunk 2
                ↓
LLM: "Poin a menjelaskan bahwa dengan terlaksananya..."
```

**Query 2:**
```
Q: "Siapa yang menandatangani?"
                ↓
Search: Find relevant chunks
    + RAG relation search: Gubernur → menandatangani → SK
                ↓
LLM: "Gubernur Daerah Istimewa Yogyakarta yang menandatangani SK..."
```

---

## ✅ Checklist Pemahaman

Jika sudah mengerti yang ini, berarti sudah paham alurnya:

- [ ] Upload PDF → Extract → Chunk → Embed → Store (3 tempat)
- [ ] Query → Search chunks → Build prompt → Call LLM → Return answer
- [ ] PostgreSQL untuk data, Qdrant untuk vectors, RAG untuk relations
- [ ] FastAPI server sebagai hub dari semua komponen
- [ ] Frontend komunikasi via HTTP request/response

---

## 🎯 Kesimpulan

RAG_Anything adalah sistem yang:

1. **Menerima PDF** (upload)
2. **Mengolah PDF** (extract text, split, embed)
3. **Menyimpan data** (PostgreSQL, Qdrant, RAG)
4. **Mencari informasi** (vector search + relation matching)
5. **Generate jawaban** (LLM dengan context)
6. **Tampil ke user** (HTTP response + UI)

**Semuanya terintegrasi jadi satu sistem RAG yang powerful!** 🚀

---

*Last Updated: January 5, 2026*
