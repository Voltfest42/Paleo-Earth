/**
 * tts.js — Text-to-speech via Amazon Polly (prod) or browser API (dev)
 *
 * DEV_MODE = true  → uses window.speechSynthesis (no AWS needed)
 * DEV_MODE = false → calls POST /tts on the Lambda API, plays Polly MP3
 */

import { DEV_MODE, API_BASE, POLLY_VOICE_ID } from './config.js';

// Get user preferred voice, or default
export function getPollyVoice() {
  return localStorage.getItem('paleo_tts_voice') || POLLY_VOICE_ID;
}

export function setPollyVoice(voiceId) {
  localStorage.setItem('paleo_tts_voice', voiceId);
}

// Sanitize text for natural speech synthesis — strips markup/emojis, expands scientific abbreviations
export function sanitizeForSpeech(text) {
  if (!text) return '';
  return text
    // Emojis and extended pictographs
    .replace(/\p{Extended_Pictographic}/gu, '')
    .replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '')

    // Inline image tags and internal media cues
    .replace(/\[\[IMAGE:[^\]]*\]\]/gi, '')

    // Headers & block elements
    .replace(/#{1,6}\s+/g, '')
    .replace(/^>+\s*/gm, '')
    .replace(/^[\s*-+•]+\s+/gm, '')

    // Markdown formatting
    .replace(/[*_]{1,3}(.+?)[*_]{1,3}/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')

    // Geological time abbreviations (Ma, Ga, ka, mya, bya)
    .replace(/\b(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*Ma\b/gi, '$1 to $2 million years ago')
    .replace(/\b(\d+(?:\.\d+)?)\s*Ma\b/gi, '$1 million years ago')
    .replace(/\bMa\b/g, 'million years ago')
    .replace(/\b(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*Ga\b/gi, '$1 to $2 billion years ago')
    .replace(/\b(\d+(?:\.\d+)?)\s*Ga\b/gi, '$1 billion years ago')
    .replace(/\b(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*ka\b/gi, '$1 to $2 thousand years ago')
    .replace(/\b(\d+(?:\.\d+)?)\s*ka\b/gi, '$1 thousand years ago')
    .replace(/\bmya\b/gi, 'million years ago')
    .replace(/\bbya\b/gi, 'billion years ago')

    // Mass extinctions and geological boundaries
    .replace(/\bK[-–—/]?Pg\b/gi, 'Cretaceous-Paleogene')
    .replace(/\bK[-–—/]?T\b/gi, 'Cretaceous-Tertiary')
    .replace(/\bP[-–—/]?Tr\b/gi, 'Permian-Triassic')
    .replace(/\bO[-–—/]?S\b/gi, 'Ordovician-Silurian')
    .replace(/\bTr[-–—/]?J\b/gi, 'Triassic-Jurassic')
    .replace(/\bPETM\b/g, 'Paleocene-Eocene Thermal Maximum')

    // Major geological & extinction acronyms
    .replace(/\bGOBE\b/g, 'Great Ordovician Biodiversification Event')
    .replace(/\bCAMP\b/g, 'Central Atlantic Magmatic Province')
    .replace(/\bCRC\b/g, 'Carboniferous Rainforest Collapse')
    .replace(/\bEOT\b/g, 'Eocene-Oligocene Transition')
    .replace(/\bMPT\b/g, 'Mid-Pleistocene Transition')
    .replace(/\bLIPs\b/g, 'Large Igneous Provinces')
    .replace(/\bLIP\b/g, 'Large Igneous Province')
    .replace(/\bBIFs\b/g, 'Banded Iron Formations')
    .replace(/\bBIF\b/g, 'Banded Iron Formation')
    .replace(/\bOAEs?\b/gi, 'Oceanic Anoxic Event')
    .replace(/\bGSSP\b/g, 'G-S-S-P')

    // Scientific word slashes (e.g. Climatic/Environmental -> Climatic and Environmental)
    .replace(/([a-zA-Z]{3,})\/([a-zA-Z]{3,})/g, '$1 and $2')

    // Geochemical isotopes & scientific notation (e.g. ¹³C-enriched -> carbon-13 enriched)
    .replace(/\u03B4\s*/g, 'delta ')
    .replace(/\u2030/g, ' per mil')
    .replace(/([\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079]+)(Sr|Pb|Ar|He|Fe|[CONSUTH])\s*\/\s*([\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079]+)(Sr|Pb|Ar|He|Fe|[CONSUTH])/g, (m, n1, el1, n2, el2) => {
      const sMap = {'\u2070':'0','\u00B9':'1','\u00B2':'2','\u00B3':'3','\u2074':'4','\u2075':'5','\u2076':'6','\u2077':'7','\u2078':'8','\u2079':'9'};
      const eMap = {'C':'carbon','O':'oxygen','N':'nitrogen','S':'sulfur','U':'uranium','Pb':'lead','Sr':'strontium','Ar':'argon','He':'helium','H':'hydrogen','Fe':'iron'};
      const num1 = n1.split('').map(c => sMap[c] || c).join('');
      const num2 = n2.split('').map(c => sMap[c] || c).join('');
      return `${eMap[el1] || el1}-${num1} to ${eMap[el2] || el2}-${num2} ratio`;
    })
    .replace(/([\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079]+)(Sr|Pb|Ar|He|Fe|[CONSUTH])\b/g, (m, nums, el) => {
      const sMap = {'\u2070':'0','\u00B9':'1','\u00B2':'2','\u00B3':'3','\u2074':'4','\u2075':'5','\u2076':'6','\u2077':'7','\u2078':'8','\u2079':'9'};
      const eMap = {'C':'carbon','O':'oxygen','N':'nitrogen','S':'sulfur','U':'uranium','Pb':'lead','Sr':'strontium','Ar':'argon','He':'helium','H':'hydrogen','Fe':'iron'};
      const num = nums.split('').map(c => sMap[c] || c).join('');
      return `${eMap[el] || el}-${num}`;
    })
    .replace(/\bcarbon-(\d+)-enriched\b/gi, 'carbon-$1 enriched')
    .replace(/\bcarbon-(\d+)-depleted\b/gi, 'carbon-$1 depleted')
    .replace(/\boxygen-(\d+)-enriched\b/gi, 'oxygen-$1 enriched')
    .replace(/\boxygen-(\d+)-depleted\b/gi, 'oxygen-$1 depleted')
    .replace(/\b(?:delta|d)13C\b/gi, 'delta carbon-13')
    .replace(/\b(?:delta|d)18O\b/gi, 'delta oxygen-18')
    .replace(/\b(?:delta|d)34S\b/gi, 'delta sulfur-34')
    .replace(/\b13C-enriched\b/gi, 'carbon-13 enriched')
    .replace(/\b13C-depleted\b/gi, 'carbon-13 depleted')
    .replace(/\b18O-enriched\b/gi, 'oxygen-18 enriched')
    .replace(/\b18O-depleted\b/gi, 'oxygen-18 depleted')

    // Chemistry, atmosphere and climate symbols
    .replace(/\bCO[2₂\u2082](?!\w)/gi, 'carbon dioxide')
    .replace(/\bO[2₂\u2082](?!\w)/gi, 'oxygen')
    .replace(/\bCH[4₄\u2084](?!\w)/gi, 'methane')
    .replace(/\bH[2₂\u2082]O(?!\w)/gi, 'water')
    .replace(/\bSO[2₂\u2082](?!\w)/gi, 'sulfur dioxide')
    .replace(/\bN[2₂\u2082](?!\w)/gi, 'nitrogen')
    .replace(/(?:\u00b0|\bdeg\b)\s*C\b/gi, ' degrees Celsius')
    .replace(/(?:\u00b0|\bdeg\b)\s*F\b/gi, ' degrees Fahrenheit')
    .replace(/(\d+)\s*%/g, '$1 percent')
    .replace(/\bppm\b/gi, 'parts per million')
    .replace(/[~≈]/g, 'approximately ')
    .replace(/\bca\.\s*/gi, 'approximately ')

    // Editorial and Latin abbreviations
    .replace(/\be\.g\.,?\s*/gi, 'for example, ')
    .replace(/\bi\.e\.,?\s*/gi, 'that is, ')
    .replace(/\betc\.?\b/gi, 'and so on')
    .replace(/\bvs\.?\b/gi, 'versus')
    .replace(/\bsp\.\b/g, 'species')
    .replace(/\bspp\.\b/g, 'species')

    // Decorative separator characters (middle dot, bullets, vertical bars)
    .replace(/\s*[·•∙⋅|│]\s*/g, ', ')

    // Punctuation and flow
    .replace(/\s*[—–]\s*/g, ', ')
    .replace(/\.{3,}/g, ', ')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

// Backward-compatible alias
const stripMarkdown = sanitizeForSpeech;

// ─── TTS state ───────────────────────────────────────────────────────────
let _currentAudio    = null;   // HTMLAudioElement (prod)
let _currentUtterance = null;  // SpeechSynthesisUtterance (dev)
let _activeBtnEl     = null;   // currently playing button element

function _setPlaying(btnEl, playing) {
  if (_activeBtnEl && _activeBtnEl !== btnEl) {
    _activeBtnEl.classList.remove('playing');
    _activeBtnEl.setAttribute('aria-pressed', 'false');
  }
  if (btnEl) {
    btnEl.classList.toggle('playing', playing);
    btnEl.setAttribute('aria-pressed', String(playing));
  }
  _activeBtnEl = playing ? btnEl : null;
}

function stopAll() {
  if (_currentAudio) {
    _currentAudio.pause();
    _currentAudio = null;
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  _setPlaying(null, false);
}

// ─── Dev mode: browser speechSynthesis ───────────────────────────────────
function speakDev(text, btnEl) {
  stopAll();
  const clean = stripMarkdown(text);
  if (!clean) return;

  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate   = 0.92;
  utterance.pitch  = 1.0;
  utterance.volume = 1.0;

  // Prefer a natural English voice if available
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find(v =>
    v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Neural') || !v.localService)
  ) || voices.find(v => v.lang.startsWith('en')) || null;
  if (preferred) utterance.voice = preferred;

  _currentUtterance = utterance;
  _setPlaying(btnEl, true);

  utterance.onend   = () => _setPlaying(btnEl, false);
  utterance.onerror = () => _setPlaying(btnEl, false);

  window.speechSynthesis.speak(utterance);
}

// ─── Prod mode: Amazon Polly via Lambda ──────────────────────────────────
async function speakProd(text, btnEl) {
  stopAll();
  const clean = stripMarkdown(text);
  if (!clean) return;

  _setPlaying(btnEl, true);

  try {
    const res = await fetch(`${API_BASE}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: clean, voiceId: getPollyVoice() }),
    });

    if (!res.ok) throw new Error(`TTS API error: ${res.status}`);

    const { audio, contentType } = await res.json();
    const bytes    = Uint8Array.from(atob(audio), c => c.charCodeAt(0));
    const blob     = new Blob([bytes], { type: contentType || 'audio/mpeg' });
    const url      = URL.createObjectURL(blob);

    const audioEl  = new Audio(url);
    _currentAudio  = audioEl;

    audioEl.onended = () => {
      URL.revokeObjectURL(url);
      _setPlaying(btnEl, false);
    };
    audioEl.onerror = () => {
      URL.revokeObjectURL(url);
      _setPlaying(btnEl, false);
    };

    await audioEl.play();

  } catch (err) {
    console.error('TTS error:', err);
    _setPlaying(btnEl, false);
  }
}

// ─── Public API ───────────────────────────────────────────────────────────

/**
 * Speak text. If already playing for this button, stop it (toggle).
 * @param {string}      text  — markdown text to speak (auto-stripped)
 * @param {HTMLElement} btnEl — the speaker button that triggered this
 */
export function speak(text, btnEl) {
  // Toggle off if this button is currently playing
  if (btnEl && btnEl.classList.contains('playing')) {
    stopAll();
    return;
  }
  if (DEV_MODE) {
    speakDev(text, btnEl);
  } else {
    speakProd(text, btnEl);
  }
}

export { stopAll };

export async function playStatic(url, btnEl) {
  // Toggle off if this button is currently playing
  if (btnEl && btnEl.classList.contains('playing')) {
    stopAll();
    return;
  }
  
  stopAll();
  _setPlaying(btnEl, true);

  try {
    const audioEl  = new Audio(url);
    _currentAudio  = audioEl;

    audioEl.onended = () => {
      _setPlaying(btnEl, false);
    };
    audioEl.onerror = () => {
      _setPlaying(btnEl, false);
    };

    await audioEl.play();
  } catch (err) {
    console.error('TTS static play error:', err);
    _setPlaying(btnEl, false);
  }
}
