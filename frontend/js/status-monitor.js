/**
 * Status Monitor JavaScript
 * Handles real-time status monitoring for PDF processing
 */

class StatusMonitor {
    constructor() {
        this.statusModal = null;
        this.statusCheckInterval = null;
        this.initModal();
    }

    initModal() {
        // Create modal HTML if it doesn't exist
        if (!document.getElementById('statusModal')) {
            const modalHTML = `
                <div id="statusModal" class="status-modal">
                    <div class="status-modal-content">
                        <div class="status-header">
                            <h2>Status Pemrosesan PDF</h2>
                            <span class="close-status">&times;</span>
                        </div>
                        
                        <div id="statusContent">
                            <div class="status-item">
                                <div class="status-label">Status:</div>
                                <span id="statusBadge" class="status-badge pending">Pending</span>
                            </div>
                            
                            <div class="status-item">
                                <div class="status-label">Tahap Proses:</div>
                                <div class="status-value" id="currentStage">Idle</div>
                            </div>
                            
                            <div class="status-item">
                                <div class="status-label">Progress:</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" id="progressFill" style="width: 0%">
                                        <span id="progressPercent">0%</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="status-item">
                                <div class="status-label">Pesan:</div>
                                <div id="statusMessage" class="status-message">Menunggu proses dimulai...</div>
                            </div>
                            
                            <div class="status-item">
                                <div class="status-label">Document ID:</div>
                                <div class="status-value" id="docIdValue">-</div>
                            </div>
                            
                            <div class="status-item">
                                <div class="status-label">Estimasi Waktu:</div>
                                <div class="estimated-time" id="estimatedTime">Menghitung...</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }

        this.statusModal = document.getElementById('statusModal');
        const closeBtn = document.querySelector('.close-status');
        
        closeBtn.onclick = () => {
            this.closeModal();
        };

        window.onclick = (event) => {
            if (event.target === this.statusModal) {
                this.closeModal();
            }
        };
    }

    showModal(docId) {
        this.statusModal.style.display = 'block';
        document.getElementById('docIdValue').textContent = docId;
        this.startStatusCheck(docId);
    }

    closeModal() {
        this.statusModal.style.display = 'none';
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }
    }

    startStatusCheck(docId) {
        // Cek status setiap 2 detik
        this.statusCheckInterval = setInterval(() => {
            this.updateStatus(docId);
        }, 2000);
        
        // Update langsung saat pertama kali
        this.updateStatus(docId);
    }

    async updateStatus(docId) {
        try {
            const response = await fetch(`/upload/status/${docId}`);
            const data = await response.json();

            // Update badge
            const statusBadge = document.getElementById('statusBadge');
            statusBadge.textContent = this.translateStatus(data.status);
            statusBadge.className = `status-badge ${data.status}`;

            // Update tahap proses
            document.getElementById('currentStage').textContent = data.current_stage;

            // Update progress bar
            const progressFill = document.getElementById('progressFill');
            const progressPercent = document.getElementById('progressPercent');
            progressFill.style.width = data.progress + '%';
            progressPercent.textContent = data.progress + '%';

            // Update message
            const statusMessage = document.getElementById('statusMessage');
            statusMessage.textContent = data.message;
            statusMessage.className = 'status-message';
            
            if (data.status === 'completed') {
                statusMessage.classList.add('success');
            } else if (data.status === 'failed') {
                statusMessage.classList.add('error');
            }

            // Update estimated time
            this.updateEstimatedTime(data);

            // Stop checking jika sudah selesai
            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(this.statusCheckInterval);
            }
        } catch (error) {
            console.error('Error checking status:', error);
            const statusMessage = document.getElementById('statusMessage');
            statusMessage.textContent = 'Error memeriksa status: ' + error.message;
            statusMessage.className = 'status-message error';
        }
    }

    updateEstimatedTime(data) {
        const estimatedTimeEl = document.getElementById('estimatedTime');
        
        if (data.status === 'processing') {
            const elapsed = (Date.now() / 1000) - data.start_time;
            const estimatedTotal = elapsed / (data.progress / 100);
            const remaining = estimatedTotal - elapsed;
            
            if (remaining > 0) {
                estimatedTimeEl.textContent = `Sisa waktu: ~${Math.ceil(remaining)} detik (Total: ~${Math.ceil(estimatedTotal)}s)`;
            }
        } else if (data.status === 'completed' && data.completed_time) {
            const totalTime = data.completed_time - data.start_time;
            estimatedTimeEl.textContent = `Selesai dalam ${totalTime.toFixed(2)} detik`;
        }
    }

    translateStatus(status) {
        const translations = {
            'pending': 'Menunggu',
            'processing': 'Sedang Diproses',
            'completed': 'Selesai',
            'failed': 'Gagal'
        };
        return translations[status] || status;
    }
}

// Initialize status monitor globally
const statusMonitor = new StatusMonitor();
