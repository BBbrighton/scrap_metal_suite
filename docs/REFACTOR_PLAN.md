# POS Terminal Refactoring Plan

> **Created**: 2026-01-18
> **Goal**: Extract inline JavaScript and CSS to shared modules for maintainability and reuse

---

## Current State Analysis

### File Sizes (Complete Analysis)

| File | Total Lines | JavaScript Lines | HTML/Jinja Lines |
|------|-------------|------------------|------------------|
| `terminal.html` | 2,565 | ~1,975 (77%) | ~590 |
| `truck.html` | 3,346 | ~2,654 (79%) | ~692 |
| **Combined** | **5,911** | **~4,629** | **~1,282** |

### Existing Shared Files

| File | Purpose | Lines | Status |
|------|---------|-------|--------|
| `public/js/pos-translations.js` | i18n translations | ~400 | Done |
| `public/js/scale_reader.js` | WebSerial scale integration | ~800 | Done |
| `public/js/html5-qrcode.min.js` | QR/Barcode scanning | Vendor | Done |
| `public/css/pos.css` | Shared styles | ~6,800 | Done |

### Problems Identified

1. **~50+ duplicate/similar functions** between `terminal.html` and `truck.html`
2. **Identical inline `<style>` blocks** in both files (25 lines each)
3. **No separation of concerns** - HTML templates are 77-79% JavaScript
4. **Difficult to maintain** - bug fixes require editing 2 files
5. **Inconsistent translation handling** - some hardcoded strings remain
6. **Inline styles** throughout HTML elements (`style="display:none"` everywhere)

---

## Complete Function Inventory

### Category 1: Core Utilities (Exact Duplicates) - 7 functions

| Function | terminal.html | truck.html | Identical? |
|----------|---------------|------------|------------|
| `t(key)` | Line 653 | Line 695 | Yes |
| `toggleLanguage()` | Line 657 | Line 757 | Yes |
| `applyLanguage(lang)` | Line 662 | Line 762 | Similar* |
| `toggleTheme()` | Line 680 | Line 857 | Yes |
| `applyTheme(theme)` | Line 686 | Line 863 | Similar* |
| `updateClock()` | Line 700 | Line 877 | Yes |
| `callAPI(method, args)` | Line 710 | Line 887 | Yes |

*Different only in terminal ID (`posTerminal` vs `truckTerminal`)

**Estimated shared lines**: ~70

---

### Category 2: Scanner Functions (Exact Duplicates) - 6 functions

| Function | terminal.html | truck.html | Identical? |
|----------|---------------|------------|------------|
| `openScanner()` | Line 732 | Line 909 | Yes |
| `onScanSuccess(decodedText)` | Line 769 | Line 946 | Yes |
| `closeScanner()` | Line 784 | Line 962 | Yes |
| `submitManualDropoff()` | Line 794 | Line 972 | Yes |
| `parseQRValue(rawValue)` | Line 803 | Line 981 | Similar* |
| `searchAndSelectDropoff(query)` | Line 824 | Line 1003 | Yes |

*Different URL pattern matching (`pos-order` vs `dropoff`)

**Estimated shared lines**: ~100

---

### Category 3: Dropoff Search (Near Duplicates) - 8 functions

| Function | terminal.html | truck.html | Notes |
|----------|---------------|------------|-------|
| `clearDropoffSearchResults()` | Line 847 | Line 1026 | Identical |
| `setDropoffActiveIndex(nextIndex)` | Line 857 | Line 1036 | Identical |
| `handleDropoffSearchKeydown(event)` | Line 883 | Line 1062 | Identical |
| `searchDropoff(query)` | Line 937 | Line 1116 | Similar (template literals) |
| `selectDropoff(...)` | Line 976 | Line 1155 | Different follow-up |
| `fetchDropoffDetails(dropoffName)` | Line 1011 | Line 1195 | Different processing |
| `toggleDropoffItems()` | Line 1187 | Line 1285 | Identical |
| `toggleDropoffDetails(event)` | Line 1196 | Line 1303 | Identical |

**Estimated shared lines**: ~150

---

### Category 4: Photo Capture (Near Duplicates) - 9 functions

| Function | terminal.html | truck.html | Notes |
|----------|---------------|------------|-------|
| `openPhotoCapture()` | Line 1451 | Line 1837 | Different params |
| `closePhotoCapture()` | Line 1485 | Line 1894 | Identical |
| `capturePhoto()` | Line 1497 | Line 1904 | Identical |
| `retakePhoto()` | Line 1517 | Line 1932 | Identical |
| `addPhotoAndContinue()` | Line 1531 | Line 1946 | Identical |
| `addPhotoAndClose()` | Line 1551 | Line 1966 | Different save logic |
| `updatePhotoThumbnails()` | Line 1563 | Line 2064 | Identical |
| `removePhoto(index)` | Line 1603 | Line 2104 | Identical |
| `b64toBlob()` | N/A | Line 2124 | Truck only |

**Estimated shared lines**: ~160

---

### Category 5: Remarks Modal (Near Duplicates) - 4 functions

| Function | terminal.html | truck.html | Notes |
|----------|---------------|------------|-------|
| `openRemarksModal()` | Line 1434 | Line 1768 | Similar |
| `closeRemarksModal()` | Line 1440 | Line 1780 | Identical |
| `saveRemarks()` | Line 1444 | Line 1784 | Different API |
| `updateRemarksButton()` | N/A | Line 1823 | Truck only |

**Estimated shared lines**: ~30

---

### Category 6: Scale Functions (Near Duplicates) - 25 functions

| Function | terminal.html | truck.html | Notes |
|----------|---------------|------------|-------|
| `checkSessionScale()` | Line 1893 | Line 2174 | Identical |
| `loadScales()` | Line 1932 | Line 2211 | Different `usage_type` |
| `populateScaleDropdown()` | Line 1970 | Line 2249 | Similar |
| `onScaleDropdownChange()` | Line 2007 | Line 2286 | Identical |
| `showSelectedScaleInfo(scale)` | Line 2027 | Line 2306 | Identical |
| `showScaleModal()` | Line 2034 | Line 2313 | Identical |
| `openScaleScanner()` | Line 2040 | Line 2319 | Identical |
| `onScaleScanSuccess(decodedText)` | Line 2077 | Line 2356 | Different type check |
| `closeScaleScanner()` | Line 2127 | Line 2407 | Identical |
| `confirmScaleSelection()` | Line 2137 | Line 2417 | Identical |
| `confirmScaleManualMode()` | Line 2449 | Line 2454 | Identical |
| `showScaleConnectionModal(state)` | Line 2174 | Line 2486 | Identical |
| `showScaleConnectionResult(...)` | Line 2204 | Line 2516 | Identical |
| `testScaleConnection(scale)` | Line 2227 | Line 2543 | Different callback |
| `closeScaleConnectionModal()` | Line 2306 | Line 2590 | Identical |
| `openScaleTestPage()` | Line 2317 | Line 2601 | Identical |
| `completeScaleSelection()` | Line 2323 | Line 2607 | Identical |
| `useManualEntryMode()` | Line 2481 | Line 2634 | Identical |
| `updateScaleDisplay()` | Line 2352 | Line 2666 | Different elements |
| `toggleScaleMenu()` | Line 2385 | Line 2702 | Identical |
| `closeScaleMenuOnOutsideClick(e)` | Line 2399 | Line 2716 | Identical |
| `handleScaleReconnect()` | Line 2409 | Line 2725 | Different connect |
| `handleScaleDisconnect()` | Line 2435 | Line 2751 | Identical |
| `disconnectScale()` | Line 641 | Line 2759 | Identical |
| `handleScaleUnplugged()` | Line 2514 | N/A | Scrap only |

**Estimated shared lines**: ~500

---

### Category 7: Session Management (Near Duplicates) - 3 functions

| Function | terminal.html | truck.html | Notes |
|----------|---------------|------------|-------|
| `confirmCloseSession()` | Line 1827 | Line 1736 | Different summary |
| `closeCloseSessionModal()` | Line 1850 | Line 1740 | Identical |
| `closeSession()` | Line 1854 | Line 1744 | Similar |

**Estimated shared lines**: ~50

---

### Category 8: Terminal-Specific Functions

#### Scrap Terminal Only (terminal.html) - 22 functions

| Function | Line | Purpose |
|----------|------|---------|
| `loadExistingScrapWeight()` | 1085 | Load reweight data |
| `loadExistingPhotos()` | 1121 | Load scrap weight photos |
| `showReweightBanner()` | 1139 | Show reweight warning |
| `renderDropoffItems()` | 1147 | Render order items |
| `toggleCart()` | 1219 | Toggle cart collapse |
| `updateCartCount()` | 1231 | Update cart badge |
| `filterCategory()` | 1280 | Filter items by category |
| `selectItem()` | 1312 | Select item for weighing |
| `closeWeightModal()` | 1329 | Close weight modal |
| `addToCart()` | 1335 | Add item to cart |
| `renderCart()` | 1371 | Render cart items |
| `removeFromCart()` | 1404 | Remove cart item |
| `clearCart()` | 1412 | Clear all cart items |
| `clearTransaction()` | 1419 | Clear transaction |
| `updateButtonStates()` | 1424 | Update button states |
| `showConfirmModal()` | 1609 | Show confirmation modal |
| `closeConfirmModal()` | 1674 | Close confirmation |
| `confirmAndRecord()` | 1678 | Confirm and record |
| `recordWeight()` | 1692 | Submit weight to API |
| `attachPhotos()` | 1745 | Attach photos to record |
| `printScrapWeight()` | 1786 | Print thermal receipt |
| `showSessionSummary()` | 1793 | Show session summary |
| `closeSummaryModal()` | 1823 | Close summary modal |
| `handleWeightUpdate()` | 2274 | Handle scale weight |
| `useLiveWeight()` | 2530 | Use live weight |
| `toggleWeightMode()` | 2538 | Toggle weight mode |
| `updateWeightModalDisplay()` | 2543 | Update modal display |

**Total scrap-specific lines**: ~550

#### Truck Terminal Only (truck.html) - 28 functions

| Function | Line | Purpose |
|----------|------|---------|
| `updateTranslations()` | 778 | Extra translation updates |
| `loadExistingTruckPhotos()` | 1230 | Load truck photos |
| `updatePhotoButtonStates()` | 1247 | Update photo buttons |
| `renderExpectedItems()` | 1257 | Render expected items |
| `toggleScrapPanel()` | 1294 | Toggle scrap records |
| `loadWeightData()` | 1377 | Load weight verification |
| `updateWeightDisplay()` | 1408 | Update variance display |
| `resetWeights()` | 1575 | Reset weight state |
| `openWeightModal()` | 1655 | Old weight modal |
| `saveWeight()` | 1682 | Old save method |
| `updatePhotoButtonForType()` | 2109 | Update photo per type |
| `updatePhotoButton()` | 2141 | Reset photo buttons |
| `connectTruckScale()` | 2772 | Connect truck scale |
| `handleTruckWeightUpdate()` | 2826 | Handle truck weight |
| `handleTruckScaleDisconnect()` | 2866 | Handle disconnect |
| `switchWeightTab()` | 2878 | Switch gross/tare tab |
| `saveGrossWeight()` | 2896 | Save gross weight |
| `saveTareWeight()` | 2914 | Save tare weight |
| `saveWeightByType()` | 2932 | Save weight by type |
| `printTruckWeight()` | 3005 | Print truck receipt |
| `showWeightConfirmation()` | 3011 | Show inline confirm |
| `updateTabCheckmarks()` | 3049 | Update checkmarks |
| `updateNetWeightSummary()` | 3084 | Update net summary |
| `showWeightConfirmModal()` | 3120 | Weight confirm modal |
| `closeWeightConfirmModal()` | 3152 | Close confirm modal |
| `confirmAndSaveWeight()` | 3158 | Confirm and save |
| `showCompleteDropoffModal()` | 3203 | Show complete modal |
| `closeCompleteDropoffModal()` | 3286 | Close complete modal |
| `confirmCompleteDropoff()` | 3290 | Complete dropoff |
| `updateCompleteButton()` | 3332 | Update complete btn |

**Total truck-specific lines**: ~750

---

## Total Estimated Savings

| Category | Duplicate Lines | Can Share |
|----------|-----------------|-----------|
| Core Utilities | ~140 (70x2) | ~70 |
| Scanner Functions | ~200 (100x2) | ~100 |
| Dropoff Search | ~300 (150x2) | ~150 |
| Photo Capture | ~320 (160x2) | ~160 |
| Remarks Modal | ~60 (30x2) | ~30 |
| Scale Functions | ~1000 (500x2) | ~500 |
| Session Management | ~100 (50x2) | ~50 |
| **TOTAL** | **~2,120** | **~1,060** |

After refactoring:
- **Before**: 4,629 lines of JavaScript across 2 files
- **After**: ~2,509 lines shared + ~550 scrap + ~750 truck = ~3,809 lines
- **Reduction**: ~820 lines (18% less code)
- **Maintainability**: Bug fixes in 1 place instead of 2

---

## Proposed File Structure

```
scrap_metal_suite/
├── public/
│   ├── css/
│   │   ├── pos.css                    # Shared styles (existing)
│   │   └── pos-fullscreen.css         # NEW: Frappe override (25 lines)
│   │
│   └── js/
│       ├── pos-translations.js        # Translations (existing)
│       ├── scale_reader.js            # Scale WebSerial (existing)
│       ├── html5-qrcode.min.js        # QR library (existing)
│       │
│       ├── pos-core.js                # NEW: Core utilities (~70 lines)
│       ├── pos-scanner.js             # NEW: Scanner functions (~100 lines)
│       ├── pos-dropoff.js             # NEW: Dropoff search (~150 lines)
│       ├── pos-photo.js               # NEW: Photo capture (~160 lines)
│       ├── pos-remarks.js             # NEW: Remarks (~30 lines)
│       ├── pos-scale-ui.js            # NEW: Scale UI (~500 lines)
│       ├── pos-session.js             # NEW: Session (~50 lines)
│       │
│       ├── terminal-scrap.js          # NEW: Scrap specific (~550 lines)
│       └── terminal-truck.js          # NEW: Truck specific (~750 lines)
│
└── www/pos/
    ├── terminal.html                  # Scrap (~590 HTML + script includes)
    └── truck.html                     # Truck (~692 HTML + script includes)
```

---

## Implementation Phases

### Phase R1: Extract Fullscreen CSS (5 min)

Create `public/css/pos-fullscreen.css`:
```css
/* Frappe fullscreen override - hide navigation */
.navbar, .web-footer, .footer, footer,
.page-header, .page-head, header.navbar {
    display: none !important;
}
body {
    padding-top: 0 !important;
    margin: 0 !important;
    overflow: hidden;
}
.main-section {
    padding: 0 !important;
    margin: 0 !important;
}
.container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}
.web-content, .page-content, main {
    padding: 0 !important;
    margin: 0 !important;
}
```

Update both HTML files to remove inline style and add:
```html
<link rel="stylesheet" href="/assets/scrap_metal_suite/css/pos-fullscreen.css">
```

---

### Phase R2: Extract Core Utilities (`pos-core.js`) - 30 min

```javascript
// pos-core.js - Core POS utilities
const POS_CORE = (function() {
    return {
        // Translation wrapper
        t: function(key) {
            return POS_I18N.t(key);
        },

        // Toggle language
        toggleLanguage: function(state) {
            state.language = POS_I18N.toggleLanguage();
            return state.language;
        },

        // Apply language to DOM
        applyLanguage: function(lang, langIconId, showCode) {
            const langIcon = document.getElementById(langIconId);
            if (langIcon) {
                langIcon.textContent = showCode ? lang.toUpperCase() : (lang === 'en' ? 'TH' : 'EN');
            }
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                el.textContent = POS_I18N.t(key);
            });
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                el.placeholder = POS_I18N.t(key);
            });
        },

        // Toggle theme
        toggleTheme: function(state) {
            state.theme = state.theme === 'dark' ? 'light' : 'dark';
            localStorage.setItem('posTheme', state.theme);
            return state.theme;
        },

        // Apply theme to terminal
        applyTheme: function(theme, terminalId) {
            const terminal = document.getElementById(terminalId);
            const themeIcon = document.getElementById('themeIcon');
            if (theme === 'light') {
                terminal.classList.add('light-theme');
                themeIcon.innerHTML = '&#127769;';
            } else {
                terminal.classList.remove('light-theme');
                themeIcon.innerHTML = '&#9728;';
            }
        },

        // Update clock
        updateClock: function() {
            const now = new Date();
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            const dow = days[now.getDay()];
            const date = now.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
            const time = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
            const el = document.getElementById('currentTime');
            if (el) el.textContent = dow + ' ' + date + ' ' + time;
        },

        // API call wrapper
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
            if (data.exc) throw new Error(data.exc);
            return data;
        },

        // Play beep sound
        playBeep: function() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioCtx.createOscillator();
                oscillator.type = 'sine';
                oscillator.frequency.setValueAtTime(800, audioCtx.currentTime);
                oscillator.connect(audioCtx.destination);
                oscillator.start();
                oscillator.stop(audioCtx.currentTime + 0.1);
            } catch (e) {}
        }
    };
})();
```

---

### Phase R3: Extract Scanner (`pos-scanner.js`) - 30 min

```javascript
// pos-scanner.js - QR/Barcode scanner functions
const POS_SCANNER = (function() {
    let html5QrCode = null;

    return {
        open: async function(elementId, statusId, onSuccess) {
            const modal = document.getElementById('scannerModal');
            modal.style.display = 'flex';

            if (html5QrCode) {
                try { await html5QrCode.stop(); } catch (e) {}
                html5QrCode = null;
            }

            document.getElementById(elementId).innerHTML = '';
            document.getElementById(statusId).textContent = POS_CORE.t('startingCamera');

            try {
                html5QrCode = new Html5Qrcode(elementId);
                await html5QrCode.start(
                    { facingMode: "environment" },
                    { fps: 10, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                    function(decodedText) {
                        POS_CORE.playBeep();
                        POS_SCANNER.close();
                        if (onSuccess) onSuccess(decodedText);
                    },
                    function() {}
                );
                document.getElementById(statusId).textContent = POS_CORE.t('pointCamera');
            } catch (err) {
                console.error('Scanner error:', err);
                document.getElementById(statusId).textContent = POS_CORE.t('cameraNotAvailable');
            }
        },

        close: async function() {
            if (html5QrCode) {
                try { await html5QrCode.stop(); } catch (e) {}
                html5QrCode = null;
            }
            document.getElementById('scannerModal').style.display = 'none';
        },

        parseQRValue: function(rawValue, patterns) {
            patterns = patterns || [/\/app\/dropoff\/([^\/\?#]+)/, /\/app\/pos-order\/([^\/\?#]+)/];
            for (var i = 0; i < patterns.length; i++) {
                var match = rawValue.match(patterns[i]);
                if (match && match[1]) return decodeURIComponent(match[1]);
            }
            if (rawValue.startsWith('http://') || rawValue.startsWith('https://')) {
                try {
                    var url = new URL(rawValue);
                    var pathParts = url.pathname.split('/').filter(function(p) { return p; });
                    if (pathParts.length > 0) return decodeURIComponent(pathParts[pathParts.length - 1]);
                } catch (e) {}
            }
            return rawValue;
        }
    };
})();
```

---

### Phase R4-R7: Similar extraction patterns

(Detailed code for each module follows same pattern)

---

## Testing Plan

### Pre-Refactoring Checklist

Before starting:
- [ ] Record video of scrap terminal full workflow
- [ ] Record video of truck terminal full workflow
- [ ] Document all button states and behaviors

### Phase Testing

#### After Each Phase:
- [ ] Run `bench build --app scrap_metal_suite`
- [ ] Clear browser cache (hard refresh)
- [ ] Test affected functionality
- [ ] Check console for errors

#### Phase R1 (CSS):
- [ ] Both terminals load without styling issues
- [ ] Frappe navbar/footer hidden
- [ ] Dark/light theme works

#### Phase R2 (Core):
- [ ] Language toggle (EN/TH) works
- [ ] Theme toggle works
- [ ] Clock updates
- [ ] API calls work (search dropoff)

#### Phase R3 (Scanner):
- [ ] Scanner modal opens
- [ ] Camera permission prompt
- [ ] QR/barcode scanning works
- [ ] Beep sound plays
- [ ] Manual entry works

#### Phase R4-R7:
(Similar testing for each module)

### End-to-End Tests

#### Scrap Terminal:
1. [ ] Open terminal (scale modal)
2. [ ] Select scale or manual mode
3. [ ] Search dropoff
4. [ ] Add items to cart
5. [ ] Enter weights
6. [ ] Add remarks
7. [ ] Capture photo
8. [ ] Confirm and record
9. [ ] Verify print
10. [ ] Close session

#### Truck Terminal:
1. [ ] Open terminal (scale modal)
2. [ ] Select scale or manual mode
3. [ ] Search dropoff
4. [ ] Record gross weight
5. [ ] Verify confirmation
6. [ ] Add photo
7. [ ] Record tare weight
8. [ ] Check net calculation
9. [ ] Check variance
10. [ ] Add remarks
11. [ ] Complete dropoff
12. [ ] Verify print
13. [ ] Close session

### Regression Checklist

- [ ] No console errors
- [ ] All modals open/close
- [ ] All API calls succeed
- [ ] Scale connection works
- [ ] Scale reconnection works
- [ ] Photos save correctly
- [ ] Remarks save correctly
- [ ] Print works
- [ ] Session close works
- [ ] Dark/light theme
- [ ] EN/TH language

---

## Implementation Order (Recommended)

| Phase | Module | Est. Time | Risk |
|-------|--------|-----------|------|
| R1 | CSS extraction | 5 min | Low |
| R2 | Core utilities | 30 min | Low |
| R3 | Scanner | 30 min | Low |
| R7 | Session | 15 min | Low |
| R5 | Photo | 45 min | Medium |
| R4 | Dropoff search | 45 min | Medium |
| R6 | Scale UI | 90 min | High |
| R8 | Terminal-specific | 120 min | Medium |

**Total: ~6-8 hours**

---

## Rollback Plan

Each phase committed separately:
```bash
git commit -m "Refactor R1: Extract fullscreen CSS"
git commit -m "Refactor R2: Extract core utilities"
# etc.
```

If issues found:
1. Identify problematic commit
2. `git revert <commit-hash>` or fix forward
3. Re-test

---

*Document version: 2.0 (Complete analysis)*
*Last updated: 2026-01-18*
