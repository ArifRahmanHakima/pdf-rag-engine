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
      // Konfigurasi marked untuk tabel dan GFM
      marked.setOptions({
        gfm: true,        // GitHub Flavored Markdown
        breaks: true,     // Convert \n to <br>
        tables: true      // Enable tables
      });
      // Pre-process text untuk deteksi tabel non-standard
      let processedText = this.detectAndConvertTables(text);
      return marked.parse(processedText);
    }
    // Fallback simple markdown with table support
    return this.parseMarkdownFallback(text);
  },

  // Deteksi dan konversi tabel yang tidak dalam format markdown standard
  detectAndConvertTables(text) {
    // Pattern untuk mendeteksi tabel dengan format:
    // Header1    Header2    Header3
    // Value1     Value2     Value3
    
    const lines = text.split('\n');
    let result = [];
    let potentialTableLines = [];
    let inPotentialTable = false;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmedLine = line.trim();
      
      // Skip empty lines
      if (!trimmedLine) {
        if (inPotentialTable && potentialTableLines.length >= 2) {
          // Convert accumulated table lines
          result.push(this.convertSpacedTableToMarkdown(potentialTableLines));
          potentialTableLines = [];
        }
        inPotentialTable = false;
        result.push(line);
        continue;
      }
      
      // Jika sudah dalam format markdown table, lewati
      if (trimmedLine.startsWith('|') && trimmedLine.endsWith('|')) {
        if (inPotentialTable && potentialTableLines.length >= 2) {
          result.push(this.convertSpacedTableToMarkdown(potentialTableLines));
          potentialTableLines = [];
        }
        inPotentialTable = false;
        result.push(line);
        continue;
      }
      
      // Deteksi baris yang terlihat seperti tabel (multiple columns dengan angka)
      // Pattern: Tahun/text diikuti angka-angka atau text dengan multiple spaces/tabs
      const isTableLike = this.isTableLikeLine(trimmedLine);
      
      if (isTableLike) {
        inPotentialTable = true;
        potentialTableLines.push(trimmedLine);
      } else {
        if (inPotentialTable && potentialTableLines.length >= 2) {
          result.push(this.convertSpacedTableToMarkdown(potentialTableLines));
          potentialTableLines = [];
        }
        inPotentialTable = false;
        result.push(line);
      }
    }
    
    // Handle table at end
    if (inPotentialTable && potentialTableLines.length >= 2) {
      result.push(this.convertSpacedTableToMarkdown(potentialTableLines));
    }
    
    return result.join('\n');
  },

  // Cek apakah baris terlihat seperti baris tabel
  isTableLikeLine(line) {
    // Baris tabel biasanya punya:
    // 1. Tahun diikuti angka-angka: "2013 68 57 60 185"
    // 2. Label diikuti angka: "Jumlah 304 261 241 806"
    // 3. Header dengan multiple words: "Tahun S-1 Teknik Sipil S-1 Teknik Industri"
    
    // Pattern 1: Dimulai dengan tahun (4 digit) atau kata diikuti multiple angka
    const yearPattern = /^\d{4}\s+\d+/;
    const labelNumberPattern = /^[A-Za-z]+\s*\d*\s+\d+\s+\d+/;
    const multiColumnPattern = /\s{2,}|\t/; // Multiple spaces atau tab
    
    // Hitung jumlah "kolom" (dipisah multiple spaces)
    const columns = line.split(/\s{2,}|\t/).filter(c => c.trim());
    
    if (columns.length >= 3) {
      // Cek apakah ada angka di kolom-kolom
      const hasNumbers = columns.some(c => /\d+/.test(c));
      if (hasNumbers) return true;
    }
    
    if (yearPattern.test(line)) return true;
    if (labelNumberPattern.test(line)) return true;
    
    return false;
  },

  // Konversi tabel dengan spasi ke format markdown
  convertSpacedTableToMarkdown(lines) {
    if (lines.length < 2) return lines.join('\n');
    
    let markdownTable = [];
    
    lines.forEach((line, index) => {
      // Split by multiple spaces atau tabs
      const cells = line.split(/\s{2,}|\t/).filter(c => c.trim());
      
      if (cells.length > 0) {
        const row = '| ' + cells.join(' | ') + ' |';
        markdownTable.push(row);
        
        // Tambahkan separator setelah header
        if (index === 0) {
          const separator = '| ' + cells.map(() => '---').join(' | ') + ' |';
          markdownTable.push(separator);
        }
      }
    });
    
    return markdownTable.join('\n');
  },

  // Fallback parser untuk tabel jika marked tidak tersedia
  parseMarkdownFallback(text) {
    // Pre-process untuk deteksi tabel
    let processedText = this.detectAndConvertTables(text);
    
    // Coba deteksi dan konversi tabel markdown
    let result = processedText;
    
    // Simple table detection (lines starting with |)
    const lines = result.split('\n');
    let inTable = false;
    let tableLines = [];
    let processedLines = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      if (line.startsWith('|') && line.endsWith('|')) {
        if (!inTable) {
          inTable = true;
          tableLines = [];
        }
        tableLines.push(line);
      } else {
        if (inTable && tableLines.length > 0) {
          processedLines.push(this.convertTableToHtml(tableLines));
          tableLines = [];
          inTable = false;
        }
        processedLines.push(line);
      }
    }
    
    // Handle table at end of text
    if (inTable && tableLines.length > 0) {
      processedLines.push(this.convertTableToHtml(tableLines));
    }
    
    result = processedLines.join('\n');
    
    // Apply other markdown formatting
    return result
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  },

  // Konversi tabel markdown ke HTML
  convertTableToHtml(tableLines) {
    if (tableLines.length < 2) return tableLines.join('\n');
    
    let html = '<table class="chat-table">';
    
    tableLines.forEach((line, index) => {
      // Skip separator line (---|---|---)
      if (line.replace(/[|\-:\s]/g, '') === '') return;
      
      const cells = line.split('|').filter(cell => cell.trim() !== '');
      const tag = index === 0 ? 'th' : 'td';
      const rowClass = index === 0 ? 'table-header' : (index % 2 === 0 ? 'table-row-even' : 'table-row-odd');
      
      html += `<tr class="${rowClass}">`;
      cells.forEach(cell => {
        html += `<${tag}>${cell.trim()}</${tag}>`;
      });
      html += '</tr>';
    });
    
    html += '</table>';
    return html;
  }
};