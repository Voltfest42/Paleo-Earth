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
import { speak, stopAll, getPollyVoice, setPollyVoice } from './tts.js';

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
  let startY      = 0;
  let startWidth  = 0;
  let startHeight = 0;
  let isMobile    = false;

  const dragStart = (x, y) => {
    dragging    = true;
    isMobile    = window.innerWidth <= 768;
    startX      = x;
    startY      = y;
    const rect  = panelLeft.getBoundingClientRect();
    startWidth  = rect.width;
    startHeight = rect.height;
    handle.classList.add('dragging');
    document.body.style.cursor     = isMobile ? 'row-resize' : 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const dragMove = (x, y) => {
    if (!dragging) return;
    if (isMobile) {
      const delta     = y - startY;
      const targetY   = startHeight + delta;

      // Snap to fullscreen if dragged near the edges
      if (targetY < 80) { // Dragged to the top (Text Fullscreen)
        panelLeft.style.height = '45vh'; // Reset for when they exit fullscreen
        const btn = document.getElementById('fullscreenRight');
        if (btn && !document.getElementById('panelRight').classList.contains('fullscreen')) btn.click();
        dragEnd();
        return;
      }
      if (targetY > container.clientHeight - 120) { // Dragged to the bottom (Globe Fullscreen)
        panelLeft.style.height = '45vh'; // Reset for when they exit fullscreen
        const btn = document.getElementById('fullscreenLeft');
        if (btn && !document.getElementById('panelLeft').classList.contains('fullscreen')) btn.click();
        dragEnd();
        return;
      }

      const newHeight = Math.max(80, Math.min(targetY, container.clientHeight - 120));
      panelLeft.style.height = `${newHeight}px`;
    } else {
      const delta    = x - startX;
      const newWidth = Math.max(320, Math.min(startWidth + delta, container.clientWidth - 280));
      panelLeft.style.width = `${newWidth}px`;
    }
  };

  const dragEnd = () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    document.body.style.cursor     = '';
    document.body.style.userSelect = '';
  };

  // Mouse events
  handle.addEventListener('mousedown', e => dragStart(e.clientX, e.clientY));
  document.addEventListener('mousemove', e => dragMove(e.clientX, e.clientY));
  document.addEventListener('mouseup', dragEnd);

  // Touch events (for mobile)
  handle.addEventListener('touchstart', e => dragStart(e.touches[0].clientX, e.touches[0].clientY), { passive: true });
  document.addEventListener('touchmove', e => {
    if (dragging) {
      // Prevent scrolling while dragging the resizer
      if (e.cancelable) e.preventDefault();
      dragMove(e.touches[0].clientX, e.touches[0].clientY);
    }
  }, { passive: false });
  document.addEventListener('touchend', dragEnd);
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

  // "?"?"? Settings Modal Logic "?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsModal = document.getElementById('settingsModal');
  const settingsCloseBtn = document.getElementById('settingsCloseBtn');
  const ttsVoiceSelect = document.getElementById('ttsVoiceSelect');

  if (settingsBtn && settingsModal && settingsCloseBtn && ttsVoiceSelect) {
    // Open
    settingsBtn.addEventListener('click', () => {
      // Sync UI with current preference
      ttsVoiceSelect.value = getPollyVoice();
      settingsModal.classList.add('active');
    });

    // Close
    settingsCloseBtn.addEventListener('click', () => {
      settingsModal.classList.remove('active');
    });
    settingsModal.addEventListener('click', (e) => {
      if (e.target === settingsModal) {
        settingsModal.classList.remove('active');
      }
    });

    // Handle voice change
    ttsVoiceSelect.addEventListener('change', (e) => {
      setPollyVoice(e.target.value);
    });
  }



  // Wiki DOM and TTS initialization
  let currentWikiText = '';
  const wikiHeader = document.querySelector('.wiki-header');
  const wikiSubtitle = document.getElementById('wikiSubtitle');
  const wikiTtsBtn = document.getElementById('wikiTtsBtn');

  if (wikiTtsBtn) {
    wikiTtsBtn.addEventListener('click', () => {
      if (currentWikiText) {
        speak(currentWikiText, wikiTtsBtn);
      }
    });
  }

  // Load data
  let keyframes, summaries, imageLibrary, climateTimeline, keyframeImages, wikiArticles;
  try {
    [keyframes, summaries, imageLibrary, climateTimeline, keyframeImages, wikiArticles] = await Promise.all([
      loadJSON('data/keyframes.json'),
      loadJSON('data/summaries.json'),
      loadJSON('data/image-library.json').then(d => d.images || []),
      loadJSON('data/climate.json').catch(() => null),
      loadJSON('data/keyframe-images.json').catch(() => ({})),
      loadJSON('data/wiki.json').catch(() => ({})),
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

  // Political borders overlay toggle
  const toggleBordersBtn = document.getElementById('toggleBordersBtn');
  if (toggleBordersBtn) {
    toggleBordersBtn.addEventListener('click', () => {
      const active = globe.toggleBorders();
      toggleBordersBtn.classList.toggle('active', active);
      toggleBordersBtn.setAttribute('aria-pressed', String(active));
      toggleBordersBtn.title = active
        ? 'Hide Political Borders Overlay'
        : 'Show Political Borders Overlay';
    });
  }

  // Climate gauges
  const gauges = new GaugeSet(document.getElementById('gaugesContainer'));

  // Chat
  const chat = new Chat({
    sendBtn:              document.getElementById('sendBtn'),
    chatInput:            document.getElementById('chatInput'),
    chatMessages:         document.getElementById('chatMessages'),
    summaryText:          document.getElementById('summaryText'),
    summarySubtitle:      document.getElementById('summarySubtitle'),
    summaryTtsBtn:        document.getElementById('summaryTtsBtn'),
    summaryHeroToggleBtn: document.getElementById('summaryHeroToggleBtn'),
    keyframeTitle:        document.getElementById('keyframeTitle'),
    keyframeBadge:        document.getElementById('keyframeBadge'),
  }, imageLibrary, keyframeImages);

  // Set initial keyframe (holocene, 0 Ma)
  const initialKeyframe = keyframes.find(k => k.id === 'holocene') || keyframes[0];
  const initialSummary  = summaries[initialKeyframe.id];
  chat.setKeyframe(initialKeyframe, initialSummary);
  renderWiki(initialKeyframe.id);
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

  // Continuous: update globe texture and climate gauges while dragging or playing
  document.getElementById('appContainer').addEventListener('machange', e => {
    const { ma, source } = e.detail;
    globe.setMa(ma, source);
    if (climateTimeline && climateTimeline[String(ma)]) {
      gauges.updateGauges(climateTimeline[String(ma)]);
    }
  });

  // Real-time: update keyframe summary card immediately
  document.getElementById('appContainer').addEventListener('keyframechange', e => {
    const kf = e.detail.keyframe;
    if (!kf) return;

    const summary = summaries[kf.id];
    if (summary) chat.setKeyframe(kf, summary);
      renderWiki(kf.id);

    if (kf.climateData) {
      gauges.updateGauges(kf.climateData);
    }
  });

  // Settled: update chat thread context divider after dragging pauses
    // Tab switching logic
  document.querySelectorAll('.panel-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.panel-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  document.getElementById('appContainer').addEventListener('keyframesettle', e => {
    const kf = e.detail.keyframe;
    if (kf) chat.onKeyframeSettled(kf);
  });

  // --- Wiki Tab Renderer -----------------------------------------------------

  function renderWiki(keyframeId) {
    const el = document.getElementById('wikiContent');
    if (!el) return;

    const article = wikiArticles && wikiArticles[keyframeId];
    if (!article) {
      if (wikiHeader) wikiHeader.style.display = 'none';
      currentWikiText = '';
      el.innerHTML = '<p style="padding:24px;color:var(--text-muted);text-align:center;font-style:italic;">No detailed article available for this period yet.<br>Check back soon!</p>';
      return;
    }

    if (wikiHeader) {
      wikiHeader.style.display = 'flex';
      if (wikiSubtitle) wikiSubtitle.textContent = article.subtitle || '';
    }

    let html = '';
    let textForTTS = article.title + '. ' + (article.subtitle ? article.subtitle + '. ' : '');

    for (const section of article.sections) {
      html += `<h3 class="wiki-heading">${section.heading}</h3>`;
      textForTTS += section.heading + '. ';

      const paragraphs = section.body.split('\n\n');
      for (const p of paragraphs) {
        if (!p.trim()) continue;
        html += `<p class="wiki-body">${p.trim()}</p>`;
        textForTTS += p.trim() + ' ';
      }
    }
    el.innerHTML = html;
    el.scrollTop = 0; // scroll back to top on keyframe change
    currentWikiText = textForTTS.trim();
  }
}

main().catch(err => {
  console.error('Fatal error during startup:', err);
});











