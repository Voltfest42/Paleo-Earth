import sys

with open("js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

js = js.replace("panelLeft.style.height = `${window.innerHeight - 14}px`;", "panelLeft.style.height = `${window.innerHeight - 18}px`;")

with open("js/app.js", "w", encoding="utf-8") as f:
    f.write(js)
