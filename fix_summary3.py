import json
import re

with open("data/summaries.json", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Replace any sequence of space + weird A stuff + space with space + dot + space
text = re.sub(r" (A.|.) ", " \u00b7 ", text)
text = re.sub(r" (A\ufffd|\ufffd) ", " \u00b7 ", text)

# Just to be extremely safe and broad, find any " Ma [anything] " and replace with " Ma \u00b7 "
text = re.sub(r" Ma [^\w\s]+ ", " Ma \u00b7 ", text)
text = re.sub(r" Present [^\w\s]+ ", " Present \u00b7 ", text)

data = json.loads(text)
data["holocene"]["subtitle"] = "12,000 years ago to Present \u00b7 The Age of Humanity"

with open("data/summaries.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
