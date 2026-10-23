import os
import json
import urllib.request
import urllib.parse
import re
import time

WIKI_API = "https://en.wikipedia.org/w/api.php"

PERIODS = [
    "Cambrian", "Ordovician", "Silurian", "Devonian", "Carboniferous", 
    "Permian", "Triassic", "Jurassic", "Cretaceous", "Paleogene", 
    "Neogene", "Quaternary"
]

OUTPUT_DIR = os.path.join(os.getcwd(), "images", "wikipedia_images")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_JSON = os.path.join(os.getcwd(), "data", "wikipedia_images_temp.json")

def api_get(params):
    query_string = urllib.parse.urlencode(params)
    url = f"{WIKI_API}?{query_string}"
    req = urllib.request.Request(url, headers={'User-Agent': 'PaleoEarthBot/2.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"API Error: {e}")
        return {}

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def get_images_for_page(page_title):
    params = {
        "action": "query",
        "prop": "images",
        "titles": page_title,
        "format": "json",
        "imlimit": "max"
    }
    images = []
    while True:
        resp = api_get(params)
        pages = resp.get("query", {}).get("pages", {})
        for page_id, page_info in pages.items():
            if "images" in page_info:
                for img in page_info["images"]:
                    title = img["title"]
                    if title.lower().endswith(('.svg', '.ogg', '.ogv', '.pdf', '.mid', '.djvu', '.xcf')): continue
                    if "icon" in title.lower() or "symbol" in title.lower(): continue
                    images.append(title)
        
        if "continue" in resp:
            params.update(resp["continue"])
        else:
            break
    return images

def get_image_info(file_title):
    params = {
        "action": "query",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "titles": file_title,
        "format": "json"
    }
    resp = api_get(params)
    pages = resp.get("query", {}).get("pages", {})
    for page_id, page_info in pages.items():
        if "imageinfo" in page_info:
            return page_info["imageinfo"][0]
    return None

def main():
    collected_images = []
    downloaded_filenames = set()

    for period in PERIODS:
        print(f"\nScanning {period}...")
        
        # Create subfolder for this period
        period_dir = os.path.join(OUTPUT_DIR, period.lower())
        os.makedirs(period_dir, exist_ok=True)
        
        file_titles = get_images_for_page(period)
        print(f"Found {len(file_titles)} potential images.")

        for f_title in file_titles:
            info = get_image_info(f_title)
            if not info:
                continue

            url = info.get("url")
            if not url:
                continue
                
            extmeta = info.get("extmetadata", {})
            artist_html = extmeta.get("Artist", {}).get("value", "")
            artist = clean_html(artist_html)
            desc_html = extmeta.get("ImageDescription", {}).get("value", "")
            desc = clean_html(desc_html)
            license_name = extmeta.get("LicenseShortName", {}).get("value", "Public Domain / Unknown")

            search_text = (artist + " " + desc + " " + f_title).lower()
            
            if "tamura" in search_text:
                print(f"  [SKIP] Nobu Tamura: {f_title}")
                continue
            if "scotese" in search_text or "paleogeography" in search_text or "map" in f_title.lower() or "globe" in search_text:
                print(f"  [SKIP] Map/Scotese: {f_title}")
                continue

            # Strip query params (e.g. ?utm_source=...) before splitting
            clean_url = url.split("?")[0]
            filename = urllib.parse.unquote(clean_url.split("/")[-1])
            filename = re.sub(r'[\\/*?:"<>|]', "", filename)
            
            if filename in downloaded_filenames:
                for record in collected_images:
                    if record["filename"] == filename and period.lower() not in record["keyframes"]:
                        record["keyframes"].append(period.lower())
                continue

            # Save in period-specific folder
            filepath = os.path.join(period_dir, filename)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'PaleoEarthBot/2.0'})
                with urllib.request.urlopen(req) as response:
                    with open(filepath, 'wb') as f:
                        f.write(response.read())
            except Exception as e:
                print(f"  [ERROR] Failed to download {filename}: {e}")
                continue

            print(f"  [OK] Downloaded {filename} to {period.lower()}/")
            downloaded_filenames.add(filename)

            collected_images.append({
                "filename": f"{period.lower()}/{filename}",
                "title": desc[:200] + ("..." if len(desc) > 200 else ""),
                "creator": artist,
                "license": license_name,
                "source_url": info.get("descriptionurl", ""),
                "keyframes": [period.lower()]
            })

            time.sleep(0.1)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(collected_images, f, indent=2, ensure_ascii=False)
    
    print(f"\nDone! Scraped {len(collected_images)} images.")
    print(f"Metadata saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
