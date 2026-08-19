document.addEventListener('DOMContentLoaded', () => {
    const config = document.getElementById('document-session');
    const timeoutMs = Number(config.dataset.timeoutMs);
    const touchUrl = config.dataset.touchUrl;
    const endUrl = config.dataset.endUrl;
    const startUrl = config.dataset.startUrl;
    const touchThrottleMs = 60_000;

    let inactivityTimer = null;
    let lastTouch = 0;
    let ending = false;

    function requestHeaders() {
        return {'X-CSRFToken': getCookie('csrftoken')};
    }

    function touchServer() {
        const now = Date.now();
        if (now - lastTouch < touchThrottleMs) return;

        lastTouch = now;
        fetch(touchUrl, {
            method: 'POST',
            headers: requestHeaders(),
            keepalive: true
        }).catch(() => {});
    }

    async function endSession() {
        if (ending) return;
        ending = true;

        try {
            await fetch(endUrl, {
                method: 'POST',
                headers: requestHeaders(),
                keepalive: true
            });
        } finally {
            window.location.assign(`${startUrl}?expired=1`);
        }
    }

    function registerActivity() {
        clearTimeout(inactivityTimer);
        inactivityTimer = window.setTimeout(endSession, timeoutMs);
        touchServer();
    }

    ['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(eventName => {
        window.addEventListener(eventName, registerActivity, {passive: true});
    });

    registerActivity();
});
