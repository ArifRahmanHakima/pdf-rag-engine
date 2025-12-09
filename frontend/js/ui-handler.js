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
    resizer: null
  },

  isResizing: false,
  startX: 0,
  startLeftWidth: 0,

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

    // Initialize session
    getSessionId();

    this.attachEvents();
    this.checkMobile();
    
    // Restore session from backend
    this.restoreSession();
  },

  async restoreSession() {
    const sessionId = STATE.sessionId;
    
    console.log('🔄 Restoring session from IndexedDB CDN:', sessionId);
    
    try {
      // Try to get session from IndexedDB first (CDN)
      const session = await StorageManager.getSession(sessionId);
      
      if (session && session.docId) {
        console.log('✅ Session found in IndexedDB:', session);
        
        STATE.docId = session.docId;
        STATE.currentPdfName = session.filename;
        
        // Switch to chat interface
        this.elements.welcomeScreen.style.display = 'none';
        this.elements.chatInterface.classList.add('active');
        
        // Update title
        this.elements.chatTitle.textContent = `📄 ${session.filename}`;
        
        // Add to chat list
        this.addToChatList(session.filename);
        
        // Try to load PDF from IndexedDB first
        const pdfData = await StorageManager.getPDF(session.docId);
        
        if (pdfData && pdfData.blob) {
          console.log('📄 Loading PDF from IndexedDB CDN');
          await PDFHandler.loadPDF(pdfData.blob);
        } else if (session.pdfUrl) {
          // Fallback to backend URL
          const fullUrl = `${CONFIG.API_BASE_URL}${session.pdfUrl}`;
          console.log('🌐 Loading PDF from backend:', fullUrl);
          await PDFHandler.loadPDF(fullUrl);
        }
        
        // Restore chat history from IndexedDB
        const chatHistory = await StorageManager.getChatHistory(sessionId);
        if (chatHistory && chatHistory.length > 0) {
          console.log(`💬 Restoring ${chatHistory.length} messages from IndexedDB`);
          ChatHandler.clearMessages();
          
          for (const msg of chatHistory) {
            // Use skipSave=true to prevent re-saving during restore
            ChatHandler.addMessage(msg.role, msg.content, true);
          }
        }
        
        // Enable input
        ChatHandler.enableInput(true);
        
        console.log('✅ Session restored from IndexedDB CDN!');
        return;
      }
      
      // If not in IndexedDB, try backend
      console.log('ℹ️ Session not in IndexedDB, trying backend...');
      const response = await fetch(`${CONFIG.API_BASE_URL}/session/${sessionId}`);
      const data = await response.json();
      
      if (data.status === 'success' && data.session) {
        const backendSession = data.session;
        console.log('✅ Session found in Redis backend:', backendSession);
        
        if (backendSession.pdf_name && backendSession.pdf_url) {
          // Save to IndexedDB for next time
          await StorageManager.saveSession({
            sessionId: sessionId,
            docId: backendSession.doc_id,
            filename: backendSession.pdf_name,
            pdfUrl: backendSession.pdf_url
          });
          
          STATE.docId = backendSession.doc_id;
          STATE.currentPdfName = backendSession.pdf_name;
          
          // Switch to chat interface
          this.elements.welcomeScreen.style.display = 'none';
          this.elements.chatInterface.classList.add('active');
          
          // Update title
          this.elements.chatTitle.textContent = `📄 ${backendSession.pdf_name}`;
          
          // Add to chat list
          this.addToChatList(backendSession.pdf_name);
          
          // Load PDF from backend
          const fullUrl = `${CONFIG.API_BASE_URL}${backendSession.pdf_url}`;
          console.log('🌐 Loading PDF from backend:', fullUrl);
          await PDFHandler.loadPDF(fullUrl);
          
          // Restore chat history
          if (backendSession.chat_history && backendSession.chat_history.length > 0) {
            console.log(`💬 Restoring ${backendSession.chat_history.length} messages`);
            ChatHandler.clearMessages();
            
            // Save to IndexedDB
            await StorageManager.saveChatHistory(sessionId, backendSession.chat_history);
            
            for (const msg of backendSession.chat_history) {
              // Use skipSave=true to prevent re-saving during restore
              ChatHandler.addMessage(msg.role, msg.content, true);
            }
          }
          
          // Enable input
          ChatHandler.enableInput(true);
          
          console.log('✅ Session restored from backend and cached to IndexedDB!');
        }
      } else {
        console.log('ℹ️ No saved session found');
      }
    } catch (error) {
      console.error('❌ Error restoring session:', error);
    }
  },

  restoreUIState() {
    // Legacy method - now using restoreSession()
    console.log('ℹ️ restoreUIState() called - using restoreSession() instead');
  },

  attachEvents() {
    // Hamburger menu
    this.elements.hamburger.addEventListener('click', () => this.toggleSidebar());

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (STATE.isMobile && 
          this.elements.sidebar.classList.contains('active') &&
          !this.elements.sidebar.contains(e.target) &&
          !this.elements.hamburger.contains(e.target)) {
        this.toggleSidebar();
      }
    });

    // New chat button
    this.elements.newChatBtn.addEventListener('click', () => {
      this.elements.pdfInput.click();
    });

    // PDF upload
    this.elements.pdfInput.addEventListener('change', async (e) => {
      await this.handleFileUpload(e);
    });

    // Drag and drop
    this.setupDragDrop();

    // Resizer for PDF viewer
    this.setupResizer();

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
    const uploadArea = document.getElementById('uploadArea');
    if (!uploadArea) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      uploadArea.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      uploadArea.addEventListener(eventName, () => {
        uploadArea.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      uploadArea.addEventListener(eventName, () => {
        uploadArea.classList.remove('drag-over');
      });
    });

    uploadArea.addEventListener('drop', async (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const file = files[0];
        if (file.type.includes('pdf')) {
          this.elements.pdfInput.files = files;
          await this.handleFileUpload({ target: { files: [file] } });
        } else {
          this.showError('Harap upload file PDF!');
        }
      }
    });
  },

  toggleSidebar() {
    this.elements.sidebar.classList.toggle('active');
    this.elements.hamburger.classList.toggle('active');
  },

  checkMobile() {
    STATE.isMobile = window.innerWidth <= 1024;
    
    if (!STATE.isMobile) {
      this.elements.sidebar.classList.remove('active');
      this.elements.hamburger.classList.remove('active');
    }
  },

  async processPDF(file) {
    try {
      // Switch to chat interface
      this.elements.welcomeScreen.style.display = 'none';
      this.elements.chatInterface.classList.add('active');
      
      // Update title
      STATE.currentPdfName = file.name;
      this.elements.chatTitle.textContent = `📄 ${file.name}`;
      
      // Clear previous chat
      ChatHandler.clearMessages();
      ChatHandler.enableInput(false);
      
      // Show processing animation
      await ChatHandler.showProcessing();
      
      // Add to chat list
      this.addToChatList(file.name);
      
      // Load PDF for viewing
      await PDFHandler.loadPDF(file);
      
      // Save PDF to IndexedDB CDN immediately
      const docId = 'doc_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      STATE.docId = docId;
      
      await StorageManager.savePDF({
        docId: docId,
        filename: file.name,
        blob: file,
        url: null,
        timestamp: Date.now()
      });
      
      // Save session to IndexedDB
      await StorageManager.saveSession({
        sessionId: STATE.sessionId,
        docId: docId,
        filename: file.name,
        pdfUrl: null
      });
      
      console.log('💾 PDF and session saved to IndexedDB CDN');
      
      // Add welcome message
      const welcomeMsg = `Halo! Saya sudah membaca dokumen "${file.name}". File berhasil diproses. Silakan tanyakan apapun tentang isi dokumen ini.`;
      ChatHandler.addMessage('bot', welcomeMsg);
      
      // Save welcome message to IndexedDB
      await StorageManager.addChatMessage(STATE.sessionId, 'bot', welcomeMsg);
      
      // Enable input
      ChatHandler.enableInput(true);
      
      // Upload to backend (non-blocking)
      this.uploadToBackend(file).catch(error => {
        console.error('Background upload error:', error);
      });
      
    } catch (error) {
      console.error('Error processing PDF:', error);
      this.showError('Terjadi kesalahan saat memproses PDF.');
      ChatHandler.addMessage('bot', 'Maaf, terjadi kesalahan saat memproses PDF. Silakan coba lagi.');
      ChatHandler.enableInput(true);
    }
  },

  async uploadToBackend(file) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', STATE.userId);
      
      const response = await fetch(`${CONFIG.API_BASE_URL}/upload`, {
        method: 'POST',
        headers: {
          'X-Session-Id': STATE.sessionId  // Send session ID
        },
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.status === 'success') {
        console.log('✅ PDF uploaded successfully:', data);
        
        // Update doc ID if provided
        if (data.doc_id) {
          STATE.docId = data.doc_id;
          console.log('💾 Session saved to Redis:', STATE.sessionId);
        }
        
        STATE.chatId = null;
        
        // Show success notification (optional)
        // this.showSuccess('PDF berhasil diupload ke server');
      } else {
        throw new Error(data.message || 'Gagal memproses PDF');
      }
    } catch (error) {
      console.error('❌ Error upload PDF:', error);
      // Don't show error to user since PDF viewer still works
      // ChatHandler.addMessage('bot', '⚠️ Upload ke server gagal, tapi Anda masih bisa melihat PDF.');
    }
  },

  addToChatList(fileName) {
    // Remove active from all items
    document.querySelectorAll('.chat-item').forEach(item => {
      item.classList.remove('active');
    });

    // Create new chat item
    const chatItem = document.createElement('div');
    chatItem.className = 'chat-item active';
    chatItem.textContent = fileName;
    chatItem.title = fileName;
    
    // Add click handler
    chatItem.addEventListener('click', () => {
      document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
      });
      chatItem.classList.add('active');
      this.elements.chatTitle.textContent = `📄 ${fileName}`;
    });
    
    this.elements.chatList.prepend(chatItem);
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
    alert(message);
    // You can replace this with a custom toast notification
  },

  showSuccess(message) {
    console.log('✅', message);
    // You can replace this with a custom toast notification
  }
};