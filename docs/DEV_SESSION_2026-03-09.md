# Development Session — 2026-03-09

## Branch: `develop`
**Starting commit:** `17a8d3a` (Fix: Cart item removal now targets correct item using unique ID)

## Pre-session Cleanup
- Compared `develop` vs `develop2` — `develop2` is stale (missing bug fixes), can be deleted
- Local `develop` was 2 commits ahead of `origin/develop` — reset to match remote
- Confirmed scheduler cron job for idle POS session cleanup exists and applies to all users (including admin)

## Tasks

### 1. Version Bump
- **Done**: `0.0.1` → `0.1.0` in `scrap_metal_suite/__init__.py`

### 2. Camera — Zoom & Tilt Controls (Both Terminals)
- **Status**: Done
- **Goal**: Add zoom and tilt controls to camera modals, works with any camera
- **Terminals**: POS (scrap) + Truck — both updated identically

**Approach** (progressive enhancement):
1. **Optical zoom + tilt** — used when camera hardware supports it (via `MediaStream` `getCapabilities()` API)
2. **Digital zoom** — canvas-based live preview (cropped center frame via `requestAnimationFrame`)
3. **Tilt** — only shown when camera hardware supports it (no digital fallback)

**Digital Zoom Implementation**:
- Requests max resolution from camera (`3840x2160` ideal) for more pixels to crop from
- **Canvas-based live preview**: At zoom >1x, hides the `<video>` element and renders cropped frames to `<canvas id="zoomPreviewCanvas">` at ~30fps via `requestAnimationFrame`
- Preview is pixel-identical to the captured image (WYSIWYG)
- At zoom =1x, falls back to raw `<video>` element (no overhead)

**Files Changed**:
| File | Changes |
|------|---------|
| `www/pos/terminal.html` | Zoom/tilt slider UI, `initCameraControls()`, `setCameraZoom()`, `setCameraTilt()`, `adjustCamera()`, `applyDigitalZoom()`, `startZoomPreview()`, `stopZoomPreview()`. Canvas-based digital zoom preview. Max resolution request. |
| `www/pos/truck.html` | Same zoom/tilt controls and canvas preview as POS terminal |
| `public/css/pos.css` | `.camera-controls`, `.camera-control-row`, `.camera-slider-group`, `.btn-cam`, `.camera-control-value`, `.camera-control-badge` styles. `#zoomPreviewCanvas` sizing. Light theme overrides. |
| `public/js/pos-translations.js` | Added `zoom`, `tilt`, `optical`, `digital` keys in EN and TH |

**UI**:
- Zoom slider with +/- buttons, shows current value (e.g., `2.5x`)
- Badge shows "Optical" or "Digital" depending on camera capability
- Tilt slider (only visible when camera supports it) with +/- buttons, shows degrees

## Notes
- Remote server deployment requires: `bench migrate && bench restart` for scheduler changes
- `develop2` branch can be safely deleted
- App version is now `0.1.0`
- Camera resolution request: `3840x2160` ideal (camera provides its max supported)
