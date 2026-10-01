import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

css = css.replace("max-height: 90vh;", "max-height: 90dvh;")
css = css.replace("max-height: 78vh;", "max-height: 78dvh;")

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
