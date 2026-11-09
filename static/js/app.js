/**
 * DocuMind AI · Interactive Application Controller
 * High-performance vanilla JavaScript client with Markdown parsing,
 * Lucide icon rendering, Drag-and-Drop upload, and AJAX RAG workflow.
 */

(function () {
  'use strict';

  // --------------------------------------------------------------------------
  // Application State
  // --------------------------------------------------------------------------
  let state = {
    csrfToken: '',
    document: null,
    maxQuestions: 30,
    theme: 'dark',
    sidebarCollapsed: false,
    isProcessing: false,
  };

  // Hydrate initial state injected by server
  const stateElement = document.getElementById('initial-state');
  if (stateElement && stateElement.textContent) {
    try {
      const parsed = JSON.parse(stateElement.textContent);
      if (parsed) {
        state = { ...state, ...parsed };
      }
    } catch (e) {
      console.warn('Could not parse initial state:', e);
    }
  }

  // Fallback CSRF token from DOM if needed
  if (!state.csrfToken) {
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    if (csrfInput) state.csrfToken = csrfInput.value;
  }

  // --------------------------------------------------------------------------
  // DOM Elements
  // --------------------------------------------------------------------------
  const elements = {
    body: document.body,
    html: document.documentElement,
    appContainer: document.getElementById('app'),
    appSidebar: document.getElementById('app-sidebar'),
    sidebarBackdrop: document.getElementById('sidebar-backdrop'),
    mobileMenuBtn: document.getElementById('mobile-menu-btn'),
    sidebarCollapseBtn: document.getElementById('sidebar-collapse-btn'),
    sidebarCloseBtn: document.getElementById('sidebar-close-btn'),
    sidebarThemeToggle: document.getElementById('sidebar-theme-toggle'),
    headerThemeToggle: document.getElementById('header-theme-toggle'),
    newChatBtn: document.getElementById('new-chat-btn'),
    headerUploadBtn: document.getElementById('header-upload-btn'),
    switchDocBtn: document.getElementById('switch-doc-btn'),
    sidebarUploadTrigger: document.getElementById('sidebar-upload-trigger'),
    openSettingsBtn: document.getElementById('open-settings-btn'),
    closeSettingsBtn: document.getElementById('close-settings-btn'),
    modalDoneBtn: document.getElementById('modal-done-btn'),
    settingsModal: document.getElementById('settings-modal'),
    toastContainer: document.getElementById('toast-container'),

    // Views
    uploadView: document.getElementById('upload-view'),
    chatView: document.getElementById('chat-view'),

    // Header Status
    headerStatusPill: document.getElementById('header-status-pill'),
    headerStatusText: document.getElementById('header-status-text'),

    // Upload Elements
    uploadForm: document.getElementById('upload-form'),
    fileInput: document.getElementById('file-input'),
    dropzone: document.getElementById('dropzone'),
    dropzonePrompt: document.getElementById('dropzone-prompt'),
    filePreview: document.getElementById('file-preview'),
    previewFilename: document.getElementById('preview-filename'),
    previewFilesize: document.getElementById('preview-filesize'),
    cancelFileBtn: document.getElementById('cancel-file-btn'),
    uploadSubmitBtn: document.getElementById('upload-submit-btn'),
    uploadProgressWrapper: document.getElementById('upload-progress-wrapper'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    progressStatusText: document.getElementById('progress-status-text'),
    progressPercentText: document.getElementById('progress-percent-text'),

    // Sidebar Active Doc
    sidebarDocumentCard: document.getElementById('sidebar-document-card'),
    sidebarHistoryList: document.getElementById('sidebar-history-list'),
    historyCount: document.getElementById('history-count'),
    docPulseIndicator: document.getElementById('doc-pulse-indicator'),
    resetDocForm: document.getElementById('reset-doc-form'),

    // Chat Elements
    chatDocBanner: document.getElementById('chat-doc-banner'),
    bannerDocName: document.getElementById('banner-doc-name'),
    bannerDocMeta: document.getElementById('banner-doc-meta'),
    chatMessages: document.getElementById('chat-messages'),
    liveTypingMessage: document.getElementById('live-typing-message'),
    suggestedChips: document.getElementById('suggested-chips'),
    askForm: document.getElementById('ask-form'),
    questionInput: document.getElementById('question-input'),
    sendBtn: document.getElementById('send-btn'),
    charCounter: document.getElementById('char-counter'),
  };

  // --------------------------------------------------------------------------
  // Theme Management
  // --------------------------------------------------------------------------
  function initTheme() {
    const savedTheme = localStorage.getItem('documind-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {
      state.theme = savedTheme;
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      state.theme = prefersDark ? 'dark' : 'light';
    }
    applyTheme(state.theme);

    // Remove preload flash protection
    setTimeout(() => {
      elements.body.classList.remove('theme-preload');
    }, 100);
  }

  function applyTheme(theme) {
    state.theme = theme;
    elements.html.setAttribute('data-theme', theme);
    localStorage.setItem('documind-theme', theme);

    // Update highlight.js theme link if needed
    const hlTheme = document.getElementById('highlight-theme');
    if (hlTheme) {
      if (theme === 'light') {
        hlTheme.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
      } else {
        hlTheme.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css';
      }
    }
  }

  function toggleTheme() {
    const nextTheme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme);
    showToast(`Switched to ${nextTheme} theme`, 'info', 2000);
  }

  // --------------------------------------------------------------------------
  // Toast Notifications
  // --------------------------------------------------------------------------
  function showToast(message, type = 'info', duration = 4000) {
    if (!elements.toastContainer) return;

    const toast = document.createElement('div');
    toast.className = 'toast';

    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle-2';
    else if (type === 'danger') iconName = 'alert-circle';
    else if (type === 'warning') iconName = 'alert-triangle';

    toast.innerHTML = `
      <i data-lucide="${iconName}" class="toast-icon ${type}"></i>
      <div class="toast-message">${escapeHtml(message)}</div>
      <button type="button" class="toast-close" aria-label="Close notification">
        <i data-lucide="x"></i>
      </button>
    `;

    elements.toastContainer.appendChild(toast);
    renderIcons(toast);

    const closeBtn = toast.querySelector('.toast-close');
    let timeoutId = null;

    const removeToast = () => {
      if (timeoutId) clearTimeout(timeoutId);
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      setTimeout(() => toast.remove(), 200);
    };

    if (closeBtn) closeBtn.addEventListener('click', removeToast);
    if (duration > 0) {
      timeoutId = setTimeout(removeToast, duration);
    }
  }

  // Process server flash messages on page load
  function processServerFlashMessages() {
    const serverFlashes = document.querySelectorAll('#server-flash-messages .server-flash');
    serverFlashes.forEach((flash) => {
      const category = flash.getAttribute('data-category') || 'info';
      const msg = flash.textContent.trim();
      if (msg) showToast(msg, category === 'danger' ? 'danger' : category === 'success' ? 'success' : 'info');
    });
  }

  // --------------------------------------------------------------------------
  // Icons & Markdown Helpers
  // --------------------------------------------------------------------------
  function renderIcons(container = document) {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons({ root: container });
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderMarkdown(text) {
    if (window.marked && typeof window.marked.parse === 'function') {
      return window.marked.parse(text);
    }
    // Fallback: safe basic line break formatting
    return `<p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>`;
  }

  function highlightCodeBlocks(container = document) {
    if (window.hljs && typeof window.hljs.highlightElement === 'function') {
      container.querySelectorAll('pre code').forEach((block) => {
        window.hljs.highlightElement(block);
      });
    }
  }

  function formatFileSize(bytes) {
    if (!bytes || isNaN(bytes)) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
      bytes /= 1024;
      i++;
    }
    return `${bytes.toFixed(1)} ${units[i]}`;
  }

  // --------------------------------------------------------------------------
  // View Navigation (Upload vs Chat)
  // --------------------------------------------------------------------------
  function switchView(viewName) {
    if (viewName === 'upload') {
      elements.uploadView.classList.remove('view-hidden');
      elements.chatView.classList.add('view-hidden');
    } else {
      elements.uploadView.classList.add('view-hidden');
      elements.chatView.classList.remove('view-hidden');
      scrollToBottom();
      if (elements.questionInput) {
        setTimeout(() => elements.questionInput.focus(), 150);
      }
    }
    closeMobileSidebar();
  }

  function closeMobileSidebar() {
    if (elements.appSidebar) elements.appSidebar.classList.remove('mobile-open');
    if (elements.sidebarBackdrop) elements.sidebarBackdrop.classList.remove('active');
  }

  function openMobileSidebar() {
    if (elements.appSidebar) elements.appSidebar.classList.add('mobile-open');
    if (elements.sidebarBackdrop) elements.sidebarBackdrop.classList.add('active');
  }

  // --------------------------------------------------------------------------
  // Document State Updates in UI
  // --------------------------------------------------------------------------
  function updateDocumentUI(doc) {
    state.document = doc;

    if (doc) {
      // Header pill
      if (elements.headerStatusPill) {
        elements.headerStatusPill.classList.add('active');
        elements.headerStatusText.textContent = `Document: ${doc.filename}`;
      }
      if (elements.headerUploadBtn) {
        elements.headerUploadBtn.querySelector('span').textContent = 'Switch PDF';
      }

      // Sidebar doc card
      if (elements.sidebarDocumentCard) {
        elements.sidebarDocumentCard.className = 'sidebar-doc-card';
        elements.sidebarDocumentCard.innerHTML = `
          <div class="doc-badge-icon">
            <i data-lucide="file-text"></i>
          </div>
          <div class="doc-badge-details">
            <div class="doc-badge-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</div>
            <div class="doc-badge-sub">
              <span>${doc.pages} pages</span>
              <span>·</span>
              <span>${doc.chunks_count || 0} chunks</span>
            </div>
          </div>
          <form action="/reset" method="post" class="reset-form" id="reset-doc-form">
            <input type="hidden" name="csrf_token" value="${state.csrfToken}">
            <button type="submit" class="icon-btn icon-btn-danger" title="Eject Document and Clear Session" aria-label="Reset document">
              <i data-lucide="trash-2"></i>
            </button>
          </form>
        `;
        renderIcons(elements.sidebarDocumentCard);
        bindResetForm();
      }

      if (elements.docPulseIndicator) {
        elements.docPulseIndicator.style.display = 'inline-flex';
      }

      // Chat top banner
      if (elements.bannerDocName) elements.bannerDocName.textContent = doc.filename;
      if (elements.bannerDocMeta) {
        elements.bannerDocMeta.textContent = `${doc.pages} pages · ${doc.chunks_count || 0} chunks indexed in memory`;
      }

      // Sidebar History
      updateHistoryList(doc.history || []);

      switchView('chat');
    } else {
      // No document
      if (elements.headerStatusPill) {
        elements.headerStatusPill.classList.remove('active');
        elements.headerStatusText.textContent = 'No Document';
      }
      if (elements.headerUploadBtn) {
        elements.headerUploadBtn.querySelector('span').textContent = 'Upload PDF';
      }

      if (elements.sidebarDocumentCard) {
        elements.sidebarDocumentCard.className = 'sidebar-doc-card empty';
        elements.sidebarDocumentCard.innerHTML = `
          <div class="sidebar-doc-empty">
            <i data-lucide="file-up" class="doc-empty-icon"></i>
            <p>No document loaded</p>
            <button type="button" class="btn btn-secondary btn-sm" id="sidebar-upload-trigger">
              Upload PDF
            </button>
          </div>
        `;
        renderIcons(elements.sidebarDocumentCard);
        const trigger = document.getElementById('sidebar-upload-trigger');
        if (trigger) trigger.addEventListener('click', () => switchView('upload'));
      }

      if (elements.docPulseIndicator) {
        elements.docPulseIndicator.style.display = 'none';
      }

      updateHistoryList([]);
      switchView('upload');
    }
  }

  function updateHistoryList(history) {
    if (!elements.sidebarHistoryList) return;
    if (elements.historyCount) elements.historyCount.textContent = history.length;

    if (!history || history.length === 0) {
      elements.sidebarHistoryList.innerHTML = `<div class="history-empty">Questions you ask will appear here.</div>`;
      return;
    }

    elements.sidebarHistoryList.innerHTML = '';
    const reversed = [...history].reverse();
    reversed.forEach((item, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'history-item';
      btn.title = item.question;
      btn.innerHTML = `
        <i data-lucide="message-square" class="history-item-icon"></i>
        <span class="history-item-text">${escapeHtml(item.question)}</span>
      `;
      btn.addEventListener('click', () => {
        closeMobileSidebar();
        switchView('chat');
        // Find matching message in chat and scroll to it
        const userMessages = document.querySelectorAll('.user-message');
        const targetIndex = history.length - 1 - idx;
        if (userMessages[targetIndex]) {
          userMessages[targetIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
          userMessages[targetIndex].style.outline = '2px solid var(--accent-primary)';
          setTimeout(() => {
            userMessages[targetIndex].style.outline = 'none';
          }, 1500);
        }
      });
      elements.sidebarHistoryList.appendChild(btn);
    });
    renderIcons(elements.sidebarHistoryList);
  }

  // --------------------------------------------------------------------------
  // File Upload Handling
  // --------------------------------------------------------------------------
  let selectedFile = null;

  function initDropzone() {
    if (!elements.dropzone || !elements.fileInput) return;

    // Click on dropzone opens native file picker
    elements.dropzone.addEventListener('click', (e) => {
      if (e.target.closest('#cancel-file-btn')) return;
      elements.fileInput.click();
    });

    // Drag events
    ['dragenter', 'dragover'].forEach((eventName) => {
      elements.dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropzone.classList.add('drag-over');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      elements.dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropzone.classList.remove('drag-over');
      });
    });

    // Handle dropped files
    elements.dropzone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        handleFileSelection(files[0]);
      }
    });

    // Handle file input change
    elements.fileInput.addEventListener('change', () => {
      if (elements.fileInput.files && elements.fileInput.files.length > 0) {
        handleFileSelection(elements.fileInput.files[0]);
      }
    });

    // Cancel selected file
    if (elements.cancelFileBtn) {
      elements.cancelFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFileSelection();
      });
    }

    // AJAX Form submission
    if (elements.uploadForm) {
      elements.uploadForm.addEventListener('submit', handleUploadSubmit);
    }
  }

  function handleFileSelection(file) {
    if (!file) return;

    // Validate PDF
    const filename = file.name.toLowerCase();
    if (!filename.endsWith('.pdf')) {
      showToast('Please select a valid PDF file.', 'danger');
      clearFileSelection();
      return;
    }

    // Validate size (10 MB = 10,485,760 bytes)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      showToast('File exceeds the 10 MB limit.', 'danger');
      clearFileSelection();
      return;
    }

    selectedFile = file;
    elements.previewFilename.textContent = file.name;
    elements.previewFilesize.textContent = formatFileSize(file.size);

    elements.dropzonePrompt.style.display = 'none';
    elements.filePreview.style.display = 'flex';
    renderIcons(elements.filePreview);
  }

  function clearFileSelection() {
    selectedFile = null;
    if (elements.fileInput) elements.fileInput.value = '';
    elements.dropzonePrompt.style.display = 'block';
    elements.filePreview.style.display = 'none';
    elements.uploadProgressWrapper.style.display = 'none';
    elements.progressBarFill.style.width = '0%';
  }

  async function handleUploadSubmit(e) {
    e.preventDefault();

    if (!selectedFile && (!elements.fileInput.files || !elements.fileInput.files[0])) {
      showToast('Please select a PDF file first.', 'warning');
      return;
    }

    const fileToUpload = selectedFile || elements.fileInput.files[0];
    const formData = new FormData();
    formData.append('document', fileToUpload);
    formData.append('csrf_token', state.csrfToken);

    // Show Progress State
    elements.uploadProgressWrapper.style.display = 'flex';
    elements.uploadSubmitBtn.disabled = true;
    const btnLabel = elements.uploadSubmitBtn.querySelector('.button-label');
    const originalBtnText = btnLabel ? btnLabel.textContent : 'Upload and Process';
    if (btnLabel) btnLabel.textContent = 'Processing PDF...';

    // Simulate multi-phase progress
    let progress = 10;
    elements.progressBarFill.style.width = `${progress}%`;
    elements.progressPercentText.textContent = `${progress}%`;
    elements.progressStatusText.textContent = 'Reading and extracting PDF text...';

    const progressInterval = setInterval(() => {
      if (progress < 40) {
        progress += 8;
        elements.progressStatusText.textContent = 'Extracting pages & checking selectable text...';
      } else if (progress < 75) {
        progress += 4;
        elements.progressStatusText.textContent = 'Generating vector embeddings via Gemini...';
      } else if (progress < 90) {
        progress += 1;
        elements.progressStatusText.textContent = 'Indexing semantic chunks in vector space...';
      }
      elements.progressBarFill.style.width = `${progress}%`;
      elements.progressPercentText.textContent = `${Math.min(progress, 95)}%`;
    }, 400);

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRF-Token': state.csrfToken,
        },
      });

      clearInterval(progressInterval);

      const data = await response.json();

      if (response.ok && data.success) {
        elements.progressBarFill.style.width = '100%';
        elements.progressPercentText.textContent = '100%';
        elements.progressStatusText.textContent = 'Document successfully indexed!';

        showToast(data.message || 'Document indexed and ready for questions!', 'success');

        setTimeout(() => {
          clearFileSelection();
          updateDocumentUI(data.document);
        }, 600);
      } else {
        const errorMsg = data.error || 'Failed to process PDF document.';
        showToast(errorMsg, 'danger');
        elements.uploadProgressWrapper.style.display = 'none';
      }
    } catch (err) {
      clearInterval(progressInterval);
      console.error('Upload error:', err);
      showToast('Network error during upload. Please check connection and try again.', 'danger');
      elements.uploadProgressWrapper.style.display = 'none';
    } finally {
      elements.uploadSubmitBtn.disabled = false;
      if (btnLabel) btnLabel.textContent = originalBtnText;
    }
  }

  // --------------------------------------------------------------------------
  // Chat Q&A Interaction
  // --------------------------------------------------------------------------
  function initChat() {
    if (!elements.questionInput) return;

    // Auto-grow textarea
    elements.questionInput.addEventListener('input', () => {
      elements.questionInput.style.height = 'auto';
      elements.questionInput.style.height = `${Math.min(elements.questionInput.scrollHeight, 160)}px`;

      const len = elements.questionInput.value.length;
      if (elements.charCounter) {
        elements.charCounter.textContent = `${len}/2000`;
      }
      if (elements.sendBtn) {
        elements.sendBtn.disabled = len === 0 || state.isProcessing;
      }
    });

    // Enter to send, Shift+Enter for newline
    elements.questionInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!elements.sendBtn.disabled) {
          elements.askForm.requestSubmit();
        }
      }
    });

    // Ask Form Submit
    if (elements.askForm) {
      elements.askForm.addEventListener('submit', handleAskSubmit);
    }

    // Suggested Questions Chips
    if (elements.suggestedChips) {
      elements.suggestedChips.addEventListener('click', (e) => {
        const chip = e.target.closest('.chip-btn');
        if (chip) {
          const q = chip.getAttribute('data-question');
          if (q && elements.questionInput) {
            elements.questionInput.value = q;
            elements.questionInput.dispatchEvent(new Event('input'));
            elements.askForm.requestSubmit();
          }
        }
      });
    }

    // Copy Message Handler (Event Delegation)
    if (elements.chatMessages) {
      elements.chatMessages.addEventListener('click', (e) => {
        const copyBtn = e.target.closest('.copy-msg-btn');
        if (copyBtn) {
          const aiWrapper = copyBtn.closest('.ai-message');
          const rawAnswer = aiWrapper.querySelector('.markdown-rendered');
          if (rawAnswer) {
            const textToCopy = rawAnswer.getAttribute('data-raw-answer') || rawAnswer.innerText;
            navigator.clipboard.writeText(textToCopy).then(() => {
              showToast('Answer copied to clipboard!', 'success', 2000);
              copyBtn.innerHTML = '<i data-lucide="check"></i>';
              renderIcons(copyBtn);
              setTimeout(() => {
                copyBtn.innerHTML = '<i data-lucide="copy"></i>';
                renderIcons(copyBtn);
              }, 2000);
            }).catch(() => {
              showToast('Could not copy to clipboard', 'warning');
            });
          }
        }
      });
    }

    // Initial render of existing markdown on page load
    document.querySelectorAll('.message-content.markdown-rendered').forEach((el) => {
      const raw = el.getAttribute('data-raw-answer') || el.innerText;
      el.innerHTML = renderMarkdown(raw);
    });
    highlightCodeBlocks();
    renderIcons();
    scrollToBottom();
  }

  async function handleAskSubmit(e) {
    e.preventDefault();

    const question = elements.questionInput.value.trim();
    if (!question || state.isProcessing) return;

    if (!state.document) {
      showToast('Please upload a document first.', 'warning');
      switchView('upload');
      return;
    }

    state.isProcessing = true;
    elements.sendBtn.disabled = true;
    elements.questionInput.value = '';
    elements.questionInput.style.height = 'auto';
    if (elements.charCounter) elements.charCounter.textContent = '0/2000';

    // 1. Append User Message
    appendUserMessage(question);
    scrollToBottom();

    // 2. Show Live Typing / Searching placeholder
    if (elements.liveTypingMessage) {
      elements.liveTypingMessage.style.display = 'flex';
      scrollToBottom();
    }

    // 3. Make AJAX Request
    const formData = new FormData();
    formData.append('question', question);
    formData.append('csrf_token', state.csrfToken);

    try {
      const response = await fetch('/ask', {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRF-Token': state.csrfToken,
        },
      });

      if (elements.liveTypingMessage) {
        elements.liveTypingMessage.style.display = 'none';
      }

      const data = await response.json();

      if (response.ok && data.success) {
        // Append AI response
        appendAiMessage(data.answer, data.sources || [], data.passages || []);

        // Update local state history
        if (!state.document.history) state.document.history = [];
        state.document.history.push({
          question: data.question,
          answer: data.answer,
          sources: data.sources,
          passages: data.passages,
        });
        updateHistoryList(state.document.history);
      } else {
        const errorMsg = data.error || 'Failed to generate answer.';
        showToast(errorMsg, 'danger');
        appendErrorMessage(errorMsg);

        if (data.expired) {
          updateDocumentUI(null);
        }
      }
    } catch (err) {
      if (elements.liveTypingMessage) {
        elements.liveTypingMessage.style.display = 'none';
      }
      console.error('Ask error:', err);
      showToast('Could not reach server. Check connection.', 'danger');
      appendErrorMessage('A network error occurred while connecting to Gemini. Please try again.');
    } finally {
      state.isProcessing = false;
      elements.sendBtn.disabled = elements.questionInput.value.trim().length === 0;
      scrollToBottom();
    }
  }

  function appendUserMessage(question) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper user-message';
    wrapper.innerHTML = `
      <div class="message-body">
        <div class="message-sender-row">
          <span class="sender-name">You</span>
        </div>
        <div class="message-content">
          <p>${escapeHtml(question)}</p>
        </div>
      </div>
      <div class="message-avatar user-avatar">
        <i data-lucide="user"></i>
      </div>
    `;
    elements.chatMessages.insertBefore(wrapper, elements.liveTypingMessage);
    renderIcons(wrapper);
  }

  function appendAiMessage(answer, sources = [], passages = []) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper ai-message';

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
      const pills = sources.map((p) => `<span class="source-pill">Page ${p}</span>`).join('');
      let passagesHtml = '';

      if (passages && passages.length > 0) {
        const passageItems = passages.map((p) => {
          const pageSpan = p.page_end && p.page_end !== p.page_start
            ? `Page ${p.page_start}-${p.page_end}`
            : `Page ${p.page_start}`;
          const scoreBadge = p.similarity ? `<span class="passage-score">Similarity: ${p.similarity}</span>` : '';
          return `
            <div class="passage-item">
              <div class="passage-meta">
                <span class="passage-page">${pageSpan}</span>
                ${scoreBadge}
              </div>
              <div class="passage-text">${escapeHtml(p.text)}</div>
            </div>
          `;
        }).join('');

        passagesHtml = `
          <details class="passages-accordion">
            <summary class="accordion-toggle">
              <i data-lucide="chevron-right" class="toggle-icon"></i>
              <span>Inspect retrieved context passages (${passages.length})</span>
            </summary>
            <div class="passages-list">
              ${passageItems}
            </div>
          </details>
        `;
      }

      sourcesHtml = `
        <div class="sources-card">
          <div class="sources-header">
            <div class="sources-title">
              <i data-lucide="bookmark"></i>
              <span>Retrieved Source Pages:</span>
            </div>
            <div class="source-pills">
              ${pills}
            </div>
          </div>
          ${passagesHtml}
        </div>
      `;
    }

    const htmlContent = renderMarkdown(answer);

    wrapper.innerHTML = `
      <div class="message-avatar">
        <i data-lucide="sparkles"></i>
      </div>
      <div class="message-body">
        <div class="message-sender-row">
          <span class="sender-name">DocuMind AI</span>
          <span class="sender-badge">Gemini RAG</span>
          <div class="message-actions">
            <button type="button" class="action-btn copy-msg-btn" title="Copy answer" aria-label="Copy answer">
              <i data-lucide="copy"></i>
            </button>
          </div>
        </div>
        <div class="message-content markdown-rendered" data-raw-answer="${escapeHtml(answer)}">
          ${htmlContent}
        </div>
        ${sourcesHtml}
        <div class="message-disclaimer">
          <i data-lucide="info"></i>
          <span>Grounded in document excerpts. Always verify critical facts in the original pages.</span>
        </div>
      </div>
    `;

    elements.chatMessages.insertBefore(wrapper, elements.liveTypingMessage);
    highlightCodeBlocks(wrapper);
    renderIcons(wrapper);
  }

  function appendErrorMessage(errorMsg) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper ai-message';
    wrapper.innerHTML = `
      <div class="message-avatar" style="background: var(--status-danger);">
        <i data-lucide="alert-triangle"></i>
      </div>
      <div class="message-body">
        <div class="message-sender-row">
          <span class="sender-name">System Alert</span>
        </div>
        <div class="message-content" style="border-color: rgba(239, 68, 68, 0.3);">
          <p style="color: var(--status-danger);">${escapeHtml(errorMsg)}</p>
        </div>
      </div>
    `;
    elements.chatMessages.insertBefore(wrapper, elements.liveTypingMessage);
    renderIcons(wrapper);
  }

  function scrollToBottom() {
    if (elements.chatMessages) {
      elements.chatMessages.scrollTo({
        top: elements.chatMessages.scrollHeight,
        behavior: 'smooth',
      });
    }
  }

  // --------------------------------------------------------------------------
  // Reset Document & Conversation
  // --------------------------------------------------------------------------
  function bindResetForm() {
    const form = document.getElementById('reset-doc-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!confirm('Are you sure you want to eject the active document and clear this conversation?')) {
        return;
      }

      try {
        const formData = new FormData();
        formData.append('csrf_token', state.csrfToken);

        const response = await fetch('/reset', {
          method: 'POST',
          body: formData,
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': state.csrfToken,
          },
        });

        const data = await response.json();
        if (response.ok && data.success) {
          showToast(data.message || 'Session reset successfully.', 'info');
          updateDocumentUI(null);
        } else {
          showToast('Could not reset session.', 'danger');
        }
      } catch (err) {
        console.error('Reset error:', err);
        showToast('Network error while resetting session.', 'danger');
      }
    });
  }

  // --------------------------------------------------------------------------
  // Modal Management
  // --------------------------------------------------------------------------
  function initModals() {
    const openSettings = () => {
      if (elements.settingsModal) elements.settingsModal.style.display = 'flex';
      renderIcons(elements.settingsModal);
    };

    const closeSettings = () => {
      if (elements.settingsModal) elements.settingsModal.style.display = 'none';
    };

    if (elements.openSettingsBtn) elements.openSettingsBtn.addEventListener('click', openSettings);
    if (elements.closeSettingsBtn) elements.closeSettingsBtn.addEventListener('click', closeSettings);
    if (elements.modalDoneBtn) elements.modalDoneBtn.addEventListener('click', closeSettings);

    if (elements.settingsModal) {
      elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) closeSettings();
      });
    }

    // Escape key closes modals
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeSettings();
    });
  }

  // --------------------------------------------------------------------------
  // Sidebar & Navigation Event Listeners
  // --------------------------------------------------------------------------
  function initNavigation() {
    // Mobile Drawer
    if (elements.mobileMenuBtn) {
      elements.mobileMenuBtn.addEventListener('click', openMobileSidebar);
    }
    if (elements.sidebarCloseBtn) {
      elements.sidebarCloseBtn.addEventListener('click', closeMobileSidebar);
    }
    if (elements.sidebarBackdrop) {
      elements.sidebarBackdrop.addEventListener('click', closeMobileSidebar);
    }

    // Desktop Collapse Toggle
    if (elements.sidebarCollapseBtn) {
      elements.sidebarCollapseBtn.addEventListener('click', () => {
        state.sidebarCollapsed = !state.sidebarCollapsed;
        elements.appSidebar.classList.toggle('collapsed', state.sidebarCollapsed);
      });
    }

    // New Chat / New Conversation button
    if (elements.newChatBtn) {
      elements.newChatBtn.addEventListener('click', () => {
        if (state.document) {
          if (confirm('Start a new session? This will eject the current document.')) {
            const resetForm = document.getElementById('reset-doc-form');
            if (resetForm) resetForm.requestSubmit();
            else switchView('upload');
          }
        } else {
          switchView('upload');
        }
      });
    }

    // Switch Document Buttons
    if (elements.headerUploadBtn) {
      elements.headerUploadBtn.addEventListener('click', () => {
        const currentView = elements.uploadView.classList.contains('view-hidden') ? 'chat' : 'upload';
        switchView(currentView === 'upload' ? 'chat' : 'upload');
      });
    }
    if (elements.switchDocBtn) {
      elements.switchDocBtn.addEventListener('click', () => {
        switchView('upload');
      });
    }

    // Theme Toggles
    if (elements.headerThemeToggle) {
      elements.headerThemeToggle.addEventListener('click', toggleTheme);
    }
    if (elements.sidebarThemeToggle) {
      elements.sidebarThemeToggle.addEventListener('click', toggleTheme);
    }

    // Sidebar Upload PDF shortcut button (when empty)
    const sidebarUpload = document.getElementById('sidebar-upload-trigger');
    if (sidebarUpload) {
      sidebarUpload.addEventListener('click', () => switchView('upload'));
    }
  }

  // --------------------------------------------------------------------------
  // Bootstrap Application
  // --------------------------------------------------------------------------
  function init() {
    initTheme();
    renderIcons();
    initNavigation();
    initDropzone();
    initChat();
    initModals();
    bindResetForm();
    processServerFlashMessages();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
