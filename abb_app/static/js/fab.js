(() => {
    function savePageState() {
        const formData = Array.from(
            document.querySelectorAll('input[id], textarea[id]')
        ).map(field => ({
            id: field.id,
            value: field.value,
            checked: field.matches('[type="checkbox"], [type="radio"]')
                ? field.checked
                : null
        }));

        sessionStorage.setItem('pageState', JSON.stringify({
            scrollPosition: window.scrollY,
            formData
        }));
    }

    function restorePageState() {
        const savedState = sessionStorage.getItem('pageState');
        if (!savedState) return;

        const pageState = JSON.parse(savedState);
        pageState.formData.forEach(({id, value, checked}) => {
            const field = document.getElementById(id);
            if (!field) return;

            field.value = value;
            if (checked !== null) field.checked = checked;
        });

        window.scrollTo(0, pageState.scrollPosition);
        sessionStorage.removeItem('pageState');
    }

    document.addEventListener('click', event => {
        const control = event.target.closest('[data-fab-action]');
        if (!control) return;

        switch (control.dataset.fabAction) {
            case 'save-page-state':
                savePageState();
                break;
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

    document.addEventListener('DOMContentLoaded', restorePageState);
})();
