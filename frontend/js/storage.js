// ============= INDEXEDDB STORAGE (Client-side CDN) =============
const StorageManager = {
  dbName: 'PDFChatStorage',
  dbVersion: 1,
  db: null,

  // Helper: Generic transaction wrapper
  _transaction(storeName, mode, operation) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction([storeName], mode);
      const store = tx.objectStore(storeName);
      const request = operation(store);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },

  // Helper: Create object store
  _createStore(db, name, keyPath, indexField) {
    if (!db.objectStoreNames.contains(name)) {
      const store = db.createObjectStore(name, { keyPath });
      store.createIndex(indexField, indexField, { unique: false });
      console.log(`📦 Created "${name}" object store`);
    }
  },

  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        console.log('✅ IndexedDB initialized');
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        this._createStore(db, 'pdfs', 'id', 'filename');
        this._createStore(db, 'sessions', 'id', 'timestamp');
        this._createStore(db, 'chats', 'sessionId', 'timestamp');
      };
    });
  },

  // ============ PDF Storage (CDN-like) ============
  async savePDF(pdfData) {
    const record = {
      id: pdfData.docId,
      filename: pdfData.filename,
      blob: pdfData.blob,
      url: pdfData.url,
      timestamp: Date.now()
    };
    await this._transaction('pdfs', 'readwrite', store => store.put(record));
    console.log('💾 PDF saved:', pdfData.filename);
    return record;
  },

  async getPDF(docId) {
    const result = await this._transaction('pdfs', 'readonly', store => store.get(docId));
    if (result) console.log('📄 PDF loaded:', result.filename);
    return result || null;
  },

  async deletePDF(docId) {
    await this._transaction('pdfs', 'readwrite', store => store.delete(docId));
    console.log('🗑️ PDF deleted');
  },

  // ============ Session Storage ============
  async saveSession(sessionData) {
    const record = {
      id: sessionData.sessionId,
      docId: sessionData.docId,
      filename: sessionData.filename,
      pdfUrl: sessionData.pdfUrl,
      timestamp: Date.now()
    };
    await this._transaction('sessions', 'readwrite', store => store.put(record));
    console.log('💾 Session saved');
    return record;
  },

  async getSession(sessionId) {
    return await this._transaction('sessions', 'readonly', store => store.get(sessionId));
  },

  // ============ Chat History Storage ============
  async saveChatHistory(sessionId, messages) {
    const record = { sessionId, messages, timestamp: Date.now() };
    await this._transaction('chats', 'readwrite', store => store.put(record));
    console.log('💾 Chat history saved');
    return record;
  },

  async getChatHistory(sessionId) {
    const result = await this._transaction('chats', 'readonly', store => store.get(sessionId));
    if (result) {
      console.log(`💬 Chat history loaded: ${result.messages.length} messages`);
      return result.messages;
    }
    return [];
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
  async clearOldData(maxAge = 7 * 24 * 60 * 60 * 1000) {
    const now = Date.now();
    const stores = ['pdfs', 'sessions', 'chats'];
    
    stores.forEach(storeName => {
      const tx = this.db.transaction([storeName], 'readwrite');
      const store = tx.objectStore(storeName);
      const request = store.openCursor();

      request.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          if (now - cursor.value.timestamp > maxAge) {
            cursor.delete();
            console.log(`🗑️ Deleted old ${storeName}:`, cursor.value.id || cursor.value.sessionId);
          }
          cursor.continue();
        }
      };
    });
  },

  // Get storage usage info
  async getStorageInfo() {
    if (navigator.storage && navigator.storage.estimate) {
      const estimate = await navigator.storage.estimate();
      const used = (estimate.usage / 1024 / 1024).toFixed(2);
      const quota = (estimate.quota / 1024 / 1024).toFixed(2);
      const percentage = ((estimate.usage / estimate.quota) * 100).toFixed(1);
      console.log(`💾 Storage: ${used}MB / ${quota}MB (${percentage}%)`);
      return { used, quota, percentage: parseFloat(percentage) };
    }
    return null;
  }
};
