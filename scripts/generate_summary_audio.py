import json
import os
import re
import subprocess
import time

SUMMARIES_FILE = 'data/summaries.json'
OUT_DIR = 'audio/summaries'
VOICES = ['Matthew', 'Joanna']

def sanitize_for_speech(text):
    if not text: return ''
    # Geological abbreviations
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*[-\u2013\u2014]\s*(\d+(?:\.\d+)?)\s*Ma\b', r'\1 to \2 million years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*Ma\b', r'\1 million years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\bMa\b', 'million years ago', text)
    text = re.sub(r'\bmya\b', 'million years ago', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*[-\u2013\u2014]\s*(\d+(?:\.\d+)?)\s*Ga\b', r'\1 to \2 billion years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*Ga\b', r'\1 billion years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\bbya\b', 'billion years ago', text, flags=re.IGNORECASE)
    
    # Strip redundant parenthetical acronyms following spelled-out names
    text = re.sub(r'\s*\([A-Z0-9\-–—/]{2,8}\)', '', text)

    # Events and Major Geological Acronyms
    text = re.sub(r'\bK[-\u2013\u2014/]?Pg\b', 'Cretaceous-Paleogene', text, flags=re.IGNORECASE)
    text = re.sub(r'\bK[-\u2013\u2014/]?T\b', 'Cretaceous-Tertiary', text, flags=re.IGNORECASE)
    text = re.sub(r'\bP[-\u2013\u2014/]?Tr\b', 'Permian-Triassic', text, flags=re.IGNORECASE)
    text = re.sub(r'\bO[-\u2013\u2014/]?S\b', 'Ordovician-Silurian', text, flags=re.IGNORECASE)
    text = re.sub(r'\bTr[-\u2013\u2014/]?J\b', 'Triassic-Jurassic', text, flags=re.IGNORECASE)
    text = re.sub(r'\bPETM\b', 'Paleocene-Eocene Thermal Maximum', text)
    text = re.sub(r'\bGOBE\b', 'Great Ordovician Biodiversification Event', text)
    text = re.sub(r'\bCAMP\b', 'Central Atlantic Magmatic Province', text)
    text = re.sub(r'\bCRC\b', 'Carboniferous Rainforest Collapse', text)
    text = re.sub(r'\bEOT\b', 'Eocene-Oligocene Transition', text)
    text = re.sub(r'\bMPT\b', 'Mid-Pleistocene Transition', text)
    text = re.sub(r'\bSPICE\b', 'S-P-I-C-E', text)
    text = re.sub(r'\bHICE\b', 'H-I-C-E', text)
    text = re.sub(r'\bDICE\b', 'D-I-C-E', text)
    text = re.sub(r'\bLIPs?\b', 'Large Igneous Province', text)
    text = re.sub(r'\bBIFs?\b', 'Banded Iron Formation', text)

    # Word slashes (e.g. Climatic/Environmental -> Climatic and Environmental)
    text = re.sub(r'([a-zA-Z]{3,})/([a-zA-Z]{3,})', r'\1 and \2', text)

    # Isotopes and notation
    text = re.sub(r'δ\s*', 'delta ', text)
    text = re.sub(r'‰', ' per mil', text)
    
    # Chemistry
    text = re.sub(r'\bCO2\b', 'carbon dioxide', text, flags=re.IGNORECASE)
    text = re.sub(r'\bO2\b', 'oxygen', text, flags=re.IGNORECASE)
    
    # Approx
    text = re.sub(r'[~\u2248]', 'approximately ', text)
    text = re.sub(r'\bca\.\s*', 'approximately ', text, flags=re.IGNORECASE)
    text = re.sub(r'\u00b7|\u2022', ' ', text) # bullets
    
    # Formatting
    text = re.sub(r'\s*[\u2014\u2013]\s*', ', ', text)
    text = text.replace('\n', ' ')
    text = re.sub(r'\s{2,}', ' ', text)
    
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return text.strip()

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    with open(SUMMARIES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for kf_id, item in data.items():
        print(f"Processing summary: {kf_id}")
        
        title = sanitize_for_speech(item.get('title', ''))
        subtitle = sanitize_for_speech(item.get('subtitle', ''))
        body = sanitize_for_speech(item.get('body', ''))
        
        ssml = f"<speak>{title}. <break time='0.2s'/>{subtitle}. <break time='0.8s'/>{body}</speak>"
        
        for voice in VOICES:
            out_file = os.path.join(OUT_DIR, f"{kf_id}_{voice.lower()}.mp3")
            if os.path.exists(out_file):
                print(f"  Skipping {out_file}")
                continue
            
            print(f"  Generating {voice}...")
            cmd = [
                'aws', 'polly', 'synthesize-speech',
                '--output-format', 'mp3',
                '--voice-id', voice,
                '--engine', 'neural',
                '--text-type', 'ssml',
                '--text', ssml,
                out_file
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            time.sleep(0.5)

if __name__ == '__main__':
    main()