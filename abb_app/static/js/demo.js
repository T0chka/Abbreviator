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
        '[data-abbreviation="ATХ"]'
    );
    const atxAbbreviation = atxCard.querySelector('.abb-description h4');

    const stepContent = Object.fromEntries(
        Array.from(document.querySelectorAll('[data-demo-step]'))
            .map(step => [step.dataset.demoStep, step])
    );

    const blocker = document.createElement('div');
    blocker.className = 'demo-tour-blocker is-hidden';

    const highlight = document.createElement('div');
    highlight.className = 'demo-tour-highlight is-hidden';

    document.body.append(blocker, highlight);

    const HIGHLIGHT_PADDING = 6;
    const defaultNextLabel = nextButton.textContent;

    const tourSteps = [
        {
            name: 'abbreviation',
            targets: () => firstCard,
            scroll: false
        },
        {
            name: 'context',
            expand: firstCard,
            targets: () => firstCard.querySelectorAll(
                '.context-item:not(.is-hidden)'
            )
        },
        {
            name: 'description',
            expand: firstCard,
            targets: () => firstCard.querySelectorAll('.btn-select-option')
        },
        {
            name: 'ai-generation',
            expand: firstCard,
            targets: () => firstCard.querySelector(
                '[data-processing-action="generate-description"]'
            )
        },
        {
            name: 'mixed-alphabet',
            expand: atxCard,
            targets: () => atxAbbreviation,
            placement: 'right'
        },
        {
            name: 'comparison',
            prepare: () => {
                comparisonBlock.classList.remove('is-hidden');
                comparisonBlock.open = true;
            },
            targets: () => comparisonBlock
        }
    ];

    let currentStep = -1;
    let targets = [];
    let placement = 'auto';
    let animationFrame = null;

    function expandCard(card) {
        const content = card.querySelector('.abb-content');
        if (getComputedStyle(content).display === 'none') {
            toggleAbbreviationContent(card.dataset.abbreviation);
        }
    }

    function highlightRect() {
        const rects = targets.map(
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

    function positionTour() {
        if (!targets.length) return;

        const rect = highlightRect();
        highlight.style.left = `${rect.left}px`;
        highlight.style.top = `${rect.top}px`;
        highlight.style.width = `${rect.width}px`;
        highlight.style.height = `${rect.height}px`;

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

    function schedulePosition() {
        cancelAnimationFrame(animationFrame);
        animationFrame = requestAnimationFrame(positionTour);
    }

    function renderStep(step) {
        const content = stepContent[step.name];
        const stepTitle = content.querySelector('h4');
        const stepBody = content.querySelector('.demo-step-body');

        title.textContent = stepTitle.textContent;
        counter.textContent = `${currentStep + 1} / ${tourSteps.length}`;
        body.replaceChildren(
            ...Array.from(
                stepBody.childNodes,
                node => node.cloneNode(true)
            )
        );
        nextButton.textContent =
            content.dataset.nextLabel || defaultNextLabel;

        const stepTargets = step.targets();
        targets = stepTargets instanceof Element
            ? [stepTargets]
            : Array.from(stepTargets);
        placement = step.placement || 'auto';

        blocker.classList.remove('is-hidden');
        highlight.classList.remove('is-hidden');
        popover.classList.remove('is-hidden');

        if (step.scroll !== false) {
            targets[0].scrollIntoView({block: 'center'});
        }

        schedulePosition();
        nextButton.disabled = false;
        nextButton.focus();
    }

    function showStep(index) {
        if (index >= tourSteps.length) {
            finishTour();
            return;
        }

        currentStep = index;
        const step = tourSteps[currentStep];

        if (step.expand) {
            expandCard(step.expand);
        }
        step.prepare?.();

        requestAnimationFrame(() => renderStep(step));
    }

    function finishTour() {
        currentStep = -1;
        targets = [];
        blocker.classList.add('is-hidden');
        highlight.classList.add('is-hidden');
        popover.classList.add('is-hidden');

        window.removeEventListener('resize', schedulePosition);
        window.removeEventListener('scroll', schedulePosition);
    }

    nextButton.addEventListener('click', () => {
        if (nextButton.disabled) return;

        nextButton.disabled = true;
        showStep(currentStep + 1);
    });

    introDialog.addEventListener(
        'cancel',
        event => event.preventDefault()
    );

    startButton.addEventListener('click', () => {
        introDialog.close();
        comparisonBlock.classList.remove('is-hidden');
        comparisonBlock.open = false;

        window.addEventListener('resize', schedulePosition);
        window.addEventListener('scroll', schedulePosition, {
            passive: true
        });

        showStep(0);
    });

    introDialog.showModal();

    const backdropColor = getComputedStyle(
        introDialog,
        '::backdrop'
    ).backgroundColor;
    highlight.style.setProperty(
        '--demo-backdrop-color',
        backdropColor
    );
});
