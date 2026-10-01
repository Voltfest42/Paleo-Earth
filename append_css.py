import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

new_css = """
/* Enable scrolling for the entire right panel on mobile */
@media (max-width: 768px) {
  .right-panel-body {
    overflow-y: auto;
    overflow-x: hidden;
  }
  
  .panel-tab-content, .tab-pane, .wiki-content, .chat-messages {
    overflow: visible;
    flex: none;
    height: auto;
  }

  .chat-input-area {
    position: sticky;
    bottom: 0;
    z-index: 10;
    box-shadow: 0 -4px 12px rgba(0,0,0,0.2);
  }
}
"""

css += new_css

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
