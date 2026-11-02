/**
 * tour.js — Interactive Onboarding & Guided Spotlight Tour for Paleo Earth
 *
 * Provides:
 *  1. Welcome Modal on first visit with "Take 1-Minute Tour" or "Explore on My Own".
 *  2. Spotlight Guided Tour highlighting 4 key UI elements across the app.
 *  3. Preserves full live interactivity (dragging the globe, scrubbing the slider,
 *     toggling period/event buttons, and switching tabs) without closing the tour.
 *  4. Re-triggerable via Settings modal or the Tour button in viewport controls.
 *  5. Full keyboard navigation (Escape, ArrowLeft, ArrowRight) and mobile responsiveness.
 */

const TOUR_STORAGE_KEY = 'paleo_earth_tour_seen';

export class TourGuide {
  constructor() {
    this.currentStep = 0;
    this.isActive = false;
    this.steps = [
      {
        id: 'globe',
        selector: '#globeContainer',
        title: 'The 3D Paleoglobe',
        content: 'Click and drag anywhere to rotate Earth across 540 million years. Scroll or pinch to zoom. Use the top-right overlay buttons to toggle political borders, ancient continents, or climate atmosphere gauges.',
        placement: 'inside-top-left',
        targetPadding: 6
      },
      {
        id: 'timeline',
        selector: '.slider-section',
        title: 'Timeline & GTS Ribbon',
        content: 'Drag the timeline scrubber to travel continuously from 540 Ma (Cambrian) to Present Day. You can also click directly on any colored period block on the Geologic Time Scale ribbon to jump through time instantly.',
        placement: 'top',
        targetPadding: 8
      },
      {
        id: 'periods-events',
        selector: '#panelRight .panel-topbar, #summaryCard',
        title: 'Periods and Events',
        content: 'As you scrub, the timeline snaps to geologic periods and major milestones—including evolutionary radiations, climate transitions, and extinction events. The header badge and summary update dynamically to reflect the active era.',
        placement: 'left',
        targetPadding: 8
      },
      {
        id: 'wiki-chat',
        selector: '.panel-tabs, .panel-tab-content',
        title: 'Encyclopedia & AI Assistant',
        content: 'Dive into detailed period summaries and encyclopedia entries. Click the speaker icon to hear audio narration, or switch to the "Ask Questions" tab to chat with our AI assistant anchored to the active time period.',
        placement: 'left',
        targetPadding: 8
      }
    ];

    this._boundOnResize = this._onWindowResize.bind(this);
    this._boundOnKeyDown = this._onKeyDown.bind(this);

    this._createTourElements();
    this._bindWelcomeModal();
  }

  /** Initialize tour: check first-time visitor status and show welcome modal */
  init() {
    const tourSeen = localStorage.getItem(TOUR_STORAGE_KEY) === 'true';
    if (!tourSeen) {
      // Delay slightly so initial textures and globe rendering settle
      setTimeout(() => {
        this.showWelcomeModal();
      }, 700);
    }
  }

  /** Build DOM elements for the spotlight and floating popover */
  _createTourElements() {
    // 1. Spotlight Box (pointer-events: none so clicks pass through to live app controls)
    this.spotlight = document.createElement('div');
    this.spotlight.className = 'tour-spotlight-box';
    this.spotlight.id = 'tourSpotlightBox';
    this.spotlight.setAttribute('aria-hidden', 'true');
    document.body.appendChild(this.spotlight);

    // 2. Floating Popover Card
    this.popover = document.createElement('div');
    this.popover.className = 'tour-popover';
    this.popover.id = 'tourPopover';
    this.popover.setAttribute('role', 'dialog');
    this.popover.setAttribute('aria-modal', 'true');
    this.popover.setAttribute('aria-label', 'Guided Tour');

    this.popover.innerHTML = `
      <div class="tour-popover-header">
        <div class="tour-step-badge" id="tourStepBadge">Step 1 of 4</div>
        <button class="tour-close-btn" id="tourCloseBtn" title="Close tour (Esc)" aria-label="Close tour">&times;</button>
      </div>
      <div class="tour-popover-body">
        <h3 class="tour-popover-title" id="tourPopoverTitle">Title</h3>
        <p class="tour-popover-desc" id="tourPopoverDesc">Description</p>
      </div>
      <div class="tour-popover-footer">
        <button class="tour-btn tour-btn-text" id="tourSkipBtn">Skip Tour</button>
        <div class="tour-nav-group">
          <button class="tour-btn tour-btn-secondary" id="tourPrevBtn">Back</button>
          <button class="tour-btn tour-btn-primary" id="tourNextBtn">Next</button>
        </div>
      </div>
      <div class="tour-dots" id="tourDots"></div>
    `;
    document.body.appendChild(this.popover);

    // Wire popover controls
    const closeBtn = this.popover.querySelector('#tourCloseBtn');
    const skipBtn = this.popover.querySelector('#tourSkipBtn');
    const prevBtn = this.popover.querySelector('#tourPrevBtn');
    const nextBtn = this.popover.querySelector('#tourNextBtn');

    if (closeBtn) closeBtn.addEventListener('click', () => this.stop());
    if (skipBtn) skipBtn.addEventListener('click', () => this.stop());
    if (prevBtn) prevBtn.addEventListener('click', () => this.prevStep());
    if (nextBtn) nextBtn.addEventListener('click', () => this.nextStep());

    // Listen to tab buttons to smoothly adjust bounds when tabs switch
    const tabs = document.querySelectorAll('.panel-tab-btn');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        if (this.isActive) {
          setTimeout(() => this._renderStep(), 60);
        }
      });
    });
  }

  /** Setup Welcome Modal events and actions */
  _bindWelcomeModal() {
    const welcomeModal = document.getElementById('welcomeModal');
    const closeBtn = document.getElementById('closeWelcomeBtn');
    const exploreBtn = document.getElementById('welcomeExploreBtn');
    const startTourBtn = document.getElementById('welcomeStartTourBtn');
    const dontShowCheckbox = document.getElementById('welcomeDontShowAgain');

    const handleDismiss = () => {
      if (dontShowCheckbox && dontShowCheckbox.checked) {
        localStorage.setItem(TOUR_STORAGE_KEY, 'true');
      }
      if (welcomeModal) welcomeModal.classList.remove('active');
    };

    if (closeBtn) {
      closeBtn.addEventListener('click', handleDismiss);
    }

    if (exploreBtn) {
      exploreBtn.addEventListener('click', handleDismiss);
    }

    if (startTourBtn) {
      startTourBtn.addEventListener('click', () => {
        handleDismiss();
        // Brief transition delay before starting tour
        setTimeout(() => {
          this.start();
        }, 250);
      });
    }

    if (welcomeModal) {
      welcomeModal.addEventListener('click', (e) => {
        if (e.target === welcomeModal) handleDismiss();
      });
    }
  }

  /** Display the Welcome Modal */
  showWelcomeModal() {
    const welcomeModal = document.getElementById('welcomeModal');
    if (welcomeModal) {
      welcomeModal.classList.add('active');
    }
  }

  /** Start the Guided Tour */
  start() {
    this.isActive = true;
    this.currentStep = 0;

    // Show tour DOM elements
    this.spotlight.classList.add('active');
    this.popover.classList.add('active');

    // Add listeners (recalculate positions on resize or slider interaction)
    window.addEventListener('resize', this._boundOnResize);
    window.addEventListener('input', this._boundOnResize);
    window.addEventListener('keydown', this._boundOnKeyDown);

    // Build dots
    this._renderDots();

    // Render first step
    this._renderStep();
  }

  /** Stop/Complete the Guided Tour */
  stop() {
    if (!this.isActive) return;
    this.isActive = false;

    // Mark as seen
    localStorage.setItem(TOUR_STORAGE_KEY, 'true');

    // Hide tour elements
    this.spotlight.classList.remove('active');
    this.popover.classList.remove('active');

    window.removeEventListener('resize', this._boundOnResize);
    window.removeEventListener('input', this._boundOnResize);
    window.removeEventListener('keydown', this._boundOnKeyDown);
  }

  /** Advance to next step or complete */
  nextStep() {
    if (this.currentStep < this.steps.length - 1) {
      this.currentStep++;
      this._renderStep();
    } else {
      this.stop();
    }
  }

  /** Go back to previous step */
  prevStep() {
    if (this.currentStep > 0) {
      this.currentStep--;
      this._renderStep();
    }
  }

  /** Render progress dots inside popover */
  _renderDots() {
    const dotsContainer = this.popover.querySelector('#tourDots');
    if (!dotsContainer) return;
    dotsContainer.innerHTML = '';
    for (let i = 0; i < this.steps.length; i++) {
      const dot = document.createElement('span');
      dot.className = `tour-dot ${i === this.currentStep ? 'active' : ''}`;
      dot.addEventListener('click', () => {
        this.currentStep = i;
        this._renderStep();
      });
      dotsContainer.appendChild(dot);
    }
  }

  /** Update active dot indicator */
  _updateDots() {
    const dots = this.popover.querySelectorAll('.tour-dot');
    dots.forEach((dot, idx) => {
      dot.classList.toggle('active', idx === this.currentStep);
    });
  }

  /** Compute aggregate bounding rectangle across one or more target elements */
  _getTargetRect(selector) {
    const targets = document.querySelectorAll(selector);
    if (!targets || targets.length === 0) return null;

    let top = Infinity;
    let left = Infinity;
    let right = -Infinity;
    let bottom = -Infinity;

    targets.forEach(t => {
      const r = t.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return;
      top = Math.min(top, r.top);
      left = Math.min(left, r.left);
      right = Math.max(right, r.right);
      bottom = Math.max(bottom, r.bottom);
    });

    if (top === Infinity) return targets[0].getBoundingClientRect();

    return {
      top,
      left,
      right,
      bottom,
      width: right - left,
      height: bottom - top
    };
  }

  /** Position spotlight and popover for the active step */
  _renderStep() {
    const step = this.steps[this.currentStep];
    const rect = this._getTargetRect(step.selector);

    if (!rect) {
      console.warn(`[TourGuide] Element not found for selector: ${step.selector}`);
      return;
    }

    // If target is in panelRight and panelLeft is fullscreen, exit fullscreen so right panel is visible
    if (this.currentStep >= 2) {
      const panelLeft = document.getElementById('panelLeft');
      const btnLeft = document.getElementById('fullscreenLeft');
      if (panelLeft && panelLeft.classList.contains('fullscreen') && btnLeft) {
        btnLeft.click();
      }
    }

    // Auto-scroll target into view if mobile or overflowed
    const firstTarget = document.querySelector(step.selector);
    if (window.innerWidth <= 768 && firstTarget) {
      firstTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Update text content
    const stepBadge = this.popover.querySelector('#tourStepBadge');
    const titleEl = this.popover.querySelector('#tourPopoverTitle');
    const descEl = this.popover.querySelector('#tourPopoverDesc');
    const prevBtn = this.popover.querySelector('#tourPrevBtn');
    const nextBtn = this.popover.querySelector('#tourNextBtn');

    if (stepBadge) stepBadge.textContent = `Step ${this.currentStep + 1} of ${this.steps.length}`;
    if (titleEl) titleEl.textContent = step.title;
    if (descEl) descEl.textContent = step.content;

    if (prevBtn) {
      prevBtn.style.visibility = this.currentStep === 0 ? 'hidden' : 'visible';
    }

    if (nextBtn) {
      nextBtn.textContent = this.currentStep === this.steps.length - 1 ? 'Finish' : 'Next';
    }

    this._updateDots();

    // Calculate bounding rect and place spotlight
    const pad = step.targetPadding || 8;
    this.spotlight.style.left = `${Math.max(0, rect.left - pad)}px`;
    this.spotlight.style.top = `${Math.max(0, rect.top - pad)}px`;
    this.spotlight.style.width = `${rect.width + pad * 2}px`;
    this.spotlight.style.height = `${rect.height + pad * 2}px`;

    // Position popover relative to spotlight
    this._positionPopover(rect, step.placement);
  }

  /** Smart popover placement with boundary clamping */
  _positionPopover(targetRect, preferredPlacement) {
    const popoverRect = this.popover.getBoundingClientRect();
    const pWidth = popoverRect.width || 340;
    const pHeight = popoverRect.height || 220;
    const margin = 16;
    const isMobile = window.innerWidth <= 768;

    let left = 0;
    let top = 0;

    if (isMobile) {
      // On mobile screens, center popover in viewport or dock to bottom/top
      left = (window.innerWidth - pWidth) / 2;
      if (targetRect.top > window.innerHeight / 2) {
        top = Math.max(margin, targetRect.top - pHeight - margin);
      } else {
        top = Math.min(window.innerHeight - pHeight - margin, targetRect.bottom + margin);
      }
    } else if (preferredPlacement === 'inside-top-left') {
      left = targetRect.left + 24;
      top = targetRect.top + 70;
    } else if (preferredPlacement === 'top') {
      left = targetRect.left + (targetRect.width - pWidth) / 2;
      top = targetRect.top - pHeight - margin;
    } else if (preferredPlacement === 'left') {
      left = targetRect.left - pWidth - margin;
      top = targetRect.top + (targetRect.height - pHeight) / 2;
      // If it overflows off the left edge, place it to the right or bottom
      if (left < margin) {
        left = targetRect.right + margin;
        if (left + pWidth > window.innerWidth - margin) {
          left = (window.innerWidth - pWidth) / 2;
          top = targetRect.bottom + margin;
        }
      }
    } else if (preferredPlacement === 'bottom') {
      left = targetRect.left + (targetRect.width - pWidth) / 2;
      top = targetRect.bottom + margin;
    }

    // Clamp inside viewport
    left = Math.max(margin, Math.min(left, window.innerWidth - pWidth - margin));
    top = Math.max(margin, Math.min(top, window.innerHeight - pHeight - margin));

    this.popover.style.left = `${left}px`;
    this.popover.style.top = `${top}px`;
  }

  _onWindowResize() {
    if (!this.isActive) return;
    this._renderStep();
  }

  _onKeyDown(e) {
    if (!this.isActive) return;
    if (e.key === 'Escape') {
      this.stop();
    } else if (e.key === 'ArrowRight') {
      this.nextStep();
    } else if (e.key === 'ArrowLeft') {
      this.prevStep();
    }
  }
}
