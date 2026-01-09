# POS Refactor Plan (Revised)

**Last Updated:** 2025-12-27
**Status:** Incremental approach - extract during feature work

---

## Problem Statement

The POS terminals are implemented as large HTML templates with embedded JavaScript (~2,500 lines each). This makes changes risky and slows feature work.

## Current State

| File | Lines | Functions | Status |
|------|-------|-----------|--------|
| terminal.html | 2,527 | ~85 | Working, monolithic |
| truck.html | 2,254 | ~65 | Working, monolithic |
| index.html | 249 | few | Simple, OK as-is |
| **scale_reader.js** | 642 | shared | **Already extracted** |
| **pos-translations.js** | 657 | shared | **Already extracted** |

**Good news:** The hardest parts (hardware integration, i18n) are already extracted and shared.

---

## Revised Strategy: Incremental Extraction

Instead of a dedicated refactor phase, extract modules **as features are built**.

### Why Incremental?

| Big-Bang Refactor | Incremental Extraction |
|-------------------|------------------------|
| Feature freeze required | Features continue |
| Test everything twice | Test once |
| Refactor code that will change | Extract stable, tested code |
| High risk, delayed value | Low risk, immediate value |

### Extraction Triggers

Extract a module when:
1. You're **rewriting** a section (e.g., UI redesign)
2. You find **duplicate code** between terminal.html and truck.html
3. A function grows beyond **~50 lines**

---

## Module Structure

When extracting, use this structure:

```
public/js/pos/
├── shared/              # Cross-terminal utilities
│   ├── api.js           # Frappe API wrapper
│   └── dom.js           # DOM helpers
├── terminal/            # Scrap terminal modules
│   └── [feature].js
└── truck/               # Truck terminal modules
    └── [feature].js
```

### Module Pattern

```javascript
// public/js/pos/[page]/[feature].js
const FeatureName = {
    state: { },

    init(container, options) {
        this.container = container;
        this.render();
        this.bindEvents();
    },

    render() {
        // Update UI based on state
    },

    bindEvents() {
        // Event delegation
    }
};
```

---

## Shared Utilities (Extract When Needed)

Only create these when you find yourself duplicating code:

### Priority 1: api.js (Easy win)

```javascript
// public/js/pos/shared/api.js
const POS_API = {
    async call(method, args) {
        try {
            const response = await frappe.call({
                method: `scrap_metal_suite.api.v1.${method}`,
                args: args
            });
            return response.message;
        } catch (error) {
            this.handleError(error);
            throw error;
        }
    },

    handleError(error) {
        console.error('API Error:', error);
        // Show user-friendly error
    }
};
```

### Priority 2: dom.js (Tiny, useful)

```javascript
// public/js/pos/shared/dom.js
const DOM = {
    $(id) { return document.getElementById(id); },
    show(el) { el.style.display = ''; },
    hide(el) { el.style.display = 'none'; },
    setText(el, text) { el.textContent = text; },
    addClass(el, cls) { el.classList.add(cls); },
    removeClass(el, cls) { el.classList.remove(cls); }
};
```

### Already Extracted (Don't Touch)

- `scale_reader.js` - WebSerial integration
- `pos-translations.js` - i18n

---

## Quick Fixes (Do Anytime)

### 1. Fix Thai Encoding

```bash
# Check current encoding
file pos-translations.js

# Convert if needed (should be UTF-8)
iconv -f ISO-8859-1 -t UTF-8 pos-translations.js > pos-translations-fixed.js
```

### 2. Fix Duplicate IDs

When you encounter duplicate IDs during feature work, rename with context:

```html
<!-- Before -->
<span id="dropoffCardDate">...</span>  <!-- exists twice -->

<!-- After -->
<span id="dropoffSearchDate">...</span>
<span id="dropoffDetailDate">...</span>
```

---

## Extraction Checklist

When extracting a module:

1. [ ] Identify functions to extract (related, ~50+ lines total)
2. [ ] Create new file in `public/js/pos/<page>/`
3. [ ] Move functions, wrap in object/module pattern
4. [ ] Add `<script src="...">` to HTML
5. [ ] Replace inline calls with module calls
6. [ ] Test the specific feature
7. [ ] Remove dead inline code

---

## What NOT to Do

- Don't create empty placeholder modules
- Don't refactor code you're not actively changing
- Don't introduce build tools (webpack, etc.) - keep it simple
- Don't create v2 parallel routes unless actively testing both

---

## When to Apply

This plan should be referenced and applied during:
- Phase 7: Truck Terminal UI Redesign
- Phase 8: Per-Item Fulfillment (if touching terminal.html)
- Any future terminal feature work

See respective implementation plans for specific module extractions.

---

*This plan replaces the previous big-bang approach with incremental extraction tied to feature work.*
