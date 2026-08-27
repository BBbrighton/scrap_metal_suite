/**
 * Production Terminal - Core Logic
 * Handles Production Sorting workflow with scale integration
 */

// ===== Utility =====
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ===== Global State =====
let currentSession = null;
let currentDropoff = null;
let currentContainer = null;   // the bag being sorted right now
let lastSortingName = null;    // for reprint
let currentItemType = 'good';
let currentWeight = 0;
let currentSelectedItem = null;
let goodItems = [];
let unwantedItems = [];
let prodScaleReader = null;
let isScaleConnected = false;
let scaleConfig = null;
let manualWeightMode = false;
let heartbeatInterval = null;

// ===== Initialization =====

document.addEventListener('DOMContentLoaded', () => {
    initializeSession();
    startHeartbeat();
});

function initializeSession() {
    const sessionBadge = document.querySelector('.session-badge');
    if (sessionBadge && sessionBadge.textContent !== 'No Session' &&
        sessionBadge.textContent.trim() !== POS_I18N.t('noSession')) {
        currentSession = sessionBadge.textContent.trim();
        initScaleConnection();
    }
}

// ===== Session Management =====

async function selectScale(scaleName, scaleDisplayName) {
    try {
        const response = await frappe.call({
            method: 'scrap_metal_suite.api.v1.production.open_session',
            args: { scale: scaleName }
        });

        if (response.message && response.message.session) {
            frappe.show_alert({
                message: POS_I18N.t('sessionStarted') || 'Session started with ' + scaleDisplayName,
                indicator: 'green'
            });
            setTimeout(() => window.location.reload(), 500);
        }
    } catch (error) {
        frappe.msgprint({
            title: POS_I18N.t('error') || 'Error',
            indicator: 'red',
            message: error.message || POS_I18N.t('failedToStartSession') || 'Failed to start session'
        });
    }
}

/** Header "Start Session" button.
 *
 * The scale picker is rendered server-side in the page body, so this only has
 * to put it in front of the operator. It used to msgprint "please select a
 * scale" and stop — a dialog telling you to use a list, over a dark overlay,
 * with no list in it and nothing to click. If the picker is empty the page
 * itself now explains why (no Production-type scale), so scroll to it rather
 * than opening a dialog that repeats an instruction the operator cannot follow.
 */
async function startSession() {
    const setup = document.getElementById('sessionSetup');
    if (!setup) {
        frappe.msgprint({
            title: POS_I18N.t('error') || 'Error',
            indicator: 'red',
            message: POS_I18N.t('scanScaleOrSelect') ||
                'The scale picker is not on this page. Reload, or ask an admin to check /pos/production.'
        });
        return;
    }
    setup.style.display = '';
    setup.scrollIntoView({ behavior: 'smooth', block: 'center' });

    const first = setup.querySelector('.scale-option');
    if (first) {
        first.focus();
    } else {
        // Picker is empty — the page explains why; make sure it is seen.
        const empty = setup.querySelector('.scale-empty');
        if (empty) empty.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

async function confirmCloseSession() {
    frappe.confirm(
        POS_I18N.t('confirmCloseSession') || 'Are you sure you want to close this session?',
        async () => {
            try {
                await frappe.call({
                    method: 'scrap_metal_suite.api.v1.production.close_session',
                    args: { session: currentSession }
                });
                frappe.show_alert({
                    message: POS_I18N.t('sessionClosed') || 'Session closed successfully',
                    indicator: 'green'
                });
                stopHeartbeat();
                setTimeout(() => window.location.href = '/pos/production', 500);
            } catch (error) {
                frappe.msgprint({
                    title: POS_I18N.t('error') || 'Error',
                    indicator: 'red',
                    message: error.message || 'Failed to close session'
                });
            }
        }
    );
}

// ===== Heartbeat (for session timeout tracking) =====

function startHeartbeat() {
    if (!currentSession) return;
    heartbeatInterval = setInterval(() => {
        frappe.call({
            method: 'scrap_metal_suite.api.v1.production.update_session_activity',
            args: { session: currentSession },
            async: true
        });
    }, 60000); // Every 60 seconds
}

function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

// ===== Scale Connection =====

async function initScaleConnection() {
    if (typeof ScaleReader === 'undefined') return;

    try {
        const response = await frappe.call({
            method: 'scrap_metal_suite.api.v1.production.get_active_session'
        });

        if (response.message && response.message.scale) {
            scaleConfig = {
                scale_name: response.message.scale_name || response.message.scale,
                baud_rate: response.message.baud_rate,
                data_bits: response.message.data_bits,
                parity: response.message.parity,
                stop_bits: response.message.stop_bits,
                flow_control: response.message.flow_control,
                protocol_detected: response.message.protocol_detected,
                unit_conversion_factor: response.message.unit_conversion_factor,
                signal_unit: response.message.signal_unit
            };
            updateScaleDisplay();
        }
    } catch (e) {
        console.error('Failed to get scale config:', e);
    }
}

function updateScaleDisplay() {
    const badge = document.getElementById('scaleBadge');
    const indicator = document.getElementById('scaleStatusIndicator');
    const nameDisplay = document.getElementById('scaleNameDisplay');
    const container = document.getElementById('scaleBadgeContainer');

    if (!badge || !scaleConfig) return;

    if (nameDisplay) nameDisplay.textContent = scaleConfig.scale_name;
    if (container) container.style.display = 'inline-block';

    if (isScaleConnected) {
        if (indicator) {
            indicator.className = 'scale-status-indicator connected';
            indicator.title = 'Connected';
        }
        document.getElementById('scaleMenuStatus').textContent = POS_I18N.t('connected') || 'Connected';
        document.getElementById('scaleMenuStatus').className = 'scale-menu-header connected';
        document.getElementById('scaleMenuConnect').style.display = 'none';
        document.getElementById('scaleMenuDisconnect').style.display = 'flex';
    } else {
        if (indicator) {
            indicator.className = 'scale-status-indicator disconnected';
            indicator.title = 'Disconnected';
        }
        document.getElementById('scaleMenuStatus').textContent = POS_I18N.t('disconnected') || 'Disconnected';
        document.getElementById('scaleMenuStatus').className = 'scale-menu-header disconnected';
        document.getElementById('scaleMenuConnect').style.display = 'flex';
        document.getElementById('scaleMenuDisconnect').style.display = 'none';
    }
}

function toggleScaleMenu() {
    const menu = document.getElementById('scaleMenu');
    if (menu) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
}

async function handleScaleConnect() {
    document.getElementById('scaleMenu').style.display = 'none';
    const indicator = document.getElementById('scaleStatusIndicator');
    if (indicator) indicator.className = 'scale-status-indicator connecting';

    try {
        prodScaleReader = new ScaleReader();

        prodScaleReader.onWeightUpdate = function (data) {
            if (data.weight !== undefined) {
                currentWeight = data.weight * (scaleConfig.unit_conversion_factor || 1);
                document.getElementById('weightValue').textContent = currentWeight.toFixed(3);

                const dot = document.getElementById('scaleStatusDot');
                if (dot) dot.className = data.stable ? 'scale-status-dot stable' : 'scale-status-dot';

                updateAddButtonState();
            }
        };

        prodScaleReader.onDisconnect = function () {
            isScaleConnected = false;
            updateScaleDisplay();
            frappe.show_alert({ message: POS_I18N.t('scaleDisconnected') || 'Scale disconnected', indicator: 'orange' });
        };

        const config = {
            baudRate: scaleConfig.baud_rate || 4800,
            dataBits: scaleConfig.data_bits || 8,
            parity: scaleConfig.parity || 'none',
            stopBits: scaleConfig.stop_bits || 1,
            flowControl: scaleConfig.flow_control || 'none'
        };

        await prodScaleReader.connectWithConfig(config);
        await prodScaleReader.startReading();
        isScaleConnected = true;
        updateScaleDisplay();
        frappe.show_alert({ message: POS_I18N.t('scaleConnected') || 'Scale connected', indicator: 'green' });

    } catch (e) {
        console.error('Scale connection failed:', e);
        isScaleConnected = false;
        updateScaleDisplay();
        frappe.show_alert({ message: e.message || 'Connection failed', indicator: 'red' });
    }
}

async function handleScaleDisconnect() {
    document.getElementById('scaleMenu').style.display = 'none';
    if (prodScaleReader) {
        await prodScaleReader.disconnect();
        prodScaleReader = null;
    }
    isScaleConnected = false;
    updateScaleDisplay();
}

async function handleScaleReconnect() {
    await handleScaleDisconnect();
    await handleScaleConnect();
}

// ===== Dropoff Search & Selection =====

let dropoffSearchTimeout;
async function searchDropoff(query) {
    clearTimeout(dropoffSearchTimeout);
    if (!query || query.length < 2) {
        document.getElementById('dropoffResults').innerHTML = '';
        return;
    }

    dropoffSearchTimeout = setTimeout(async () => {
        try {
            // The sorter scans a bag sticker, so a CTN-shaped query should
            // return bags, not the loads they belong to. Anything else is a
            // dropoff search as before.
            if (/ctn/i.test(query)) {
                const cres = await frappe.call({
                    method: 'scrap_metal_suite.api.v1.production.search_containers',
                    args: { query: query }
                });
                displayContainerResults(cres.message || []);
                return;
            }
            const response = await frappe.call({
                method: 'scrap_metal_suite.api.v1.production.search_dropoff',
                args: { query: query }
            });
            displayDropoffResults(response.message || []);
        } catch (error) {
            console.error('Dropoff search error:', error);
        }
    }, 300);
}

function displayDropoffResults(results) {
    const container = document.getElementById('dropoffResults');
    if (!results || results.length === 0) {
        container.innerHTML = '<div class="no-results">' + (POS_I18N.t('noDropoffsFound') || 'No dropoffs found') + '</div>';
        return;
    }

    container.innerHTML = results.map(d =>
        '<div class="result-item" onclick="selectDropoff(\'' + escapeHtml(d.name) + '\')">' +
        '<div class="result-id">' + escapeHtml(d.name) + '</div>' +
        '<div class="result-info">' + escapeHtml(d.supplier_name || d.supplier || '') + ' - ' + escapeHtml(d.total_actual_weight) + ' kg</div>' +
        '</div>'
    ).join('');
}


/** Render container search hits. Selecting one opens its whole dropoff. */
function displayContainerResults(rows) {
    const box = document.getElementById('dropoffResults');
    if (!rows || rows.length === 0) {
        box.innerHTML = '<div class="no-results">' +
            (POS_I18N.t('noContainersFound') || 'No containers found') + '</div>';
        return;
    }
    box.innerHTML = rows.map(function (c) {
        const w = parseFloat(c.net_weight || 0).toFixed(1);
        const sorted = c.has_sorting
            ? ' <span style="color:#f59e0b">• ' + (POS_I18N.t('alreadySorted') || 'sorting started') + '</span>'
            : '';

        // A voided or superseded bag is shown, not hidden — scanning its
        // sticker should say why it cannot be used rather than "not found" —
        // but it is greyed and cannot be selected.
        if (c.sortable === false) {
            return '<div class="result-item" style="opacity:.55;cursor:not-allowed"' +
                ' onclick="notSortable(\'' + escapeHtml(c.name) + '\',\'' +
                escapeHtml(c.status || '') + '\')">' +
                '<div class="result-id">' + escapeHtml(c.name) +
                ' <span style="color:#ef4444;font-size:.75rem">• ' +
                escapeHtml(c.status || '') + '</span></div>' +
                '<div class="result-info">' + escapeHtml(c.item_name || c.item_code || '') +
                ' — ' + w + ' kg<br>' + escapeHtml(c.dropoff) + ' · ' +
                escapeHtml(c.supplier_name || '') + '</div>' +
                '</div>';
        }

        return '<div class="result-item" onclick="selectContainer(\'' +
            escapeHtml(c.name) + '\',\'' + escapeHtml(c.dropoff) + '\')">' +
            '<div class="result-id">' + escapeHtml(c.name) + '</div>' +
            '<div class="result-info">' + escapeHtml(c.item_name || c.item_code || '') +
            ' — ' + w + ' kg<br>' + escapeHtml(c.dropoff) + ' · ' +
            escapeHtml(c.supplier_name || '') + sorted + '</div>' +
            '</div>';
    }).join('');
}

/** Explain why a written-off bag cannot be sorted. */
function notSortable(ctn, status) {
    frappe.msgprint({
        title: POS_I18N.t('cannotSort') || 'Cannot sort this container',
        indicator: 'orange',
        message: (POS_I18N.t('containerNotActive') ||
            'Container {0} is {1}. It was written off during receiving and is not available for sorting.')
            .replace('{0}', ctn).replace('{1}', status)
    });
}

/** Scanned or picked a bag: open its dropoff, then focus that bag. */
async function selectContainer(ctn, dropoffId) {
    await selectDropoff(dropoffId);
    selectWorkContainer(ctn);
}

/** Make one bag the active one. Everything added is tagged to it. */
function selectWorkContainer(ctn) {
    const c = ((currentDropoff && currentDropoff.containers) || [])
        .find(function (x) { return x.name === ctn; });

    currentContainer = ctn;
    renderContainerWorklist();
    updateSubmitButton();

    if (c) {
        frappe.show_alert({
            message: (POS_I18N.t('sortingContainer') || 'Sorting') + ' ' + ctn +
                     ' (' + parseFloat(c.net_weight || 0).toFixed(1) + ' kg)',
            indicator: 'blue'
        }, 3);
    }
}

/**
 * The dropoff's bags, as a worklist. The active bag is highlighted and shows
 * how much has been booked against it so far, so the sorter can see when a bag
 * is fully accounted for without doing the arithmetic themselves.
 */
function renderContainerWorklist() {
    const box = document.getElementById('containerWorklist');
    if (!box) return;

    const containers = (currentDropoff && currentDropoff.containers) || [];
    if (!containers.length) {
        box.innerHTML = '';
        return;
    }

    // Booked = what earlier submitted sessions already recorded, plus what is
    // staged in this one. Without the prior part a bag sorted yesterday looks
    // untouched and gets weighed again, doubling it into Dropoff Final.
    const booked = {};
    containers.forEach(function (c) {
        booked[c.name] = parseFloat(c.already_sorted || 0);
    });
    goodItems.concat(unwantedItems).forEach(function (i) {
        if (i.container) booked[i.container] = (booked[i.container] || 0) + parseFloat(i.weight || 0);
    });

    box.innerHTML =
        '<div class="dropoff-items-header">' +
            (POS_I18N.t('containers') || 'Containers') + ' (' + containers.length + ')' +
        '</div>' +
        containers.map(function (c) {
            const recv = parseFloat(c.net_weight || 0);
            const out = booked[c.name] || 0;
            const active = (c.name === currentContainer);
            const done = out > 0 && Math.abs(recv - out) < 0.0005;
            const colour = done ? '#22c55e' : (out > 0 ? '#f59e0b' : '#94a3b8');
            const priorNote = c.already_sorted > 0
                ? '<br><span style="font-size:.65rem;color:#f59e0b">' +
                  (POS_I18N.t('sortedEarlier') || 'sorted earlier') + ': ' +
                  parseFloat(c.already_sorted).toFixed(1) + ' kg</span>'
                : '';
            return '<div class="dropoff-item-row" style="cursor:pointer;' +
                (active ? 'outline:2px solid #2563eb;border-radius:6px;' : '') +
                (c.fully_sorted ? 'opacity:.65;' : '') + '"' +
                ' onclick="selectWorkContainer(\'' + escapeHtml(c.name) + '\')">' +
                '<span class="dropoff-item-name">' + escapeHtml(c.name) +
                '<br><span style="font-size:.7rem;opacity:.7">' +
                escapeHtml(c.item_name || c.item_code || '') + '</span>' + priorNote + '</span>' +
                '<span class="dropoff-item-weight" style="color:' + colour + '">' +
                out.toFixed(1) + ' / ' + recv.toFixed(1) + ' kg</span>' +
                '</div>';
        }).join('');
}


/**
 * Reopen a dropoff whose sorting was already submitted.
 *
 * Same shape as the scrap terminal's reopen: submitted work is locked server
 * side, and getting past it is an explicit, reasoned act. Cancels the
 * submitted sorting so its rows leave the Dropoff Final aggregate, then the
 * load is sorted afresh.
 */
async function reopenSorting() {
    if (!currentDropoff) return;

    const reason = window.prompt(
        POS_I18N.t('promptReopenSortingReason') || 'Reason to reopen this sorting:',
        ''
    );
    if (!reason || !reason.trim()) return;

    try {
        const res = await frappe.call({
            method: 'scrap_metal_suite.api.v1.production.reopen_sorting',
            args: { dropoff: currentDropoff.name, reason: reason.trim() }
        });
        const msg = res.message || {};
        frappe.show_alert({
            message: (POS_I18N.t('sortingReopened') || 'Sorting reopened — {0} cancelled')
                .replace('{0}', (msg.cancelled_sortings || []).join(', ')),
            indicator: 'orange'
        }, 5);

        // Reload so the worklist reflects the cleared aggregate.
        await selectDropoff(currentDropoff.name);
    } catch (err) {
        frappe.msgprint({
            title: POS_I18N.t('error') || 'Error',
            indicator: 'red',
            message: (err && err.message) || 'Failed to reopen sorting'
        });
    }
}

/** Show the Reopen control only when there is submitted work to reopen. */
function updateReopenButton() {
    const btn = document.getElementById('btnReopenSorting');
    if (!btn) return;
    const locked = !!(currentDropoff && (currentDropoff.containers || [])
        .some(function (c) { return (c.already_sorted || 0) > 0; }));
    btn.style.display = locked ? '' : 'none';
}

async function selectDropoff(dropoffId) {
    try {
        const response = await frappe.call({
            method: 'scrap_metal_suite.api.v1.production.get_dropoff_for_sorting',
            args: { dropoff: dropoffId }
        });

        currentDropoff = response.message;
        document.getElementById('currentDropoffId').textContent = currentDropoff.name;
        document.getElementById('currentDropoffSupplier').textContent = currentDropoff.supplier_name || currentDropoff.supplier || 'N/A';
        document.getElementById('currentDropoffWeight').textContent = (currentDropoff.total_actual_weight || 0) + ' kg';

        // Show items list from dropoff
        var itemsHtml = '';
        var srcItems = currentDropoff.source_items || [];
        if (srcItems.length > 0) {
            itemsHtml = '<div class="dropoff-items-header">' + (POS_I18N.t('items') || 'Items') + ':</div>';
            for (var i = 0; i < srcItems.length; i++) {
                var si = srcItems[i];
                var w = parseFloat(si.total_weight || si.weight || 0);
                itemsHtml += '<div class="dropoff-item-row">' +
                    '<span class="dropoff-item-name">' + escapeHtml(si.item_name || si.item || '') + '</span>' +
                    '<span class="dropoff-item-weight">' + w.toFixed(1) + ' kg</span>' +
                    '</div>';
            }
        } else {
            itemsHtml = '<div class="dropoff-items-header" style="color:#94a3b8;font-size:0.75rem;">No item breakdown available</div>';
        }
        document.getElementById('dropoffItemsList').innerHTML = itemsHtml;

        currentContainer = null;
        renderContainerWorklist();
        updateReopenButton();

        document.getElementById('dropoffDetails').style.display = 'block';
        document.getElementById('dropoffResults').innerHTML = '';
        document.getElementById('dropoffSearch').value = currentDropoff.name;

        enableSortingInterface();
        updateSubmitButton();

        // Show "From Dropoff" tab and auto-select it
        var fromTab = document.getElementById('fromDropoffTab');
        if (fromTab) {
            fromTab.style.display = '';
            filterCategory(fromTab, 'fromDropoff');
        }
    } catch (error) {
        frappe.msgprint({
            title: POS_I18N.t('error') || 'Error',
            indicator: 'red',
            message: serverError(error, 'Failed to load dropoff') +
                '<br><br><small>' + escapeHtml(dropoffId) + '</small>'
        });
    }
}

/** Pull the real reason out of a Frappe error.
 *
 * A server-side throw arrives with the message in `_server_messages` or
 * `exc`, and `error.message` is usually undefined — so `error.message || "..."`
 * silently discarded every server error and showed the same generic sentence
 * over a dark overlay. That is how a missing database column surfaced for weeks
 * as "Failed to load dropoff" with nothing to act on.
 */
function serverError(error, fallback) {
    try {
        const msgs = (error && (error._server_messages || (error.responseJSON || {})._server_messages));
        if (msgs) {
            const parsed = JSON.parse(msgs);
            const first = typeof parsed[0] === 'string' ? JSON.parse(parsed[0]) : parsed[0];
            if (first && first.message) return first.message;
        }
    } catch (e) { /* fall through to the plainer sources below */ }
    if (error && error.message) return error.message;
    if (error && error.exc_type) return error.exc_type;
    return fallback;
}

function clearDropoff() {
    currentDropoff = null;
    currentContainer = null;
    renderContainerWorklist();
    // Hide "From Dropoff" tab and reset to All
    var fromTab = document.getElementById('fromDropoffTab');
    if (fromTab) fromTab.style.display = 'none';
    var allTab = document.querySelector('.category-tab[data-category=""]');
    if (allTab) filterCategory(allTab, '');
    document.getElementById('dropoffDetails').style.display = 'none';
    document.getElementById('dropoffSearch').value = '';
    disableSortingInterface();
    updateSubmitButton();
}

function enableSortingInterface() {
    const grid = document.getElementById('itemGrid');
    if (grid) grid.style.opacity = '1';
    if (grid) grid.style.pointerEvents = 'auto';
}

function disableSortingInterface() {
    const grid = document.getElementById('itemGrid');
    if (grid) grid.style.opacity = '0.5';
    if (grid) grid.style.pointerEvents = 'none';
}

// ===== Item Type Tabs (Good / Unwanted) =====

function switchItemType(type) {
    currentItemType = type;
    document.querySelectorAll('.item-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelector('.item-tab[data-type="' + type + '"]').classList.add('active');
}

// ===== Category Filter Tabs =====

function filterCategory(btn, category) {
    // Support both terminal CSS conventions
    document.querySelectorAll('.category-tab, .prod-category-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');

    // Get all item buttons (both conventions)
    var allItems = document.querySelectorAll('.item-btn, .prod-item-btn');

    if (category === 'fromDropoff') {
        var dropoffItemCodes = [];
        if (currentDropoff && currentDropoff.source_items) {
            dropoffItemCodes = currentDropoff.source_items.map(function(i) { return i.item || i.item_code; });
        }
        allItems.forEach(function(item) {
            var code = item.getAttribute('data-item-code') || '';
            item.style.display = dropoffItemCodes.indexOf(code) >= 0 ? '' : 'none';
        });
        return;
    }

    allItems.forEach(function(item) {
        var itemCat = item.getAttribute('data-category') || item.getAttribute('data-group') || '';
        if (category === 'all' || category === '' || itemCat === category) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

// ===== Item Card Selection =====

function selectItemCard(itemCode, itemName, uom) {
    currentSelectedItem = { code: itemCode, name: itemName, uom: uom };

    // Highlight selected card
    document.querySelectorAll('.item-btn').forEach(btn => btn.classList.remove('selected'));
    const card = document.querySelector('.item-btn[data-item-code="' + itemCode + '"]');
    if (card) card.classList.add('selected');

    // Show item name in weight section
    const selectedLabel = document.getElementById('selectedItemName');
    if (selectedLabel) selectedLabel.textContent = itemName;

    // Show manual weight input if in manual mode
    updateWeightSection();
    updateAddButtonState();
}

// ===== Weight Capture =====

function captureWeight() {
    if (isScaleConnected && prodScaleReader) {
        // Weight already updating via scale callback
        updateAddButtonState();
    } else if (!manualWeightMode) {
        // No scale - switch to manual
        toggleManualWeight();
    }
}

function toggleManualWeight() {
    manualWeightMode = !manualWeightMode;
    updateWeightSection();
}

function updateWeightSection() {
    const manualInput = document.getElementById('manualWeightInput');
    const scaleSection = document.getElementById('liveWeightSection');
    const manualSection = document.getElementById('manualWeightSection');
    const modeBtn = document.getElementById('weightModeBtn');

    if (isScaleConnected && !manualWeightMode) {
        if (scaleSection) scaleSection.style.display = 'block';
        if (manualSection) manualSection.style.display = 'none';
        if (modeBtn) modeBtn.textContent = POS_I18N.t('enterManually') || 'Enter Manually';
    } else {
        if (scaleSection) scaleSection.style.display = 'none';
        if (manualSection) manualSection.style.display = 'block';
        if (modeBtn) modeBtn.textContent = POS_I18N.t('useScale') || 'Use Scale';
    }
}

function onManualWeightInput(value) {
    currentWeight = parseFloat(value) || 0;
    document.getElementById('weightValue').textContent = currentWeight.toFixed(3);
    updateAddButtonState();
}

// ===== Add / Remove Items =====

function updateAddButtonState() {
    const addBtn = document.getElementById('addItemBtn');
    if (!addBtn) return;
    addBtn.disabled = !(currentSelectedItem && currentWeight > 0);
}

function addItem() {
    if (!currentSelectedItem || currentWeight <= 0) {
        frappe.msgprint(POS_I18N.t('selectItemAndWeight') || 'Please select an item and capture weight');
        return;
    }

    // Sorting is per bag: every output has to say which container it came from,
    // or Dropoff Final cannot show received-vs-sorted and the weight is
    // unattributable.
    if (!currentContainer) {
        frappe.msgprint(POS_I18N.t('selectContainerFirst') ||
            'Select a container first — pick one from the list on the left.');
        return;
    }

    const remarks = document.getElementById('remarks');
    const item = {
        container: currentContainer,
        item_code: currentSelectedItem.code,
        item_name: currentSelectedItem.name,
        weight: currentWeight,
        uom: currentSelectedItem.uom || 'Kg',
        remarks: remarks ? remarks.value : ''
    };

    if (currentItemType === 'good') {
        goodItems.push(item);
    renderContainerWorklist();
    } else {
        unwantedItems.push(item);
    renderContainerWorklist();
    }

    // Reset
    currentWeight = 0;
    currentSelectedItem = null;
    document.getElementById('weightValue').textContent = '0.000';
    if (remarks) remarks.value = '';
    const manualInput = document.getElementById('manualWeightInput');
    if (manualInput) manualInput.value = '';

    // Deselect card
    document.querySelectorAll('.item-btn').forEach(btn => btn.classList.remove('selected'));
    const selectedLabel = document.getElementById('selectedItemName');
    if (selectedLabel) selectedLabel.textContent = POS_I18N.t('noItemSelected') || 'No item selected';

    updateItemsList();
    updateSummary();
    updateSubmitButton();
    updateAddButtonState();
}

function removeItem(type, index) {
    if (type === 'good') {
        goodItems.splice(index, 1);
    } else {
        unwantedItems.splice(index, 1);
    }
    renderContainerWorklist();
    updateItemsList();
    updateSummary();
    updateSubmitButton();
}

// ===== Items List Display =====

function updateItemsList() {
    const container = document.getElementById('itemsList');
    if (!container) return;

    let html = '';

    if (goodItems.length > 0) {
        html += '<div class="items-group"><h4 style="color: #4caf50;">' + (POS_I18N.t('goodTotal') || 'Good Items:') + '</h4>';
        goodItems.forEach((item, index) => {
            html += '<div class="item-entry good">' +
                '<div class="item-details">' +
                '<span class="item-name">' + escapeHtml(item.item_name) + '</span>' +
                '<span class="item-weight">' + item.weight.toFixed(3) + ' ' + escapeHtml(item.uom) + '</span>' +
                '</div>' +
                '<button class="btn-remove" onclick="removeItem(\'good\', ' + index + ')">x</button>' +
                '</div>';
        });
        html += '</div>';
    }

    if (unwantedItems.length > 0) {
        html += '<div class="items-group"><h4 style="color: #f44336;">' + (POS_I18N.t('unwantedTotal') || 'Unwanted:') + '</h4>';
        unwantedItems.forEach((item, index) => {
            html += '<div class="item-entry unwanted">' +
                '<div class="item-details">' +
                '<span class="item-name">' + escapeHtml(item.item_name) + '</span>' +
                '<span class="item-weight">' + item.weight.toFixed(3) + ' ' + escapeHtml(item.uom) + '</span>' +
                '</div>' +
                '<button class="btn-remove" onclick="removeItem(\'unwanted\', ' + index + ')">x</button>' +
                '</div>';
        });
        html += '</div>';
    }

    container.innerHTML = html || '<div class="no-items">' + (POS_I18N.t('noItemsAdded') || 'No items added yet') + '</div>';
}

// ===== Summary & Variance =====

function updateSummary() {
    const goodTotal = goodItems.reduce((sum, item) => sum + item.weight, 0);
    const unwantedTotal = unwantedItems.reduce((sum, item) => sum + item.weight, 0);
    const totalSorted = goodTotal + unwantedTotal;

    document.getElementById('goodTotal').textContent = goodTotal.toFixed(3) + ' kg';
    document.getElementById('unwantedTotal').textContent = unwantedTotal.toFixed(3) + ' kg';
    document.getElementById('totalSorted').textContent = totalSorted.toFixed(3) + ' kg';

    if (currentDropoff && totalSorted > 0) {
        const dropoffWeight = currentDropoff.total_actual_weight || 0;
        const variance = totalSorted - dropoffWeight;
        const variancePercent = dropoffWeight > 0 ? (variance / dropoffWeight * 100).toFixed(2) : '0.00';

        document.getElementById('varianceValue').textContent = variance.toFixed(3) + ' kg (' + variancePercent + '%)';
        document.getElementById('varianceRow').style.display = 'flex';
    }
}

// ===== Submit Sorting =====

function updateSubmitButton() {
    const submitBtn = document.getElementById('submitBtn');
    if (!submitBtn) return;
    submitBtn.disabled = !((goodItems.length > 0 || unwantedItems.length > 0) && currentDropoff);
}


/**
 * Print an 80mm thermal slip for a sorting record.
 *
 * Same hidden-iframe approach as the scrap and truck terminals: the operator
 * gets the browser's print dialog with the slip already loaded, so it lands on
 * the thermal printer without a download step. Falls back to a new tab if the
 * iframe is blocked.
 */
function printSortingSlip(sortingName) {
    if (!sortingName) return;
    lastSortingName = sortingName;

    const url = '/printview?doctype=Production%20Sorting&name=' +
                encodeURIComponent(sortingName) +
                '&format=Production%20Sorting%20Thermal&no_letterhead=1';

    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';
    iframe.src = url;
    iframe.onload = function () {
        try { iframe.contentWindow.print(); }
        catch (e) { window.open(url + '&trigger_print=1', '_blank'); }
        setTimeout(function () { iframe.remove(); }, 10000);
    };
    document.body.appendChild(iframe);
}

/** Reprint the last slip — the operator's recovery when paper jams or runs out. */
function reprintLastSorting() {
    if (!lastSortingName) {
        frappe.show_alert({
            message: POS_I18N.t('noRecentSorting') || 'No sorting slip to reprint yet',
            indicator: 'orange'
        }, 3);
        return;
    }
    printSortingSlip(lastSortingName);
}

async function submitSorting() {
    if (!currentDropoff) {
        frappe.msgprint(POS_I18N.t('selectDropoffFirst') || 'Please select a Dropoff first');
        return;
    }
    if (goodItems.length === 0 && unwantedItems.length === 0) {
        frappe.msgprint(POS_I18N.t('addAtLeastOneItem') || 'Please add at least one item');
        return;
    }

    frappe.confirm(
        (POS_I18N.t('confirmSubmitSorting') || 'Submit sorting for') + ' ' + currentDropoff.name + '?<br>' +
        (POS_I18N.t('goodTotal') || 'Good Items:') + ' ' + goodItems.length + '<br>' +
        (POS_I18N.t('unwantedTotal') || 'Unwanted:') + ' ' + unwantedItems.length,
        async () => {
            try {
                const response = await frappe.call({
                    method: 'scrap_metal_suite.api.v1.production.create_sorting',
                    args: {
                        session: currentSession,
                        dropoff: currentDropoff.name,
                        good_items: goodItems,
                        unwanted_items: unwantedItems
                    }
                });

                if (response.message) {
                    frappe.show_alert({
                        message: (POS_I18N.t('sortingSubmitted') || 'Sorting submitted: ') + response.message.name,
                        indicator: 'green'
                    });

                    // Print the thermal slip straight away, as the scrap
                    // terminal does on save. Fired before the reset below so
                    // the name is still in hand.
                    printSortingSlip(response.message.name);

                    // Reset
                    goodItems = [];
                    unwantedItems = [];
                    currentDropoff = null;
                    currentContainer = null;
                    renderContainerWorklist();

                    document.getElementById('dropoffDetails').style.display = 'none';
                    document.getElementById('dropoffSearch').value = '';
                    updateItemsList();
                    updateSummary();
                    updateSubmitButton();
                }
            } catch (error) {
                frappe.msgprint({
                    title: POS_I18N.t('error') || 'Error',
                    indicator: 'red',
                    message: error.message || 'Failed to submit sorting'
                });
            }
        }
    );
}

// Close scale menu when clicking outside
document.addEventListener('click', function (e) {
    const menu = document.getElementById('scaleMenu');
    const badge = document.getElementById('scaleBadge');
    if (menu && badge && !badge.contains(e.target) && !menu.contains(e.target)) {
        menu.style.display = 'none';
    }
});
