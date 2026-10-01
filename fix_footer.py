import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find = "  .resize-handle {"
replace = """  .globe-footer {
    height: auto;
    padding: 10px 12px 16px;
  }

  .resize-handle {"""

css = css.replace(find, replace)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
