# React Frontend Integration Guide

## 📋 Ringkasan

File `ChatBot.jsx` adalah React component yang siap pakai untuk connect ke FastAPI backend. Component ini mengimplementasikan ChatPDF-style interface dengan fitur:

- 💬 Chat interface yang user-friendly
- 📤 PDF upload dengan drag-drop
- 🔍 Query dengan instant response
- 📌 Source content display
- ⏱️ Processing time tracking
- 📊 System status monitoring

## 🚀 Setup React Project

### 1. Create React App (atau Vite)

```bash
# Menggunakan Vite (lebih cepat)
npm create vite@latest rag-chatbot -- --template react
cd rag-chatbot
npm install

# Atau Create React App
npx create-react-app rag-chatbot
cd rag-chatbot
```

### 2. Install Dependencies

```bash
npm install axios
```

### 3. Setup Structure

```
rag-chatbot/
├── src/
│   ├── components/
│   │   └── ChatBot.jsx          ← Copy dari sini
│   ├── App.jsx
│   ├── App.css
│   └── index.js
├── package.json
└── .env
```

### 4. Buat `.env` File (Optional, untuk konfigurasi)

```
REACT_APP_API_URL=http://localhost:8000
```

## 💻 Implementasi

### Cara 1: Direct Import

**App.jsx:**
```jsx
import ChatBot from './components/ChatBot';

function App() {
  return (
    <ChatBot apiUrl="http://localhost:8000" />
  );
}

export default App;
```

**App.css:**
```css
body {
  margin: 0;
  padding: 0;
}

#root {
  width: 100%;
  height: 100vh;
}
```

**index.js:**
```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### Cara 2: Dengan Layout (Header + Sidebar)

```jsx
import React from 'react';
import ChatBot from './components/ChatBot';

function App() {
  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      {/* Sidebar */}
      <aside style={{ width: '250px', backgroundColor: '#f5f5f5', padding: '20px' }}>
        <h3>📚 Info</h3>
        <ul>
          <li>Sistem: RAG Anything</li>
          <li>Backend: FastAPI + LightRAG</li>
          <li>Status: ✓ Online</li>
        </ul>
      </aside>

      {/* Main Chat */}
      <main style={{ flex: 1 }}>
        <ChatBot apiUrl={process.env.REACT_APP_API_URL || 'http://localhost:8000'} />
      </main>
    </div>
  );
}

export default App;
```

## 🏃 Run Development Server

```bash
# Terminal 1: Backend FastAPI
cd RAG_Anything
.\venv\Scripts\Activate.ps1
python fastapi_app.py
# Output: Uvicorn running on http://0.0.0.0:8000

# Terminal 2: Frontend React
cd rag-chatbot
npm start
# Output: Listening on http://localhost:3000
```

Buka browser: **http://localhost:3000**

## 🎨 Component Props

```jsx
<ChatBot 
  apiUrl="http://localhost:8000"  // Backend URL (required)
/>
```

## 📱 Component Features

### Auto-Features (Built-in)

✅ **Message History** - Semua pesan tersimpan dalam state
✅ **Auto Scroll** - Scroll ke message terbaru
✅ **File Upload** - Drag-drop support (need add)
✅ **Status Bar** - Show doc count, total size, model
✅ **Loading State** - Spinner saat tunggu response
✅ **Error Handling** - Display error messages dengan baik
✅ **Auto Refresh** - Refresh status setiap 5 detik

### Customization Options

#### Ubah Color Scheme

Di `ChatBot.jsx`, find `styles` object dan edit:

```jsx
const styles = {
  header: {
    backgroundColor: '#1976D2',  // Ubah warna header
  },
  message_user: {
    backgroundColor: '#1976D2',  // Ubah user message color
  },
  message_bot: {
    backgroundColor: '#f5f5f5',  // Ubah bot message color
  },
  // ...
};
```

#### Ubah Font/Size

```jsx
const styles = {
  container: {
    fontFamily: "'Courier New', monospace",  // Ubah font
  },
  title: {
    fontSize: '32px',  // Ubah title size
  },
  // ...
};
```

#### Tambah Custom Buttons

```jsx
<div style={styles.inputArea}>
  <button onClick={handleClearHistory}>🗑️ Clear History</button>
  <button onClick={handleExport}>📥 Export Chat</button>
  {/* ... existing upload/input ... */}
</div>
```

## 🔗 API Integration Details

### How Request/Response Works

```
User: [Input "apa itu?"] → Click Send
         ↓
React: Create fetch request
         ↓
POST /api/query
{
  "question": "apa itu?",
  "max_results": 5
}
         ↓
FastAPI: Process request
         ↓
Python: Search chunks + LLM response
         ↓
FastAPI: Return JSON
{
  "question": "apa itu?",
  "answer": "jawaban...",
  "source_content": "...",
  "search_score": 0.95,
  "processing_time_ms": 3500
}
         ↓
React: Receive response
         ↓
Add message to state
         ↓
Display in chat UI
```

### Error Handling

Component sudah handle common errors:

```javascript
try {
  // API call
  const response = await axios.post(...);
  // Process response
} catch (error) {
  // Handle error
  const errorMessage = {
    type: 'error',
    content: `Error: ${error.response?.data?.detail || error.message}`
  };
  setMessages(prev => [...prev, errorMessage]);
}
```

Status codes:
- `200` - Success
- `400` - Bad request (invalid query)
- `500` - Server error (LightRAG crash)

## 🚀 Advanced Features (Optional)

### 1. Real-Time Streaming

Untuk streaming response (partial answer):

```jsx
// Ganti axios dengan fetch untuk streaming
const response = await fetch(`${apiUrl}/api/query`, {
  method: 'POST',
  body: JSON.stringify(payload),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  // Update message with chunk (streaming effect)
}
```

### 2. Dark Mode

```jsx
const [darkMode, setDarkMode] = useState(false);

const getStyles = () => ({
  container: {
    backgroundColor: darkMode ? '#1e1e1e' : '#f5f5f5',
    color: darkMode ? '#fff' : '#000',
  },
  // ... apply darkMode condition to all styles
});
```

### 3. Message Export

```jsx
const handleExportChat = () => {
  const chatText = messages
    .map(m => `${m.type.toUpperCase()}: ${m.content}`)
    .join('\n\n');
  
  const element = document.createElement('a');
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(chatText));
  element.setAttribute('download', `chat_${new Date().getTime()}.txt`);
  element.click();
};
```

### 4. Document Preview

```jsx
// Dalam sourceDetails:
<div style={styles.sourcePreview}>
  <iframe
    src={`https://docs.google.com/viewer?url=${documentUrl}&embedded=true`}
    style={{ width: '100%', height: '300px' }}
  />
</div>
```

## 🧪 Testing

### Manual Test Checklist

- [ ] Upload PDF → Message muncul
- [ ] Query dengan dokumen kosong → Error message
- [ ] Query dengan dokumen → Answer muncul
- [ ] Click source → Show content
- [ ] Refresh page → History hilang (normal, state-based)
- [ ] Multiple queries → All messages visible
- [ ] Long answer → Text wrap properly
- [ ] Slow network → Loading spinner show

### Unit Test (Jest + React Testing Library)

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatBot from './ChatBot';

describe('ChatBot Component', () => {
  test('renders upload button', () => {
    render(<ChatBot apiUrl="http://localhost:8000" />);
    expect(screen.getByText('📤 Upload PDF')).toBeInTheDocument();
  });

  test('sends query on button click', async () => {
    render(<ChatBot apiUrl="http://localhost:8000" />);
    
    const input = screen.getByPlaceholderText(/Tanyakan/);
    fireEvent.change(input, { target: { value: 'test question' } });
    fireEvent.click(screen.getByText('➤'));
    
    await waitFor(() => {
      expect(screen.getByText('test question')).toBeInTheDocument();
    });
  });
});
```

## 📦 Build for Production

```bash
# Optimize bundle
npm run build

# Output di build/ folder
# Static files siap di-deploy ke Vercel, Netlify, etc.

# Deployment ke Vercel:
npm install -g vercel
vercel deploy
```

## ⚠️ Important Notes

### 1. CORS Issue

Jika dapat error `CORS policy blocked`:

**Backend (fastapi_app.py):**
```python
# Development: allow semua
allow_origins=["*"]

# Production: specify domain
allow_origins=[
    "https://yourdomain.com",
    "https://app.yourdomain.com"
]
```

### 2. API URL Configuration

**Development:**
```jsx
const API_URL = 'http://localhost:8000';
```

**Production:**
```jsx
const API_URL = process.env.REACT_APP_API_URL || 'https://api.yourdomain.com';
```

### 3. Session Persistence

Current component TIDAK menyimpan message history. Untuk persistent chat:

```jsx
// Save ke localStorage
useEffect(() => {
  localStorage.setItem('chatHistory', JSON.stringify(messages));
}, [messages]);

// Load dari localStorage
useEffect(() => {
  const saved = localStorage.getItem('chatHistory');
  if (saved) setMessages(JSON.parse(saved));
}, []);
```

### 4. Authentication (Optional)

Jika backend perlu auth:

```jsx
const response = await axios.post(
  `${apiUrl}/api/query`,
  payload,
  {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  }
);
```

## 📚 Sumber Belajar

- **React Docs**: https://react.dev/
- **Axios**: https://axios-http.com/
- **Styling with CSS-in-JS**: https://styled-components.com/
- **React Hooks**: https://react.dev/reference/react

## 🎯 Next Steps

1. ✅ FastAPI backend running
2. ✅ React component created
3. 🔲 **Setup React project** ← Next
4. 🔲 Customize styling
5. 🔲 Deploy frontend
6. 🔲 Setup production backend
7. 🔲 Add authentication
8. 🔲 Monitor & analytics

---

**Status**: ✅ Ready untuk deploy!  
**Waktu Setup**: ~15 menit  
**Difficulty**: ⭐⭐ Beginner-friendly
