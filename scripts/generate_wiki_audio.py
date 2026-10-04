import json
import os
import re
import subprocess
import time

WIKI_FILE = 'data/wiki.json'
OUT_DIR = 'audio/wiki'

VOICES = ['Matthew', 'Joanna']

def sanitize_for_speech(text):
    if not text: return ''
    
    # Remove citation brackets [1], [2, 3]
    text = re.sub(r'\[\d+(,\s*\d+)*\]', '', text)
    
    # Geological abbreviations
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*[-\u2013\u2014]\s*(\d+(?:\.\d+)?)\s*Ma\b', r'\1 to \2 million years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*Ma\b', r'\1 million years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\bMa\b', 'million years ago', text)
    text = re.sub(r'\bmya\b', 'million years ago', text, flags=re.IGNORECASE)
    
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*[-\u2013\u2014]\s*(\d+(?:\.\d+)?)\s*Ga\b', r'\1 to \2 billion years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+(?:\.\d+)?)\s*Ga\b', r'\1 billion years ago', text, flags=re.IGNORECASE)
    text = re.sub(r'\bbya\b', 'billion years ago', text, flags=re.IGNORECASE)
    
    # Events
    text = re.sub(r'\bK[-\u2013\u2014/]?Pg\b', 'K-P-G', text, flags=re.IGNORECASE)
    text = re.sub(r'\bK[-\u2013\u2014/]?T\b', 'K-T', text, flags=re.IGNORECASE)
    text = re.sub(r'\bP[-\u2013\u2014/]?Tr\b', 'Permian-Triassic', text, flags=re.IGNORECASE)
    text = re.sub(r'\bPETM\b', 'P-E-T-M', text)
    
    # Chemistry
    text = re.sub(r'\bCO2\b', 'carbon dioxide', text, flags=re.IGNORECASE)
    text = re.sub(r'\bO2\b', 'oxygen', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCH4\b', 'methane', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:\u00b0|\bdeg\b)\s*C\b', ' degrees Celsius', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
    text = re.sub(r'\bppm\b', 'parts per million', text, flags=re.IGNORECASE)
    
    # Approx
    text = re.sub(r'[~\u2248]', 'approximately ', text)
    text = re.sub(r'\bca\.\s*', 'approximately ', text, flags=re.IGNORECASE)
    
    # Formatting
    text = text.replace('\n', ' ')
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def synthesize_chunk(text, voice, out_file):
    # Call AWS Polly
    # We use engine 'neural' for higher quality voices (Matthew, Joanna support neural)
    cmd = [
        'aws', 'polly', 'synthesize-speech',
        '--output-format', 'mp3',
        '--voice-id', voice,
        '--engine', 'neural',
        '--text-type', 'text',
        '--text', text,
        out_file
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    with open(WIKI_FILE, 'r', encoding='utf-8') as f:
        wiki = json.load(f)
        
    for article_id, article in wiki.items():
        print(f"Processing: {article_id}")
        
        # Build logical chunks
        chunks = []
        title_chunk = article.get('title', '') + '. ' + (article.get('subtitle', '') + '.' if article.get('subtitle') else '')
        chunks.append(title_chunk)
        
        for section in article.get('sections', []):
            h = section.get('heading', '')
            if 'source' in h.lower() or 'reference' in h.lower():
                continue
            body = section.get('body', '')
            chunks.append(h + '. ' + body)
            
        sanitized_chunks = [sanitize_for_speech(c) for c in chunks if c.strip()]
        
        for voice in VOICES:
            final_file = os.path.join(OUT_DIR, f"{article_id}_{voice.lower()}.mp3")
            if os.path.exists(final_file):
                print(f"  Skipping {final_file} (already exists)")
                continue
            
            print(f"  Generating audio for {voice}...")
            temp_files = []
            try:
                for i, chunk in enumerate(sanitized_chunks):
                    if not chunk: continue
                    temp_f = os.path.join(OUT_DIR, f"temp_{article_id}_{voice.lower()}_{i}.mp3")
                    
                    # Split chunk further if it's magically > 2900 chars just in case
                    if len(chunk) > 2900:
                        sentences = re.split(r'(?<=[.!?]) +', chunk)
                        sub_chunk = ""
                        for s in sentences:
                            if len(sub_chunk) + len(s) > 2900:
                                t = os.path.join(OUT_DIR, f"temp_{article_id}_{voice.lower()}_{i}_{len(temp_files)}.mp3")
                                synthesize_chunk(sub_chunk, voice, t)
                                temp_files.append(t)
                                sub_chunk = s + " "
                            else:
                                sub_chunk += s + " "
                        if sub_chunk.strip():
                            t = os.path.join(OUT_DIR, f"temp_{article_id}_{voice.lower()}_{i}_{len(temp_files)}.mp3")
                            synthesize_chunk(sub_chunk, voice, t)
                            temp_files.append(t)
                    else:
                        synthesize_chunk(chunk, voice, temp_f)
                        temp_files.append(temp_f)
                    
                    time.sleep(0.5) # small delay to prevent rate limits
                
                # Merge temp files
                with open(final_file, 'wb') as outfile:
                    for t in temp_files:
                        with open(t, 'rb') as infile:
                            outfile.write(infile.read())
                
                print(f"  Saved {final_file}")
            
            finally:
                for t in temp_files:
                    if os.path.exists(t):
                        os.remove(t)

if __name__ == '__main__':
    main()