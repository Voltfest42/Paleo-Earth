import sys

with open("js/gauges.js", "r", encoding="utf-8") as f:
    js = f.read()

find_build = """      const label = document.createElement('div');
      label.className = 'gauge-label';
      label.textContent = def.label;

      wrap.appendChild(svg);
      wrap.appendChild(label);
      this._container.appendChild(wrap);

      this._gauges[def.key] = {"""

replace_build = """      // Desktop Arc Gauge
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

      this._gauges[def.key] = {"""

js = js.replace(find_build, replace_build)

find_els = """        def,
        fillEl:  svg.getElementById(`fill-${def.key}`),
        valueEl: svg.getElementById(`val-${def.key}`),
        current: (def.min + def.max) / 2,"""

replace_els = """        def,
        fillEl:  svg.getElementById(`fill-${def.key}`),
        valueEl: svg.getElementById(`val-${def.key}`),
        barFillEl: barWrap.querySelector(`#bar-fill-${def.key}`),
        barValueEl: barWrap.querySelector(`#bar-val-${def.key}`),
        current: (def.min + def.max) / 2,"""

js = js.replace(find_els, replace_els)

find_render = """    const { def, fillEl, valueEl, current } = g;

    const fraction = Math.max(0, Math.min(1, (current - def.min) / (def.max - def.min)));
    const offset   = ARC_LEN * (1 - fraction);
    fillEl.setAttribute('stroke-dashoffset', offset.toFixed(2));

    const hue   = valueToHue(current, def.colorStops);
    const sat   = 65 + fraction * 15;  // slightly more saturated when high
    const light = 42 + fraction * 8;
    fillEl.setAttribute('stroke', `hsl(${Math.round(hue)},${Math.round(sat)}%,${Math.round(light)}%)`);

    valueEl.textContent = def.format(current);"""

replace_render = """    const { def, fillEl, valueEl, barFillEl, barValueEl, current } = g;

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
    barValueEl.textContent = `${def.format(current)} ${def.unit}`;"""

js = js.replace(find_render, replace_render)

with open("js/gauges.js", "w", encoding="utf-8") as f:
    f.write(js)
