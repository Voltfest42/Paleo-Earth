/**
 * gauges.js — SVG arc gauges for O₂, CO₂, and Temperature
 *
 * Each gauge is a 270° arc. The fill animates smoothly when
 * updateGauges() is called with new climate data.
 */

// ─── Gauge definitions ───────────────────────────────────────────────────
const GAUGE_DEFS = [
  {
    key:    'o2',
    label:  'O₂',
    unit:   '%',
    min:    -2.0,   // Sets floor so minimum O2 (1.8%) sits at ~10% of the dial
    max:    37.3,   // Exact dataset maximum (37.24%) fills the gauge to 100%
    format: v => `${Math.max(0, v).toFixed(1)}%`,
    // Colour stops: [value, hsl-hue]  (green=120, blue=210, yellow=45, red=0)
    colorStops: [
      [2,    210], // blue (anoxic early Cambrian)
      [10,   160], // teal
      [21,   120], // green (normal modern)
      [30,   45],  // yellow (high)
      [37,   0],   // red (Carboniferous/Permian peak)
    ],
  },
  {
    key:    'co2',
    label:  'CO₂',
    unit:   'ppm',
    min:    -250,   // Sets floor so minimum CO2 (220 ppm) sits at ~10% of the dial
    max:    4850,   // Exact dataset maximum (4,850 ppm) fills the gauge to 100%
    format: v => v >= 1000 ? `${(v/1000).toFixed(1)}k` : `${Math.round(v)}`,
    colorStops: [
      [220,  120], // green (Pleistocene/icehouse)
      [420,  100], // yellow-green (modern)
      [1000, 60],  // yellow
      [2500, 30],  // orange
      [4850, 0],   // red (Cambrian peak)
    ],
  },
  {
    key:    'temp',
    label:  'Temp',
    unit:   '°C',
    min:    5.5,    // Sets floor so minimum Temp (8.1°C) sits at ~10% of the dial
    max:    33.0,   // Exact dataset maximum (32.86°C) fills the gauge to 100%
    format: v => `${v.toFixed(1)}°`,
    colorStops: [
      [8,    210], // blue (icehouse cold)
      [14,   120], // green (modern temperate)
      [22,   60],  // yellow (warm greenhouse)
      [28,   25],  // orange
      [33,   0],   // red (Permian-Triassic hyperthermal)
    ],
  },
];

// ─── SVG arc geometry ─────────────────────────────────────────────────────
const R      = 34;          // arc radius
const CX     = 50;          // centre X
const CY     = 52;          // centre Y (slightly low to give room for value)
const START_DEG = 225;      // arc starts at 225° (bottom-left)
const TOTAL_DEG = 270;      // arc spans 270°
const CIRC   = 2 * Math.PI * R;
const ARC_LEN = (TOTAL_DEG / 360) * CIRC; // length of the 270° arc

function degToRad(d) { return (d * Math.PI) / 180; }

function polarToXY(angleDeg, r = R) {
  const rad = degToRad(angleDeg - 90); // SVG 0° = top
  return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)];
}

function arcPath(startDeg, spanDeg, r = R) {
  const [x1, y1] = polarToXY(startDeg, r);
  const [x2, y2] = polarToXY(startDeg + spanDeg, r);
  const large     = spanDeg > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
}

/** Interpolate hue from stops table */
function valueToHue(value, stops) {
  value = Math.max(stops[0][0], Math.min(stops[stops.length - 1][0], value));
  for (let i = 0; i < stops.length - 1; i++) {
    const [v0, h0] = stops[i];
    const [v1, h1] = stops[i + 1];
    if (value >= v0 && value <= v1) {
      const t = (value - v0) / (v1 - v0);
      return h0 + t * (h1 - h0);
    }
  }
  return stops[stops.length - 1][1];
}

// ─── GaugeSet class ──────────────────────────────────────────────────────
export class GaugeSet {
  /**
   * @param {HTMLElement} container — .climate-gauges div
   */
  constructor(container) {
    this._container = container;
    this._gauges    = {};
    this._build();
  }

  _build() {
    for (const def of GAUGE_DEFS) {
      const wrap = document.createElement('div');
      wrap.className = 'gauge-wrap';

      const trackPath = arcPath(START_DEG, TOTAL_DEG);
      const fillPath  = arcPath(START_DEG, TOTAL_DEG); // same path, dashoffset controls fill

      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 100 70');
      svg.setAttribute('aria-label', `${def.label} gauge`);
      svg.innerHTML = `
        <path class="gauge-track" d="${trackPath}" stroke-width="5"/>
        <path class="gauge-fill"  id="fill-${def.key}" d="${fillPath}"
          stroke-width="5"
          stroke-dasharray="${ARC_LEN}"
          stroke-dashoffset="${ARC_LEN}"
          stroke="hsl(120,70%,45%)"/>
        <text x="${CX}" y="${CY + 4}" text-anchor="middle"
          font-size="10" font-weight="700" fill="#e8edf5"
          id="val-${def.key}">--</text>
        <text x="${CX}" y="${CY + 16}" text-anchor="middle"
          font-size="7" fill="#7a91b5">${def.unit}</text>
      `;

      // Desktop Arc Gauge
      const arcWrap = document.createElement('div');
      arcWrap.className = 'arc-gauge';
      
      const label = document.createElement('div');
      label.className = 'gauge-label';
      label.textContent = def.label;
      
      arcWrap.appendChild(svg);
      arcWrap.appendChild(label);

      // Mobile Bar Gauge
      const barWrap = document.createElement('div');
      barWrap.className = 'bar-gauge';
      barWrap.innerHTML = `
        <div class="bar-label">${def.label}</div>
        <div class="bar-track">
          <div class="bar-fill" id="bar-fill-${def.key}"></div>
        </div>
        <div class="bar-value" id="bar-val-${def.key}">-- ${def.unit}</div>
      `;

      wrap.appendChild(arcWrap);
      wrap.appendChild(barWrap);
      this._container.appendChild(wrap);

      this._gauges[def.key] = {
        def,
        fillEl:  svg.getElementById(`fill-${def.key}`),
        valueEl: svg.getElementById(`val-${def.key}`),
        barFillEl: barWrap.querySelector(`#bar-fill-${def.key}`),
        barValueEl: barWrap.querySelector(`#bar-val-${def.key}`),
        current: (def.min + def.max) / 2,
        target:  (def.min + def.max) / 2,
        rafId:   null,
      };
    }
  }

  /**
   * Animate all gauges to new climate values.
   * @param {{ o2Percent: number, co2Ppm: number, tempC: number }} data
   */
  updateGauges(data) {
    const map = { o2: data.o2Percent, co2: data.co2Ppm, temp: data.tempC };
    for (const [key, g] of Object.entries(this._gauges)) {
      g.target = map[key] ?? g.target;
      this._animateGauge(key);
    }
  }

  _animateGauge(key) {
    const g = this._gauges[key];
    cancelAnimationFrame(g.rafId);

    const tick = () => {
      const diff = g.target - g.current;
      if (Math.abs(diff) < 0.005) {
        g.current = g.target;
        this._renderGauge(key);
        return;
      }
      g.current += diff * 0.08;
      this._renderGauge(key);
      g.rafId = requestAnimationFrame(tick);
    };

    g.rafId = requestAnimationFrame(tick);
  }

  _renderGauge(key) {
    const g = this._gauges[key];
    const { def, fillEl, valueEl, barFillEl, barValueEl, current } = g;

    const fraction = Math.max(0, Math.min(1, (current - def.min) / (def.max - def.min)));
    const offset   = ARC_LEN * (1 - fraction);
    fillEl.setAttribute('stroke-dashoffset', offset.toFixed(2));

    const hue   = valueToHue(current, def.colorStops);
    const sat   = 65 + fraction * 15;
    const light = 42 + fraction * 8;
    const colorStr = `hsl(${Math.round(hue)},${Math.round(sat)}%,${Math.round(light)}%)`;
    
    fillEl.setAttribute('stroke', colorStr);
    valueEl.textContent = def.format(current);

    // Update Mobile Bar Gauge
    barFillEl.style.width = `${fraction * 100}%`;
    barFillEl.style.backgroundColor = colorStr;
    barValueEl.textContent = `${def.format(current)} ${def.unit}`;
  }

  /** Set all gauges immediately without animation (for instant page load) */
  setGaugesImmediate(data) {
    const map = { o2: data.o2Percent, co2: data.co2Ppm, temp: data.tempC };
    for (const [key, g] of Object.entries(this._gauges)) {
      g.current = g.target = map[key] ?? g.current;
      this._renderGauge(key);
    }
  }
}
