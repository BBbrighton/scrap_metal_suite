/**
 * Scale Reader - WebSerial API integration for industrial scales
 *
 * Supported Protocols:
 * 1. STX-M Protocol (2400 baud, 7E1) - MOST COMMON
 *    - Frame: STX M status weight.dec weight.dec CR LF
 *    - Header: 0x02 0x4D
 *    - Example: "STX M 0    0.0   0.0 CR LF"
 *
 * 2. STX Protocol (1200 baud, 7E1)
 *    - Frame: STX ( status weight... CR LF
 *    - Header: 0x02 0x28
 *
 * 3. HP-05 Protocol (fixed 17 bytes)
 *    - Header: 0x82 0x28
 *    - Checksum validated
 *
 * 4. HP-05 Variant (high-bit ASCII, CR/LF terminated)
 *    - Header: 0x82 0x28
 *    - Data has 0x80 offset (e.g., 0xB0 = '0')
 *    - Terminated with 0x0D 0x0A
 *
 * Usage:
 *   const reader = new ScaleReader();
 *   await reader.autoDetect(callbackFn);
 *   await reader.connect(config);
 *   await reader.disconnect();
 */

/**
 * Assert WebSerial is usable, and say *why* when it is not.
 *
 * `navigator.serial` is absent for two very different reasons, and reporting
 * both as "browser not supported" sends people to reinstall a browser that was
 * never the problem:
 *
 *   1. The browser genuinely lacks WebSerial (Firefox, Safari).
 *   2. The browser has it, but the page is not a **secure context**. WebSerial,
 *      like getUserMedia, is gated on HTTPS or localhost. Served over plain
 *      http:// on a custom hostname — http://smt.local:8000, the usual dev
 *      setup here — the API is simply not exposed.
 *
 * Production (https://smt.x-desk.tech) is a secure context, so case 2 is a
 * dev-only trap. It has already cost this project once: the device-webcam
 * capture was removed after getUserMedia failed the same way.
 */
function assertWebSerial() {
    if ('serial' in navigator) return;

    if (typeof window !== 'undefined' && window.isSecureContext === false) {
        throw new Error(
            'WebSerial needs a secure context. This page is served over ' +
            (window.location ? window.location.origin : 'http') +
            ' — use https://, or http://localhost, or allow this origin under ' +
            'chrome://flags/#unsafely-treat-insecure-origin-as-secure. ' +
            'The browser itself is fine.'
        );
    }

    throw new Error('WebSerial API not supported in this browser. Use Chrome/Edge.');
}

class ScaleReader {
    constructor() {
        this.port = null;
        this.reader = null;
        this.isConnected = false;
        this.config = null;
        this.lastWeight = null;
        this.onWeightUpdate = null;
        this.onStatusUpdate = null;
        this.onDisconnect = null; // Callback when port is physically disconnected
        this.buffer = new Uint8Array(255);
        this.bufferIndex = 0;
        this._boundDisconnectHandler = null;
    }

    /**
     * Set up disconnect event listener for the port
     */
    _setupDisconnectListener() {
        if (!this.port) return;

        // Remove any existing listener
        this._removeDisconnectListener();

        // Create bound handler so we can remove it later
        this._boundDisconnectHandler = async (event) => {
            console.log('Port disconnect event received');
            // Clean up our state
            this.isConnected = false;
            if (this.reader) {
                try {
                    this.reader.releaseLock();
                } catch (e) {}
                this.reader = null;
            }
            this.port = null;
            this.config = null;

            // Notify listeners
            if (this.onStatusUpdate) {
                this.onStatusUpdate({ status: 'disconnected', reason: 'unplugged' });
            }
            if (this.onDisconnect) {
                this.onDisconnect();
            }
        };

        this.port.addEventListener('disconnect', this._boundDisconnectHandler);
    }

    /**
     * Remove disconnect event listener
     */
    _removeDisconnectListener() {
        if (this.port && this._boundDisconnectHandler) {
            this.port.removeEventListener('disconnect', this._boundDisconnectHandler);
            this._boundDisconnectHandler = null;
        }
    }

    /**
     * Connect with a known configuration (faster than autoDetect)
     * Falls back to autoDetect if the preferred config fails
     *
     * @param {Object} preferredConfig - The preferred serial config to try first
     * @param {Function} onProgress - Callback for progress updates
     * @returns {Object} Configuration that worked
     */
    async connectWithConfig(preferredConfig, onProgress = null) {
        // Throws with the actual reason (missing API vs insecure context)
        assertWebSerial();

        // Prompt user to select serial port
        try {
            this.port = await navigator.serial.requestPort();
        } catch (err) {
            throw new Error('No port selected: ' + err.message);
        }

        // Try the preferred config first (single attempt)
        if (preferredConfig && preferredConfig.baudRate) {
            const configDesc = `${preferredConfig.baudRate} baud, ${preferredConfig.dataBits}${(preferredConfig.parity || 'none')[0].toUpperCase()}${preferredConfig.stopBits}`;

            console.log('ScaleReader: Trying saved config:', configDesc);
            if (onProgress) {
                onProgress(`Trying saved config: ${configDesc}...`);
            }

            try {
                await this.port.open(preferredConfig);

                // Try to read data for 3 seconds
                const result = await this.testRead(5000);

                if (result.success) {
                    this.config = preferredConfig;
                    this._setupDisconnectListener();

                    console.log('ScaleReader: ✓ Connected with saved config:', configDesc);
                    if (onProgress) {
                        onProgress(`✓ Connected with saved config: ${configDesc}`);
                    }
                    return {
                        config: preferredConfig,
                        weight: result.weight,
                        stable: result.stable,
                        protocol: result.protocol,
                        rawData: result.rawData
                    };
                }

                // Didn't work, close and fall back
                await this.port.close();
                console.log('ScaleReader: ✗ Saved config failed, trying auto-detect...');
                if (onProgress) {
                    onProgress(`✗ Saved config failed, trying auto-detect...`);
                }
            } catch (err) {
                // Failed to open or read
                try {
                    await this.port.close();
                } catch (e) {}

                console.log('ScaleReader: ✗ Saved config error:', err.message, '- trying auto-detect...');
                if (onProgress) {
                    onProgress(`✗ Saved config error: ${err.message} - trying auto-detect...`);
                }
            }
        }

        // Fall back to autoDetect (will reuse the already-selected port)
        return await this._autoDetectWithPort(onProgress);
    }

    /**
     * Internal: Auto-detect using already-selected port
     */
    async _autoDetectWithPort(onProgress = null) {
        // Test configurations - ordered by likelihood
        const testConfigs = [
            // Most common: 4800/8N1 for HP-05 variant (smaller scales)
            { baudRate: 4800, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // Truck scale: 2400/7E1
            { baudRate: 2400, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // STX protocol: 1200/7E1
            { baudRate: 1200, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // Truck scale alternate: 2400/8N1 (same data, different framing)
            { baudRate: 2400, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // Other rates
            { baudRate: 1200, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 9600, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 9600, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
        ];

        for (const config of testConfigs) {
            const configDesc = `${config.baudRate} baud, ${config.dataBits}${config.parity[0].toUpperCase()}${config.stopBits}`;
            if (onProgress) {
                onProgress(`Testing ${configDesc}...`);
            }

            try {
                // Ensure port is fully closed before opening with new config
                await this._ensurePortClosed();
                await this._delay(500); // Delay for port to fully settle between config tests

                await this.port.open(config);
                const result = await this.testRead(5000);

                if (result.success) {
                    this.config = config;
                    this._setupDisconnectListener();

                    if (onProgress) {
                        onProgress(`✓ DETECTED: ${configDesc}`);
                    }
                    return {
                        config: config,
                        weight: result.weight,
                        stable: result.stable,
                        protocol: result.protocol,
                        rawData: result.rawData
                    };
                }

                await this._ensurePortClosed();
            } catch (err) {
                await this._ensurePortClosed();
                if (onProgress) {
                    onProgress(`✗ ${configDesc} error: ${err.message}`);
                }
            }
        }

        this.port = null;
        throw new Error('Could not detect scale. Ensure scale is powered on and connected.');
    }

    /**
     * Helper: Ensure port is fully closed
     */
    async _ensurePortClosed() {
        if (!this.port) return;

        try {
            // Check if port is open by checking readable/writable
            if (this.port.readable || this.port.writable) {
                await this.port.close();
            }
        } catch (e) {
            // Port may already be closed, that's fine
        }
    }

    /**
     * Helper: Promise-based delay
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Auto-detect scale configuration by testing multiple baud rates
     *
     * @param {Function} onProgress - Callback for progress updates
     * @returns {Object} Detected configuration or null
     */
    async autoDetect(onProgress = null) {
        // Throws with the actual reason (missing API vs insecure context)
        assertWebSerial();

        // Prompt user to select serial port
        try {
            this.port = await navigator.serial.requestPort();
        } catch (err) {
            throw new Error('No port selected: ' + err.message);
        }

        // Test configurations - ordered by likelihood for faster detection
        const testConfigs = [
            // Most common: 4800/8N1 for HP-05 variant (smaller scales)
            { baudRate: 4800, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // Truck scale: 2400/7E1
            { baudRate: 2400, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // STX protocol: 1200/7E1
            { baudRate: 1200, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // Truck scale alternate: 2400/8N1
            { baudRate: 2400, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            // Other rates
            { baudRate: 1200, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 9600, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 9600, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
        ];

        for (const config of testConfigs) {
            const configDesc = `${config.baudRate} baud, ${config.dataBits}${config.parity[0].toUpperCase()}${config.stopBits}`;
            if (onProgress) {
                onProgress(`Testing ${configDesc}...`);
            }

            try {
                // Ensure port is fully closed before opening with new config
                await this._ensurePortClosed();
                await this._delay(500); // Delay for port to fully settle between config tests

                await this.port.open(config);

                // Try to read data for 3 seconds
                const result = await this.testRead(5000);

                if (result.success) {
                    // Found working configuration!
                    this.config = config;

                    // Set up disconnect listener for USB unplug events
                    this._setupDisconnectListener();

                    if (onProgress) {
                        onProgress(`✓ DETECTED: ${configDesc}`);
                        onProgress(`  Protocol: ${result.protocol}`);
                        onProgress(`  Weight: ${result.weight} kg ${result.stable ? '(STABLE)' : '(unstable)'}`);
                        onProgress(`  This configuration works! Connecting...`);
                    }
                    return {
                        config: config,
                        weight: result.weight,
                        stable: result.stable,
                        protocol: result.protocol,
                        rawData: result.rawData
                    };
                }

                // Close and try next config
                await this._ensurePortClosed();

                // Show debug data even on failure
                if (result.debugData && onProgress) {
                    const byteCount = result.debugData.split(' ').filter(b => b).length;
                    onProgress(`✗ ${configDesc} failed (received ${byteCount} bytes)`);
                    if (byteCount > 0) {
                        // Show first 100 bytes of raw data for analysis
                        const bytes = result.debugData.split(' ').filter(b => b);
                        const preview = bytes.slice(0, 100).join(' ');
                        onProgress(`  Raw (first ${Math.min(byteCount, 100)} bytes): ${preview}`);
                        if (byteCount > 100) {
                            onProgress(`  ... (${byteCount - 100} more bytes not shown)`);
                        }
                    }
                } else if (onProgress) {
                    onProgress(`✗ ${configDesc} failed (no data received)`);
                }

            } catch (err) {
                // Failed to open or read - try next config
                await this._ensurePortClosed();
                if (onProgress) {
                    onProgress(`✗ ${configDesc} error: ${err.message}`);
                }
            }
        }

        // None worked
        this.port = null;
        throw new Error('Could not detect scale. Ensure scale is powered on and connected.');
    }

    /**
     * Test read data from currently open port and auto-detect protocol
     *
     * @param {number} timeout - Timeout in milliseconds
     * @returns {Object} { success, weight, rawData, debugData, protocol }
     */
    async testRead(timeout = 3000) {
        return new Promise(async (resolve) => {
            const startTime = Date.now();
            const reader = this.port.readable.getReader();
            const allBytesReceived = [];  // Store all bytes for analysis

            const checkData = async () => {
                try {
                    const { value, done } = await reader.read();

                    if (done) {
                        reader.releaseLock();
                        resolve({
                            success: false,
                            debugData: Array.from(allBytesReceived).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ')
                        });
                        return;
                    }

                    // Store all received bytes
                    for (let byte of value) {
                        allBytesReceived.push(byte);
                        this.buffer[this.bufferIndex++] = byte;

                        // Keep buffer manageable
                        if (this.bufferIndex > 200) {
                            this.buffer.copyWithin(0, 100);
                            this.bufferIndex -= 100;
                        }
                    }

                    // Try to decode with current buffer contents
                    const decoded = this.tryDecodeAny(this.buffer.slice(0, this.bufferIndex));

                    if (decoded && decoded.valid) {
                        reader.releaseLock();
                        resolve({
                            success: true,
                            weight: decoded.weight,
                            stable: decoded.stable,
                            unit: decoded.unit,
                            protocol: decoded.protocol,
                            rawData: Array.from(allBytesReceived).slice(0, 100).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '),
                            debugData: Array.from(allBytesReceived).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ')
                        });
                        return;
                    }

                    // Check timeout
                    if (Date.now() - startTime > timeout) {
                        reader.releaseLock();
                        resolve({
                            success: false,
                            debugData: Array.from(allBytesReceived).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ')
                        });
                        return;
                    }

                    // Continue reading
                    checkData();

                } catch (err) {
                    reader.releaseLock();
                    resolve({
                        success: false,
                        error: err.message,
                        debugData: Array.from(allBytesReceived).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ')
                    });
                }
            };

            checkData();
        });
    }

    /**
     * Try to decode buffer with any known protocol
     * @param {Uint8Array} buffer
     * @returns {Object|null}
     */
    tryDecodeAny(buffer) {
        // Try STX-M protocol first (most common for this scale)
        const stxMResult = this.decodeSTXMProtocol(buffer);
        if (stxMResult) return stxMResult;

        // Try original STX protocol
        const stxResult = this.decodeSTXProtocol(buffer);
        if (stxResult) return stxResult;

        // Try HP-05 variant (high-bit ASCII) - common at 4800 baud
        const hp05VarResult = this.decodeHP05VariantProtocol(buffer);
        if (hp05VarResult) return hp05VarResult;

        // Try standard HP-05 protocol
        const hp05Result = this.decodeHP05Protocol(buffer);
        if (hp05Result) return hp05Result;

        return null;
    }

    /**
     * Decode STX-M protocol (2400 baud, 7E1)
     * Frame: STX M status spaces weight.decimal spaces weight.decimal CR LF
     * Example: 0x02 0x4d 0x30 0x20 0x20 0x20 0x20 0x30 0x2e 0x30 0x20 0x20 0x20 0x30 0x2e 0x30 0x0d 0x0a
     *          STX  'M'  '0'  ' '  ' '  ' '  ' '  '0'  '.'  '0'  ' '  ' '  ' '  '0'  '.'  '0'  CR   LF
     */
    decodeSTXMProtocol(buffer) {
        if (buffer.length < 10) return null;

        // Look for STX (0x02) followed by 'M' (0x4D) and ending with CR LF
        for (let i = 0; i <= buffer.length - 10; i++) {
            if (buffer[i] === 0x02 && buffer[i + 1] === 0x4D) {
                // Found potential frame start, look for CR LF
                for (let j = i + 8; j < Math.min(buffer.length - 1, i + 25); j++) {
                    if (buffer[j] === 0x0D && buffer[j + 1] === 0x0A) {
                        // Found complete frame!
                        const frame = buffer.slice(i, j + 2);
                        const result = this.parseSTXMFrame(frame);
                        if (result) return result;
                    }
                }
            }
        }
        return null;
    }

    /**
     * Parse STX-M frame
     * Format: STX M status [spaces] weight.decimals [spaces] weight.decimals CR LF
     */
    parseSTXMFrame(frame) {
        if (frame.length < 10) return null;
        if (frame[0] !== 0x02 || frame[1] !== 0x4D) return null;

        // Status: '0' = stable, other = unstable
        const statusChar = String.fromCharCode(frame[2]);
        const stable = (statusChar === '0');

        // Convert frame to string (skip STX and M)
        let dataStr = '';
        for (let i = 3; i < frame.length - 2; i++) {
            dataStr += String.fromCharCode(frame[i]);
        }

        // Extract weight - find the first number with decimal point
        // Format is typically: "    0.0   0.0" (spaces + weight + spaces + weight)
        const weightMatch = dataStr.match(/(\d+\.?\d*)/);
        if (!weightMatch) return null;

        const weight = parseFloat(weightMatch[1]);
        if (isNaN(weight)) return null;

        return {
            valid: true,
            weight: weight,
            stable: stable,
            unit: 'kg',
            protocol: 'STX-M',
            status: statusChar
        };
    }

    /**
     * Decode STX protocol (1200 baud, 7E1)
     * Frame: STX ( status weight... CR LF
     */
    decodeSTXProtocol(buffer) {
        if (buffer.length < 18) return null;

        // Look for STX (0x02) followed by '(' (0x28) and ending with CR LF
        for (let i = 0; i <= buffer.length - 18; i++) {
            if (buffer[i] === 0x02 && buffer[i + 1] === 0x28) {
                // Found potential frame start, look for CR LF
                for (let j = i + 16; j < Math.min(buffer.length - 1, i + 20); j++) {
                    if (buffer[j] === 0x0D && buffer[j + 1] === 0x0A) {
                        // Found complete frame!
                        const frame = buffer.slice(i, j + 2);
                        return this.parseSTXFrame(frame);
                    }
                }
            }
        }
        return null;
    }

    /**
     * Parse STX frame
     */
    parseSTXFrame(frame) {
        if (frame.length < 18) return null;
        if (frame[0] !== 0x02 || frame[1] !== 0x28) return null;

        // Status: '0' = stable, '8' = unstable
        const statusChar = String.fromCharCode(frame[2]);
        const stable = (statusChar === '0');

        // Extract weight digits (ASCII, bytes 3-10)
        let weightStr = '';
        for (let i = 3; i <= 10; i++) {
            const char = String.fromCharCode(frame[i]);
            if (char >= '0' && char <= '9') {
                weightStr += char;
            }
        }

        if (weightStr.length === 0) return null;

        // Parse weight (in grams, convert to kg)
        const weightGrams = parseInt(weightStr, 10);
        const weight = weightGrams / 1000;

        return {
            valid: true,
            weight: weight,
            stable: stable,
            unit: 'kg',
            protocol: 'STX',
            status: statusChar
        };
    }

    /**
     * Decode HP-05 protocol (fixed 17 bytes)
     */
    decodeHP05Protocol(buffer) {
        if (buffer.length < 17) return null;

        for (let i = 0; i <= buffer.length - 17; i++) {
            const frame = buffer.slice(i, i + 17);
            const result = this.decodeHP05Frame(frame);
            if (result && result.valid) {
                return { ...result, protocol: 'HP-05' };
            }
        }
        return null;
    }

    /**
     * Decode HP-05 Variant protocol (high-bit ASCII, CR/LF terminated)
     * Common at 4800 baud, 8N1
     *
     * Frame format (variable length, ~18 bytes):
     * [0-1]: Header 0x82 0x28 or 0x82 0xAA (truck scale variant)
     * [2]: Status byte (0x30 = stable)
     * [3-8]: Weight digits with 0x80 offset (e.g., 0xA0 = space, 0xB4 = '4')
     * [...]: More data
     * [n-1, n]: CR LF (0x0D 0x0A) or CR+. (0x8D 0x2E for truck variant)
     *
     * Variant A: 0x82 0x28 ... 0x0D 0x0A (smaller scales)
     * Variant B (8N1): 0x82 0xAA ... 0x8D 0xA5 (truck scales, all bytes +0x80)
     * Variant C (7E1): 0x02 0x2A ... 0x0D 0x25 (truck scales, plain ASCII)
     */
    decodeHP05VariantProtocol(buffer) {
        if (buffer.length < 12) return null;

        for (let i = 0; i <= buffer.length - 12; i++) {
            // Header: 0x82 0x28 or 0x82 0xAA (8N1) or 0x02 0x28 or 0x02 0x2A (7E1)
            const b0 = buffer[i];
            const b1 = buffer[i + 1];
            const isHeader = (b0 === 0x82 && (b1 === 0x28 || b1 === 0xAA)) ||
                             (b0 === 0x02 && (b1 === 0x28 || b1 === 0x2A));

            if (isHeader) {
                for (let j = i + 10; j < Math.min(buffer.length - 1, i + 25); j++) {
                    // Terminator: CR (0x0D or 0x8D) followed by checksum byte (varies)
                    const t0 = buffer[j];
                    if (t0 === 0x0D || t0 === 0x8D) {
                        const frame = buffer.slice(i, j + 2);
                        const result = this.parseHP05VariantFrame(frame);
                        if (result && result.valid) {
                            return result;
                        }
                    }
                }
            }
        }
        return null;
    }

    /**
     * Parse HP-05 Variant frame
     */
    parseHP05VariantFrame(frame) {
        if (frame.length < 12) return null;
        const h0 = frame[0], h1 = frame[1];
        if (!((h0 === 0x82 && (h1 === 0x28 || h1 === 0xAA)) ||
              (h0 === 0x02 && (h1 === 0x28 || h1 === 0x2A)))) return null;

        // Determine if this is a truck scale (header byte 2 is * / 0x2A / 0xAA)
        const isTruckVariant = (h1 === 0x2A || h1 === 0xAA);

        // Status byte - 0x30 typically means stable
        const statusByte = frame[2];
        const stable = (statusByte === 0x30);

        // Extract weight digits from data bytes (high-bit ASCII)
        // Scan all data bytes between header and terminator
        // 0xA0 = space, 0xB0-0xB9 = '0'-'9' (with 0x80 offset)
        // 0x30-0x39 = '0'-'9' (plain ASCII)
        let weightStr = '';
        let decimalPos = -1;
        for (let i = 3; i < frame.length - 2; i++) {
            const byte = frame[i];
            const ascii = byte & 0x7F;
            const char = String.fromCharCode(ascii);

            if (char >= '0' && char <= '9') {
                weightStr += char;
            } else if (char === '.' || byte === 0xAE) {
                decimalPos = weightStr.length;
            } else if (char === ' ' || byte === 0xA0) {
                // Skip spaces (leading padding)
            }
        }

        if (weightStr.length === 0) return null;

        let weight;
        if (decimalPos >= 0) {
            weight = parseFloat(weightStr.slice(0, decimalPos) + '.' + weightStr.slice(decimalPos));
        } else {
            weight = parseInt(weightStr, 10);
        }

        // Return raw weight value - unit_conversion_factor from Scale DocType
        // handles the conversion to kg (e.g. 0.000001 for grams, 1 for kg)

        return {
            valid: true,
            weight: weight,
            stable: stable,
            unit: 'kg',
            protocol: 'HP-05-VAR',
            status: statusByte
        };
    }

    /**
     * Connect to scale with specified configuration
     *
     * @param {Object} config - Serial port configuration
     */
    async connect(config) {
        if (this.isConnected) {
            throw new Error('Already connected. Disconnect first.');
        }

        // Throws with the actual reason (missing API vs insecure context)
        assertWebSerial();

        // If no port selected yet, prompt user
        if (!this.port) {
            try {
                this.port = await navigator.serial.requestPort();
            } catch (err) {
                throw new Error('No port selected: ' + err.message);
            }
        }

        // Open port with config
        try {
            await this.port.open(config);
            this.config = config;
            this.isConnected = true;
            this.bufferIndex = 0;

            // Set up disconnect listener for USB unplug events
            this._setupDisconnectListener();

            // Start reading
            this.startReading();

            if (this.onStatusUpdate) {
                this.onStatusUpdate({ status: 'connected', config: config });
            }

        } catch (err) {
            throw new Error('Failed to open port: ' + err.message);
        }
    }

    /**
     * Start continuous reading from scale
     */
    async startReading() {
        // Don't start if port isn't available
        if (!this.port || !this.port.readable) {
            console.error('Cannot start reading: port not available');
            return;
        }

        let reader;
        try {
            reader = this.port.readable.getReader();
            this.reader = reader;
        } catch (err) {
            console.error('Failed to get reader:', err);
            return;
        }

        try {
            while (this.isConnected) {
                const { value, done } = await reader.read();

                if (done) {
                    console.log('Read stream ended');
                    break;
                }

                // Append to buffer
                for (let byte of value) {
                    this.buffer[this.bufferIndex++] = byte;

                    // Try to decode with any protocol
                    const decoded = this.tryDecodeAny(this.buffer.slice(0, this.bufferIndex));

                    if (decoded && decoded.valid) {
                        this.lastWeight = decoded.weight;

                        if (this.onWeightUpdate) {
                            this.onWeightUpdate({
                                weight: decoded.weight,
                                stable: decoded.stable,
                                unit: decoded.unit,
                                protocol: decoded.protocol,
                                rawData: Array.from(this.buffer.slice(0, Math.min(this.bufferIndex, 50))).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ')
                            });
                        }

                        // Reset buffer after successful decode
                        this.bufferIndex = 0;
                    }

                    // Keep buffer manageable (sliding window)
                    if (this.bufferIndex > 200) {
                        this.buffer.copyWithin(0, 100);
                        this.bufferIndex -= 100;
                    }
                }
            }
        } catch (err) {
            // Only log if it's a real error, not a cancellation
            if (err.name !== 'AbortError' && this.isConnected) {
                console.error('Read error:', err);
                if (this.onStatusUpdate) {
                    this.onStatusUpdate({ status: 'error', message: err.message });
                }
            }
        } finally {
            // Release the reader lock - this is important for reconnection
            try {
                reader.releaseLock();
                console.log('Reader lock released');
            } catch (e) {
                // Lock might already be released
            }
            // Clear the stored reference if it matches
            if (this.reader === reader) {
                this.reader = null;
            }
        }
    }

    /**
     * Decode HP-05 scale protocol frame
     *
     * Frame format (17 bytes):
     * [0-1]: Header 0x82 0x28
     * [2]: Status byte
     * [3-8]: Weight digits (6 bytes ASCII)
     * [9]: Decimal point position
     * [10]: Unit (kg/lb)
     * [11-15]: Reserved
     * [16]: Checksum
     *
     * @param {Uint8Array} frame - 17 byte frame
     * @returns {Object|null} Decoded data or null if invalid
     */
    decodeHP05Frame(frame) {
        // Check header
        if (frame[0] !== 0x82 || frame[1] !== 0x28) {
            return null;
        }

        // Extract status
        const status = frame[2];
        const stable = (status & 0x01) === 0x01;  // Bit 0: stable

        // Extract weight digits (ASCII)
        let weightStr = '';
        for (let i = 3; i <= 8; i++) {
            const char = String.fromCharCode(frame[i]);
            if (char >= '0' && char <= '9') {
                weightStr += char;
            } else if (char === ' ') {
                // Skip leading spaces
            } else {
                // Invalid character
                return null;
            }
        }

        if (weightStr.length === 0) {
            return null;
        }

        // Parse weight as integer
        let weight = parseInt(weightStr, 10);

        // Apply decimal point
        const decimalPos = frame[9];
        if (decimalPos > 0 && decimalPos <= 3) {
            weight = weight / Math.pow(10, decimalPos);
        }

        // Extract unit
        const unitByte = frame[10];
        let unit = 'kg';
        if (unitByte === 0x01) {
            unit = 'lb';
        }

        // Verify checksum (simple XOR)
        let checksum = 0;
        for (let i = 0; i < 16; i++) {
            checksum ^= frame[i];
        }

        const valid = (checksum === frame[16]);

        return {
            valid: valid,
            weight: weight,
            stable: stable,
            unit: unit,
            status: status
        };
    }

    /**
     * Disconnect from scale
     * @param {boolean} forgetPort - If true, completely release port permission (requires re-authorization)
     */
    async disconnect(forgetPort = false) {
        // 1. Signal the read loop to stop
        this.isConnected = false;

        // 2. Cancel and release the reader properly
        if (this.reader) {
            try {
                // Cancel any pending read operation
                await this.reader.cancel();
            } catch (e) {
                // Ignore cancel errors - reader might already be done
                console.log('Reader cancel:', e.message);
            }
            try {
                // Release the lock so the port can be closed
                this.reader.releaseLock();
            } catch (e) {
                // Ignore release errors - might already be released
                console.log('Reader release:', e.message);
            }
            this.reader = null;
        }

        // 3. Small delay to ensure read loop has exited
        await new Promise(resolve => setTimeout(resolve, 100));

        // 4. Remove disconnect event listener before closing port
        this._removeDisconnectListener();

        // 5. Close the port
        if (this.port) {
            try {
                await this.port.close();
                console.log('Port closed successfully');
            } catch (e) {
                // Port may already be closed
                console.log('Port close:', e.message);
            }

            // 6. If forgetPort is true, release the port permission entirely
            // This allows other pages/sessions to access the port without unplugging
            if (forgetPort && typeof this.port.forget === 'function') {
                try {
                    await this.port.forget();
                    console.log('Port permission released');
                } catch (e) {
                    console.log('Port forget error:', e.message);
                }
            }

            this.port = null;
        }

        // 6. Reset all state
        this.config = null;
        this.lastWeight = null;
        this.bufferIndex = 0;

        if (this.onStatusUpdate) {
            this.onStatusUpdate({ status: 'disconnected' });
        }
    }

    /**
     * Get list of previously authorized ports
     *
     * @returns {Array} List of ports
     */
    static async getPorts() {
        if (!('serial' in navigator)) {
            return [];
        }

        return await navigator.serial.getPorts();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScaleReader;
}
