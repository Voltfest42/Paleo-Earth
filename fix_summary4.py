import json

with open("data/summaries.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for key, entry in data.items():
    if "subtitle" in entry:
        sub = entry["subtitle"]
        # In python, the character might appear as '\xc2\xb7' or something depending on encoding, 
        # but if we just split by " Ma " or " Present " we can fix it.
        if " Present " in sub:
            parts = sub.split(" Present ", 1)
            entry["subtitle"] = parts[0] + " Present \u00b7 " + parts[1][2:] if len(parts[1]) > 2 else sub
        elif " Ma " in sub:
            parts = sub.split(" Ma ", 1)
            # parts[1] might be like "A Ice Ages" -> we want to skip the corrupted chars and find the first letter
            import string
            for i, c in enumerate(parts[1]):
                if c in string.ascii_letters:
                    entry["subtitle"] = parts[0] + " Ma \u00b7 " + parts[1][i:]
                    break

data["holocene"]["subtitle"] = "12,000 years ago to Present \u00b7 The Age of Humanity"

with open("data/summaries.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
