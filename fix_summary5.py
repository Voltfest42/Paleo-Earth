import json
import string

with open("data/summaries.json", "r", encoding="utf-8", errors="ignore") as f:
    data = json.load(f)

for key, entry in data.items():
    if "subtitle" in entry:
        sub = entry["subtitle"]
        if " Present " in sub:
            parts = sub.split(" Present ", 1)
            for i, c in enumerate(parts[1]):
                if c in string.ascii_letters:
                    entry["subtitle"] = parts[0] + " Present \u00b7 " + parts[1][i:]
                    break
        elif " Ma " in sub:
            parts = sub.split(" Ma ", 1)
            for i, c in enumerate(parts[1]):
                if c in string.ascii_letters:
                    entry["subtitle"] = parts[0] + " Ma \u00b7 " + parts[1][i:]
                    break

data["holocene"]["subtitle"] = "12,000 years ago to Present \u00b7 The Age of Humanity"

with open("data/summaries.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=True)
