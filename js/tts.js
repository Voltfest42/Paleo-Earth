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
    .replace(/\bK[-–—/]?Pg\b/gi, 'K-P-G')
    .replace(/\bK[-–—/]?T\b/gi, 'K-T')
    .replace(/\bP[-–—/]?Tr\b/gi, 'Permian-Triassic')
    .replace(/\bO[-–—/]?S\b/gi, 'Ordovician-Silurian')
    .replace(/\bPETM\b/g, 'P-E-T-M')

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
