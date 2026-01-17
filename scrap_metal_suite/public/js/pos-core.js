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

            const data = await response.json();

            if (data.exc) {
                throw new Error(data.exc);
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
