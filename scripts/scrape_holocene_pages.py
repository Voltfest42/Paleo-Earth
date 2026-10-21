import os
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import time
import unicodedata

WIKI_API = 'https://en.wikipedia.org/w/api.php'
HEADERS = {'User-Agent': 'PaleoEarthBot/2.0 (https://paleo-earth.com; educational research; axel.eriksen91@gmail.com)'}

OUTPUT_BASE = os.path.join(os.getcwd(), 'images', 'wikipedia_images')
OUTPUT_JSON = os.path.join(os.getcwd(), 'data', 'wikipedia_images_temp.json')

PAGES = [
    'Neolithic_Revolution',
    'Göbekli_Tepe'
]

def clean_html(raw_html):
    if not raw_html: return ''
    cleanr = re.compile(r'<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def sanitize_filename(name):
    # Convert to pure ASCII, strip Turkish/accented marks (e.g. Göbekli -> Gobekli, Şanlıurfa -> Sanliurfa)
    n = unicodedata.normalize('NFKD', name)
    n = n.encode('ascii', 'ignore').decode('ascii')
    # Replace spaces, commas, parentheses, quotes
    n = re.sub(r'[\s,;:()\[\]{}"\'`!?*<>|]+', '_', n)
    n = re.sub(r'_+', '_', n)
    n = n.strip('_')
    base, ext = os.path.splitext(n)
    if len(base) > 60:
        base = base[:60].rstrip('_')
    return f"{base}{ext}"

def get_page_images(title):
    params = {
        'action': 'query',
        'prop': 'images',
        'titles': title,
        'redirects': '1',
        'format': 'json',
        'imlimit': 'max'
    }
    url = f"{WIKI_API}?{urllib.parse.urlencode(params)}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
            pages = resp.get('query', {}).get('pages', {})
            images = []
            for pid, pdata in pages.items():
                for img in pdata.get('images', []):
                    t = img['title']
                    tl = t.lower()
                    if tl.endswith(('.ogg', '.ogv', '.pdf', '.mid', '.djvu', '.xcf', '.gif')): continue
                    if any(bad in tl for bad in ['icon', 'symbol', 'flag of', 'commons-logo', 'emojione', 'wiki letter', 'red pog', 'semi-protection']):
                        continue
                    images.append(t)
            return images
        except Exception:
            time.sleep(2)
    return []

def get_batch_image_info(file_titles):
    if not file_titles: return {}
    results = {}
    for i in range(0, len(file_titles), 30):
        chunk = file_titles[i:i+30]
        params = {
            'action': 'query',
            'prop': 'imageinfo',
            'iiprop': 'url|extmetadata',
            'iiurlwidth': 1920,
            'titles': '|'.join(chunk),
            'format': 'json'
        }
        url = f"{WIKI_API}?{urllib.parse.urlencode(params)}"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
                pages = resp.get('query', {}).get('pages', {})
                for pid, pinfo in pages.items():
                    t = pinfo.get('title')
                    if 'imageinfo' in pinfo and pinfo['imageinfo']:
                        results[t] = pinfo['imageinfo'][0]
                break
            except Exception:
                time.sleep(2)
        time.sleep(0.5)
    return results

def download_file_with_retry(url, target_filepath, max_retries=5):
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                with open(target_filepath, 'wb') as out_f:
                    out_f.write(data)
            time.sleep(1.0)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 7 + (attempt * 4)
                print(f"    [RATE LIMIT 429] Waiting {wait_time}s on attempt {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                print(f"    [HTTP ERROR {e.code}] {e}")
                return False
        except Exception as e:
            print(f"    [DOWNLOAD ERROR] {e}")
            time.sleep(2)
    return False

def main():
    folder_dir = os.path.join(OUTPUT_BASE, 'holocene')
    os.makedirs(folder_dir, exist_ok=True)

    existing_records = []
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            try:
                existing_records = json.load(f)
            except Exception:
                existing_records = []

    records_by_relpath = {r['filename']: r for r in existing_records}
    downloaded_count = 0

    for page in PAGES:
        safe_page_title = page.encode('ascii', 'replace').decode('ascii')
        print(f"\nScanning {safe_page_title} -> images/wikipedia_images/holocene/...")
        file_titles = get_page_images(page)
        info_map = get_batch_image_info(file_titles)

        for ft in file_titles:
            info = info_map.get(ft)
            if not info:
                continue

            url = info.get('thumburl') if ft.lower().endswith('.svg') and info.get('thumburl') else info.get('url')
            if not url:
                url = info.get('url')
            if not url:
                continue

            raw_url = url.split('?')[0]
            orig_filename = urllib.parse.unquote(raw_url.split('/')[-1])
            filename = sanitize_filename(orig_filename)
            rel_path = f"holocene/{filename}"

            extmeta = info.get('extmetadata', {})
            artist = clean_html(extmeta.get('Artist', {}).get('value', ''))
            desc = clean_html(extmeta.get('ImageDescription', {}).get('value', ''))
            lic = extmeta.get('LicenseShortName', {}).get('value', 'Unknown')

            target_filepath = os.path.join(folder_dir, filename)

            if os.path.exists(target_filepath) and os.path.getsize(target_filepath) > 0:
                print(f"  [EXISTS] {filename}")
            else:
                print(f"  Downloading: {filename}...")
                ok = download_file_with_retry(url, target_filepath)
                if ok:
                    print(f"    [OK] Downloaded {filename} ({os.path.getsize(target_filepath)} bytes)")
                    downloaded_count += 1
                else:
                    print(f"    [FAILED] {filename}")
                    continue

            records_by_relpath[rel_path] = {
                "filename": rel_path,
                "title": desc[:250] + ("..." if len(desc) > 250 else ""),
                "creator": artist,
                "license": lic,
                "source_url": info.get("descriptionurl", ""),
                "keyframes": ["holocene"]
            }

    final_records = list(records_by_relpath.values())
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(final_records, f, indent=2, ensure_ascii=False)

    print(f"\n=======================================================")
    print(f"Holocene Scraping Complete!")
    print(f"New images downloaded: {downloaded_count}")
    print(f"Total cataloged records: {len(final_records)}")
    print(f"=======================================================")

if __name__ == '__main__':
    main()
