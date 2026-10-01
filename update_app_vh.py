import sys

with open("js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

js = js.replace("panelLeft.style.height = '45vh';", "panelLeft.style.height = '45%';")

with open("js/app.js", "w", encoding="utf-8") as f:
    f.write(js)
