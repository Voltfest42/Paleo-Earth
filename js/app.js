/**
 * app.js — Main entry point for Paleo Earth
 *
 * Loads all data, initialises modules, wires events.
 *
 * Run locally with:
 *   python -m http.server 8000
 *   then open http://localhost:8000
 * (ES modules cannot be loaded from file:// in most browsers.)
 */

import { DEV_MODE, SLIDER_DEBOUNCE_MS } from './config.js';
import { Globe    } from './globe.js';
import { GaugeSet } from './gauges.js';
import { Slider   } from './slider.js';
import { Chat     } from './chat.js';
import { stopAll  } from './tts.js';

// ─── Data loading ──────────────────────────────────────────────────────────
async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

// ─── Panel fullscreen toggle ───────────────────────────────────────────────
function initFullscreen() {
  const panelLeft  = document.getElementById('panelLeft');
  const panelRight = document.getElementById('panelRight');
  const handle     = document.getElementById('resizeHandle');
  const btnLeft    = document.getElementById('fullscreenLeft');
  const btnRight   = document.getElementById('fullscreenRight');

  btnLeft.addEventListener('click', () => {
    const active = panelLeft.classList.toggle('fullscreen');
    panelRight.style.display = active ? 'none' : '';
    handle.style.display     = active ? 'none' : '';
    btnLeft.title = active ? 'Exit fullscreen' : 'Expand globe';
  });

  btnRight.addEventListener('click', () => {
    const active = panelRight.classList.toggle('fullscreen');
    panelLeft.style.display  = active ? 'none' : '';
    handle.style.display     = active ? 'none' : '';
    btnRight.title = active ? 'Exit fullscreen' : 'Expand info panel';
  });

  // Escape key exits any fullscreen panel
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (panelLeft.classList.contains('fullscreen')) btnLeft.click();
      if (panelRight.classList.contains('fullscreen')) btnRight.click();
    }
  });
}

// ─── Panel resize (drag handle) ────────────────────────────────────────────
function initResize() {
  const handle    = document.getElementById('resizeHandle');
  const panelLeft = document.getElementById('panelLeft');
  const container = document.getElementById('appContainer');
  let dragging    = false;
  let startX      = 0;
  let startWidth  = 0;

  handle.addEventListener('mousedown', e => {
    dragging   = true;
    startX     = e.clientX;
    startWidth = panelLeft.getBoundingClientRect().width;
    handle.classList.add('dragging');
    document.body.style.cursor    = 'col-resize';
    document.body.style.userSelect = 'none';
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const delta    = e.clientX - startX;
    const newWidth = Math.max(320, Math.min(startWidth + delta, container.clientWidth - 280));
    panelLeft.style.width = `${newWidth}px`;
  });

  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    document.body.style.cursor     = '';
    document.body.style.userSelect = '';
  });
}

// ─── Main ─────────────────────────────────────────────────────────────────
async function main() {
  // Show DEV mode badge
  if (DEV_MODE) {
    const badge = document.getElementById('devModeIndicator');
    if (badge) badge.style.display = 'inline-block';
    console.info(
      '%cPaleo Earth — DEV MODE%c\nChat uses mock responses. TTS uses browser speechSynthesis.\nSet DEV_MODE = false in js/config.js when deploying to AWS.',
      'font-weight:bold;color:#f0a500', 'color:inherit'
    );
  }

  // Panel layout
  initFullscreen();
  initResize();

  // Load data
  let keyframes, summaries, imageLibrary;
  try {
    [keyframes, summaries, imageLibrary] = await Promise.all([
      loadJSON('data/keyframes.json'),
      loadJSON('data/summaries.json'),
      loadJSON('data/image-library.json').then(d => d.images || []),
    ]);
  } catch (err) {
    console.error('Failed to load data files:', err);
    document.getElementById('summaryText').textContent =
      'Error loading data. Make sure you are running from a local HTTP server (python -m http.server 8000).';
    return;
  }

  // Globe
  const globeContainer = document.getElementById('globeContainer');
  const globe          = new Globe(globeContainer);

  // Load the initial texture (0 Ma / frame 1)
  await globe.setMa(0);
  globe.setLoading(false);

  // Climate gauges
  const gauges = new GaugeSet(document.getElementById('gaugesContainer'));

  // Chat
  const chat = new Chat({
    sendBtn:         document.getElementById('sendBtn'),
    chatInput:       document.getElementById('chatInput'),
    chatMessages:    document.getElementById('chatMessages'),
    summaryText:     document.getElementById('summaryText'),
    summarySubtitle: document.getElementById('summarySubtitle'),
    summaryTtsBtn:   document.getElementById('summaryTtsBtn'),
    keyframeTitle:   document.getElementById('keyframeTitle'),
    keyframeBadge:   document.getElementById('keyframeBadge'),
  }, imageLibrary);

  // Set initial keyframe (holocene, 0 Ma)
  const initialKeyframe = keyframes.find(k => k.id === 'holocene') || keyframes[0];
  const initialSummary  = summaries[initialKeyframe.id];
  chat.setKeyframe(initialKeyframe, initialSummary);
  gauges.setGaugesImmediate(initialKeyframe.climateData);

  // Slider
  const slider = new Slider(
    document.getElementById('appContainer'),      // event target
    document.getElementById('timeSlider'),
    document.getElementById('sliderTrackOverlay'),
    document.getElementById('sliderMaLabel'),
    document.getElementById('sliderPeriodLabel'),
    document.getElementById('eraLabel'),
    keyframes,
    document.getElementById('sliderPlayBtn'),
  );

  // Ensure initial clean state at 0 Ma
  slider.setMa(0);

  // ── Wire slider events ──────────────────────────────────────────────────

  // Continuous: update globe texture while dragging
  document.getElementById('appContainer').addEventListener('machange', e => {
    globe.setMa(e.detail.ma);
  });

  // Real-time: update keyframe summary card and climate gauges immediately
  document.getElementById('appContainer').addEventListener('keyframechange', e => {
    const kf = e.detail.keyframe;
    if (!kf) return;

    const summary = summaries[kf.id];
    if (summary) chat.setKeyframe(kf, summary);

    gauges.updateGauges(kf.climateData);

    // Stop any TTS playing when changing keyframes
    stopAll();
  });

  // Settled: update chat thread context divider after dragging pauses
  document.getElementById('appContainer').addEventListener('keyframesettle', e => {
    const kf = e.detail.keyframe;
    if (kf) chat.onKeyframeSettled(kf);
  });
}

main().catch(err => {
  console.error('Fatal error during startup:', err);
});
