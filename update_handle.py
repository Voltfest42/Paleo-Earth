import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find = """    width: 100%;
    height: 14px;
    background: rgba(255, 255, 255, 0.15);"""

replace = """    width: 100%;
    height: 18px;
    background: rgba(255, 255, 255, 0.2);"""

css = css.replace(find, replace)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
