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
import { TEXTURE_CACHE_SIZE, getFrameForMa, texturePath } from './config.js';

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
    this._loader  = loader;
    this._maxSize = maxSize;
    this._map     = new Map();
  }

  async get(index, ma) {
    const key = `${index}_${ma}`;
    if (this._map.has(key)) {
      this._map.get(key).lastUsed = Date.now();
      return this._map.get(key).texture;
    }

    const texture = await this._load(texturePath(index, ma));
    this._map.set(key, { texture, lastUsed: Date.now() });
    this._evict();
    return texture;
  }

  _load(path) {
    return new Promise((resolve, reject) => {
      this._loader.load(path, resolve, undefined, reject);
    });
  }

  _evict() {
    if (this._map.size <= this._maxSize) return;
    let oldest = Infinity, oldestKey = null;
    for (const [key, entry] of this._map) {
      if (entry.lastUsed < oldest) { oldest = entry.lastUsed; oldestKey = key; }
    }
    if (oldestKey) {
      this._map.get(oldestKey).texture.dispose();
      this._map.delete(oldestKey);
    }
  }

  dispose() {
    for (const { texture } of this._map.values()) texture.dispose();
    this._map.clear();
  }
}

// ─── Globe class ────────────────────────────────────────────────────────
export class Globe {
  constructor(container) {
    this._container = container;
    this._animId    = null;
    this._currentFrameMa = null;

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
    this._renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this._renderer.toneMappingExposure = 1.05;
    this._container.appendChild(this._renderer.domElement);

    this._loader = new THREE.TextureLoader();
    this._cache  = new TextureCache(this._loader, TEXTURE_CACHE_SIZE);
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
    const placeholder = new THREE.DataTexture(
      new Uint8Array([10, 15, 30]),
      1, 1, THREE.RGBFormat
    );
    placeholder.needsUpdate = true;

    this._globeMaterial = new THREE.MeshStandardMaterial({
      map:          placeholder,
      roughness:    0.7,
      metalness:    0.0,
      // ── Ready for normal & roughness maps:
      // normalMap:     normalTexture,
      // normalMapType: THREE.TangentSpaceNormalMap,
      // normalScale:   new THREE.Vector2(1.0, 1.0),
      // roughnessMap:  roughnessTexture,
    });

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
    // Ambient light: balanced so the shadowed side remains clearly visible and readable
    this._scene.add(new THREE.AmbientLight(0xdde8f5, 0.48));

    // Directional key light mounted to the camera: offset 45° to the right and 45° up
    this._sunLight = new THREE.DirectionalLight(0xfff8ee, 2.4);

    // Position light at 45° right (+X) and 45° up (+Y) relative to camera's view axis
    this._sunLight.position.set(2.8, 2.8, 0.0);
    this._sunLight.target.position.set(0, 0, -2.8);

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
    this._controls.update();
    this._renderer.render(this._scene, this._camera);
  }

  // ── Public API ────────────────────────────────────────────────────────

  /**
   * Load and display the discrete globe texture for the given Ma value.
   * Switches cleanly at 2.5 Ma midpoints.
   */
  async setMa(ma) {
    const { index, ma: snappedMa } = getFrameForMa(ma);

    if (this._currentFrameMa === snappedMa && this._globeMaterial.map) {
      return;
    }

    this._currentFrameMa = snappedMa;

    try {
      const tex = await this._cache.get(index, snappedMa);
      tex.colorSpace = THREE.SRGBColorSpace;
      this._globeMaterial.map = tex;
      this._globeMaterial.needsUpdate = true;
    } catch (err) {
      console.warn(`Globe texture load failed for ${index}_earth_diffuse_${snappedMa}.jpg:`, err);
    }
  }

  /** Show/hide the loading overlay */
  setLoading(visible) {
    const el = document.getElementById('globeLoading');
    if (el) el.classList.toggle('hidden', !visible);
  }

  /** Clean up scene and renderer */
  dispose() {
    cancelAnimationFrame(this._animId);
    this._resizeObserver.disconnect();
    this._controls.dispose();
    this._cache.dispose();
    this._renderer.dispose();
    this._container.removeChild(this._renderer.domElement);
  }
}
