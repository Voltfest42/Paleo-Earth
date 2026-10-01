import sys
import re

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

# Replace the desktop fullscreen styles
find_fs = """/* Fullscreen states */
.panel-left.fullscreen {
  width: 100vw !important;
  height: 100% !important;
  position: fixed;
  top: 0; left: 0;
  z-index: 200;
}

.panel-right.fullscreen {
  width: 100vw !important;
  height: 100% !important;
  position: fixed;
  top: 0; right: 0;
  z-index: 200;
}"""

replace_fs = """/* Fullscreen states (Flexbox based) */
.panel-left.fullscreen {
  flex: 1 !important;
  width: auto !important;
  height: auto !important;
  max-width: none !important;
}

.panel-right.fullscreen {
  flex: 1 !important;
  width: auto !important;
  height: auto !important;
  max-width: none !important;
}"""

# For safety if I missed exact spacing:
if "width: 100vw !important;" in css:
    css = re.sub(r"\.panel-left\.fullscreen\s*\{[^}]*\}", ".panel-left.fullscreen {\n  flex: 1 !important;\n  width: auto !important;\n  height: auto !important;\n  max-width: none !important;\n}", css)
    css = re.sub(r"\.panel-right\.fullscreen\s*\{[^}]*\}", ".panel-right.fullscreen {\n  flex: 1 !important;\n  width: auto !important;\n  height: auto !important;\n  max-width: none !important;\n}", css)

# Add styling to the handle in mobile
find_mobile_handle = """.resize-handle {
    width: 100%;
    height: var(--handle-width);
    cursor: row-resize;
  }"""

replace_mobile_handle = """.resize-handle {
    width: 100%;
    height: 14px;
    background: rgba(255, 255, 255, 0.15);
    cursor: row-resize;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }
  
  /* Visual pill for affordance */
  .resize-handle::after {
    content: '';
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 48px;
    height: 4px;
    background: rgba(255, 255, 255, 0.6);
    border-radius: 2px;
  }"""

css = css.replace(find_mobile_handle, replace_mobile_handle)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
