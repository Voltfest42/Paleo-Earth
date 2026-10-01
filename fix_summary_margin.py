import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find = """  /* Summary card spacing */
  .summary-card {
    padding: 12px;
    margin-bottom: 8px; /* Tighter gap */
  }"""

replace = """  /* Summary card spacing */
  .summary-card {
    padding: 12px;
    margin: 12px 12px 8px 12px; /* Reduce horizontal margin to save space */
  }"""

css = css.replace(find, replace)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
