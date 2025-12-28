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
    toggleSidebarBtn: null,
    chatOptionsBtn: null,
    chatOptionsDropdown: null,
    renameModalOverlay: null,
    renameInput: null
  },

  isResizing: false,
  startX: 0,
  startLeftWidth: 0,
  currentUploadId: null,
  progressInterval: null,

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
    this.elements.toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    this.elements.chatOptionsBtn = document.getElementById('chatOptionsBtn');
    this.elements.chatOptionsDropdown = document.getElementById('chatOptionsDropdown');
    this.elements.renameModalOverlay = document.getElementById('renameModalOverlay');
    this.elements.renameInput = document.getElementById('renameInput');

    // Load sidebar state from localStorage
    this.loadSidebarState();

    // Load saved documents from localStorage
    DocStorage.loadAll();
    this.renderChatList();

    this.attachEvents();
    this.checkMobile();
  },

  attachEvents() {
    // Hamburger menu (mobile)
    this.elements.hamburger?.addEventListener('click', () => this.toggleSidebar());

    // Toggle sidebar button (desktop)
    console.log('Toggle button element:', this.elements.toggleSidebarBtn); // Debug log
    if (this.elements.toggleSidebarBtn) {
      this.elements.toggleSidebarBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggleSidebarDesktop();
      });
      console.log('Toggle sidebar event listener attached!'); // Debug log
    }

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (STATE.isMobile && 
          this.elements.sidebar?.classList.contains('active') &&
          !this.elements.sidebar.contains(e.target) &&
          !this.elements.hamburger?.contains(e.target)) {
        this.closeSidebar();
      }
      
      // Close dropdown when clicking outside
      if (this.elements.chatOptionsDropdown?.classList.contains('active') &&
          !this.elements.chatOptionsBtn?.contains(e.target) &&
          !this.elements.chatOptionsDropdown?.contains(e.target)) {
        this.closeChatOptionsDropdown();
      }
    });

    // Chat options dropdown toggle
    this.elements.chatOptionsBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleChatOptionsDropdown();
    });

    // Rename chat button
    document.getElementById('renameChatBtn')?.addEventListener('click', () => {
      this.closeChatOptionsDropdown();
      this.openRenameModal();
    });

    // Export chat button
    document.getElementById('exportChatBtn')?.addEventListener('click', () => {
      this.closeChatOptionsDropdown();
      this.exportChat();
    });

    // Reset chat button
    document.getElementById('resetChatBtn')?.addEventListener('click', () => {
      this.closeChatOptionsDropdown();
      this.resetChat();
    });

    // Rename modal events
    document.getElementById('renameCancelBtn')?.addEventListener('click', () => {
      this.closeRenameModal();
    });

    document.getElementById('renameSaveBtn')?.addEventListener('click', () => {
      this.saveRename();
    });

    this.elements.renameModalOverlay?.addEventListener('click', (e) => {
      if (e.target === this.elements.renameModalOverlay) {
        this.closeRenameModal();
      }
    });

    this.elements.renameInput?.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        this.saveRename();
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

    // Window resize handler
    window.addEventListener('resize', Utils.debounce(() => {
      this.checkMobile();
    }, 250));
  },

  // Chat Options Dropdown Functions
  toggleChatOptionsDropdown() {
    this.elements.chatOptionsDropdown?.classList.toggle('active');
  },

  closeChatOptionsDropdown() {
    this.elements.chatOptionsDropdown?.classList.remove('active');
  },

  // Rename Modal Functions
  openRenameModal() {
    const currentName = this.elements.chatTitle?.textContent?.replace('📄 ', '') || '';
    if (this.elements.renameInput) {
      this.elements.renameInput.value = currentName;
    }
    this.elements.renameModalOverlay?.classList.add('active');
    setTimeout(() => {
      this.elements.renameInput?.focus();
      this.elements.renameInput?.select();
    }, 100);
  },

  closeRenameModal() {
    this.elements.renameModalOverlay?.classList.remove('active');
  },

  saveRename() {
    const newName = this.elements.renameInput?.value?.trim();
    if (newName) {
      // Update title
      if (this.elements.chatTitle) {
        this.elements.chatTitle.textContent = `📄 ${newName}`;
      }
      
      // Update in storage
      if (STATE.docId && STATE.documents[STATE.docId]) {
        STATE.documents[STATE.docId].fileName = newName;
        DocStorage.saveAll();
        this.renderChatList();
      }
      
      this.closeRenameModal();
      this.showSuccess('Nama chat berhasil diubah!');
    }
  },

  // Export Chat Function
  exportChat() {
    if (!STATE.docId) {
      this.showError('Tidak ada chat untuk diekspor!');
      return;
    }

    const doc = STATE.documents[STATE.docId];
    if (!doc || !doc.messages || doc.messages.length === 0) {
      this.showError('Chat kosong, tidak ada yang diekspor!');
      return;
    }

    // Create export content
    let exportContent = `Chat Export - ${doc.fileName}\n`;
    exportContent += `Tanggal: ${new Date().toLocaleString('id-ID')}\n`;
    exportContent += `${'='.repeat(50)}\n\n`;

    doc.messages.forEach(msg => {
      const role = msg.role === 'user' ? '👤 Anda' : '🤖 Bot';
      const time = msg.time ? new Date(msg.time).toLocaleString('id-ID') : '';
      exportContent += `${role} ${time ? `(${time})` : ''}:\n${msg.text}\n\n`;
    });

    // Download as text file
    const blob = new Blob([exportContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${doc.fileName.replace('.pdf', '')}-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    this.showSuccess('Chat berhasil diekspor!');
  },

  // Reset Chat Function
  resetChat() {
    if (!STATE.docId) {
      this.showError('Tidak ada chat untuk direset!');
      return;
    }

    if (confirm('Apakah Anda yakin ingin mereset chat ini? Semua pesan akan dihapus.')) {
      // Clear messages in storage
      if (STATE.documents[STATE.docId]) {
        STATE.documents[STATE.docId].messages = [];
        STATE.documents[STATE.docId].chatId = null;
        DocStorage.saveAll();
      }

      // Clear chat messages on screen
      ChatHandler.clearMessages(true);
      STATE.chatId = null;

      this.showSuccess('Chat berhasil direset!');
    }
  },

  // Success notification
  showSuccess(message) {
    // Create success toast
    const toast = document.createElement('div');
    toast.className = 'success-toast';
    toast.innerHTML = `<span>✅</span> ${message}`;
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #10b981;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
      z-index: 9999;
      animation: slideInRight 0.3s ease;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.animation = 'slideOutRight 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
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
  },

  closeSidebar() {
    this.elements.sidebar?.classList.remove('active');
    this.elements.hamburger?.classList.remove('active');
  },

  // Toggle sidebar untuk desktop
  toggleSidebarDesktop() {
    console.log('Toggle sidebar clicked!'); // Debug log
    const sidebar = this.elements.sidebar;
    const toggleBtn = this.elements.toggleSidebarBtn;
    const mainContainer = document.querySelector('.main-container');
    
    console.log('Sidebar element:', sidebar); // Debug log
    console.log('MainContainer:', mainContainer); // Debug log
    
    if (sidebar) {
      sidebar.classList.toggle('collapsed');
      toggleBtn?.classList.toggle('sidebar-hidden');
      mainContainer?.classList.toggle('sidebar-collapsed');
      
      // Update title tooltip
      const isCollapsed = sidebar.classList.contains('collapsed');
      console.log('Is collapsed:', isCollapsed); // Debug log
      
      if (toggleBtn) {
        toggleBtn.title = isCollapsed ? 'Tampilkan sidebar' : 'Sembunyikan sidebar';
      }
      
      // Save state to localStorage
      localStorage.setItem('sidebarCollapsed', isCollapsed ? 'true' : 'false');
    }
  },

  // Load sidebar state from localStorage
  loadSidebarState() {
    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    
    if (isCollapsed) {
      const sidebar = this.elements.sidebar;
      const toggleBtn = this.elements.toggleSidebarBtn;
      const mainContainer = document.querySelector('.main-container');
      
      sidebar?.classList.add('collapsed');
      toggleBtn?.classList.add('sidebar-hidden');
      mainContainer?.classList.add('sidebar-collapsed');
      
      if (toggleBtn) {
        toggleBtn.title = 'Tampilkan sidebar';
      }
    }
  },

  checkMobile() {
    STATE.isMobile = window.innerWidth <= 1024;
    
    if (!STATE.isMobile) {
      this.closeSidebar();
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
      
      // Don't add to chat list yet - wait for doc_id
      
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
      
      // Show summary if available
      if (uploadResult && uploadResult.summary) {
        const summaryHtml = Utils.parseMarkdown(`📋 **Ringkasan Dokumen:**\n\n${uploadResult.summary}`);
        ChatHandler.addMessage('bot', summaryHtml, true);
        DocStorage.saveMessage(STATE.docId, 'bot', `📋 **Ringkasan Dokumen:**\n\n${uploadResult.summary}`);
      }
      
      // Add welcome message
      const welcomeMsg = `Halo! Dokumen "${file.name}" berhasil diproses. Silakan tanyakan apapun tentang isi dokumen ini.`;
      ChatHandler.addMessage('bot', welcomeMsg);
      
      // Show suggested questions if available
      if (uploadResult && uploadResult.suggested_questions && uploadResult.suggested_questions.length > 0) {
        ChatHandler.showSuggestedQuestions(uploadResult.suggested_questions);
      }
      
      // Save doc_id dari response backend
      if (uploadResult && uploadResult.doc_id) {
        STATE.docId = uploadResult.doc_id;
        console.log('📄 Document ID:', STATE.docId);
        
        // Add to chat list with doc_id
        this.addToChatList(file.name, STATE.docId);
        
        // Save welcome message
        DocStorage.saveMessage(STATE.docId, 'bot', welcomeMsg);
      }
      
      // Enable input
      ChatHandler.enableInput(true);
      
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
            
            if (response.status === 'queued') {
              // File diterima, mulai monitoring dengan status modal
              const docId = response.doc_id;
              
              // Complete step 1
              this.updateProcessingStep({ step: 'reading', progress: 100, status: 'completed' });
              await Utils.sleep(300);
              
              // Simpan doc_id untuk querynya nanti
              STATE.docId = docId;
              
              // Tampilkan status modal
              if (typeof statusMonitor !== 'undefined') {
                statusMonitor.showModal(docId);
              }
              
              // Step 2-4 akan diupdate dari status modal
              // Tapi set default progress di UI untuk fallback
              this.updateProcessingStep({ step: 'analyzing', progress: 0, status: 'processing' });
              
              // Tunggu hingga status menjadi completed (cek setiap 3 detik)
              let isProcessing = true;
              let checkCount = 0;
              const maxChecks = 600; // 30 menit maksimal
              
              while (isProcessing && checkCount < maxChecks) {
                checkCount++;
                await Utils.sleep(3000);
                
                // Cek status
                try {
                  const statusResponse = await fetch(`${CONFIG.API_BASE_URL}/upload/status/${docId}`);
                  const statusData = await statusResponse.json();
                  
                  if (statusData.status === 'completed') {
                    this.updateProcessingStep({ step: 'embedding', progress: 100, status: 'completed' });
                    await Utils.sleep(300);
                    this.updateProcessingStep({ step: 'ready', progress: 100, status: 'completed' });
                    await Utils.sleep(500);
                    isProcessing = false;
                    
                    // Fetch summary and suggested questions
                    try {
                      const summaryResponse = await fetch(`${CONFIG.API_BASE_URL}/upload/summary/${docId}`);
                      const summaryData = await summaryResponse.json();
                      
                      if (summaryData.status === 'success') {
                        response.summary = summaryData.summary;
                        response.suggested_questions = summaryData.suggested_questions;
                      }
                    } catch (err) {
                      console.error('Error fetching summary:', err);
                    }
                    
                    resolve(response);
                  } else if (statusData.status === 'failed') {
                    reject(new Error(`Processing failed: ${statusData.message}`));
                    return;
                  }
                } catch (error) {
                  console.error('Error checking status:', error);
                }
              }
              
              if (isProcessing) {
                reject(new Error('Processing timeout after 30 minutes'));
              }
            } else if (response.status === 'success') {
              // Old behavior - instant processing
              STATE.docId = response.doc_id;
              
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

  addToChatList(fileName, docId = null) {
    // If docId provided, save to storage
    if (docId) {
      DocStorage.saveDocument(docId, fileName);
    }
    
    // Re-render the chat list
    this.renderChatList();
    
    // Set active the new/current item
    const currentDocId = docId || STATE.docId;
    this.setActiveChatItem(currentDocId);
  },
  
  renderChatList() {
    // Clear existing list
    this.elements.chatList.innerHTML = '';
    
    // Get all documents
    const documents = DocStorage.getAllDocuments();
    
    console.log('📋 Rendering chat list:', documents.length, 'documents');
    
    if (documents.length === 0) {
      const emptyMsg = document.createElement('div');
      emptyMsg.className = 'chat-list-empty';
      emptyMsg.textContent = 'Belum ada dokumen';
      emptyMsg.style.cssText = 'color: #888; font-size: 12px; padding: 10px; text-align: center;';
      this.elements.chatList.appendChild(emptyMsg);
      return;
    }
    
    const self = this; // Store reference to UIHandler
    
    documents.forEach(doc => {
      const chatItem = document.createElement('div');
      chatItem.className = 'chat-item';
      chatItem.setAttribute('data-doc-id', doc.docId);
      
      if (doc.docId === STATE.docId) {
        chatItem.classList.add('active');
      }
      
      // Container for filename
      const fileNameSpan = document.createElement('span');
      fileNameSpan.className = 'chat-item-name';
      fileNameSpan.textContent = doc.fileName;
      fileNameSpan.title = doc.fileName;
      
      // Delete button
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'chat-item-delete';
      deleteBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"></polyline>
        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        <line x1="10" y1="11" x2="10" y2="17"></line>
        <line x1="14" y1="11" x2="14" y2="17"></line>
      </svg>`;
      deleteBtn.title = 'Hapus dokumen';
      deleteBtn.type = 'button';
      
      // Use closure to capture doc values
      const docIdToDelete = doc.docId;
      const fileNameToDelete = doc.fileName;
      
      deleteBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('🗑️ Delete clicked for:', fileNameToDelete);
        self.deleteDocument(docIdToDelete, fileNameToDelete);
      });
      
      chatItem.appendChild(fileNameSpan);
      chatItem.appendChild(deleteBtn);
      
      // Click to switch document - use closure
      const docIdToSwitch = doc.docId;
      chatItem.addEventListener('click', function(e) {
        // Don't switch if clicking delete button
        if (e.target.classList.contains('chat-item-delete')) {
          return;
        }
        console.log('📄 Switching to document:', docIdToSwitch);
        self.switchToDocument(docIdToSwitch);
      });
      
      this.elements.chatList.appendChild(chatItem);
    });
  },
  
  setActiveChatItem(docId) {
    console.log('🎯 Setting active chat item:', docId);
    document.querySelectorAll('.chat-item').forEach(item => {
      item.classList.remove('active');
      const itemDocId = item.getAttribute('data-doc-id');
      if (itemDocId === docId) {
        item.classList.add('active');
        console.log('✅ Found and activated item');
      }
    });
  },
  
  async switchToDocument(docId) {
    console.log('🔄 switchToDocument called with:', docId);
    
    const doc = DocStorage.getDocument(docId);
    if (!doc) {
      console.error('❌ Document not found:', docId);
      this.showError('Dokumen tidak ditemukan');
      return;
    }
    
    console.log('📄 Found document:', doc.fileName);
    
    // Update state
    STATE.docId = docId;
    STATE.chatId = doc.chatId || null;
    STATE.currentPdfName = doc.fileName;
    STATE.currentFileName = doc.fileName;
    
    // Update UI
    this.elements.welcomeScreen.style.display = 'none';
    this.elements.chatInterface.classList.add('active');
    this.elements.chatTitle.textContent = `📄 ${doc.fileName}`;
    
    // Set active in list
    this.setActiveChatItem(docId);
    
    // Clear and load messages
    ChatHandler.clearMessages(false); // false = don't reset chatId
    
    // Load saved messages
    if (doc.messages && doc.messages.length > 0) {
      console.log('💬 Loading', doc.messages.length, 'messages');
      doc.messages.forEach(msg => {
        // Bot messages will be parsed as markdown automatically
        ChatHandler.addMessage(msg.role, msg.text, false, false);
      });
    } else {
      // Add welcome message if no history
      console.log('👋 Adding welcome message (no history)');
      const welcomeMsg = `Halo! Dokumen "${doc.fileName}" berhasil diproses. Silakan tanyakan apapun tentang isi dokumen ini.`;
      ChatHandler.addMessage('bot', welcomeMsg);
      DocStorage.saveMessage(docId, 'bot', welcomeMsg);
    }
    
    // Enable input
    ChatHandler.enableInput(true);
    
    // Try to load PDF if file exists
    try {
      await this.loadPDFFromServer(doc.fileName);
    } catch (e) {
      console.warn('Could not load PDF preview:', e);
    }
    
    // Close sidebar on mobile
    if (STATE.isMobile) {
      this.closeSidebar();
    }
    
    console.log('✅ Switched to document:', doc.fileName);
  },
  
  async loadPDFFromServer(fileName) {
    // Try to fetch PDF from uploads folder
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/uploads/${encodeURIComponent(fileName)}`);
      if (response.ok) {
        const blob = await response.blob();
        const file = new File([blob], fileName, { type: 'application/pdf' });
        await PDFHandler.loadPDF(file);
      }
    } catch (e) {
      console.warn('PDF file not available for preview');
    }
  },
  
  deleteDocument(docId, fileName) {
    // Confirm deletion
    if (!confirm(`Hapus dokumen "${fileName}"?\n\nSemua riwayat chat akan dihapus.`)) {
      return;
    }
    
    // Delete from storage
    DocStorage.deleteDocument(docId);
    
    // Delete from server (optional - call API)
    this.deleteDocumentFromServer(docId).catch(e => console.warn('Server delete failed:', e));
    
    // If current document is deleted, reset to welcome screen
    if (STATE.docId === docId) {
      STATE.docId = null;
      STATE.chatId = null;
      STATE.currentPdfName = '';
      STATE.currentFileName = '';
      
      this.elements.chatInterface.classList.remove('active');
      this.elements.welcomeScreen.style.display = 'flex';
      ChatHandler.clearMessages();
      PDFHandler.reset();
    }
    
    // Re-render list
    this.renderChatList();
    
    this.showSuccess('Dokumen berhasil dihapus');
  },
  
  async deleteDocumentFromServer(docId) {
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/upload/${docId}`, {
        method: 'DELETE'
      });
      return response.ok;
    } catch (e) {
      console.error('Error deleting from server:', e);
      return false;
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