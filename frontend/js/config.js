// ============= CONFIGURATION =============
const CONFIG = {
  API_BASE_URL: window.location.origin, // Auto-detect base URL
  WS_BASE_URL: window.location.origin.replace('http', 'ws'), // WebSocket URL
  PDF_WORKER_URL: 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js',
  MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB sesuai .env
  DEFAULT_SCALE: 1.2,
  MIN_SCALE: 0.5,
  MAX_SCALE: 3.0,
  SCALE_STEP: 0.2,
  PROCESSING_STEPS: [
    { id: 'step1', name: 'Reading PDF...', key: 'reading' },
    { id: 'step2', name: 'Analyzing content...', key: 'analyzing' },
    { id: 'step3', name: 'Creating embeddings...', key: 'embedding' },
    { id: 'step4', name: 'Ready to chat!', key: 'ready' }
  ]
};

// Global state
const STATE = {
  chatId: null,
  docId: null,
  userId: "user_" + Math.random().toString(36).substr(2, 9),
  currentPdfName: "",
  currentFileName: "",
  pdfDoc: null,
  pageNum: 1,
  pageRendering: false,
  pageNumPending: null,
  scale: CONFIG.DEFAULT_SCALE,
  isMobile: window.innerWidth <= 768,
  isProcessing: false,
  ws: null,
  // Document management
  documents: {}, // { docId: { fileName, chatId, messages: [], pdfData: null } }
};

// Document Storage Manager
const DocStorage = {
  STORAGE_KEY: 'chatpdf_documents',
  
  // Load all documents from localStorage
  loadAll() {
    try {
      const data = localStorage.getItem(this.STORAGE_KEY);
      if (data) {
        STATE.documents = JSON.parse(data);
      }
    } catch (e) {
      console.error('Error loading documents:', e);
      STATE.documents = {};
    }
  },
  
  // Save all documents to localStorage
  saveAll() {
    try {
      // Don't save pdfData to localStorage (too large)
      const docsToSave = {};
      for (const [docId, doc] of Object.entries(STATE.documents)) {
        docsToSave[docId] = {
          fileName: doc.fileName,
          chatId: doc.chatId,
          messages: doc.messages || [],
          uploadTime: doc.uploadTime
        };
      }
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(docsToSave));
    } catch (e) {
      console.error('Error saving documents:', e);
    }
  },
  
  // Add or update a document
  saveDocument(docId, fileName, chatId = null) {
    if (!STATE.documents[docId]) {
      STATE.documents[docId] = {
        fileName,
        chatId,
        messages: [],
        uploadTime: Date.now()
      };
    } else {
      STATE.documents[docId].fileName = fileName;
      if (chatId) STATE.documents[docId].chatId = chatId;
    }
    this.saveAll();
  },
  
  // Save message to document
  saveMessage(docId, role, text) {
    if (STATE.documents[docId]) {
      if (!STATE.documents[docId].messages) {
        STATE.documents[docId].messages = [];
      }
      STATE.documents[docId].messages.push({ role, text, time: Date.now() });
      this.saveAll();
    }
  },
  
  // Update chatId for document
  updateChatId(docId, chatId) {
    if (STATE.documents[docId]) {
      STATE.documents[docId].chatId = chatId;
      this.saveAll();
    }
  },
  
  // Get document
  getDocument(docId) {
    return STATE.documents[docId] || null;
  },
  
  // Delete document
  deleteDocument(docId) {
    if (STATE.documents[docId]) {
      delete STATE.documents[docId];
      this.saveAll();
      return true;
    }
    return false;
  },
  
  // Get all documents as array
  getAllDocuments() {
    return Object.entries(STATE.documents).map(([docId, doc]) => ({
      docId,
      ...doc
    })).sort((a, b) => (b.uploadTime || 0) - (a.uploadTime || 0));
  }
};

// Configure PDF.js
if (typeof pdfjsLib !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = CONFIG.PDF_WORKER_URL;
}

// Utility functions
const Utils = {
  formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },

  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  generateUploadId() {
    return `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  },

  // Parse markdown untuk menampilkan formatting di chat
  parseMarkdown(text) {
    if (typeof marked !== 'undefined') {
      return marked.parse(text);
    }
    // Fallback simple markdown
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }
};