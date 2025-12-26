// ============= MAIN APP INITIALIZATION =============
document.addEventListener('DOMContentLoaded', () => {
  console.log('🚀 Initializing ChatPDF...');
  
  try {
    // Initialize status monitor first
    if (typeof statusMonitor !== 'undefined') {
      console.log('✅ Status monitor initialized');
    }
    
    // Initialize all modules in order
    UIHandler.init();
    PDFHandler.init();
    ChatHandler.init();
    
    console.log('✅ ChatPDF initialized successfully');
    console.log('📊 Configuration:', {
      maxFileSize: Utils.formatFileSize(CONFIG.MAX_FILE_SIZE),
      defaultScale: CONFIG.DEFAULT_SCALE,
      userId: STATE.userId,
      docId: STATE.docId
    });
    
    // Check if PDF.js is loaded
    if (typeof pdfjsLib === 'undefined') {
      console.error('❌ PDF.js library not loaded!');
      // alert('Error: PDF viewer library not loaded. Please refresh the page.');
    }
    
  } catch (error) {
    console.error('❌ Initialization error:', error);
    // alert('Error initializing application. Please refresh the page.');
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
  Utils,
  DocStorage
};

console.log('💡 Debug tools available at window.ChatPDFDebug');
console.log('📚 Loaded documents:', DocStorage.getAllDocuments().length);