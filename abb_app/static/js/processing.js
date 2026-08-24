const processingConfig = document.getElementById('processing-config');

const processingUrls = {
    update: processingConfig.dataset.updateUrl,
    difference: processingConfig.dataset.differenceUrl,
    export: processingConfig.dataset.exportUrl,
    preview: processingConfig.dataset.previewUrl,
    generate: processingConfig.dataset.generateUrl
};

const CONTEXT_LIMITS = [1, 3, 5, 10, Infinity];
const CONTEXT_WINDOWS = [25, 50, 75, 100, 150];

const globalSettingsPanel = document.getElementById(
    'global-settings-panel'
);
const globalSettingsButton = document.querySelector(
    '[data-processing-action="toggle-global-settings"]'
);

let tableCheckEnabled =
    processingConfig.dataset.compareWithExisting === 'true';
let pendingGeneration = null;
let workflowResize = null;
let previewRequestId = 0;
let comparisonRequestId = 0;

function getAbbreviationItem(abbreviation) {
    return Array.from(
        document.querySelectorAll('.abbreviation-item')
    ).find(item => item.dataset.abbreviation === abbreviation);
}

function contextDatasetKey(setting) {
    return setting === 'limit'
        ? 'contextLimitIndex'
        : 'contextWindowIndex';
}

function getGlobalContextIndex(setting) {
    return Number(document.querySelector(
        `[data-context-setting="${setting}"][data-context-scope="global"]`
    ).value);
}

function getEffectiveContextIndex(item, setting) {
    const key = contextDatasetKey(setting);
    return item.dataset[key] === undefined
        ? getGlobalContextIndex(setting)
        : Number(item.dataset[key]);
}

function getEffectiveContextLimit(item) {
    return CONTEXT_LIMITS[getEffectiveContextIndex(item, 'limit')];
}

function getEffectiveContextWindow(item) {
    return CONTEXT_WINDOWS[getEffectiveContextIndex(item, 'window')];
}

function trimContextText(context, abbreviation, windowSize) {
    const hasLeadingEllipsis = context.startsWith('...');
    const hasTrailingEllipsis = context.endsWith('...');
    const startOffset = hasLeadingEllipsis ? 3 : 0;
    const endOffset = hasTrailingEllipsis ? -3 : undefined;
    const core = context.slice(startOffset, endOffset).trim();
    const abbreviationIndex = core.indexOf(abbreviation);

    if (abbreviationIndex < 0) return context;

    const start = Math.max(0, abbreviationIndex - windowSize);
    const end = Math.min(
        core.length,
        abbreviationIndex + abbreviation.length + windowSize
    );
    const prefix = hasLeadingEllipsis || start > 0 ? '...' : '';
    const suffix = hasTrailingEllipsis || end < core.length ? '...' : '';

    return `${prefix}${core.slice(start, end).trim()}${suffix}`;
}

function applyContextSettings(item) {
    const limit = getEffectiveContextLimit(item);
    const windowSize = getEffectiveContextWindow(item);
    const abbreviation = item.dataset.abbreviation;

    item.querySelectorAll('.context-item').forEach((context, index) => {
        context.classList.toggle(
            'is-hidden',
            Number.isFinite(limit) && index >= limit
        );

        const text = context.querySelector('.context-text');
        if (!text.dataset.fullContext) {
            text.dataset.fullContext = text.textContent.trim();
        }
        text.textContent = trimContextText(
            text.dataset.fullContext,
            abbreviation,
            windowSize
        );
    });
}

function applyGlobalContextSetting(setting) {
    const globalRange = document.querySelector(
        `[data-context-setting="${setting}"][data-context-scope="global"]`
    );
    const key = contextDatasetKey(setting);

    document.querySelectorAll('.abbreviation-item').forEach(item => {
        if (item.dataset[key] === undefined) {
            item.querySelector(
                `[data-context-setting="${setting}"][data-context-scope="card"]`
            ).value = globalRange.value;
        }
        applyContextSettings(item);
    });
}

function setCardContextSetting(item, setting, index) {
    item.dataset[contextDatasetKey(setting)] = String(index);
    item.querySelector(
        `[data-context-setting="${setting}"][data-context-scope="card"]`
    ).value = String(index);
    item.querySelector('.card-settings-reset')
        .classList.remove('is-hidden');
    applyContextSettings(item);
}

function resetCardContextSettings(item) {
    delete item.dataset.contextLimitIndex;
    delete item.dataset.contextWindowIndex;

    for (const setting of ['limit', 'window']) {
        item.querySelector(
            `[data-context-setting="${setting}"][data-context-scope="card"]`
        ).value = String(getGlobalContextIndex(setting));
    }

    item.querySelector('.card-settings-reset').classList.add('is-hidden');
    applyContextSettings(item);
}

function closeCardSettings(except = null) {
    document.querySelectorAll('.card-context-settings').forEach(panel => {
        if (panel !== except) panel.classList.add('is-hidden');
    });
}

function toggleCardSettings(item) {
    const panel = item.querySelector('.card-context-settings');
    closeCardSettings(panel);
    panel.classList.toggle('is-hidden');
}

function setGlobalSettingsOpen(open) {
    globalSettingsPanel.classList.toggle('is-open', open);
    globalSettingsPanel.setAttribute('aria-hidden', String(!open));
    globalSettingsButton.setAttribute('aria-expanded', String(open));
}

function toggleGlobalSettings() {
    setGlobalSettingsOpen(
        !globalSettingsPanel.classList.contains('is-open')
    );
}

function chooseTableCheck(enabled) {
    tableCheckEnabled = enabled;
    const comparisonBlock = document.getElementById('comparison-block');

    if (comparisonBlock) {
        comparisonBlock.classList.toggle('is-hidden', !enabled);
    }

    document.getElementById('table-check-dialog').close();
}

async function updateDifferenceSection() {
    const section = document.getElementById('differences-section');
    if (!section) return;

    const requestId = ++comparisonRequestId;

    try {
        const response = await fetchWrapper(
            processingUrls.difference,
            getTableSettings()
        );
        if (!response.ok) {
            throw new Error(
                'Update difference section failed, wrong response'
            );
        }
        if (requestId === comparisonRequestId) {
            section.innerHTML = response.data;
        }
    } catch (error) {
        if (requestId === comparisonRequestId) {
            alert(`Failed to update difference section: ${error.message}`);
        }
    }
}

function refreshTableViews() {
    const updates = [updateTablePreview()];
    if (tableCheckEnabled) {
        updates.push(updateDifferenceSection());
    }
    return Promise.all(updates);
}

function getTableSettings() {
    return {
        sort_mode: document.querySelector(
            'input[name="table-sort-mode"]:checked'
        ).value,
        script_order: document.querySelector(
            'input[name="table-script-order"]:checked'
        ).value,
        use_correct_form: document.getElementById(
            'use-correct-form'
        ).checked,
        scope: document.querySelector(
            'input[name="table-scope"]:checked'
        )?.value || 'all'
    };
}

function renderAbbreviationText(cell, entry) {
    const parts = entry.highlighted;
    if (!Array.isArray(parts) || !parts.length) {
        cell.textContent = entry.abbreviation;
        return;
    }

    for (const part of parts) {
        const character = document.createElement('span');
        character.textContent = part.char;

        if (part.mismatch) {
            character.classList.add('tooltip', 'tooltip-right', 'red');
            if (part.tooltip) {
                const tooltip = document.createElement('span');
                tooltip.classList.add('tooltiptext');
                tooltip.textContent = part.tooltip;
                character.append(tooltip);
            }
        }
        cell.append(character);
    }
}

function renderTablePreview(entries) {
    const empty = document.getElementById('table-preview-empty');
    const wrapper = document.getElementById('table-preview-wrapper');
    const body = document.getElementById('table-preview-body');

    body.replaceChildren();
    if (!entries.length) {
        empty.classList.remove('is-hidden');
        wrapper.classList.add('is-hidden');
        return;
    }

    const rows = entries.map(entry => {
        const row = document.createElement('tr');
        const abbreviation = document.createElement('td');
        const description = document.createElement('td');
        renderAbbreviationText(abbreviation, entry);
        description.textContent = entry.description;
        row.append(abbreviation, description);
        return row;
    });

    body.append(...rows);
    empty.classList.add('is-hidden');
    wrapper.classList.remove('is-hidden');
}

async function updateTablePreview() {
    const requestId = ++previewRequestId;

    try {
        const response = await fetchWrapper(
            processingUrls.preview,
            getTableSettings()
        );
        if (!response.ok) {
            throw new Error(
                response.data?.error || 'Не удалось обновить таблицу'
            );
        }
        if (requestId === previewRequestId) {
            renderTablePreview(response.data.entries);
        }
    } catch (error) {
        if (requestId === previewRequestId) {
            const empty = document.getElementById('table-preview-empty');
            const wrapper = document.getElementById('table-preview-wrapper');
            empty.textContent = 'Не удалось обновить предварительный просмотр.';
            empty.classList.remove('is-hidden');
            wrapper.classList.add('is-hidden');
        }
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

        await refreshTableViews();
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

function setCardCollapseState(item, collapsed) {
    const content = item.querySelector('.abb-content');
    const toggleButton = item.querySelector('.toggle-btn');
    const toggleIcon = toggleButton.querySelector('.material-icons');
    const toggleTooltip = toggleButton.querySelector('.tooltiptext');
    const settingsButton = item.querySelector('.card-settings-btn');
    const settingsPanel = item.querySelector('.card-context-settings');
    const titleLeft = item.querySelector('.abb-title-left');

    content.style.display = collapsed ? 'none' : 'block';
    toggleIcon.textContent = collapsed ? 'expand_more' : 'expand_less';
    toggleTooltip.textContent = collapsed
        ? 'Развернуть карточку'
        : 'Свернуть карточку';
    toggleButton.setAttribute(
        'aria-label',
        collapsed ? 'Развернуть карточку' : 'Свернуть карточку'
    );
    settingsButton.classList.toggle('is-hidden', collapsed);
    if (collapsed) settingsPanel.classList.add('is-hidden');
    titleLeft.classList.toggle('moved', collapsed);
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
    const isCollapsed =
        window.getComputedStyle(content).display === 'none';

    setCardCollapseState(item, !isCollapsed || forceCollapse);
}

async function generateAbbreviationTable() {
    try {
        const response = await fetchWrapper(
            processingUrls.export,
            getTableSettings()
        );
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

function openGenerationConsent(button, item) {
    const allContexts = Array.from(item.querySelectorAll('.context-item'));
    if (!allContexts.length) {
        alert('Для этого сокращения нет контекста для генерации.');
        return;
    }

    const contextLimit = getEffectiveContextLimit(item);
    const contextWindow = getEffectiveContextWindow(item);
    const contexts = Number.isFinite(contextLimit)
        ? allContexts.slice(0, contextLimit)
        : allContexts;
    const dialog = document.getElementById('llm-consent-dialog');
    const contextContainer = document.getElementById(
        'llm-consent-contexts'
    );
    const abbreviation = item.dataset.abbreviation;

    document.getElementById(
        'llm-consent-abbreviation'
    ).textContent = abbreviation;
    contextContainer.replaceChildren(
        ...contexts.map(context => context.cloneNode(true))
    );

    pendingGeneration = {button, item, contextLimit, contextWindow};
    dialog.showModal();
}

function cancelGeneration() {
    pendingGeneration = null;
    document.getElementById('llm-consent-dialog').close();
}

async function confirmGeneration() {
    if (!pendingGeneration) return;

    const {button, item, contextLimit, contextWindow} = pendingGeneration;
    pendingGeneration = null;
    document.getElementById('llm-consent-dialog').close();
    await generateDescription(button, item, contextLimit, contextWindow);
}

async function generateDescription(
    button,
    item,
    contextLimit,
    contextWindow
) {
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
                confirmed: true,
                context_limit: Number.isFinite(contextLimit)
                    ? contextLimit
                    : 'all',
                context_chars: contextWindow
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

function startWorkflowResize(event, handle) {
    if (event.button !== 0) return;

    const body = handle.closest('.workflow-tool')
        .querySelector('.workflow-tool-body');
    const styles = window.getComputedStyle(body);

    workflowResize = {
        body,
        handle,
        pointerId: event.pointerId,
        startY: event.clientY,
        startHeight: body.getBoundingClientRect().height,
        minHeight: Number.parseFloat(styles.minHeight) || 0,
        maxHeight: Number.parseFloat(styles.maxHeight) || Infinity
    };

    body.style.height = `${workflowResize.startHeight}px`;
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add('is-resizing-workflow');
    event.preventDefault();
}

function resizeWorkflowPanel(event) {
    if (!workflowResize || event.pointerId !== workflowResize.pointerId) {
        return;
    }

    const height = Math.min(
        workflowResize.maxHeight,
        Math.max(
            workflowResize.minHeight,
            workflowResize.startHeight
                + event.clientY - workflowResize.startY
        )
    );
    workflowResize.body.style.height = `${height}px`;
}

function stopWorkflowResize(event) {
    if (!workflowResize || event.pointerId !== workflowResize.pointerId) {
        return;
    }

    if (workflowResize.handle.hasPointerCapture(event.pointerId)) {
        workflowResize.handle.releasePointerCapture(event.pointerId);
    }
    workflowResize = null;
    document.body.classList.remove('is-resizing-workflow');
}

document.addEventListener('click', event => {
    const control = event.target.closest('[data-processing-action]');
    const action = control?.dataset.processingAction;

    if (!event.target.closest('#global-settings-panel')
        && action !== 'toggle-global-settings') {
        setGlobalSettingsOpen(false);
    }

    if (!control) {
        if (!event.target.closest('.card-context-settings')) {
            closeCardSettings();
        }
        return;
    }

    const item = control.closest('.abbreviation-item');
    const abbreviation = item?.dataset.abbreviation;

    switch (action) {
        case 'toggle-global-settings':
            event.stopPropagation();
            closeCardSettings();
            toggleGlobalSettings();
            break;
        case 'table-check':
            chooseTableCheck(control.dataset.enabled === 'true');
            break;
        case 'toggle-abbreviation':
            toggleAbbreviationContent(abbreviation);
            break;
        case 'toggle-card-settings':
            event.stopPropagation();
            setGlobalSettingsOpen(false);
            toggleCardSettings(item);
            break;
        case 'reset-card-context':
            event.stopPropagation();
            resetCardContextSettings(item);
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

document.addEventListener('pointerdown', event => {
    const handle = event.target.closest('[data-workflow-resize]');
    if (handle) startWorkflowResize(event, handle);
});

document.addEventListener('pointermove', resizeWorkflowPanel);
document.addEventListener('pointerup', stopWorkflowResize);
document.addEventListener('pointercancel', stopWorkflowResize);

document.addEventListener('keydown', event => {
    if (event.key === 'Escape'
        && globalSettingsPanel.classList.contains('is-open')) {
        setGlobalSettingsOpen(false);
        globalSettingsButton.focus();
    }
});

document.addEventListener('input', event => {
    const range = event.target.closest('[data-context-setting]');
    if (!range) return;

    const setting = range.dataset.contextSetting;
    if (range.dataset.contextScope === 'global') {
        applyGlobalContextSetting(setting);
        return;
    }

    const item = range.closest('.abbreviation-item');
    setCardContextSetting(item, setting, Number(range.value));
});

document.addEventListener('change', event => {
    if (
        event.target.matches('input[name="table-sort-mode"]')
        || event.target.matches('input[name="table-script-order"]')
        || event.target.matches('input[name="table-scope"]')
        || event.target.id === 'use-correct-form'
    ) {
        refreshTableViews();
    }
});

function updateWorkflowToggle(details) {
    const control = details.querySelector('.workflow-toggle');
    if (!control) return;

    control.querySelector('.material-icons').textContent = details.open
        ? 'expand_less'
        : 'expand_more';
    control.querySelector('.tooltiptext').textContent = details.open
        ? 'Свернуть'
        : 'Развернуть';
}

document.addEventListener('DOMContentLoaded', () => {
    applyGlobalContextSetting('limit');
    applyGlobalContextSetting('window');
    updateTablePreview();

    document.querySelectorAll('.workflow-tool').forEach(details => {
        updateWorkflowToggle(details);
        details.addEventListener('toggle', () => {
            updateWorkflowToggle(details);
        });
    });

    const consentDialog = document.getElementById('llm-consent-dialog');
    consentDialog.addEventListener('cancel', () => {
        pendingGeneration = null;
    });

    const comparisonBlock = document.getElementById('comparison-block');
    if (tableCheckEnabled && comparisonBlock) {
        comparisonBlock.classList.remove('is-hidden');
    }

    const tableDialog = document.getElementById('table-check-dialog');
    if (!tableDialog) return;

    tableDialog.addEventListener('cancel', event => {
        event.preventDefault();
    });
    tableDialog.showModal();
});
