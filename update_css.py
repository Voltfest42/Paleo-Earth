import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

mobile_css = """

/* "?"?"? Mobile Layout Overrides "?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"? */
@media (max-width: 768px) {
  .app-container {
    flex-direction: column;
  }

  .panel-left {
    width: 100% !important;
    height: var(--left-width); /* Repurposing --left-width for height */
    min-width: unset;
    min-height: 200px;
    border-bottom: 1px solid var(--border);
  }

  .panel-right {
    width: 100% !important;
    flex: 1;
    min-width: unset;
    min-height: 200px;
    border-left: none;
  }

  .resize-handle {
    width: 100%;
    height: var(--handle-width);
    cursor: row-resize;
  }
}
"""

css += mobile_css

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
