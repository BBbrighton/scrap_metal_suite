
// =============================================================================
// SERVER ERRORS, IN WORDS
//
// Frappe answers a failed call with three things: `_server_messages` (the
// translated sentence written for a person), `exc_type` (the exception class)
// and `exc` (a Python traceback). Only the first is fit to show at a
// weighbridge; the traceback tells an operator nothing and buries the reason.
// =============================================================================

/** Strip the HTML Frappe allows in its messages, and tidy the whitespace. */
function plainText(html) {
    if (!html) return '';
    const el = document.createElement('div');
    el.innerHTML = String(html);
    return (el.textContent || '').replace(/\s+/g, ' ').trim();
}

/** Plain-language text for an HTTP status, when there is nothing better. */
function serverStatusMessage(status) {
    if (status === 401 || status === 403) return 'Your session has expired. Please sign in again.';
    if (status === 404) return 'That was not found. It may have been deleted.';
    if (status === 409) return 'Someone else changed this at the same time. Please reload and try again.';
    if (status === 417) return 'The server rejected that request.';
    if (status >= 500) return 'The server had a problem. Please try again.';
    if (status === 0) return 'No connection to the server. Check the network.';
    return 'Request failed (' + status + ').';
}

/** Last-resort wording per exception class, when no server message was sent. */
function messageForExcType(excType) {
    const map = {
        PermissionError: 'You do not have permission to do that.',
        DoesNotExistError: 'That record no longer exists.',
        TimestampMismatchError: 'Someone else changed this record while you had it open. Please reload.',
        DuplicateEntryError: 'That already exists.',
        LinkExistsError: 'This is still used by something else, so it cannot be removed.',
        MandatoryError: 'Something required is missing.',
        LinkValidationError: 'A linked record is missing or invalid.',
        ValidationError: 'That could not be saved. Please check the values.'
    };
    return map[excType] || null;
}

/**
 * The best sentence we can give the person at the scale.
 *
 * Order matters: the server's own message first, because it names the actual
 * item, document or field. Everything after it is a fallback.
 */
function readableServerError(data, response) {
    let raw = data && data._server_messages;
    if (raw) {
        try {
            const list = typeof raw === 'string' ? JSON.parse(raw) : raw;
            const texts = (list || []).map(function (m) {
                try {
                    const o = typeof m === 'string' ? JSON.parse(m) : m;
                    return plainText(o.message || o.title || o);
                } catch (_) {
                    return plainText(m);
                }
            }).filter(Boolean);
            if (texts.length) return texts.join('\n');
        } catch (_) { /* fall through */ }
    }

    const byType = messageForExcType(data && data.exc_type);
    if (byType) return byType;

    if (response && !response.ok) return serverStatusMessage(response.status);
    return 'Something went wrong. Please try again.';
}

/**
 * pos-core.js - Core POS utilities shared between terminals
 *
 * Usage:
 *   POS_CORE.init({ terminalId: 'posTerminal', langDisplayMode: 'toggle' });
 *   POS_CORE.t('key');
 *   POS_CORE.toggleLanguage(state);
 *   etc.
 */
const POS_CORE = (function() {
    // Configuration set by init()
    let config = {
        terminalId: 'posTerminal',      // 'posTerminal' or 'truckTerminal'
        langDisplayMode: 'toggle',       // 'toggle' (EN/TH swap) or 'show' (show current)
        langIconId: 'langIcon',
        langLabelId: 'langLabel',
        themeIconId: 'themeIcon',
        clockId: 'currentTime',
        onLanguageChange: null           // Optional callback after language change
    };

    return {
        /**
         * Initialize core module with terminal-specific config
         */
        init: function(options) {
            Object.assign(config, options || {});
        },

        /**
         * Translation wrapper
         */
        t: function(key) {
            return POS_I18N.t(key);
        },

        /**
         * Toggle language between EN and TH
         * @param {Object} state - Terminal state object with 'language' property
         * @returns {string} New language code
         */
        toggleLanguage: function(state) {
            state.language = POS_I18N.toggleLanguage();
            this.applyLanguage(state.language);
            return state.language;
        },

        /**
         * Apply language to DOM elements
         * @param {string} lang - Language code ('en' or 'th')
         */
        applyLanguage: function(lang) {
            // Update language indicator based on display mode
            if (config.langDisplayMode === 'toggle') {
                // Show opposite language (what you'll switch to)
                const langIcon = document.getElementById(config.langIconId);
                if (langIcon) {
                    langIcon.textContent = lang === 'en' ? 'TH' : 'EN';
                }
            } else if (config.langDisplayMode === 'show') {
                // Show current language
                const langLabel = document.getElementById(config.langLabelId);
                if (langLabel) {
                    langLabel.textContent = lang.toUpperCase();
                }
            }

            // Update all elements with data-i18n attribute
            document.querySelectorAll('[data-i18n]').forEach(function(el) {
                const key = el.getAttribute('data-i18n');
                el.textContent = POS_I18N.t(key);
            });

            // Update placeholders
            document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
                const key = el.getAttribute('data-i18n-placeholder');
                el.placeholder = POS_I18N.t(key);
            });

            // Call optional callback for terminal-specific updates
            if (config.onLanguageChange && typeof config.onLanguageChange === 'function') {
                config.onLanguageChange(lang);
            }
        },

        /**
         * Toggle theme between dark and light
         * @param {Object} state - Terminal state object with 'theme' property
         * @returns {string} New theme
         */
        toggleTheme: function(state) {
            state.theme = state.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('posTheme', state.theme);
            this.applyTheme(state.theme);
            return state.theme;
        },

        /**
         * Apply theme to terminal
         * @param {string} theme - 'dark' or 'light'
         */
        applyTheme: function(theme) {
            const terminal = document.getElementById(config.terminalId);
            const themeIcon = document.getElementById(config.themeIconId);

            if (theme === 'light') {
                if (terminal) terminal.classList.add('light-theme');
                if (themeIcon) themeIcon.innerHTML = '&#127769;'; // moon
            } else {
                if (terminal) terminal.classList.remove('light-theme');
                if (themeIcon) themeIcon.innerHTML = '&#9728;'; // sun
            }
        },

        /**
         * Update clock display
         */
        updateClock: function() {
            const now = new Date();
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            const dow = days[now.getDay()];
            const date = now.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
            const time = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
            const el = document.getElementById(config.clockId);
            if (el) {
                el.textContent = dow + ' ' + date + ' ' + time;
            }
        },

        /**
         * Start clock auto-update
         */
        startClock: function() {
            this.updateClock();
            setInterval(this.updateClock.bind(this), 1000);
        },

        /**
         * Make API call to Frappe backend
         * @param {string} method - API method path
         * @param {Object} args - Arguments to pass
         * @returns {Promise<Object>} Response data
         */
        callAPI: async function(method, args) {
            args = args || {};
            const response = await fetch('/api/method/' + method, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Frappe-CSRF-Token': frappe.csrf_token
                },
                body: JSON.stringify(args)
            });

            let data;
            try {
                data = await response.json();
            } catch (_) {
                // Not JSON at all - a gateway error page, or the server is down.
                const err = new Error(response.ok
                    ? 'The server sent a reply we could not read.'
                    : serverStatusMessage(response.status));
                err.status = response.status;
                throw err;
            }

            if (data.exc || data.exc_type || !response.ok) {
                // `data.exc` is a raw Python traceback. It is useless to the
                // person at the scale and it hides the actual reason, which
                // Frappe puts in `_server_messages` already translated. Show
                // that; keep the traceback in the console for whoever debugs it.
                const err = new Error(readableServerError(data, response));
                err.excType = data.exc_type || null;
                err.traceback = data.exc || null;
                err.status = response.status;
                if (data.exc) console.error('[' + method + '] server traceback:', data.exc);
                throw err;
            }

            return data;
        },

        /**
         * Play beep sound (for scan success, etc.)
         */
        playBeep: function() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioCtx.createOscillator();
                oscillator.type = 'sine';
                oscillator.frequency.setValueAtTime(800, audioCtx.currentTime);
                oscillator.connect(audioCtx.destination);
                oscillator.start();
                oscillator.stop(audioCtx.currentTime + 0.1);
            } catch (e) {
                // Audio not available, ignore
            }
        },

        /**
         * Get current config (for debugging)
         */
        getConfig: function() {
            return Object.assign({}, config);
        }
    };
})();
