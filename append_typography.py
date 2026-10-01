import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

new_css = """
/* Phase 3: Typography and Touch Targets for Mobile */
@media (max-width: 768px) {
  /* Smaller headings to prevent wrapping */
  .keyframe-title {
    font-size: 18px; /* Was 22px */
  }
  .keyframe-badge {
    font-size: 10px; /* Was 11px */
    padding: 2px 6px;
  }
  
  /* Wiki typography spacing */
  .wiki-subtitle {
    font-size: 1.15rem; /* Was 1.4rem */
  }
  .wiki-header {
    padding: 12px 12px 0 12px;
  }
  .wiki-content {
    padding: 12px;
  }
  
  /* Panel topbar spacing */
  .panel-topbar {
    padding: 10px 12px;
    height: auto;
  }
  
  /* Summary card spacing */
  .summary-card {
    padding: 12px;
    margin-bottom: 8px; /* Tighter gap */
  }
  .summary-text {
    font-size: 13px; /* Slightly smaller for readability in narrow columns */
    line-height: 1.6;
  }
  
  /* Tabs touch targets */
  .panel-tab-btn {
    padding: 14px 10px; /* Increase tap area */
    font-size: 14px; 
    flex: 1; /* Ensure they divide evenly */
  }
  
  /* Standard Buttons Touch Targets (TTS, Fullscreen, Play, Summary Image) */
  .tts-btn, .fullscreen-btn, .summary-btn, .play-btn {
    width: 38px;
    height: 38px;
  }
  .tts-btn svg, .fullscreen-btn svg, .summary-btn svg, .play-btn svg {
    width: 20px;
    height: 20px;
  }

  /* Globe Control Buttons (Settings, Borders) */
  .globe-control-btn {
    padding: 8px 16px; /* Increase tap area */
    font-size: 14px;
    gap: 8px;
  }
  .globe-control-btn .globe-control-icon {
    width: 16px;
    height: 16px;
  }
  
  /* Timeline Labels */
  .slider-ma-label {
    font-size: 15px; /* Was 18px */
  }
  .slider-period-label {
    font-size: 13px; /* Was 16px */
  }
  .slider-axis {
    font-size: 11px; /* Was 12px (0.75rem / 0.85rem) */
  }
  
  /* Chat inputs */
  .chat-input-row input {
    font-size: 16px; /* Prevent iOS Safari auto-zoom on focus by enforcing >=16px */
    padding: 10px 14px;
    height: 44px; /* Better touch target */
  }
  .chat-input-area {
    padding: 10px;
  }
  #sendBtn {
    width: 44px;
    height: 44px;
  }
  #sendBtn svg {
    width: 20px;
    height: 20px;
  }
  
  /* Reduce side padding on chat messages for more text room */
  .chat-messages {
    padding: 12px;
  }
}
"""

css += new_css

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
