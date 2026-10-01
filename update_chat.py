import sys

with open("js/chat.js", "r", encoding="utf-8") as f:
    js = f.read()

find = "this._el.chatMessages.scrollTop = this._el.chatMessages.scrollHeight;"
replace = """this._el.chatMessages.scrollTop = this._el.chatMessages.scrollHeight;
    const panelBody = this._el.chatMessages.closest('.right-panel-body');
    if (panelBody) panelBody.scrollTop = panelBody.scrollHeight;"""

js = js.replace(find, replace)

with open("js/chat.js", "w", encoding="utf-8") as f:
    f.write(js)
