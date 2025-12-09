// ============= INDEXEDDB STORAGE (Client-side CDN) =============
const StorageManager = {
  dbName: 'PDFChatStorage',
  dbVersion: 1,
  db: null,

  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);

      request.onerror = () => {
        console.error('❌ IndexedDB error:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        console.log('✅ IndexedDB initialized');
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // Store for PDF files (binary data)
        if (!db.objectStoreNames.contains('pdfs')) {
          const pdfStore = db.createObjectStore('pdfs', { keyPath: 'id' });
          pdfStore.createIndex('filename', 'filename', { unique: false });
          console.log('📦 Created "pdfs" object store');
        }

        // Store for session data
        if (!db.objectStoreNames.contains('sessions')) {
          const sessionStore = db.createObjectStore('sessions', { keyPath: 'id' });
          sessionStore.createIndex('timestamp', 'timestamp', { unique: false });
          console.log('📦 Created "sessions" object store');
        }

        // Store for chat history
        if (!db.objectStoreNames.contains('chats')) {
          const chatStore = db.createObjectStore('chats', { keyPath: 'sessionId' });
          chatStore.createIndex('timestamp', 'timestamp', { unique: false });
          console.log('📦 Created "chats" object store');
        }
      };
    });
  },

  // ============ PDF Storage (CDN-like) ============
  async savePDF(pdfData) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pdfs'], 'readwrite');
      const store = transaction.objectStore('pdfs');

      const pdfRecord = {
        id: pdfData.docId,
        filename: pdfData.filename,
        blob: pdfData.blob,
        url: pdfData.url,
        timestamp: Date.now()
      };

      const request = store.put(pdfRecord);

      request.onsuccess = () => {
        console.log('💾 PDF saved to IndexedDB:', pdfData.filename);
        resolve(pdfRecord);
      };

      request.onerror = () => {
        console.error('❌ Failed to save PDF:', request.error);
        reject(request.error);
      };
    });
  },

  async getPDF(docId) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pdfs'], 'readonly');
      const store = transaction.objectStore('pdfs');
      const request = store.get(docId);

      request.onsuccess = () => {
        if (request.result) {
          console.log('📄 PDF loaded from IndexedDB:', request.result.filename);
          resolve(request.result);
        } else {
          console.log('ℹ️ PDF not found in IndexedDB');
          resolve(null);
        }
      };

      request.onerror = () => {
        console.error('❌ Failed to get PDF:', request.error);
        reject(request.error);
      };
    });
  },

  async deletePDF(docId) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['pdfs'], 'readwrite');
      const store = transaction.objectStore('pdfs');
      const request = store.delete(docId);

      request.onsuccess = () => {
        console.log('🗑️ PDF deleted from IndexedDB');
        resolve();
      };

      request.onerror = () => {
        console.error('❌ Failed to delete PDF:', request.error);
        reject(request.error);
      };
    });
  },

  // ============ Session Storage ============
  async saveSession(sessionData) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['sessions'], 'readwrite');
      const store = transaction.objectStore('sessions');

      const sessionRecord = {
        id: sessionData.sessionId,
        docId: sessionData.docId,
        filename: sessionData.filename,
        pdfUrl: sessionData.pdfUrl,
        timestamp: Date.now()
      };

      const request = store.put(sessionRecord);

      request.onsuccess = () => {
        console.log('💾 Session saved to IndexedDB');
        resolve(sessionRecord);
      };

      request.onerror = () => {
        console.error('❌ Failed to save session:', request.error);
        reject(request.error);
      };
    });
  },

  async getSession(sessionId) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['sessions'], 'readonly');
      const store = transaction.objectStore('sessions');
      const request = store.get(sessionId);

      request.onsuccess = () => {
        resolve(request.result || null);
      };

      request.onerror = () => {
        console.error('❌ Failed to get session:', request.error);
        reject(request.error);
      };
    });
  },

  // ============ Chat History Storage ============
  async saveChatHistory(sessionId, messages) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['chats'], 'readwrite');
      const store = transaction.objectStore('chats');

      const chatRecord = {
        sessionId: sessionId,
        messages: messages,
        timestamp: Date.now()
      };

      const request = store.put(chatRecord);

      request.onsuccess = () => {
        console.log('💾 Chat history saved to IndexedDB');
        resolve(chatRecord);
      };

      request.onerror = () => {
        console.error('❌ Failed to save chat history:', request.error);
        reject(request.error);
      };
    });
  },

  async getChatHistory(sessionId) {
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction(['chats'], 'readonly');
      const store = transaction.objectStore('chats');
      const request = store.get(sessionId);

      request.onsuccess = () => {
        if (request.result) {
          console.log(`💬 Chat history loaded: ${request.result.messages.length} messages`);
          resolve(request.result.messages);
        } else {
          resolve([]);
        }
      };

      request.onerror = () => {
        console.error('❌ Failed to get chat history:', request.error);
        reject(request.error);
      };
    });
  },

  async addChatMessage(sessionId, role, content) {
    try {
      const history = await this.getChatHistory(sessionId);
      history.push({ role, content, timestamp: Date.now() });
      await this.saveChatHistory(sessionId, history);
    } catch (error) {
      console.error('❌ Failed to add chat message:', error);
    }
  },

  // ============ Cleanup ============
  async clearOldData(maxAge = 7 * 24 * 60 * 60 * 1000) { // 7 days default
    const now = Date.now();
    
    // Clean old PDFs
    const pdfTx = this.db.transaction(['pdfs'], 'readwrite');
    const pdfStore = pdfTx.objectStore('pdfs');
    const pdfRequest = pdfStore.openCursor();

    pdfRequest.onsuccess = (event) => {
      const cursor = event.target.result;
      if (cursor) {
        if (now - cursor.value.timestamp > maxAge) {
          cursor.delete();
          console.log('🗑️ Deleted old PDF:', cursor.value.filename);
        }
        cursor.continue();
      }
    };

    // Clean old sessions
    const sessionTx = this.db.transaction(['sessions'], 'readwrite');
    const sessionStore = sessionTx.objectStore('sessions');
    const sessionRequest = sessionStore.openCursor();

    sessionRequest.onsuccess = (event) => {
      const cursor = event.target.result;
      if (cursor) {
        if (now - cursor.value.timestamp > maxAge) {
          cursor.delete();
          console.log('🗑️ Deleted old session:', cursor.value.id);
        }
        cursor.continue();
      }
    };

    // Clean old chats
    const chatTx = this.db.transaction(['chats'], 'readwrite');
    const chatStore = chatTx.objectStore('chats');
    const chatRequest = chatStore.openCursor();

    chatRequest.onsuccess = (event) => {
      const cursor = event.target.result;
      if (cursor) {
        if (now - cursor.value.timestamp > maxAge) {
          cursor.delete();
          console.log('🗑️ Deleted old chat:', cursor.value.sessionId);
        }
        cursor.continue();
      }
    };
  },

  // Get storage usage info
  async getStorageInfo() {
    if (navigator.storage && navigator.storage.estimate) {
      const estimate = await navigator.storage.estimate();
      const used = (estimate.usage / 1024 / 1024).toFixed(2);
      const quota = (estimate.quota / 1024 / 1024).toFixed(2);
      console.log(`💾 Storage: ${used}MB / ${quota}MB (${((estimate.usage / estimate.quota) * 100).toFixed(1)}%)`);
      return { used, quota, percentage: (estimate.usage / estimate.quota) * 100 };
    }
    return null;
  }
};
