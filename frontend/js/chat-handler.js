// ============= CHAT HANDLER MODULE =============
const ChatHandler = {
  elements: {
    messages: null,
    input: null,
    sendBtn: null,
    processingIndicator: null,
    fastBtn: null,
    qualityBtn: null
  },

  currentMode: 'quality', // 'fast' or 'quality'

  init() {
    this.elements.messages = document.getElementById('chatMessages');
    this.elements.input = document.getElementById('chatInput');
    this.elements.sendBtn = document.getElementById('sendBtn');
    this.elements.processingIndicator = document.getElementById('processingIndicator');
    this.elements.fastBtn = document.getElementById('fastBtn');
    this.elements.qualityBtn = document.getElementById('qualityBtn');

    this.attachEvents();
    
    // No need to load session here - handled by UIHandler.restoreSession()
  },

  loadSession() {
    // Legacy method - now handled by UIHandler.restoreSession()
    console.log('ℹ️ loadSession() called - session restore handled by backend');
  },

  attachEvents() {
    this.elements.sendBtn.addEventListener('click', () => this.sendMessage());

    this.elements.input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    this.elements.input.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });

    this.elements.fastBtn.addEventListener('click', () => this.setMode('fast'));
    this.elements.qualityBtn.addEventListener('click', () => this.setMode('quality'));

    this.elements.messages.addEventListener('click', () => {
      this.elements.input.focus();
    });
  },

  setMode(mode) {
    this.currentMode = mode;

    if (mode === 'fast') {
      this.elements.fastBtn.classList.add('active');
      this.elements.qualityBtn.classList.remove('active');
    } else {
      this.elements.fastBtn.classList.remove('active');
      this.elements.qualityBtn.classList.add('active');
    }
  },

  async sendMessage() {
    const question = this.elements.input.value.trim();
    if (!question) return;

    // Tambahkan pesan user
    this.addMessage('user', question);
    this.elements.input.value = '';
    this.elements.input.style.height = 'auto';

    // Tampilkan bubble bot loading
    this.addBotLoadingBubble();

    this.elements.sendBtn.disabled = true;

    try {
      const params = new URLSearchParams({
        question: question,
        doc_id: STATE.docId,
        user_id: STATE.userId,
        mode: this.currentMode
      });

      if (STATE.chatId) {
        params.append('chat_id', STATE.chatId);
      }

      const response = await fetch(`${CONFIG.API_BASE_URL}/chat/send?${params.toString()}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Id': STATE.sessionId  // Send session ID
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.chat_id) {
        STATE.chatId = data.chat_id;
        console.log('💬 Chat ID:', data.chat_id);
      }

      this.removeBotLoadingBubble();

      if (data.answer) {
        await Utils.sleep(300);
        this.addMessage('bot', data.answer);
        
        // Save bot message to IndexedDB CDN
        await StorageManager.addChatMessage(STATE.sessionId, 'bot', data.answer);
      } else {
        throw new Error('Tidak ada jawaban dari server');
      }

    } catch (error) {
      this.removeBotLoadingBubble();
      this.addMessage('bot', 'Maaf, terjadi kesalahan: ' + error.message);
    } finally {
      this.elements.sendBtn.disabled = false;
      this.elements.input.focus();
    }
  },

  addMessage(role, text, skipSave = false) {
    const message = document.createElement('div');
    message.className = `message ${role}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'bot' ? '🤖' : '👤';

    const content = document.createElement('div');
    content.className = 'message-content';

    if (role === 'bot') {
      content.innerHTML = marked.parse(text);
    } else {
      content.textContent = text;
    }

    message.appendChild(avatar);
    message.appendChild(content);
    this.elements.messages.appendChild(message);

    this.scrollToBottom();
    
    // Save user message to IndexedDB CDN only if not restoring
    if (role === 'user' && !skipSave) {
      StorageManager.addChatMessage(STATE.sessionId, 'user', text).catch(err => {
        console.error('Failed to save message to IndexedDB:', err);
      });
    }
  },

  // ✅ TAMBAHAN: animasi bubble loading bot
  addBotLoadingBubble() {
    const bubble = document.createElement('div');
    bubble.className = 'message bot-message loading-bubble';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🤖';

    const content = document.createElement('div');
    content.className = 'message-content';
    content.innerHTML = `
      <span class="typing-loader">
        <span>.</span><span>.</span><span>.</span>
      </span>
    `;

    bubble.appendChild(avatar);
    bubble.appendChild(content);
    bubble.id = "loadingBubble";

    this.elements.messages.appendChild(bubble);
    this.scrollToBottom();
  },

  removeBotLoadingBubble() {
    const bubble = document.getElementById("loadingBubble");
    if (bubble) bubble.remove();
  },
  
  scrollToBottom() {
    this.elements.messages.scrollTo({
      top: this.elements.messages.scrollHeight,
      behavior: 'smooth'
    });
  },

  async showProcessing() {
    this.elements.processingIndicator.classList.add('active');

    for (let i = 0; i < CONFIG.PROCESSING_STEPS.length; i++) {
      const step = CONFIG.PROCESSING_STEPS[i];
      const stepEl = document.getElementById(step.id);

      document.querySelectorAll('.process-step').forEach(s => {
        s.classList.remove('active', 'completed');
      });

      stepEl.classList.add('active');
      await Utils.sleep(step.duration);

      stepEl.classList.remove('active');
      stepEl.classList.add('completed');

      if (i < CONFIG.PROCESSING_STEPS.length - 1) {
        await Utils.sleep(300);
      }
    }

    await Utils.sleep(500);
    this.elements.processingIndicator.classList.remove('active');

    document.querySelectorAll('.process-step').forEach(s => {
      s.classList.remove('active', 'completed');
    });
  },

  clearMessages() {
    this.elements.messages.innerHTML = '';
    STATE.chatId = null;
  },

  enableInput(enable = true) {
    this.elements.input.disabled = !enable;
    this.elements.sendBtn.disabled = !enable;

    if (enable) {
      this.elements.input.focus();
    }
  }
};
