import os
import sys
import json
import time
import re
import urllib.request
import xml.etree.ElementTree as ET
try:
    import anthropic
except ImportError:
    print("Please install the Anthropic SDK: pip install anthropic")
    sys.exit(1)

# File Paths
USED_URLS_FILE = "spinops_deduped.txt"
LIBRARY_FILE = "data/image-library.json"
IMAGES_DIR = "images/paleo_art/"

# API Settings
MODEL = "claude-haiku-4-5-20251001" # Using the latest 4.5 Haiku as requested

def get_used_urls():
    used = set()
    
    # 1. Load from the text file
    if os.path.exists(USED_URLS_FILE):
        with open(USED_URLS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip().split('?')[0] # strip queries
                if url.startswith("http"):
                    used.add(url)
                    
    # 2. Load from the existing JSON library to be extra safe
    if os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for img in data.get("images", []):
                if "source_url" in img:
                    url = img["source_url"].split('?')[0]
                    used.add(url)
                    
    return used

def scrape_all_posts():
    print("Scraping Nobu Tamura's blog history (this may take a minute)...")
    posts = []
    start_index = 1
    max_results = 150
    
    while True:
        url = f"https://spinops.blogspot.com/feeds/posts/default?start-index={start_index}&max-results={max_results}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            xml_data = urllib.request.urlopen(req).read()
        except Exception as e:
            print(f"Error fetching feed: {e}")
            break
            
        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        
        if not entries:
            break
            
        for entry in entries:
            title_tag = entry.find('atom:title', ns)
            title = title_tag.text if title_tag is not None else "Untitled"
            
            post_url = None
            for link in entry.findall('atom:link', ns):
                if link.attrib.get('rel') == 'alternate':
                    post_url = link.attrib.get('href')
                    break
                    
            if not post_url: continue
            
            categories = [c.attrib['term'] for c in entry.findall('atom:category', ns)]
            
            content_tag = entry.find('atom:content', ns)
            content = content_tag.text if content_tag is not None else ""
            
            # Find image using regex
            img_link = None
            match = re.search(r'href=["\']([^"\']+\.(?:jpg|jpeg|png))["\']', content, re.IGNORECASE)
            if match:
                img_link = match.group(1)
            else:
                match = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png))["\']', content, re.IGNORECASE)
                if match: img_link = match.group(1)
                
            if img_link:
                posts.append({
                    "title": title,
                    "url": post_url.split('?')[0],
                    "categories": categories,
                    "image_url": img_link
                })
                
        start_index += max_results
        
    print(f"Found a total of {len(posts)} posts with images on the blog.")
    return posts

def categorize_with_claude(client, post):
    prompt = f"""You are a paleontologist API working on the "Paleo Earth" project.
We are adding a new paleoart image to our database. 

Blog Post Title: {post['title']}
Blog Categories/Tags: {post['categories']}
Post URL: {post['url']}

Based on the title and categories, please generate the JSON metadata for this image. 
If the title is a specific creature, write a 1-2 sentence educational description about it. 
If it is a composite (e.g. "Burgess Shale biota"), write a description of that ecosystem.

Output STRICTLY valid JSON with no markdown wrapping, using this exact schema:
{{
  "id": "(lowercase_creature_name)_tamura",
  "filename": "(lowercase_creature_name)_nobu_tamura.jpg",
  "title": "{post['title']}",
  "credit": "Nobu Tamura",
  "license": "CC BY-SA 4.0",
  "description": "(1-2 sentence description of the creature/biome)",
  "tags": ["(relevant tags like 'dinosaur', 'paleozoic', 'theropod', 'invertebrate', etc.)"],
  "keyframes": ["(the specific geological periods this belongs to, e.g. 'late_cretaceous', 'cambrian')"],
  "source_url": "{post['url']}"
}}
"""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        # Extract JSON (in case Claude wraps it)
        text = response.content[0].text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(text)
    except Exception as e:
        print(f"Claude API Error: {e}")
        return None

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("Please enter your Anthropic API Key: ").strip()
        
    client = anthropic.Anthropic(api_key=api_key)
    
    used_urls = get_used_urls()
    print(f"Loaded {len(used_urls)} already-used URLs to skip.")
    
    all_posts = scrape_all_posts()
    
    # Filter
    new_posts = [p for p in all_posts if p['url'] not in used_urls]
    print(f"\n--- FOUND {len(new_posts)} BRAND NEW IMAGES TO IMPORT ---")
    
    if len(new_posts) == 0:
        print("Nothing new to import!")
        sys.exit(0)
        
    proceed = input("Do you want to proceed with downloading and categorizing these via Claude API? (y/n): ")
    if proceed.lower() != 'y':
        sys.exit(0)
        
    # Load JSON library
    with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)
        
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)

    success_count = 0
    for i, post in enumerate(new_posts, 1):
        print(f"\n[{i}/{len(new_posts)}] Processing: {post['title']}")
        
        # 1. Ask Claude
        metadata = categorize_with_claude(client, post)
        if not metadata:
            print("  -> Failed to generate metadata. Skipping.")
            continue
            
        # 2. Download Image
        filename = metadata.get("filename", f"nobu_tamura_{i}.jpg")
        # Ensure it ends with jpg/png based on the original link
        ext = post['image_url'].split('.')[-1].lower()
        if ext in ['jpg', 'jpeg', 'png'] and not filename.endswith(ext):
             filename = filename.split('.')[0] + '.' + ext
        metadata['filename'] = filename
        
        filepath = os.path.join(IMAGES_DIR, filename)
        
        try:
            req = urllib.request.Request(post['image_url'], headers={'User-Agent': 'Mozilla/5.0'})
            img_data = urllib.request.urlopen(req).read()
            with open(filepath, "wb") as f:
                f.write(img_data)
            print(f"  -> Saved {filename}")
        except Exception as e:
            print(f"  -> Failed to download image: {e}")
            continue
            
        # 3. Append to DB
        db["images"].append(metadata)
        success_count += 1
        
        # Save incrementally so we don't lose progress if it crashes
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
            
        # Sleep to respect API rate limits
        time.sleep(1)
        
    print(f"\nFinished! Successfully imported {success_count} new images.")

if __name__ == "__main__":
    main()



