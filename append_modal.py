import sys

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

modal = """
  <!-- Settings Modal -->
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
"""

if 'id="settingsModal"' not in html:
    html = html.replace('</body>', modal + '\n</body>')
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
