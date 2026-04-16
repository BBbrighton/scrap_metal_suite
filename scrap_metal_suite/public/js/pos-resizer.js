(function () {
    'use strict';

    const MIN_RIGHT_PX = 320;
    const MAX_RIGHT_RATIO = 0.5;
    const MOBILE_BREAKPOINT = 768;

    function clamp(width) {
        const max = Math.floor(window.innerWidth * MAX_RIGHT_RATIO);
        const min = Math.min(MIN_RIGHT_PX, max);
        return Math.max(min, Math.min(max, width));
    }

    function applyWidth(el, width) {
        el.style.width = width + 'px';
        el.style.flex = '0 0 ' + width + 'px';
    }

    function clearWidth(el) {
        el.style.width = '';
        el.style.flex = '';
    }

    function init(opts) {
        const right = document.querySelector(opts.rightSelector);
        const resizer = document.querySelector(opts.resizerSelector);
        if (!right || !resizer) return;

        const storageKey = opts.storageKey;

        function isMobile() {
            return window.innerWidth <= MOBILE_BREAKPOINT;
        }

        function restore() {
            if (isMobile()) { clearWidth(right); return; }
            const saved = parseInt(localStorage.getItem(storageKey), 10);
            if (saved && !isNaN(saved)) {
                applyWidth(right, clamp(saved));
            }
        }

        let startX = 0;
        let startWidth = 0;

        function getX(e) {
            return e.touches ? e.touches[0].clientX : e.clientX;
        }

        function onDown(e) {
            if (isMobile()) return;
            startX = getX(e);
            startWidth = right.getBoundingClientRect().width;
            document.body.classList.add('resizing-panes');
            resizer.classList.add('dragging');
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
            document.addEventListener('touchmove', onMove, { passive: false });
            document.addEventListener('touchend', onUp);
            e.preventDefault();
        }

        function onMove(e) {
            const dx = startX - getX(e);
            applyWidth(right, clamp(startWidth + dx));
            if (e.cancelable) e.preventDefault();
        }

        function onUp() {
            document.body.classList.remove('resizing-panes');
            resizer.classList.remove('dragging');
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onUp);
            const finalWidth = Math.round(right.getBoundingClientRect().width);
            try { localStorage.setItem(storageKey, String(finalWidth)); } catch (_) {}
        }

        function onDblClick() {
            clearWidth(right);
            try { localStorage.removeItem(storageKey); } catch (_) {}
        }

        function onResize() {
            if (isMobile()) { clearWidth(right); return; }
            const saved = parseInt(localStorage.getItem(storageKey), 10);
            if (saved && !isNaN(saved)) {
                applyWidth(right, clamp(saved));
            } else {
                const current = right.getBoundingClientRect().width;
                const clamped = clamp(current);
                if (Math.abs(clamped - current) > 1) applyWidth(right, clamped);
            }
        }

        resizer.addEventListener('mousedown', onDown);
        resizer.addEventListener('touchstart', onDown, { passive: false });
        resizer.addEventListener('dblclick', onDblClick);
        window.addEventListener('resize', onResize);

        restore();
    }

    window.POS_RESIZER = { init: init };
})();
