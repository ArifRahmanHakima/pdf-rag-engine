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
                                <span>⚠️</span>
                                <span>Mohon tunggu, jangan tutup halaman ini.</span>
                            </div>
                            
                            <!-- Processing Animation -->
                            <div class="processing-animation" id="processingAnimation">
                                <div class="spinner-container">
                                    <div class="spinner"></div>
                                    <div class="spinner-icon" id="spinnerIcon">📄</div>
                                </div>
                                <div class="processing-text" id="processingText">Sedang Memproses...</div>
                                <div class="processing-stage" id="processingStage">Mengekstrak teks dari PDF</div>
                            </div>
                            
                            <!-- Progress Section -->
                            <div class="progress-section" id="progressSection">
                                <div class="progress-header">
                                    <span class="progress-label">Progress</span>
                                    <span class="progress-percent" id="progressPercent">0%</span>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                                </div>
                            </div>
                            
                            <!-- Time Remaining -->
                            <div class="time-remaining" id="timeRemaining">
                                <div class="time-icon">⏱️</div>
                                <div class="time-value" id="timeValue">--</div>
                                <div class="time-label">detik lagi</div>
                            </div>
                            
                            <!-- Status Message -->
                            <div class="status-message-box info" id="statusMessageBox">
                                <span class="message-icon">💡</span>
                                <span id="statusMessage">Mempersiapkan dokumen...</span>
                            </div>
                            
                            <!-- Completion State (Hidden by default) -->
                            <div class="completion-state hidden" id="completionState">
                                <div class="completion-icon" id="completionIcon">✅</div>
                                <div class="completion-title" id="completionTitle">Proses Selesai!</div>
                                <div class="completion-subtitle" id="completionSubtitle">Dokumen siap digunakan untuk chat</div>
                                <div class="completion-actions">
                                    <button class="action-btn primary" id="startChatBtn">
                                        <span>💬</span> Mulai Chat
                                    </button>
                                    <button class="action-btn secondary" id="closeModalBtn">
                                        Tutup
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
        const closeModalBtn = document.getElementById('closeModalBtn');
        const startChatBtn = document.getElementById('startChatBtn');
        
        // Close button - only works when not processing
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            if (!this.isProcessing) {
                this.closeModal();
            }
        };

        closeModalBtn.onclick = () => this.closeModal();
        
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
        document.getElementById('timeRemaining').classList.remove('hidden');
        document.getElementById('statusMessageBox').classList.remove('hidden');
        document.getElementById('warningBanner').classList.remove('hidden');
        
        // Hide completion state
        document.getElementById('completionState').classList.add('hidden');
        
        // Reset values
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressPercent').textContent = '0%';
        document.getElementById('timeValue').textContent = '--';
        document.getElementById('spinnerIcon').textContent = '📄';
        document.getElementById('processingText').textContent = 'Sedang Memproses...';
        document.getElementById('processingStage').textContent = 'Mengekstrak teks dari PDF';
        
        // Reset message box
        const messageBox = document.getElementById('statusMessageBox');
        messageBox.className = 'status-message-box info';
        document.getElementById('statusMessage').textContent = 'Mempersiapkan dokumen...';
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

            // Update progress
            const progress = data.progress || 0;
            document.getElementById('progressFill').style.width = progress + '%';
            document.getElementById('progressPercent').textContent = progress + '%';

            // Update stage info
            this.updateStageInfo(data.current_stage);

            // Update time remaining
            this.updateTimeRemaining(data);

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
            document.getElementById('statusMessage').textContent = 'Error: ' + error.message;
            document.getElementById('statusMessageBox').className = 'status-message-box error';
        }
    }

    updateStageInfo(stage) {
        const stageInfo = {
            'Text Extraction': { icon: '📄', text: 'Mengekstrak Teks', desc: 'Membaca konten dari file PDF...' },
            'Chunking': { icon: '✂️', text: 'Memecah Dokumen', desc: 'Membagi dokumen menjadi bagian kecil...' },
            'Embedding': { icon: '🧠', text: 'Membuat Embedding', desc: 'Mengkonversi teks ke vektor...' },
            'Indexing': { icon: '📊', text: 'Menyimpan Data', desc: 'Menyimpan ke database RAG...' },
            'Completed': { icon: '✅', text: 'Selesai!', desc: 'Dokumen siap digunakan' }
        };

        const info = stageInfo[stage] || { icon: '⏳', text: 'Memproses...', desc: stage || 'Mohon tunggu...' };
        
        document.getElementById('spinnerIcon').textContent = info.icon;
        document.getElementById('processingText').textContent = info.text;
        document.getElementById('processingStage').textContent = info.desc;
    }

    updateTimeRemaining(data) {
        const timeValueEl = document.getElementById('timeValue');
        
        if (data.status === 'processing' && data.start_time && data.progress > 5) {
            const elapsed = (Date.now() / 1000) - data.start_time;
            const estimatedTotal = elapsed / (data.progress / 100);
            const remaining = Math.max(0, Math.ceil(estimatedTotal - elapsed));
            
            if (remaining > 60) {
                const mins = Math.floor(remaining / 60);
                const secs = remaining % 60;
                timeValueEl.textContent = `${mins}m ${secs}s`;
            } else if (remaining > 0) {
                timeValueEl.textContent = remaining;
            } else {
                timeValueEl.textContent = '< 5';
            }
        } else if (data.progress <= 5) {
            timeValueEl.textContent = 'Menghitung...';
        }
    }

    updateMessage(data) {
        const messageBox = document.getElementById('statusMessageBox');
        const messageText = document.getElementById('statusMessage');
        
        const messages = {
            'Text Extraction': '💡 Sedang membaca isi dokumen PDF Anda...',
            'Chunking': '💡 Memecah dokumen agar mudah dicari...',
            'Embedding': '💡 AI sedang memahami konteks dokumen...',
            'Indexing': '💡 Menyimpan untuk pencarian cepat...',
            'Completed': '✨ Dokumen berhasil diproses!'
        };

        messageText.textContent = messages[data.current_stage] || data.message || 'Memproses dokumen...';
        
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
        document.getElementById('timeRemaining').classList.add('hidden');
        document.getElementById('statusMessageBox').classList.add('hidden');
        document.getElementById('warningBanner').classList.add('hidden');

        // Show completion state
        const completionState = document.getElementById('completionState');
        completionState.classList.remove('hidden');

        if (success) {
            document.getElementById('completionIcon').textContent = '✅';
            document.getElementById('completionTitle').textContent = 'Proses Selesai!';
            document.getElementById('completionSubtitle').textContent = 'Dokumen siap digunakan untuk chat';
            document.getElementById('startChatBtn').innerHTML = '<span>💬</span> Mulai Chat';
        } else {
            document.getElementById('completionIcon').textContent = '❌';
            document.getElementById('completionTitle').textContent = 'Proses Gagal';
            document.getElementById('completionSubtitle').textContent = errorMessage || 'Terjadi kesalahan saat memproses dokumen';
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
