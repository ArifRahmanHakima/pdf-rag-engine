/**
 * RAG Chatbot Frontend - ChatPDF Style
 * Handles UI, API calls, session management
 */

let currentSessionId = null;
let currentDocId = null;  // Track selected document
let isLoading = false;
let documents = [];  // List of documents in current session

// ===== DOM Elements =====
let uploadBtn, fileInputModal, uploadModal, uploadArea, uploadProgress, uploadStatus, modalClose;
let sessionsList, currentPdfName, deleteBtn, pdfViewer;
let chatMessages, chatInput, sendBtn, statusIndicator;

// Wait for DOM to load
document.addEventListener('DOMContentLoaded', () => {
    console.log('[JS] DOM loaded, initializing...');
    
    // Initialize DOM references
    uploadBtn = document.getElementById('uploadBtn');
    fileInputModal = document.getElementById('fileInputModal');
    uploadModal = document.getElementById('uploadModal');
    uploadArea = document.getElementById('uploadArea');
    uploadProgress = document.getElementById('uploadProgress');
    uploadStatus = document.getElementById('uploadStatus');
    modalClose = document.querySelector('.modal-close');

    sessionsList = document.getElementById('sessionsList');
    currentPdfName = document.getElementById('currentPdfName');
    deleteBtn = document.getElementById('deleteBtn');
    pdfViewer = document.getElementById('pdfViewer');

    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendBtn = document.getElementById('sendBtn');
    statusIndicator = document.getElementById('statusIndicator');

    console.log('[JS] Elements loaded:', { uploadBtn, uploadModal, uploadArea });

    // ===== Event Listeners =====
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            console.log('[JS] Upload button clicked!');
            openUploadModal();
        });
        console.log('[JS] Upload button listener attached');
    } else {
        console.error('[JS] uploadBtn not found!');
    }
    if (uploadArea) uploadArea.addEventListener('click', () => fileInputModal.click());
    if (fileInputModal) fileInputModal.addEventListener('change', (e) => handleFileSelect(e.target.files[0]));
    if (modalClose) modalClose.addEventListener('click', closeUploadModal);
    if (uploadModal) uploadModal.addEventListener('click', (e) => {
        if (e.target === uploadModal) closeUploadModal();
    });

    // Drag and drop
    if (uploadArea) {
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFileSelect(e.dataTransfer.files[0]);
        });
    }

    if (deleteBtn) deleteBtn.addEventListener('click', deleteCurrentSession);
    if (chatInput) chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !isLoading && currentSessionId) {
            sendMessage();
        }
    });
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);

    // Load sessions on startup
    loadSessions();
});

// ===== Upload Handling =====
function openUploadModal() {
    uploadModal.classList.add('show');
    uploadProgress.style.display = 'none';
}

function closeUploadModal() {
    uploadModal.classList.remove('show');
    fileInputModal.value = '';
}

async function handleFileSelect(file) {
    if (!file || file.type !== 'application/pdf') {
        alert('Please select a valid PDF file');
        return;
    }

    // Show progress
    uploadArea.style.display = 'none';
    uploadProgress.style.display = 'block';
    
    // Animate progress bar
    const progressFill = document.querySelector('.progress-fill');
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 30;
        if (progress > 90) progress = 90;
        progressFill.style.width = progress + '%';
    }, 300);
    
    uploadStatus.textContent = 'Uploading PDF...';

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            const sessionId = data.session_id;
            
            uploadStatus.textContent = 'Processing PDF...';

            // Wait untuk ingest complete
            const result = await waitForSessionReady(sessionId);
            
            clearInterval(interval);
            
            if (result && result.success) {
                progressFill.style.width = '100%';
                uploadStatus.textContent = 'Done! ✓';
                
                // Close modal dan load session
                setTimeout(() => {
                    closeUploadModal();
                    loadSessions();
                    selectSession(sessionId, result.summary);
                }, 500);
            } else {
                alert('Processing timeout (3min). PDF may still be processing.\nYou can try refreshing or selecting the PDF from the list.');
                closeUploadModal();
                loadSessions();
            }
        } else {
            clearInterval(interval);
            alert('Upload failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        clearInterval(interval);
        alert('Upload error: ' + error.message);
        console.error(error);
    } finally {
        progressFill.style.width = '0%';
        uploadArea.style.display = 'block';
        uploadProgress.style.display = 'none';
    }
}

async function waitForSessionReady(sessionId, maxRetries = 180, retryInterval = 1000) {
    /**
     * Poll /api/status endpoint untuk track ingest progress
     * maxRetries: up to 180 seconds (3 minutes) untuk PDF kompleks
     */
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(`/api/status/${sessionId}`);
            const data = await response.json();

            if (!data.success) {
                console.error('Status check failed:', data.error);
                return false;
            }

            const statusInfo = data.status;
            const progress = data.progress;

            // Update progress text
            if (progress) {
                uploadStatus.textContent = `Uploading... ✓\n${progress}`;
            }

            // Check if ready
            if (statusInfo === 'ready') {
                console.log('Session ready!');
                return { success: true, summary: data.summary };
            } else if (statusInfo === 'error') {
                alert('Processing error: ' + (data.error || 'Unknown error'));
                return false;
            }

            // Still ingesting, continue polling
        } catch (error) {
            console.error('Error checking session status:', error);
            // Continue trying
        }

        // Wait before next retry
        await new Promise(resolve => setTimeout(resolve, retryInterval));
    }

    // Timeout
    console.warn('Session ready check timed out');
    return false;
}

// ===== Session Management =====
async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        const data = await response.json();

        if (!data.success) {
            sessionsList.innerHTML = '<div class="empty-state"><p>Error loading sessions</p></div>';
            return;
        }

        if (data.sessions.length === 0) {
            sessionsList.innerHTML = '<div class="empty-state"><p>No PDFs uploaded yet</p></div>';
            return;
        }

        // Clear list
        sessionsList.innerHTML = '';

        // Add sessions
        data.sessions.forEach(session => {
            const item = document.createElement('div');
            item.className = 'session-item';
            item.setAttribute('data-session', session.session_id);
            if (session.session_id === currentSessionId) {
                item.classList.add('active');
            }

            const uploadDate = new Date(session.upload_time);
            const dateStr = uploadDate.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            item.innerHTML = `
                <div class="session-name">${session.filename}</div>
                <div class="session-date">${dateStr}</div>
            `;

            item.addEventListener('click', () => selectSession(session.session_id));

            sessionsList.appendChild(item);
        });

        // Auto-select first PDF if none selected
        if (!currentSessionId && data.sessions.length > 0) {
            selectSession(data.sessions[0].session_id);
        }
    } catch (error) {
        console.error('Load sessions error:', error);
    }
}

async function selectSession(sessionId, initialSummary = null) {
    currentSessionId = sessionId;
    
    // Update active state
    document.querySelectorAll('.session-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Find and mark the clicked session as active
    const sessionItem = document.querySelector(`[data-session="${sessionId}"]`);
    if (sessionItem) {
        sessionItem.classList.add('active');
    }

    // Get session info
    fetch('/api/sessions')
        .then(r => r.json())
        .then(async data => {
            const session = data.sessions.find(s => s.session_id === sessionId);
            if (session) {
                currentPdfName.textContent = session.filename;
                
                // RESTORE chat history from localStorage instead of clearing
                loadChatHistory(sessionId);
                
                // Load documents FIRST to set currentDocId properly
                await loadDocuments(sessionId);
                console.log(`[selectSession] After loadDocuments, currentDocId: ${currentDocId}, documents: ${documents.length}`);
                
                // THEN load PDF with correct currentDocId
                await loadPdfContent(sessionId, initialSummary);
                console.log(`[selectSession] After loadPdfContent`);
            }
        });

    // Enable chat
    chatInput.disabled = false;
    sendBtn.disabled = false;

    // Update delete button
    deleteBtn.style.display = 'block';
}

function loadChatHistory(sessionId) {
    /**
     * Restore chat history from localStorage
     */
    const key = `chat_${sessionId}`;
    const history = localStorage.getItem(key);
    
    if (history) {
        try {
            const messages = JSON.parse(history);
            chatMessages.innerHTML = '';
            messages.forEach(msg => {
                addMessage(msg.text, msg.role, false); // Don't save again
            });
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } catch (e) {
            console.error('Failed to restore chat history:', e);
            chatMessages.innerHTML = '<div class="empty-state"><p>Select a PDF and start asking questions</p></div>';
        }
    } else {
        chatMessages.innerHTML = '<div class="empty-state"><p>Select a PDF and start asking questions</p></div>';
    }
}

function saveChatHistory(sessionId) {
    /**
     * Save chat history to localStorage
     */
    const key = `chat_${sessionId}`;
    const messages = [];
    
    chatMessages.querySelectorAll('.chat-message').forEach(msg => {
        const role = msg.classList.contains('user-message') ? 'user' : 'assistant';
        const text = msg.querySelector('.message-content')?.textContent || msg.textContent;
        messages.push({ role, text });
    });
    
    localStorage.setItem(key, JSON.stringify(messages));
}

async function loadDocuments(sessionId) {
    /**
     * Load list of documents in this session and show in left sidebar
     */
    try {
        const response = await fetch(`/api/documents/${sessionId}`);
        const data = await response.json();
        
        if (!data.success) {
            console.error('Failed to load documents:', data.error);
            return;
        }
        
        documents = data.documents;
        const selectedDoc = data.selected_doc;
        
        console.log(`[loadDocuments] Found ${documents.length} docs, selected: ${selectedDoc}`);
        
        // Show documents list in left sidebar
        const documentsList = document.getElementById('documentsList');
        const docsContainer = document.getElementById('docsContainer');
        
        if (documents.length > 0) {
            documentsList.style.display = 'block';
            docsContainer.innerHTML = '';
            
            documents.forEach(doc => {
                const docItem = document.createElement('div');
                docItem.className = 'doc-item';
                
                // Determine if this should be active
                const isSelected = doc.doc_id === selectedDoc || (selectedDoc === null && documents[0].doc_id === doc.doc_id);
                if (isSelected) {
                    docItem.classList.add('active');
                    currentDocId = doc.doc_id;
                }
                
                docItem.innerHTML = `
                    <div class="doc-name">${doc.filename}</div>
                    <div class="doc-meta">${doc.pages} pages</div>
                    <button class="btn-delete-doc" title="Delete document" onclick="event.stopPropagation(); deleteDocument('${currentSessionId}', '${doc.doc_id}')">🗑️</button>
                `;
                
                docItem.addEventListener('click', () => {
                    selectDocument(doc.doc_id);
                    // Update active state
                    document.querySelectorAll('.doc-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    docItem.classList.add('active');
                });
                
                docsContainer.appendChild(docItem);
            });
            
            // Final sanity check: if currentDocId is still not set, use first doc
            if (!currentDocId && documents.length > 0) {
                currentDocId = documents[0].doc_id;
                console.log(`[loadDocuments] currentDocId not set, using first: ${currentDocId}`);
            }
            console.log(`[loadDocuments] Final currentDocId: ${currentDocId}`);
        } else {
            documentsList.style.display = 'none';
            currentDocId = null;
        }
    } catch (error) {
        console.error('Load documents error:', error);
    }
}

async function selectDocument(docId) {
    /**
     * Switch to a different document and reload PDF
     */
    currentDocId = docId;
    
    // Clear old PDF first
    pdfViewer.innerHTML = '<div class="empty-state"><p>Loading PDF...</p></div>';
    
    // Update server about document selection and wait for completion
    try {
        const response = await fetch(`/api/select-document/${currentSessionId}?doc_id=${docId}`, {
            method: 'POST'
        });
        if (!response.ok) {
            console.error('Select document failed');
            return;
        }
    } catch (err) {
        console.error('Select document error:', err);
        return;
    }
    
    // THEN reload PDF with new document (now currentDocId is properly set)
    await loadPdfContent(currentSessionId);
    
    console.log(`📄 Switched to document: ${docId}`);
}

async function deleteDocument(sessionId, docId) {
    /**
     * Delete a document and all its data
     */
    if (!confirm(`Delete document? All chunks, chat history, and PDF will be removed.`)) {
        return;
    }
    
    try {
        console.log(`[deleteDocument] Deleting doc: ${docId}`);
        
        const response = await fetch(`/api/delete-document/${sessionId}/${docId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (!data.success) {
            alert(`Error: ${data.error}`);
            return;
        }
        
        console.log(`[deleteDocument] Backend deletion successful`);
        
        // Clear current doc ID if it was deleted
        if (currentDocId === docId) {
            currentDocId = null;
            console.log(`[deleteDocument] Current doc was deleted, clearing currentDocId`);
        }
        
        // Reload documents list - this will also set currentDocId correctly
        await loadDocuments(sessionId);
        console.log(`[deleteDocument] After loadDocuments, currentDocId: ${currentDocId}`);
        
        // Load PDF if any documents remain
        if (documents.length > 0 && currentDocId) {
            console.log(`[deleteDocument] Loading PDF for doc: ${currentDocId}`);
            await loadPdfContent(sessionId);
        } else if (documents.length === 0) {
            // No documents left
            currentDocId = null;
            pdfViewer.innerHTML = '<div class="empty-state"><p>No documents uploaded yet</p><p style="font-size: 12px; color: #999;">Upload a PDF to start chatting</p></div>';
            chatMessages.innerHTML = '';
            console.log(`[deleteDocument] No documents left`);
        }
        
        console.log(`🗑️ Deleted document: ${docId}`);
    } catch (error) {
        console.error('Delete document error:', error);
        alert('Error deleting document');
    }
}

async function loadPdfContent(sessionId, initialSummary = null) {
    /**
     * Load PDF viewer and summary - ONLY if currentDocId is set
     */
    
    // Guard: don't load PDF if no document selected
    if (!currentDocId) {
        pdfViewer.innerHTML = '<div class="empty-state"><p>No document selected</p><p style="font-size: 12px; color: #999;">Select a document from the left to view PDF</p></div>';
        return;
    }
    
    try {
        const response = await fetch(`/api/status/${sessionId}`);
        const data = await response.json();

        if (!data.success) return;

        const status = data.status;
        const summary = initialSummary || data.summary;

        // Show summary in chat
        if (summary && status === 'ready') {
            const summaryMsg = document.createElement('div');
            summaryMsg.className = 'chat-message assistant-message';
            summaryMsg.innerHTML = `
                <div class="message-content">
                    <strong>📄 Document Summary:</strong><br>
                    ${summary}
                </div>
                <div class="message-time">${new Date().toLocaleTimeString()}</div>
            `;
            chatMessages.appendChild(summaryMsg);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Display PDF file in viewer - with explicit check for currentDocId
        if (!currentDocId) {
            pdfViewer.innerHTML = '<div class="empty-state"><p>No document selected</p></div>';
            return;
        }
        
        pdfViewer.innerHTML = `
            <iframe 
                src="/api/pdf/${sessionId}/${currentDocId}" 
                style="width: 100%; height: 100%; border: none; background: #f5f5f5;"
                type="application/pdf">
            </iframe>
        `;
    } catch (error) {
        console.error('Load PDF content error:', error);
        pdfViewer.innerHTML = `
            <div class="empty-state">
                <p>⚠️ Failed to load PDF</p>
                <p style="font-size: 12px; color: #999;">${error.message}</p>
            </div>
        `;
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

async function deleteCurrentSession() {
    if (!currentSessionId) return;

    if (!confirm('Are you sure you want to delete this PDF?')) return;

    try {
        const response = await fetch(`/api/sessions/${currentSessionId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            currentSessionId = null;
            currentPdfName.textContent = 'Select a PDF';
            chatMessages.innerHTML = '<div class="empty-state"><p>Select a PDF to chat</p></div>';
            pdfViewer.innerHTML = '<div class="empty-state"><div style="font-size: 48px; margin-bottom: 10px;">📄</div><h3>No PDF selected</h3></div>';
            chatInput.disabled = true;
            sendBtn.disabled = true;
            deleteBtn.style.display = 'none';

            loadSessions();
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('Failed to delete session');
    }
}

// ===== Chat =====
async function sendMessage() {
    const message = chatInput.value.trim();

    if (!message || !currentSessionId || !currentDocId || isLoading) return;

    // Add user message
    addMessage(message, 'user');
    chatInput.value = '';

    isLoading = true;
    updateStatus('thinking');
    
    // Add loading indicator
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'message assistant';
    loadingMsg.id = 'loading-msg';
    loadingMsg.textContent = '⏳ Processing...';
    chatMessages.appendChild(loadingMsg);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: currentSessionId,
                doc_id: currentDocId,  // Send selected document
                question: message
            })
        });

        const data = await response.json();

        // Remove loading message
        const loadingElement = document.getElementById('loading-msg');
        if (loadingElement) {
            loadingElement.remove();
        }

        if (data.success) {
            addMessage(data.answer, 'assistant');
            updateStatus('ready');
        } else {
            addMessage(`Error: ${data.error || 'Unknown error'}`, 'assistant');
            updateStatus('error');
        }
    } catch (error) {
        const loadingElement = document.getElementById('loading-msg');
        if (loadingElement) {
            loadingElement.remove();
        }
        addMessage('Error: ' + error.message, 'assistant');
        updateStatus('error');
        console.error(error);
    } finally {
        isLoading = false;
    }
}

function addMessage(text, sender, save = true) {
    const msg = document.createElement('div');
    msg.className = `message ${sender}`;
    
    // Add proper message structure
    if (sender === 'user') {
        msg.className = 'chat-message user-message';
    } else {
        msg.className = 'chat-message assistant-message';
    }
    
    msg.innerHTML = `
        <div class="message-content">${escapeHtml(text)}</div>
        <div class="message-time">${new Date().toLocaleTimeString()}</div>
    `;
    
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Save to localStorage
    if (save && currentSessionId) {
        saveChatHistory(currentSessionId);
    }
}

function updateStatus(status) {
    statusIndicator.textContent = status;
    statusIndicator.style.background = status === 'ready' ? '#e8f5e9' : status === 'thinking' ? '#fff3e0' : '#ffebee';
    statusIndicator.style.color = status === 'ready' ? '#2e7d32' : status === 'thinking' ? '#e65100' : '#c62828';
}

// ===== Initialization =====
loadSessions();
setInterval(loadSessions, 5000); // Refresh sessions every 5s
