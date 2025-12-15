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
  isMobile: window.innerWidth <= 1024,
  isTablet: window.innerWidth <= 900,
  isProcessing: false,
  ws: null
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