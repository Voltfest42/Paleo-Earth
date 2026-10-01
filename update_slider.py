import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find = """  .chat-messages {
    padding: 12px;
  }
}"""

replace = """  .chat-messages {
    padding: 12px;
  }

  /* Increase slider thumb size for touch */
  input[type="range"]::-webkit-slider-thumb {
    width: 20px;
    height: 20px;
  }
}"""

css = css.replace(find, replace)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
