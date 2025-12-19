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

    if (this.elements.fastBtn) {
      this.elements.fastBtn.addEventListener('click', () => this.setMode('fast'));
    }
    if (this.elements.qualityBtn) {
      this.elements.qualityBtn.addEventListener('click', () => this.setMode('quality'));
    }

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
      }
      
      // Add bot response with reveal animation
      if (data.answer) {
        await Utils.sleep(300); // Small delay for natural feel
        const answerHtml = Utils.parseMarkdown(data.answer);
        this.addMessage('bot', answerHtml, true, true); // true untuk HTML, true untuk reveal animation
        
        // ✅ Simpan chat history setelah respons bot
        if (STATE.docId && UIHandler.saveChatHistory) {
          UIHandler.saveChatHistory();
        }
      } else {
        throw new Error('Tidak ada jawaban dari server');
      }
      
    } catch (error) {
      console.error('Error sending message:', error);
      this.removeTypingIndicator(typingId);
      this.addMessage('bot', `❌ Maaf, terjadi kesalahan: ${error.message}`);
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
    
    message.appendChild(avatar);
    message.appendChild(content);
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

  clearMessages() {
    this.elements.messages.innerHTML = '';
    STATE.chatId = null;
  },

  enableInput(enable = true) {
    this.elements.input.disabled = !enable;
    this.elements.sendBtn.disabled = !enable;
    if (enable) this.elements.input.focus();
  },

  // ==================== SUMMARY DISPLAY METHODS ====================
  
  showGeneratingSummary() {
    const container = document.createElement('div');
    container.id = 'generatingSummary';
    container.className = 'generating-summary';
    container.innerHTML = `
      <div class="spinner"></div>
      <span class="generating-summary-text">📝 Sedang membuat ringkasan dokumen...</span>
    `;
    this.elements.messages.appendChild(container);
    this.scrollToBottom();
  },

  hideGeneratingSummary() {
    const element = document.getElementById('generatingSummary');
    if (element) {
      element.style.opacity = '0';
      element.style.transform = 'translateY(-10px)';
      element.style.transition = 'all 0.3s ease';
      setTimeout(() => element.remove(), 300);
    }
  },

  async showSummaryCard(summary, fileName) {
    // Remove generating indicator
    this.hideGeneratingSummary();
    
    await Utils.sleep(200);
    
    // Create summary card
    const card = document.createElement('div');
    card.className = 'summary-card';
    card.id = 'summaryCard';
    
    // Parse summary to HTML
    const summaryHtml = marked.parse(summary);
    
    card.innerHTML = `
      <div class="summary-card-header">
        <span class="summary-card-icon">📋</span>
        <div>
          <div class="summary-card-title">Ringkasan Dokumen</div>
          <div class="summary-card-subtitle">${fileName}</div>
        </div>
      </div>
      <div class="summary-card-content" id="summaryContent">
        ${summaryHtml}
      </div>
      <div class="summary-card-footer">
        <div class="summary-ready-badge">
          <span class="checkmark">✓</span>
          <span>Siap menerima pertanyaan</span>
        </div>
      </div>
    `;
    
    this.elements.messages.appendChild(card);
    this.scrollToBottom();
    
    // Animate typing effect (optional - for dramatic effect)
    await Utils.sleep(500);
    
    return card;
  },

  // Method to display summary with typing animation
  async showSummaryWithTyping(summary, fileName) {
    this.hideGeneratingSummary();
    await Utils.sleep(200);
    
    // Create summary card without content first
    const card = document.createElement('div');
    card.className = 'summary-card';
    card.id = 'summaryCard';
    
    card.innerHTML = `
      <div class="summary-card-header">
        <span class="summary-card-icon">📋</span>
        <div>
          <div class="summary-card-title">Ringkasan Dokumen</div>
          <div class="summary-card-subtitle">${fileName}</div>
        </div>
      </div>
      <div class="summary-card-content" id="summaryContent">
        <span class="summary-typing"></span>
      </div>
    `;
    
    this.elements.messages.appendChild(card);
    this.scrollToBottom();
    
    // Type out the summary
    const contentEl = document.getElementById('summaryContent');
    const typingSpan = contentEl.querySelector('.summary-typing');
    
    // Split into words for faster "typing"
    const words = summary.split(' ');
    let currentText = '';
    
    for (let i = 0; i < words.length; i++) {
      currentText += (i === 0 ? '' : ' ') + words[i];
      typingSpan.textContent = currentText;
      this.scrollToBottom();
      
      // Random delay between words (15-40ms)
      await Utils.sleep(Math.random() * 25 + 15);
    }
    
    // Remove typing cursor and show final HTML
    await Utils.sleep(300);
    contentEl.innerHTML = marked.parse(summary);
    
    // Add footer with ready badge
    const footer = document.createElement('div');
    footer.className = 'summary-card-footer';
    footer.innerHTML = `
      <div class="summary-ready-badge">
        <span class="checkmark">✓</span>
        <span>Siap menerima pertanyaan</span>
      </div>
    `;
    card.appendChild(footer);
    
    this.scrollToBottom();
    return card;
  }
};
