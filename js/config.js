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

export function bordersPath(index, ma) {
  return `textures/${index}_earth_borders_${ma}.jpg`;
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
export const TEXTURE_CACHE_SIZE = 16;

// Timeline animation duration in seconds for full 0 to 540 Ma playback
// 24 seconds provides a smooth, cinematic cadence (~4.5 frames/sec) with ample lookahead headroom
export const SLIDER_PLAY_DURATION_SEC = 24.0;

// Normal map strength in the shader (0.10 = 10% strength, 0.0 = disabled)
export const NORMAL_MAP_SCALE = 0.1;

// ─── Globe Lighting & Shading Settings ───────────────────────────────────
// Ambient light intensity (higher keeps unlit terrain readable and prevents pitch-black shadows)
export const GLOBE_AMBIENT_LIGHT = 0.95;

// Directional sunlight intensity (soft key light for specular ocean glints and subtle 3D curvature)
export const GLOBE_SUN_LIGHT = 0.65;

// Shadow lift power applied in the shader to soften deep hillshade crevices
// 1.0 = untouched texture; 0.80 = lifts deep shadows while preserving bright summits
export const GLOBE_SHADOW_LIFT_GAMMA = 0.80;

// Political borders overlay color (0xffffff = crisp white, 0x000000 = black)
export const GLOBE_BORDERS_COLOR = 0xffffff;

// --- Geologic Time Scale Periods -----------------------------------------
// Used for the visual time bar above the slider. Values map exactly to the 0-540 Ma scale.
export const GEOLOGIC_PERIODS = [
  { id: 'Q',  name: 'Quaternary',    start: 0,      end: 2.6,    color: '249, 249, 127' },
  { id: 'N',  name: 'Neogene',       start: 2.6,    end: 23.0,   color: '255, 230, 25' },
  { id: 'Pg', name: 'Paleogene',     start: 23.0,   end: 66.0,   color: '253, 167, 95' },
  { id: 'K',  name: 'Cretaceous',    start: 66.0,   end: 145.0,  color: '127, 198, 78' },
  { id: 'J',  name: 'Jurassic',      start: 145.0,  end: 201.3,  color: '52, 178, 201' },
  { id: 'T',  name: 'Triassic',      start: 201.3,  end: 251.9,  color: '129, 43, 146' },
  { id: 'P',  name: 'Permian',       start: 251.9,  end: 298.9,  color: '240, 64, 40' },
  { id: 'C',  name: 'Carboniferous', start: 298.9,  end: 358.9,  color: '103, 165, 153' },
  { id: 'D',  name: 'Devonian',      start: 358.9,  end: 419.2,  color: '203, 140, 55' },
  { id: 'S',  name: 'Silurian',      start: 419.2,  end: 443.8,  color: '179, 225, 182' },
  { id: 'O',  name: 'Ordovician',    start: 443.8,  end: 485.4,  color: '0, 146, 112' },
  { id: '?',  name: 'Cambrian',      start: 485.4,  end: 540.0,  color: '127, 160, 86' }
];

