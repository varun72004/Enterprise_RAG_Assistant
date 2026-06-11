// ========================================
// PDF AI Chatbot — Frontend Application
// ========================================

'use strict';

// ── Constants & State ──────────────────────────────────────────

/** @type {string} Base URL for API requests (empty = same origin) */
const API_BASE = 'https://pdf-ai-chatbot-backend-mcym.onrender.com';

/** @type {number} Maximum file size in bytes (50 MB) */
const MAX_FILE_SIZE = 50 * 1024 * 1024;

/** @type {Array<{role: string, content: string, sources?: Array}>} Chat message history */
let chatMessages = [];

/** @type {Array<{filename: string, size?: number}>} Currently uploaded documents */
let uploadedDocs = [];

/** @type {boolean} Whether the assistant is currently streaming a response */
let isStreaming = false;


// ── DOM References ─────────────────────────────────────────────

/** @type {Object<string, HTMLElement>} Cached DOM element references */
let DOM = {};

/**
 * Initialise all DOM references once the document is ready.
 */
function cacheDOMReferences() {
    DOM = {
        // Header / Layout
        header:           document.getElementById('app-header'),
        sidebar:          document.getElementById('sidebar'),
        sidebarToggle:    document.getElementById('sidebar-toggle'),
        sidebarOverlay:   document.getElementById('sidebar-overlay'),

        // Upload
        uploadArea:       document.getElementById('upload-area'),
        fileInput:        document.getElementById('file-input'),
        uploadBtn:        document.getElementById('upload-btn'),
        uploadProgress:   document.getElementById('upload-progress'),
        uploadProgressBar:document.getElementById('upload-progress-bar'),
        progressFilename: document.querySelector('.progress-filename'),
        progressPercent:  document.querySelector('.progress-percent'),

        // Document list
        pdfList:          document.getElementById('pdf-list'),
        pdfCount:         document.getElementById('pdf-count'),
        pdfListEmpty:     document.getElementById('pdf-list-empty'),

        // Chat
        chatContainer:    document.getElementById('chat-container'),
        chatMessages:     document.getElementById('chat-messages'),
        welcomeScreen:    document.getElementById('welcome-screen'),
        typingIndicator:  document.getElementById('typing-indicator'),

        // Input
        messageInput:     document.getElementById('message-input'),
        sendBtn:          document.getElementById('send-btn'),
        clearBtn:         document.getElementById('clear-btn'),

        // Toasts
        toastContainer:   document.getElementById('toast-container'),
    };
}


// ── Initialisation ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    cacheDOMReferences();
    setupEventListeners();
    setupDragAndDrop();
    refreshDocuments();

    // Auto-focus the input field
    DOM.messageInput.focus();
});


// ── Event Listeners ────────────────────────────────────────────

/**
 * Wire up all interactive event listeners.
 */
function setupEventListeners() {
    // Send message
    DOM.sendBtn.addEventListener('click', sendMessage);
    DOM.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Clear chat
    DOM.clearBtn.addEventListener('click', clearChat);

    // File upload
    DOM.uploadBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        DOM.fileInput.click();
    });
    DOM.uploadArea.addEventListener('click', () => DOM.fileInput.click());
    DOM.uploadArea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            DOM.fileInput.click();
        }
    });
    DOM.fileInput.addEventListener('change', (e) => handleFileSelect(e.target.files));

    // Mobile sidebar toggle
    DOM.sidebarToggle.addEventListener('click', toggleSidebar);
    DOM.sidebarOverlay.addEventListener('click', toggleSidebar);
}


// ── Drag & Drop ────────────────────────────────────────────────

/**
 * Set up drag-and-drop event handlers on the upload area.
 */
function setupDragAndDrop() {
    const area = DOM.uploadArea;

    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        area.classList.add('drag-over');
    });

    area.addEventListener('dragenter', (e) => {
        e.preventDefault();
        e.stopPropagation();
        area.classList.add('drag-over');
    });

    area.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        area.classList.remove('drag-over');
    });

    area.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        area.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            handleFileSelect(e.dataTransfer.files);
        }
    });
}


// ── Upload Functions ───────────────────────────────────────────

/**
 * Validate and begin uploading each selected file.
 * @param {FileList} files - Selected file list from input or drop event.
 */
function handleFileSelect(files) {
    if (!files || !files.length) return;

    for (const file of files) {
        // Validate extension
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showToast(`"${file.name}" is not a PDF file.`, 'error');
            continue;
        }
        // Validate size
        if (file.size > MAX_FILE_SIZE) {
            showToast(`"${file.name}" exceeds the 50 MB size limit.`, 'error');
            continue;
        }
        uploadFile(file);
    }

    // Reset file input so the same file can be re-selected
    DOM.fileInput.value = '';
}


/**
 * Upload a single PDF file to the server using XMLHttpRequest for progress tracking.
 * @param {File} file - The PDF file to upload.
 */
function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();

    // Show progress bar
    DOM.uploadProgress.style.display = 'block';
    if (DOM.progressFilename) DOM.progressFilename.textContent = file.name;
    if (DOM.progressPercent) DOM.progressPercent.textContent = '0%';
    DOM.uploadProgressBar.style.width = '0%';
    DOM.uploadProgressBar.setAttribute('aria-valuenow', '0');

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            DOM.uploadProgressBar.style.width = `${pct}%`;
            DOM.uploadProgressBar.setAttribute('aria-valuenow', String(pct));
            if (DOM.progressPercent) DOM.progressPercent.textContent = `${pct}%`;
        }
    });

    xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
            showToast(`"${file.name}" uploaded successfully!`, 'success');
            refreshDocuments();
        } else {
            let detail = 'Upload failed.';
            try {
                const resp = JSON.parse(xhr.responseText);
                detail = resp.detail || detail;
            } catch (_) { /* ignore */ }
            showToast(detail, 'error');
        }
        hideUploadProgress();
    });

    xhr.addEventListener('error', () => {
        showToast(`Failed to upload "${file.name}". Network error.`, 'error');
        hideUploadProgress();
    });

    xhr.addEventListener('abort', () => {
        showToast(`Upload of "${file.name}" was cancelled.`, 'warning');
        hideUploadProgress();
    });

    xhr.open('POST', `${API_BASE}/upload`);
    xhr.send(formData);
}


/**
 * Hide the upload progress bar after a brief delay.
 */
function hideUploadProgress() {
    setTimeout(() => {
        DOM.uploadProgress.style.display = 'none';
        DOM.uploadProgressBar.style.width = '0%';
    }, 600);
}


/**
 * Fetch the current list of documents from the server and re-render the sidebar.
 */
async function refreshDocuments() {
    try {
        const res = await fetch(`${API_BASE}/documents`);
        if (!res.ok) throw new Error('Failed to fetch documents');
        const data = await res.json();
        uploadedDocs = data.documents || data || [];
        renderDocumentList(uploadedDocs);
    } catch (err) {
        console.warn('Could not fetch documents:', err);
        // Don't show toast on initial load failure — silent retry
    }
}


/**
 * Render the list of PDF items in the sidebar.
 * @param {Array<{filename: string, size?: number, pages?: number}>} docs
 */
function renderDocumentList(docs) {
    // Update badge count
    DOM.pdfCount.textContent = String(docs.length);

    // Remove existing PDF items (keep the empty-state element)
    const existing = DOM.pdfList.querySelectorAll('.pdf-item');
    existing.forEach((el) => el.remove());

    // Show/hide empty state
    if (DOM.pdfListEmpty) {
        DOM.pdfListEmpty.style.display = docs.length === 0 ? 'flex' : 'none';
    }

    // Create items
    docs.forEach((doc) => {
        const item = document.createElement('div');
        item.className = 'pdf-item';

        const name = typeof doc === 'string' ? doc : doc.filename;
        const size = typeof doc === 'object' && doc.size ? formatFileSize(doc.size) : '';

        item.innerHTML = `
            <div class="pdf-item-icon"><i class="bi bi-file-earmark-pdf-fill"></i></div>
            <div class="pdf-item-info">
                <div class="pdf-item-name" title="${escapeHTML(name)}">${escapeHTML(name)}</div>
                ${size ? `<div class="pdf-item-meta">${size}</div>` : ''}
            </div>
            <button class="pdf-item-delete" title="Remove document" aria-label="Delete ${escapeHTML(name)}">
                <i class="bi bi-x-lg"></i>
            </button>
        `;

        // Delete handler
        item.querySelector('.pdf-item-delete').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteDocument(name);
        });

        DOM.pdfList.appendChild(item);
    });
}


/**
 * Delete a document from the server and refresh the list.
 * @param {string} filename - The filename to delete.
 */
async function deleteDocument(filename) {
    try {
        const res = await fetch(`${API_BASE}/document/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || 'Failed to delete document');
        }
        showToast(`"${filename}" removed.`, 'success');
        refreshDocuments();
    } catch (err) {
        showToast(err.message, 'error');
    }
}


// ── Chat Functions ─────────────────────────────────────────────

/**
 * Send the user's question to the /chat endpoint and stream the response via SSE.
 */
async function sendMessage() {
    const question = DOM.messageInput.value.trim();
    if (!question || isStreaming) return;

    // Hide welcome, show messages
    toggleWelcomeScreen(false);

    // Add user message to UI
    addMessageToUI('user', question);
    chatMessages.push({ role: 'user', content: question });

    // Clear input & lock UI
    DOM.messageInput.value = '';
    setStreamingState(true);
    showTypingIndicator();

    // Create an empty assistant message element to stream into
    const assistantWrapper = createEmptyAssistantMessage();
    const bubbleEl = assistantWrapper.querySelector('.message-bubble');
    let fullContent = '';

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Failed to get response' }));
            throw new Error(error.detail || 'Failed to get response');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const raw = line.slice(6).trim();
                if (!raw) continue;

                try {
                    const data = JSON.parse(raw);

                    switch (data.type) {
                        case 'token':
                            fullContent += data.content;
                            bubbleEl.textContent = fullContent;
                            scrollToBottom();
                            break;

                        case 'sources':
                            if (data.content && data.content.length > 0) {
                                const sourceHTML = createSourceCards(data.content);
                                assistantWrapper.insertAdjacentHTML('beforeend', sourceHTML);
                            }
                            break;

                        case 'done':
                            // Streaming complete
                            break;

                        case 'error':
                            showToast(data.content || 'An error occurred.', 'error');
                            break;

                        default:
                            break;
                    }
                } catch (parseErr) {
                    console.warn('Failed to parse SSE data:', raw, parseErr);
                }
            }
        }

        // Store final message
        chatMessages.push({ role: 'assistant', content: fullContent });

    } catch (err) {
        // Remove the empty assistant message if an error occurred before any content
        if (!fullContent) {
            assistantWrapper.remove();
        }
        showToast(err.message || 'An error occurred while sending your message.', 'error');
    } finally {
        hideTypingIndicator();
        setStreamingState(false);
        DOM.messageInput.focus();
        scrollToBottom();
    }
}


/**
 * Add a fully-formed message to the chat UI.
 * @param {'user'|'assistant'} role - The message sender role.
 * @param {string} content - The message text content.
 * @param {Array} [sources] - Optional source references.
 */
function addMessageToUI(role, content, sources) {
    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper ${role}`;

    const label = role === 'user' ? 'You' : 'AI Assistant';

    wrapper.innerHTML = `
        <span class="message-label">${label}</span>
        <div class="message-bubble">${escapeHTML(content)}</div>
    `;

    if (sources && sources.length > 0) {
        wrapper.insertAdjacentHTML('beforeend', createSourceCards(sources));
    }

    // Insert before typing indicator
    DOM.chatMessages.insertBefore(wrapper, DOM.typingIndicator);
    scrollToBottom();
}


/**
 * Create an empty assistant message wrapper and insert it into the chat.
 * @returns {HTMLElement} The wrapper element containing the empty bubble.
 */
function createEmptyAssistantMessage() {
    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper assistant';
    wrapper.innerHTML = `
        <span class="message-label">AI Assistant</span>
        <div class="message-bubble"></div>
    `;
    DOM.chatMessages.insertBefore(wrapper, DOM.typingIndicator);
    return wrapper;
}


/**
 * Generate HTML for source reference cards.
 * @param {Array<{filename: string, page?: number, content?: string, excerpt?: string}>} sources
 * @returns {string} HTML string for the source cards section.
 */
function createSourceCards(sources) {
    if (!sources || sources.length === 0) return '';

    const uid = `src-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    const cards = sources.map((src) => {
        const filename = src.filename || src.source || 'Unknown';
        const page = src.page != null ? src.page : (src.page_number != null ? src.page_number : null);
        const excerpt = src.content || src.excerpt || '';

        return `
            <div class="source-card">
                <div class="source-card-icon"><i class="bi bi-file-earmark-pdf-fill"></i></div>
                <div class="source-card-body">
                    <div class="source-card-header">
                        <span class="source-card-filename" title="${escapeHTML(filename)}">${escapeHTML(filename)}</span>
                        ${page != null ? `<span class="source-card-page">p. ${page}</span>` : ''}
                    </div>
                    ${excerpt ? `<div class="source-card-excerpt">${escapeHTML(excerpt)}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="source-cards-wrapper">
            <button class="source-toggle-btn" onclick="toggleSourceCards('${uid}', this)" type="button">
                <i class="bi bi-chevron-down"></i>
                ${sources.length} source${sources.length !== 1 ? 's' : ''}
            </button>
            <div class="source-cards-list" id="${uid}">
                ${cards}
            </div>
        </div>
    `;
}


/**
 * Toggle the visibility of a source cards list.
 * @param {string} id - The DOM id of the source cards list.
 * @param {HTMLElement} btn - The toggle button element.
 */
function toggleSourceCards(id, btn) {
    const list = document.getElementById(id);
    if (!list) return;
    const isExpanded = list.classList.toggle('expanded');
    btn.classList.toggle('expanded', isExpanded);
}
// Expose to global scope for inline onclick
window.toggleSourceCards = toggleSourceCards;


/**
 * Clear the chat history: call the backend, reset local state, and restore the welcome screen.
 */
async function clearChat() {
    try {
        await fetch(`${API_BASE}/clear-chat`, { method: 'POST' });
    } catch (err) {
        console.warn('Backend clear-chat failed (may not be implemented):', err);
    }

    chatMessages = [];

    // Remove all message wrappers (keep welcome screen & typing indicator)
    const wrappers = DOM.chatMessages.querySelectorAll('.message-wrapper');
    wrappers.forEach((el) => el.remove());

    toggleWelcomeScreen(true);
    showToast('Chat cleared.', 'info');
    DOM.messageInput.focus();
}


// ── UI Helpers ─────────────────────────────────────────────────

/**
 * Create and show a Bootstrap 5 toast notification.
 * @param {string} message - The notification message.
 * @param {'success'|'error'|'warning'|'info'} [type='info'] - The visual type of the toast.
 */
function showToast(message, type = 'info') {
    const iconMap = {
        success: 'bi-check-circle-fill',
        error:   'bi-exclamation-triangle-fill',
        warning: 'bi-exclamation-circle-fill',
        info:    'bi-info-circle-fill',
    };

    const toastId = `toast-${Date.now()}`;

    const toastHTML = `
        <div id="${toastId}" class="toast toast-glass" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="5000">
            <div class="toast-accent-bar ${type}"></div>
            <div class="toast-header">
                <i class="bi ${iconMap[type] || iconMap.info} toast-icon ${type}"></i>
                <strong class="me-auto" style="font-size:0.82rem;">${capitalise(type)}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">${escapeHTML(message)}</div>
        </div>
    `;

    DOM.toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    const toastEl = document.getElementById(toastId);
    const bsToast = new bootstrap.Toast(toastEl, { delay: 5000 });
    bsToast.show();

    // Remove from DOM after hidden
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}


/**
 * Show the typing indicator in the chat.
 */
function showTypingIndicator() {
    DOM.typingIndicator.style.display = 'block';
    scrollToBottom();
}


/**
 * Hide the typing indicator.
 */
function hideTypingIndicator() {
    DOM.typingIndicator.style.display = 'none';
}


/**
 * Show or hide the welcome screen.
 * @param {boolean} show - Whether to display the welcome screen.
 */
function toggleWelcomeScreen(show) {
    DOM.welcomeScreen.style.display = show ? 'flex' : 'none';
}


/**
 * Smooth-scroll the chat messages container to the bottom.
 */
function scrollToBottom() {
    requestAnimationFrame(() => {
        DOM.chatMessages.scrollTo({
            top: DOM.chatMessages.scrollHeight,
            behavior: 'smooth',
        });
    });
}


/**
 * Lock or unlock the UI during streaming.
 * @param {boolean} streaming - Whether the app is currently streaming.
 */
function setStreamingState(streaming) {
    isStreaming = streaming;
    DOM.messageInput.disabled = streaming;
    DOM.sendBtn.disabled = streaming;
}


/**
 * Format a byte count into a human-readable string.
 * @param {number} bytes - File size in bytes.
 * @returns {string} Formatted string, e.g. "2.4 MB".
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const size = (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1);
    return `${size} ${units[i]}`;
}


/**
 * Toggle the sidebar open/closed on mobile viewports.
 */
function toggleSidebar() {
    const isOpen = DOM.sidebar.classList.toggle('open');
    DOM.sidebarOverlay.classList.toggle('active', isOpen);
}


/**
 * Escape HTML special characters for safe insertion.
 * @param {string} str - Raw string.
 * @returns {string} Escaped string safe for innerHTML.
 */
function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}


/**
 * Capitalise the first letter of a string.
 * @param {string} str
 * @returns {string}
 */
function capitalise(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}
