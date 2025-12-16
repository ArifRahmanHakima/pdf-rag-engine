// ============= PDF HANDLER MODULE =============
const PDFHandler = {
  elements: {
    canvas: null,
    loading: null,
    pageInfo: null,
    pageInput: null,
    prevBtn: null,
    nextBtn: null,
    zoomInBtn: null,
    zoomOutBtn: null,
    canvasContainer: null
  },

  init() {
    this.elements.canvas = document.getElementById('pdfCanvas');
    this.elements.loading = document.getElementById('pdfLoading');
    this.elements.pageInfo = document.getElementById('pageInfo');
    this.elements.pageInput = document.getElementById('pageInput');
    this.elements.prevBtn = document.getElementById('prevPage');
    this.elements.nextBtn = document.getElementById('nextPage');
    this.elements.zoomInBtn = document.getElementById('zoomIn');
    this.elements.zoomOutBtn = document.getElementById('zoomOut');
    this.elements.canvasContainer = document.getElementById('pdfCanvasContainer');

    this.attachEvents();
  },

  attachEvents() {
    if (!this.elements.prevBtn) return;

    this.elements.prevBtn.addEventListener('click', () => this.prevPage());
    this.elements.nextBtn.addEventListener('click', () => this.nextPage());
    this.elements.zoomInBtn.addEventListener('click', () => this.zoomIn());
    this.elements.zoomOutBtn.addEventListener('click', () => this.zoomOut());
    
    this.elements.pageInput.addEventListener('change', (e) => {
      this.goToPage(parseInt(e.target.value));
    });

    this.elements.pageInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        this.goToPage(parseInt(e.target.value));
      }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (!STATE.pdfDoc) return;
      
      if (e.key === 'ArrowLeft') {
        this.prevPage();
      } else if (e.key === 'ArrowRight') {
        this.nextPage();
      } else if (e.key === '+' && e.ctrlKey) {
        e.preventDefault();
        this.zoomIn();
      } else if (e.key === '-' && e.ctrlKey) {
        e.preventDefault();
        this.zoomOut();
      }
    });
  },

  async loadPDF(file) {
    this.showLoading(true);
    
    const fileReader = new FileReader();
    
    return new Promise((resolve, reject) => {
      fileReader.onload = async () => {
        try {
          const typedarray = new Uint8Array(fileReader.result);
          STATE.pdfDoc = await pdfjsLib.getDocument(typedarray).promise;
          
          this.elements.pageInput.max = STATE.pdfDoc.numPages;
          this.updatePageInfo();
          
          // Reset to first page and default scale
          STATE.pageNum = 1;
          STATE.scale = CONFIG.DEFAULT_SCALE;
          
          await this.renderPage(STATE.pageNum);
          this.showLoading(false);
          resolve();
        } catch (error) {
          console.error('Error loading PDF:', error);
          this.showLoading(false);
          reject(error);
        }
      };

      fileReader.onerror = () => {
        this.showLoading(false);
        reject(new Error('Failed to read file'));
      };
      
      fileReader.readAsArrayBuffer(file);
    });
  },

  async renderPage(num) {
    if (!STATE.pdfDoc) return;
    
    STATE.pageRendering = true;
    this.updateButtonStates();
    
    try {
      const page = await STATE.pdfDoc.getPage(num);
      const viewport = page.getViewport({ scale: STATE.scale });
      const canvas = this.elements.canvas;
      const context = canvas.getContext('2d');
      
      // Set canvas dimensions
      canvas.height = viewport.height;
      canvas.width = viewport.width;
      
      // Render PDF page
      const renderContext = {
        canvasContext: context,
        viewport: viewport
      };
      
      await page.render(renderContext).promise;
      
      STATE.pageRendering = false;
      STATE.pageNum = num;
      
      // If there's a pending page render, do it now
      if (STATE.pageNumPending !== null) {
        const pending = STATE.pageNumPending;
        STATE.pageNumPending = null;
        this.renderPage(pending);
      }
      
      this.updatePageInfo();
      this.updateButtonStates();
    } catch (error) {
      console.error('Error rendering page:', error);
      STATE.pageRendering = false;
      this.updateButtonStates();
    }
  },

  queueRenderPage(num) {
    if (STATE.pageRendering) {
      STATE.pageNumPending = num;
    } else {
      this.renderPage(num);
    }
  },

  prevPage() {
    if (STATE.pageNum <= 1) return;
    STATE.pageNum--;
    this.queueRenderPage(STATE.pageNum);
  },

  nextPage() {
    if (!STATE.pdfDoc || STATE.pageNum >= STATE.pdfDoc.numPages) return;
    STATE.pageNum++;
    this.queueRenderPage(STATE.pageNum);
  },

  goToPage(num) {
    if (!STATE.pdfDoc) return;
    
    if (isNaN(num)) num = 1;
    if (num < 1) num = 1;
    if (num > STATE.pdfDoc.numPages) num = STATE.pdfDoc.numPages;
    
    STATE.pageNum = num;
    this.queueRenderPage(STATE.pageNum);
  },

  zoomIn() {
    if (STATE.scale >= CONFIG.MAX_SCALE) return;
    STATE.scale += CONFIG.SCALE_STEP;
    STATE.scale = Math.round(STATE.scale * 10) / 10; // Round to 1 decimal
    this.queueRenderPage(STATE.pageNum);
  },

  zoomOut() {
    if (STATE.scale <= CONFIG.MIN_SCALE) return;
    STATE.scale -= CONFIG.SCALE_STEP;
    STATE.scale = Math.round(STATE.scale * 10) / 10; // Round to 1 decimal
    this.queueRenderPage(STATE.pageNum);
  },

  updatePageInfo() {
    if (!STATE.pdfDoc) return;
    
    this.elements.pageInfo.textContent = `of ${STATE.pdfDoc.numPages}`;
    this.elements.pageInput.value = STATE.pageNum;
  },

  updateButtonStates() {
    if (!STATE.pdfDoc) return;
    
    // Disable/enable navigation buttons
    this.elements.prevBtn.disabled = STATE.pageNum <= 1;
    this.elements.nextBtn.disabled = STATE.pageNum >= STATE.pdfDoc.numPages;
    
    // Disable/enable zoom buttons
    this.elements.zoomInBtn.disabled = STATE.scale >= CONFIG.MAX_SCALE;
    this.elements.zoomOutBtn.disabled = STATE.scale <= CONFIG.MIN_SCALE;
  },

  showLoading(show) {
    if (show) {
      this.elements.loading.classList.add('active');
    } else {
      this.elements.loading.classList.remove('active');
    }
  },

  reset() {
    STATE.pdfDoc = null;
    STATE.pageNum = 1;
    STATE.scale = CONFIG.DEFAULT_SCALE;
    STATE.pageRendering = false;
    STATE.pageNumPending = null;
    
    if (this.elements.canvas) {
      const context = this.elements.canvas.getContext('2d');
      context.clearRect(0, 0, this.elements.canvas.width, this.elements.canvas.height);
    }
    
    if (this.elements.pageInfo) {
      this.elements.pageInfo.textContent = 'of 1';
    }
    if (this.elements.pageInput) {
      this.elements.pageInput.value = 1;
    }
  },

  // Alias untuk reset - lebih mudah dibaca
  clearPDF() {
    this.reset();
  }
};