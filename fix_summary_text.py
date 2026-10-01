import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find = """  .summary-text {
    font-size: 13px; /* Slightly smaller for readability in narrow columns */
    line-height: 1.6;
  }"""

replace = """  .summary-text {
    font-size: 14.5px;
    line-height: 1.6;
  }"""

css = css.replace(find, replace)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
