document.addEventListener('DOMContentLoaded', () => {
    if (
        new URLSearchParams(window.location.search).get('expired') === '1'
    ) {
        window.history.replaceState({}, '', window.location.pathname);
    }

    const uploadContainer = document.getElementById('uploadContainer');
    const fileInput = document.getElementById('fileInput');
    const uploadForm = document.getElementById('uploadForm');
    const loadingOverlay = document.getElementById('loading-overlay');
    const demoLink = document.getElementById('demoLink');
    const errorDialog = document.getElementById('upload-error-dialog');
    const errorMessage = document.getElementById('upload-error-message');
    const errorClose = document.getElementById('uploadErrorClose');

    const maxUploadSize = Number(uploadForm.dataset.maxUploadSize);
    const maxUploadSizeMb = uploadForm.dataset.maxUploadSizeMb;
    const processUrlTemplate = uploadForm.dataset.processUrl;

    function setLoading(visible) {
        loadingOverlay.classList.toggle('is-hidden', !visible);
    }

    function formatMb(bytes) {
        return new Intl.NumberFormat('ru-RU', {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1
        }).format(bytes / (1024 * 1024));
    }

    function showError(message) {
        setLoading(false);
        errorMessage.textContent = message;

        if (typeof errorDialog.showModal === 'function') {
            errorDialog.showModal();
        } else {
            alert(message);
        }
    }

    function validateFile(file) {
        if (!file.name.toLowerCase().endsWith('.docx')) {
            window.umami?.track('upload_failed', {
                reason: 'file_type'
            });
            showError('Можно загрузить только файл формата .docx.');
            return false;
        }

        if (file.size > maxUploadSize) {
            window.umami?.track('upload_failed', {
                reason: 'file_size'
            });
            showError(
                `Файл слишком большой: ${formatMb(file.size)} МБ. ` +
                `Максимальный размер: ${maxUploadSizeMb} МБ.`
            );
            return false;
        }

        return true;
    }

    async function uploadFile(file) {
        if (!file || !validateFile(file)) {
            fileInput.value = '';
            return;
        }

        const formData = new FormData(uploadForm);
        formData.set('uploaded_file', file, file.name);
        setLoading(true);

        try {
            const response = await fetch(uploadForm.action, {
                method: 'POST',
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                body: formData
            });

            let data = {};
            try {
                data = await response.json();
            } catch {
                // An upstream proxy may return a non-JSON error page.
            }

            if (!response.ok) {
                throw new Error(
                    data.error || 'Не удалось загрузить документ.'
                );
            }

            if (!data.session_id) {
                throw new Error('Не удалось создать сессию обработки.');
            }

            window.umami?.track('document_uploaded');
            window.location.assign(
                processUrlTemplate.replace(
                    '__SESSION_ID__',
                    data.session_id
                )
            );
        } catch (error) {
            window.umami?.track('upload_failed', {
                reason: 'server'
            });
            fileInput.value = '';
            showError(error.message);
        }
    }

    function preventDragDefaults(event) {
        event.preventDefault();
        event.stopPropagation();
    }

    fileInput.addEventListener('change', event => {
        uploadFile(event.target.files[0]);
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadContainer.addEventListener(
            eventName,
            preventDragDefaults
        );
    });

    uploadContainer.addEventListener('dragover', () => {
        uploadContainer.classList.add('drag-over');
    });

    uploadContainer.addEventListener('dragleave', () => {
        uploadContainer.classList.remove('drag-over');
    });

    uploadContainer.addEventListener('drop', event => {
        uploadContainer.classList.remove('drag-over');
        uploadFile(event.dataTransfer.files[0]);
    });

    demoLink.addEventListener('click', () => {
        setLoading(true);
    });

    errorClose.addEventListener('click', () => {
        errorDialog.close();
    });

    window.addEventListener('pageshow', () => {
        setLoading(false);
    });
});
