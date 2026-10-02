/**
 * globe.js — Three.js globe with discrete texture frame switching
 *
 * Uses MeshStandardMaterial for high-fidelity PBR rendering and lighting.
 * Atmosphere is rendered via a dedicated additive Fresnel shell that stays
 * strictly locked to the silhouette rim at all camera rotations and angles.
 *
 * Normal map and roughness map slots are present but commented out —
 * ready to uncomment when those textures are available in textures/.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import {
  TEXTURE_CACHE_SIZE,
  NORMAL_MAP_SCALE,
  GLOBE_AMBIENT_LIGHT,
  GLOBE_SUN_LIGHT,
  GLOBE_SHADOW_LIFT_GAMMA,
  getFrameForMa,
  diffusePath,
  normalPath,
  roughnessPath,
  bordersPath,
  GLOBE_BORDERS_COLOR,
} from './config.js';

// ─── Atmosphere Fresnel Shaders (Pure View Space) ───────────────────────
const ATMO_VERT = /* glsl */`
  varying vec3 vViewNormal;
  varying vec3 vViewPosition;

  void main() {
    vViewNormal   = normalize(normalMatrix * normal);
    vec4 mvPos    = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPos.xyz;
    gl_Position   = projectionMatrix * mvPos;
  }
`;

const ATMO_FRAG = /* glsl */`
  varying vec3 vViewNormal;
  varying vec3 vViewPosition;

  void main() {
    vec3 N = normalize(vViewNormal);
    vec3 V = normalize(vViewPosition);

    // In View Space, facing the camera directly gives dotNV = 1.0 -> fresnel = 0.0 (fully transparent)
    // Grazing silhouette edges give dotNV -> 0.0 -> fresnel -> 1.0 (crisp glowing rim)
    float dotNV = dot(N, V);
    if (dotNV <= 0.0) discard;

    float fresnel = pow(1.0 - dotNV, 3.5);
    vec3 atmoColor = vec3(0.38, 0.68, 1.0);

    gl_FragColor = vec4(atmoColor, fresnel * 0.7);
  }
`;

// ─── LRU texture cache ──────────────────────────────────────────────────
class TextureCache {
  constructor(loader, maxSize) {
    this._loader    = loader;
    this._maxSize   = maxSize;
    this._map       = new Map();
    this._pending   = new Map();
    this._activeKey = null;
  }

  has(key) {
    return this._map.has(key);
  }

  isPending(key) {
    return this._pending.has(key);
  }

  setActiveKey(key) {
    this._activeKey = key;
    if (this._map.has(key)) {
      this._map.get(key).lastUsed = Date.now();
    }
  }

  async getFrame(index, ma) {
    const key = `${index}_${ma}`;
    if (this._map.has(key)) {
      const entry = this._map.get(key);
      entry.lastUsed = Date.now();
      return entry;
    }

    if (this._pending.has(key)) {
      return this._pending.get(key);
    }

    const promise = Promise.all([
      this._load(diffusePath(index, ma)),
      this._load(normalPath(index, ma)),
      this._load(roughnessPath(index, ma)),
    ]).then(([diffuse, normal, roughness]) => {
      this._pending.delete(key);

      diffuse.colorSpace   = THREE.SRGBColorSpace;
      normal.colorSpace    = THREE.NoColorSpace;
      roughness.colorSpace = THREE.NoColorSpace;

      const entry = { diffuse, normal, roughness, lastUsed: Date.now() };
      this._map.set(key, entry);
      this._evict();
      return entry;
    }).catch(err => {
      this._pending.delete(key);
      throw err;
    });

    this._pending.set(key, promise);
    return promise;
  }

  preload(index, ma) {
    const key = `${index}_${ma}`;
    if (this._map.has(key) || this._pending.has(key)) return;
    this.getFrame(index, ma).catch(() => {});
  }

  _load(path) {
    return new Promise((resolve, reject) => {
      this._loader.load(path, resolve, undefined, reject);
    });
  }

  _evict() {
    while (this._map.size > this._maxSize) {
      let oldest = Infinity, oldestKey = null;
      for (const [key, entry] of this._map) {
        if (key === this._activeKey) continue;
        if (entry.lastUsed < oldest) {
          oldest = entry.lastUsed;
          oldestKey = key;
        }
      }
      if (!oldestKey) break;
      const entry = this._map.get(oldestKey);
      if (entry.diffuse) entry.diffuse.dispose();
      if (entry.normal) entry.normal.dispose();
      if (entry.roughness) entry.roughness.dispose();
      this._map.delete(oldestKey);
    }
  }

  dispose() {
    for (const entry of this._map.values()) {
      if (entry.diffuse) entry.diffuse.dispose();
      if (entry.normal) entry.normal.dispose();
      if (entry.roughness) entry.roughness.dispose();
    }
    this._map.clear();
    this._pending.clear();
  }
}

// ─── LRU border texture cache ───────────────────────────────────────────
class BorderTextureCache {
  constructor(loader, maxSize) {
    this._loader  = loader;
    this._maxSize = maxSize;
    this._map     = new Map();
    this._pending = new Map();
  }

  has(key) {
    return this._map.has(key);
  }

  async getBorder(index, ma) {
    const key = `${index}_${ma}`;
    if (this._map.has(key)) {
      const tex = this._map.get(key);
      tex.lastUsed = Date.now();
      return tex;
    }

    if (this._pending.has(key)) {
      return this._pending.get(key);
    }

    const promise = this._load(bordersPath(index, ma)).then(tex => {
      this._pending.delete(key);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.lastUsed   = Date.now();
      this._map.set(key, tex);
      this._evict();
      return tex;
    }).catch(err => {
      this._pending.delete(key);
      throw err;
    });

    this._pending.set(key, promise);
    return promise;
  }

  preload(index, ma) {
    const key = `${index}_${ma}`;
    if (this._map.has(key) || this._pending.has(key)) return;
    this.getBorder(index, ma).catch(() => {});
  }

  _load(path) {
    return new Promise((resolve, reject) => {
      this._loader.load(path, resolve, undefined, reject);
    });
  }

  _evict() {
    while (this._map.size > this._maxSize) {
      let oldest = Infinity, oldestKey = null;
      for (const [key, tex] of this._map) {
        if (tex.lastUsed < oldest) {
          oldest = tex.lastUsed;
          oldestKey = key;
        }
      }
      if (!oldestKey) break;
      const tex = this._map.get(oldestKey);
      tex.dispose();
      this._map.delete(oldestKey);
    }
  }

  dispose() {
    for (const tex of this._map.values()) {
      tex.dispose();
    }
    this._map.clear();
    this._pending.clear();
  }
}

// ─── Globe class ────────────────────────────────────────────────────────
export class Globe {
  constructor(container) {
    this._container           = container;
    this._animId              = null;
    this._ticket              = 0;
    this._appliedTicket       = 0;
    this._targetMa            = null;
    this._displayedMa         = null;
    this._debounceTimer       = null;

    // Political borders overlay state
    this._showBorders          = false;
    this._targetBordersOpacity = 0.0;

    this._init();
    this._buildStars();
    this._buildGlobe();
    this._buildAtmosphere();
    this._addLights();
    this._setupControls();
    this._setupResize();
    this._animate();
  }

  // ── Scene / renderer ──────────────────────────────────────────────────
  _init() {
    const w = this._container.clientWidth;
    const h = this._container.clientHeight;

    this._scene    = new THREE.Scene();
    this._camera   = new THREE.PerspectiveCamera(40, w / h, 0.1, 1000);
    // Halfway point between close-up (2.8) and max zoom-out (6.0) for comfortable full-globe framing
    this._camera.position.set(0, 0, 4.4);

    this._renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this._renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this._renderer.setSize(w, h);
    this._renderer.outputColorSpace = THREE.SRGBColorSpace;
    this._renderer.toneMapping = THREE.LinearToneMapping;
    this._renderer.toneMappingExposure = 1.0;
    this._container.appendChild(this._renderer.domElement);

    this._loader       = new THREE.TextureLoader();
    this._cache        = new TextureCache(this._loader, TEXTURE_CACHE_SIZE);
    this._bordersCache = new BorderTextureCache(this._loader, TEXTURE_CACHE_SIZE);
  }

  // ── Stars ─────────────────────────────────────────────────────────────
  _buildStars() {
    const count  = 8000;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) {
      positions[i] = (Math.random() - 0.5) * 400;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.3,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.7,
    });
    this._scene.add(new THREE.Points(geo, mat));
  }

  // ── Globe mesh (Standard Material) ────────────────────────────────────
  _buildGlobe() {
    // 1x1 initial placeholders so Three.js compiles the PBR shader program with all
    // three map channels (map, normalMap, roughnessMap) active immediately at startup.
    const diffusePlaceholder = new THREE.DataTexture(
      new Uint8Array([10, 15, 30, 255]),
      1, 1, THREE.RGBAFormat
    );
    diffusePlaceholder.needsUpdate = true;

    // Flat tangent-space normal (0.5, 0.5, 1.0) -> RGB (128, 128, 255)
    const normalPlaceholder = new THREE.DataTexture(
      new Uint8Array([128, 128, 255, 255]),
      1, 1, THREE.RGBAFormat
    );
    normalPlaceholder.needsUpdate = true;

    // Neutral mid-roughness placeholder (180/255 ≈ 0.70)
    const roughPlaceholder = new THREE.DataTexture(
      new Uint8Array([180, 180, 180, 255]),
      1, 1, THREE.RGBAFormat
    );
    roughPlaceholder.needsUpdate = true;

    // Transparent 1x1 initial placeholder for political borders overlay
    const bordersPlaceholder = new THREE.DataTexture(
      new Uint8Array([0, 0, 0, 0]),
      1, 1, THREE.RGBAFormat
    );
    bordersPlaceholder.needsUpdate = true;

    // Uniforms object shared between Three.js shader and Globe controller
    this._customUniforms = {
      bordersMap:     { value: bordersPlaceholder },
      bordersOpacity: { value: 0.0 },
      bordersColor:   { value: new THREE.Color(GLOBE_BORDERS_COLOR) },
    };

    this._globeMaterial = new THREE.MeshStandardMaterial({
      map:           diffusePlaceholder,
      normalMap:     normalPlaceholder,
      normalMapType: THREE.TangentSpaceNormalMap,
      normalScale:   new THREE.Vector2(NORMAL_MAP_SCALE, NORMAL_MAP_SCALE),
      roughnessMap:  roughPlaceholder,
      roughness:     1.0,
      metalness:     0.0,
    });

    // Shader hook: inject border overlay and shadow softening
    this._globeMaterial.onBeforeCompile = (shader) => {
      // Connect custom uniforms
      shader.uniforms.bordersMap     = this._customUniforms.bordersMap;
      shader.uniforms.bordersOpacity = this._customUniforms.bordersOpacity;
      shader.uniforms.bordersColor   = this._customUniforms.bordersColor;

      // Declare uniforms in fragment shader header
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <map_pars_fragment>',
        /* glsl */`
        #include <map_pars_fragment>
        uniform sampler2D bordersMap;
        uniform float bordersOpacity;
        uniform vec3 bordersColor;
        `
      );

      // Blend border overlay over diffuseColor
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <map_fragment>',
        /* glsl */`
        #ifdef USE_MAP
          vec4 sampledDiffuseColor = texture2D( map, vMapUv );
          #ifdef DECODE_VIDEO_TEXTURE
            sampledDiffuseColor = vec4( mix( pow( sampledDiffuseColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), sampledDiffuseColor.rgb * 0.0773993808, vec3( lessThanEqual( sampledDiffuseColor.rgb, vec3( 0.04045 ) ) ) ), sampledDiffuseColor.w );
          #endif
          // Soften deep shadow crevices in the texture to eliminate harsh cratering
          #if ${GLOBE_SHADOW_LIFT_GAMMA < 1.0 ? '1' : '0'}
            sampledDiffuseColor.rgb = pow(sampledDiffuseColor.rgb, vec3(${GLOBE_SHADOW_LIFT_GAMMA.toFixed(2)}));
          #endif
          diffuseColor *= sampledDiffuseColor;

          // Political border overlay: sample luminance (red channel) from B&W border texture and blend
          if (bordersOpacity > 0.0) {
            vec4 borderSample = texture2D( bordersMap, vMapUv );
            vec3 bLineCol = bordersColor;
            diffuseColor.rgb = mix( diffuseColor.rgb, bLineCol, borderSample.r * bordersOpacity );
          }
        #endif
        `
      );
    };

    const geo = new THREE.SphereGeometry(1, 128, 64);
    this._globe = new THREE.Mesh(geo, this._globeMaterial);
    this._scene.add(this._globe);
  }

  // ── Atmosphere Rim Glow (Dedicated Additive Layer) ────────────────────
  _buildAtmosphere() {
    const geo = new THREE.SphereGeometry(1.012, 64, 32);
    const mat = new THREE.ShaderMaterial({
      vertexShader:   ATMO_VERT,
      fragmentShader: ATMO_FRAG,
      blending:       THREE.AdditiveBlending,
      transparent:    true,
      depthWrite:     false,
      side:           THREE.FrontSide,
    });
    this._atmoMesh = new THREE.Mesh(geo, mat);
    this._scene.add(this._atmoMesh);
  }

  // ── Lights ────────────────────────────────────────────────────────────
  _addLights() {
    // Balanced ambient light so terrain colors, coastlines, and shadowed slopes
    // remain visible, readable, and true to their authored brightness:
    this._ambientLight = new THREE.AmbientLight(0xffffff, GLOBE_AMBIENT_LIGHT);
    this._scene.add(this._ambientLight);

    // Directional key light mounted to the camera: provides subtle 3D curvature,
    // gentle relief enhancement, and ocean specular glints without harsh contrast
    this._sunLight = new THREE.DirectionalLight(0xfff8ee, GLOBE_SUN_LIGHT);
    this._sunLight.position.set(1.8, 1.8, 2.5);
    this._sunLight.target.position.set(0, 0, 0);

    this._camera.add(this._sunLight);
    this._camera.add(this._sunLight.target);
    this._scene.add(this._camera);
  }

  // ── OrbitControls ─────────────────────────────────────────────────────
  _setupControls() {
    this._controls = new OrbitControls(this._camera, this._renderer.domElement);
    this._controls.enableDamping    = true;
    this._controls.dampingFactor    = 0.08;
    this._controls.enablePan        = false;
    this._controls.minDistance      = 1.4;
    this._controls.maxDistance      = 6.0;
    this._controls.rotateSpeed      = 0.5;
    this._controls.autoRotate       = true;
    this._controls.autoRotateSpeed  = 0.4;

    // Stop auto-rotation while dragging
    this._renderer.domElement.addEventListener('pointerdown', () => {
      this._controls.autoRotate = false;
    });
    this._renderer.domElement.addEventListener('pointerup', () => {
      setTimeout(() => { this._controls.autoRotate = true; }, 4000);
    });
  }

  // ── Resize handler ────────────────────────────────────────────────────
  _setupResize() {
    this._resizeObserver = new ResizeObserver(() => {
      const w = this._container.clientWidth;
      const h = this._container.clientHeight;
      this._camera.aspect = w / h;
      this._camera.updateProjectionMatrix();
      this._renderer.setSize(w, h);
    });
    this._resizeObserver.observe(this._container);
  }

  // ── Animation loop ────────────────────────────────────────────────────
  _animate() {
    this._animId = requestAnimationFrame(() => this._animate());

    // Smooth transition for political borders opacity
    if (this._customUniforms && this._customUniforms.bordersOpacity) {
      const cur = this._customUniforms.bordersOpacity.value;
      const tgt = this._targetBordersOpacity;
      if (Math.abs(cur - tgt) > 0.002) {
        this._customUniforms.bordersOpacity.value += (tgt - cur) * 0.18;
      } else if (cur !== tgt) {
        this._customUniforms.bordersOpacity.value = tgt;
      }
    }

    this._controls.update();
    this._renderer.render(this._scene, this._camera);
  }

  // ── Public API ────────────────────────────────────────────────────────

  /**
   * Load and display the discrete globe textures (diffuse, normal, roughness)
   * for the given Ma value. Switches cleanly at 2.5 Ma midpoints.
   *
   * Employs ticket-based monotonic updates, lookahead preloading, and
   * scrub debouncing to prevent network saturation and frame discarding.
   *
   * @param {number} ma — age in millions of years (0-540)
   * @param {string} source — 'play' | 'drag' | 'settle' | 'direct'
   */
  setMa(ma, source = 'direct') {
    const { index, ma: snappedMa } = getFrameForMa(ma);

    // If already targeting this discrete frame, return early
    if (this._targetMa === snappedMa) {
      return Promise.resolve();
    }

    const prevTargetMa = this._targetMa;
    this._targetMa = snappedMa;
    const key = `${index}_${snappedMa}`;
    const isForward = prevTargetMa === null || snappedMa >= prevTargetMa;

    // Clear any pending scrub debounce timer
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = null;
    }

    // Fast path:
    // If playback ('play'), drag release ('settle'), programmatic jump ('direct'),
    // initial load (prevTargetMa === null), or texture already cached/pending:
    // Fetch and apply immediately with 0 delay!
    if (
      source === 'play' ||
      source === 'settle' ||
      source === 'direct' ||
      prevTargetMa === null ||
      this._cache.has(key) ||
      this._cache.isPending(key)
    ) {
      return this._fetchAndApply(index, snappedMa, key, isForward);
    }

    // Drag path: user is actively scrubbing across uncached frames.
    // Debounce by 90ms so rapid dragging doesn't flood the browser connection pool
    // with dozens of requests for frames that are dragged past in milliseconds.
    return new Promise((resolve) => {
      this._debounceTimer = setTimeout(() => {
        this._debounceTimer = null;
        resolve(this._fetchAndApply(index, snappedMa, key, isForward));
      }, 90);
    });
  }

  async _fetchAndApply(index, snappedMa, key, isForward) {
    const ticket = ++this._ticket;

    try {
      const framePromise = this._cache.getFrame(index, snappedMa);
      const borderPromise = this._showBorders ? this._bordersCache.getBorder(index, snappedMa) : Promise.resolve(null);
      
      const [frame, borderTex] = await Promise.all([framePromise, borderPromise]);

      // Discard only if a strictly newer frame has ALREADY been applied to the globe
      if (ticket < this._appliedTicket) {
        return;
      }

      this._appliedTicket = ticket;
      this._displayedMa   = snappedMa;
      this._cache.setActiveKey(key);

      this._globeMaterial.map          = frame.diffuse;
      this._globeMaterial.normalMap    = frame.normal;
      this._globeMaterial.roughnessMap = frame.roughness;
      
      if (borderTex) {
        this._customUniforms.bordersMap.value = borderTex;
      }
      
      this._globeMaterial.needsUpdate  = true;

      // Lookahead preload:
      // Only preload if the globe has caught up with the current targetMa.
      // If the user already moved on, don't waste network requests on this frame's neighbors.
      if (this._targetMa === snappedMa) {
        if (isForward && snappedMa < 540) {
          const nextMa = snappedMa + 5;
          const nextIndex = (nextMa / 5) + 1;
          this._cache.preload(nextIndex, nextMa);
          if (this._showBorders) this._bordersCache.preload(nextIndex, nextMa);
        } else if (!isForward && snappedMa > 0) {
          const prevMa = snappedMa - 5;
          const prevIndex = (prevMa / 5) + 1;
          this._cache.preload(prevIndex, prevMa);
          if (this._showBorders) this._bordersCache.preload(prevIndex, prevMa);
        }
      }
    } catch (err) {
      console.warn(`Globe textures load failed for frame ${index} (${snappedMa} Ma):`, err);
      if (this._targetMa === snappedMa && this._displayedMa !== snappedMa) {
        this._targetMa = this._displayedMa;
      }
    }
  }

  async _loadAndApplyBorder(index, snappedMa, ticket) {
    try {
      const borderTex = await this._bordersCache.getBorder(index, snappedMa);
      if (ticket < this._appliedTicket) return;
      this._customUniforms.bordersMap.value = borderTex;
    } catch (err) {
      console.warn(`Border texture load failed for frame ${index} (${snappedMa} Ma):`, err);
    }
  }

  /**
   * Toggle political borders overlay on/off.
   * @returns {boolean} current enabled state
   */
  toggleBorders() {
    return this.setBordersEnabled(!this._showBorders);
  }

  /**
   * Enable or disable political borders overlay.
   * @param {boolean} enabled
   * @returns {boolean}
   */
  setBordersEnabled(enabled) {
    this._showBorders = !!enabled;
    this._targetBordersOpacity = this._showBorders ? 1.0 : 0.0;

    if (this._showBorders) {
      const currentMa = this._displayedMa !== null ? this._displayedMa : (this._targetMa !== null ? this._targetMa : 0);
      const { index, ma: snappedMa } = getFrameForMa(currentMa);
      this._loadAndApplyBorder(index, snappedMa, this._appliedTicket);
    }
    return this._showBorders;
  }

  /**
   * Get current political borders overlay state.
   * @returns {boolean}
   */
  getBordersEnabled() {
    return this._showBorders;
  }

  /**
   * Set color for political borders (default: #ffffff).
   * @param {number|string|THREE.Color} color
   */
  setBorderColor(color) {
    if (this._customUniforms && this._customUniforms.bordersColor) {
      this._customUniforms.bordersColor.value.set(color);
    }
  }

  /**
   * Dynamically adjust normal map strength.
   * @param {number} scale — e.g. 0.10 for 10% strength
   */
  setNormalScale(scale) {
    this._globeMaterial.normalScale.set(scale, scale);
  }

  reloadTextures() {
    // Clear LRU caches fully
    this._cache._map.forEach(entry => {
      if (entry.diffuse) entry.diffuse.dispose();
      if (entry.normal) entry.normal.dispose();
      if (entry.roughness) entry.roughness.dispose();
    });
    this._cache._map.clear();
    this._cache._pending.clear();
    
    this._bordersCache._map.forEach(tex => tex.dispose());
    this._bordersCache._map.clear();
    this._bordersCache._pending.clear();

    // Re-apply current frame to trigger fresh fetch
    if (this._targetMa !== null) {
      this.setMa(this._targetMa, 'direct');
    }
  }

  /** Show/hide the loading overlay */
  setLoading(visible) {
    const el = document.getElementById('globeLoading');
    if (el) el.classList.toggle('hidden', !visible);
  }

  /** Clean up scene and renderer */
  dispose() {
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = null;
    }
    cancelAnimationFrame(this._animId);
    this._resizeObserver.disconnect();
    this._controls.dispose();
    this._cache.dispose();
    this._bordersCache.dispose();
    this._renderer.dispose();
    this._container.removeChild(this._renderer.domElement);
  }
}
