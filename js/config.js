/**
 * config.js — Global configuration for Paleo Earth
 *
 * ┌─────────────────────────────────────────────────────────┐
 * │  DEV_MODE = true  → local development, no AWS needed    │
 * │  DEV_MODE = false → production mode, calls Lambda APIs  │
 * └─────────────────────────────────────────────────────────┘
 *
 * For local testing:
 *   python -m http.server 8000
 *   open http://localhost:8000
 */

// ─── Mode switch ────────────────────────────────────────────────────────
export const DEV_MODE = false;

// AWS API Gateway base URL
export const API_BASE = 'https://zazc8i568e.execute-api.us-east-1.amazonaws.com/prod';

// Amazon Polly neural voice ID used for TTS
export const POLLY_VOICE_ID = 'Matthew';

// ─── Keyframe Hero Illustrations ──────────────────────────────────────────
// Master feature flag for displaying hero mood illustrations in the summary card.
// Set to false to disable this feature globally across the entire app.
export const ENABLE_KEYFRAME_HERO_IMAGES = true;

// ─── Time range ──────────────────────────────────────────────────────────
export const MIN_MA = 0;
export const MAX_MA = 540;

// ─── Texture manifest ────────────────────────────────────────────────────
// All 109 diffuse texture frames at strict 5-million-year intervals (0 to 540 Ma).
// Format: [index (1-109), ma (0-540)]
export const TEXTURE_FRAMES = Array.from({ length: 109 }, (_, i) => [i + 1, i * 5]);

/**
 * Build texture file paths for a given frame entry.
 * @param {number} index  — texture sequence index (1-109)
 * @param {number} ma     — age in millions of years (0-540)
 * @returns {string}
 */
export function diffusePath(index, ma) {
  return `textures/${index}_earth_diffuse_${ma}.jpg`;
}

export function normalPath(index, ma) {
  return `textures/${index}_earth_normal_${ma}.jpg`;
}

export function roughnessPath(index, ma) {
  return `textures/${index}_earth_rough_${ma}.jpg`;
}

// Backwards compatibility alias
export const texturePath = diffusePath;

/**
 * Find the discrete texture frame for a given Ma value.
 * Hard jumps occur at the 2.5 Ma midpoint (e.g. 0-2 Ma -> 0 Ma, 3-7 Ma -> 5 Ma).
 *
 * @param {number} ma  — current slider value in Ma
 * @returns {{ index: number, ma: number }}
 */
export function getFrameForMa(ma) {
  const clampedMa = Math.min(MAX_MA, Math.max(MIN_MA, Number(ma) || 0));
  const snappedMa = Math.round(clampedMa / 5) * 5;
  const index     = (snappedMa / 5) + 1;
  return { index, ma: snappedMa };
}

// ─── Keyframe detection threshold ───────────────────────────────────────
// How close (in Ma) the slider must be to an event keyframe to snap to it.
export const PERIOD_SNAP_RADIUS = 8;  // Ma
export const EVENT_SNAP_RADIUS  = 5;  // Ma

// Debounce delay (ms) after slider stops before updating chat context divider
export const SLIDER_DEBOUNCE_MS = 300;

// Texture cache size (number of frames kept in GPU memory; each frame has diffuse, normal, rough)
export const TEXTURE_CACHE_SIZE = 10;

// Normal map strength in the shader (0.10 = 10% strength, reducing harsh relief shading)
export const NORMAL_MAP_SCALE = 0.10;
