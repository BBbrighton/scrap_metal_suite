/**
 * Scale Reader - WebSerial API integration for HP-05 and compatible scales
 *
 * Protocol: HP-05
 * - Frame length: 17 bytes
 * - Header: 0x82 0x28
 * - Data format: See decodeHP05Frame() for details
 *
 * Usage:
 *   const reader = new ScaleReader();
 *   await reader.autoDetect(callbackFn);
 *   await reader.connect(config);
 *   await reader.disconnect();
 */

class ScaleReader {
    constructor() {
        this.port = null;
        this.reader = null;
        this.isConnected = false;
        this.config = null;
        this.lastWeight = null;
        this.onWeightUpdate = null;
        this.onStatusUpdate = null;
        this.buffer = new Uint8Array(255);
        this.bufferIndex = 0;
    }

    /**
     * Auto-detect scale configuration by testing multiple baud rates
     *
     * @param {Function} onProgress - Callback for progress updates
     * @returns {Object} Detected configuration or null
     */
    async autoDetect(onProgress = null) {
        // Check if WebSerial is supported
        if (!('serial' in navigator)) {
            throw new Error('WebSerial API not supported in this browser. Use Chrome/Edge.');
        }

        // Prompt user to select serial port
        try {
            this.port = await navigator.serial.requestPort();
        } catch (err) {
            throw new Error('No port selected: ' + err.message);
        }

        // Test configurations - comprehensive set matching working HTML
        const testConfigs = [
            // 8N1 configurations
            { baudRate: 1200, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 2400, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 4800, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 9600, dataBits: 8, parity: 'none', stopBits: 1, flowControl: 'none', bufferSize: 255 },

            // 7E1 configurations (7 data bits, even parity)
            { baudRate: 1200, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 2400, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
            { baudRate: 9600, dataBits: 7, parity: 'even', stopBits: 1, flowControl: 'none', bufferSize: 255 },
        ];

        for (const config of testConfigs) {
            const configDesc = `${config.baudRate} baud, ${config.dataBits}${config.parity[0].toUpperCase()}${config.stopBits}`;
            if (onProgress) {
                onProgress(`Testing ${configDesc}...`);
            }

            try {
                await this.port.open(config);

                // Try to read data for 3 seconds
                const result = await this.testRead(3000);

                if (result.success) {
                    // Found working configuration!
                    this.config = config;
                    if (onProgress) {
                        onProgress(`✓ Detected: ${configDesc}, Weight: ${result.weight} kg`);
                    }
                    if (result.debugData) {
                        if (onProgress) {
                            onProgress(`Debug: ${result.debugData}`);
                        }
                    }
                    return {
                        config: config,
                        weight: result.weight,
                        rawData: result.rawData
                    };
                }

                // Close and try next config
                await this.port.close();

                // Show debug data even on failure
                if (result.debugData && onProgress) {
                    const byteCount = result.debugData.split(' ').filter(b => b).length;
                    onProgress(`✗ ${configDesc} failed (received ${byteCount} bytes)`);
                    if (byteCount > 0 && byteCount <= 50) {
                        // Show raw bytes if we got some data
                        onProgress(`  Raw: ${result.debugData}`);
                    }
                } else if (onProgress) {
                    onProgress(`✗ ${configDesc} failed (no data received)`);
                }

            } catch (err) {
                // Failed to open or read - try next config
                try {
                    await this.port.close();
                } catch (e) {
                    // Ignore close errors
                }
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
     * Test read data from currently open port
     *
     * @param {number} timeout - Timeout in milliseconds
     * @returns {Object} { success, weight, rawData, debugData }
     */
    async testRead(timeout = 3000) {
        return new Promise(async (resolve) => {
            const startTime = Date.now();
            const reader = this.port.readable.getReader();
            const allBytesReceived = [];  // DEBUG: Store all bytes received

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

                    // DEBUG: Store all received bytes
                    for (let byte of value) {
                        allBytesReceived.push(byte);
                    }

                    // Append to buffer
                    for (let byte of value) {
                        this.buffer[this.bufferIndex++] = byte;

                        // Check for complete HP-05 frame (17 bytes)
                        if (this.bufferIndex >= 17) {
                            const frame = this.buffer.slice(0, 17);
                            const decoded = this.decodeHP05Frame(frame);

                            if (decoded && decoded.valid) {
                                reader.releaseLock();
                                resolve({
                                    success: true,
                                    weight: decoded.weight,
                                    rawData: Array.from(frame).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '),
                                    debugData: Array.from(allBytesReceived).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ')
                                });
                                return;
                            }

                            // Shift buffer
                            this.buffer.copyWithin(0, 1);
                            this.bufferIndex--;
                        }
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
     * Connect to scale with specified configuration
     *
     * @param {Object} config - Serial port configuration
     */
    async connect(config) {
        if (this.isConnected) {
            throw new Error('Already connected. Disconnect first.');
        }

        // Check if WebSerial is supported
        if (!('serial' in navigator)) {
            throw new Error('WebSerial API not supported in this browser. Use Chrome/Edge.');
        }

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
        const reader = this.port.readable.getReader();
        this.reader = reader;

        try {
            while (this.isConnected) {
                const { value, done } = await reader.read();

                if (done) {
                    break;
                }

                // Append to buffer
                for (let byte of value) {
                    this.buffer[this.bufferIndex++] = byte;

                    // Check for complete HP-05 frame (17 bytes)
                    if (this.bufferIndex >= 17) {
                        const frame = this.buffer.slice(0, 17);
                        const decoded = this.decodeHP05Frame(frame);

                        if (decoded && decoded.valid) {
                            this.lastWeight = decoded.weight;

                            if (this.onWeightUpdate) {
                                this.onWeightUpdate({
                                    weight: decoded.weight,
                                    stable: decoded.stable,
                                    unit: decoded.unit,
                                    rawData: Array.from(frame).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' ')
                                });
                            }
                        }

                        // Shift buffer (sliding window)
                        this.buffer.copyWithin(0, 1);
                        this.bufferIndex--;
                    }
                }
            }
        } catch (err) {
            console.error('Read error:', err);
            if (this.onStatusUpdate) {
                this.onStatusUpdate({ status: 'error', message: err.message });
            }
        } finally {
            reader.releaseLock();
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
     */
    async disconnect() {
        if (!this.isConnected) {
            return;
        }

        this.isConnected = false;

        if (this.reader) {
            try {
                await this.reader.cancel();
            } catch (e) {
                // Ignore
            }
            this.reader = null;
        }

        if (this.port) {
            try {
                await this.port.close();
            } catch (e) {
                // Ignore
            }
            this.port = null;
        }

        this.config = null;
        this.lastWeight = null;

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
