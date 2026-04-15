# Terminal UI Uniformity Plan

**Date:** 2026-04-14
**Status:** Proposed
**Author:** Engineering (via Claude Code UI analysis agent)

---

## 1. Current State

Four terminal HTML files exist with inconsistent architectures:

| Aspect | POS (`pos/terminal.html`) | Truck (`pos/truck.html`) | Prod-Orange (`pos/production.html`) | Prod-Blue (`production/terminal.html`) |
|---|---|---|---|---|
| **Lines** | 2,546 | 3,320 | 370 | 604 |
| **CSS classes** | `.terminal-*` | `.terminal-*` | `.production-*` | `.prod-*` |
| **Inline JS** | ~1,958 lines | ~2,630 lines | ~88 lines | ~425 lines |
| **Uses POS_CORE** | No | No | No | Yes |
| **Uses data-i18n** | No | No | No | Yes |
| **Theme toggle** | Yes (inline) | Yes (inline) | No | Yes (via POS_CORE) |
| **Layout** | 2-panel | 2-panel | 3-panel | 2-panel (460px fixed right) |
| **CSS files** | `pos.css` + `pos-fullscreen.css` | Same | `pos.css` + `production-theme.css` | `production.css` (standalone) |

### Key Problems

1. **Three different CSS class namespaces** — no shared structural CSS
2. **Massive inline JS** — POS (1,958 lines) and Truck (2,630 lines) have all logic inline
3. **Duplicated fullscreen overrides** — written 4 separate ways
4. **Two production terminals** — orange (3-panel) and blue (2-panel) with different architectures
5. **`terminal-base.css` does not exist** despite being referenced in project memory

---

## 2. Recommendation: Keep Blue Production Terminal

The blue terminal (`production/terminal.html`) follows the best patterns:
- Uses `POS_CORE` for theme, clock, API wrapper
- Uses `data-i18n` attributes for translation
- Uses `production.css` with CSS custom properties
- Clean 2-panel layout matching POS/Truck

**Delete `pos/production.html`** (orange terminal).

---

## 3. Unified Architecture

### 3.1 Unified Class Convention (2-panel for all)

```
.terminal-container#[terminalId]     <-- root, receives .light-theme
  header.t-header
    .t-header-left                   <-- back btn, brand, session, operator, scale badge
    .t-header-center                 <-- clock
    .t-header-right                  <-- lang, theme, session controls
  .t-body                            <-- flex row
    .t-panel-left                    <-- flex:1, category tabs + item grid
    .t-panel-right                   <-- 460px fixed, context area (cart/dropoff/variance)
```

### 3.2 CSS Strategy

**Create `terminal-base.css`** — shared structural CSS + fullscreen overrides:

```css
:root {
  /* Structure */
  --t-header-height: 56px;
  --t-panel-right-width: 460px;
  --t-radius: 8px;
  --t-gap: 12px;

  /* Colors (overridden per theme) */
  --t-primary: #3b82f6;
  --t-primary-light: #60a5fa;
  --t-bg: #0f172a;
  --t-card-bg: #1e293b;
  --t-card-border: #334155;
  --t-text: #ffffff;
  --t-text-secondary: #94a3b8;
  --t-success: #22c55e;
  --t-warning: #f59e0b;
  --t-danger: #ef4444;
}

/* Fullscreen overrides — single source of truth */
.navbar, .web-footer, .footer, footer,
.page-header, .page-head, header.navbar { display: none !important; }
```

**Three thin theme files** (~20 lines each):

| File | Primary Color | Use |
|------|--------------|-----|
| `pos-theme.css` | `#3b82f6` (blue) | POS scrap weighing |
| `truck-theme.css` | `#0891b2` (teal) | Truck weighing |
| `production-theme.css` | `#f97316` (orange) | Production sorting |

### 3.3 JS Module Strategy

| Module | Scope | Status |
|--------|-------|--------|
| `pos-core.js` | All terminals | Exists — i18n, theme, clock, API, audio |
| `pos-translations.js` | All terminals | Exists — base EN/TH keys |
| `production-translations.js` | Production only | Exists — extend() pattern |
| `scale_reader.js` | All terminals | Exists — WebSerial |
| `pos-scanner.js` | POS + Truck | Exists — QR/barcode |
| `pos-terminal.js` | POS only | **CREATE** — extract from inline |
| `truck-terminal.js` | Truck only | **CREATE** — extract from inline |

---

## 4. File Actions

| File | Action |
|------|--------|
| `www/pos/production.html` | **DELETE** — orange terminal, replaced by blue |
| `www/pos/production.html.backup` | **DELETE** |
| `public/css/production-theme-fix.css` | **DELETE** — orphaned, no references |
| `public/css/pos-fullscreen.css` | **DELETE** — merge into `terminal-base.css` |
| `public/js/production-terminal.js` | **DELETE** — belongs to orange terminal |
| `public/css/terminal-base.css` | **CREATE** — shared structural CSS |
| `public/css/pos-theme.css` | **CREATE** — POS color overrides |
| `public/css/truck-theme.css` | **CREATE** — Truck color overrides |
| `public/js/pos-terminal.js` | **CREATE** — extract ~1,958 lines from inline |
| `public/js/truck-terminal.js` | **CREATE** — extract ~2,630 lines from inline |
| `www/production/terminal.html` | **KEEP** — refactor to use `terminal-base.css` |
| `public/css/production.css` | **KEEP** — rename/refactor to theme file |

---

## 5. Migration Order

1. Create `terminal-base.css` with shared structure + fullscreen overrides
2. Create `pos-theme.css` extracting colors from `pos.css`
3. Create `truck-theme.css`
4. Refactor production terminal to use `terminal-base.css` + `production-theme.css`
5. Extract POS inline JS to `pos-terminal.js`
6. Extract Truck inline JS to `truck-terminal.js`
7. Refactor POS and Truck HTML to shared class names + `data-i18n`
8. Delete dead files
9. Test all three terminals end-to-end

---

## 6. Why NOT React

Considered and rejected:
- Frappe web templates are server-rendered Jinja2 — React fights the framework
- Terminals already behave like SPAs with vanilla JS + `frappe.call()`
- Would require build pipeline (Webpack/Vite), router, state management
- The real problem is inconsistency, not tech stack — a shared base template solves it
- Team knows the current stack and it works in production
