# System Diagrams & Visual Guide

## 1. Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│                        CHATPDF-STYLE APPLICATION                        │
│                                                                           │
│  ┌─────────────────────────────────────┐   ┌──────────────────────────┐ │
│  │      FRONTEND (React)                │   │   BACKEND (FastAPI)      │ │
│  │      http://localhost:5173           │   │   http://localhost:8000  │ │
│  │                                      │   │                          │ │
│  │  ┌────────────────────────────────┐  │   │ ┌──────────────────────┐│ │
│  │  │     ChatBot Component          │  │   │ │   API Routes         ││ │
│  │  │                                │  │   │ │                      ││ │
│  │  │ • Header with title           │  │   │ │ GET  /               ││ │
│  │  │ • Status bar (docs, size)     │  │   │ │ GET  /api/status     ││ │
│  │  │ • Message container           │  │   │ │ GET  /api/documents  ││ │
│  │  │ • Empty state on load         │  │   │ │ POST /api/upload     ││ │
│  │  │ • Upload PDF button           │  ◄───┼─┼ POST /api/query      ││ │
│  │  │ • Message input field         │  │   │ │                      ││ │
│  │  │ • Send button                 │  │   │ └──────────────────────┘│ │
│  │  │ • Loading spinner             │  │   │                          │ │
│  │  │ • Error display               │  │   │ ┌──────────────────────┐│ │
│  │  │ • Source content details      │  │   │ │   Core Functions     ││ │
│  │  │                                │  │   │ │                      ││ │
│  │  │ Styling: CSS-in-JS            │  │   │ │ • extract_pdf()      ││ │
│  │  │ HTTP Client: Axios            │  │   │ │ • chunk_text()       ││ │
│  │  │ State: React Hooks            │  │   │ │ • search_similar()   ││ │
│  │  │                                │  │   │ │ • ingest_pdf()       ││ │
│  │  └────────────────────────────────┘  │   │ │                      ││ │
│  │                                      │   │ └──────────────────────┘│ │
│  │  Languages:                          │   │                          │ │
│  │  • JavaScript/JSX                    │   │ Languages:               │ │
│  │  • CSS-in-JS                         │   │ • Python                 │ │
│  │                                      │   │ • Async/Await            │ │
│  │  Dependencies:                       │   │                          │ │
│  │  • React 18                          │   │ Dependencies:            │ │
│  │  • Axios                             │   │ • FastAPI                │ │
│  │  • (No CSS framework)                │   │ • Uvicorn                │ │
│  │                                      │   │ • Pydantic               │ │
│  └─────────────────────────────────────┘   └──────────────────────────┘ │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │         Data Flow: HTTP + JSON                                       │ │
│  │                                                                       │ │
│  │  Frontend sends JSON request:                                       │ │
│  │  POST /api/upload                                                   │ │
│  │  Content-Type: multipart/form-data                                  │ │
│  │  Body: [PDF file bytes]                                             │ │
│  │                                                                       │ │
│  │  Backend processes & returns JSON response:                         │ │
│  │  {                                                                   │ │
│  │    "filename": "dokumen.pdf",                                       │ │
│  │    "status": "completed",                                           │ │
│  │    "chunks": 9,                                                     │ │
│  │    "processing_time_s": 45.2                                        │ │
│  │  }                                                                   │ │
│  │                                                                       │ │
│  │  Similar pattern untuk /api/query dengan JSON payload               │ │
│  │                                                                       │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │         Storage: Shared File System                                  │ │
│  │                                                                       │ │
│  │  RAG_Anything/                                                      │ │
│  │  ├── docs/                    ← Uploaded PDFs                       │ │
│  │  │   ├── dokumen1.pdf                                               │ │
│  │  │   └── dokumen2.pdf                                               │ │
│  │  │                                                                   │ │
│  │  └── rag_storage/             ← LightRAG storage                    │ │
│  │      ├── kv_store_text_chunks.json      ← All chunks                │ │
│  │      ├── kv_store_doc_status.json       ← Upload status             │ │
│  │      ├── kv_store_full_docs.json        ← Original docs             │ │
│  │      ├── vdb_chunks.json                ← Embeddings                │ │
│  │      └── [Other LightRAG files]                                     │ │
│  │                                                                       │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Request/Response Flow Diagram

### Upload PDF Flow

```
┌─────────────────┐
│  USER           │
│                 │
│ 1. Click upload │
│ 2. Select PDF   │
│ 3. Submit       │
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  FRONTEND (React/ChatBot.jsx)       │
│                                     │
│ • Get file from input               │
│ • Create FormData object            │
│ • Show loading spinner              │
│                                     │
│ axios.post('/api/upload')           │
│ Body: FormData with file            │
└────────┬────────────────────────────┘
         │
         │  HTTP POST multipart/form-data
         │  Content-Type: multipart/form-data
         │
         ▼
┌─────────────────────────────────────┐
│  BACKEND (FastAPI/fastapi_app.py)   │
│                                     │
│ @app.post("/api/upload")            │
│ • Receive file                      │
│ • Save to disk                      │
│ • Validate PDF                      │
│                                     │
│ ↓ await ingest_pdf()                │
│                                     │
│ ├─ extract_pdf()                    │
│ │  └─ EasyOCR extraction (~40s)    │
│ │                                   │
│ ├─ chunk_text()                     │
│ │  └─ Split into ~9 chunks         │
│ │                                   │
│ ├─ rag.ainsert()                    │
│ │  └─ Embed & store (~3s)          │
│ │                                   │
│ └─ Save status to JSON              │
│                                     │
│ Return JSON response                │
└────────┬────────────────────────────┘
         │
         │  HTTP 200 OK + JSON
         │  {
         │    "status": "completed",
         │    "chunks": 9,
         │    "processing_time_s": 45.2
         │  }
         │
         ▼
┌─────────────────────────────────────┐
│  FRONTEND (React/ChatBot.jsx)       │
│                                     │
│ • Hide spinner                      │
│ • Add success message to chat       │
│ • Reload documents list             │
│ • Refresh status bar                │
│ • Enable query input                │
│                                     │
│ Display: "✓ File uploaded: 9 chunks"│
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  USER           │
│                 │
│ Sees success    │
│ Can now ask     │
│ questions       │
│                 │
└─────────────────┘
```

### Query Flow

```
┌─────────────────┐
│  USER           │
│                 │
│ 1. Type Q: ?    │
│ 2. Click send   │
│                 │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  FRONTEND (React)                        │
│                                          │
│ • Get question text                      │
│ • Clear input field                      │
│ • Add user message to chat               │
│ • Show loading spinner                   │
│                                          │
│ axios.post('/api/query')                 │
│ Body: { question: "...", max_results: 5 }
└────────┬─────────────────────────────────┘
         │
         │  HTTP POST application/json
         │  {
         │    "question": "apa itu?",
         │    "max_results": 5
         │  }
         │
         ▼
┌──────────────────────────────────────────┐
│  BACKEND (FastAPI)                       │
│                                          │
│ @app.post("/api/query")                  │
│ • Validate request                       │
│                                          │
│ ↓ search_similar_optimized()             │
│ • Load chunks from JSON                  │
│ • Keyword matching                       │
│ • Score relevant chunks                  │
│ • Combine related chunks (~0.5s)        │
│                                          │
│ ↓ llm_model_func_openrouter()            │
│ • Create system prompt                   │
│ • Create query prompt with context       │
│ • Send to OpenRouter API                 │
│ • Get LLM response (~2-3s)              │
│                                          │
│ • Format response                        │
│ • Calculate processing time              │
│                                          │
│ Return JSON response                     │
└────────┬─────────────────────────────────┘
         │
         │  HTTP 200 OK + JSON
         │  {
         │    "question": "apa itu?",
         │    "answer": "jawaban...",
         │    "source_content": "...",
         │    "search_score": 0.95,
         │    "processing_time_ms": 3500
         │  }
         │
         ▼
┌──────────────────────────────────────────┐
│  FRONTEND (React)                        │
│                                          │
│ • Hide spinner                           │
│ • Add bot message to chat                │
│ • Display answer                         │
│ • Show source in <details> element       │
│ • Show search score & processing time    │
│                                          │
│ User sees in chat:                       │
│ ┌─────────────────────────────────────┐  │
│ │ You: apa itu?                       │  │
│ ├─────────────────────────────────────┤  │
│ │ Bot: jawaban lengkap...             │  │
│ │                                     │  │
│ │ 📌 Sumber (Score: 0.95)             │  │
│ │   [Click to expand]                 │  │
│ │ ⏱️ 3500ms                            │  │
│ └─────────────────────────────────────┘  │
│                                          │
│ Ready for next question                  │
└──────────────────────────────────────────┘
```

---

## 3. Component Interaction Diagram

```
┌──────────────────────────────────────────────────────┐
│                ChatBot Component                     │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ Header Section                                 │ │
│  │ • Title: "📄 RAG ChatBot"                      │ │
│  │ • Subtitle: "Chat dengan dokumen Anda"        │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ Status Bar                                     │ │
│  │ • 📁 Dokumen: 3                                │ │
│  │ • 💾 Total: 45KB                               │ │
│  │ • 🔧 Model: Qwen                               │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ Messages Container (Scroll)                    │ │
│  │                                                │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ Empty State (Initial Load)                │ │ │
│  │  │ "👋 Upload dokumen atau mulai tanya!"   │ │ │
│  │  │ [List of available documents]             │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  │                                                │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ User Message (Blue, Right)                │ │ │
│  │  │ "You: apa itu?"                          │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  │                                                │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ Loading Indicator (Centered)              │ │ │
│  │  │ "[spinning] Mencari jawaban..."          │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  │                                                │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ Bot Message (White, Left)                 │ │ │
│  │  │ "Bot: jawaban lengkap..."                │ │ │
│  │  │                                           │ │ │
│  │  │ 📌 Sumber (Score: 0.95)                  │ │ │
│  │  │ [Expandable source content]               │ │ │
│  │  │ ⏱️ 3500ms                                 │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  │                                                │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ System Message (Green, Center)            │ │ │
│  │  │ "✓ File uploaded: 9 chunks"              │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  │                                                │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ Error Message (Red, Left)                 │ │ │
│  │  │ "✗ Error: Something went wrong"          │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  │                                                │ │
│  │  [Auto-scroll to bottom]                      │ │
│  │                                                │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ Input Area                                     │ │
│  │                                                │ │
│  │  ┌────────────────────────────────────────┐  │ │
│  │  │ [hidden file input]                    │  │ │
│  │  │ [📤 Upload PDF] [Status]               │  │ │
│  │  └────────────────────────────────────────┘  │ │
│  │                                                │ │
│  │  ┌────────────────────────────────────────┐  │ │
│  │  │ [Type message here...] [Send ➤]       │  │ │
│  │  └────────────────────────────────────────┘  │ │
│  │                                                │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack Layers

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│                    UI LAYER                        │
│            ┌───────────────────────┐               │
│            │   React Components    │               │
│            │ • ChatBot.jsx         │               │
│            │ • Message Display     │               │
│            │ • File Upload         │               │
│            └───────────────────────┘               │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│                STYLING & STATE                     │
│      ┌────────────────────────────────────┐        │
│      │ CSS-in-JS       React Hooks        │        │
│      │ • styles object • useState         │        │
│      │ • Responsive    • useEffect        │        │
│      │ • Animations    • useRef           │        │
│      └────────────────────────────────────┘        │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│                HTTP & API LAYER                    │
│         ┌────────────────────────────────┐         │
│         │ Axios HTTP Client              │         │
│         │ • POST /api/upload             │         │
│         │ • POST /api/query              │         │
│         │ • GET /api/documents           │         │
│         │ • GET /api/status              │         │
│         └────────────────────────────────┘         │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│              FASTAPI BACKEND LAYER                 │
│        ┌──────────────────────────────────┐        │
│        │ FastAPI Framework                │        │
│        │ • Route decorators               │        │
│        │ • Pydantic models                │        │
│        │ • Async handlers                 │        │
│        │ • Error handling                 │        │
│        └──────────────────────────────────┘        │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│           BUSINESS LOGIC LAYER                     │
│    ┌────────────────────────────────────────┐      │
│    │ From main_openrouter.py                │      │
│    │ • extract_pdf()                        │      │
│    │ • chunk_text()                         │      │
│    │ • search_similar_optimized()           │      │
│    │ • ingest_pdf()                         │      │
│    └────────────────────────────────────────┘      │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│          EXTERNAL SERVICES LAYER                   │
│   ┌─────────────────────────────────────────┐      │
│   │ EasyOCR      │ LightRAG │ OpenRouter    │      │
│   │ PDF extract  │ Storage  │ LLM API       │      │
│   │ GPU accel    │ Search   │ Response gen  │      │
│   └─────────────────────────────────────────┘      │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│               DATA STORAGE LAYER                   │
│         ┌────────────────────────────────┐         │
│         │ File System                    │         │
│         │ • docs/          [PDF files]   │         │
│         │ • rag_storage/   [Embeddings]  │         │
│         │ • kv_store_*.json [Chunks]     │         │
│         └────────────────────────────────┘         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 5. State Management Flow

```
ChatBot Component State:

┌─────────────────────────────────────────┐
│ messages: Message[]                      │
│ - Stored in React state                 │
│ - Each message has: id, type, content   │
│ - Types: user, bot, system, error       │
│ - Not persisted (lost on refresh)       │
│ - Updated on upload/query response      │
└─────────────────────────────────────────┘
         │
         ├─→ Display in messagesContainer
         ├─→ Auto-scroll to bottom
         └─→ Update on each interaction
                  │
                  ▼
         ┌─────────────────────────────────┐
         │ loading: boolean                │
         │ - Show spinner during request   │
         │ - Disable send button           │
         │ - Disable upload button         │
         └─────────────────────────────────┘
                  │
                  ▼
         ┌─────────────────────────────────┐
         │ documents: DocumentInfo[]       │
         │ - Fetched from GET /api/docs    │
         │ - Updated on upload             │
         │ - Displayed in empty state      │
         └─────────────────────────────────┘
                  │
                  ▼
         ┌─────────────────────────────────┐
         │ uploading: boolean              │
         │ - Show loading on upload btn    │
         │ - Disable file input            │
         │ - Disable submit during upload  │
         └─────────────────────────────────┘
                  │
                  ▼
         ┌─────────────────────────────────┐
         │ systemStatus: SystemStatus      │
         │ - Docs count                    │
         │ - Total chars                   │
         │ - Last ingest time              │
         │ - Models used                   │
         │ - Auto refresh setiap 5s        │
         └─────────────────────────────────┘
```

---

## 6. Error Handling Flow

```
┌─ API Call ─────────────────────┐
│                                 │
│  axios.post(...) atau           │
│  fetch(...) Request             │
│                                 │
└────────────┬────────────────────┘
             │
             ▼
      ┌─────────────────────────┐
      │ Response received?      │
      └──────┬────────────┬──────┘
             │ Yes        │ No
             ▼            ▼
      ┌──────────────┐  ┌──────────────────────┐
      │ Check status │  │ Network Error        │
      │ code         │  │ • Connection refused │
      └──┬──────┬────┘  │ • CORS blocked       │
         │      │       │ • Timeout            │
         │      └─────┐ └──────────────────────┘
         │            │
    200-299      400-599
         │            │
         ▼            ▼
    ┌────────────┐  ┌──────────────────┐
    │ Success    │  │ Error Response   │
    │ Process    │  │ • 400: Bad req   │
    │ response   │  │ • 401: Unauth    │
    │ Add msg    │  │ • 500: Server    │
    │ to chat    │  │ • Extract detail │
    │ Hide loader│  │ Show error msg   │
    │ Enable     │  │ in chat (red)    │
    │ input      │  │ Log to console   │
    └────────────┘  └──────────────────┘
         │                    │
         └────────┬───────────┘
                  │
                  ▼
          ┌─────────────────────┐
          │ Chat Ready          │
          │ User dapat          │
          │ interact again      │
          └─────────────────────┘
```

---

**Diagrams Created**: 6
**Coverage**: Full system architecture, request flows, components, layers, state management, error handling

Visual guide lengkap untuk memahami bagaimana sistem bekerja! 📊
