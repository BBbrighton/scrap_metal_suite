# Terminal.html Migration Plan

> **Context**: The modified terminal.html had Jinja template literal conflicts (`${variable}` patterns interpreted by Jinja). The file was reverted to the committed working version. This plan tracks migrating features from the modified version safely.

---

## Problem: Jinja Template Literal Conflict

JavaScript template literals like `` `${variable}` `` are interpreted by Jinja:
- Jinja sees `{variable}` and tries to evaluate it
- When variable is undefined, outputs `<ol></ol>` or similar
- Breaks entire JavaScript execution

**Solution**: Use string concatenation instead of template literals:
```javascript
// BAD (Jinja interprets {name}):
const msg = `Hello ${name}`;

// GOOD (safe for Jinja):
const msg = "Hello " + name;
```

---

## Migration Strategy

**Most features can be copy-pasted directly** from `terminal.html.modified` because they don't use template literals with variables. Only the following need string concatenation fixes:
- `searchDropoff()` - has template literal in HTML generation
- `attachPhotos()` - has template literal for filename
- `updatePhotoButton()` - has template literal
- Some other functions with dynamic HTML

**Priority**: Manual scale selection first (for dev mode without live scale)

---

## Features to Migrate

### Priority 1: Scale Manual Entry (DEV MODE)

| Feature | Source | Migration Method | Status |
|---------|--------|------------------|--------|
| 1. Disconnect & Refresh button | HTML + `disconnectAndReload()` | Copy-paste | Pending |
| 2. Manual Entry mode button | HTML in scale modal footer | Copy-paste | Pending |
| 3. `confirmScaleManualMode()` | JS function | Copy-paste | Pending |
| 4. `useManualEntryMode()` | JS function | Copy-paste | Pending |
| 5. Update `updateScaleDisplay()` | Show/hide new buttons | Copy-paste additions | Pending |

### Priority 2: Core Functionality

| Feature | Source | Migration Method | Status |
|---------|--------|------------------|--------|
| 6. Order → Dropoff HTML rename | HTML elements | Copy-paste | Pending |
| 7. `searchDropoff()` | JS function | **FIX TEMPLATE LITERALS** | Pending |
| 8. `selectDropoff()` | JS function | Copy-paste | Pending |
| 9. `fetchDropoffDetails()` | JS function | Copy-paste | Pending |
| 10. `clearDropoff()` | JS function | Copy-paste | Pending |
| 11. `renderDropoffItems()` | JS function | **FIX TEMPLATE LITERALS** | Pending |
| 12. `toggleDropoffItems()` | JS function | Copy-paste | Pending |
| 13. `toggleDropoffDetails()` | JS function | Copy-paste | Pending |
| 14. API endpoint changes | Multiple functions | Find & replace | Pending |
| 15. Truck Gross Weight display | HTML + JS in `fetchDropoffDetails()` | Copy-paste | Pending |

### Priority 3: Photo Enhancements (NEEDS FIXES)

| Feature | Source | Migration Method | Status |
|---------|--------|------------------|--------|
| 16. `capturedPhotos[]` state | State init | Copy-paste | Pending |
| 17. `capturePhoto()` | JS function | Copy-paste | Pending |
| 18. `retakePhoto()` | JS function | Copy-paste | Pending |
| 19. `savePhoto()` | JS function | **FIX TEMPLATE LITERALS** | Pending |
| 20. `updatePhotoButton()` | JS function | **FIX TEMPLATE LITERALS** | Pending |
| 21. `attachPhotos()` | JS function | **FIX TEMPLATE LITERALS** (already fixed) | Pending |

---

## Detailed Changes

### 1. Disconnect & Refresh Button (Copy-Paste)

**Location**: Scale menu in header (after disconnect button)

```html
<button class="scale-menu-item" id="scaleMenuDisconnectRefresh" onclick="disconnectAndReload()" style="display:none;">
    <span>🔄</span> <span>Disconnect & Refresh</span>
</button>
```

**Function** (copy-paste):
```javascript
async function disconnectAndReload() {
    document.getElementById('scaleMenu').style.display = 'none';
    try {
        await cleanupScaleConnection(false);
    } catch (e) {
        console.error('Error disconnecting before reload:', e);
    }
    window.location.reload();
}
```

---

### 2. Manual Entry Mode Button (Copy-Paste)

**Location**: Scale modal footer (change from single button to column layout)

```html
<div class="modal-footer" style="flex-direction: column; gap: 10px;">
    <button class="btn-pos btn-success btn-large" onclick="confirmScaleSelection()" id="confirmScaleBtn" disabled data-i18n="confirmScale">
        Confirm & Connect Scale
    </button>
    <button class="btn-pos btn-secondary" onclick="confirmScaleManualMode()" id="manualModeBtn" disabled data-i18n="confirmScaleManual">
        Confirm Scale (Manual Entry)
    </button>
</div>
```

---

### 3. confirmScaleManualMode() (Copy-Paste)

```javascript
async function confirmScaleManualMode() {
    if (!state.selectedScale) {
        frappe.msgprint(t('scaleRequired'));
        return;
    }

    try {
        const response = await callAPI('scrap_metal_suite.api.v1.pos.set_session_scale', {
            session: state.session,
            scale: state.selectedScale.name
        });

        if (response.message) {
            state.scale = state.selectedScale;
            state.isScaleConnected = false;  // Not connected - manual entry mode
            document.getElementById('scaleModal').style.display = 'none';
            updateScaleDisplay();
            frappe.show_alert({
                message: t('scaleSetManualMode') || 'Scale set - using manual weight entry',
                indicator: 'blue'
            }, 3);
        }
    } catch (error) {
        frappe.msgprint({
            title: t('error'),
            indicator: 'red',
            message: error.message || 'Failed to set scale'
        });
    }
}
```

---

### 4. useManualEntryMode() (Copy-Paste)

**Add button to connection failure modal footer**:
```html
<button class="btn-pos btn-warning" onclick="useManualEntryMode()" data-i18n="useManualEntry">Use Manual Entry</button>
```

**Function**:
```javascript
async function useManualEntryMode() {
    if (!state.selectedScale) {
        frappe.msgprint(t('scaleRequired'));
        return;
    }

    try {
        const response = await callAPI('scrap_metal_suite.api.v1.pos.set_session_scale', {
            session: state.session,
            scale: state.selectedScale.name
        });

        if (response.message) {
            state.scale = state.selectedScale;
            state.isScaleConnected = false;  // Not connected - manual entry mode
            document.getElementById('scaleModal').style.display = 'none';
            document.getElementById('scaleConnectionModal').style.display = 'none';
            updateScaleDisplay();
            frappe.show_alert({
                message: t('scaleSetManualMode') || 'Scale set - using manual weight entry',
                indicator: 'blue'
            }, 3);
        }
    } catch (error) {
        frappe.msgprint({
            title: t('error'),
            indicator: 'red',
            message: error.message || 'Failed to set scale'
        });
    }
}
```

---

### 5. updateScaleDisplay() Additions (Copy-Paste)

Add these lines to `updateScaleDisplay()`:

```javascript
const disconnectRefreshBtn = document.getElementById('scaleMenuDisconnectRefresh');

// In the isScaleConnected block:
if (state.isScaleConnected) {
    // ... existing code ...
    disconnectRefreshBtn.style.display = 'flex';
} else {
    // ... existing code ...
    disconnectRefreshBtn.style.display = 'none';
}
```

Also add to `onScaleDropdownChange()`:
```javascript
document.getElementById('manualModeBtn').disabled = false;  // when scale selected
document.getElementById('manualModeBtn').disabled = true;   // when no scale
```

---

### 7. searchDropoff() - NEEDS TEMPLATE LITERAL FIX

The original uses template literals. Use this fixed version:

```javascript
async function searchDropoff(query) {
    clearTimeout(searchTimeout);
    const resultsDiv = document.getElementById('dropoffResults');

    if (query.length < 2) {
        resultsDiv.innerHTML = '';
        resultsDiv.style.display = 'none';
        return;
    }

    searchTimeout = setTimeout(async () => {
        try {
            const data = await callAPI('scrap_metal_suite.api.v1.dropoff.lookup_dropoff', { query: query });

            if (data.message && data.message.length > 0) {
                resultsDiv.innerHTML = data.message.map(function(o) {
                    return '<div class="dropoff-result" onclick="selectDropoff(\'' + o.name + '\', \'' + (o.dropoff_date || '') + '\', \'' + (o.license_plate || '') + '\', \'' + (o.supplier_name || '') + '\', \'' + (o.status || 'Draft') + '\')">' +
                        '<span class="dropoff-id">' + o.name + '</span>' +
                        '<span class="dropoff-details">' + (o.supplier_name || '') + (o.license_plate ? ' | ' + o.license_plate : '') + (o.status === 'Closed' ? ' | ✓' : '') + '</span>' +
                    '</div>';
                }).join('');
                resultsDiv.style.display = 'block';
            } else {
                resultsDiv.innerHTML = '<div class="no-results">' + t('noDropoffsFound') + '</div>';
                resultsDiv.style.display = 'block';
            }
        } catch (error) {
            console.error('Dropoff search error:', error);
            resultsDiv.innerHTML = '<div class="no-results">' + t('errorSearchingDropoff') + '</div>';
            resultsDiv.style.display = 'block';
        }
    }, 300);
}
```

---

### 11. renderDropoffItems() - NEEDS TEMPLATE LITERAL FIX

```javascript
function renderDropoffItems(items) {
    const section = document.getElementById('dropoffItemsSection');
    const list = document.getElementById('dropoffItemsList');
    const countEl = document.getElementById('dropoffItemsCount');
    const fromOrderTab = document.getElementById('fromOrderTab');

    state.dropoffItems = items || [];

    if (fromOrderTab) {
        if (items && items.length > 0) {
            fromOrderTab.style.display = 'inline-block';
        } else {
            fromOrderTab.style.display = 'none';
        }
    }

    if (!items || items.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    countEl.textContent = items.length;

    var html = '';
    items.forEach(function(item) {
        var weight = item.weight ? parseFloat(item.weight).toFixed(2) + ' Kg' : '-';
        html += '<div class="order-item-row">' +
            '<span class="order-item-name">' + (item.item_name || item.item_code) + '</span>' +
            '<span class="order-item-weight">' + weight + '</span>' +
        '</div>';
    });
    list.innerHTML = html;
}
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `terminal.html` | Current working version (reverted) |
| `terminal.html.modified` | Version with all features - use for copy-paste |
| `terminal.html.bak` | Old backup from Dec 19 (can delete) |

---

## Migration Checklist

### Phase 1: Scale Manual Entry (Priority for Dev)
- [ ] 1. Add Disconnect & Refresh button to scale menu HTML
- [ ] 2. Add `disconnectAndReload()` function
- [ ] 3. Modify scale modal footer layout
- [ ] 4. Add Manual Entry mode button
- [ ] 5. Add `confirmScaleManualMode()` function
- [ ] 6. Add Use Manual Entry button to connection failure modal
- [ ] 7. Add `useManualEntryMode()` function
- [ ] 8. Update `updateScaleDisplay()` for new buttons
- [ ] 9. Update `onScaleDropdownChange()` for new button states

### Phase 2: Core Dropoff Functionality
- [ ] 10. Rename Order → Dropoff in HTML elements
- [ ] 11. Add `searchDropoff()` (with template literal fix)
- [ ] 12. Add `selectDropoff()`
- [ ] 13. Add `fetchDropoffDetails()`
- [ ] 14. Add `clearDropoff()`
- [ ] 15. Add `renderDropoffItems()` (with template literal fix)
- [ ] 16. Add `toggleDropoffItems()`
- [ ] 17. Add `toggleDropoffDetails()`
- [ ] 18. Update API endpoints
- [ ] 19. Add Truck Gross Weight HTML and JS

### Phase 3: Photo Enhancements
- [ ] 20. Change `capturedPhotoData` to `capturedPhotos[]`
- [ ] 21. Update `capturePhoto()`
- [ ] 22. Update `retakePhoto()`
- [ ] 23. Update `savePhoto()` (with template literal fix)
- [ ] 24. Add `updatePhotoButton()` (with template literal fix)
- [ ] 25. Replace `attachPhoto()` with `attachPhotos()` (already fixed)

### Cleanup
- [ ] 26. Delete `terminal.html.modified`
- [ ] 27. Delete `terminal.html.bak`
- [ ] 28. Test all functionality
- [ ] 29. Commit changes

---

*Created: 2025-12-28*
