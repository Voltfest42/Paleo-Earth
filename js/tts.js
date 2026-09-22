/**
 * tts.js — Text-to-speech via Amazon Polly (prod) or browser API (dev)
 *
 * DEV_MODE = true  → uses window.speechSynthesis (no AWS needed)
 * DEV_MODE = false → calls POST /tts on the Lambda API, plays Polly MP3
 */

import { DEV_MODE, API_BASE, POLLY_VOICE_ID } from './config.js';

// Strip markdown before handing to TTS — avoids "asterisk asterisk" etc.
function stripMarkdown(text) {
  return text
    .replace(/#{1,6}\s+/g, '')          // headers
    .replace(/\*\*(.+?)\*\*/g, '$1')    // bold
    .replace(/\*(.+?)\*/g, '$1')        // italic
    .replace(/__(.+?)__/g, '$1')        // bold alt
    .replace(/_(.+?)_/g, '$1')          // italic alt
    .replace(/`(.+?)`/g, '$1')          // inline code
    .replace(/\[\[IMAGE:[^\]]*\]\]/gi, '') // image tags
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // links
    .replace(/[-*+]\s+/g, '')           // list markers
    .replace(/>\s+/g, '')               // blockquotes
    .replace(/\n{2,}/g, '. ')           // paragraph breaks → pause
    .replace(/\n/g, ' ')
    .trim();
}

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
      body: JSON.stringify({ text: clean, voiceId: POLLY_VOICE_ID }),
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
