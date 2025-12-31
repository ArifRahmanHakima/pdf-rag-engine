/**
 * Status Monitor JavaScript
 * Handles real-time status monitoring for PDF processing
 * User-friendly UI with blocking during processing
 */

class StatusMonitor {
    constructor() {
        this.statusModal = null;
        this.statusCheckInterval = null;
        this.isProcessing = false;
        this.currentDocId = null;
        this.initModal();
    }

    initModal() {
        // Create modal HTML if it doesn't exist
        if (!document.getElementById('statusModal')) {
            const modalHTML = `
                <div id="statusModal" class="status-modal">
                    <div class="status-modal-content">
                        <div class="status-header">
                            <h2><span class="header-icon">📄</span> Memproses PDF</h2>
                            <span class="close-status" id="closeStatusBtn">&times;</span>
                        </div>
                        
                        <div id="statusContent">
                            <!-- Warning Banner -->
                            <div class="warning-banner" id="warningBanner">
                                <span>⏳</span>
                                <span>Mohon tunggu sebentar ya...</span>
                            </div>
                            
                            <!-- Processing Animation -->
                            <div class="processing-animation" id="processingAnimation">
                                <div class="spinner-container">
                                    <div class="spinner"></div>
                                    <div class="spinner-icon" id="spinnerIcon">📄</div>
                                </div>
                                <div class="processing-text" id="processingText">Sedang membaca PDF...</div>
                            </div>
                            
                            <!-- Progress Section -->
                            <div class="progress-section" id="progressSection">
                                <div class="progress-bar">
                                    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                                </div>
                            </div>
                            
                            <!-- Status Message -->
                            <div class="status-message-box info" id="statusMessageBox">
                                <span class="message-icon">💡</span>
                                <span id="statusMessage">Sedang mempersiapkan dokumen Anda...</span>
                            </div>
                            
                            <!-- Completion State (Hidden by default) -->
                            <div class="completion-state hidden" id="completionState">
                                <div class="completion-icon" id="completionIcon">✅</div>
                                <div class="completion-title" id="completionTitle">Selesai!</div>
                                <div class="completion-subtitle" id="completionSubtitle">PDF siap untuk ditanyakan</div>
                                <div class="completion-actions">
                                    <button class="action-btn primary" id="startChatBtn">
                                        <span>💬</span> Mulai Tanya
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }

        this.statusModal = document.getElementById('statusModal');
        this.bindEvents();
    }

    bindEvents() {
        const closeBtn = document.getElementById('closeStatusBtn');
        const startChatBtn = document.getElementById('startChatBtn');
        
        // Close button - only works when not processing
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            if (!this.isProcessing) {
                this.closeModal();
            }
        };
        
        startChatBtn.onclick = () => {
            this.closeModal();
            const chatInput = document.getElementById('chatInput');
            if (chatInput) chatInput.focus();
        };

        // Block clicking outside modal during processing
        this.statusModal.onclick = (e) => {
            if (e.target === this.statusModal && !this.isProcessing) {
                this.closeModal();
            }
        };

        // Block ESC key during processing
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.statusModal.style.display === 'block') {
                if (!this.isProcessing) {
                    this.closeModal();
                }
                e.preventDefault();
            }
        });
    }

    showModal(docId) {
        this.currentDocId = docId;
        this.resetModalState();
        this.statusModal.style.display = 'block';
        this.setProcessingState(true);
        this.startStatusCheck(docId);
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        this.statusModal.style.display = 'none';
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }
        document.body.style.overflow = '';
    }

    resetModalState() {
        // Show processing elements
        document.getElementById('processingAnimation').classList.remove('hidden');
        document.getElementById('progressSection').classList.remove('hidden');
        document.getElementById('statusMessageBox').classList.remove('hidden');
        document.getElementById('warningBanner').classList.remove('hidden');
        
        // Hide completion state
        document.getElementById('completionState').classList.add('hidden');
        
        // Reset values
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('spinnerIcon').textContent = '📄';
        document.getElementById('processingText').textContent = 'Sedang membaca PDF...';
        
        // Reset message box
        const messageBox = document.getElementById('statusMessageBox');
        messageBox.className = 'status-message-box info';
        document.getElementById('statusMessage').textContent = 'Sedang mempersiapkan dokumen Anda...';
    }

    setProcessingState(isProcessing) {
        this.isProcessing = isProcessing;
        const closeBtn = document.getElementById('closeStatusBtn');
        
        if (isProcessing) {
            closeBtn.classList.remove('enabled');
        } else {
            closeBtn.classList.add('enabled');
        }
    }

    startStatusCheck(docId) {
        this.statusCheckInterval = setInterval(() => {
            this.updateStatus(docId);
        }, 1500);
        this.updateStatus(docId);
    }

    async updateStatus(docId) {
        try {
            const response = await fetch(`/upload/status/${docId}`);
            const data = await response.json();

            // Update progress bar only
            const progress = data.progress || 0;
            document.getElementById('progressFill').style.width = progress + '%';

            // Update stage info
            this.updateStageInfo(data.current_stage);

            // Update message
            this.updateMessage(data);

            // Handle completion or failure
            if (data.status === 'completed') {
                this.handleCompletion(true);
            } else if (data.status === 'failed') {
                this.handleCompletion(false, data.message);
            }

        } catch (error) {
            console.error('Error checking status:', error);
            document.getElementById('statusMessage').textContent = 'Maaf, terjadi kesalahan. Silakan coba lagi.';
            document.getElementById('statusMessageBox').className = 'status-message-box error';
        }
    }

    updateStageInfo(stage) {
        const stageInfo = {
            'Text Extraction': { icon: '📄', text: 'Sedang membaca PDF...' },
            'Chunking': { icon: '✂️', text: 'Sedang memproses...' },
            'Embedding': { icon: '🧠', text: 'Hampir selesai...' },
            'Indexing': { icon: '📊', text: 'Sedikit lagi...' },
            'Completed': { icon: '✅', text: 'Selesai!' }
        };

        const info = stageInfo[stage] || { icon: '⏳', text: 'Mohon tunggu...' };
        
        document.getElementById('spinnerIcon').textContent = info.icon;
        document.getElementById('processingText').textContent = info.text;
    }

    updateMessage(data) {
        const messageBox = document.getElementById('statusMessageBox');
        const messageText = document.getElementById('statusMessage');
        
        const messages = {
            'Text Extraction': '💡 Sedang membaca dokumen Anda...',
            'Chunking': '💡 Mempersiapkan isi dokumen...',
            'Embedding': '💡 AI sedang mempelajari dokumen...',
            'Indexing': '💡 Hampir selesai, tunggu sebentar...',
            'Completed': '✨ Selesai! Dokumen siap ditanyakan'
        };

        messageText.textContent = messages[data.current_stage] || data.message || 'Mohon tunggu sebentar...';
        
        if (data.status === 'completed') {
            messageBox.className = 'status-message-box success';
        } else if (data.status === 'failed') {
            messageBox.className = 'status-message-box error';
        } else {
            messageBox.className = 'status-message-box info';
        }
    }

    handleCompletion(success, errorMessage = '') {
        clearInterval(this.statusCheckInterval);
        this.setProcessingState(false);

        // Hide processing elements
        document.getElementById('processingAnimation').classList.add('hidden');
        document.getElementById('progressSection').classList.add('hidden');
        document.getElementById('statusMessageBox').classList.add('hidden');
        document.getElementById('warningBanner').classList.add('hidden');

        // Show completion state
        const completionState = document.getElementById('completionState');
        completionState.classList.remove('hidden');

        if (success) {
            document.getElementById('completionIcon').textContent = '✅';
            document.getElementById('completionTitle').textContent = 'Selesai!';
            document.getElementById('completionSubtitle').textContent = 'PDF siap untuk ditanyakan';
            document.getElementById('startChatBtn').innerHTML = '<span>💬</span> Mulai Tanya';
        } else {
            document.getElementById('completionIcon').textContent = '❌';
            document.getElementById('completionTitle').textContent = 'Gagal';
            document.getElementById('completionSubtitle').textContent = errorMessage || 'Maaf, terjadi kesalahan. Silakan coba lagi.';
            document.getElementById('startChatBtn').innerHTML = '<span>🔄</span> Coba Lagi';
            document.getElementById('startChatBtn').onclick = () => {
                this.closeModal();
                document.getElementById('newChatBtn')?.click();
            };
        }
    }
}

// Initialize status monitor globally
const statusMonitor = new StatusMonitor();
