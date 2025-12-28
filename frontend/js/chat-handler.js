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

  addMessage(role, text, isHtml = false, withTyping = false) {
    const message = document.createElement('div');
    message.className = `message ${role}-message`;
    
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content-wrapper';
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    // For bot messages with typing animation
    if (role === 'bot' && withTyping) {
      content.innerHTML = '<span class="typing-cursor"></span>';
      contentWrapper.appendChild(content);
      message.appendChild(contentWrapper);
      this.elements.messages.appendChild(message);
      this.scrollToBottom();
      
      // Start typing animation
      const htmlContent = isHtml && text.includes('<') ? text : marked.parse(text);
      this.typeText(content, htmlContent, () => {
        // Add action buttons after typing is complete
        const actionsDiv = this.createMessageActions(content);
        actionsDiv.classList.add('fade-in');
        contentWrapper.appendChild(actionsDiv);
      });
      return;
    }
    
    // For bot messages without typing (from history)
    if (role === 'bot') {
      if (isHtml && text.includes('<')) {
        content.innerHTML = text;
      } else {
        content.innerHTML = marked.parse(text);
      }
    } else {
      // User messages: plain text
      content.textContent = text;
    }
    
    contentWrapper.appendChild(content);
    
    // Add action buttons for bot messages (Gemini style)
    if (role === 'bot') {
      const actionsDiv = this.createMessageActions(content);
      contentWrapper.appendChild(actionsDiv);
    }
    
    message.appendChild(contentWrapper);
    this.elements.messages.appendChild(message);
    this.scrollToBottom();
  },

  // Fast reveal animation - show all at once with smooth effect
  typeText(element, html, onComplete) {
    // Add animation class
    element.classList.add('message-reveal');
    element.innerHTML = html;
    
    // Scroll and complete
    this.scrollToBottom();
    
    // Small delay then show action buttons
    setTimeout(() => {
      element.classList.remove('message-reveal');
      if (onComplete) onComplete();
    }, 400);
  },

  // Create message action buttons (Copy, Like, Dislike, Read aloud)
  createMessageActions(contentElement) {
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'message-actions';
    
    // Copy button with text
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn-with-text';
    copyBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span>Salin</span>
    `;
    copyBtn.title = 'Salin teks';
    copyBtn.onclick = () => this.copyMessageNew(contentElement, copyBtn);
    
    // Like button
    const likeBtn = document.createElement('button');
    likeBtn.className = 'message-action-btn';
    likeBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
      </svg>
    `;
    likeBtn.title = 'Respons bagus';
    likeBtn.onclick = () => this.toggleLike(likeBtn);
    
    // Dislike button
    const dislikeBtn = document.createElement('button');
    dislikeBtn.className = 'message-action-btn';
    dislikeBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
      </svg>
    `;
    dislikeBtn.title = 'Respons kurang bagus';
    dislikeBtn.onclick = () => this.toggleDislike(dislikeBtn);
    
    // Read aloud button
    const readBtn = document.createElement('button');
    readBtn.className = 'message-action-btn';
    readBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
      </svg>
    `;
    readBtn.title = 'Bacakan';
    readBtn.onclick = () => this.readAloud(contentElement, readBtn);
    
    actionsDiv.appendChild(copyBtn);
    actionsDiv.appendChild(likeBtn);
    actionsDiv.appendChild(dislikeBtn);
    actionsDiv.appendChild(readBtn);
    
    return actionsDiv;
  },

  // Copy message (new style)
  copyMessageNew(contentElement, buttonElement) {
    const text = contentElement.innerText || contentElement.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
      const span = buttonElement.querySelector('span');
      span.textContent = 'Tersalin!';
      buttonElement.classList.add('copied');
      
      setTimeout(() => {
        span.textContent = 'Salin';
        buttonElement.classList.remove('copied');
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy:', err);
      UIHandler.showError('Gagal menyalin teks');
    });
  },

  // Toggle like
  toggleLike(button) {
    const isLiked = button.classList.contains('liked');
    
    // Remove dislike if active
    const parent = button.parentElement;
    const dislikeBtn = parent.querySelector('.message-action-btn.disliked');
    if (dislikeBtn) {
      dislikeBtn.classList.remove('disliked');
    }
    
    button.classList.toggle('liked');
    
    if (!isLiked) {
      UIHandler.showSuccess('Terima kasih atas feedback positif!');
    }
  },

  // Toggle dislike
  toggleDislike(button) {
    const isDisliked = button.classList.contains('disliked');
    
    // Remove like if active
    const parent = button.parentElement;
    const likeBtn = parent.querySelector('.message-action-btn.liked');
    if (likeBtn) {
      likeBtn.classList.remove('liked');
    }
    
    button.classList.toggle('disliked');
    
    if (!isDisliked) {
      UIHandler.showSuccess('Terima kasih atas feedback Anda!');
    }
  },

  // Read aloud using Web Speech API
  currentSpeech: null,
  
  readAloud(contentElement, buttonElement) {
    // Check if speech synthesis is supported
    if (!('speechSynthesis' in window)) {
      UIHandler.showError('Browser tidak mendukung text-to-speech');
      return;
    }
    
    // If already speaking, stop
    if (this.currentSpeech && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      buttonElement.classList.remove('speaking');
      this.currentSpeech = null;
      return;
    }
    
    const text = contentElement.innerText || contentElement.textContent;
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Set Indonesian voice if available
    const voices = window.speechSynthesis.getVoices();
    const indonesianVoice = voices.find(voice => voice.lang.includes('id')) || 
                           voices.find(voice => voice.lang.includes('en'));
    if (indonesianVoice) {
      utterance.voice = indonesianVoice;
    }
    
    utterance.lang = 'id-ID';
    utterance.rate = 1;
    utterance.pitch = 1;
    
    // Events
    utterance.onstart = () => {
      buttonElement.classList.add('speaking');
    };
    
    utterance.onend = () => {
      buttonElement.classList.remove('speaking');
      this.currentSpeech = null;
    };
    
    utterance.onerror = () => {
      buttonElement.classList.remove('speaking');
      this.currentSpeech = null;
    };
    
    this.currentSpeech = utterance;
    window.speechSynthesis.speak(utterance);
  },

  // Copy message to clipboard (legacy - keep for compatibility)
  copyMessage(contentElement, buttonElement) {
    this.copyMessageNew(contentElement, buttonElement);
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
    message.className = 'message bot-message typing-message';
    message.id = typingId;
    
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content-wrapper';
    
    const content = document.createElement('div');
    content.className = 'typing-indicator-modern';
    content.innerHTML = `
      <div class="typing-animation">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
      <span class="typing-text">Sedang menjawab...</span>
    `;
    
    contentWrapper.appendChild(content);
    message.appendChild(contentWrapper);
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
