/**
 * Camera Client - CCTV capture for the POS terminals
 *
 * Mirrors ScaleReader: the hardware is read by whatever native process is on
 * the camera LAN, and only the result reaches the server. Requires pos-core.js
 * (uses POS_CORE.callAPI).
 *
 * Two transports, selected by the `agentUrl` option. The terminal code is
 * identical either way:
 *
 *   agentUrl unset  - the Frappe backend Digest-fetches the camera.
 *                     Dev / on-prem only: the server must be on the camera LAN.
 *   agentUrl set    - a local agent on the on-site PC fetches on the LAN and
 *                     uploads to the cloud. This is the cloud-production path.
 *
 * Usage:
 *   const cam = new CameraClient({ usageType: 'Truck', agentUrl });
 *   await cam.loadCameras();
 *   cam.startPreview(name, imgEl, { fps: 1.25, onFrame, onError });
 *   cam.stopPreview();
 *   await cam.capture(name, { parentDoctype, parentDoc, weightType, dropoff, session });
 *   await cam.captureAll({ parentDoctype, parentDoc, weightType, dropoff, session });
 */

class CameraClient {
    constructor(options) {
        options = options || {};

        this.usageType = options.usageType || null;
        // Trailing slash trimmed so `${agentUrl}/frame` never doubles up
        this.agentUrl = (options.agentUrl || '').replace(/\/+$/, '') || null;

        this.cameras = [];
        this.agentOnline = null;      // null = not checked yet
        this.lastError = null;

        this._previewTimer = null;
        this._previewCamera = null;
        this._previewObjectUrl = null;
        this._previewSeq = 0;
    }

    // =========================================================================
    // MODE
    // =========================================================================

    isAgentMode() {
        return !!this.agentUrl;
    }

    hasCameras() {
        return this.cameras.length > 0;
    }

    getCamera(name) {
        return this.cameras.find(c => c.camera_name === name || c.name === name) || null;
    }

    // =========================================================================
    // DISCOVERY
    // =========================================================================

    /**
     * Check the local agent's /health endpoint.
     * @returns {Promise<Object|null>} health payload, or null if unreachable
     */
    async checkAgent() {
        if (!this.isAgentMode()) return null;

        try {
            const response = await fetch(this.agentUrl + '/health', { method: 'GET' });
            if (!response.ok) throw new Error('HTTP ' + response.status);

            const health = await response.json();
            this.agentOnline = true;
            return health;
        } catch (e) {
            this.agentOnline = false;
            this.lastError = e.message;
            console.warn('CameraClient: capture agent offline -', e.message);
            return null;
        }
    }

    /**
     * Load the camera list for this terminal.
     *
     * In agent mode the agent's own list is authoritative, because it is the
     * agent that must resolve the name to a LAN address. The cloud registry is
     * only used to enrich it (location) - a cloud record the agent doesn't know
     * about is dropped, and the mismatch is logged rather than left to fail
     * later as a silent 404 on /frame.
     */
    async loadCameras() {
        let registry = [];

        try {
            const response = await POS_CORE.callAPI(
                'scrap_metal_suite.api.v1.camera.get_cameras',
                { usage_type: this.usageType }
            );
            registry = (response.message && response.message.cameras) || [];
        } catch (e) {
            this.lastError = e.message;
            console.warn('CameraClient: could not load camera registry -', e.message);
        }

        if (!this.isAgentMode()) {
            this.cameras = registry;
            return this.cameras;
        }

        const health = await this.checkAgent();
        if (!health) {
            this.cameras = [];
            return this.cameras;
        }

        const agentNames = (health.cameras || []).map(c => (typeof c === 'string' ? c : c.name));
        const byName = {};
        registry.forEach(c => { byName[c.camera_name] = c; });

        this.cameras = agentNames.map(name => Object.assign(
            { camera_name: name, name: name, usage_type: this.usageType },
            byName[name] || {}
        ));

        const unknown = agentNames.filter(n => !byName[n]);
        if (unknown.length) {
            console.warn('CameraClient: agent cameras not in the cloud registry:', unknown.join(', '));
        }
        const missing = registry.map(c => c.camera_name).filter(n => agentNames.indexOf(n) === -1);
        if (missing.length) {
            console.warn('CameraClient: registry cameras the agent cannot reach:', missing.join(', '));
        }

        return this.cameras;
    }

    // =========================================================================
    // LIVE PREVIEW
    // =========================================================================

    /**
     * Poll frames from one camera into an <img> element.
     *
     * @param {string} cameraName
     * @param {HTMLImageElement} imgEl
     * @param {Object} options - { fps, onFrame(src), onError(err) }
     */
    startPreview(cameraName, imgEl, options) {
        options = options || {};
        const fps = options.fps || 1.25;
        const interval = Math.max(200, Math.round(1000 / fps));

        this.stopPreview();
        this._previewCamera = cameraName;

        const seq = ++this._previewSeq;
        const tick = async () => {
            // A newer preview (or a stop) supersedes this loop
            if (seq !== this._previewSeq) return;

            try {
                const src = await this._fetchFrame(cameraName);
                if (seq !== this._previewSeq) return;

                if (imgEl) imgEl.src = src;
                if (options.onFrame) options.onFrame(src);
            } catch (e) {
                this.lastError = e.message;
                if (options.onError) options.onError(e);
            }
        };

        tick();
        this._previewTimer = setInterval(tick, interval);
    }

    stopPreview() {
        this._previewSeq++;

        if (this._previewTimer) {
            clearInterval(this._previewTimer);
            this._previewTimer = null;
        }

        if (this._previewObjectUrl) {
            URL.revokeObjectURL(this._previewObjectUrl);
            this._previewObjectUrl = null;
        }

        this._previewCamera = null;
    }

    /**
     * One preview frame, as something assignable to img.src.
     * Agent mode returns a blob URL (no base64 round-trip); backend mode
     * returns the data URI from live_frame().
     */
    async _fetchFrame(cameraName) {
        if (this.isAgentMode()) {
            const url = this.agentUrl + '/frame?camera=' + encodeURIComponent(cameraName)
                + '&_=' + Date.now();

            const response = await fetch(url, { method: 'GET' });
            if (!response.ok) throw new Error('Agent frame failed: HTTP ' + response.status);

            const blob = await response.blob();

            if (this._previewObjectUrl) URL.revokeObjectURL(this._previewObjectUrl);
            this._previewObjectUrl = URL.createObjectURL(blob);
            return this._previewObjectUrl;
        }

        const response = await POS_CORE.callAPI(
            'scrap_metal_suite.api.v1.camera.live_frame',
            { camera: cameraName }
        );

        if (!response.message || !response.message.image) {
            throw new Error('No frame returned');
        }
        return response.message.image;
    }

    // =========================================================================
    // TESTING
    // =========================================================================

    /**
     * Probe one camera and report whether it actually returns an image.
     *
     * Transport-agnostic, so callers get the truth about the path in use: in
     * agent mode it pulls a frame through the agent (proving the LAN hop), in
     * backend mode it asks the server to fetch. Never throws.
     *
     * @returns {Promise<Object>} { ok, camera, channel?, bytes?, error? }
     */
    async testCamera(cameraName) {
        if (this.isAgentMode()) {
            try {
                const url = this.agentUrl + '/frame?camera=' + encodeURIComponent(cameraName)
                    + '&_=' + Date.now();
                const response = await fetch(url, { method: 'GET' });

                if (!response.ok) {
                    let detail = 'HTTP ' + response.status;
                    try {
                        const body = await response.json();
                        if (body && body.error) detail = body.error;
                    } catch (e) { /* not JSON - keep the status */ }
                    return { ok: false, camera: cameraName, error: detail };
                }

                const blob = await response.blob();
                return { ok: true, camera: cameraName, bytes: blob.size, via: 'agent' };
            } catch (e) {
                return { ok: false, camera: cameraName, error: e.message };
            }
        }

        try {
            const response = await POS_CORE.callAPI(
                'scrap_metal_suite.api.v1.camera.test_connection',
                { camera: cameraName }
            );
            const result = response.message || {};
            return {
                ok: !!result.ok,
                camera: cameraName,
                channel: result.channel,
                bytes: result.bytes,
                error: result.error,
                via: 'backend'
            };
        } catch (e) {
            return { ok: false, camera: cameraName, error: e.message };
        }
    }

    /**
     * Probe every loaded camera.
     * @returns {Promise<Object>} { total, online, results[] }
     */
    async testAll() {
        if (!this.hasCameras()) await this.loadCameras();

        const results = [];
        for (const cam of this.cameras) {
            results.push(await this.testCamera(cam.camera_name || cam.name));
        }

        return {
            total: results.length,
            online: results.filter(r => r.ok).length,
            results: results
        };
    }

    // =========================================================================
    // CAPTURE
    // =========================================================================

    /**
     * Capture one camera into a Weight Photo row.
     *
     * @param {string} cameraName
     * @param {Object} opts - { parentDoctype, parentDoc, weightType, dropoff, session, highRes }
     */
    async capture(cameraName, opts) {
        opts = opts || {};

        if (this.isAgentMode()) {
            const result = await this._agentCapture(Object.assign({ camera: cameraName }, opts));

            // The agent reports per-camera failures in its summary rather than
            // as an HTTP error. A single manual capture must surface that as a
            // throw, so the modal shows the reason instead of a false success.
            if (!result.ok) {
                throw new Error((result.errors && result.errors[0]) || 'Capture failed');
            }
            return result;
        }

        const response = await POS_CORE.callAPI(
            'scrap_metal_suite.api.v1.camera.capture_snapshot',
            {
                camera: cameraName,
                parent_doctype: opts.parentDoctype,
                parent_doc: opts.parentDoc,
                weight_type: opts.weightType || null,
                dropoff: opts.dropoff || null,
                session: opts.session || null,
                high_res: opts.highRes === false ? 0 : 1
            }
        );

        return response.message;
    }

    /**
     * Capture every active camera for this terminal. Used by auto-capture on
     * weight save.
     *
     * Never throws: a camera or agent failure must not block the weigh.
     *
     * @returns {Promise<Object>} { ok, fail, photo_count, results, errors }
     */
    async captureAll(opts) {
        opts = opts || {};

        if (this.isAgentMode()) {
            // One round trip - the agent loops over its own cameras
            try {
                const result = await this._agentCapture(Object.assign({ usageType: this.usageType }, opts));
                return {
                    ok: result.ok || 0,
                    fail: result.fail || 0,
                    photo_count: result.photo_count || 0,
                    results: result.results || [],
                    errors: result.errors || []
                };
            } catch (e) {
                this.lastError = e.message;
                return { ok: 0, fail: 1, photo_count: 0, results: [], errors: [e.message] };
            }
        }

        if (!this.hasCameras()) {
            await this.loadCameras();
        }

        const summary = { ok: 0, fail: 0, photo_count: 0, results: [], errors: [] };

        for (const cam of this.cameras) {
            const name = cam.camera_name || cam.name;
            try {
                const result = await this.capture(name, opts);
                summary.ok++;
                summary.photo_count = result.photo_count || summary.photo_count;
                summary.results.push(result);
            } catch (e) {
                summary.fail++;
                summary.errors.push(name + ': ' + e.message);
                console.warn('CameraClient: capture failed for', name, '-', e.message);
            }
        }

        return summary;
    }

    /**
     * POST a capture request to the local agent, which fetches on the LAN and
     * uploads to the cloud itself.
     */
    async _agentCapture(opts) {
        const body = {
            parentDoctype: opts.parentDoctype,
            parentDoc: opts.parentDoc,
            weightType: opts.weightType || null,
            dropoff: opts.dropoff || null,
            session: opts.session || null
        };

        if (opts.camera) body.camera = opts.camera;
        if (opts.usageType) body.usageType = opts.usageType;

        const response = await fetch(this.agentUrl + '/capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            throw new Error('Agent capture failed: HTTP ' + response.status);
        }

        return response.json();
    }
}

window.CameraClient = CameraClient;
