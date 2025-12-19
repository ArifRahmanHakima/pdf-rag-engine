// ============= UI HANDLER MODULE =============
const UIHandler = {
  elements: {
    sidebar: null,
    hamburger: null,
    welcomeScreen: null,
    chatInterface: null,
    pdfInput: null,
    newChatBtn: null,
    chatTitle: null,
    chatList: null,
    pdfViewerColumn: null,
    chatColumn: null,
    resizer: null,
    sidebarOverlay: null,
    mobileViewToggle: null,
    showPdfBtn: null,
    showChatBtn: null
  },

  isResizing: false,
  startX: 0,
  startLeftWidth: 0,
  currentUploadId: null,
  progressInterval: null,
  mobileView: 'chat', // 'chat' or 'pdf'
  
  // Storage untuk chat history per dokumen
  chatHistories: {},
  uploadedDocs: {},

  // ========== LOCAL STORAGE FUNCTIONS ==========
  saveToLocalStorage() {
    try {
      const data = {
        chatHistories: this.chatHistories,
        uploadedDocs: this.uploadedDocs,
        lastDocId: STATE.docId,
        lastFileName: STATE.currentFileName
      };
      localStorage.setItem('pdfRagData', JSON.stringify(data));
      console.log('💾 Data saved to localStorage:', data);
      console.log('💾 uploadedDocs count:', Object.keys(this.uploadedDocs).length);
      console.log('💾 chatHistories count:', Object.keys(this.chatHistories).length);
    } catch (e) {
      console.warn('Failed to save to localStorage:', e);
    }
  },

  loadFromLocalStorage() {
    try {
      const saved = localStorage.getItem('pdfRagData');
      console.log('📂 Raw localStorage data:', saved);
      if (saved) {
        const data = JSON.parse(saved);
        this.chatHistories = data.chatHistories || {};
        this.uploadedDocs = data.uploadedDocs || {};
        console.log('📂 Data loaded from localStorage');
        console.log('📂 uploadedDocs:', this.uploadedDocs);
        console.log('📂 chatHistories keys:', Object.keys(this.chatHistories));
        return data;
      } else {
        console.log('📂 No data in localStorage');
      }
    } catch (e) {
      console.warn('Failed to load from localStorage:', e);
    }
    return null;
  },

  restoreSession() {
    console.log('🔄 restoreSession() called');
    const data = this.loadFromLocalStorage();
    if (!data) {
      console.log('📭 No saved session found');
      return false;
    }

    // Restore sidebar dengan dokumen yang sudah diupload
    const docs = Object.values(this.uploadedDocs);
    console.log('📋 Documents to restore:', docs);
    
    if (docs.length === 0) {
      console.log('📭 No documents to restore');
      return false;
    }

    console.log(`🔄 Restoring ${docs.length} documents...`);

    // Tambahkan semua dokumen ke sidebar
    docs.forEach(docInfo => {
      this.restoreDocToSidebar(docInfo);
    });

    // Restore dokumen terakhir yang aktif
    if (data.lastDocId && this.uploadedDocs[data.lastDocId]) {
      const lastDoc = this.uploadedDocs[data.lastDocId];
      const chatItem = document.querySelector(`[data-doc-id="${data.lastDocId}"]`);
      
      console.log(`🎯 Restoring last document: ${lastDoc.fileName}`);
      console.log('📦 Chat item found:', !!chatItem);
      console.log('📦 Welcome screen:', this.elements.welcomeScreen);
      console.log('📦 Chat interface:', this.elements.chatInterface);
      
      if (chatItem) {
        // Set active state
        document.querySelectorAll('.chat-item').forEach(item => item.classList.remove('active'));
        chatItem.classList.add('active');
        
        // Update STATE
        STATE.docId = data.lastDocId;
        STATE.currentFileName = lastDoc.fileName;
        
        // Update UI
        this.elements.chatTitle.textContent = `📄 ${lastDoc.fileName}`;
        
        // Show chat interface - gunakan class active sesuai CSS
        if (this.elements.welcomeScreen && this.elements.chatInterface) {
          this.elements.welcomeScreen.style.display = 'none';
          this.elements.chatInterface.classList.add('active');
          console.log('✅ Chat interface shown');
        } else {
          console.error('❌ Welcome screen or chat interface element not found!');
        }
        
        // Load chat history
        if (this.chatHistories[data.lastDocId] && ChatHandler.elements.messages) {
          ChatHandler.elements.messages.innerHTML = this.chatHistories[data.lastDocId].html;
          STATE.chatId = this.chatHistories[data.lastDocId].chatId;
          console.log('✅ Chat history restored');
        }
        
        // Try to load PDF
        this.reloadPDF(lastDoc.fileName);
        
        ChatHandler.enableInput(true);
        return true;
      }
    }

    return docs.length > 0;
  },

  restoreDocToSidebar(docInfo) {
    // Cek apakah sudah ada di sidebar
    if (document.querySelector(`[data-doc-id="${docInfo.docId}"]`)) {
      return;
    }

    const chatItem = document.createElement('div');
    chatItem.className = 'chat-item';
    chatItem.textContent = docInfo.fileName;
    chatItem.title = docInfo.fileName;
    chatItem.dataset.docId = docInfo.docId;
    chatItem.dataset.fileName = docInfo.fileName;

    chatItem.addEventListener('click', () => {
      this.switchToDocument(chatItem);
    });

    this.elements.chatList.appendChild(chatItem);
  },

  async reloadPDF(fileName) {
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/uploads/${fileName}`);
      if (response.ok) {
        const blob = await response.blob();
        const file = new File([blob], fileName, { type: 'application/pdf' });
        await PDFHandler.loadPDF(file);
      }
    } catch (error) {
      console.warn('Could not reload PDF file:', error);
    }
  },
  // ========== END LOCAL STORAGE FUNCTIONS ==========

  init() {
    this.elements.sidebar = document.getElementById('sidebar');
    this.elements.hamburger = document.getElementById('hamburgerBtn');
    this.elements.welcomeScreen = document.getElementById('welcomeScreen');
    this.elements.chatInterface = document.getElementById('chatInterface');
    this.elements.pdfInput = document.getElementById('pdfInput');
    this.elements.newChatBtn = document.getElementById('newChatBtn');
    this.elements.chatTitle = document.getElementById('chatTitle');
    this.elements.chatList = document.getElementById('chatList');
    this.elements.pdfViewerColumn = document.getElementById('pdfViewerColumn');
    this.elements.chatColumn = document.getElementById('chatColumn');
    this.elements.resizer = document.getElementById('resizer');
    this.elements.sidebarOverlay = document.getElementById('sidebarOverlay');
    this.elements.mobileViewToggle = document.getElementById('mobileViewToggle');
    this.elements.showPdfBtn = document.getElementById('showPdfBtn');
    this.elements.showChatBtn = document.getElementById('showChatBtn');

    this.attachEvents();
    this.checkMobile();
  },

  attachEvents() {
    // Hamburger menu
    this.elements.hamburger?.addEventListener('click', () => this.toggleSidebar());

    // Sidebar overlay click to close
    this.elements.sidebarOverlay?.addEventListener('click', () => this.closeSidebar());

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (STATE.isMobile && 
          this.elements.sidebar?.classList.contains('active') &&
          !this.elements.sidebar.contains(e.target) &&
          !this.elements.hamburger?.contains(e.target)) {
        this.closeSidebar();
      }
    });

    // New chat button
    this.elements.newChatBtn?.addEventListener('click', () => {
      this.elements.pdfInput.click();
    });

    // PDF upload
    this.elements.pdfInput?.addEventListener('change', async (e) => {
      await this.handleFileUpload(e);
    });

    // Drag and drop
    this.setupDragDrop();

    // Resizer for PDF viewer
    this.setupResizer();

    // Mobile view toggle buttons
    this.elements.showPdfBtn?.addEventListener('click', () => this.switchMobileView('pdf'));
    this.elements.showChatBtn?.addEventListener('click', () => this.switchMobileView('chat'));

    // Window resize handler
    window.addEventListener('resize', Utils.debounce(() => {
      this.checkMobile();
    }, 250));
  },

  async handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    if (!file.type.includes('pdf')) {
      this.showError('Harap upload file PDF!');
      this.elements.pdfInput.value = '';
      return;
    }

    // Validate file size
    if (file.size > CONFIG.MAX_FILE_SIZE) {
      this.showError(`Ukuran file maksimal ${Utils.formatFileSize(CONFIG.MAX_FILE_SIZE)}!`);
      this.elements.pdfInput.value = '';
      return;
    }

    await this.processPDF(file);
    this.elements.pdfInput.value = '';
  },

  setupDragDrop() {
    const uploadBox = document.querySelector('.upload-box');
    if (!uploadBox) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      uploadBox.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      uploadBox.addEventListener(eventName, () => {
        uploadBox.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      uploadBox.addEventListener(eventName, () => {
        uploadBox.classList.remove('drag-over');
      });
    });

    uploadBox.addEventListener('drop', async (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const file = files[0];
        if (file.type.includes('pdf')) {
          await this.handleFileUpload({ target: { files: [file] } });
        } else {
          this.showError('Harap upload file PDF!');
        }
      }
    });
  },

  toggleSidebar() {
    this.elements.sidebar?.classList.toggle('active');
    this.elements.hamburger?.classList.toggle('active');
    this.elements.sidebarOverlay?.classList.toggle('active');
  },

  closeSidebar() {
    this.elements.sidebar?.classList.remove('active');
    this.elements.hamburger?.classList.remove('active');
    this.elements.sidebarOverlay?.classList.remove('active');
  },

  switchMobileView(view) {
    this.mobileView = view;
    
    if (view === 'pdf') {
      this.elements.pdfViewerColumn?.classList.add('mobile-active');
      this.elements.chatColumn?.classList.remove('mobile-active');
      this.elements.showPdfBtn?.classList.add('active');
      this.elements.showChatBtn?.classList.remove('active');
    } else {
      this.elements.pdfViewerColumn?.classList.remove('mobile-active');
      this.elements.chatColumn?.classList.add('mobile-active');
      this.elements.showPdfBtn?.classList.remove('active');
      this.elements.showChatBtn?.classList.add('active');
    }
  },

  checkMobile() {
    STATE.isMobile = window.innerWidth <= 1024;
    STATE.isTablet = window.innerWidth <= 900;
    
    if (!STATE.isMobile) {
      this.closeSidebar();
    }
    
    // Reset mobile view when switching to desktop
    if (!STATE.isTablet) {
      this.elements.pdfViewerColumn?.classList.remove('mobile-active');
      this.elements.chatColumn?.classList.remove('mobile-active');
    } else {
      // Ensure at least one view is active on mobile/tablet
      if (!this.elements.pdfViewerColumn?.classList.contains('mobile-active') &&
          !this.elements.chatColumn?.classList.contains('mobile-active')) {
        this.switchMobileView('chat');
      }
    }
  },

async processPDF(file) {
    if (STATE.isProcessing) {
      this.showError('Sedang memproses file lain. Mohon tunggu...');
      return;
    }

    STATE.isProcessing = true;

    try {
      // Generate unique upload ID
      this.currentUploadId = Utils.generateUploadId();

      // Switch to chat interface
      this.elements.welcomeScreen.style.display = 'none';
      this.elements.chatInterface.classList.add('active');
      
      // Update title
      STATE.currentPdfName = file.name;
      STATE.currentFileName = file.name;
      this.elements.chatTitle.textContent = `📄 ${file.name}`;
      
      // Clear previous chat
      ChatHandler.clearMessages();
      ChatHandler.enableInput(false);
      
      // Show processing indicator
      this.showProcessingSteps();
      
      // Load PDF for viewing (parallel with backend processing)
      const pdfLoadPromise = PDFHandler.loadPDF(file);
      
      // Start step 1: Reading
      this.updateProcessingStep({ step: 'reading', progress: 0, status: 'processing' });
      
      await Utils.sleep(500);
      
      // Upload to backend
      const uploadResult = await this.uploadToBackend(file);
      
      // Wait for PDF load
      await pdfLoadPromise;
      
      // Hide processing indicator
      this.hideProcessingSteps();
      
      // Save doc_id dari response backend
      if (uploadResult && uploadResult.doc_id) {
        STATE.docId = uploadResult.doc_id;
        console.log('📄 Document ID:', STATE.docId);
        
        // Add to chat list with doc_id
        this.addToChatList(file.name, uploadResult.doc_id);
      }
      
      // Show summary with enhanced display
      if (uploadResult && uploadResult.summary) {
        // Use the new summary card with typing animation
        await ChatHandler.showSummaryWithTyping(uploadResult.summary, file.name);
        await Utils.sleep(500); // Wait for animation to complete
      } else {
        // If no summary, show simple welcome message
        const welcomeMsg = `📄 Dokumen "${file.name}" berhasil diproses. Silakan tanyakan apapun tentang isi dokumen ini.`;
        ChatHandler.addMessage('bot', welcomeMsg);
      }
      
      // Enable input AFTER summary is fully displayed
      ChatHandler.enableInput(true);
      
      // ✅ Simpan chat history untuk dokumen ini (termasuk summary)
      if (STATE.docId) {
        this.saveChatHistory();
      }
      
      this.showSuccess('PDF berhasil diproses!');
      
    } catch (error) {
      console.error('Error processing PDF:', error);
      this.showError(`Terjadi kesalahan: ${error.message}`);
      ChatHandler.addMessage('bot', `❌ Maaf, terjadi kesalahan: ${error.message}`);
      ChatHandler.enableInput(true);
      this.hideProcessingSteps();
    } finally {
      STATE.isProcessing = false;
      this.currentUploadId = null;
    }
  },

  async uploadToBackend(file) {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);

      const xhr = new XMLHttpRequest();

      // Upload progress
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percentComplete = (e.loaded / e.total) * 100;
          this.updateProcessingStep({ 
            step: 'reading', 
            progress: percentComplete, 
            status: 'processing',
            message: `Uploading... ${percentComplete.toFixed(0)}%`
          });
        }
      });

      // Upload complete, now processing
      xhr.addEventListener('load', async () => {
        if (xhr.status === 200) {
          try {
            const response = JSON.parse(xhr.responseText);
            
            if (response.status === 'success') {
              // Complete step 1
              this.updateProcessingStep({ step: 'reading', progress: 100, status: 'completed' });
              await Utils.sleep(300);
              
              // Step 2: Analyzing
              this.updateProcessingStep({ step: 'analyzing', progress: 0, status: 'processing' });
              await Utils.sleep(800);
              
              // Simulate analyzing progress
              for (let i = 0; i <= 100; i += 25) {
                this.updateProcessingStep({ step: 'analyzing', progress: i, status: 'processing' });
                await Utils.sleep(200);
              }
              this.updateProcessingStep({ step: 'analyzing', progress: 100, status: 'completed' });
              await Utils.sleep(300);
              
              // Step 3: Embedding
              this.updateProcessingStep({ step: 'embedding', progress: 0, status: 'processing' });
              
              // Simulate embedding progress
              for (let i = 0; i <= 100; i += 20) {
                this.updateProcessingStep({ step: 'embedding', progress: i, status: 'processing' });
                await Utils.sleep(300);
              }
              this.updateProcessingStep({ step: 'embedding', progress: 100, status: 'completed' });
              await Utils.sleep(300);
              
              // Step 4: Ready
              this.updateProcessingStep({ step: 'ready', progress: 100, status: 'completed' });
              await Utils.sleep(300);
              
              // Show generating summary indicator in chat
              ChatHandler.showGeneratingSummary();
              await Utils.sleep(500);
              
              resolve(response);
            } else {
              reject(new Error(response.detail || 'Upload failed'));
            }
          } catch (error) {
            reject(new Error('Invalid response from server'));
          }
        } else {
          try {
            const errorResponse = JSON.parse(xhr.responseText);
            reject(new Error(errorResponse.detail || `HTTP error! status: ${xhr.status}`));
          } catch {
            reject(new Error(`HTTP error! status: ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload aborted'));
      });

      // Send request
      xhr.open('POST', `${CONFIG.API_BASE_URL}/upload`);
      xhr.send(formData);
    });
  },

  showProcessingSteps() {
    const processingIndicator = document.getElementById('processingIndicator');
    processingIndicator.classList.add('active');
    
    // Reset all steps
    CONFIG.PROCESSING_STEPS.forEach(step => {
      const stepEl = document.getElementById(step.id);
      stepEl.classList.remove('active', 'completed', 'error');
    });
  },

  hideProcessingSteps() {
    const processingIndicator = document.getElementById('processingIndicator');
    processingIndicator.classList.remove('active');
  },

  updateProcessingStep(data) {
    const { step, progress, status, message } = data;
    
    // Find step by key
    const stepConfig = CONFIG.PROCESSING_STEPS.find(s => s.key === step);
    if (!stepConfig) return;
    
    const stepEl = document.getElementById(stepConfig.id);
    if (!stepEl) return;

    // Remove all states first
    stepEl.classList.remove('active', 'completed', 'error');

    if (status === 'processing') {
      // Mark previous steps as completed
      const currentIndex = CONFIG.PROCESSING_STEPS.findIndex(s => s.id === stepConfig.id);
      CONFIG.PROCESSING_STEPS.forEach((s, index) => {
        if (index < currentIndex) {
          const prevStepEl = document.getElementById(s.id);
          prevStepEl.classList.remove('active');
          prevStepEl.classList.add('completed');
        }
      });

      stepEl.classList.add('active');
      
      // Update progress bar
      if (progress !== undefined) {
        this.updateStepProgress(stepConfig.id, progress);
      }
      
      // Update text if message provided
      if (message) {
        const stepText = stepEl.querySelector('.step-text');
        if (stepText) {
          const originalText = stepConfig.name;
          stepText.textContent = message || originalText;
        }
      }
    } else if (status === 'completed') {
      stepEl.classList.add('completed');
      
      // Reset text to original
      const stepText = stepEl.querySelector('.step-text');
      if (stepText) {
        stepText.textContent = stepConfig.name;
      }
    } else if (status === 'error') {
      stepEl.classList.add('error');
      if (message) {
        const stepText = stepEl.querySelector('.step-text');
        if (stepText) {
          stepText.textContent = message;
        }
      }
    }
  },

  updateStepProgress(stepId, percent) {
    const stepEl = document.getElementById(stepId);
    if (!stepEl) return;

    const progressBar = stepEl.querySelector('.step-progress');
    if (progressBar) {
      progressBar.style.setProperty('--progress', `${percent}%`);
    }
  },

  addToChatList(fileName, docId = null, filePath = null) {
    // Remove active from all items
    document.querySelectorAll('.chat-item').forEach(item => {
      item.classList.remove('active');
    });

    // Create new chat item
    const chatItem = document.createElement('div');
    chatItem.className = 'chat-item active';
    chatItem.textContent = fileName;
    chatItem.title = fileName;
    
    // Store doc info
    const docInfo = {
      fileName: fileName,
      docId: docId || STATE.docId,
      filePath: filePath
    };
    chatItem.dataset.docId = docInfo.docId;
    chatItem.dataset.fileName = fileName;
    
    // Save to uploadedDocs
    if (docInfo.docId) {
      this.uploadedDocs[docInfo.docId] = docInfo;
      // ✅ Simpan ke localStorage
      this.saveToLocalStorage();
    }
    
    // Add click handler to switch between documents
    chatItem.addEventListener('click', () => {
      this.switchToDocument(chatItem);
    });
    
    this.elements.chatList.prepend(chatItem);
  },

  // Simpan chat history untuk dokumen saat ini
  saveChatHistory() {
    if (STATE.docId && ChatHandler.elements.messages) {
      this.chatHistories[STATE.docId] = {
        html: ChatHandler.elements.messages.innerHTML,
        chatId: STATE.chatId
      };
      console.log(`💾 Chat history saved for: ${STATE.docId}`);
      
      // ✅ Simpan ke localStorage
      this.saveToLocalStorage();
    }
  },
  
  // Muat chat history untuk dokumen tertentu
  loadChatHistory(docId) {
    if (this.chatHistories[docId]) {
      ChatHandler.elements.messages.innerHTML = this.chatHistories[docId].html;
      STATE.chatId = this.chatHistories[docId].chatId;
      console.log(`📂 Chat history loaded for: ${docId}`);
      return true;
    }
    return false;
  },

  async switchToDocument(chatItem) {
    const docId = chatItem.dataset.docId;
    const fileName = chatItem.dataset.fileName;
    
    if (!docId) {
      console.warn('No doc_id found for this chat item');
      return;
    }
    
    // Don't switch if already active
    if (chatItem.classList.contains('active')) {
      return;
    }
    
    console.log(`🔄 Switching to document: ${fileName} (${docId})`);
    
    // ✅ Simpan chat history dokumen saat ini sebelum pindah
    this.saveChatHistory();
    
    // Update active state
    document.querySelectorAll('.chat-item').forEach(item => {
      item.classList.remove('active');
    });
    chatItem.classList.add('active');
    
    // Update STATE
    const previousDocId = STATE.docId;
    STATE.docId = docId;
    STATE.currentFileName = fileName;
    
    // Update UI
    this.elements.chatTitle.textContent = `📄 ${fileName}`;
    
    // Pastikan chat interface ditampilkan
    this.elements.welcomeScreen.style.display = 'none';
    this.elements.chatInterface.classList.add('active');
    
    // ✅ Coba muat chat history yang tersimpan
    const historyLoaded = this.loadChatHistory(docId);
    
    if (!historyLoaded) {
      // Jika tidak ada history, clear dan tampilkan welcome message
      ChatHandler.elements.messages.innerHTML = '';
      STATE.chatId = null;
      ChatHandler.addMessage('bot', `Anda sekarang dalam sesi chat untuk dokumen "${fileName}". Silakan tanyakan apapun tentang isi dokumen ini.`);
    }
    
    // Try to load the PDF file if it exists in uploads
    const uploadDir = 'uploads';
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/${uploadDir}/${fileName}`);
      if (response.ok) {
        const blob = await response.blob();
        const file = new File([blob], fileName, { type: 'application/pdf' });
        await PDFHandler.loadPDF(file);
      }
    } catch (error) {
      console.warn('Could not reload PDF file:', error);
    }
    
    ChatHandler.enableInput(true);
    
    // Close sidebar on mobile
    if (STATE.isMobile) {
      this.closeSidebar();
    }
  },

  setupResizer() {
    const resizer = this.elements.resizer;
    if (!resizer) return;

    const leftPanel = this.elements.pdfViewerColumn;
    const rightPanel = this.elements.chatColumn;

    resizer.addEventListener('mousedown', (e) => {
      this.isResizing = true;
      this.startX = e.clientX;
      this.startLeftWidth = leftPanel.offsetWidth;
      
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!this.isResizing) return;
      
      const container = leftPanel.parentElement;
      const deltaX = e.clientX - this.startX;
      const containerWidth = container.offsetWidth;
      const newLeftWidth = this.startLeftWidth + deltaX;
      const minWidth = 300;
      const maxWidth = containerWidth - minWidth - 5;
      
      if (newLeftWidth >= minWidth && newLeftWidth <= maxWidth) {
        const leftPercent = (newLeftWidth / containerWidth) * 100;
        const rightPercent = 100 - leftPercent - (5 / containerWidth * 100);
        
        leftPanel.style.width = `${leftPercent}%`;
        rightPanel.style.width = `${rightPercent}%`;
      }
    });

    document.addEventListener('mouseup', () => {
      if (this.isResizing) {
        this.isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    });
  },

  showError(message) {
    const toast = document.createElement('div');
    toast.className = 'toast toast-error';
    toast.innerHTML = `
      <span>❌</span>
      <span>${Utils.escapeHtml(message)}</span>
    `;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  showSuccess(message) {
    const toast = document.createElement('div');
    toast.className = 'toast toast-success';
    toast.innerHTML = `
      <span>✅</span>
      <span>${Utils.escapeHtml(message)}</span>
    `;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }
};