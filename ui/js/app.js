/**
 * RAG Chatbot Frontend - ChatPDF Style
 * Handles UI, API calls, session management
 */

let currentSessionId = null;
let currentDocId = null;  // Track selected document
let isLoading = false;
let documents = [];  // List of documents in current session
let lastUploadButtonClicked = 'ocr';  // Track which upload button was clicked (ocr or docstring)
let isUploading = false;  // Track if upload is in progress
let lastSessionsLoadTime = 0;  // Debounce loadSessions to prevent duplicates
let isLoadingSessions = false;  // Prevent concurrent loads

// ===== Storage Helpers =====
function saveCurrentSelection(sessionId, docId) {
    localStorage.setItem('lastSession', sessionId);
    localStorage.setItem(`lastDoc_${sessionId}`, docId);
    console.log(`[STORAGE] Saved: session=${sessionId}, doc=${docId}`);
}

function getLastSelection() {
    const lastSession = localStorage.getItem('lastSession');
    return lastSession ? {
        sessionId: lastSession,
        docId: localStorage.getItem(`lastDoc_${lastSession}`)
    } : null;
}


// Track which upload button was clicked
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

    // ===== Disclaimer Handler =====
    const disclaimerBtn = document.getElementById('disclaimerBtn');
    const disclaimerModal = document.getElementById('disclaimerModal');
    if (disclaimerBtn) {
        disclaimerBtn.addEventListener('click', () => {
            disclaimerModal.classList.add('show');
        });
    }
    if (disclaimerModal) {
        disclaimerModal.addEventListener('click', (e) => {
            if (e.target === disclaimerModal) {
                disclaimerModal.classList.remove('show');
            }
        });
    }

    // ===== Event Listeners =====
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            console.log('[JS] Upload button clicked!');
            lastUploadButtonClicked = 'ocr';
            openUploadModal();
        });
        console.log('[JS] Upload button listener attached');
    } else {
        console.error('[JS] uploadBtn not found!');
    }

    // ===== DOCSTRING UPLOAD BUTTON (NEW) =====
    const uploadDocstringBtn = document.getElementById('uploadDocstringBtn');
    if (uploadDocstringBtn) {
        uploadDocstringBtn.addEventListener('click', () => {
            console.log('[JS] DocString upload button clicked!');
            lastUploadButtonClicked = 'docstring';
            openUploadModal();
        });
        console.log('[JS] DocString upload button listener attached');
    } else {
        console.warn('[JS] uploadDocstringBtn not found (DocString API may not be configured)');
    }

    if (uploadArea) uploadArea.addEventListener('click', () => fileInputModal.click());
    if (fileInputModal) fileInputModal.addEventListener('change', (e) => {
        // Route to correct handler based on which button was clicked
        if (lastUploadButtonClicked === 'docstring') {
            handleFileSelectDocstring(e.target.files[0]);
        } else {
            handleFileSelect(e.target.files[0]);
        }
    });
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
            // Route to correct handler based on which button was last clicked
            if (lastUploadButtonClicked === 'docstring') {
                handleFileSelectDocstring(e.dataTransfer.files[0]);
            } else {
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });
    }

    if (deleteBtn) deleteBtn.addEventListener('click', () => {
        if (currentSessionId && currentDocId) {
            deleteDocumentFromList(currentSessionId, currentDocId);
        }
    });
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
    
    // Jika upload masih berjalan, show loading toast
    if (isUploading) {
        showLoadingToast();
    }
}

async function handleFileSelect(file) {
    if (!file || file.type !== 'application/pdf') {
        alert('Please select a valid PDF file');
        return;
    }

    // Show progress
    uploadArea.style.display = 'none';
    uploadProgress.style.display = 'block';
    
    // Extract PDF metadata
    const fileSize = file.size;
    const fileName = file.name;
    let pageCount = '?';
    let pdfType = 'Unknown';
    
    try {
        // Use PDF.js to get page count
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        pageCount = pdf.numPages;
        
        // Estimate PDF type (scanned vs digital)
        // Try to detect text to determine if scanned or digital
        let hasText = false;
        try {
            const page = await pdf.getPage(1);
            const textContent = await page.getTextContent();
            hasText = textContent.items.length > 0;
        } catch (e) {
            hasText = false;
        }
        
        pdfType = hasText ? '📋 Digital PDF' : '📸 Scanned PDF';
        
    } catch (error) {
        console.error('Error reading PDF:', error);
        pageCount = '?';
        pdfType = 'PDF (unknown type)';
    }
    
    // Calculate estimate time
    let estimatedSeconds;
    
    if (lastUploadButtonClicked === 'docstring') {
        // DocString API timing is HIGHLY VARIABLE - cannot be predicted accurately
        // Actual data shows: 5 pages=82s, 4 pages=30s, 12 pages=126s
        // Formulas don't work - use safe conservative estimate for all DocString uploads
        estimatedSeconds = 90; // Safe default: 1.5 minutes
    } else {
        // OCR timing (Tesseract + RAG + chunking)
        if (pageCount === '?') {
            estimatedSeconds = 60;  // Conservative estimate for unknown
        } else if (pdfType.includes('Scanned')) {
            estimatedSeconds = Math.ceil(pageCount * 5.5) + 5; // 5.5 sec/page + 5 sec overhead
        } else {
            estimatedSeconds = Math.ceil(pageCount * 2) + 3; // 2 sec/page + 3 sec overhead
        }
    }
    
    const estimatedTime = estimatedSeconds < 60 
        ? `~${estimatedSeconds} detik` 
        : `~${Math.ceil(estimatedSeconds / 60)} menit`;
    
    // Update upload info display
    const uploadInfo = document.getElementById('uploadInfo');
    if (uploadInfo) {
        document.getElementById('infoFileName').textContent = fileName;
        document.getElementById('infoPages').textContent = `${pageCount} halaman`;
        document.getElementById('infoPdfType').textContent = pdfType;
        document.getElementById('infoEstimate').textContent = estimatedTime;
        uploadInfo.style.display = 'block';
    }
    
    // Animate progress bar
    const progressFill = document.querySelector('.progress-fill');
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 30;
        if (progress > 90) progress = 90;
        progressFill.style.width = progress + '%';
    }, 300);
    
    uploadStatus.textContent = 'Uploading PDF...';

    // Set upload flag
    isUploading = true;

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
            const docId = data.doc_id;
            
            // Clear old chat history for this doc (if it was deleted before)
            const chatKey = `chat_${sessionId}_${docId}`;
            localStorage.removeItem(chatKey);
            console.log(`[handleFileSelect] Cleared old chat history: ${chatKey}`);
            
            uploadStatus.textContent = 'Processing PDF...';
            updateToastProgress(60, 'Processing with OCR...');

            // Wait untuk ingest complete
            const result = await waitForSessionReady(sessionId);
            
            clearInterval(interval);
            
            if (result && result.success) {
                progressFill.style.width = '100%';
                uploadStatus.textContent = 'Done! ✓';
                updateToastProgress(100, 'Upload complete!');
                isUploading = false;
                
                // Close modal dan load session
                setTimeout(() => {
                    closeUploadModal();
                    removeToastAfterSuccess();
                    loadSessions();
                    selectSession(sessionId, result.summary);
                }, 500);
            } else {
                alert('Processing timeout (3min). PDF may still be processing.\nYou can try refreshing or selecting the PDF from the list.');
                isUploading = false;
                closeUploadModal();
                removeToastAfterSuccess();
                loadSessions();
            }
        } else {
            clearInterval(interval);
            isUploading = false;
            alert('Upload failed: ' + (data.error || 'Unknown error'));
            closeToast();
        }
    } catch (error) {
        clearInterval(interval);
        isUploading = false;
        alert('Upload error: ' + error.message);
        console.error(error);
        closeToast();
    } finally {
        progressFill.style.width = '0%';
        uploadArea.style.display = 'block';
        uploadProgress.style.display = 'none';
    }
}

// ===== DOCSTRING FILE HANDLER (NEW) =====
async function handleFileSelectDocstring(file) {
    if (!file || file.type !== 'application/pdf') {
        alert('Please select a valid PDF file');
        return;
    }

    // Show progress
    uploadArea.style.display = 'none';
    uploadProgress.style.display = 'block';
    
    // Extract PDF metadata (same as existing)
    const fileSize = file.size;
    const fileName = file.name;
    let pageCount = '?';
    let pdfType = 'Unknown';
    
    try {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        pageCount = pdf.numPages;
        
        let hasText = false;
        try {
            const page = await pdf.getPage(1);
            const textContent = await page.getTextContent();
            hasText = textContent.items.length > 0;
        } catch (e) {
            hasText = false;
        }
        
        pdfType = hasText ? '📋 Digital PDF' : '📸 Scanned PDF';
    } catch (error) {
        console.error('Error reading PDF:', error);
        pageCount = '?';
        pdfType = 'PDF (unknown type)';
    }
    
    // Estimate time - DocString API timing is HIGHLY VARIABLE and unpredictable
    // Cannot use formula-based estimates due to inconsistent performance
    // Use safe fixed estimate for all DocString uploads
    let estimatedSeconds = 90; // Safe default: 1.5 minutes
    
    const estimatedTime = estimatedSeconds < 60 
        ? `~${estimatedSeconds} detik` 
        : `~${Math.ceil(estimatedSeconds / 60)} menit`;
    
    // Update upload info display
    const uploadInfo = document.getElementById('uploadInfo');
    if (uploadInfo) {
        document.getElementById('infoFileName').textContent = fileName;
        document.getElementById('infoPages').textContent = `${pageCount} halaman`;
        document.getElementById('infoPdfType').textContent = pdfType;
        document.getElementById('infoEstimate').textContent = estimatedTime;
        uploadInfo.style.display = 'block';
    }
    
    // Animate progress bar
    const progressFill = document.querySelector('.progress-fill');
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 30;
        if (progress > 90) progress = 90;
        progressFill.style.width = progress + '%';
    }, 300);
    
    uploadStatus.textContent = 'Uploading dengan DocString...';

    // Set upload flag
    isUploading = true;

    try {
        const formData = new FormData();
        formData.append('file', file);

        // Upload to /api/upload-docstring (DocString endpoint)
        const response = await fetch('/api/upload-docstring', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            const sessionId = data.session_id;
            const docId = data.doc_id;
            
            const chatKey = `chat_${sessionId}_${docId}`;
            localStorage.removeItem(chatKey);
            
            uploadStatus.textContent = 'Processing dengan DocString AI...';
            updateToastProgress(60, 'Processing with DocString API...');

            const result = await waitForSessionReady(sessionId);
            
            clearInterval(interval);
            
            if (result && result.success) {
                progressFill.style.width = '100%';
                uploadStatus.textContent = 'Done! ✓';
                updateToastProgress(100, 'Upload complete!');
                isUploading = false;
                
                setTimeout(() => {
                    closeUploadModal();
                    removeToastAfterSuccess();
                    loadSessions();
                    selectSession(sessionId, result.summary);
                }, 500);
            } else {
                alert('Processing timeout (3min). PDF may still be processing.');
                isUploading = false;
                closeUploadModal();
                removeToastAfterSuccess();
                loadSessions();
            }
        } else {
            clearInterval(interval);
            isUploading = false;
            alert('Upload failed: ' + (data.error || 'Unknown error'));
            closeToast();
        }
    } catch (error) {
        clearInterval(interval);
        isUploading = false;
        alert('Upload error: ' + error.message);
        console.error(error);
        closeToast();
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
    // Debounce: prevent calling too frequently to avoid duplicates
    const now = Date.now();
    if (isLoadingSessions || (now - lastSessionsLoadTime) < 500) {
        console.log(`[loadSessions] Skipping - already loading or called too recently`);
        return;
    }
    
    isLoadingSessions = true;
    lastSessionsLoadTime = now;
    
    try {
        // Load all documents from all sessions
        const response = await fetch('/api/sessions');
        const data = await response.json();

        if (!data.success) {
            sessionsList.innerHTML = '<div class="empty-state"><p>Error loading documents</p></div>';
            return;
        }

        if (data.sessions.length === 0) {
            sessionsList.innerHTML = '<div class="empty-state"><p>No PDFs uploaded yet</p></div>';
            return;
        }

        // CLEAR before repopulating
        sessionsList.innerHTML = '';

        // For each session, load and display its documents
        for (const session of data.sessions) {
            try {
                const docsResponse = await fetch(`/api/documents/${session.session_id}`);
                const docsData = await docsResponse.json();
                
                if (docsData.success && docsData.documents.length > 0) {
                    // Display each document as a clickable item
                    docsData.documents.forEach(doc => {
                        const item = document.createElement('div');
                        item.className = 'session-item';
                        item.setAttribute('data-session', session.session_id);
                        item.setAttribute('data-doc', doc.doc_id);
                        
                        if (currentSessionId === session.session_id && currentDocId === doc.doc_id) {
                            item.classList.add('active');
                        }

                        const uploadDate = new Date(doc.upload_time || session.upload_time);
                        const dateStr = uploadDate.toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                        });

                        item.innerHTML = `
                            <div style="flex: 1;">
                                <div class="session-name">${doc.filename}</div>
                                <div class="session-date">${dateStr}</div>
                            </div>
                            <button class="btn-delete-doc" data-session="${session.session_id}" data-doc="${doc.doc_id}" title="Delete document">
                                🗑️
                            </button>
                        `;

                        // Click to select document
                        item.addEventListener('click', (e) => {
                            if (!e.target.classList.contains('btn-delete-doc')) {
                                selectDocument(doc.doc_id, session.session_id, doc.filename);
                            }
                        });

                        sessionsList.appendChild(item);
                    });
                }
            } catch (err) {
                console.error(`Error loading documents for session ${session.session_id}:`, err);
            }
        }

        // Add delete button listeners (attach AFTER rendering all documents)
        document.querySelectorAll('.btn-delete-doc').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const sessionId = btn.getAttribute('data-session');
                const docId = btn.getAttribute('data-doc');
                await deleteDocumentFromList(sessionId, docId);
            });
        });

        // Auto-select first document if none selected
        if (!currentSessionId && data.sessions.length > 0) {
            const firstSession = data.sessions[0];
            const docsResponse = await fetch(`/api/documents/${firstSession.session_id}`);
            const docsData = await docsResponse.json();
            if (docsData.success && docsData.documents.length > 0) {
                selectDocument(docsData.documents[0].doc_id, firstSession.session_id, docsData.documents[0].filename);
            }
        }
    } catch (error) {
        console.error('Load sessions error:', error);
    } finally {
        isLoadingSessions = false;
    }
}

async function deleteDocumentFromList(sessionId, docId) {
    // Get document name from the item element
    const itemElement = document.querySelector(`[data-session="${sessionId}"][data-doc="${docId}"]`);
    const docName = itemElement ? itemElement.querySelector('.session-name').textContent : docId;
    
    if (!confirm(`Delete "${docName}"?\n\nThis will delete:\n- PDF file\n- All chunks and embeddings\n- All chat history\n\nThis cannot be undone!`)) {
        return;
    }

    try {
        console.log(`[deleteDocumentFromList] Deleting: session=${sessionId}, doc=${docId}`);
        isLoading = true;
        updateStatus('deleting');
        
        const response = await fetch(`/api/delete-document/${sessionId}/${docId}`, {
            method: 'DELETE'
        });

        console.log(`[deleteDocumentFromList] Response status: ${response.status}`);
        const data = await response.json();
        console.log(`[deleteDocumentFromList] Response data:`, data);

        if (data.success) {
            console.log(`[✓] Document deleted successfully`);
            
            // Clear chat history for deleted document
            const chatKey = `chat_${sessionId}_${docId}`;
            localStorage.removeItem(chatKey);
            console.log(`[✓] Cleared chat history: ${chatKey}`);
            
            // If deleted current document, clear display
            if (currentSessionId === sessionId && currentDocId === docId) {
                currentDocId = null;
                currentPdfName.textContent = 'Select a PDF';
                chatMessages.innerHTML = '<div class="empty-state"><p>PDF deleted. Select another PDF to chat.</p></div>';
                pdfViewer.innerHTML = '<div class="empty-state"><div style="font-size: 48px; margin-bottom: 10px;">🗑️</div><h3>PDF Deleted</h3><p>Select another PDF or upload a new one</p></div>';
                chatInput.disabled = true;
                sendBtn.disabled = true;
                deleteBtn.style.display = 'none';
            }
            
            // Wait a moment for backend to complete
            await new Promise(r => setTimeout(r, 500));
            
            // Reload sessions/documents list
            console.log(`[*] Reloading sessions after delete`);
            await loadSessions();
        } else {
            const errorMsg = data.error || 'Failed to delete document';
            console.error(`[!] Delete failed: ${errorMsg}`);
            alert(`Delete failed: ${errorMsg}`);
        }
    } catch (error) {
        console.error(`[!] Delete error:`, error);
        alert(`Delete error: ${error.message}`);
    } finally {
        isLoading = false;
        updateStatus('ready');
    }
}

function loadChatHistory(sessionId, docId) {
    /**
     * Restore chat history from localStorage - PER DOCUMENT
     * This REPLACES current chat with history for specific document
     */
    const key = `chat_${sessionId}_${docId}`;
    const history = localStorage.getItem(key);
    
    console.log(`[loadChatHistory] Loading chat for session: ${sessionId}, doc: ${docId}, key: ${key}`);
    
    // ALWAYS clear current chat when switching doc
    chatMessages.innerHTML = '';
    
    if (history) {
        try {
            const messages = JSON.parse(history);
            messages.forEach(msg => {
                addMessage(msg.text, msg.role, false); // Don't save again
            });
            chatMessages.scrollTop = chatMessages.scrollHeight;
            console.log(`[loadChatHistory] Loaded ${messages.length} messages for doc ${docId}`);
        } catch (e) {
            console.error('Failed to restore chat history:', e);
            chatMessages.innerHTML = '<div class="empty-state"><p>Select a PDF and start asking questions</p></div>';
        }
    } else {
        chatMessages.innerHTML = '<div class="empty-state"><p>Select a PDF and start asking questions</p></div>';
        console.log(`[loadChatHistory] No chat history found for doc ${docId}`);
    }
}

function saveChatHistory(sessionId, docId) {
    /**
     * Save chat history to localStorage - PER DOCUMENT
     */
    const key = `chat_${sessionId}_${docId}`;
    const messages = [];
    
    chatMessages.querySelectorAll('.chat-message').forEach(msg => {
        const role = msg.classList.contains('user-message') ? 'user' : 'assistant';
        const text = msg.querySelector('.message-content')?.textContent || msg.textContent;
        messages.push({ role, text });
    });
    
    localStorage.setItem(key, JSON.stringify(messages));
    console.log(`[saveChatHistory] Saved ${messages.length} messages for session: ${sessionId}, doc: ${docId}`);
}


async function selectDocument(docId, sessionId = null, docFilename = null) {
    /**
     * Switch to a different document and reload PDF
     */
    
    // If sessionId not provided, use current
    if (!sessionId) {
        sessionId = currentSessionId;
    }
    if (!sessionId) {
        console.error('[selectDocument] No session ID available');
        return;
    }
    
    console.log(`[selectDocument] Switching to session=${sessionId}, doc=${docId}`);
    
    // FIRST: Save chat history for PREVIOUS document
    if (currentSessionId && currentDocId && (currentSessionId !== sessionId || currentDocId !== docId)) {
        console.log(`[selectDocument] Saving chat for previous doc: ${currentDocId}`);
        saveChatHistory(currentSessionId, currentDocId);
    }
    
    // THEN: Update current selection
    currentSessionId = sessionId;
    currentDocId = docId;
    
    if (docFilename) {
        currentPdfName.textContent = docFilename;
    }
    
    // Save selection to localStorage
    saveCurrentSelection(sessionId, docId);
    
    // Update active state in list
    document.querySelectorAll('.session-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeItem = document.querySelector(`[data-session="${sessionId}"][data-doc="${docId}"]`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
    
    // Clear old PDF first
    pdfViewer.innerHTML = '<div class="empty-state"><p>Loading PDF...</p></div>';
    
    // Load chat history for THIS specific document
    loadChatHistory(sessionId, docId);
    
    // Load PDF content
    await loadPdfContent(sessionId, docId);
    
    // Enable chat
    chatInput.disabled = false;
    sendBtn.disabled = false;
    deleteBtn.style.display = 'block';
    
    console.log(`📄 Switched to: ${docFilename || docId}`);
}

async function deleteDocument(sessionId, docId) {
    /**
     * Delete a document and all its data (including chat)
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
        
        // DELETE chat history for this document from localStorage
        const chatKey = `chat_${sessionId}_${docId}`;
        localStorage.removeItem(chatKey);
        console.log(`[deleteDocument] Deleted chat history key: ${chatKey}`);
        
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
            // Load fresh chat for the new document
            loadChatHistory(sessionId, currentDocId);
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

function formatMarkdownTables(text) {
    /**
     * Convert markdown pipe tables to HTML tables
     * Supports: | header | header |
     *           |--------|--------|
     *           | data   | data   |
     */
    const lines = text.split('\n');
    const tableRegex = /^\s*\|.*\|\s*$/;
    
    let result = [];
    let inTable = false;
    let tableLines = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        
        if (tableRegex.test(line)) {
            if (!inTable) {
                inTable = true;
                tableLines = [line];
            } else {
                tableLines.push(line);
            }
        } else {
            if (inTable && tableLines.length > 1) {
                // Convert accumulated table lines to HTML
                const htmlTable = convertTableLinesToHTML(tableLines);
                result.push(htmlTable);
                tableLines = [];
            }
            inTable = false;
            result.push(line);
        }
    }
    
    // Handle last table if exists
    if (inTable && tableLines.length > 1) {
        const htmlTable = convertTableLinesToHTML(tableLines);
        result.push(htmlTable);
    }
    
    return result.join('\n');
}

function convertTableLinesToHTML(tableLines) {
    /**
     * Convert markdown table lines to HTML table
     * Lines format: | col1 | col2 | col3 |
     */
    if (tableLines.length < 2) return tableLines.join('\n');
    
    // Parse headers (first line)
    const headerLine = tableLines[0];
    const headers = headerLine.split('|').map(h => h.trim()).filter(h => h);
    
    if (headers.length === 0) return tableLines.join('\n');
    
    // Skip separator line (line 1)
    // Parse data rows (line 2+)
    const rows = [];
    for (let i = 2; i < tableLines.length; i++) {
        const line = tableLines[i];
        if (!tableRegex.test(line)) break;
        
        const cells = line.split('|').map(c => c.trim()).filter(c => c);
        if (cells.length > 0) {
            // Pad cells to match header count
            while (cells.length < headers.length) {
                cells.push('');
            }
            rows.push(cells.slice(0, headers.length));
        }
    }
    
    if (rows.length === 0) return tableLines.join('\n');
    
    // Build HTML table with proper escaping
    let html = '<table><thead><tr>';
    headers.forEach(h => {
        const escaped = escapeHtml(h).replace(/\s+/g, ' ');
        html += `<th>${escaped}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    rows.forEach(row => {
        html += '<tr>';
        for (let i = 0; i < headers.length; i++) {
            const cell = (row[i] || '').trim();
            const escaped = escapeHtml(cell).replace(/\s+/g, ' ');
            html += `<td>${escaped}</td>`;
        }
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    return html;
}

const tableRegex = /^\s*\|.*\|\s*$/;

function addMessage(text, sender, save = true) {
    const msg = document.createElement('div');
    msg.className = `message ${sender}`;
    
    // Add proper message structure
    if (sender === 'user') {
        msg.className = 'chat-message user-message';
    } else {
        msg.className = 'chat-message assistant-message';
    }
    
    // Convert markdown tables to HTML before displaying
    const formattedText = formatMarkdownTables(text);
    
    // Check if text contains HTML table (don't escape it)
    const hasTable = formattedText.includes('<table>');
    
    let contentHtml;
    if (hasTable) {
        // Text has table - use it as-is (already formatted)
        contentHtml = formattedText;
    } else {
        // Regular text - escape it and convert line breaks to <br>
        contentHtml = escapeHtml(formattedText)
            .split('\n')
            .map(line => line.trim() ? line : '<br>')  // Keep empty lines as <br>
            .join('<br>');
    }
    
    msg.innerHTML = `
        <div class="message-content">${contentHtml}</div>
        <div class="message-time">${new Date().toLocaleTimeString()}</div>
    `;
    
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Save to localStorage - PER DOCUMENT
    if (save && currentSessionId && currentDocId) {
        saveChatHistory(currentSessionId, currentDocId);
    }
}

function updateStatus(status) {
    statusIndicator.textContent = status;
    statusIndicator.style.background = status === 'ready' ? '#e8f5e9' : status === 'thinking' ? '#fff3e0' : '#ffebee';
    statusIndicator.style.color = status === 'ready' ? '#2e7d32' : status === 'thinking' ? '#e65100' : '#c62828';
}

// ===== Toast Notification Functions =====
function showLoadingToast() {
    const toastContainer = document.getElementById('toastContainer');
    
    // Hapus toast lama jika ada
    const existingToast = document.getElementById('uploadToast');
    if (existingToast) {
        return; // Toast sudah ada, jangan buat yang baru
    }
    
    const toast = document.createElement('div');
    toast.id = 'uploadToast';
    toast.className = 'toast-notification';
    toast.innerHTML = `
        <div class="toast-header">
            <span class="toast-title">Uploading to RAG System</span>
            <button class="toast-close" onclick="closeToast()">×</button>
        </div>
        <div class="toast-status">
            <span class="toast-spinner"></span>
            <span id="toastStatusText">Processing with ${lastUploadButtonClicked === 'docstring' ? 'DocString API' : 'OCR'}...</span>
        </div>
        <div class="toast-progress">
            <div id="toastProgressBar" class="toast-progress-bar" style="width: 0%"></div>
        </div>
        <div id="toastPercent" class="toast-percent">0%</div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
}

function updateToastProgress(percent, status) {
    const progressBar = document.getElementById('toastProgressBar');
    const percentText = document.getElementById('toastPercent');
    const statusText = document.getElementById('toastStatusText');
    
    if (progressBar && percentText && statusText) {
        progressBar.style.width = percent + '%';
        percentText.textContent = percent + '%';
        statusText.textContent = status;
    }
}

function closeToast() {
    const toast = document.getElementById('uploadToast');
    if (toast) {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }
}

function removeToastAfterSuccess() {
    // Wait a bit before closing for user feedback
    setTimeout(() => {
        closeToast();
    }, 2000);
}

// ===== Initialization =====
loadSessions();
// DO NOT auto-refresh - it causes chat history to reload multiple times
// Only refresh manually after upload/delete
