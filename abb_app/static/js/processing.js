const processingConfig = document.getElementById('processing-config');

const processingUrls = {
    update: processingConfig.dataset.updateUrl,
    difference: processingConfig.dataset.differenceUrl,
    export: processingConfig.dataset.exportUrl,
    generate: processingConfig.dataset.generateUrl
};

let compareWithExisting =
    processingConfig.dataset.compareWithExisting === 'true';

function getAbbreviationItem(abbreviation) {
    return Array.from(
        document.querySelectorAll('.abbreviation-item')
    ).find(item => item.dataset.abbreviation === abbreviation);
}

function chooseTableCheck(enabled) {
    compareWithExisting = enabled;

    if (enabled) {
        document.getElementById('comparison-block')
            .classList.remove('is-hidden');
    }

    document.getElementById('table-check-dialog').close();
}

async function updateDifferenceSection() {
    const section = document.getElementById('differences-section');
    if (!section) return;

    try {
        const response = await fetchWrapper(processingUrls.difference);
        if (!response.ok) {
            throw new Error(
                'Update difference section failed, wrong response'
            );
        }
        section.innerHTML = response.data;
    } catch (error) {
        alert(`Failed to update difference section: ${error.message}`);
    }
}

async function fetchWrapper(url, data = null) {
    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        const contentType = response.headers.get('content-type');

        let responseData;
        if (contentType?.includes('application/json')) {
            responseData = await response.json();
        } else if (contentType?.includes(
            'application/vnd.openxmlformats-officedocument.'
            + 'wordprocessingml.document'
        )) {
            responseData = await response.blob();
        } else {
            responseData = await response.text();
        }

        return {
            ok: response.ok,
            status: response.status,
            data: responseData,
            contentType
        };
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

async function handleAbbreviation(
    abbreviation,
    description = null,
    action
) {
    const item = getAbbreviationItem(abbreviation);
    if (!item) {
        throw new Error(`Abbreviation card not found: ${abbreviation}`);
    }

    if (action === 'add' && !description) {
        description = item.querySelector('input[type="text"]')
            .value.trim();
        if (!description) return;
    }

    try {
        const response = await fetchWrapper(processingUrls.update, {
            abbreviation,
            description,
            action
        });

        if (!response.ok) {
            throw new Error(
                response.data?.error || 'Failed to update abbreviation'
            );
        }

        updateAbbreviationUI(item, description, action);
        toggleAbbreviationContent(abbreviation, true);

        if (compareWithExisting) {
            await updateDifferenceSection();
        }
    } catch (error) {
        alert(`Failed to handle abbreviation: ${error.message}`);
    }
}

function updateAbbreviationUI(item, description, action) {
    const descriptionText = item.querySelector('.description-text');
    const statusIcon = item.querySelector('.status-icon');
    const addButton = item.querySelector('.btn-success');

    if (action === 'skip') {
        descriptionText.textContent = '- (убрано)';
        statusIcon.textContent = '✗';
    } else {
        descriptionText.textContent = `- ${description}`;
        statusIcon.textContent = '✓';
    }

    addButton.textContent = '✓';
}

function toggleAbbreviationContent(
    abbreviation,
    forceCollapse = false
) {
    const item = getAbbreviationItem(abbreviation);
    if (!item) {
        throw new Error(`Abbreviation card not found: ${abbreviation}`);
    }

    const content = item.querySelector('.abb-content');
    const toggleButton = item.querySelector('.toggle-btn');
    const titleLeft = item.querySelector('.abb-title-left');
    const isCollapsed =
        window.getComputedStyle(content).display === 'none';

    if (isCollapsed && !forceCollapse) {
        content.style.display = 'block';
        toggleButton.textContent = '▼';
        titleLeft.classList.remove('moved');
        return;
    }

    content.style.display = 'none';
    toggleButton.textContent = '▶';
    titleLeft.classList.add('moved');
}

async function generateAbbreviationTable() {
    try {
        const response = await fetchWrapper(processingUrls.export);
        if (!response.ok) {
            throw new Error(
                response.data?.error || 'Неизвестная ошибка'
            );
        }

        const url = window.URL.createObjectURL(response.data);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'abbreviation_table.docx';
        document.body.appendChild(link);
        link.click();
        window.umami?.track('table_exported');
        window.URL.revokeObjectURL(url);
        link.remove();
    } catch (error) {
        alert(`Не удалось сгенерировать таблицу: ${error.message}`);
    }
}

let pendingGeneration = null;

function openGenerationConsent(button, item) {
    const contexts = item.querySelectorAll('.context-item');
    if (!contexts.length) {
        alert('Для этого сокращения нет контекста для генерации.');
        return;
    }

    const dialog = document.getElementById('llm-consent-dialog');
    const contextContainer = document.getElementById(
        'llm-consent-contexts'
    );
    const abbreviation = item.dataset.abbreviation;

    document.getElementById(
        'llm-consent-abbreviation'
    ).textContent = abbreviation;
    contextContainer.replaceChildren(
        ...Array.from(contexts, context => context.cloneNode(true))
    );

    pendingGeneration = {button, item};
    dialog.showModal();
}

function cancelGeneration() {
    pendingGeneration = null;
    document.getElementById('llm-consent-dialog').close();
}

async function confirmGeneration() {
    if (!pendingGeneration) return;

    const {button, item} = pendingGeneration;
    pendingGeneration = null;
    document.getElementById('llm-consent-dialog').close();
    await generateDescription(button, item);
}

async function generateDescription(button, item) {
    const abbreviation = item.dataset.abbreviation;
    const input = item.querySelector('input[type="text"]');
    const icon = button.querySelector('.magic-wand-icon');

    try {
        button.disabled = true;
        icon.textContent = 'hourglass_empty';

        const response = await fetch(processingUrls.generate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                abbreviation,
                confirmed: true
            })
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(
                data.error || 'Failed to generate description'
            );
        }

        input.value = data.description;
        input.focus();
        window.umami?.track('llm_generated');
    } catch (error) {
        console.error('Description generation failed:', error);
        window.umami?.track('llm_failed');
        alert(
            'Не удалось сгенерировать расшифровку: '
            + error.message
        );
    } finally {
        button.disabled = false;
        icon.textContent = 'auto_fix_high';
    }
}

document.addEventListener('click', event => {
    const control = event.target.closest('[data-processing-action]');
    if (!control) return;

    const action = control.dataset.processingAction;
    const item = control.closest('.abbreviation-item');
    const abbreviation = item?.dataset.abbreviation;

    switch (action) {
        case 'table-check':
            chooseTableCheck(control.dataset.enabled === 'true');
            break;
        case 'toggle-abbreviation':
            toggleAbbreviationContent(abbreviation);
            break;
        case 'select-description':
            handleAbbreviation(
                abbreviation,
                control.dataset.description,
                'add'
            );
            break;
        case 'add-description':
            handleAbbreviation(abbreviation, null, 'add');
            break;
        case 'skip-abbreviation':
            handleAbbreviation(abbreviation, null, 'skip');
            break;
        case 'generate-description':
            event.stopPropagation();
            openGenerationConsent(control, item);
            break;
        case 'cancel-generation':
            cancelGeneration();
            break;
        case 'confirm-generation':
            confirmGeneration();
            break;
        case 'export-table':
            event.preventDefault();
            generateAbbreviationTable();
            break;
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const consentDialog = document.getElementById('llm-consent-dialog');
    consentDialog.addEventListener('cancel', () => {
        pendingGeneration = null;
    });

    const tableDialog = document.getElementById('table-check-dialog');
    if (!tableDialog) return;

    tableDialog.addEventListener('cancel', event => {
        event.preventDefault();
    });
    tableDialog.showModal();
});
