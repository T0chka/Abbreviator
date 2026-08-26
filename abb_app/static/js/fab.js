(() => {
    document.addEventListener('click', event => {
        const control = event.target.closest('[data-fab-action]');
        if (!control) return;

        switch (control.dataset.fabAction) {
            case 'back':
                window.history.back();
                break;
            case 'scroll-top':
                window.scrollTo({top: 0, behavior: 'smooth'});
                break;
            case 'scroll-bottom':
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
                break;
        }
    });
})();
