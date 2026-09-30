/**
 * slider.js — Time slider with animation playback, keyframe detection, and marker overlay
 *
 * Emits two custom events on the container element:
 *   'machange'       — fires continuously while dragging or playing; detail: { ma }
 *   'keyframechange' — fires immediately when crossing into new keyframe; detail: { keyframe }
 *   'keyframesettle' — fires after dragging or playing pauses; detail: { keyframe }
 */

import {
  MIN_MA,
  MAX_MA,
  SLIDER_DEBOUNCE_MS,
  SLIDER_PLAY_DURATION_SEC,
  PERIOD_SNAP_RADIUS,
  EVENT_SNAP_RADIUS,
  GEOLOGIC_PERIODS,
} from './config.js';

export class Slider {
  /**
   * @param {HTMLElement}  container      — the slider section / app container element
   * @param {HTMLElement}  inputEl        — the <input type="range"> element
   * @param {HTMLElement}  trackOverlay   — the marker overlay div
   * @param {HTMLElement}  maLabel        — displays "0 Ma" etc.
   * @param {HTMLElement}  periodLabel    — displays period name
   * @param {HTMLElement}  eraLabel       — topbar label "Holocene · 0 Ma"
   * @param {object[]}     keyframes      — keyframes.json array
   * @param {HTMLElement}  [playBtn]      — optional play/pause button element
   */
  constructor(container, inputEl, trackOverlay, maLabel, periodLabel, eraLabel, keyframes, playBtn = null) {
    this._container     = container;
    this._input         = inputEl;
    this._overlay       = trackOverlay;
    this._maLabel       = maLabel;
    this._periodLabel   = periodLabel;
    this._eraLabel      = eraLabel;
    this._keyframes     = keyframes;
    this._playBtn       = playBtn;
    this._debounceTimer = null;
    this._currentMa     = 0;
    this._playMa        = 0;
    this._activeKeyframe = null;

    // Animation state
    this._isPlaying          = false;
    this._playAnimId         = null;
    this._lastPlayTimestamp  = null;
    this._playDurationSec    = SLIDER_PLAY_DURATION_SEC;

    // Force input element reset on init
    this._input.value = '0';
    this._input.setAttribute('autocomplete', 'off');

    this._buildGeologicTimeBar();
    this._buildMarkers();
    this._attach();
    this._initPlayButton();
    this._update(0); // initial render
  }

  // ── Marker overlay ────────────────────────────────────────────────────
  _buildGeologicTimeBar() {
    const barEl = document.getElementById('geologicTimeBar');
    if (!barEl || !GEOLOGIC_PERIODS) return;
    
    // Clear existing (if any)
    barEl.innerHTML = '';
    
    // The total time span is MAX_MA (540). The slider maps 0 to the left and 540 to the right.
    const totalMa = MAX_MA - MIN_MA;
    
    GEOLOGIC_PERIODS.forEach(period => {
      const block = document.createElement('div');
      block.className = 'period-block';
      
      const duration = period.end - period.start;
      const widthPct = (duration / totalMa) * 100;
      
      block.style.width = `${widthPct}%`;
      block.style.backgroundColor = `rgba(${period.color}, 0.25)`;
      block.textContent = period.id;
      block.title = `${period.name} (${period.start} - ${period.end} Ma)`;
      
      // Click interaction: jump to the middle of the period
      block.addEventListener('click', () => {
        const middleMa = Math.round((period.start + period.end) / 2);
        this._input.value = middleMa;
        
        // Emulate typical input event dispatching so the slider instantly snaps and updates
        this._input.dispatchEvent(new Event('input', { bubbles: true }));
        this._input.dispatchEvent(new Event('change', { bubbles: true }));
      });
      
      barEl.appendChild(block);
    });
  }

  _buildMarkers() {
    this._overlay.innerHTML = '';
    const total = MAX_MA - MIN_MA;

    for (const kf of this._keyframes) {
      const pct = (kf.ma / total) * 100;
      const el  = document.createElement('div');
      el.className = `slider-marker${kf.type === 'event' ? ' event' : ''}`;
      el.style.left = `${pct}%`;
      el.title = `${kf.label} (${kf.ma} Ma)`;

      // Tooltip on hover
      el.addEventListener('mouseenter', () => this._showTooltip(kf, el));
      el.addEventListener('mouseleave', () => this._hideTooltip());

      // Click marker to jump directly
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        this.setMa(kf.ma);
      });

      this._overlay.appendChild(el);
    }
  }

  _showTooltip(kf, anchor) {
    this._removeTooltip();
    const tip = document.createElement('div');
    tip.className = 'slider-tooltip';
    tip.textContent = `${kf.label} · ${kf.ma} Ma`;
    tip.style.cssText = `
      position:absolute; bottom:calc(100% + 6px); left:50%;
      transform:translateX(-50%);
      background:rgba(13,20,32,0.95); color:#e8edf5;
      font-size:10px; white-space:nowrap; padding:4px 8px;
      border-radius:4px; border:1px solid rgba(255,255,255,0.1);
      pointer-events:none; z-index:20;
    `;
    anchor.style.position = 'absolute';
    anchor.appendChild(tip);
    this._tooltip = tip;
  }

  _hideTooltip()  { this._removeTooltip(); }
  _removeTooltip() {
    if (this._tooltip) { this._tooltip.remove(); this._tooltip = null; }
  }

  // ── Input wiring ──────────────────────────────────────────────────────
  _attach() {
    this._input.min  = String(MIN_MA);
    this._input.max  = String(MAX_MA);
    this._input.step = '1';

    // If user touches or drags the slider, pause automatic playback
    this._input.addEventListener('pointerdown', () => this.pause());
    this._input.addEventListener('keydown', () => this.pause());

    this._input.addEventListener('input', () => {
      this.pause();
      const ma = parseInt(this._input.value, 10) || 0;
      this._currentMa = ma;
      this._playMa    = ma;
      this._update(ma);

      // Fire continuous ma event for globe texture updates (source: drag)
      this._container.dispatchEvent(new CustomEvent('machange', { detail: { ma, source: 'drag' }, bubbles: true }));

      // Immediate real-time keyframe update (updates summary card & gauges instantaneously)
      this._detectKeyframe(ma);

      // Debounce settle event (for chat conversation context divider)
      clearTimeout(this._debounceTimer);
      this._debounceTimer = setTimeout(() => {
        if (this._activeKeyframe) {
          this._container.dispatchEvent(
            new CustomEvent('keyframesettle', { detail: { keyframe: this._activeKeyframe }, bubbles: true })
          );
        }
      }, SLIDER_DEBOUNCE_MS);
    });

    // When dragging completes (mouse/touch released)
    this._input.addEventListener('change', () => {
      const ma = parseInt(this._input.value, 10) || 0;
      this._container.dispatchEvent(new CustomEvent('machange', { detail: { ma, source: 'settle' }, bubbles: true }));
    });
  }

  // ── Play / Pause animation ────────────────────────────────────────────
  _initPlayButton() {
    if (!this._playBtn) return;

    this._playBtn.addEventListener('click', () => {
      this.togglePlay();
    });
  }

  togglePlay() {
    if (this._isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  play() {
    if (this._isPlaying) return;
    this._isPlaying = true;
    this._updatePlayButtonUI();

    // If we are at the very end, restart from beginning
    if (this._currentMa >= MAX_MA) {
      this._playMa = 0;
      this._setSliderValue(0, 'play');
    } else {
      this._playMa = this._currentMa;
    }

    this._lastPlayTimestamp = performance.now();

    const step = (timestamp) => {
      if (!this._isPlaying) return;

      const deltaMs = timestamp - this._lastPlayTimestamp;
      this._lastPlayTimestamp = timestamp;

      const maPerMs = (MAX_MA - MIN_MA) / (this._playDurationSec * 1000);
      this._playMa += deltaMs * maPerMs;

      if (this._playMa >= MAX_MA) {
        this._playMa = MAX_MA;
        this._setSliderValue(MAX_MA, 'play');
        this.pause();
        return;
      }

      this._setSliderValue(this._playMa, 'play');
      this._playAnimId = requestAnimationFrame(step);
    };

    this._playAnimId = requestAnimationFrame(step);
  }

  pause() {
    if (!this._isPlaying) return;
    this._isPlaying = false;
    if (this._playAnimId) {
      cancelAnimationFrame(this._playAnimId);
      this._playAnimId = null;
    }
    this._updatePlayButtonUI();

    // Trigger settle event when playback stops
    if (this._activeKeyframe) {
      this._container.dispatchEvent(
        new CustomEvent('keyframesettle', { detail: { keyframe: this._activeKeyframe }, bubbles: true })
      );
    }
  }

  _updatePlayButtonUI() {
    if (!this._playBtn) return;
    const playIcon  = this._playBtn.querySelector('#playIcon');
    const pauseIcon = this._playBtn.querySelector('#pauseIcon');
    if (playIcon && pauseIcon) {
      playIcon.style.display  = this._isPlaying ? 'none' : 'block';
      pauseIcon.style.display = this._isPlaying ? 'block' : 'none';
    }
    this._playBtn.classList.toggle('playing', this._isPlaying);
    this._playBtn.title = this._isPlaying ? 'Pause timeline animation' : 'Play timeline animation';
  }

  _setSliderValue(maFloat, source = 'drag') {
    const ma = Math.round(maFloat);
    if (ma !== this._currentMa) {
      this._currentMa   = ma;
      this._input.value = String(ma);
      this._update(ma);
      this._container.dispatchEvent(new CustomEvent('machange', { detail: { ma, source }, bubbles: true }));
      this._detectKeyframe(ma);
    }
  }

  // ── Label update ──────────────────────────────────────────────────────
  _update(ma) {
    this._maLabel.textContent = `${ma} Ma`;

    // Find the best keyframe for the current Ma
    const kf = this._findBestKeyframe(ma);
    if (kf) {
      const name = kf.type === 'event' ? kf.label : (kf.period || kf.label);
      this._periodLabel.textContent = name;
      if (this._eraLabel) {
        this._eraLabel.textContent = `${kf.type === 'event' ? kf.label : kf.period} · ${ma} Ma`;
      }
    }

    // Highlight active marker
    const markers = this._overlay.querySelectorAll('.slider-marker');
    markers.forEach((m, i) => {
      const markerKf = this._keyframes[i];
      const radius = markerKf.snapRadius !== undefined
        ? markerKf.snapRadius
        : (markerKf.type === 'event' ? EVENT_SNAP_RADIUS : PERIOD_SNAP_RADIUS);
      m.classList.toggle('active', Math.abs(markerKf.ma - ma) <= radius);
    });
  }

  // ── Keyframe detection ────────────────────────────────────────────────
  _detectKeyframe(ma) {
    const best = this._findBestKeyframe(ma);

    if (best && best !== this._activeKeyframe) {
      this._activeKeyframe = best;
      this._container.dispatchEvent(
        new CustomEvent('keyframechange', { detail: { keyframe: best }, bubbles: true })
      );
    }
  }

  _findBestKeyframe(ma) {
    // 1. Check event keyframes first if within their snap radius
    let bestEvent = null, bestEventDist = Infinity;
    for (const kf of this._keyframes) {
      if (kf.type === 'event') {
        const radius = kf.snapRadius !== undefined ? kf.snapRadius : EVENT_SNAP_RADIUS;
        const d = Math.abs(kf.ma - ma);
        if (d <= radius && d < bestEventDist) {
          bestEventDist = d;
          bestEvent = kf;
        }
      }
    }
    if (bestEvent) return bestEvent;

    // 2. Otherwise find the closest period keyframe
    let bestPeriod = null, bestPeriodDist = Infinity;
    for (const kf of this._keyframes) {
      if (kf.type === 'period') {
        const d = Math.abs(kf.ma - ma);
        if (d < bestPeriodDist) {
          bestPeriodDist = d;
          bestPeriod = kf;
        }
      }
    }
    if (bestPeriod) return bestPeriod;

    // 3. Fallback to closest keyframe of any type
    let best = null, bestDist = Infinity;
    for (const kf of this._keyframes) {
      const d = Math.abs(kf.ma - ma);
      if (d < bestDist) {
        bestDist = d;
        best = kf;
      }
    }
    return best || this._keyframes[0];
  }

  // ── Public API ────────────────────────────────────────────────────────
  get currentMa()        { return this._currentMa; }
  get activeKeyframe()   { return this._activeKeyframe; }

  /** Programmatically jump to a Ma value */
  setMa(ma) {
    this.pause();
    const clamped = Math.max(MIN_MA, Math.min(MAX_MA, ma));
    this._currentMa = clamped;
    this._playMa    = clamped;
    this._input.value = String(clamped);
    this._update(clamped);
    this._container.dispatchEvent(new CustomEvent('machange', { detail: { ma: clamped, source: 'direct' }, bubbles: true }));
    this._detectKeyframe(clamped);
  }

  reset() {
    this.setMa(0);
  }
}
