# FastAPI Backend - Penerapan & Dokumentasi

## 📋 Ringkasan

FastAPI adalah framework Python untuk membuat REST API dengan cepat dan mudah. File `fastapi_app.py` membungkus semua fungsi dari `main_openrouter.py` menjadi HTTP endpoints yang bisa diakses oleh frontend.

## 🏗️ Arsitektur

```
┌─────────────────┐
│  React Frontend │
│  (Browser)      │
└────────┬────────┘
         │ HTTP Requests
         │ (JSON)
         ▼
┌─────────────────────────────────────┐
│     FastAPI Backend                 │
│  (fastapi_app.py)                   │
├─────────────────────────────────────┤
│ • Upload PDF       (/api/upload)    │
│ • Query Documents  (/api/query)     │
│ • List Documents   (/api/documents) │
│ • Get Status       (/api/status)    │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Backend Logic                      │
│  (main_openrouter.py functions)     │
├─────────────────────────────────────┤
│ • PDF Extraction (EasyOCR)          │
│ • Text Chunking                     │
│ • LightRAG Storage                  │
│ • Keyword Search                    │
│ • LLM Response (OpenRouter)         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Data Storage                       │
│  (rag_storage/)                     │
├─────────────────────────────────────┤
│ • kv_store_text_chunks.json         │
│ • kv_store_doc_status.json          │
│ • Embeddings & Vectors              │
└─────────────────────────────────────┘
```

## 🚀 Cara Install & Run

### 1. Install FastAPI
```powershell
cd C:\Users\farha\OneDrive\Gambar\Dokumen\magang\RAG_Anything
.\venv\Scripts\Activate.ps1
pip install fastapi uvicorn
```

### 2. Run Server
```powershell
# Run dengan auto-reload (development)
python -m uvicorn fastapi_app:app --reload --host 0.0.0.0 --port 8000

# Atau langsung
python fastapi_app.py
```

Output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 3. Akses API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Disini bisa test semua endpoint langsung dari browser!

## 📡 API Endpoints

### 1. Health Check
```
GET /
```
**Response:**
```json
{
  "status": "running",
  "message": "RAG Anything API is running",
  "version": "1.0.0"
}
```

### 2. Get System Status
```
GET /api/status
```
**Response:**
```json
{
  "status": "healthy",
  "documents_count": 3,
  "total_chars": 45000,
  "last_ingest": "2025-12-05T14:30:00",
  "embedding_model": "Qwen3-embedding-0.6B",
  "llm_model": "OpenRouter LLM"
}
```

### 3. List Documents
```
GET /api/documents
```
**Response:**
```json
[
  {
    "filename": "dokumen1.pdf",
    "status": "completed",
    "timestamp": "1733399400.123",
    "chars": 15000
  },
  {
    "filename": "dokumen2.pdf",
    "status": "completed",
    "timestamp": "1733399500.456",
    "chars": 20000
  }
]
```

### 4. Upload & Ingest PDF
```
POST /api/upload
Content-Type: multipart/form-data

Body: file (PDF file)
```
**Response:**
```json
{
  "filename": "dokumen1.pdf",
  "status": "completed",
  "message": "File berhasil diingest: 9 chunks",
  "processing_time_s": 45.23,
  "chunks": 9,
  "chars": 15000
}
```

### 5. Query Documents
```
POST /api/query
Content-Type: application/json

Body:
{
  "question": "apa isi bagian menimbang poin e?",
  "max_results": 5
}
```
**Response:**
```json
{
  "question": "apa isi bagian menimbang poin e?",
  "answer": "Poin e dalam bagian menimbang membahas tentang...",
  "source_content": "poin e. [excerpt dari dokumen]...",
  "search_score": 0.95,
  "processing_time_ms": 3500.0
}
```

## 💻 Contoh Penggunaan dari Frontend (React)

### Menggunakan Fetch API

```javascript
// 1. Upload PDF
async function uploadPDF(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('http://localhost:8000/api/upload', {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  console.log('Upload result:', result);
}

// 2. Query Documents
async function askQuestion(question) {
  const response = await fetch('http://localhost:8000/api/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      question: question,
      max_results: 5
    })
  });
  
  const result = await response.json();
  return result;
}

// 3. Get System Status
async function getStatus() {
  const response = await fetch('http://localhost:8000/api/status');
  const status = await response.json();
  return status;
}

// 4. List Documents
async function listDocuments() {
  const response = await fetch('http://localhost:8000/api/documents');
  const docs = await response.json();
  return docs;
}
```

### Menggunakan Axios (Alternative)

```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

// Query
const response = await axios.post(`${API_BASE}/api/query`, {
  question: 'apa itu?',
  max_results: 5
});

console.log(response.data.answer);
```

## 🔑 Poin Penting Penerapan

### 1. **CORS (Cross-Origin Requests)**
FastAPI sudah dikonfigurasi untuk menerima requests dari frontend manapun:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Di production: ganti dengan domain spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. **Request/Response Format (JSON)**
- Frontend **SEND** JSON via HTTP POST
- Backend **MENERIMA** JSON, parse ke Pydantic models
- Backend **RETURN** JSON dengan struktur yang jelas

Contoh:
```
Frontend: POST /api/query + {"question": "apa itu?"}
         ↓
Backend: Parse ke QueryRequest model
         ↓
Backend: Process dengan logic dari main_openrouter.py
         ↓
Backend: Return JSON QueryResponse
         ↓
Frontend: Terima dan tampilkan di UI
```

### 3. **Async/Await**
FastAPI support async operations. Semua function yang heavy (LLM, search) pakai `async`:
```python
@app.post("/api/query")
async def query_documents(request: QueryRequest):
    # Tidak block thread, bisa handle multiple requests bersamaan
    results = await search_similar_optimized(request.question, rag_instance)
    answer = await llm_model_func_openrouter(...)
```

### 4. **Error Handling**
Backend return HTTP error codes yang standard:
```python
if not request.question.strip():
    raise HTTPException(status_code=400, detail="Question tidak boleh kosong")
    # Return 400 Bad Request

raise HTTPException(status_code=500, detail=str(e))
# Return 500 Internal Server Error
```

Frontend bisa check status code dan handle accordingly.

### 5. **Global RAG Instance**
RAG diinisialisasi SEKALI saat startup, bukan setiap request:
```python
rag_instance = None

@app.on_event("startup")
async def startup_event():
    global rag_instance
    rag_instance = initialize_rag()  # Dipanggil 1x saja
```

Ini efficient dan cepat!

## 📊 Flow Lengkap Chat Interface

```
┌─ User Upload PDF ─┐
│                   │
│  Browser          │  POST /api/upload
│  ┌─────────────┐  │  (file + multipart)
│  │ [Upload]    ├──┼──────────────────→
│  └─────────────┘  │                    ↓
│                   │              Backend proses OCR
│                   │              Chunk text
│                   │              Embed & store
│                   │              ↓
│                   │  Return 200 OK
│  ← status: "completed"  {"chunks": 9, "chars": 15000}
│  ✓ File diingested
│
└─ User Ask Question ─┐
│                     │
│  Browser            │  POST /api/query
│  ┌─────────────┐    │  {"question": "apa itu?"}
│  │ [Type Q]    ├────┼──────────────────→
│  │ [Send]      │    │                    ↓
│  └─────────────┘    │              Backend search keywords
│                     │              Find related chunks
│                     │              Get LLM response
│                     │              ↓
│  Display answer     │  Return 200 OK
│  ← {"answer": "...", "score": 0.95}
│  ✓ Answer tampil
│
```

## 🎯 Next Steps untuk Frontend

Setelah FastAPI running, frontend perlu:

1. **Chat Component**
   - Input field untuk pertanyaan
   - Display untuk jawaban
   - File upload button untuk PDF

2. **API Integration**
   - useEffect hook untuk call `/api/documents` saat load
   - onClick handler untuk `/api/upload`
   - onClick handler untuk `/api/query`

3. **UI State Management**
   - Loading states (searching..., generating...)
   - Error handling
   - Message history

4. **Display Context**
   - Show source content (dari `source_content` field)
   - Show confidence score (dari `search_score`)
   - Show processing time

## 🔧 Troubleshooting

### API tidak bisa diakses
```
❌ Connection refused
→ Pastikan server running: python fastapi_app.py
→ Check port 8000 tidak dipakai: netstat -ano | findstr 8000
```

### PDF tidak ter-extract
```
❌ Text too short atau No text extracted
→ Cek file PDF valid
→ Cek EasyOCR bisa run (test di main_openrouter.py dulu)
```

### Query response lambat
```
⚠️ >10s response time
→ Check embedding model loading (first query selalu lambat)
→ Check LightRAG worker count (set ke 2 sudah optimal)
```

### CORS Error dari frontend
```
❌ Access to XMLHttpRequest blocked by CORS policy
→ Ganti allow_origins["*"] ke domain spesifik
→ Atau test dengan extension seperti "Allow CORS" di dev
```

## 📝 Config untuk Production

Sebelum deploy ke production:

1. **Disable reload mode**
   ```python
   # Development
   uvicorn.run(..., reload=True)
   
   # Production
   uvicorn.run(..., reload=False)
   ```

2. **Specific CORS origins**
   ```python
   allow_origins=[
       "http://localhost:3000",      # Local React dev
       "https://yourdomain.com",     # Production frontend
   ]
   ```

3. **Environment variables**
   - Store API keys di `.env`
   - Load dengan `load_dotenv()`
   - Jangan hardcode secrets

4. **Logging & Monitoring**
   - Setup proper logging untuk production
   - Monitor error rates
   - Track API response times

5. **Docker**
   ```dockerfile
   FROM python:3.10
   WORKDIR /app
   COPY . .
   RUN pip install -r requirements.txt
   CMD ["python", "fastapi_app.py"]
   ```

## 📚 Sumber Belajar

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Uvicorn**: https://www.uvicorn.org/
- **Pydantic Models**: https://docs.pydantic.dev/
- **HTTP Status Codes**: https://httpwg.org/specs/rfc9110.html

---

**Status**: ✅ FastAPI ready to use!  
**Next**: Build React frontend untuk connect ke API ini
