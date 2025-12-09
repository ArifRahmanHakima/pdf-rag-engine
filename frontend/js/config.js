// ============= CONFIGURATION =============
const CONFIG = {
  API_BASE_URL: '',
  PDF_WORKER_URL: 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js',
  MAX_FILE_SIZE: 5 * 1024 * 1024, // 5MB
  DEFAULT_SCALE: 1.2,
  MIN_SCALE: 0.5,
  MAX_SCALE: 3.0,
  SCALE_STEP: 0.2,
  PROCESSING_STEPS: [
    { id: 'step1', duration: 1500 },
    { id: 'step2', duration: 1500 },
    { id: 'step3', duration: 1500 },
    { id: 'step4', duration: 1000 }
  ]
};

// Global state
const STATE = {
  sessionId: null,  // Redis session ID
  chatId: null,
  docId: "doc001",
  userId: "user123",
  currentPdfName: "",
  pdfDoc: null,
  pageNum: 1,
  pageRendering: false,
  pageNumPending: null,
  scale: CONFIG.DEFAULT_SCALE,
  isMobile: window.innerWidth <= 768
};

// Initialize or get session ID
function getSessionId() {
  let sessionId = sessionStorage.getItem('session_id');
  if (!sessionId) {
    sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('session_id', sessionId);
    console.log('🆕 New session created:', sessionId);
  } else {
    console.log('📋 Existing session:', sessionId);
  }
  STATE.sessionId = sessionId;
  return sessionId;
}

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
  }
};