document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);

    if (params.get('expired') === '1') {
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

    function formatMb(bytes) {
        return new Intl.NumberFormat('ru-RU', {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1
        }).format(bytes / (1024 * 1024));
    }

    function showError(message) {
        loadingOverlay.classList.add('is-hidden');
        errorMessage.textContent = message;

        if (typeof errorDialog.showModal === 'function') {
            errorDialog.showModal();
        } else {
            alert(message);
        }
    }

    function validateFile(file) {
        if (!file.name.toLowerCase().endsWith('.docx')) {
            showError('Можно загрузить только файл формата .docx.');
            return false;
        }

        if (file.size > maxUploadSize) {
            showError(
                `Файл слишком большой: ${formatMb(file.size)} МБ. ` +
                `Максимальный размер: ${maxUploadSizeMb} МБ.`
            );
            return false;
        }

        return true;
    }

    function processUrl(sessionId) {
        return processUrlTemplate.replace('__SESSION_ID__', sessionId);
    }

    async function uploadFile(file) {
        if (!file || !validateFile(file)) {
            fileInput.value = '';
            return;
        }

        const formData = new FormData(uploadForm);
        formData.set('uploaded_file', file, file.name);
        loadingOverlay.classList.remove('is-hidden');

        try {
            const response = await fetch(uploadForm.action, {
                method: 'POST',
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                body: formData
            });

            let data = {};
            try {
                data = await response.json();
            } catch (_) {
                // nginx or another upstream may return a non-JSON error page.
            }

            if (!response.ok) {
                throw new Error(
                    data.error || 'Не удалось загрузить документ.'
                );
            }

            if (!data.session_id) {
                throw new Error('Не удалось создать сессию обработки.');
            }

            window.location.assign(processUrl(data.session_id));
        } catch (error) {
            fileInput.value = '';
            showError(error.message);
        }
    }

    fileInput.addEventListener('change', event => {
        uploadFile(event.target.files[0]);
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadContainer.addEventListener(eventName, event => {
            event.preventDefault();
            event.stopPropagation();
        });
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
        loadingOverlay.classList.remove('is-hidden');
    });

    errorClose.addEventListener('click', () => {
        errorDialog.close();
    });
});
