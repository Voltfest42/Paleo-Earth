import os
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import time

WIKI_API = 'https://en.wikipedia.org/w/api.php'
HEADERS = {'User-Agent': 'PaleoEarthBot/2.0 (https://paleo-earth.com; educational research; axel.eriksen91@gmail.com)'}

OUTPUT_BASE = os.path.join(os.getcwd(), 'images', 'wikipedia_images')
OUTPUT_JSON = os.path.join(os.getcwd(), 'data', 'wikipedia_images_temp.json')

PAGES_CONFIG = [
    {'page': 'Late_Pleistocene', 'folder': 'quaternary', 'keyframes': ['quaternary', 'mid_pleistocene', 'late_pleistocene']},
    {'page': 'Pleistocene', 'folder': 'quaternary', 'keyframes': ['quaternary', 'mid_pleistocene', 'early_quaternary']},
    {'page': 'Pliocene', 'folder': 'neogene', 'keyframes': ['neogene', 'late_neogene']},
    {'page': 'Miocene', 'folder': 'neogene', 'keyframes': ['neogene', 'mid_neogene', 'early_neogene']},
    {'page': 'Cretaceous–Paleogene_extinction_event', 'folder': 'kpg_extinction', 'keyframes': ['kpg_extinction', 'late_cretaceous']},
    {'page': 'Triassic–Jurassic_extinction', 'folder': 'triassic_jurassic_extinction', 'keyframes': ['triassic_jurassic_extinction', 'late_triassic']},
    {'page': 'Permian–Triassic_extinction_event', 'folder': 'permian_triassic_extinction', 'keyframes': ['permian_triassic_extinction', 'late_permian']},
    {'page': 'Carboniferous_rainforest_collapse', 'folder': 'carboniferous_rainforest_collapse', 'keyframes': ['carboniferous_rainforest_collapse', 'mid_carboniferous', 'late_carboniferous']},
    {'page': 'Late_Devonian_mass_extinction', 'folder': 'late_devonian_extinction', 'keyframes': ['late_devonian_extinction', 'late_devonian']},
    {'page': 'Late_Ordovician_mass_extinction', 'folder': 'end_ordovician_extinction', 'keyframes': ['end_ordovician_extinction', 'late_ordovician']}
]

def clean_html(raw_html):
    if not raw_html: return ''
    cleanr = re.compile(r'<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

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
                    if t.lower().endswith(('.svg', '.ogg', '.ogv', '.pdf', '.mid', '.djvu', '.xcf', '.gif')): continue
                    if 'icon' in t.lower() or 'symbol' in t.lower(): continue
                    images.append(t)
            return images
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  [API 429] Waiting 5s before retry...")
                time.sleep(5)
            else:
                break
        except Exception:
            time.sleep(2)
    return []

def get_batch_image_info(file_titles):
    if not file_titles: return {}
    results = {}
    for i in range(0, len(file_titles), 40):
        chunk = file_titles[i:i+40]
        params = {
            'action': 'query',
            'prop': 'imageinfo',
            'iiprop': 'url|extmetadata',
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
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    print(f"  [IMAGEINFO 429] Waiting 6s before retry...")
                    time.sleep(6)
                else:
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
            time.sleep(1.2)  # Polite spacing between downloads
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
    existing_records = []
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            try:
                existing_records = json.load(f)
            except Exception:
                existing_records = []

    records_by_relpath = {r['filename']: r for r in existing_records}
    downloaded_set = set(records_by_relpath.keys())
    
    new_downloads_count = 0
    updated_count = 0

    for cfg in PAGES_CONFIG:
        page = cfg['page']
        folder = cfg['folder']
        keyframes = cfg['keyframes']
        
        folder_dir = os.path.join(OUTPUT_BASE, folder)
        os.makedirs(folder_dir, exist_ok=True)
        
        print(f"\nProcessing {page} -> images/wikipedia_images/{folder}/...")
        file_titles = get_page_images(page)
        info_map = get_batch_image_info(file_titles)
        
        for ft in file_titles:
            info = info_map.get(ft)
            if not info or not info.get('url'):
                continue
                
            extmeta = info.get('extmetadata', {})
            artist = clean_html(extmeta.get('Artist', {}).get('value', ''))
            desc = clean_html(extmeta.get('ImageDescription', {}).get('value', ''))
            license_name = extmeta.get('LicenseShortName', {}).get('value', 'Public Domain / Unknown')
            
            raw_url = info.get('url', '')
            clean_url = raw_url.split('?')[0]
            filename = urllib.parse.unquote(clean_url.split('/')[-1])
            filename = re.sub(r'[\/:*?"<>|]', '', filename)
            rel_path = f"{folder}/{filename}"
            
            search_text = f"{artist} {desc} {ft} {filename}".lower()
            
            if 'tamura' in search_text:
                continue
            if 'scotese' in search_text or 'paleogeography' in search_text or 'map' in ft.lower() or 'globe' in search_text or 'chart' in ft.lower():
                continue
            if 'bufo periglenes' in search_text:
                continue
            if 'blue marble' in search_text or 'as17-148' in search_text:
                continue
            if 'stratigraphic column' in search_text:
                continue
            if 'temperature' in search_text and ('climate' in search_text or 'recovery' in search_text or 'cycles' in search_text):
                continue

            target_filepath = os.path.join(folder_dir, filename)

            # Check if file already exists on disk
            if os.path.exists(target_filepath) and os.path.getsize(target_filepath) > 0:
                # Register in records if not present
                if rel_path not in records_by_relpath:
                    records_by_relpath[rel_path] = {
                        "filename": rel_path,
                        "title": desc[:250] + ("..." if len(desc) > 250 else ""),
                        "creator": artist,
                        "license": license_name,
                        "source_url": info.get("descriptionurl", ""),
                        "keyframes": keyframes
                    }
                else:
                    rec = records_by_relpath[rel_path]
                    for kf in keyframes:
                        if kf not in rec.get('keyframes', []):
                            rec['keyframes'].append(kf)
                            updated_count += 1
                continue

            # File needs download
            print(f"  Downloading: {filename}...")
            success = download_file_with_retry(raw_url, target_filepath)
            if success:
                print(f"    [OK] Downloaded {filename} ({os.path.getsize(target_filepath)} bytes)")
                new_downloads_count += 1
                records_by_relpath[rel_path] = {
                    "filename": rel_path,
                    "title": desc[:250] + ("..." if len(desc) > 250 else ""),
                    "creator": artist,
                    "license": license_name,
                    "source_url": info.get("descriptionurl", ""),
                    "keyframes": keyframes
                }
            else:
                print(f"    [FAILED] {filename}")

    # Save merged records
    final_records = list(records_by_relpath.values())
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(final_records, f, indent=2, ensure_ascii=False)

    print(f"\n=======================================================")
    print(f"Scraping & Download Complete!")
    print(f"New images downloaded: {new_downloads_count}")
    print(f"Records updated: {updated_count}")
    print(f"Total cataloged images: {len(final_records)}")
    print(f"=======================================================")

if __name__ == '__main__':
    main()
