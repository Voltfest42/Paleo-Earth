/**
 * slider.js — Time slider with keyframe detection and marker overlay
 *
 * Emits two custom events on the container element:
 *   'machange'       — fires continuously while dragging; detail: { ma }
 *   'keyframechange' — fires after SLIDER_DEBOUNCE_MS idle; detail: { keyframe }
 *                      keyframe is the nearest keyframe object, or null if none
 *                      is within snap radius.
 */

import { MIN_MA, MAX_MA, SLIDER_DEBOUNCE_MS, PERIOD_SNAP_RADIUS, EVENT_SNAP_RADIUS } from './config.js';

export class Slider {
  /**
   * @param {HTMLElement}  container      — the slider section element
   * @param {HTMLElement}  inputEl        — the <input type="range"> element
   * @param {HTMLElement}  trackOverlay   — the marker overlay div
   * @param {HTMLElement}  maLabel        — displays "0 Ma" etc.
   * @param {HTMLElement}  periodLabel    — displays period name
   * @param {HTMLElement}  eraLabel       — topbar label "Holocene · 0 Ma"
   * @param {object[]}     keyframes      — keyframes.json array
   */
  constructor(container, inputEl, trackOverlay, maLabel, periodLabel, eraLabel, keyframes) {
    this._container    = container;
    this._input        = inputEl;
    this._overlay      = trackOverlay;
    this._maLabel      = maLabel;
    this._periodLabel  = periodLabel;
    this._eraLabel     = eraLabel;
    this._keyframes    = keyframes;
    this._debounceTimer = null;
    this._currentMa    = 0;
    this._activeKeyframe = null;

    this._buildMarkers();
    this._attach();
    this._update(0); // initial render
  }

  // ── Marker overlay ────────────────────────────────────────────────────
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

    this._input.addEventListener('input', () => {
      const ma = parseInt(this._input.value, 10);
      this._currentMa = ma;
      this._update(ma);

      // Fire continuous ma event for globe texture updates
      this._container.dispatchEvent(new CustomEvent('machange', { detail: { ma }, bubbles: true }));

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
      const radius = markerKf.type === 'event' ? EVENT_SNAP_RADIUS : PERIOD_SNAP_RADIUS;
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
    // 1. Check event keyframes first if within EVENT_SNAP_RADIUS
    let bestEvent = null, bestEventDist = Infinity;
    for (const kf of this._keyframes) {
      if (kf.type === 'event') {
        const d = Math.abs(kf.ma - ma);
        if (d <= EVENT_SNAP_RADIUS && d < bestEventDist) {
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
    this._input.value = String(Math.max(MIN_MA, Math.min(MAX_MA, ma)));
    this._input.dispatchEvent(new Event('input'));
  }
}
