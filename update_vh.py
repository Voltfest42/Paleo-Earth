import sys

with open("style.css", "r", encoding="utf-8") as f:
    css = f.read()

find = """.app-container {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}"""

replace = """.app-container {
  display: flex;
  width: 100vw;
  height: 100vh; /* Fallback for older browsers */
  height: 100dvh; /* Accounts for mobile browser UI like address and navigation bars */
  overflow: hidden;
}"""

css = css.replace(find, replace)

with open("style.css", "w", encoding="utf-8") as f:
    f.write(css)
