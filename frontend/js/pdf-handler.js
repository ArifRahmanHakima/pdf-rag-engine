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
          
          // Reset to first page and default scale
          STATE.pageNum = 1;
          STATE.scale = CONFIG.DEFAULT_SCALE;
          
          // Create container for all pages
          this.createPDFContainer();
          
          // Render first batch of pages
          await this.renderInitialPages();
          
          this.updatePageInfo();
          this.showLoading(false);
          
          // Setup scroll listener for continuous rendering
          this.setupScrollListener();
          
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

  createPDFContainer() {
    // Clear existing and create wrapper
    this.elements.canvasContainer.innerHTML = '';
    
    const wrapper = document.createElement('div');
    wrapper.id = 'pdfPagesWrapper';
    
    this.elements.canvasContainer.appendChild(wrapper);
  },

  async renderInitialPages() {
    if (!STATE.pdfDoc) return;
    
    // Create canvas elements for all pages
    const wrapper = document.getElementById('pdfPagesWrapper');
    for (let pageNum = 1; pageNum <= STATE.pdfDoc.numPages; pageNum++) {
      const canvas = document.createElement('canvas');
      canvas.dataset.page = pageNum;
      wrapper.appendChild(canvas);
    }
    
    // Render first page immediately
    await this.renderPageToCanvas(1);
  },

  setupScrollListener() {
    if (!this.elements.canvasContainer) return;
    
    const scrollContainer = this.elements.canvasContainer;
    let scrollTimeout;
    
    scrollContainer.addEventListener('scroll', () => {
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        this.updateCurrentPageFromScroll();
        this.renderVisiblePages();
      }, 150);
    });
  },

  updateCurrentPageFromScroll() {
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (!wrapper) return;
    
    const scrollContainer = this.elements.canvasContainer;
    const containerRect = scrollContainer.getBoundingClientRect();
    const pageCanvases = wrapper.querySelectorAll('canvas');
    
    let closestPage = 1;
    let closestDistance = Infinity;
    
    pageCanvases.forEach((canvas, index) => {
      const canvasRect = canvas.getBoundingClientRect();
      const distance = Math.abs(canvasRect.top - (containerRect.top + containerRect.height / 2));
      
      if (distance < closestDistance) {
        closestDistance = distance;
        closestPage = index + 1;
      }
    });
    
    if (closestPage !== STATE.pageNum) {
      STATE.pageNum = closestPage;
      this.updatePageInfo();
    }
  },

  renderVisiblePages() {
    if (!STATE.pdfDoc) return;
    
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (!wrapper) return;
    
    const scrollContainer = this.elements.canvasContainer;
    const containerHeight = scrollContainer.clientHeight;
    const scrollTop = scrollContainer.scrollTop;
    
    // Render pages that are visible or close to visible area
    const pageCanvases = wrapper.querySelectorAll('canvas');
    pageCanvases.forEach((canvas, index) => {
      const pageNum = index + 1;
      const canvasRect = canvas.getBoundingClientRect();
      
      // Check if canvas is in visible area (with some margin for lazy loading)
      const isInViewport = canvasRect.bottom > -500 && canvasRect.top < containerHeight + 500;
      
      if (isInViewport && canvas.dataset.rendered !== 'true') {
        this.renderPageToCanvas(pageNum);
      }
    });
  },

  async renderPageToCanvas(pageNum) {
    if (!STATE.pdfDoc || pageNum < 1 || pageNum > STATE.pdfDoc.numPages) return;
    
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (!wrapper) return;
    
    const canvas = wrapper.querySelector(`canvas[data-page="${pageNum}"]`);
    if (!canvas || canvas.dataset.rendered === 'true') return;
    
    try {
      const page = await STATE.pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: STATE.scale });
      const context = canvas.getContext('2d');
      
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      
      const renderContext = {
        canvasContext: context,
        viewport: viewport
      };
      
      await page.render(renderContext).promise;
      canvas.dataset.rendered = 'true';
    } catch (error) {
      console.error('Error rendering page ' + pageNum + ':', error);
    }
  },

  prevPage() {
    if (STATE.pageNum <= 1) return;
    STATE.pageNum--;
    this.updatePageInfo();
    
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (wrapper) {
      const canvas = wrapper.querySelector(`canvas[data-page="${STATE.pageNum}"]`);
      if (canvas) {
        canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  },

  nextPage() {
    if (STATE.pageNum >= STATE.pdfDoc.numPages) return;
    STATE.pageNum++;
    this.updatePageInfo();
    
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (wrapper) {
      const canvas = wrapper.querySelector(`canvas[data-page="${STATE.pageNum}"]`);
      if (canvas) {
        canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  },

  goToPage(num) {
    if (num < 1 || num > STATE.pdfDoc.numPages) return;
    STATE.pageNum = num;
    this.updatePageInfo();
    
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (wrapper) {
      const canvas = wrapper.querySelector(`canvas[data-page="${STATE.pageNum}"]`);
      if (canvas) {
        canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  },

  zoomIn() {
    if (STATE.scale >= CONFIG.MAX_SCALE) return;
    STATE.scale += CONFIG.SCALE_STEP;
    STATE.scale = Math.round(STATE.scale * 10) / 10;
    this.reRenderAllPages();
  },

  zoomOut() {
    if (STATE.scale <= CONFIG.MIN_SCALE) return;
    STATE.scale -= CONFIG.SCALE_STEP;
    STATE.scale = Math.round(STATE.scale * 10) / 10;
    this.reRenderAllPages();
  },

  reRenderAllPages() {
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (!wrapper) return;
    
    const canvases = wrapper.querySelectorAll('canvas');
    canvases.forEach(canvas => {
      canvas.dataset.rendered = 'false';
    });
    
    // Re-render visible pages
    this.renderVisiblePages();
    this.updatePageInfo();
  },

  updatePageInfo() {
    if (!STATE.pdfDoc) return;
    
    if (this.elements.pageInfo) {
      this.elements.pageInfo.textContent = `${STATE.pageNum} of ${STATE.pdfDoc.numPages}`;
    }
    if (this.elements.pageInput) {
      this.elements.pageInput.value = STATE.pageNum;
      this.elements.pageInput.max = STATE.pdfDoc.numPages;
    }
    
    this.updateButtonStates();
  },

  updateButtonStates() {
    if (!STATE.pdfDoc) return;
    
    // Disable/enable navigation buttons
    if (this.elements.prevBtn) this.elements.prevBtn.disabled = STATE.pageNum <= 1;
    if (this.elements.nextBtn) this.elements.nextBtn.disabled = STATE.pageNum >= STATE.pdfDoc.numPages;
    
    // Disable/enable zoom buttons
    if (this.elements.zoomInBtn) this.elements.zoomInBtn.disabled = STATE.scale >= CONFIG.MAX_SCALE;
    if (this.elements.zoomOutBtn) this.elements.zoomOutBtn.disabled = STATE.scale <= CONFIG.MIN_SCALE;
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
    
    const wrapper = document.getElementById('pdfPagesWrapper');
    if (wrapper) {
      wrapper.innerHTML = '';
    }
  }
};
