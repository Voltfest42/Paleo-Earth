import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find1 = """.panel-left.fullscreen {
  width: 100vw !important;
  position: fixed;"""

replace1 = """.panel-left.fullscreen {
  width: 100vw !important;
  height: 100% !important;
  position: fixed;"""

find2 = """.panel-right.fullscreen {
  width: 100vw !important;
  position: fixed;"""

replace2 = """.panel-right.fullscreen {
  width: 100vw !important;
  height: 100% !important;
  position: fixed;"""

css = css.replace(find1, replace1).replace(find2, replace2)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
