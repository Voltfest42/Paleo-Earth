import sys

with open("js/globe.js", "r", encoding="utf-8") as f:
    js = f.read()

find = """  async _fetchAndApply(index, snappedMa, key, isForward) {
    const ticket = ++this._ticket;

    try {
      const frame = await this._cache.getFrame(index, snappedMa);

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
      this._globeMaterial.needsUpdate  = true;

      // If borders overlay is enabled, also fetch and apply the border texture
      if (this._showBorders) {
        this._loadAndApplyBorder(index, snappedMa, ticket);
      }

      // Lookahead preload:"""

replace = """  async _fetchAndApply(index, snappedMa, key, isForward) {
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

      // Lookahead preload:"""

js = js.replace(find, replace)

with open("js/globe.js", "w", encoding="utf-8") as f:
    f.write(js)
