document.addEventListener('DOMContentLoaded', () => {
    const introDialog = document.getElementById('demo-intro-dialog');
    const startButton = document.getElementById('demoStartButton');
    const popover = document.getElementById('demo-popover');
    const title = document.getElementById('demoPopoverTitle');
    const body = document.getElementById('demoPopoverBody');
    const counter = document.getElementById('demoStepCounter');
    const nextButton = popover.querySelector('.demo-next-button');
    const comparisonBlock = document.getElementById('comparison-block');
    const firstCard = document.querySelector('.abbreviation-item');
    const atxAbbreviation = document.querySelector(
        '[data-abbreviation="AT\u0425"] .abb-description h4'
    );
    const steps = Array.from(document.querySelectorAll('[data-demo-step]'));
    const stepByName = Object.fromEntries(
        steps.map(step => [step.dataset.demoStep, step])
    );

    const defaultNextLabel = nextButton.textContent;
    let target = null;
    let clickTarget = null;
    let clickHandler = null;
    let placement = 'auto';

    function clearTarget() {
        if (target) {
            target.classList.remove('demo-tour-target');
        }

        if (clickTarget && clickHandler) {
            clickTarget.removeEventListener('click', clickHandler);
        }

        target = null;
        clickTarget = null;
        clickHandler = null;
    }

    function finishTour() {
        clearTarget();
        popover.classList.add('is-hidden');
    }

    function positionPopover() {
        if (!target || popover.classList.contains('is-hidden')) return;

        const rect = target.getBoundingClientRect();
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

    function setStepContent(step) {
        const stepTitle = step.querySelector('h4');
        const stepBody = step.querySelector('.demo-step-body');
        const stepNumber = steps.indexOf(step) + 1;

        title.textContent = stepTitle.textContent;
        counter.textContent = `${stepNumber} / ${steps.length}`;
        body.replaceChildren(
            ...Array.from(stepBody.childNodes, node => node.cloneNode(true))
        );
        nextButton.textContent =
            step.dataset.nextLabel || defaultNextLabel;
    }

    function showStep(
        name,
        stepTarget,
        {onNext = finishTour, stepPlacement = 'auto',
         advanceOnTargetClick = false} = {}
    ) {
        clearTarget();

        target = stepTarget;
        placement = stepPlacement;
        setStepContent(stepByName[name]);
        nextButton.onclick = onNext;

        target.classList.add('demo-tour-target');
        popover.classList.remove('is-hidden');
        target.scrollIntoView({behavior: 'smooth', block: 'center'});
        window.setTimeout(positionPopover, 250);

        if (advanceOnTargetClick) {
            clickTarget = target;
            clickHandler = () => window.setTimeout(onNext, 150);
            target.addEventListener('click', clickHandler, {once: true});
        }
    }

    function showComparisonStep() {
        showStep('comparison', comparisonBlock);
    }

    function showMixedAlphabetStep() {
        showStep('mixed-alphabet', atxAbbreviation, {
            stepPlacement: 'right',
            onNext: showComparisonStep
        });
    }

    function showDescriptionStep() {
        showStep(
            'description',
            firstCard.querySelector('.btn-select-option'),
            {
                advanceOnTargetClick: true,
                onNext: showMixedAlphabetStep
            }
        );
    }

    function showContextStep() {
        showStep('context', firstCard.querySelector('.context-item'), {
            onNext: showDescriptionStep
        });
    }

    function showAbbreviationStep() {
        showStep('abbreviation', firstCard, {
            onNext: showContextStep
        });
    }

    window.addEventListener('resize', positionPopover);
    window.addEventListener('scroll', positionPopover, {passive: true});

    introDialog.addEventListener(
        'cancel',
        event => event.preventDefault()
    );

    startButton.addEventListener('click', () => {
        introDialog.close();
        comparisonBlock.classList.remove('is-hidden');
        showAbbreviationStep();
    });

    introDialog.showModal();
});
