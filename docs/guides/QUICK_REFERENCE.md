# FastAPI + React Quick Reference

## 🎯 Dalam 5 Menit

### Backend (Terminal 1)
```powershell
cd RAG_Anything
.\venv\Scripts\Activate.ps1
pip install fastapi uvicorn  # Jika belum install
python fastapi_app.py
```
✅ Backend siap di http://localhost:8000

### Frontend (Terminal 2)
```bash
npm create vite@latest rag-chatbot -- --template react
cd rag-chatbot
npm install axios
# Copy ChatBot.jsx ke src/components/ChatBot.jsx
npm run dev
```
✅ Frontend siap di http://localhost:5173

### Test
- Buka http://localhost:5173
- Upload PDF
- Tanya pertanyaan
- Done! 🎉

---

## 📚 File Reference

### Backend Files

| File | Purpose | Status |
|------|---------|--------|
| `fastapi_app.py` | Main API server | ✅ Ready |
| `FASTAPI_GUIDE.md` | Setup & endpoints doc | ✅ Ready |
| `test_fastapi.py` | Test script | ✅ Ready |

**Key Endpoints:**
```
POST   /api/upload     → Upload PDF
POST   /api/query      → Ask question
GET    /api/documents  → List docs
GET    /api/status     → System health
```

### Frontend Files

| File | Purpose | Status |
|------|---------|--------|
| `ChatBot.jsx` | React component | ✅ Ready |
| `REACT_INTEGRATION.md` | Setup & usage doc | ✅ Ready |

**Key Features:**
- 💬 Chat interface
- 📤 File upload
- 📌 Source display
- ⏱️ Performance tracking

---

## 🔧 Common Commands

### Backend
```powershell
# Run
python fastapi_app.py

# Run with reload (dev)
python -m uvicorn fastapi_app:app --reload

# Run with specific host/port
python -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8080

# Test
python test_fastapi.py
```

### Frontend
```bash
# Create project
npm create vite@latest rag-chatbot -- --template react

# Install deps
npm install
npm install axios

# Run dev
npm run dev

# Build for prod
npm run build

# Preview build
npm run preview
```

---

## 🌐 API Endpoints Cheat Sheet

### 1. Health Check
```
GET /
Response: { status: "running", version: "1.0.0" }
```

### 2. System Status
```
GET /api/status
Response: {
  status: "healthy",
  documents_count: 3,
  total_chars: 45000,
  embedding_model: "Qwen3-embedding-0.6B",
  llm_model: "OpenRouter LLM"
}
```

### 3. List Documents
```
GET /api/documents
Response: [
  {
    filename: "doc1.pdf",
    status: "completed",
    chars: 15000
  }
]
```

### 4. Upload PDF
```
POST /api/upload
Body: multipart/form-data
  - file: <PDF file>
Response: {
  filename: "doc.pdf",
  status: "completed",
  chunks: 9,
  processing_time_s: 45.2
}
```

### 5. Query
```
POST /api/query
Body: {
  "question": "apa itu?",
  "max_results": 5
}
Response: {
  question: "apa itu?",
  answer: "jawaban...",
  source_content: "...",
  search_score: 0.95,
  processing_time_ms: 3500
}
```

---

## 💻 React Code Snippets

### Basic Setup
```jsx
import ChatBot from './components/ChatBot';

function App() {
  return (
    <ChatBot apiUrl="http://localhost:8000" />
  );
}

export default App;
```

### Custom Styling
```jsx
<ChatBot 
  apiUrl="http://localhost:8000"
  theme="dark"  // Jika support
  maxMessageLength={1000}  // Jika support
/>
```

### Error Handling
```jsx
import axios from 'axios';

try {
  const response = await axios.post(
    'http://localhost:8000/api/query',
    { question: 'apa?' }
  );
  console.log(response.data);
} catch (error) {
  if (error.response?.status === 400) {
    console.log('Bad request');
  } else if (error.response?.status === 500) {
    console.log('Server error');
  }
}
```

---

## 🐛 Troubleshooting

### Backend tidak bisa akses
```
❌ Connection refused
✅ Solusi: python fastapi_app.py
```

### CORS Error di Frontend
```
❌ Access to XMLHttpRequest blocked by CORS policy
✅ Solusi: Check allow_origins di fastapi_app.py
```

### PDF upload lambat
```
⚠️ 45+ detik per file
✅ Normal: EasyOCR needs time
```

### Query response lambat
```
⚠️ >10 detik per query
✅ Solusi: 
  - First query always slow (model loading)
  - Check LightRAG workers = 2
```

### File not found
```
❌ Module not found
✅ Solusi: pip install yang missing
```

---

## 📋 Setup Checklist

### Backend
- [ ] Install dependencies (`pip install fastapi uvicorn`)
- [ ] Run backend (`python fastapi_app.py`)
- [ ] Test Swagger UI (http://localhost:8000/docs)
- [ ] Upload test PDF via /api/upload
- [ ] Query test via /api/query

### Frontend
- [ ] Create Vite project (`npm create vite...`)
- [ ] Install axios (`npm install axios`)
- [ ] Copy ChatBot.jsx
- [ ] Setup App.jsx
- [ ] Run frontend (`npm run dev`)
- [ ] Test in browser

### Integration
- [ ] Upload PDF from React
- [ ] Query documents
- [ ] Check processing times
- [ ] Verify source display

---

## ⚡ Performance Tips

### Backend
```python
# Reduce workers (faster)
os.environ["LIGHTRAG_MAX_ASYNC_WORKERS"] = "2"

# Increase workers (more concurrent)
os.environ["LIGHTRAG_MAX_ASYNC_WORKERS"] = "4"

# Skip expensive operations
await rag.ainsert(
    text,
    skip_module_relation=True,
    skip_module_entity=True,
)
```

### Frontend
```jsx
// Debounce search
const [timeout, setTimeout] = useState(null);

const handleSearch = (query) => {
  clearTimeout(timeout);
  setTimeout(
    () => performSearch(query),
    500  // Wait 500ms before search
  );
};

// Lazy load messages
const [visibleMessages, setVisibleMessages] = useState(
  messages.slice(-20)  // Only show last 20
);
```

---

## 🚀 Deployment Quick Steps

### Production Backend (Railway/Heroku)
```bash
# 1. Create requirements.txt
pip freeze > requirements.txt

# 2. Create Procfile
echo "web: uvicorn fastapi_app:app --host 0.0.0.0 --port \$PORT" > Procfile

# 3. Deploy
git push heroku main
```

### Production Frontend (Vercel/Netlify)
```bash
# 1. Build
npm run build

# 2. Deploy
vercel deploy --prod
```

---

## 📖 Documentation Links

**Backend Setup**: See `FASTAPI_GUIDE.md`
**Frontend Setup**: See `REACT_INTEGRATION.md`
**Architecture**: See `ARCHITECTURE.md`

---

## 📞 Quick Help

**Q: Backend berjalan tapi frontend tidak bisa connect?**
A: Check CORS di fastapi_app.py, pastikan `allow_origins` include frontend URL

**Q: Upload PDF gagal?**
A: Check docs/ folder exist, pastikan PDF valid

**Q: Query response kosong?**
A: Check kv_store_text_chunks.json ada isinya, verify search logic

**Q: Styling ugly?**
A: Edit `styles` object di ChatBot.jsx

---

## 📊 Status

✅ FastAPI backend ready
✅ React component ready  
✅ API endpoints ready
✅ Documentation complete

🎉 **System ready for deployment!**

---

Created: Dec 5, 2025
Status: Production-ready
