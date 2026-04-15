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

async function startSession() {
    frappe.msgprint({
        title: POS_I18N.t('startSession') || 'Start Session',
        message: POS_I18N.t('scanScaleOrSelect') || 'Please select a scale to start your production session'
    });
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
            message: error.message || 'Failed to load dropoff'
        });
    }
}

function clearDropoff() {
    currentDropoff = null;
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

    const remarks = document.getElementById('remarks');
    const item = {
        item_code: currentSelectedItem.code,
        item_name: currentSelectedItem.name,
        weight: currentWeight,
        uom: currentSelectedItem.uom || 'Kg',
        remarks: remarks ? remarks.value : ''
    };

    if (currentItemType === 'good') {
        goodItems.push(item);
    } else {
        unwantedItems.push(item);
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

                    // Reset
                    goodItems = [];
                    unwantedItems = [];
                    currentDropoff = null;

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
