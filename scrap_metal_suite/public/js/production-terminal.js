/**
 * Production Terminal - Core Logic
 * Handles Production Sorting workflow
 */

// Global state
let currentSession = null;
let currentDropoff = null;
let currentItemType = 'good'; // 'good' or 'unwanted'
let currentWeight = 0;
let goodItems = [];
let unwantedItems = [];
let scaleReader = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Production Terminal initialized');
    initializeSession();
});

/**
 * Initialize session from server context
 */
function initializeSession() {
    // Check if session exists from template
    const sessionBadge = document.querySelector('.session-badge');
    if (sessionBadge && sessionBadge.textContent !== 'No Session') {
        currentSession = sessionBadge.textContent.trim();
        console.log('Active session found:', currentSession);
    }
}

/**
 * Start a new production session with selected scale
 */
async function selectScale(scaleName, scaleDisplayName) {
    try {
        const response = await frappe.call({
            method: 'scrap_metal_suite.api.v1.production.open_session',
            args: { scale: scaleName }
        });

        if (response.message && response.message.session) {
            frappe.show_alert({
                message: `Session started with ${scaleDisplayName}`,
                indicator: 'green'
            });
            // Reload to show sorting interface
            setTimeout(() => window.location.reload(), 500);
        }
    } catch (error) {
        frappe.msgprint({
            title: 'Error',
            indicator: 'red',
            message: error.message || 'Failed to start session'
        });
    }
}

/**
 * Alternative: Start session button (without scale selection)
 */
async function startSession() {
    frappe.msgprint({
        title: 'Start Session',
        message: 'Please select a scale to start your production session'
    });
}

/**
 * Close current session
 */
async function confirmCloseSession() {
    frappe.confirm(
        'Are you sure you want to close this session?',
        async () => {
            try {
                await frappe.call({
                    method: 'scrap_metal_suite.api.v1.production.close_session',
                    args: { session: currentSession }
                });

                frappe.show_alert({
                    message: 'Session closed successfully',
                    indicator: 'green'
                });

                setTimeout(() => window.location.href = '/pos/production', 500);
            } catch (error) {
                frappe.msgprint({
                    title: 'Error',
                    indicator: 'red',
                    message: error.message || 'Failed to close session'
                });
            }
        }
    );
}

/**
 * Search for dropoff by ID
 */
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

/**
 * Display dropoff search results
 */
function displayDropoffResults(results) {
    const container = document.getElementById('dropoffResults');

    if (!results || results.length === 0) {
        container.innerHTML = '<div class="no-results">No dropoffs found</div>';
        return;
    }

    container.innerHTML = results.map(d => `
        <div class="result-item" onclick="selectDropoff('${d.name}')">
            <div class="result-id">${d.name}</div>
            <div class="result-info">${d.supplier} - ${d.total_actual_weight} kg</div>
        </div>
    `).join('');
}

/**
 * Select dropoff for sorting
 */
async function selectDropoff(dropoffId) {
    try {
        const response = await frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'Dropoff',
                name: dropoffId
            }
        });

        currentDropoff = response.message;

        // Display dropoff details
        document.getElementById('currentDropoffId').textContent = currentDropoff.name;
        document.getElementById('currentDropoffSupplier').textContent = currentDropoff.supplier || 'N/A';
        document.getElementById('currentDropoffWeight').textContent = `${currentDropoff.total_actual_weight || 0} kg`;

        document.getElementById('dropoffDetails').style.display = 'block';
        document.getElementById('dropoffResults').innerHTML = '';
        document.getElementById('dropoffSearch').value = currentDropoff.name;

        // Enable sorting interface
        enableSortingInterface();

    } catch (error) {
        frappe.msgprint({
            title: 'Error',
            indicator: 'red',
            message: error.message || 'Failed to load dropoff'
        });
    }
}

/**
 * Clear selected dropoff
 */
function clearDropoff() {
    currentDropoff = null;
    document.getElementById('dropoffDetails').style.display = 'none';
    document.getElementById('dropoffSearch').value = '';
    disableSortingInterface();
}

/**
 * Enable sorting interface
 */
function enableSortingInterface() {
    // Enable item selection and weighing
    document.getElementById('itemSelect').disabled = false;
}

/**
 * Disable sorting interface
 */
function disableSortingInterface() {
    document.getElementById('itemSelect').disabled = true;
    document.getElementById('addItemBtn').disabled = true;
}

/**
 * Switch between good and unwanted item types
 */
function switchItemType(type) {
    currentItemType = type;

    // Update tab styles
    document.querySelectorAll('.item-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`.item-tab[data-type="${type}"]`).classList.add('active');

    // Show/hide return reason
    const returnReasonSection = document.getElementById('returnReasonSection');
    if (type === 'unwanted') {
        returnReasonSection.style.display = 'block';
    } else {
        returnReasonSection.style.display = 'none';
    }
}

/**
 * Select item from dropdown
 */
function selectItem() {
    const select = document.getElementById('itemSelect');
    if (select.value) {
        // Enable add button if item selected and weight > 0
        updateAddButtonState();
    }
}

/**
 * Capture weight from scale
 */
function captureWeight() {
    // If scale_reader.js is loaded and connected
    if (window.scaleReader && window.scaleReader.isConnected()) {
        currentWeight = window.scaleReader.lastWeight;
        document.getElementById('weightValue').textContent = currentWeight.toFixed(3);
        updateAddButtonState();
    } else {
        // Manual weight entry for testing
        const weight = prompt('Enter weight (kg):');
        if (weight && !isNaN(weight)) {
            currentWeight = parseFloat(weight);
            document.getElementById('weightValue').textContent = currentWeight.toFixed(3);
            updateAddButtonState();
        }
    }
}

/**
 * Update add button state
 */
function updateAddButtonState() {
    const itemSelect = document.getElementById('itemSelect');
    const addBtn = document.getElementById('addItemBtn');

    if (itemSelect.value && currentWeight > 0) {
        addBtn.disabled = false;
    } else {
        addBtn.disabled = true;
    }
}

/**
 * Add item to sorting list
 */
function addItem() {
    const itemSelect = document.getElementById('itemSelect');
    const itemCode = itemSelect.value;
    const itemName = itemSelect.options[itemSelect.selectedIndex].text;
    const uom = itemSelect.options[itemSelect.selectedIndex].dataset.uom || 'Kg';
    const remarks = document.getElementById('remarks').value;

    if (!itemCode || currentWeight <= 0) {
        frappe.msgprint('Please select an item and capture weight');
        return;
    }

    const item = {
        item_code: itemCode,
        item_name: itemName,
        weight: currentWeight,
        uom: uom,
        remarks: remarks
    };

    if (currentItemType === 'good') {
        goodItems.push(item);
    } else {
        const returnReason = document.getElementById('returnReason').value;
        item.return_reason = returnReason;
        unwantedItems.push(item);
    }

    // Reset form
    currentWeight = 0;
    document.getElementById('weightValue').textContent = '0.000';
    document.getElementById('remarks').value = '';
    document.getElementById('addItemBtn').disabled = true;

    // Update UI
    updateItemsList();
    updateSummary();
    updateSubmitButton();
}

/**
 * Update items list display
 */
function updateItemsList() {
    const container = document.getElementById('itemsList');

    let html = '';

    if (goodItems.length > 0) {
        html += '<div class="items-group"><h4 style="color: #4caf50;">Good Items</h4>';
        goodItems.forEach((item, index) => {
            html += `
                <div class="item-entry good">
                    <div class="item-details">
                        <span class="item-name">${item.item_name}</span>
                        <span class="item-weight">${item.weight.toFixed(3)} ${item.uom}</span>
                    </div>
                    <button class="btn-remove" onclick="removeItem('good', ${index})">×</button>
                </div>
            `;
        });
        html += '</div>';
    }

    if (unwantedItems.length > 0) {
        html += '<div class="items-group"><h4 style="color: #f44336;">Unwanted Items</h4>';
        unwantedItems.forEach((item, index) => {
            html += `
                <div class="item-entry unwanted">
                    <div class="item-details">
                        <span class="item-name">${item.item_name}</span>
                        <span class="item-weight">${item.weight.toFixed(3)} ${item.uom}</span>
                        <span class="item-reason">${item.return_reason}</span>
                    </div>
                    <button class="btn-remove" onclick="removeItem('unwanted', ${index})">×</button>
                </div>
            `;
        });
        html += '</div>';
    }

    container.innerHTML = html || '<div class="no-items">No items added yet</div>';
}

/**
 * Remove item from list
 */
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

/**
 * Update summary totals
 */
function updateSummary() {
    const goodTotal = goodItems.reduce((sum, item) => sum + item.weight, 0);
    const unwantedTotal = unwantedItems.reduce((sum, item) => sum + item.weight, 0);
    const totalSorted = goodTotal + unwantedTotal;

    document.getElementById('goodTotal').textContent = `${goodTotal.toFixed(3)} kg`;
    document.getElementById('unwantedTotal').textContent = `${unwantedTotal.toFixed(3)} kg`;
    document.getElementById('totalSorted').textContent = `${totalSorted.toFixed(3)} kg`;

    // Calculate variance if dropoff selected
    if (currentDropoff && totalSorted > 0) {
        const dropoffWeight = currentDropoff.total_actual_weight || 0;
        const variance = totalSorted - dropoffWeight;
        const variancePercent = (variance / dropoffWeight * 100).toFixed(2);

        document.getElementById('varianceValue').textContent = `${variance.toFixed(3)} kg (${variancePercent}%)`;
        document.getElementById('varianceRow').style.display = 'flex';
    }
}

/**
 * Update submit button state
 */
