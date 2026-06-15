// ========================================
// PDF AI Chatbot — Frontend Application
// ========================================

'use strict';

// ── Constants & State ──────────────────────────────────────────

/** @type {string} Base URL for API requests (empty = same origin) */
const API_BASE = '';

/** @type {number} Maximum file size in bytes (50 MB) */
const MAX_FILE_SIZE = 50 * 1024 * 1024;

/** @type {Array<{role: string, content: string, sources?: Array}>} Chat message history */
let chatMessages = [];

/** @type {Array<Object>} Currently uploaded documents with metadata */
let uploadedDocs = [];

/** @type {boolean} Whether the assistant is currently streaming a response */
let isStreaming = false;

/** @type {string} Unique session ID for isolating this user's uploads and chat */
let sessionId = sessionStorage.getItem('pdf_chat_session_id');
if (!sessionId) {
    sessionId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
    sessionStorage.setItem('pdf_chat_session_id', sessionId);
}


// ── DOM References ─────────────────────────────────────────────

/** @type {Object<string, HTMLElement>} Cached DOM element references */
let DOM = {};

/**
 * Initialise all DOM references once the document is ready.
 */
function cacheDOMReferences() {
    DOM = {
        // Layout
        sidebar:          document.getElementById('sidebar'),
        sidebarToggle:    document.getElementById('sidebar-toggle'),
        sidebarOverlay:   document.getElementById('sidebar-overlay'),

        // Upload
        uploadArea:       document.getElementById('upload-area'),
        fileInput:        document.getElementById('file-input'),
        uploadProgress:   document.getElementById('upload-progress'),
        uploadProgressBar:document.getElementById('upload-progress-bar'),
        progressFilename: document.querySelector('.progress-filename'),
        progressPercent:  document.querySelector('.progress-percent'),

        // Document list
        pdfList:          document.getElementById('pdf-list'),
        pdfCount:         document.getElementById('pdf-count'),
        pdfListEmpty:     document.getElementById('pdf-list-empty'),

        // Chat
        chatMessages:     document.getElementById('chat-messages'),
        welcomeScreen:    document.getElementById('welcome-screen'),
        typingIndicator:  document.getElementById('typing-indicator'),

        // Input
        messageInput:     document.getElementById('message-input'),
        sendBtn:          document.getElementById('send-btn'),
        clearBtn:         document.getElementById('clear-btn'),
        queryAttachBtn:   document.getElementById('query-attach-btn'),

        // Toasts
        toastContainer:   document.getElementById('toast-container'),

        // Summary Metrics Cards
        summaryDocsCount:     document.getElementById('summary-docs-count'),
        summaryChunksCount:    document.getElementById('summary-chunks-count'),

        // Attribution List
        attributionList:      document.getElementById('attribution-list'),

        // Pipeline Elements
        pipelineRetrieved:    document.getElementById('pipeline-retrieved'),
        pipelineReranked:     document.getElementById('pipeline-reranked'),
        pipelineRatio:        document.getElementById('pipeline-ratio'),
        pipelineTokens:       document.getElementById('pipeline-tokens'),
        generationStatusBar:  document.getElementById('generation-status-bar'),
        generationStatusText: document.getElementById('generation-status-text'),

        // Pipeline Flow Nodes
        nodeQuery:            document.getElementById('pipeline-node-query'),
        nodeRetrieve:         document.getElementById('pipeline-node-retrieve'),
        nodeRerank:           document.getElementById('pipeline-node-rerank'),
        nodeCompress:         document.getElementById('pipeline-node-compress'),
        nodeLlm:              document.getElementById('pipeline-node-llm'),
    };
}


// ── Initialisation ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    cacheDOMReferences();
    setupEventListeners();
    setupDragAndDrop();
    refreshDocuments();
    updateSummaryCards();

    // Auto-focus the input field
    if (DOM.messageInput) DOM.messageInput.focus();
});


// ── Event Listeners ────────────────────────────────────────────

/**
 * Wire up all interactive event listeners.
 */
function setupEventListeners() {
    // Send message
    if (DOM.sendBtn) DOM.sendBtn.addEventListener('click', sendMessage);
    if (DOM.messageInput) {
        DOM.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Clear chat
    if (DOM.clearBtn) DOM.clearBtn.addEventListener('click', clearChat);

    // File upload trigger
    if (DOM.queryAttachBtn) {
        DOM.queryAttachBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            DOM.fileInput.click();
        });
    }
    if (DOM.uploadArea) {
        DOM.uploadArea.addEventListener('click', () => DOM.fileInput.click());
        DOM.uploadArea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                DOM.fileInput.click();
            }
        });
    }
    if (DOM.fileInput) DOM.fileInput.addEventListener('change', (e) => handleFileSelect(e.target.files));

    // Mobile sidebar toggle
    if (DOM.sidebarToggle) DOM.sidebarToggle.addEventListener('click', toggleSidebar);
    if (DOM.sidebarOverlay) DOM.sidebarOverlay.addEventListener('click', toggleSidebar);
}


// ── Drag & Drop ────────────────────────────────================

/**
 * Set up drag-and-drop event handlers on the upload area.
 */
function setupDragAndDrop() {
    const area = DOM.uploadArea;
    if (!area) return;

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

    const allowedExtensions = ['.pdf', '.html', '.htm', '.csv'];

    for (const file of files) {
        // Validate extension
        const fileName = file.name.toLowerCase();
        const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));
        if (!hasValidExtension) {
            showToast(`"${file.name}" is not a supported file type. Allowed: PDF, HTML, CSV.`, 'error');
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
 * Upload a single file to the server using XMLHttpRequest for progress tracking.
 * @param {File} file - The file to upload.
 */
function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();

    // Show progress bar
    if (DOM.uploadProgress) DOM.uploadProgress.style.display = 'block';
    if (DOM.progressFilename) DOM.progressFilename.textContent = file.name;
    if (DOM.progressPercent) DOM.progressPercent.textContent = '0%';
    if (DOM.uploadProgressBar) {
        DOM.uploadProgressBar.style.width = '0%';
        DOM.uploadProgressBar.setAttribute('aria-valuenow', '0');
    }

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            if (DOM.uploadProgressBar) {
                DOM.uploadProgressBar.style.width = `${pct}%`;
                DOM.uploadProgressBar.setAttribute('aria-valuenow', String(pct));
            }
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
            refreshDocuments();
        }
        hideUploadProgress();
    });

    xhr.addEventListener('error', () => {
        showToast(`Failed to upload "${file.name}". Network error.`, 'error');
        hideUploadProgress();
        refreshDocuments();
    });

    xhr.open('POST', `${API_BASE}/upload`);
    xhr.setRequestHeader('X-Session-ID', sessionId);
    xhr.send(formData);
}


/**
 * Hide the upload progress bar after a brief delay.
 */
function hideUploadProgress() {
    setTimeout(() => {
        if (DOM.uploadProgress) DOM.uploadProgress.style.display = 'none';
        if (DOM.uploadProgressBar) DOM.uploadProgressBar.style.width = '0%';
    }, 600);
}


/**
 * Fetch the current list of documents from the server and re-render the sidebar.
 */
async function refreshDocuments() {
    try {
        const res = await fetch(`${API_BASE}/documents`, {
            headers: { 'X-Session-ID': sessionId }
        });
        if (!res.ok) throw new Error('Failed to fetch documents');
        const data = await res.json();
        uploadedDocs = data.documents || data || [];
        renderDocumentList(uploadedDocs);
        updateSummaryCards();
    } catch (err) {
        console.warn('Could not fetch documents:', err);
    }
}


/**
 * Render the list of document items in the sidebar Left Panel.
 * @param {Array<Object>} docs
 */
function renderDocumentList(docs) {
    if (DOM.pdfCount) DOM.pdfCount.textContent = String(docs.length);

    // Remove existing cards
    const existing = DOM.pdfList.querySelectorAll('.file-item-card');
    existing.forEach((el) => el.remove());

    if (DOM.pdfListEmpty) {
        DOM.pdfListEmpty.style.display = docs.length === 0 ? 'flex' : 'none';
    }

    docs.forEach((doc) => {
        const item = document.createElement('div');
        item.className = 'file-item-card';

        const name = doc.filename;
        const size = doc.file_size ? formatFileSize(doc.file_size) : '0 KB';
        const type = doc.document_type || 'PDF';
        const status = (doc.status || 'Indexed').toLowerCase();
        const chunkCount = doc.chunk_count || 0;
        const pageCount = doc.page_count || 0;

        let statusClass = 'indexed';
        let statusBadgeText = '✓ Indexed';
        if (status === 'processing') {
            statusClass = 'processing';
            statusBadgeText = '⟳ Ingesting';
        } else if (status === 'failed') {
            statusClass = 'failed';
            statusBadgeText = '⚠ Failed';
        }

        let typeIcon = 'bi-file-earmark-pdf-fill';
        if (type === 'CSV') typeIcon = 'bi-file-earmark-spreadsheet-fill';
        else if (type === 'HTML') typeIcon = 'bi-file-earmark-code-fill';

        item.innerHTML = `
            <div class="file-item-top">
                <div class="file-item-badge-row">
                    <span class="badge-type">${type}</span>
                    <span class="badge-status ${statusClass}">${statusBadgeText}</span>
                </div>
                <button class="file-item-delete" title="Delete knowledge source">
                    <i class="bi bi-trash-fill"></i>
                </button>
            </div>
            <div class="file-item-title" title="${escapeHTML(name)}" style="font-size:0.75rem; font-weight:600; margin-top:0.25rem;">
                <i class="bi ${typeIcon} text-cyan me-1"></i>${escapeHTML(name)}
            </div>
            <div class="file-item-details">
                <span>Size: ${size}</span>
                <span>•</span>
                <span>Chunks: ${chunkCount}</span>
                <span>•</span>
                <span>Pages: ${pageCount}</span>
            </div>
        `;

        item.querySelector('.file-item-delete').addEventListener('click', (e) => {
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
            headers: { 'X-Session-ID': sessionId }
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
 * Highlight a specific step in the pipeline flow.
 * @param {string} nodeId - The DOM ID of the node to highlight.
 */
function highlightPipelineStep(nodeId) {
    const nodes = [DOM.nodeQuery, DOM.nodeRetrieve, DOM.nodeRerank, DOM.nodeCompress, DOM.nodeLlm];
    nodes.forEach(node => {
        if (!node) return;
        if (node.id === nodeId) {
            node.classList.add('active');
        } else {
            node.classList.remove('active');
        }
    });
}

/**
 * Send the user's question to the /chat endpoint and stream the response via SSE.
 */
async function sendMessage() {
    const question = DOM.messageInput.value.trim();
    if (!question || isStreaming) return;

    // Reset pipeline stats UI
    if (DOM.pipelineRetrieved) DOM.pipelineRetrieved.textContent = '0';
    if (DOM.pipelineReranked) DOM.pipelineReranked.textContent = '0';
    if (DOM.pipelineRatio) DOM.pipelineRatio.textContent = '1.00';
    if (DOM.pipelineTokens) DOM.pipelineTokens.textContent = '0';
    highlightPipelineStep('pipeline-node-query');

    // Show loading spinner on attribution
    if (DOM.attributionList) {
        DOM.attributionList.innerHTML = `
            <div class="attribution-empty">
                <div class="spinner-border text-cyan mb-2" role="status" style="width: 1.5rem; height: 1.5rem; border-width: 0.15em;"></div>
                <p style="font-size:0.75rem; font-weight:600;">Retrieving Sources...</p>
                <span style="font-size:0.6rem; color:#9aa0a6;">Searching knowledge bases and computing relevance...</span>
            </div>
        `;
    }

    // Hide welcome, show messages
    toggleWelcomeScreen(false);

    // Add user message to UI
    addMessageToUI('user', question);
    chatMessages.push({ role: 'user', content: question });

    // Clear input & lock UI
    DOM.messageInput.value = '';
    setStreamingState(true);
    showTypingIndicator();

    // Create empty assistant bubble
    const assistantWrapper = createEmptyAssistantMessage();
    const bubbleEl = assistantWrapper.querySelector('.message-bubble');
    let fullContent = '';

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Session-ID': sessionId
            },
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
                        case 'status':
                            // Show generation status bar
                            if (DOM.generationStatusBar && DOM.generationStatusText) {
                                DOM.generationStatusBar.style.display = 'flex';
                                DOM.generationStatusText.textContent = data.content;
                            }
                            // Update pipeline highlights
                            if (data.content.includes('Retrieving')) {
                                highlightPipelineStep('pipeline-node-retrieve');
                            } else if (data.content.includes('Reranking')) {
                                highlightPipelineStep('pipeline-node-rerank');
                            } else if (data.content.includes('Compressing')) {
                                highlightPipelineStep('pipeline-node-compress');
                            } else if (data.content.includes('Generating')) {
                                highlightPipelineStep('pipeline-node-llm');
                            }
                            break;

                        case 'pipeline':
                            // Update pipeline execution numbers
                            if (DOM.pipelineRetrieved) DOM.pipelineRetrieved.textContent = data.retrieved_chunks;
                            if (DOM.pipelineReranked) DOM.pipelineReranked.textContent = data.reranked_chunks;
                            if (DOM.pipelineRatio) DOM.pipelineRatio.textContent = data.compression_ratio.toFixed(2);
                            if (DOM.pipelineTokens) DOM.pipelineTokens.textContent = data.context_tokens;
                            break;

                        case 'token':
                            fullContent += data.content;
                            bubbleEl.textContent = fullContent;
                            scrollToBottom();
                            break;

                        case 'citations':
                            // Hide status bar
                            if (DOM.generationStatusBar) DOM.generationStatusBar.style.display = 'none';

                            if (data.citations && data.citations.length > 0) {
                                // Add sources below the bubble
                                const mappedSources = data.citations.map(c => ({
                                    filename: c.file,
                                    page: c.page,
                                    excerpt: c.excerpt
                                }));
                                const sourceHTML = createSourceCards(mappedSources);
                                assistantWrapper.insertAdjacentHTML('beforeend', sourceHTML);

                                // Populate Far-Right panel
                                if (DOM.attributionList) {
                                    DOM.attributionList.innerHTML = '';
                                    data.citations.forEach((c) => {
                                        const filename = c.file || 'Unknown Document';
                                        const page = c.page != null ? `p. ${c.page}` : '';
                                        const score = c.rerank_score != null ? `${Math.round(100 / (1 + Math.exp(-c.rerank_score)))}% Match` : 'Relevance Match';
                                        const rawExcerpt = c.excerpt || '';
                                        const highlighted = highlightExcerpt(rawExcerpt, question);

                                        const card = document.createElement('div');
                                        card.className = 'attribution-card';
                                        card.innerHTML = `
                                            <div class="attribution-meta">
                                                <span class="attr-filename" title="${escapeHTML(filename)}">
                                                    <i class="bi bi-file-earmark-text text-cyan me-1"></i>${escapeHTML(filename)}
                                                </span>
                                                ${page ? `<span class="attr-page">${page}</span>` : ''}
                                                <span class="attr-score-badge">${score}</span>
                                            </div>
                                            <div class="attribution-excerpt">${highlighted}</div>
                                        `;
                                        DOM.attributionList.appendChild(card);
                                    });
                                }
                            } else {
                                showDefaultAttributionEmptyState();
                            }
                            break;

                        case 'done':
                            break;

                        case 'error':
                            showToast(data.content || 'An error occurred.', 'error');
                            break;
                    }
                } catch (parseErr) {
                    console.warn('Failed to parse SSE data:', raw, parseErr);
                }
            }
        }

        chatMessages.push({ role: 'assistant', content: fullContent });

    } catch (err) {
        if (!fullContent) {
            assistantWrapper.remove();
        }
        showToast(err.message || 'An error occurred while sending your message.', 'error');
    } finally {
        if (DOM.generationStatusBar) DOM.generationStatusBar.style.display = 'none';
        hideTypingIndicator();
        setStreamingState(false);
        if (DOM.messageInput) DOM.messageInput.focus();
        scrollToBottom();
        updateSummaryCards();
    }
}


/**
 * Add a fully-formed message to the chat UI.
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

    DOM.chatMessages.insertBefore(wrapper, DOM.typingIndicator);
    scrollToBottom();
}


/**
 * Create an empty assistant message wrapper and insert it into the chat.
 * @returns {HTMLElement} The wrapper element.
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
 */
function createSourceCards(sources) {
    if (!sources || sources.length === 0) return '';

    const uid = `src-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    const cards = sources.map((src) => {
        const filename = src.filename || src.source || 'Unknown';
        const page = src.page != null ? src.page : null;
        const excerpt = src.excerpt || '';

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
 */
function toggleSourceCards(id, btn) {
    const list = document.getElementById(id);
    if (!list) return;
    const isExpanded = list.classList.toggle('expanded');
    btn.classList.toggle('expanded', isExpanded);
}
window.toggleSourceCards = toggleSourceCards;


/**
 * Clear the chat history.
 */
async function clearChat() {
    try {
        await fetch(`${API_BASE}/clear-session`, { 
            method: 'POST',
            headers: { 'X-Session-ID': sessionId }
        });
    } catch (err) {
        console.warn('Backend clear-session failed:', err);
    }

    chatMessages = [];

    const wrappers = DOM.chatMessages.querySelectorAll('.message-wrapper');
    wrappers.forEach((el) => el.remove());

    showDefaultAttributionEmptyState();
    updateSummaryCards();
    toggleWelcomeScreen(true);
    showToast('Chat cleared.', 'info');
    if (DOM.messageInput) DOM.messageInput.focus();
}


// ── UI Helpers ─────────────────────────────────────────────────

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

    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

function showTypingIndicator() {
    if (DOM.typingIndicator) DOM.typingIndicator.style.display = 'block';
    scrollToBottom();
}

function hideTypingIndicator() {
    if (DOM.typingIndicator) DOM.typingIndicator.style.display = 'none';
}

function toggleWelcomeScreen(show) {
    if (DOM.welcomeScreen) DOM.welcomeScreen.style.display = show ? 'flex' : 'none';
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        if (DOM.chatMessages) {
            DOM.chatMessages.scrollTo({
                top: DOM.chatMessages.scrollHeight,
                behavior: 'smooth',
            });
        }
    });
}

function setStreamingState(streaming) {
    isStreaming = streaming;
    if (DOM.messageInput) DOM.messageInput.disabled = streaming;
    if (DOM.sendBtn) DOM.sendBtn.disabled = streaming;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const size = (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1);
    return `${size} ${units[i]}`;
}

function toggleSidebar() {
    if (DOM.sidebar) {
        const isOpen = DOM.sidebar.classList.toggle('open');
        if (DOM.sidebarOverlay) {
            DOM.sidebarOverlay.classList.toggle('active', isOpen);
        }
    }
}

function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function capitalise(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

const stopWords = new Set(['what', 'is', 'the', 'how', 'to', 'a', 'an', 'and', 'or', 'in', 'of', 'for', 'on', 'with', 'at', 'by', 'from', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between', 'out', 'against', 'during', 'without', 'before', 'under', 'around', 'here', 'there', 'when', 'where', 'why', 'who', 'which', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs', 'do', 'does', 'did', 'done', 'doing', 'have', 'has', 'had', 'having', 'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must', 'be', 'been', 'being', 'am', 'are', 'was', 'were']);

function highlightExcerpt(excerpt, query) {
    if (!excerpt) return '';
    if (!query) return escapeHTML(excerpt);
    
    const escapedExcerpt = escapeHTML(excerpt);
    
    const words = query.toLowerCase()
        .replace(/[^\w\s]/g, '')
        .split(/\s+/)
        .filter(w => w.length > 2 && !stopWords.has(w));
        
    if (words.length === 0) {
        return escapedExcerpt;
    }
    
    words.sort((a, b) => b.length - a.length);
    
    const escapedWords = words.map(w => w.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'));
    const regex = new RegExp(`\\b(${escapedWords.join('|')})\\b`, 'gi');
    
    return escapedExcerpt.replace(regex, '<mark>$1</mark>');
}

function showDefaultAttributionEmptyState() {
    if (DOM.attributionList) {
        DOM.attributionList.innerHTML = `
            <div class="attribution-empty">
                <i class="bi bi-shield-check text-cyan" style="font-size: 1.5rem; margin-bottom: 0.5rem;"></i>
                <p style="font-size: 0.75rem; font-weight: 600; margin: 0 0 0.15rem 0;">No query dispatched</p>
                <span style="font-size: 0.6rem; text-align: center; color: #9aa0a6;">Citations and similarity scores will populate when answer generates.</span>
            </div>
        `;
    }
}

async function updateSummaryCards() {
    try {
        const res = await fetch(`${API_BASE}/metrics`);
        if (!res.ok) throw new Error('API error fetching metrics');
        const data = await res.json();
        
        if (DOM.summaryDocsCount) DOM.summaryDocsCount.textContent = data.documents_indexed ?? 0;
        if (DOM.summaryChunksCount) DOM.summaryChunksCount.textContent = data.vector_chunks ?? 0;
        
        const navBadge = document.getElementById('indexed-count-nav');
        if (navBadge) navBadge.textContent = data.documents_indexed ?? 0;
    } catch (err) {
        console.warn('Failed to update summary metrics cards:', err);
    }
}
