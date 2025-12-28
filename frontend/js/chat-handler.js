const ChatHandler = {
  elements: {
    messages: null,
    input: null,
    sendBtn: null,
    processingIndicator: null,
    fastBtn: null,
    qualityBtn: null
  },

  currentMode: 'quality',

  init() {
    this.elements.messages = document.getElementById('chatMessages');
    this.elements.input = document.getElementById('chatInput');
    this.elements.sendBtn = document.getElementById('sendBtn');
    this.elements.processingIndicator = document.getElementById('processingIndicator');
    this.elements.fastBtn = document.getElementById('fastBtn');
    this.elements.qualityBtn = document.getElementById('qualityBtn');
    this.attachEvents();
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
    this.elements.fastBtn.classList.toggle('active', mode === 'fast');
    this.elements.qualityBtn.classList.toggle('active', mode === 'quality');
  },

async sendMessage() {
    const question = this.elements.input.value.trim();
    if (!question) return;

    // Check if PDF is loaded
    if (!STATE.docId) {
      UIHandler.showError('Silakan upload PDF terlebih dahulu!');
      return;
    }

    // Add user message
    this.addMessage('user', question);
    
    // Save user message to storage
    DocStorage.saveMessage(STATE.docId, 'user', question);
    
    this.elements.input.value = '';
    this.elements.input.style.height = 'auto';
    
    // Disable send button
    this.elements.sendBtn.disabled = true;
    
    // Show enhanced typing indicator
    const typingId = this.showEnhancedTypingIndicator();

    try {
      const params = new URLSearchParams({
        question: question,
        doc_id: STATE.docId,  // Gunakan doc_id yang sudah disimpan
        user_id: STATE.userId,
      });
      
      if (STATE.chatId) {
        params.append('chat_id', STATE.chatId);
      }
      
      const response = await fetch(`${CONFIG.API_BASE_URL}/chat/send?${params.toString()}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Remove typing indicator
      this.removeTypingIndicator(typingId);
      
      // Update chat ID from response
      if (data.chat_id) {
        STATE.chatId = data.chat_id;
        // Update chat ID in storage
        DocStorage.updateChatId(STATE.docId, data.chat_id);
      }
      
      // Add bot response with reveal animation
      if (data.answer) {
        await Utils.sleep(300); // Small delay for natural feel
        const answerHtml = Utils.parseMarkdown(data.answer);
        this.addMessage('bot', answerHtml, true, true); // true untuk HTML, true untuk reveal animation
        
        // Save bot message to storage (save raw text, not HTML)
        DocStorage.saveMessage(STATE.docId, 'bot', data.answer);
      } else {
        throw new Error('Tidak ada jawaban dari server');
      }
      
    } catch (error) {
      console.error('Error sending message:', error);
      this.removeTypingIndicator(typingId);
      const errorMsg = `❌ Maaf, terjadi kesalahan: ${error.message}`;
      this.addMessage('bot', errorMsg);
      DocStorage.saveMessage(STATE.docId, 'bot', errorMsg);
      UIHandler.showError(`Gagal mengirim pesan: ${error.message}`);
    } finally {
      this.elements.sendBtn.disabled = false;
      this.elements.input.focus();
    }
  },

  addMessage(role, text, isHtml = false, withReveal = false) {
    const message = document.createElement('div');
    message.className = `message ${role}-message`;
    
    if (withReveal) {
      message.classList.add('active');
    }
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'bot' ? '🤖' : '👤';
    
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content-wrapper';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    if (withReveal) {
      content.classList.add('revealing');
    }
    
    if (isHtml) {
      content.innerHTML = text;
    } else {
      content.textContent = text;
    }
    
    contentWrapper.appendChild(content);
    
    // Add copy button for bot messages
    if (role === 'bot') {
      const copyBtn = document.createElement('button');
      copyBtn.className = 'copy-message-btn';
      copyBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
        <span>Copy</span>
      `;
      copyBtn.onclick = () => this.copyMessage(content, copyBtn);
      contentWrapper.appendChild(copyBtn);
    }
    
    message.appendChild(avatar);
    message.appendChild(contentWrapper);
    this.elements.messages.appendChild(message);
    
    // Remove active class after animation
    if (withReveal) {
      setTimeout(() => {
        message.classList.remove('active');
      }, 2000);
    }
    
    // Smooth scroll to bottom
    this.scrollToBottom();
  },

  // Copy message to clipboard
  copyMessage(contentElement, buttonElement) {
    const text = contentElement.innerText || contentElement.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
      // Change button to show success
      buttonElement.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span>Copied!</span>
      `;
      buttonElement.classList.add('copied');
      
      // Reset after 2 seconds
      setTimeout(() => {
        buttonElement.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          <span>Copy</span>
        `;
        buttonElement.classList.remove('copied');
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy:', err);
      UIHandler.showError('Gagal menyalin teks');
    });
  },

  // Show suggested questions
  showSuggestedQuestions(questions) {
    const container = document.createElement('div');
    container.className = 'suggested-questions';
    
    const title = document.createElement('div');
    title.className = 'suggested-title';
    title.innerHTML = '💡 <span>Pertanyaan yang mungkin ingin Anda tanyakan:</span>';
    container.appendChild(title);
    
    const questionsWrapper = document.createElement('div');
    questionsWrapper.className = 'suggested-questions-list';
    
    questions.forEach(question => {
      const btn = document.createElement('button');
      btn.className = 'suggested-question-btn';
      btn.textContent = question;
      btn.onclick = () => {
        this.elements.input.value = question;
        this.elements.input.focus();
        // Optionally auto-send
        // this.sendMessage();
        // Remove suggested questions after click
        container.remove();
      };
      questionsWrapper.appendChild(btn);
    });
    
    container.appendChild(questionsWrapper);
    this.elements.messages.appendChild(container);
    this.scrollToBottom();
  },

  showEnhancedTypingIndicator() {
    const typingId = 'typing-' + Date.now();
    const message = document.createElement('div');
    message.className = 'message bot-message';
    message.id = typingId;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🤖';
    
    const content = document.createElement('div');
    content.className = 'message-content typing-indicator';
    content.innerHTML = `
      <div class="typing-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    `;
    
    message.appendChild(avatar);
    message.appendChild(content);
    this.elements.messages.appendChild(message);
    
    this.scrollToBottom();
    
    return typingId;
  },

  removeTypingIndicator(typingId) {
    const typingElement = document.getElementById(typingId);
    if (typingElement) {
      // Fade out animation
      typingElement.style.opacity = '0';
      typingElement.style.transform = 'translateY(-10px)';
      typingElement.style.transition = 'all 0.3s ease';
      
      setTimeout(() => {
        typingElement.remove();
      }, 300);
    }
  },

  addMessage(role, text) {
    const message = document.createElement('div');
    message.className = `message ${role}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'bot' ? '🤖' : '👤';

    const content = document.createElement('div');
    content.className = 'message-content';
    content.innerHTML = role === 'bot' ? marked.parse(text) : Utils.escapeHtml(text);

    message.appendChild(avatar);
    message.appendChild(content);
    this.elements.messages.appendChild(message);
    this.scrollToBottom();
  },

  addBotLoadingBubble() {
    const bubble = document.createElement('div');
    bubble.className = 'message bot-message loading-bubble';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '🤖';

    const content = document.createElement('div');
    content.className = 'message-content';
    content.innerHTML = `<span class="typing-loader"><span>.</span><span>.</span><span>.</span></span>`;

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

  // NEW: animasi dikontrol manual
  startProcessing() {
    this.elements.processingIndicator.classList.add('active');
    this.elements.currentStep = 0;
    this._advanceProcessingStep();
  },

  endProcessing() {
    const steps = CONFIG.PROCESSING_STEPS;
    for (let i = this.elements.currentStep; i < steps.length; i++) {
      const stepEl = document.getElementById(steps[i].id);
      stepEl.classList.remove('active');
      stepEl.classList.add('completed');
    }
    this.elements.processingIndicator.classList.remove('active');
  },

  _advanceProcessingStep() {
    const steps = CONFIG.PROCESSING_STEPS;
    if (this.elements.currentStep >= steps.length) return;

    const step = steps[this.elements.currentStep];
    const stepEl = document.getElementById(step.id);
    stepEl.classList.add('active');

    setTimeout(() => {
      stepEl.classList.remove('active');
      stepEl.classList.add('completed');
      this.elements.currentStep++;
      this._advanceProcessingStep();
    }, step.duration);
  },

  clearMessages(resetChatId = true) {
    this.elements.messages.innerHTML = '';
    if (resetChatId) {
      STATE.chatId = null;
    }
  },

  enableInput(enable = true) {
    this.elements.input.disabled = !enable;
    this.elements.sendBtn.disabled = !enable;
    if (enable) this.elements.input.focus();
  }
};
