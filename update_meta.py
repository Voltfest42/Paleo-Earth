import sys

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

find = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
replace = '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">'

html = html.replace(find, replace)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)
