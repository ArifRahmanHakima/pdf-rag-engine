// ============= MAIN APP INITIALIZATION =============
document.addEventListener('DOMContentLoaded', () => {
  console.log('🚀 Initializing ChatPDF...');
  
  // Initialize auth handler first (isolated to ensure it always runs)
  try {
    if (typeof AuthHandler !== 'undefined') {
      AuthHandler.init();
      AuthHandler.attachModalEvents();
      console.log('✅ Auth handler initialized');
    }
  } catch (authError) {
    console.error('❌ Auth handler error:', authError);
  }
  
  try {
    // Initialize status monitor
    if (typeof statusMonitor !== 'undefined') {
      console.log('✅ Status monitor initialized');
    }
    
    // Initialize all modules in order
    if (typeof UIHandler !== 'undefined') {
      UIHandler.init();
      console.log('✅ UI handler initialized');
    }
    
    if (typeof PDFHandler !== 'undefined') {
      PDFHandler.init();
      console.log('✅ PDF handler initialized');
    }
    
    if (typeof ChatHandler !== 'undefined') {
      ChatHandler.init();
      console.log('✅ Chat handler initialized');
    }
    
    console.log('✅ ChatPDF initialized successfully');
    console.log('📊 Configuration:', {
      maxFileSize: typeof Utils !== 'undefined' ? Utils.formatFileSize(CONFIG.MAX_FILE_SIZE) : 'N/A',
      defaultScale: CONFIG.DEFAULT_SCALE,
      isLoggedIn: typeof AuthHandler !== 'undefined' ? AuthHandler.isLoggedIn() : false,
      docId: STATE.docId
    });
    
    // Check if PDF.js is loaded
    if (typeof pdfjsLib === 'undefined') {
      console.error('❌ PDF.js library not loaded!');
    }
    
  } catch (error) {
    console.error('❌ Initialization error:', error);
  }
});

// Handle window resize
window.addEventListener('resize', Utils.debounce(() => {
  STATE.isMobile = window.innerWidth <= 1024;
  
  // Close sidebar on desktop
  if (!STATE.isMobile) {
    const sidebar = document.getElementById('sidebar');
    const hamburger = document.getElementById('hamburgerBtn');
    if (sidebar) sidebar.classList.remove('active');
    if (hamburger) hamburger.classList.remove('active');
  }
}, 250));

// Handle page visibility change
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    console.log('📴 Page hidden');
  } else {
    console.log('👀 Page visible');
  }
});

// Prevent default drag and drop on document
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  document.addEventListener(eventName, (e) => {
    // Only prevent if not in upload area
    if (!e.target.closest('#uploadArea')) {
      e.preventDefault();
      e.stopPropagation();
    }
  });
});

// Global error handler
window.addEventListener('error', (e) => {
  console.error('Global error:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled promise rejection:', e.reason);
});

// Export for debugging in console
window.ChatPDFDebug = {
  STATE,
  CONFIG,
  PDFHandler,
  ChatHandler,
  UIHandler,
  AuthHandler: typeof AuthHandler !== 'undefined' ? AuthHandler : null,
  Utils,
  DocStorage
};

console.log('💡 Debug tools available at window.ChatPDFDebug');
console.log('📚 Loaded documents:', DocStorage.getAllDocuments().length);
console.log('🔐 Auth status:', typeof AuthHandler !== 'undefined' ? (AuthHandler.isLoggedIn() ? 'Logged in' : 'Not logged in') : 'Auth not available');