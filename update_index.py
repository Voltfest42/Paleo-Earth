import sys

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

find_btn = """        <div class="globe-viewport-controls">
          <button class="globe-control-btn" id="toggleBordersBtn" title="Toggle Political Borders Overlay" aria-pressed="false">"""

replace_btn = """        <div class="globe-viewport-controls">
          <button class="globe-control-btn" id="settingsBtn" title="Settings">
            <svg class="globe-control-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>
          <button class="globe-control-btn" id="toggleBordersBtn" title="Toggle Political Borders Overlay" aria-pressed="false">"""

html = html.replace(find_btn, replace_btn)

find_modal = """  <script type="module" src="js/app.js"></script>
</body>"""

replace_modal = """  <!-- Settings Modal -->
  <div class="modal-overlay" id="settingsModal">
    <div class="modal-content">
      <div class="modal-header">
        <h2>Settings</h2>
        <button class="modal-close" id="settingsCloseBtn">&times;</button>
      </div>
      <div class="modal-body">
        <div class="setting-row">
          <div class="setting-info">
            <h3>TTS Voice</h3>
            <p>Select the narrator voice for text-to-speech.</p>
          </div>
          <div class="setting-control">
            <select id="ttsVoiceSelect" class="settings-select">
              <option value="Matthew">Matthew (Male)</option>
              <option value="Joanna">Joanna (Female)</option>
            </select>
          </div>
        </div>
        <div class="setting-row">
          <div class="setting-info">
            <h3>Texture Quality</h3>
            <p>Lower resolution improves performance on older devices.</p>
          </div>
          <div class="setting-control">
            <select id="textureQualitySelect" class="settings-select" disabled>
              <option value="high">High (4K)</option>
              <option value="low">Low (1K) - Coming Soon</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script type="module" src="js/app.js"></script>
</body>"""

html = html.replace(find_modal, replace_modal)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)
