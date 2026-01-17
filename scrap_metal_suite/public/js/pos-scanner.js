/**
 * pos-scanner.js - QR/Barcode scanner functions shared between terminals
 *
 * Usage:
 *   POS_SCANNER.open(function(decodedText) { ... });
 *   POS_SCANNER.close();
 *   POS_SCANNER.parseQRValue(rawValue, ['/app/dropoff/', '/app/pos-order/']);
 */
const POS_SCANNER = (function() {
    let html5QrCode = null;
    let onSuccessCallback = null;

    // Default element IDs
    const config = {
        modalId: 'scannerModal',
        readerId: 'qr-reader',
        statusId: 'scannerStatus',
        manualInputId: 'manualDropoffInput'
    };

    return {
        /**
         * Open the scanner modal and start camera
         * @param {Function} onSuccess - Callback when scan succeeds (receives decodedText)
         * @param {Object} options - Optional config overrides
         */
        open: async function(onSuccess, options) {
            onSuccessCallback = onSuccess;
            const opts = Object.assign({}, config, options || {});

            const modal = document.getElementById(opts.modalId);
            if (modal) {
                modal.style.display = 'flex';
            }

            // Stop existing scanner if any
            if (html5QrCode) {
                try {
                    await html5QrCode.stop();
                } catch (e) {}
                html5QrCode = null;
            }

            // Clear reader element
            const readerEl = document.getElementById(opts.readerId);
            if (readerEl) {
                readerEl.innerHTML = '';
            }

            // Update status
            const statusEl = document.getElementById(opts.statusId);
            if (statusEl) {
                statusEl.textContent = POS_CORE.t('startingCamera');
            }

            try {
                html5QrCode = new Html5Qrcode(opts.readerId);

                const scanConfig = {
                    fps: 10,
                    qrbox: { width: 250, height: 250 },
                    aspectRatio: 1.0
                };

                await html5QrCode.start(
                    { facingMode: "environment" },
                    scanConfig,
                    this._handleScanSuccess.bind(this),
                    function() {} // Ignore failures
                );

                if (statusEl) {
                    statusEl.textContent = POS_CORE.t('pointCamera');
                }
            } catch (err) {
                console.error('Scanner error:', err);
                if (statusEl) {
                    statusEl.textContent = POS_CORE.t('cameraNotAvailable');
                }
            }
        },

        /**
         * Internal scan success handler
         */
        _handleScanSuccess: function(decodedText) {
            POS_CORE.playBeep();
            this.close();
            if (onSuccessCallback && typeof onSuccessCallback === 'function') {
                onSuccessCallback(decodedText);
            }
        },

        /**
         * Close the scanner modal and stop camera
         */
        close: async function() {
            if (html5QrCode) {
                try {
                    await html5QrCode.stop();
                } catch (e) {}
                html5QrCode = null;
            }
            const modal = document.getElementById(config.modalId);
            if (modal) {
                modal.style.display = 'none';
            }
        },

        /**
         * Submit manual entry from input field
         * @param {Function} onSuccess - Optional callback (uses last open callback if not provided)
         */
        submitManual: function(onSuccess) {
            const input = document.getElementById(config.manualInputId);
            const value = input ? input.value.trim() : '';
            if (value) {
                this.close();
                const callback = onSuccess || onSuccessCallback;
                if (callback && typeof callback === 'function') {
                    callback(value);
                }
            }
        },

        /**
         * Parse QR value to extract document ID
         * @param {string} rawValue - Raw scanned value
         * @param {Array} patterns - URL patterns to match (e.g., ['/app/dropoff/', '/app/pos-order/'])
         * @returns {string} Extracted document ID or original value
         */
        parseQRValue: function(rawValue, patterns) {
            patterns = patterns || ['/app/dropoff/', '/app/pos-order/'];

            // Check each pattern
            for (var i = 0; i < patterns.length; i++) {
                var pattern = patterns[i];
                if (rawValue.includes(pattern)) {
                    // Build regex to extract ID after pattern
                    var regex = new RegExp(pattern.replace(/\//g, '\\/') + '([^\\/\\?#]+)');
                    var match = rawValue.match(regex);
                    if (match && match[1]) {
                        return decodeURIComponent(match[1]);
                    }
                }
            }

            // Try to extract from generic URL
            if (rawValue.startsWith('http://') || rawValue.startsWith('https://')) {
                try {
                    var url = new URL(rawValue);
                    var pathParts = url.pathname.split('/').filter(function(p) { return p; });
                    if (pathParts.length > 0) {
                        return decodeURIComponent(pathParts[pathParts.length - 1]);
                    }
                } catch (e) {}
            }

            return rawValue;
        },

        /**
         * Check if scanner is currently active
         */
        isActive: function() {
            return html5QrCode !== null;
        }
    };
})();
