// ─── Shared Auth & API Utilities ───────────────────────────────────────────────

const Auth = {
    token: () => localStorage.getItem('cert_token'),
    user: () => JSON.parse(localStorage.getItem('cert_user') || 'null'),

    getAuthToken() {
        return this.token();
    },

    getAuthHeader() {
        const token = this.token();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },

    save(token, user) {
        localStorage.setItem('cert_token', token);
        localStorage.setItem('cert_user', JSON.stringify(user));
    },

    clear() {
        localStorage.removeItem('cert_token');
        localStorage.removeItem('cert_user');
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    },

    isLoggedIn() {
        return !!this.token();
    },

    logout() {
        this.clear();
        window.location.href = '/';
    },

    handle401() {
        this.clear();
        showToast('Session expired. Please log in again.', 'error');
        setTimeout(() => {
            window.location.href = '/';
        }, 1200);
    }
};

const API = {
    base: '',

    headers(auth = false) {
        const h = { 'Content-Type': 'application/json' };
        const token = Auth.token();
        if (token) {
            h['Authorization'] = `Bearer ${token}`;
        }
        return h;
    },

    async post(path, body, auth = true) {
        try {
            const res = await fetch(this.base + path, {
                method: 'POST',
                headers: this.headers(auth),
                body: JSON.stringify(body)
            });

            if (res.status === 401) {
                Auth.handle401();
                throw new Error('Session expired');
            }

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || data.error || 'Request failed');
            }
            return data;
        } catch (err) {
            if (err.message === 'Failed to fetch') {
                showToast('Network error. Check backend server connection.', 'error');
            }
            throw err;
        }
    },

    async get(path, auth = true) {
        try {
            const res = await fetch(this.base + path, {
                method: 'GET',
                headers: this.headers(auth)
            });

            if (res.status === 401) {
                Auth.handle401();
                throw new Error('Session expired');
            }

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || data.error || 'Request failed');
            }
            return data;
        } catch (err) {
            if (err.message === 'Failed to fetch') {
                showToast('Network error. Check backend server connection.', 'error');
            }
            throw err;
        }
    }
};

// ─── Toast Notifications ───────────────────────────────────────────────────────

function showToast(message, type = 'info') {
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${icons[type]}</span><span>${escapeHtml(message)}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ─── Loading Overlay ───────────────────────────────────────────────────────────

function showLoading(text = 'Processing...') {
    let overlay = document.getElementById('loadingOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `<div class="spinner"></div><div class="loading-text">${escapeHtml(text)}</div>`;
        document.body.appendChild(overlay);
    } else {
        const textEl = overlay.querySelector('.loading-text');
        if (textEl) textEl.textContent = text;
        overlay.style.display = 'flex';
    }
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.style.display = 'none';
}

// ─── Page Auth Guards ─────────────────────────────────────────────────────────

function requireAuth() {
    if (!Auth.isLoggedIn()) {
        window.location.href = '/';
        return false;
    }
    return true;
}

function redirectIfLoggedIn() {
    if (Auth.isLoggedIn()) {
        window.location.href = '/dashboard';
    }
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
