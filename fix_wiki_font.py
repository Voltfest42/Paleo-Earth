import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find = """  .wiki-content {
    padding: 12px;
  }"""

replace = """  .wiki-content {
    padding: 12px 14px;
  }
  .wiki-heading {
    font-size: 16px; /* Balance heading */
  }
  .wiki-body {
    font-size: 14px; /* Slightly larger for easier reading on small screens */
    line-height: 1.6;
    margin-bottom: 12px; /* Better paragraph separation */
  }"""

css = css.replace(find, replace)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
