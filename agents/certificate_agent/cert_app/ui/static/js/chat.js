// ─── Chat Interface Script ───────────────────────────────────────────────────

let currentSessionId = null;
let isStreaming = false;

let sessionStatus = 'onboarding';
let currentTopic = '';
let currentQuestionIndex = 0;
let totalQuestions = 0;
let chatTimerInterval = null;
let chatQuestionTimerSecs = 180;
let chatTabSwitchCount = 0;
let chatVisibilityHandler = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuth()) return;

    // Display user name in nav
    const user = Auth.user();
    if (user && user.name) {
        const nameEl = document.getElementById('userDisplayName');
        if (nameEl) nameEl.textContent = user.name;
    }

    // Initialize chat first so welcome message renders immediately
    initChat();

    // Load past sessions independently
    loadSessionList();
});

// ─── Load Past Sessions List ─────────────────────────────────────────────────

async function loadSessionList() {
    const listEl = document.getElementById('sessionList');
    if (!listEl) return;
    try {
        const sessions = await API.get('/api/chat/sessions', true);
        if (!sessions || sessions.length === 0) {
            listEl.innerHTML = '<div style="color:var(--text-muted); font-size:.85rem; padding:12px; text-align:center;">No past exam sessions found.<br><span style="font-size:.8rem; margin-top:4px; display:block;">Type a topic below to start your first exam!</span></div>';
            return;
        }

        listEl.innerHTML = sessions.map(s => {
            const isActive = s.id === currentSessionId ? 'active' : '';
            const topicDisplay = s.topic || 'Untitled Exam';
            const badgeClass = getStatusBadgeClass(s.status);
            const badgeLabel = getStatusLabel(s.status);
            const dateStr = s.started_at ? new Date(s.started_at).toLocaleDateString() : '';

            return `
                <div class="session-item ${isActive}" onclick="switchSession('${s.id}')">
                    <div class="session-item-title">${escapeHtml(topicDisplay)}</div>
                    <div class="session-item-meta">
                        <span class="badge ${badgeClass}">${badgeLabel}</span>
                        <span>${dateStr}</span>
                    </div>
                    ${s.score != null ? `<div style="font-size:.75rem;color:var(--primary-orange);font-weight:600;">Score: ${s.score}%</div>` : ''}
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error('Failed to load chat sessions:', err);
        listEl.innerHTML = '<div style="color:var(--danger); font-size:.8rem; padding:12px; text-align:center;">Failed to load sessions</div>';
    }
}

function getStatusBadgeClass(status) {
    switch (status) {
        case 'completed': return 'badge-success';
        case 'failed': return 'badge-danger';
        case 'in_exam': return 'badge-warning';
        case 'ready': return 'badge-info';
        case 'calibrating': return 'badge-info';
        default: return 'badge-info';
    }
}

function getStatusLabel(status) {
    switch (status) {
        case 'completed': return 'PASSED';
        case 'failed': return 'FAILED';
        case 'in_exam': return 'IN EXAM';
        case 'ready': return 'READY';
        case 'calibrating': return 'GENERATING';
        case 'onboarding': return 'NEW';
        default: return status.toUpperCase();
    }
}

// ─── Initialize Chat State ───────────────────────────────────────────────────

async function initChat() {
    const urlParams = new URLSearchParams(window.location.search);
    const sid = urlParams.get('session_id');
    const topic = urlParams.get('topic');

    const container = document.getElementById('messagesContainer');
    container.innerHTML = '';

    if (sid) {
        currentSessionId = sid;
        await loadExistingSession(sid);
    } else if (topic) {
        currentSessionId = null;
        renderWelcomeMessage();
        sendMessage(topic);
    } else {
        currentSessionId = null;
        renderWelcomeMessage();
    }
}

function renderWelcomeMessage() {
    const container = document.getElementById('messagesContainer');
    const topics = [
        { name: 'Python', desc: 'Core syntax, OOP, decorators & async programming' },
        { name: 'Docker', desc: 'Containers, images, volume management & networks' },
        { name: 'AWS', desc: 'IAM roles, EC2 instances, S3, Lambda & VPC routing' },
        { name: 'React', desc: 'Hooks, virtual DOM diffing, state & component lifecycle' }
    ];

    container.innerHTML = `
        <div class="welcome-container">
            <div class="welcome-logo">⚡</div>
            <h1 class="welcome-title">CertifyAI</h1>
            <p class="welcome-subtitle">Get certified instantly on any technical skill. What topic would you like to test?</p>
            
            <div class="welcome-grid">
                ${topics.map(t => `
                    <div class="welcome-card" onclick="sendTopicChip('${t.name}')">
                        <div class="welcome-card-title">${t.name}</div>
                        <div class="welcome-card-desc">${t.desc}</div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// ─── Topic Quick-Select Chips ────────────────────────────────────────────────

function sendTopicChip(topic) {
    if (isStreaming) return;
    const input = document.getElementById('messageInput');
    input.value = topic;
    sendMessage(topic);
}

// ─── Switch Active Session ───────────────────────────────────────────────────

function switchSession(sid) {
    if (sid === currentSessionId) return;
    window.location.href = `/chat?session_id=${sid}`;
}

function startNewSession() {
    window.location.href = '/chat';
}

// ─── Load Existing Session History ───────────────────────────────────────────

async function loadExistingSession(sid) {
    showLoading('Loading session history...');
    try {
        const data = await API.get(`/api/chat/session/${sid}`, true);
        hideLoading();

        if (!data || !data.messages) return;

        sessionStatus = (data.session && data.session.status) || 'onboarding';
        currentTopic = (data.session && data.session.topic) || '';
        currentQuestionIndex = (data.session && data.session.current_question_index) || 0;
        totalQuestions = (data.session && data.session.total_questions) || 0;

        updateHeaderAndTimer();

        const container = document.getElementById('messagesContainer');
        container.innerHTML = '';

        data.messages.forEach(msg => {
            renderMessage(msg);
        });

        scrollToBottom();

        if (sessionStatus === 'generating') {
            startGenerationPolling();
        }
    } catch (err) {
        hideLoading();
        showToast(err.message || 'Failed to load session', 'error');
    }
}

// ─── Message Rendering ───────────────────────────────────────────────────────

function renderMessage(msg, animate = false, onComplete = null) {
    const container = document.getElementById('messagesContainer');
    const role = msg.role || 'assistant';
    const msgType = msg.message_type || 'text';
    const metadata = msg.metadata || {};

    const formatContent = (text) => {
        if (!text) return '';
        return escapeHtml(text)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    };

    // Handle typewriter animation for assistant text or mcq_question messages
    if (role === 'assistant' && animate && (msgType === 'text' || msgType === 'mcq_question')) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${role}`;
        const timeStr = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

        if (msgType === 'mcq_question' && Array.isArray(metadata.options) && metadata.options.length > 0) {
            const chipsHtml = metadata.options.map(opt => `
                <button class="mcq-chip" onclick="handleChipClick('${escapeHtml(opt.replace(/'/g, "\\'"))}')">
                    ${escapeHtml(opt)}
                </button>
            `).join('');

            wrapper.innerHTML = `
                <div class="message-bubble">
                    <div class="typed-text-content"></div>
                    <div class="mcq-options-container" style="display: none; opacity: 0; transition: opacity 0.5s ease;">
                        ${chipsHtml}
                    </div>
                </div>
                <div class="message-time">${timeStr}</div>
            `;
            container.appendChild(wrapper);
            scrollToBottom();

            const textEl = wrapper.querySelector('.typed-text-content');
            const chipsEl = wrapper.querySelector('.mcq-options-container');

            typewriteText(textEl, msg.content, formatContent, () => {
                chipsEl.style.display = 'flex';
                chipsEl.offsetHeight; // Force reflow
                chipsEl.style.opacity = '1';
                scrollToBottom();
                if (onComplete) onComplete();
            });
        } else {
            wrapper.innerHTML = `
                <div class="message-bubble">
                    <div class="typed-text-content"></div>
                </div>
                <div class="message-time">${timeStr}</div>
            `;
            container.appendChild(wrapper);
            scrollToBottom();

            const textEl = wrapper.querySelector('.typed-text-content');
            typewriteText(textEl, msg.content, formatContent, () => {
                if (onComplete) onComplete();
            });
        }
        return;
    }

    // --- Otherwise standard static rendering ---
    const wrapper = document.createElement('div');
    wrapper.className = `message-wrapper ${role}`;

    let bubbleHtml = `<div class="message-bubble">${formatContent(msg.content)}</div>`;

    // 1. MCQ Question Chips (for in-chat exam mode)
    if (msgType === 'mcq_question' && Array.isArray(metadata.options) && metadata.options.length > 0) {
        const chipsHtml = metadata.options.map(opt => `
            <button class="mcq-chip" onclick="handleChipClick('${escapeHtml(opt.replace(/'/g, "\\'"))}')">
                ${escapeHtml(opt)}
            </button>
        `).join('');

        bubbleHtml = `
            <div class="message-bubble">
                <div>${formatContent(msg.content)}</div>
                <div class="mcq-options-container">
                    ${chipsHtml}
                </div>
            </div>
        `;
    }

    // 2. Take Exam Card — generated when 30 questions are ready
    if (msgType === 'take_exam_card') {
        const topic = metadata.topic || 'Exam';
        const total = metadata.total_questions || 30;
        const sid = metadata.session_id || currentSessionId;
        const beginner = metadata.beginner || 0;
        const intermediate = metadata.intermediate || 0;
        const advanced = metadata.advanced || 0;

        bubbleHtml = `
            <div class="take-exam-card">
                <div class="take-exam-card-header">
                    <div class="take-exam-card-icon">🎓</div>
                    <div>
                        <div class="take-exam-card-title">${escapeHtml(topic)} Certification</div>
                        <div class="take-exam-card-subtitle">AI-Generated Exam Ready</div>
                    </div>
                </div>
                <div class="take-exam-card-stats">
                    <div class="take-exam-stat">
                        <div class="take-exam-stat-value">${total}</div>
                        <div class="take-exam-stat-label">Questions</div>
                    </div>
                    ${beginner ? `<div class="take-exam-stat">
                        <div class="take-exam-stat-value" style="color:var(--success)">${beginner}</div>
                        <div class="take-exam-stat-label">Beginner</div>
                    </div>` : ''}
                    ${intermediate ? `<div class="take-exam-stat">
                        <div class="take-exam-stat-value" style="color:var(--accent-dark)">${intermediate}</div>
                        <div class="take-exam-stat-label">Intermediate</div>
                    </div>` : ''}
                    ${advanced ? `<div class="take-exam-stat">
                        <div class="take-exam-stat-value" style="color:var(--danger)">${advanced}</div>
                        <div class="take-exam-stat-label">Advanced</div>
                    </div>` : ''}
                    <div class="take-exam-stat">
                        <div class="take-exam-stat-value">70%</div>
                        <div class="take-exam-stat-label">Pass Score</div>
                    </div>
                </div>
                <button class="take-exam-btn" onclick="launchOfficialExam('${escapeHtml(topic)}', '${sid}')">
                    Take Exam ⚡
                </button>
            </div>
        `;
    }

    // 3. Certificate Card (exam result)
    if (msgType === 'certificate_card') {
        const passed = metadata.passed;
        const score = metadata.score_percentage || 0;
        const certId = metadata.certificate_id;
        const certNum = metadata.certificate_number;
        const cardClass = passed ? 'passed' : 'failed';
        const title = passed ? '🏆 Certification Earned!' : '❌ Exam Complete';

        const actionHtml = certId ? `
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <a href="/api/certificate/download/${certId}?token=${encodeURIComponent(Auth.token() || '')}" target="_blank" class="btn btn-primary btn-sm" style="text-decoration:none;">
                    ⬇ Download PDF Certificate
                  </a>
                <a href="/dashboard" class="btn btn-secondary btn-sm" style="text-decoration:none;">
                    View Dashboard
                </a>
            </div>
        ` : `
            <div style="margin-top:8px;">
                <div style="color:var(--text-muted); font-size:.85rem; margin-bottom:10px;">
                    Score: <strong>${score}%</strong> — Passing threshold is 70%. Start a new exam to try again.
                </div>
                <button class="btn btn-primary btn-sm" onclick="startNewSession()">Start New Exam</button>
            </div>
        `;

        bubbleHtml = `
            <div class="certificate-card ${cardClass}">
                <div class="certificate-card-title">${title}</div>
                <div>Topic: <strong>${escapeHtml(metadata.topic || 'Exam')}</strong></div>
                <div>Score: <strong>${score}%</strong></div>
                ${certNum ? `<div style="font-size:.8rem; color:var(--text-muted);">Certificate ID: <strong>#${escapeHtml(certNum)}</strong></div>` : ''}
                ${actionHtml}
            </div>
        `;
    }

    const timeStr = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    wrapper.innerHTML = `
        ${bubbleHtml}
        <div class="message-time">${timeStr}</div>
    `;

    container.appendChild(wrapper);
    scrollToBottom();
    if (onComplete) onComplete();
}

function handleChipClick(optionText) {
    if (isStreaming) return;
    sendMessage(optionText);
}

// ─── Handle Form Submit ──────────────────────────────────────────────────────

function handleChatSubmit(e) {
    e.preventDefault();
    if (isStreaming) return;

    const input = document.getElementById('messageInput');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    sendMessage(text);
}

// ─── Send Message & Stream SSE Response ──────────────────────────────────────

// Queue of incoming messages to animate
let renderQueue = [];
let isRenderingQueue = false;

function renderMessageAnimated(msg) {
    return new Promise((resolve) => {
        renderMessage(msg, true, resolve);
    });
}

async function processRenderQueue() {
    if (isRenderingQueue) return;
    isRenderingQueue = true;

    while (renderQueue.length > 0) {
        const nextMsg = renderQueue.shift();
        await renderMessageAnimated(nextMsg);
    }

    isRenderingQueue = false;
    if (sessionStatus !== 'generating') {
        toggleInputState(true);
        isStreaming = false;
    }
}

// Typewriter Text Effect Helper
function typewriteText(element, text, formatContent, callback) {
    if (!text) {
        if (callback) callback();
        return;
    }
    let index = 0;
    element.innerHTML = '';
    element.classList.add('typing');
    const interval = setInterval(() => {
        if (index < text.length) {
            element.innerHTML = formatContent(text.substring(0, index + 1));
            index++;
            scrollToBottom();
        } else {
            clearInterval(interval);
            element.classList.remove('typing');
            if (callback) callback();
        }
    }, 15);
}

// ─── Send Message & Stream SSE Response ──────────────────────────────────────

async function sendMessage(text) {
    if (isStreaming) return;
    isStreaming = true;
    toggleInputState(false);

    // Render User Message immediately
    renderMessage({
        role: 'user',
        content: text,
        message_type: 'text',
        created_at: new Date().toISOString()
    });

    let indicatorText = "CertifyAI is typing...";
    if (sessionStatus === 'in_exam') {
        indicatorText = "⚡ CertifyAI is grading and generating the next question...";
    } else if (text && (text.toLowerCase() === 'yes' || text.toLowerCase() === 'start' || text.toLowerCase() === 'yes, start the exam')) {
        indicatorText = "⚡ CertifyAI is setting up your exam...";
    } else if (sessionStatus === 'onboarding' && (text.toLowerCase() === 'beginner' || text.toLowerCase() === 'intermediate' || text.toLowerCase() === 'advanced' || text.toLowerCase() === 'mixed')) {
        indicatorText = "⚡ Generating your exam questions (this takes 10-15s)...";
    }

    showTypingIndicator(indicatorText);

    try {
        // Start Session if no active session_id
        if (!currentSessionId) {
            const startRes = await API.post('/api/chat/start', { topic: text }, true);
            currentSessionId = startRes.session_id;
            window.history.pushState(null, '', `?session_id=${currentSessionId}`);
            loadSessionList();
        }

        // ── Pre-submit state sync ─────────────────────────────────────────────
        // If local state is uncertain (poll timed out, or we're not in_exam yet),
        // fetch the real backend session state before submitting. If the backend
        // has already moved to in_exam (late-success race), reload the UI to show
        // the real Question 1 instead of submitting this message as an answer.
        if (currentSessionId && sessionStatus !== 'in_exam') {
            try {
                const stateCheck = await API.get(`/api/chat/session/${currentSessionId}`, true);
                const realStatus = (stateCheck.session && stateCheck.session.status) || sessionStatus;
                if (realStatus === 'in_exam' && sessionStatus !== 'in_exam') {
                    // Backend is in_exam but frontend didn't know — sync and show Q1.
                    removeTypingIndicator();
                    sessionStatus = 'in_exam';
                    currentQuestionIndex = stateCheck.session.current_question_index || 0;
                    totalQuestions = stateCheck.session.total_questions || 0;
                    currentTopic = stateCheck.session.topic || '';
                    updateHeaderAndTimer();
                    const container = document.getElementById('messagesContainer');
                    container.innerHTML = '';
                    stateCheck.messages.forEach(msg => renderMessage(msg));
                    scrollToBottom();
                    showToast('✅ Your exam was ready! Here is Question 1.', 'success');
                    isStreaming = false;
                    toggleInputState(true);
                    return;
                }
            } catch (_) {
                // Network error during state check: proceed with submission anyway.
            }
        }

        // Stream SSE response via Fetch + ReadableStream
        const token = Auth.token();
        const response = await fetch('/api/chat/message', {

            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: text
            })
        });

        // Typing indicator stays visible until the SSE stream delivers its
        // first real event chunk — only then do we remove it.
        // (Removing it here, right after fetch() returns headers, is too early
        // and causes the indicator to flash and vanish before the response
        // content has actually arrived.)

        if (response.status === 429) {
            const errData = await response.json();
            showToast(errData.detail || 'Rate limit exceeded. Try again in a minute.', 'error');
            toggleInputState(true);
            isStreaming = false;
            return;
        }

        if (response.status === 403) {
            showToast('Access denied to this session.', 'error');
            toggleInputState(true);
            isStreaming = false;
            return;
        }

        if (!response.ok) {
            throw new Error('Failed to send message.');
        }

        // Read SSE Stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');
            buffer = events.pop();

            for (const ev of events) {
                if (!ev.trim()) continue;
                parseAndRenderSSE(ev);
            }
        }

        if (buffer.trim()) {
            parseAndRenderSSE(buffer);
        }

        loadSessionList();
        
        // Remove typing indicator right before rendering response content
        if (sessionStatus !== 'generating') {
            removeTypingIndicator();
        }

        // Start processing the animation queue
        processRenderQueue();

    } catch (err) {
        removeTypingIndicator();
        showToast(err.message || 'Error sending message', 'error');
        toggleInputState(true);
        isStreaming = false;
    }
}

// ─── SSE Event Parser ────────────────────────────────────────────────────────

function parseAndRenderSSE(eventChunk) {
    const lines = eventChunk.split('\n');
    let eventName = 'message';
    let dataStr = '';

    for (const line of lines) {
        if (line.startsWith('event:')) {
            eventName = line.replace('event:', '').trim();
        } else if (line.startsWith('data:')) {
            dataStr = line.replace('data:', '').trim();
        }
    }

    if (!dataStr) return;

    try {
        const payload = JSON.parse(dataStr);
        if (eventName === 'message') {
            renderQueue.push(payload);
        } else if (eventName === 'status') {
            sessionStatus = payload.session_status || 'onboarding';
            currentQuestionIndex = payload.current_question_index || 0;
            totalQuestions = payload.total_questions || 0;
            updateHeaderAndTimer();
            loadSessionList();
            if (sessionStatus === 'generating') {
                startGenerationPolling();
            }
        }
    } catch (e) {
        console.error('Failed to parse SSE payload:', e);
    }
}

// ─── Launch Exam ─────────────────────────────────────────────────────────────

function launchOfficialExam(topic, sessionId) {
    if (sessionId) {
        // Launch with pre-generated questions from chat session
        window.location.href = `/exam?session_id=${encodeURIComponent(sessionId)}&topic=${encodeURIComponent(topic)}`;
    } else if (topic) {
        // Fallback: generate new exam
        sessionStorage.setItem('examTopic', topic);
        window.location.href = `/exam?topic=${encodeURIComponent(topic)}`;
    }
}

// ─── UI Helper Utilities ─────────────────────────────────────────────────────

function showTypingIndicator(customText = "CertifyAI is typing...") {
    removeTypingIndicator();
    const container = document.getElementById('messagesContainer');
    const indicator = document.createElement('div');
    indicator.id = 'typingIndicatorWrapper';
    indicator.className = 'message-wrapper assistant';
    indicator.innerHTML = `
        <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <span style="margin-left:4px; font-size:.85rem; color:var(--text-muted); font-weight: 500;">${escapeHtml(customText)}</span>
        </div>
    `;
    container.appendChild(indicator);
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = document.getElementById('typingIndicatorWrapper');
    if (el) el.remove();
}

function toggleInputState(enabled) {
    const input = document.getElementById('messageInput');
    const btn = document.getElementById('sendBtn');
    input.disabled = !enabled;
    btn.disabled = !enabled;
    if (enabled) input.focus();
}

function scrollToBottom() {
    const container = document.getElementById('messagesContainer');
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Toggle mobile sidebar
function toggleMobileSidebar() {
    const layout = document.querySelector('.chat-layout');
    if (layout) {
        layout.classList.toggle('sidebar-open');
    }
}

// Click outside sidebar or backdrop to close it
document.addEventListener('click', (e) => {
    const layout = document.querySelector('.chat-layout');
    if (layout && layout.classList.contains('sidebar-open')) {
        const sidebar = document.querySelector('.chat-sidebar');
        const toggleBtn = document.querySelector('.btn-sidebar-toggle');
        if (sidebar && !sidebar.contains(e.target) && toggleBtn && !toggleBtn.contains(e.target)) {
            layout.classList.remove('sidebar-open');
        }
    }
});

// ─── Chat Exam Timing & Monitoring
function updateHeaderAndTimer() {
    const header = document.getElementById('chatExamHeader');
    if (!header) return;

    if (sessionStatus === 'in_exam') {
        header.style.display = 'flex';
        document.getElementById('chatExamTopic').textContent = (currentTopic || 'Exam') + ' Certification';
        
        const qNum = (currentQuestionIndex || 0) + 1;
        document.getElementById('chatExamQCounter').textContent = `Question ${qNum} / ${totalQuestions || 30}`;

        if (window.lastRenderedQIndex !== currentQuestionIndex) {
            chatQuestionTimerSecs = 180;
            window.lastRenderedQIndex = currentQuestionIndex;
        }

        if (!chatTimerInterval) {
            startChatTimer();
        }
        initChatTabSwitchDetection();
    } else {
        header.style.display = 'none';
        stopChatTimer();
        removeChatTabSwitchDetection();
    }
}

function startChatTimer() {
    if (chatTimerInterval) return;
    chatTimerInterval = setInterval(() => {
        chatQuestionTimerSecs--;
        const m = String(Math.floor(chatQuestionTimerSecs / 60)).padStart(2, '0');
        const s = String(chatQuestionTimerSecs % 60).padStart(2, '0');
        const timerEl = document.getElementById('chatExamTimer');
        if (timerEl) {
            timerEl.textContent = `⏱ ${m}:${s}`;
        }

        if (chatQuestionTimerSecs <= 0) {
            handleChatQuestionTimeout();
        }
    }, 1000);
}

function stopChatTimer() {
    if (chatTimerInterval) {
        clearInterval(chatTimerInterval);
        chatTimerInterval = null;
    }
}

function handleChatQuestionTimeout() {
    showToast("⏱ Time's up for Question " + (currentQuestionIndex + 1) + "! Skipping...", "error");
    chatQuestionTimerSecs = 180; // Reset
    sendMessage("Timeout");
}

function initChatTabSwitchDetection() {
    if (chatVisibilityHandler) return;
    
    chatVisibilityHandler = () => {
        if (document.visibilityState === 'hidden' && sessionStatus === 'in_exam') {
            chatTabSwitchCount++;
            if (chatTabSwitchCount >= 3) {
                alert("🚨 Exam Auto-Submitted!\n\nYou have switched tabs 3 times. Your exam has been automatically submitted.");
                sendMessage("force_submit_exam_due_to_tab_switches");
            } else {
                alert(`⚠️ Warning: Tab switch detected! (Warning ${chatTabSwitchCount} of 3).\n\nLeaving this tab 3 times will automatically submit your exam.`);
            }
        }
    };
    document.addEventListener('visibilitychange', chatVisibilityHandler);
}

function removeChatTabSwitchDetection() {
    if (chatVisibilityHandler) {
        document.removeEventListener('visibilitychange', chatVisibilityHandler);
        chatVisibilityHandler = null;
    }
}

// ─── Question Generation Polling ─────────────────────────────────────────────
let generationPollInterval = null;
const MAX_POLL_ATTEMPTS = 30; // 30 × 2 s = 60 s hard timeout
let pollAttemptCount = 0;

function startGenerationPolling() {
    if (generationPollInterval) return;

    pollAttemptCount = 0;
    isStreaming = true;
    toggleInputState(false);
    showTypingIndicator("⚡ Generating your exam questions (this takes 10-15s)...");

    generationPollInterval = setInterval(async () => {
        pollAttemptCount++;

        // Hard timeout — stop polling after MAX_POLL_ATTEMPTS ticks
        if (pollAttemptCount > MAX_POLL_ATTEMPTS) {
            stopGenerationPolling();
            // Do NOT set sessionStatus = 'generation_failed' here.
            // The background thread may still succeed a few seconds later.
            // Leave the DB as the source of truth: show an actionable message
            // and let the user refresh to get the real outcome rather than
            // permanently poisoning local state with a premature failure.
            showToast(
                "⚠️ Generation is taking longer than expected. Please refresh the page to check if your exam is ready, or send any message to try again.",
                "error",
                8000
            );
            isStreaming = false;
            toggleInputState(true);
            return;
        }

        try {
            const data = await API.get(`/api/chat/session/${currentSessionId}`, true);
            const status = (data.session && data.session.status) || 'onboarding';

            if (status === 'in_exam' || status === 'generation_failed') {
                stopGenerationPolling();

                // Update local session state
                sessionStatus = status;
                currentTopic = (data.session && data.session.topic) || '';
                currentQuestionIndex = (data.session && data.session.current_question_index) || 0;
                totalQuestions = (data.session && data.session.total_questions) || 0;
                updateHeaderAndTimer();
                loadSessionList();

                // Find and render new messages that arrived during generation
                const messageWrappers = document.querySelectorAll('.message-wrapper:not(#typingIndicatorWrapper)');
                const renderedCount = messageWrappers.length;
                if (data.messages && data.messages.length > renderedCount) {
                    for (let i = renderedCount; i < data.messages.length; i++) {
                        renderMessage(data.messages[i], true);
                    }
                }

                if (status === 'generation_failed') {
                    showToast("❌ Exam generation failed. Please try again.", "error");
                }

                isStreaming = false;
                toggleInputState(true);
            }
        } catch (err) {
            console.error("Error polling session status:", err);
        }
    }, 2000);
}

function stopGenerationPolling() {
    if (generationPollInterval) {
        clearInterval(generationPollInterval);
        generationPollInterval = null;
    }
    removeTypingIndicator();
}
