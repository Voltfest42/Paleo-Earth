import re
import sys

def patch_globe():
    with open('js/globe.js', 'r', encoding='utf-8') as f:
        content = f.read()

    # Imports
    content = content.replace(
        "bordersPath,\n  GLOBE_BORDERS_COLOR,",
        "bordersPath,\n  GLOBE_BORDERS_COLOR,\n  continentIdPath,\n  continentOutlinePath,"
    )

    # Class vars
    content = content.replace(
        "this._showBorders          = false;",
        "this._showBorders          = false;\n    this._showContinents       = false;\n    this._idCanvas = document.createElement('canvas');\n    this._idCtx = this._idCanvas.getContext('2d', { willReadFrequently: true });\n    this._raycaster = new THREE.Raycaster();\n    this._hoveredColorStr = null;"
    )

    # Caches
    content = content.replace(
        "this._bordersCache = new BorderTextureCache(this._loader, TEXTURE_CACHE_SIZE);",
        "this._bordersCache = new BorderTextureCache(this._loader, TEXTURE_CACHE_SIZE);\n    this._outlineCache = new BorderTextureCache(this._loader, TEXTURE_CACHE_SIZE);\n    this._idCache = new BorderTextureCache(this._loader, TEXTURE_CACHE_SIZE);"
    )

    # Placeholders
    placeholder_insertion = """
    const outlinePlaceholder = new THREE.DataTexture(new Uint8Array([0,0,0,0]), 1, 1, THREE.RGBAFormat);
    outlinePlaceholder.needsUpdate = true;
    const idPlaceholder = new THREE.DataTexture(new Uint8Array([0,0,0,0]), 1, 1, THREE.RGBAFormat);
    idPlaceholder.needsUpdate = true;
"""
    content = content.replace(
        "const bordersPlaceholder = new THREE.DataTexture(",
        placeholder_insertion + "    const bordersPlaceholder = new THREE.DataTexture("
    )

    # Uniforms
    uniforms_insertion = """
      continentOutlineMap: { value: outlinePlaceholder },
      continentIdMap: { value: idPlaceholder },
      continentsOpacity: { value: 0.0 },
      hoveredContinentColor: { value: new THREE.Color(0,0,0) },
      hoveredContinentUiColor: { value: new THREE.Color(0,0,0) },
      hoveredGlowOpacity: { value: 0.0 },
"""
    content = content.replace(
        "bordersMap:     { value: bordersPlaceholder },",
        "bordersMap:     { value: bordersPlaceholder },\n" + uniforms_insertion
    )

    # Shader onBeforeCompile
    shader_uniforms = """
        uniform sampler2D bordersMap;
        uniform float bordersOpacity;
        uniform vec3 bordersColor;
        
        uniform sampler2D continentOutlineMap;
        uniform sampler2D continentIdMap;
        uniform float continentsOpacity;
        uniform vec3 hoveredContinentColor;
        uniform vec3 hoveredContinentUiColor;
        uniform float hoveredGlowOpacity;
"""
    content = re.sub(
        r'uniform sampler2D bordersMap;.*?uniform vec3 bordersColor;',
        shader_uniforms,
        content,
        flags=re.DOTALL
    )

    shader_frag = """
          // Political border overlay
          if (bordersOpacity > 0.0) {
            vec4 borderSample = texture2D( bordersMap, vMapUv );
            diffuseColor.rgb = mix( diffuseColor.rgb, bordersColor, borderSample.r * bordersOpacity );
          }

          // Continents Outline overlay
          if (continentsOpacity > 0.0) {
            vec4 outlineSample = texture2D( continentOutlineMap, vMapUv );
            // outlineSample has the color in rgb and opacity in a
            diffuseColor.rgb = mix( diffuseColor.rgb, outlineSample.rgb, outlineSample.a * continentsOpacity );
          }

          // Hover Glow
          if (hoveredGlowOpacity > 0.0) {
            vec4 idSample = texture2D( continentIdMap, vMapUv );
            // Match color
            float dist = distance(idSample.rgb, hoveredContinentColor);
            if (dist < 0.05 && idSample.a > 0.1) {
              // Additive glow
              diffuseColor.rgb += hoveredContinentUiColor * hoveredGlowOpacity;
            }
          }
"""
    content = re.sub(
        r'// Political border overlay:.*?bordersOpacity \);\n\s+}',
        shader_frag,
        content,
        flags=re.DOTALL
    )

    # Animation update
    anim_update = """
    // Smooth transition for continent opacity
    if (this._customUniforms && this._customUniforms.continentsOpacity) {
      const curC = this._customUniforms.continentsOpacity.value;
      const tgtC = this._showContinents ? 1.0 : 0.0;
      if (Math.abs(curC - tgtC) > 0.002) {
        this._customUniforms.continentsOpacity.value += (tgtC - curC) * 0.18;
      } else {
        this._customUniforms.continentsOpacity.value = tgtC;
      }
    }
"""
    content = content.replace(
        "this._controls.update();",
        anim_update + "\n    this._controls.update();"
    )

    # Fetch and Apply
    fetch_apply = """
      const borderPromise = this._showBorders ? this._bordersCache.getBorder(index, snappedMa) : Promise.resolve(null);
      
      // Load ID map regardless if continents shown or not, so picking works!
      // But only load if the file exists (we might just have frame 1). We catch errors.
      const idPromise = new Promise(res => {
         this._loader.load(continentIdPath(index, snappedMa), tex => res(tex), undefined, () => res(null));
      });
      const outlinePromise = this._showContinents ? new Promise(res => {
         this._loader.load(continentOutlinePath(index, snappedMa), tex => res(tex), undefined, () => res(null));
      }) : Promise.resolve(null);
      
      const [frame, borderTex, idTex, outlineTex] = await Promise.all([framePromise, borderPromise, idPromise, outlinePromise]);
"""
    content = re.sub(
        r'const borderPromise = .*?\n.*const \[frame, borderTex\] = await Promise\.all\(\[framePromise, borderPromise\]\);',
        fetch_apply,
        content,
        flags=re.DOTALL
    )

    tex_apply = """
      if (borderTex) {
        this._customUniforms.bordersMap.value = borderTex;
      }
      if (outlineTex) {
        this._customUniforms.continentOutlineMap.value = outlineTex;
      }
      if (idTex) {
        this._customUniforms.continentIdMap.value = idTex;
        if (idTex.image) {
            this._idCanvas.width = idTex.image.width;
            this._idCanvas.height = idTex.image.height;
            this._idCtx.drawImage(idTex.image, 0, 0);
        }
      } else {
        // Clear canvas if no map
        this._idCtx.clearRect(0, 0, this._idCanvas.width, this._idCanvas.height);
      }
"""
    content = re.sub(
        r'if \(borderTex\) \{\n\s+this\._customUniforms\.bordersMap\.value = borderTex;\n\s+\}',
        tex_apply,
        content,
        flags=re.DOTALL
    )

    # Toggles
    toggle_continents = """
  toggleContinents() {
    this._showContinents = !this._showContinents;
    if (this._showContinents) {
      const currentMa = this._displayedMa !== null ? this._displayedMa : (this._targetMa !== null ? this._targetMa : 0);
      const { index, ma: snappedMa } = getFrameForMa(currentMa);
      this._loader.load(continentOutlinePath(index, snappedMa), tex => {
         this._customUniforms.continentOutlineMap.value = tex;
      });
    }
    return this._showContinents;
  }

  setHoveredContinent(colorObj, opacity) {
    if (colorObj) {
        this._customUniforms.hoveredContinentColor.value.setRGB(colorObj.r/255, colorObj.g/255, colorObj.b/255);
        if (colorObj.uiColor) {
            this._customUniforms.hoveredContinentUiColor.value.setRGB(colorObj.uiColor[0], colorObj.uiColor[1], colorObj.uiColor[2]);
        } else {
            this._customUniforms.hoveredContinentUiColor.value.setRGB(colorObj.r/255, colorObj.g/255, colorObj.b/255);
        }
    }
    this._customUniforms.hoveredGlowOpacity.value = opacity;
  }

  getContinentColorAt(ndcX, ndcY) {
    if (this._idCanvas.width === 0 || this._idCanvas.height === 0) return null;
    this._raycaster.setFromCamera({x: ndcX, y: ndcY}, this._camera);
    const intersects = this._raycaster.intersectObject(this._globe);
    if (intersects.length > 0) {
        const uv = intersects[0].uv;
        const x = Math.floor(uv.x * this._idCanvas.width);
        const y = Math.floor((1.0 - uv.y) * this._idCanvas.height);
        const data = this._idCtx.getImageData(x, y, 1, 1).data;
        if (data[3] > 0 && !(data[0]===0 && data[1]===0 && data[2]===0) && !(data[0]===255 && data[1]===255 && data[2]===255)) {
            return `${data[0]},${data[1]},${data[2]}`;
        }
    }
    return null;
  }
"""
    content = content.replace("toggleBorders() {", toggle_continents + "\n  toggleBorders() {")

    with open('js/globe.js', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_globe()
