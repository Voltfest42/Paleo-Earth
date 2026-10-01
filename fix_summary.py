import sys, json

with open("data/summaries.json", "r", encoding="utf-8") as f:
    text = f.read()

# Replace the specific holocene subtitle
text = text.replace('"0.012 Ma to Present · The Age of Humanity"', '"12,000 years ago to Present · The Age of Humanity"')
text = text.replace('"0.012 Ma to Present  The Age of Humanity"', '"12,000 years ago to Present · The Age of Humanity"')
text = text.replace('"12,000 year ago to Present A The Age of Humanity"', '"12,000 years ago to Present · The Age of Humanity"')

# Fix any corrupted unicode question marks or weird chars
text = text.replace("", "·")
text = text.replace("A·", "·")

with open("data/summaries.json", "w", encoding="utf-8") as f:
    f.write(text)
