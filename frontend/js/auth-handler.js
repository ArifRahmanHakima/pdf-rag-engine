// ============= AUTH HANDLER MODULE =============
const AuthHandler = {
  TOKEN_KEY: 'chatpdf_auth_token',
  USER_KEY: 'chatpdf_user',

  // Get stored token
  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  // Get stored user
  getUser() {
    try {
      const user = localStorage.getItem(this.USER_KEY);
      return user ? JSON.parse(user) : null;
    } catch (e) {
      console.error('Error parsing user:', e);
      return null;
    }
  },

  // Check if user is logged in
  isLoggedIn() {
    return !!this.getToken();
  },

  // Save auth data
  saveAuth(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    STATE.currentUser = user;
    STATE.authToken = token;
  },

  // Clear auth data
  clearAuth() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    STATE.currentUser = null;
    STATE.authToken = null;
  },

  // Get auth headers for API requests
  getAuthHeaders() {
    const token = this.getToken();
    if (!token) return {};
    return {
      'Authorization': `Bearer ${token}`
    };
  },

  // Initialize auth state
  init() {
    console.log('🔐 AuthHandler.init() called');
    const token = this.getToken();
    const user = this.getUser();
    
    if (token && user) {
      STATE.authToken = token;
      STATE.currentUser = user;
      this.updateUI();
      this.verifyToken();
    } else {
      this.updateUI();
    }
    console.log('🔐 AuthHandler.init() completed');
  },

  // Verify token is still valid
  async verifyToken() {
    if (!this.getToken()) return false;
    
    try {
      const response = await fetch(`${CONFIG.API_BASE_URL}/auth/verify`, {
        method: 'POST',
        headers: this.getAuthHeaders()
      });
      
      if (!response.ok) {
        console.log('Token expired or invalid');
        this.clearAuth();
        this.updateUI();
        return false;
      }
      
      return true;
    } catch (error) {
      console.error('Error verifying token:', error);
      return false;
    }
  },

  // Update UI based on auth state
  updateUI() {
    console.log('🔐 AuthHandler.updateUI() called');
    const authArea = document.getElementById('authArea');
    const user = this.getUser();
    
    console.log('🔐 authArea element:', authArea);
    console.log('🔐 user:', user);
    
    if (authArea) {
      if (user) {
        authArea.innerHTML = `
          <div class="user-info">
            <span class="user-name">Hi, ${Utils.escapeHtml(user.name)}</span>
            <button class="logout-btn" id="logoutBtn" title="Logout">
              <i class="fa-solid fa-sign-out-alt"></i>
            </button>
          </div>
        `;
        
        // Attach logout handler
        document.getElementById('logoutBtn')?.addEventListener('click', () => this.logout());
      } else {
        authArea.innerHTML = `
          <button class="auth-btn signin-btn" id="signinBtn">Sign In</button>
          <button class="auth-btn signup-btn" id="signupBtn">Sign Up</button>
        `;
        
        // Attach handlers
        const signinBtn = document.getElementById('signinBtn');
        const signupBtn = document.getElementById('signupBtn');
        
        console.log('🔐 signinBtn:', signinBtn);
        console.log('🔐 signupBtn:', signupBtn);
        
        if (signinBtn) {
          signinBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('🔐 Sign In clicked!');
            this.showLoginModal();
          });
        }
        
        if (signupBtn) {
          signupBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('🔐 Sign Up clicked!');
            this.showRegisterModal();
          });
        }
      }
    } else {
      console.error('🔐 authArea element not found!');
    }
  },

  // Show login modal
  showLoginModal() {
    console.log('🔐 showLoginModal() called');
    const modal = document.getElementById('loginModal');
    console.log('🔐 loginModal element:', modal);
    if (modal) {
      modal.classList.add('active');
      console.log('🔐 Modal class after add:', modal.className);
      document.getElementById('loginEmail')?.focus();
    } else {
      console.error('🔐 loginModal not found!');
    }
  },

  // Hide login modal
  hideLoginModal() {
    const modal = document.getElementById('loginModal');
    if (modal) {
      modal.classList.remove('active');
      // Clear form
      document.getElementById('loginForm')?.reset();
      this.clearLoginError();
    }
  },

  // Show register modal
  showRegisterModal() {
    console.log('🔐 showRegisterModal() called');
    const modal = document.getElementById('registerModal');
    console.log('🔐 registerModal element:', modal);
    if (modal) {
      modal.classList.add('active');
      console.log('🔐 Modal class after add:', modal.className);
      document.getElementById('registerName')?.focus();
    } else {
      console.error('🔐 registerModal not found!');
    }
  },

  // Hide register modal
  hideRegisterModal() {
    const modal = document.getElementById('registerModal');
    if (modal) {
      modal.classList.remove('active');
      // Clear form
      document.getElementById('registerForm')?.reset();
      this.clearRegisterError();
    }
  },

  // Show error on login form
  showLoginError(message) {
    const errorDiv = document.getElementById('loginError');
    if (errorDiv) {
      errorDiv.textContent = message;
      errorDiv.style.display = 'block';
    }
  },

  // Clear login error
  clearLoginError() {
    const errorDiv = document.getElementById('loginError');
    if (errorDiv) {
      errorDiv.textContent = '';
      errorDiv.style.display = 'none';
    }
  },

  // Show error on register form
  showRegisterError(message) {
    const errorDiv = document.getElementById('registerError');
    if (errorDiv) {
      errorDiv.textContent = message;
      errorDiv.style.display = 'block';
    }
  },

  // Clear register error
  clearRegisterError() {
    const errorDiv = document.getElementById('registerError');
    if (errorDiv) {
      errorDiv.textContent = '';
      errorDiv.style.display = 'none';
    }
  },

  // Validate email format
  isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  },

  // Register user
  async register(name, email, password, confirmPassword) {
    this.clearRegisterError();
    
    // Validation
    if (!name || !name.trim()) {
      this.showRegisterError('Nama tidak boleh kosong');
      return false;
    }
    
    if (!email || !this.isValidEmail(email)) {
      this.showRegisterError('Email tidak valid');
      return false;
    }
    
    if (!password || password.length < 8) {
      this.showRegisterError('Password minimal 8 karakter');
      return false;
    }
    
    if (password !== confirmPassword) {
      this.showRegisterError('Konfirmasi password tidak cocok');
      return false;
    }
    
    try {
      const registerBtn = document.getElementById('registerSubmitBtn');
      if (registerBtn) {
        registerBtn.disabled = true;
        registerBtn.textContent = 'Mendaftar...';
      }
      
      const response = await fetch(`${CONFIG.API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name, email, password })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || 'Gagal mendaftar');
      }
      
      // Save auth data
      this.saveAuth(data.token, data.user);
      
      // Update UI
      this.updateUI();
      
      // Close modal
      this.hideRegisterModal();
      
      // Show success message
      if (typeof UIHandler !== 'undefined' && UIHandler.showSuccess) {
        UIHandler.showSuccess(`Selamat datang, ${data.user.name}!`);
      }
      
      return true;
      
    } catch (error) {
      console.error('Register error:', error);
      this.showRegisterError(error.message);
      return false;
    } finally {
      const registerBtn = document.getElementById('registerSubmitBtn');
      if (registerBtn) {
        registerBtn.disabled = false;
        registerBtn.textContent = 'Daftar';
      }
    }
  },

  // Login user
  async login(email, password) {
    this.clearLoginError();
    
    // Validation
    if (!email || !this.isValidEmail(email)) {
      this.showLoginError('Email tidak valid');
      return false;
    }
    
    if (!password) {
      this.showLoginError('Password tidak boleh kosong');
      return false;
    }
    
    try {
      const loginBtn = document.getElementById('loginSubmitBtn');
      if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.textContent = 'Masuk...';
      }
      
      const response = await fetch(`${CONFIG.API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email, password })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || 'Email atau password salah');
      }
      
      // Save auth data
      this.saveAuth(data.token, data.user);
      
      // Update UI
      this.updateUI();
      
      // Close modal
      this.hideLoginModal();
      
      // Show success message
      if (typeof UIHandler !== 'undefined' && UIHandler.showSuccess) {
        UIHandler.showSuccess(`Selamat datang kembali, ${data.user.name}!`);
      }
      
      return true;
      
    } catch (error) {
      console.error('Login error:', error);
      this.showLoginError(error.message);
      return false;
    } finally {
      const loginBtn = document.getElementById('loginSubmitBtn');
      if (loginBtn) {
        loginBtn.disabled = false;
        loginBtn.textContent = 'Masuk';
      }
    }
  },

  // Logout user
  logout() {
    this.clearAuth();
    
    // Reset document state
    STATE.docId = null;
    STATE.chatId = null;
    
    // Clear documents from storage (optional - keep or remove based on requirement)
    STATE.documents = {};
    DocStorage.saveAll();
    
    // Update UI
    this.updateUI();
    
    // Show welcome screen
    if (typeof UIHandler !== 'undefined') {
      UIHandler.showWelcomeScreen();
      UIHandler.renderChatList();
    }
    
    // Show success message
    if (typeof UIHandler !== 'undefined' && UIHandler.showSuccess) {
      UIHandler.showSuccess('Berhasil logout');
    }
  },

  // Require login for action
  requireLogin(action) {
    if (!this.isLoggedIn()) {
      this.showLoginModal();
      return false;
    }
    return true;
  },

  // Toggle password visibility
  togglePasswordVisibility(inputId, buttonId) {
    const input = document.getElementById(inputId);
    const button = document.getElementById(buttonId);
    
    if (!input || !button) return;
    
    const icon = button.querySelector('i');
    if (!icon) return;
    
    const isPassword = input.type === 'password';
    
    if (isPassword) {
      input.type = 'text';
      icon.classList.remove('fa-eye');
      icon.classList.add('fa-eye-slash');
      button.title = 'Hide Password';
    } else {
      input.type = 'password';
      icon.classList.remove('fa-eye-slash');
      icon.classList.add('fa-eye');
      button.title = 'Show Password';
    }
  },

  // Attach password toggle events
  attachPasswordToggleEvents() {
    // Login password toggle
    const loginToggle = document.getElementById('loginPasswordToggle');
    if (loginToggle) {
      loginToggle.addEventListener('click', (e) => {
        e.preventDefault();
        this.togglePasswordVisibility('loginPassword', 'loginPasswordToggle');
      });
    }

    // Register password toggle
    const registerToggle = document.getElementById('registerPasswordToggle');
    if (registerToggle) {
      registerToggle.addEventListener('click', (e) => {
        e.preventDefault();
        this.togglePasswordVisibility('registerPassword', 'registerPasswordToggle');
      });
    }

    // Register confirm password toggle
    const confirmToggle = document.getElementById('registerConfirmPasswordToggle');
    if (confirmToggle) {
      confirmToggle.addEventListener('click', (e) => {
        e.preventDefault();
        this.togglePasswordVisibility('registerConfirmPassword', 'registerConfirmPasswordToggle');
      });
    }
  },

  // Attach modal event listeners
  attachModalEvents() {
    // Attach password toggle events
    this.attachPasswordToggleEvents();
    
    // Login modal
    const loginModal = document.getElementById('loginModal');
    const loginClose = document.getElementById('loginModalClose');
    const loginForm = document.getElementById('loginForm');
    const switchToRegister = document.getElementById('switchToRegister');
    
    loginClose?.addEventListener('click', () => this.hideLoginModal());
    loginModal?.addEventListener('click', (e) => {
      if (e.target === loginModal) this.hideLoginModal();
    });
    
    loginForm?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('loginEmail')?.value;
      const password = document.getElementById('loginPassword')?.value;
      await this.login(email, password);
    });
    
    switchToRegister?.addEventListener('click', (e) => {
      e.preventDefault();
      this.hideLoginModal();
      this.showRegisterModal();
    });
    
    // Register modal
    const registerModal = document.getElementById('registerModal');
    const registerClose = document.getElementById('registerModalClose');
    const registerForm = document.getElementById('registerForm');
    const switchToLogin = document.getElementById('switchToLogin');
    
    registerClose?.addEventListener('click', () => this.hideRegisterModal());
    registerModal?.addEventListener('click', (e) => {
      if (e.target === registerModal) this.hideRegisterModal();
    });
    
    registerForm?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('registerName')?.value;
      const email = document.getElementById('registerEmail')?.value;
      const password = document.getElementById('registerPassword')?.value;
      const confirmPassword = document.getElementById('registerConfirmPassword')?.value;
      await this.register(name, email, password, confirmPassword);
    });
    
    switchToLogin?.addEventListener('click', (e) => {
      e.preventDefault();
      this.hideRegisterModal();
      this.showLoginModal();
    });
  }
};

// Export for debugging
if (typeof window !== 'undefined') {
  window.AuthHandler = AuthHandler;
}
