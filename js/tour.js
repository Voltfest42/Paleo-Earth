/**
 * tour.js — Interactive Onboarding & Guided Spotlight Tour for Paleo Earth
 *
 * Provides:
 *  1. Welcome Modal on first visit with "Take 1-Minute Tour" or "Explore on My Own".
 *  2. 5-Step Spotlight Guided Tour highlighting key UI elements across the app.
 *  3. Preserves full live interactivity (dragging the globe, scrubbing the slider,
 *     toggling period/event buttons, and switching tabs) without closing the tour.
 *  4. Mobile-optimized HUD: Compact popover dimensions and strategic top/bottom docking
 *     to prevent obscuring highlighted controls.
 *  5. Step 4 specifically demonstrates the draggable splitter bar on mobile, smoothly
 *     expanding the encyclopedia and AI chat panel into full view for Step 5.
 *  6. Re-triggerable via Settings modal or the Tour button in viewport controls.
 *  7. Full keyboard navigation (Escape, ArrowLeft, ArrowRight) and mobile responsiveness.
 */

const TOUR_STORAGE_KEY = 'paleo_earth_tour_seen';

export class TourGuide {
  constructor() {
    this.currentStep = 0;
    this.isActive = false;
    this._initialPanelHeight = undefined;

    this.steps = [
      {
        id: 'globe',
        selector: '#globeContainer',
        title: 'The 3D Paleoglobe',
        content: 'Click and drag anywhere to rotate Earth across 540 million years. Scroll or pinch to zoom. Use the top-right overlay buttons to toggle political borders, ancient continents, or climate atmosphere gauges.',
        placement: 'inside-top-left',
        mobilePlacement: 'bottom',
        targetPadding: 6
      },
      {
        id: 'timeline',
        selector: '.slider-section',
        title: 'Timeline & GTS Ribbon',
        content: 'Drag the timeline scrubber to travel continuously from 540 Ma (Cambrian) to Present Day. You can also click directly on any colored period block on the Geologic Time Scale ribbon to jump through time instantly.',
        placement: 'top',
        mobilePlacement: 'top',
        targetPadding: 8
      },
      {
        id: 'periods-events',
        selector: '#panelRight .panel-topbar, #summaryCard',
        title: 'Periods and Events',
        content: 'As you scrub, the timeline snaps to geologic periods and major milestones—including evolutionary radiations, climate transitions, and extinction events. The header badge and summary update dynamically to reflect the active era.',
        placement: 'left',
        mobilePlacement: 'top',
        targetPadding: 8
      },
      {
        id: 'splitter',
        selector: '#resizeHandle',
        title: 'Draggable Splitter Bar',
        content: 'Drag this divider bar to customize your split-screen view. On mobile, watch it slide up now to reveal the full encyclopedia and chat panel below!',
        placement: 'top',
        mobilePlacement: 'top',
        targetPadding: 6
      },
      {
        id: 'wiki-chat',
        selector: '.panel-tabs, .panel-tab-content',
        title: 'Encyclopedia & AI Assistant',
        content: 'Dive into detailed period summaries and encyclopedia entries. Tap the speaker icon to hear audio narration, or switch to the "Ask Questions" tab to chat with our AI assistant anchored to the active time period.',
        placement: 'left',
        mobilePlacement: 'top',
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
        <div class="tour-step-badge" id="tourStepBadge">Step 1 of 5</div>
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
          setTimeout(() => this._updatePositions(), 60);
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
    this._initialPanelHeight = undefined;

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

    // Restore mobile panel height if modified
    const isMobile = window.innerWidth <= 768;
    const panelLeft = document.getElementById('panelLeft');
    if (isMobile && panelLeft && this._initialPanelHeight !== undefined) {
      panelLeft.style.transition = 'height 0.35s ease';
      panelLeft.style.height = this._initialPanelHeight;
      setTimeout(() => {
        panelLeft.style.transition = '';
        this._initialPanelHeight = undefined;
        if (window._globeInstance && window._globeInstance.onWindowResize) {
          window._globeInstance.onWindowResize();
        }
      }, 360);
    }

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
    const isMobile = window.innerWidth <= 768;
    const panelLeft = document.getElementById('panelLeft');

    // Manage mobile layout transitions for steps 3 and 4 (Splitter & Wiki/Chat)
    if (isMobile && panelLeft) {
      if (this.currentStep >= 3) {
        // Entering Step 4 or 5: expand right panel
        if (this._initialPanelHeight === undefined) {
          this._initialPanelHeight = panelLeft.style.height || '';
        }
        if (panelLeft.style.height !== '32%') {
          panelLeft.style.transition = 'height 0.4s cubic-bezier(0.2, 0.9, 0.3, 1)';
          panelLeft.style.height = '32%';
          setTimeout(() => {
            if (window._globeInstance && window._globeInstance.onWindowResize) {
              window._globeInstance.onWindowResize();
            }
            this._updatePositions();
          }, 420);
        }
      } else if (this._initialPanelHeight !== undefined) {
        // Back to Steps 0, 1, or 2: restore initial panel height
        panelLeft.style.transition = 'height 0.35s ease';
        panelLeft.style.height = this._initialPanelHeight;
        setTimeout(() => {
          this._initialPanelHeight = undefined;
          panelLeft.style.transition = '';
          if (window._globeInstance && window._globeInstance.onWindowResize) {
            window._globeInstance.onWindowResize();
          }
          this._updatePositions();
        }, 360);
      }
    }

    // Exit fullscreen on panelLeft if active on desktop/tablet
    if (this.currentStep >= 2 && panelLeft && panelLeft.classList.contains('fullscreen')) {
      const btnLeft = document.getElementById('fullscreenLeft');
      if (btnLeft) btnLeft.click();
    }

    // Auto-scroll target into view if needed
    const firstTarget = document.querySelector(step.selector);
    if (isMobile && firstTarget && this.currentStep !== 3) {
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

    // Context-sensitive description for splitter on mobile vs desktop
    let desc = step.content;
    if (step.id === 'splitter') {
      desc = isMobile
        ? 'Drag this divider bar up to expand the encyclopedia and chat, or drag down to enlarge the globe. (Notice how it slid up to reveal the articles below!)'
        : 'Drag this divider bar left or right to customize your split-screen view between the 3D globe and the information panel.';
    }
    if (descEl) descEl.textContent = desc;

    if (prevBtn) {
      prevBtn.style.visibility = this.currentStep === 0 ? 'hidden' : 'visible';
    }

    if (nextBtn) {
      nextBtn.textContent = this.currentStep === this.steps.length - 1 ? 'Finish' : 'Next';
    }

    this._updateDots();
    this._updatePositions();
  }

  /** Update physical positions of spotlight box and popover */
  _updatePositions() {
    const step = this.steps[this.currentStep];
    const rect = this._getTargetRect(step.selector);
    if (!rect) return;

    const pad = step.targetPadding || 8;
    this.spotlight.style.left = `${Math.max(0, rect.left - pad)}px`;
    this.spotlight.style.top = `${Math.max(0, rect.top - pad)}px`;
    this.spotlight.style.width = `${rect.width + pad * 2}px`;
    this.spotlight.style.height = `${rect.height + pad * 2}px`;

    this._positionPopover(rect, step);
  }

  /** Smart popover placement with boundary clamping */
  _positionPopover(targetRect, step) {
    const popoverRect = this.popover.getBoundingClientRect();
    const pWidth = popoverRect.width || 330;
    const pHeight = popoverRect.height || 150;
    const margin = 12;
    const isMobile = window.innerWidth <= 768;

    let left = 0;
    let top = 0;

    if (isMobile) {
      left = Math.max(margin, (window.innerWidth - pWidth) / 2);

      const pref = step.mobilePlacement || 'auto';
      if (pref === 'top') {
        top = margin;
      } else if (pref === 'bottom') {
        top = window.innerHeight - pHeight - margin;
      } else {
        const targetCenterY = targetRect.top + targetRect.height / 2;
        if (targetCenterY > window.innerHeight / 2) {
          top = margin;
        } else {
          top = window.innerHeight - pHeight - margin;
        }
      }
    } else {
      const preferredPlacement = step.placement;
      if (preferredPlacement === 'inside-top-left') {
        left = targetRect.left + 24;
        top = targetRect.top + 70;
      } else if (preferredPlacement === 'top') {
        left = targetRect.left + (targetRect.width - pWidth) / 2;
        top = targetRect.top - pHeight - 16;
      } else if (preferredPlacement === 'left') {
        left = targetRect.left - pWidth - 16;
        top = targetRect.top + (targetRect.height - pHeight) / 2;
        if (left < margin) {
          left = targetRect.right + 16;
          if (left + pWidth > window.innerWidth - margin) {
            left = (window.innerWidth - pWidth) / 2;
            top = targetRect.bottom + 16;
          }
        }
      } else if (preferredPlacement === 'bottom') {
        left = targetRect.left + (targetRect.width - pWidth) / 2;
        top = targetRect.bottom + 16;
      }
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
