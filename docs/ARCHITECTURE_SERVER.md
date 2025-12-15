# RAG Chatbot Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WEB BROWSER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ PDF History  │  │ PDF Viewer   │  │ Chat Panel   │          │
│  │ (Left)       │  │ (Center)     │  │ (Right)      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
         ↑                    ↓                    ↑
         │       HTTP REST API (/static, /api)    │
         └────────────────────┬────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  FastAPI Server   │
                    │ (main_server.py)  │
                    │                   │
                    │ Routes:           │
                    │ - GET /          │ ← Serves UI (index.html)
                    │ - POST /upload   │ ← Upload PDF
                    │ - GET /sessions  │ ← List PDFs
                    │ - POST /query    │ ← Ask question
                    │ - DELETE /...    │ ← Delete PDF
                    │ - GET /health    │ ← Server status
                    └────┬────────┬────┘
                         │        │
        ┌────────────────┘        └───────────────┐
        │                                         │
        ▼                                         ▼
┌──────────────────────┐              ┌──────────────────────┐
│   Core RAG Logic     │              │   Storage Layer      │
│                      │              │                      │
│ • extract_text()    │              │ rag_storage/         │
│ • search_chunks()   │              │ pdf_sessions/        │
│ • LightRAG          │              │                      │
│ • Embedding Model   │              │ folder_1/            │
│ • LLM Integration   │              │ ├─ metadata.json     │
│                      │              │ ├─ original.pdf      │
│ From:               │              │ └─ rag_storage/      │
│ • main_openrouter.py│              │                      │
│ • embedding_qwen.py │              │ folder_2/            │
│ • llm_openrouter.py │              │ └─ (same structure) │
│                      │              │                      │
└──────────────────────┘              └──────────────────────┘
        ↑                                         ↑
        │ Uses                                   │ Stores/Reads
        └───────────────────────┬────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   External Services   │
                    │                       │
                    │ • OpenRouter API      │ ← LLM (Llama 3.1)
                    │   (llm_model_func)    │
                    │                       │
                    │ • EasyOCR             │ ← Text extraction
                    │ • PDF2Image           │ ← PDF processing
                    │ • HuggingFace         │ ← Qwen embedding
                    └───────────────────────┘
```

## Data Flow - PDF Upload

```
User Upload
    │
    ▼
┌─────────────────────┐
│  Upload Modal       │
│  (Drag-drop/Click)  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  POST /api/upload   │
│  (FastAPI endpoint) │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 1. Create session folder (folder_N)     │
│ 2. Save metadata.json                   │
│ 3. Save original PDF                    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Background Task: ingest_pdf_async()      │
└──────┬───────────────────────────────────┘
       │
       ├─► extract_text_from_pdf_with_ocr() ─► EasyOCR (8 workers @ DPI=120)
       │   Time: 35-40s
       │
       ├─► LightRAG.ainsert(text) ────────────► LightRAG processing
       │   Time: 10-15s
       │   - Entity extraction (LLM)
       │   - Relation extraction (LLM)
       │   - Chunk embedding (Qwen)
       │   - Graph construction
       │
       └─► Update metadata.json (status="ready")
           Time: <1s
           Total: 50-55s ✅
```

## Data Flow - User Query

```
User Question (Text)
    │
    ▼
┌──────────────────┐
│  Chat Input      │
│  Send Button     │
└──────┬───────────┘
       │
       ▼
┌────────────────────────────┐
│ POST /api/query            │
│ session_id + question      │
└──────┬─────────────────────┘
       │
       ├─► search_chunks() ──────────────┐
       │   Semantic similarity search     │
       │   Time: 1-2s                    │
       │   Query embedding: Qwen model   │
       │   Return top-k relevant chunks  │
       │                                  │
       ├─► LightRAG.aquery() ───────────┐
       │   Augmented generation          │
       │   Time: 2-5s                    │
       │   LLM: Llama 3.1 8B (OpenRouter)│
       │   Prompt: Question + Context    │
       │                                  │
       └─► Return Answer ────────────────┐
           Total: 3-7s ✅                │
           │
           ▼
       JSON Response
       {
         "answer": "...",
         "timing": {...}
       }
           │
           ▼
    Update UI Chat Message
    (Auto-scroll, timestamp)
```

## State Management

```
┌──────────────────────────────────────┐
│     Frontend State (app.js)           │
├──────────────────────────────────────┤
│ • currentSessionId                   │ ← Active PDF
│ • isLoading                          │ ← Query in progress
│ • chatMessages []                    │ ← Message history
└──────────────────────────────────────┘
         ↕ (Sync via HTTP)
┌──────────────────────────────────────┐
│     Backend State (main_server.py)    │
├──────────────────────────────────────┤
│ • rag_instances {}                   │ ← LightRAG per session
│ • embedding_model                    │ ← Shared (loaded once)
│ • embedding_func                     │ ← Shared (loaded once)
│ • Sessions in disk (metadata.json)   │ ← Persistent
└──────────────────────────────────────┘
         ↕ (Persist to disk)
┌──────────────────────────────────────┐
│        File System Storage             │
├──────────────────────────────────────┤
│ rag_storage/pdf_sessions/            │
│ ├─ folder_1/                         │ ← Session 1
│ │  ├─ metadata.json                  │   (pdf name, status)
│ │  ├─ original.pdf                   │   (original file)
│ │  └─ rag_storage/                   │   (LightRAG data)
│ ├─ folder_2/                         │ ← Session 2
│ │  └─ (same structure)               │   (isolated)
│ └─ ...                               │
└──────────────────────────────────────┘
```

## Session Isolation

```
Session 1 (folder_1)          Session 2 (folder_2)
┌─────────────────────┐       ┌─────────────────────┐
│ PDF: report.pdf     │       │ PDF: article.pdf    │
├─────────────────────┤       ├─────────────────────┤
│ RAG Instance #1     │       │ RAG Instance #2     │
│ ├─ Entity graph     │       │ ├─ Entity graph     │
│ ├─ Embeddings       │       │ ├─ Embeddings       │
│ ├─ Chunks           │       │ ├─ Chunks           │
│ └─ Relations        │       │ └─ Relations        │
└─────────────────────┘       └─────────────────────┘
         ↕                              ↕
  Isolated Context            Isolated Context

User switches between sessions:
• Only ONE RAG instance active at a time
• Context fully isolated (no cross-contamination)
• Each PDF has own embedding space
• Quick switching (instant, no reload)
```

## Deployment Architecture

```
Development
┌────────────────────────────────────┐
│  localhost:8000                    │
│  ├─ main_server.py (FastAPI)       │
│  └─ ui/ (Static files)             │
│                                    │
│  Storage: ./rag_storage/           │
│  Config: .env                      │
└────────────────────────────────────┘

Production (Future)
┌────────────────────────────────────┐
│  Docker Container                  │
│  ├─ FastAPI app                    │
│  ├─ Uvicorn server                 │
│  └─ Static files                   │
│                                    │
│  Volume Mounts:                    │
│  ├─ /app/rag_storage (persistent)  │
│  └─ /app/.env (config)             │
└────────────────────────────────────┘
         ↕
┌────────────────────────────────────┐
│  Reverse Proxy (nginx)             │
│  ├─ SSL/TLS                        │
│  ├─ Rate limiting                  │
│  └─ Load balancing                 │
└────────────────────────────────────┘
         ↕
┌────────────────────────────────────┐
│  External Services                 │
│  ├─ OpenRouter API (LLM)           │
│  └─ HuggingFace Hub (embeddings)   │
└────────────────────────────────────┘
```

## Component Dependencies

```
main_server.py (FastAPI)
    │
    ├─ imports: FastAPI, Uvicorn
    │
    ├─ imports: embedding_qwen.py
    │   └─ loads: Qwen embedding model
    │
    ├─ imports: llm_openrouter.py
    │   └─ uses: OpenRouter API (LLM)
    │
    ├─ imports: main_openrouter.py
    │   ├─ extract_text_from_pdf_with_ocr()
    │   ├─ search_chunks()
    │   └─ uses: EasyOCR, PDF2Image
    │
    ├─ imports: lightrag
    │   ├─ Entity extraction
    │   ├─ Relation extraction
    │   ├─ Knowledge graph
    │   └─ Semantic search
    │
    └─ imports: ui/ (static files)
        ├─ index.html
        ├─ css/style.css
        └─ js/app.js (Fetch API → server)
```

## Performance Characteristics

```
Resource Usage Over Time (6-page PDF)

RAM (MB)
│
├─ 500  ┌────── Embedding model (persistent)
│       │
├─ 300  │  ┌─── OCR processing peak
│       │  │
├─ 200  │  │  ┌─ LightRAG processing
│       │  │  │
├─ 100  │  │  │
│       │  │  │
├─ 0    └──┴──┴────────────────► Time
  0     10s 35s  50s
         │   │    │
         │   │    └─ Ready (stable)
         │   └────── RAG indexing (10-15s)
         └────────── OCR extraction (35-40s)

Disk Usage
folder_1/
├─ original.pdf ............................ 500KB
├─ metadata.json ........................... 1KB
└─ rag_storage/
   ├─ graph_chunk_entity_relation.graphml ... 50KB
   ├─ vdb_chunks.json ....................... 2MB (embeddings)
   ├─ vdb_entities.json ..................... 200KB
   ├─ vdb_relationships.json ................ 100KB
   ├─ kv_store_*.json ....................... 1MB
   └─ ...
   Total per PDF: 5-10MB
```

## Error Handling Flow

```
Exception Occurs
    │
    ├─► Upload Error
    │   └─► Return {"success": false, "error": "..."}
    │       Display user-friendly message
    │
    ├─► Query Error
    │   └─► Add error message to chat
    │       Show in orange/red color
    │
    ├─► Session Not Found
    │   └─► HTTP 404
    │       Redirect to empty state
    │
    └─► Server Error
        └─► HTTP 500
            Log to console
            Show spinner and retry hint
```

This diagram shows:
- Multi-layer architecture (browser → server → storage)
- Clear separation of concerns
- Data flow for upload and query
- Session isolation mechanism
- Performance characteristics
- Error handling strategy
- Deployment options

All components designed for scalability and future enhancement.
