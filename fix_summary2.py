import json

with open("data/summaries.json", "r", encoding="utf-8", errors="replace") as f:
    data = json.load(f)

for key, entry in data.items():
    sub = entry.get("subtitle", "")
    # Fix the specific holocene one
    if key == "holocene":
        entry["subtitle"] = "12,000 years ago to Present \u00b7 The Age of Humanity"
    else:
        # Replace any weird character with the dot
        # Sometimes it's loaded as \ufffd
        if "\ufffd" in sub:
            entry["subtitle"] = sub.replace("\ufffd", "\u00b7")
        # If it has " A " or something, let's just make sure it's correct
        if " A " in sub:
            entry["subtitle"] = sub.replace(" A ", " \u00b7 ")

with open("data/summaries.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
