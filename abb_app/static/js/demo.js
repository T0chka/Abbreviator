document.addEventListener('DOMContentLoaded', () => {
    const introDialog = document.getElementById('demo-intro-dialog');
    const startButton = document.getElementById('demoStartButton');
    const popover = document.getElementById('demo-popover');
    const title = document.getElementById('demoPopoverTitle');
    const body = document.getElementById('demoPopoverBody');
    const counter = document.getElementById('demoStepCounter');
    const nextButton = popover.querySelector('.demo-next-button');
    const comparisonBlock = document.getElementById('comparison-block');
    const abbreviationList = document.querySelector('.abbreviation-list');
    const firstCard = abbreviationList.querySelector('.abbreviation-item');
    const atxCard = abbreviationList.querySelector(
        '[data-abbreviation="AT\u0425"]'
    );
    const atxAbbreviation = atxCard.querySelector('.abb-description h4');

    const steps = Array.from(document.querySelectorAll('[data-demo-step]'));
    const stepByName = Object.fromEntries(
        steps.map(step => [step.dataset.demoStep, step])
    );

    const highlight = document.createElement('div');
    const HIGHLIGHT_PADDING = 6;
    highlight.className = 'demo-tour-highlight is-hidden';
    document.body.appendChild(highlight);

    const defaultNextLabel = nextButton.textContent;

    let activeStep = null;
    let target = null;
    let highlightTargets = [];
    let placement = 'auto';
    let directHighlightTarget = null;
    let animationFrame = null;
    let nextAction = null;
    let nextLockedUntil = 0;

    function isCollapsed(card) {
        const content = card.querySelector('.abb-content');
        return getComputedStyle(content).display === 'none';
    }

    function expandCard(card) {
        if (isCollapsed(card)) {
            toggleAbbreviationContent(card.dataset.abbreviation);
        }
    }

    function clearStep() {
        if (directHighlightTarget) {
            directHighlightTarget.classList.remove('demo-tour-target');
        }
    
        directHighlightTarget = null;
        activeStep = null;
        nextAction = null;
        target = null;
        highlightTargets = [];
        highlight.classList.add('is-hidden');
        popover.classList.add('is-hidden');
    }

    function finishTour() {
        clearStep();
        layoutObserver.disconnect();
    }

    function getHighlightRect() {
        const rects = highlightTargets.map(
            element => element.getBoundingClientRect()
        );
    
        const left = Math.min(...rects.map(rect => rect.left)) -
            HIGHLIGHT_PADDING;
        const top = Math.min(...rects.map(rect => rect.top)) -
            HIGHLIGHT_PADDING;
        const right = Math.max(...rects.map(rect => rect.right)) +
            HIGHLIGHT_PADDING;
        const bottom = Math.max(...rects.map(rect => rect.bottom)) +
            HIGHLIGHT_PADDING;
    
        return {
            left,
            top,
            right,
            bottom,
            width: right - left,
            height: bottom - top
        };
    }

    function positionHighlight() {
        if (highlightTargets.length === 1) {
            return;
        }
    
        const rect = getHighlightRect();
    
        highlight.style.left = `${rect.left}px`;
        highlight.style.top = `${rect.top}px`;
        highlight.style.width = `${rect.width}px`;
        highlight.style.height = `${rect.height}px`;
    }

    function positionPopover() {
        const rect = getHighlightRect();
        const margin = 16;
        const gap = 12;
        const width = popover.offsetWidth;
        const height = popover.offsetHeight;

        if (placement === 'right') {
            popover.style.left = `${rect.right + gap}px`;
            popover.style.top = `${rect.top}px`;
            return;
        }

        const left = Math.max(
            margin,
            Math.min(rect.left, window.innerWidth - width - margin)
        );

        let top = rect.bottom + gap;
        if (top + height > window.innerHeight - margin) {
            top = rect.top - height - gap;
        }

        popover.style.left = `${left}px`;
        popover.style.top = `${Math.max(margin, top)}px`;
    }

    function refreshGeometry() {
        if (!target || popover.classList.contains('is-hidden')) return;

        positionHighlight();
        positionPopover();
    }

    function scheduleGeometryRefresh() {
        cancelAnimationFrame(animationFrame);
        animationFrame = requestAnimationFrame(refreshGeometry);
    }

    function setStepContent(step) {
        const stepTitle = step.querySelector('h4');
        const stepBody = step.querySelector('.demo-step-body');
        const stepNumber = steps.indexOf(step) + 1;

        title.textContent = stepTitle.textContent;
        counter.textContent = `${stepNumber} / ${steps.length}`;

        body.replaceChildren(
            ...Array.from(
                stepBody.childNodes,
                node => node.cloneNode(true)
            )
        );

        nextButton.textContent =
            step.dataset.nextLabel || defaultNextLabel;
    }

    function showStep(
        name,
        stepTarget,
        {
            onNext = finishTour,
            stepPlacement = 'auto',
            stepHighlights = [stepTarget],
            scrollTarget = true
        } = {}
    ) {
        clearStep();

        activeStep = name;
        target = stepTarget;
        highlightTargets = stepHighlights;
        placement = stepPlacement;

        setStepContent(stepByName[name]);
        nextAction = onNext;
        nextLockedUntil = performance.now() + 250;

        if (highlightTargets.length === 1) {
            directHighlightTarget = highlightTargets[0];
            directHighlightTarget.classList.add('demo-tour-target');
            highlight.classList.add('is-hidden');
        } else {
            positionHighlight();
            highlight.classList.remove('is-hidden');
        }
        
        popover.classList.remove('is-hidden');

        if (scrollTarget) {
            target.scrollIntoView({block: 'center'});
        }

        scheduleGeometryRefresh();
    }

    function showComparisonStep() {
        showStep('comparison', comparisonBlock);
    }

    function showMixedAlphabetStep() {
        expandCard(atxCard);

        requestAnimationFrame(() => {
            showStep('mixed-alphabet', atxAbbreviation, {
                stepPlacement: 'right',
                onNext: showComparisonStep
            });
        });
    }

    function showAIGenerationStep() {
        expandCard(firstCard);

        requestAnimationFrame(() => {
            const generateButton = firstCard.querySelector(
                '[data-processing-action="generate-description"]'
            );

            showStep('ai-generation', generateButton, {
                onNext: showMixedAlphabetStep
            });
        });
    }

    function showDescriptionStep() {
        expandCard(firstCard);

        requestAnimationFrame(() => {
            const descriptions = Array.from(
                firstCard.querySelectorAll('.btn-select-option')
            );

            showStep('description', descriptions[0], {
                stepHighlights: descriptions,
                onNext: showAIGenerationStep
            });
        });
    }

    function showContextStep() {
        expandCard(firstCard);

        requestAnimationFrame(() => {
            const contexts = Array.from(
                firstCard.querySelectorAll('.context-item')
            );

            showStep('context', contexts[0], {
                stepHighlights: contexts,
                onNext: showDescriptionStep
            });
        });
    }

    function showAbbreviationStep() {
        showStep('abbreviation', firstCard, {
            scrollTarget: false,
            onNext: showContextStep
        });
    }

    function handleLayoutChange() {
        scheduleGeometryRefresh();
    }

    function handleNextClick(event) {
        event.preventDefault();
        event.stopPropagation();

        if (!nextAction || performance.now() < nextLockedUntil) {
            return;
        }

        const action = nextAction;
        nextAction = null;
        action();
    }

    const layoutObserver = new MutationObserver(handleLayoutChange);

    layoutObserver.observe(abbreviationList, {
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'style']
    });
    
    layoutObserver.observe(comparisonBlock, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: ['class', 'style']
    });

    window.addEventListener('resize', scheduleGeometryRefresh);
    window.addEventListener('scroll', scheduleGeometryRefresh, {
        passive: true
    });

    abbreviationList.addEventListener(
        'transitionend',
        scheduleGeometryRefresh
    );

    introDialog.addEventListener(
        'cancel',
        event => event.preventDefault()
    );

    nextButton.addEventListener('click', handleNextClick);

    startButton.addEventListener('click', () => {
        introDialog.close();
        comparisonBlock.classList.remove('is-hidden');
        showAbbreviationStep();
    });

    introDialog.showModal();
});