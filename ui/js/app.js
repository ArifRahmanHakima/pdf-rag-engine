/**
 * RAG Chatbot Frontend - ChatPDF Style
 * Handles UI, API calls, session management
 */

let currentSessionId = null;
let currentDocId = null;  // Track selected document
let isLoading = false;
let documents = [];  // List of documents in current session

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
    // Scanned PDF (OCR): ~5-6 sec/page (Tesseract + RAG + chunking)
    // Digital PDF: ~2 sec/page (RAG + chunking)
    let estimatedSeconds;
    if (pageCount === '?') {
        estimatedSeconds = 90;  // Conservative estimate
    } else if (pdfType.includes('Scanned')) {
        estimatedSeconds = Math.ceil(pageCount * 5.5) + 5; // 5.5 sec/page + 5 sec overhead for chunking
    } else {
        estimatedSeconds = Math.ceil(pageCount * 2) + 3; // 2 sec/page + 3 sec overhead
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
    console.log(`[selectSession] Switching to session: ${sessionId} (from ${currentSessionId})`);
    
    // CRITICAL: Clear old doc selection when switching session
    // This prevents using doc from previous session
    currentSessionId = sessionId;
    currentDocId = null;
    
    // Clear chat history when switching session
    chatMessages.innerHTML = '';
    
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
                
                // Load documents FIRST to set currentDocId properly for NEW session
                await loadDocuments(sessionId);
                console.log(`[selectSession] After loadDocuments, currentDocId: ${currentDocId}, documents: ${documents.length}`);
                
                // THEN restore chat history for this specific document
                if (currentDocId) {
                    loadChatHistory(sessionId, currentDocId);
                }
                
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
        let selectedDoc = data.selected_doc;  // From backend (already validated)
        
        console.log(`[loadDocuments] Found ${documents.length} docs, backend selected: ${selectedDoc}`);
        
        // Show documents list in left sidebar
        const documentsList = document.getElementById('documentsList');
        const docsContainer = document.getElementById('docsContainer');
        
        if (!documentsList || !docsContainer) {
            console.error('[loadDocuments] documentsList or docsContainer not found!');
            return;
        }
        
        if (documents.length > 0) {
            documentsList.style.display = 'block';
            docsContainer.innerHTML = '';  // Clear completely
            
            documents.forEach(doc => {
                const docItem = document.createElement('div');
                docItem.className = 'doc-item';
                
                // Determine if this should be active
                // Priority: backend selected > localStorage > first doc
                const isSelected = doc.doc_id === selectedDoc;
                if (isSelected) {
                    docItem.classList.add('active');
                    currentDocId = doc.doc_id;
                    saveCurrentSelection(sessionId, doc.doc_id);  // Save to localStorage
                }
                
                docItem.innerHTML = `
                    <div class="doc-name">${doc.filename}</div>
                    <div class="doc-meta">${doc.pages} pages</div>
                `;
                
                docItem.addEventListener('click', () => {
                    console.log(`[loadDocuments click] Clicked doc: ${doc.doc_id}`);
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
                saveCurrentSelection(sessionId, currentDocId);  // Save to localStorage
                console.log(`[loadDocuments] Set currentDocId to first doc: ${currentDocId}`);
            }
            console.log(`[loadDocuments] Final currentDocId: ${currentDocId}`);
        } else {
            // NO documents - hide the section completely and clear
            documentsList.style.display = 'none';
            docsContainer.innerHTML = '';
            currentDocId = null;
            console.log(`[loadDocuments] No documents, hiding list`);
        }
    } catch (error) {
        console.error('Load documents error:', error);
    }
}

async function selectDocument(docId) {
    /**
     * Switch to a different document and reload PDF
     */
    console.log(`[selectDocument] Switching from doc: ${currentDocId} to doc: ${docId}`);
    
    // FIRST: Save chat history for PREVIOUS document (use old docId!)
    if (currentSessionId && currentDocId && currentDocId !== docId) {
        console.log(`[selectDocument] Saving chat for previous doc: ${currentDocId}`);
        saveChatHistory(currentSessionId, currentDocId);
    }
    
    // THEN: Update to new document
    currentDocId = docId;
    
    // Save selection to localStorage
    if (currentSessionId) {
        saveCurrentSelection(currentSessionId, docId);
    }
    
    // Clear old PDF first
    pdfViewer.innerHTML = '<div class="empty-state"><p>Loading PDF...</p></div>';
    
    // Update server about document selection
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
    
    // Load chat history for THIS specific document
    loadChatHistory(currentSessionId, docId);
    
    // THEN reload PDF with new document (now currentDocId is properly set to new doc)
    await loadPdfContent(currentSessionId);
    
    console.log(`📄 Switched to document: ${docId}`);
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
    if (!currentSessionId || !currentDocId) return;

    if (!confirm('Are you sure you want to delete this PDF and all related data?')) return;

    try {
        // Delete from backend (chunks, embeddings, file)
        const response = await fetch(`/api/delete-document/${currentSessionId}/${currentDocId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            // Clear local chat history for this document
            const chatKey = `chat_${currentSessionId}_${currentDocId}`;
            localStorage.removeItem(chatKey);
            console.log(`[deleteDocument] Cleared chat history: ${chatKey}`);

            // Reset current document
            currentDocId = null;
            currentPdfName.textContent = 'Select a PDF';
            chatMessages.innerHTML = '<div class="empty-state"><p>Select a PDF to chat</p></div>';
            pdfViewer.innerHTML = '<div class="empty-state"><div style="font-size: 48px; margin-bottom: 10px;">📄</div><h3>No PDF selected</h3></div>';
            chatInput.disabled = true;
            sendBtn.disabled = true;
            deleteBtn.style.display = 'none';

            // Reload documents and sessions
            await loadDocuments(currentSessionId);
            
            // If no documents left in session, reload sessions
            if (documents.length === 0) {
                loadSessions();
            } else {
                // Select first available document
                selectDocument(documents[0].doc_id);
            }
        } else {
            alert('Failed to delete: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('Failed to delete document');
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
    
    msg.innerHTML = `
        <div class="message-content">${formattedText}</div>
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

// ===== Initialization =====
loadSessions();
setInterval(loadSessions, 5000); // Refresh sessions every 5s
