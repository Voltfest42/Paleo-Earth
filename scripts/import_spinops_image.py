#!/usr/bin/env python3
"""
import_spinops_image.py
=======================
Automates importing paleoart illustrations from Nobu Tamura's portfolio blog
(https://spinops.blogspot.com/) into Paleo Earth.

What it does:
1. Fetches post metadata (post ID, title, systematics, horizon/locality, size, description)
   via Blogger's JSON feed.
2. Extracts and downloads the highest available resolution web image to `images/`.
3. Determines appropriate tags and maps geological age to Paleo Earth's 47 keyframe IDs.
4. Generates a clean, factual entry and updates `data/image-library.json`.

Usage:
    python scripts/import_spinops_image.py <URL1> [URL2 ...]
    python scripts/import_spinops_image.py --file urls.txt
"""

import sys
import os
import re
import json
import html
import urllib.request
import urllib.error
from pathlib import Path

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = PROJECT_ROOT / "images"
IMAGE_LIB_PATH = PROJECT_ROOT / "data" / "image-library.json"
KEYFRAMES_PATH = PROJECT_ROOT / "data" / "keyframes.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Period / Epoch to Paleo Earth Keyframe mapping
AGE_KEYFRAME_MAP = [
    # Cenozoic
    (r'\bholocene\b', ["holocene"]),
    (r'\b(late\s+pleistocene|middle\s+pleistocene|mid\s+pleistocene)\b', ["mid_pleistocene"]),
    (r'\b(early\s+pleistocene|pleistocene|quaternary)\b', ["mid_pleistocene", "early_quaternary"]),
    (r'\b(pliocene|late\s+neogene)\b', ["late_neogene"]),
    (r'\b(late\s+miocene|middle\s+miocene|mid\s+miocene)\b', ["mid_neogene"]),
    (r'\b(early\s+miocene|miocene|neogene)\b', ["mid_neogene", "early_neogene"]),
    (r'\b(oligocene|late\s+paleogene)\b', ["late_paleogene", "eocene_oligocene_transition"]),
    (r'\b(middle\s+eocene|mid\s+eocene|eocene)\b', ["mid_paleogene", "eocene_oligocene_transition"]),
    (r'\b(early\s+eocene|petm)\b', ["mid_paleogene", "petm"]),
    (r'\b(paleocene|early\s+paleogene|danian)\b', ["early_paleogene"]),
    (r'\b(paleogene|tertiary)\b', ["early_paleogene", "mid_paleogene", "late_paleogene"]),

    # Mesozoic
    (r'\b(late\s+cretaceous|maastrichtian|campanian|santonian|coniacian|turonian|cenomanian)\b', ["late_cretaceous", "kpg_extinction"]),
    (r'\b(middle\s+cretaceous|mid\s+cretaceous|albian|aptian)\b', ["mid_cretaceous"]),
    (r'\b(early\s+cretaceous|lower\s+cretaceous|barremian|hauterivian|valanginian|berriasian)\b', ["early_cretaceous"]),
    (r'\bcretaceous\b', ["late_cretaceous", "mid_cretaceous", "early_cretaceous"]),

    (r'\b(late\s+jurassic|upper\s+jurassic|tithonian|kimmeridgian|oxfordian)\b', ["late_jurassic"]),
    (r'\b(middle\s+jurassic|mid\s+jurassic|callovian|bathonian|bajocian|aalenian)\b', ["mid_jurassic", "jurassic_marine_revolution"]),
    (r'\b(early\s+jurassic|lower\s+jurassic|toarcian|pliensbachian|sinemurian|hettangian)\b', ["early_jurassic"]),
    (r'\bjurassic\b', ["late_jurassic", "mid_jurassic", "early_jurassic"]),

    (r'\b(late\s+triassic|upper\s+triassic|rhaetian|norian|carnian)\b', ["late_triassic", "triassic_jurassic_extinction"]),
    (r'\b(middle\s+triassic|mid\s+triassic|ladinian|anisian)\b', ["mid_triassic"]),
    (r'\b(early\s+triassic|lower\s+triassic|olenekian|induan)\b', ["early_triassic", "permian_triassic_extinction"]),
    (r'\btriassic\b', ["late_triassic", "mid_triassic", "early_triassic"]),

    # Paleozoic
    (r'\b(late\s+permian|upper\s+permian|changhsingian|wuchiapingian|lopingian)\b', ["late_permian", "permian_triassic_extinction"]),
    (r'\b(middle\s+permian|mid\s+permian|guadalupian|capitanian|wordian|roadian)\b', ["mid_permian"]),
    (r'\b(early\s+permian|lower\s+permian|cisuralian|kungurian|artinskian|sakmarian|asselian)\b', ["early_permian"]),
    (r'\bpermian\b', ["late_permian", "mid_permian", "early_permian"]),

    (r'\b(late\s+carboniferous|pennsylvanian|gzhelian|kasimovian|moscovian|bashkirian)\b', ["late_carboniferous", "carboniferous_rainforest_collapse"]),
    (r'\b(middle\s+carboniferous|mid\s+carboniferous)\b', ["mid_carboniferous"]),
    (r'\b(early\s+carboniferous|mississippian|serpukhovian|visean|tournaisian)\b', ["early_carboniferous"]),
    (r'\bcarboniferous\b', ["late_carboniferous", "mid_carboniferous", "early_carboniferous"]),

    (r'\b(late\s+devonian|upper\s+devonian|famennian|frasnian)\b', ["late_devonian", "late_devonian_extinction"]),
    (r'\b(middle\s+devonian|mid\s+devonian|givetian|eifelian)\b', ["mid_devonian"]),
    (r'\b(early\s+devonian|lower\s+devonian|emsian|pragian|lochkovian)\b', ["early_devonian"]),
    (r'\bdevonian\b', ["late_devonian", "mid_devonian", "early_devonian"]),

    (r'\b(late\s+silurian|pridoli|ludlow)\b', ["late_silurian"]),
    (r'\b(middle\s+silurian|mid\s+silurian|wenlock)\b', ["mid_silurian"]),
    (r'\b(early\s+silurian|lower\s+silurian|llandovery)\b', ["early_silurian"]),
    (r'\bsilurian\b', ["late_silurian", "mid_silurian", "early_silurian"]),

    (r'\b(late\s+ordovician|upper\s+ordovician|katian|sandbian|hirnantian)\b', ["late_ordovician", "end_ordovician_extinction"]),
    (r'\b(middle\s+ordovician|mid\s+ordovician|darriwilian|dapingian)\b', ["mid_ordovician", "great_ordovician_biodiversification"]),
    (r'\b(early\s+ordovician|lower\s+ordovician|floian|tremadocian)\b', ["early_ordovician"]),
    (r'\bordovician\b', ["late_ordovician", "mid_ordovician", "early_ordovician"]),

    (r'\b(late\s+cambrian|upper\s+cambrian|furongian|jiangshanian|paibian)\b', ["late_cambrian"]),
    (r'\b(middle\s+cambrian|mid\s+cambrian|miaolingian|guzhangian|drumian|wuliuan)\b', ["mid_cambrian"]),
    (r'\b(early\s+cambrian|lower\s+cambrian|series\s+2|stage\s+4|stage\s+3|stage\s+2|terreneuvian|fortunian)\b', ["early_cambrian", "cambrian_explosion"]),
    (r'\bcambrian\b', ["early_cambrian", "mid_cambrian", "late_cambrian", "cambrian_explosion"]),
]

def fetch_url(url: str) -> str:
    """Fetch URL text with User-Agent header."""
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='ignore')

def get_post_id(html_text: str) -> str | None:
    """Extract Blogger postId from HTML."""
    m = re.search(r'["\']postId["\']\s*:\s*["\']?(\d+)', html_text)
    if m:
        return m.group(1)
    # Check alternate pattern
    m = re.search(r'post-(\d+)', html_text)
    if m:
        return m.group(1)
    return None

def clean_html_text(raw_html: str) -> str:
    """Strip tags and unescape HTML entities."""
    text = re.sub(r'<br\s*/?>', ' ', raw_html, flags=re.I)
    text = re.sub(r'</p>', ' ', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    return ' '.join(text.split())

def extract_metadata(entry: dict, page_html: str) -> dict:
    """Extract structured fields from Blogger post entry."""
    title_raw = entry.get('title', {}).get('$t', '').strip()
    content_html = entry.get('content', {}).get('$t', '')

    # Find image URLs
    # Priority: <a> href pointing to image > <img> src
    a_imgs = re.findall(r'<a[^>]+href=["\']([^"\']+\.(?:jpg|png|webp|jpeg)[^"\']*)["\']', content_html, re.I)
    img_tags = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content_html, re.I)

    image_candidates = a_imgs + img_tags
    if not image_candidates:
        # Fallback to page_html
        og_img = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', page_html)
        if og_img:
            image_candidates.append(og_img.group(1))

    raw_image_url = image_candidates[0] if image_candidates else None
    best_image_url = None
    if raw_image_url:
        # Switch to highest resolution available (s1600 or s0)
        best_image_url = re.sub(r'/(s\d+|w\d+-h\d+[^/]*)/', '/s1600/', raw_image_url)

    # Clean text
    clean_text = clean_html_text(content_html)

    # Extract Systematics
    sys_match = re.search(r'Systematics:\s*([^\n\r]+?)(?=\s*(?:Size:|Type Horizon|Type Specimen|Synonyms|$))', clean_text, re.I)
    systematics = sys_match.group(1).strip() if sys_match else ""

    # Extract Size
    size_match = re.search(r'Size:\s*([^\n\r]+?)(?=\s*(?:Type Horizon|Type Specimen|Synonyms|Systematics|$))', clean_text, re.I)
    size = size_match.group(1).strip() if size_match else ""

    # Extract Horizon and Locality
    horizon_match = re.search(r'Type Horizon and Locality:\s*([^\n\r]+?)(?=\s*(?:Type Specimen|Synonyms|Size|Systematics|$))', clean_text, re.I)
    horizon = horizon_match.group(1).strip() if horizon_match else ""

    # Extract Description body
    # Look for descriptive sentences outside the labeled fields
    desc_text = ""
    # Look for paragraph text following the metadata block
    paragraphs = re.findall(r'<p>(.*?)</p>', content_html, re.I | re.S)
    body_paras = []
    for p in paragraphs:
        p_clean = clean_html_text(p)
        if p_clean and not any(k in p_clean.lower() for k in ['systematics:', 'type horizon', 'all illustrations on this site', 'references:']):
            body_paras.append(p_clean)

    if body_paras:
        desc_text = ' '.join(body_paras)
    else:
        # Fallback from clean_text
        m_body = re.search(r'(?:Synonyms:[^.]*\.|\d{4}\.?)\s*([A-Z][^\n\r]+?)(?=\s*(?:References:|All illustrations|\b[A-Z][a-z]+ \d{1,2}, \d{4}))', clean_text)
        if m_body:
            desc_text = m_body.group(1).strip()

    # Organism name / Species
    species_name = title_raw
    if not species_name:
        m_sp = re.search(r'<b><i>([A-Za-z\s]+)</i>', content_html)
        if m_sp:
            species_name = m_sp.group(1).strip()

    return {
        "title": species_name.strip(),
        "image_url": best_image_url,
        "systematics": systematics,
        "size": size,
        "horizon": horizon,
        "description_body": desc_text,
        "raw_text": clean_text,
    }

def derive_classification(meta: dict) -> dict:
    """Generate tags, keyframes, title, id, and description for image-library.json."""
    title = meta["title"]
    # Genus and species tokens
    words = [re.sub(r'[^a-zA-Z0-9]', '', w).lower() for w in title.split() if w]
    genus = words[0] if words else "fossil"
    species = words[1] if len(words) > 1 else ""

    # Unique id
    item_id = f"{genus}_{species}_tamura" if species else f"{genus}_tamura"

    # Filename
    filename = f"{genus}_{species}_nobu_tamura.jpg" if species else f"{genus}_nobu_tamura.jpg"

    combined_text = f"{meta['title']} {meta['systematics']} {meta['horizon']} {meta['description_body']} {meta['raw_text']}".lower()

    # Determine keyframes
    keyframes = set()
    for pattern, kf_list in AGE_KEYFRAME_MAP:
        if re.search(pattern, combined_text):
            keyframes.update(kf_list)
            break  # Stop at the most specific match

    if not keyframes:
        keyframes.add("early_cambrian")  # sensible default if unparsed

    # Determine tags
    tags = set()
    if genus: tags.add(genus)
    if species: tags.add(f"{genus}_{species}")

    # Broad taxonomic categories from systematics
    tax_terms = {
        "trilobita": ["trilobite", "arthropod", "marine_invertebrate"],
        "arthropoda": ["arthropod", "invertebrate"],
        "dinosauria": ["dinosaur", "reptile", "land_vertebrate"],
        "pterosauria": ["pterosaur", "flying_reptile"],
        "sauropterygia": ["marine_reptile", "sauropterygian"],
        "ichthyosauria": ["ichthyosaur", "marine_reptile"],
        "mosasauridae": ["mosasaur", "marine_reptile"],
        "placodermi": ["placoderm", "fish"],
        "actinopterygii": ["fish", "bony_fish"],
        "sarcopterygii": ["lobe_finned_fish", "fish"],
        "chondrichthyes": ["shark", "cartilaginous_fish"],
        "amphibia": ["amphibian", "tetrapod"],
        "synapsida": ["synapsid", "land_vertebrate"],
        "therapsida": ["therapsid", "synapsid"],
        "mammalia": ["mammal"],
        "mollusca": ["mollusc", "marine_invertebrate"],
        "ammonoidea": ["ammonite", "cephalopod", "mollusc"],
        "brachiopoda": ["brachiopod", "marine_invertebrate"],
        "echinodermata": ["echinoderm", "marine_invertebrate"],
        "chordata": ["chordate"],
    }
    for sys_key, tag_list in tax_terms.items():
        if sys_key in combined_text:
            tags.update(tag_list)

    # Eras & Periods
    eras = [
        ("cambrian", ["cambrian", "paleozoic"]),
        ("ordovician", ["ordovician", "paleozoic"]),
        ("silurian", ["silurian", "paleozoic"]),
        ("devonian", ["devonian", "paleozoic"]),
        ("carboniferous", ["carboniferous", "paleozoic"]),
        ("permian", ["permian", "paleozoic"]),
        ("triassic", ["triassic", "mesozoic"]),
        ("jurassic", ["jurassic", "mesozoic"]),
        ("cretaceous", ["cretaceous", "mesozoic"]),
        ("paleogene", ["paleogene", "cenozoic"]),
        ("neogene", ["neogene", "cenozoic"]),
        ("quaternary", ["quaternary", "cenozoic"]),
    ]
    for per, per_tags in eras:
        if per in combined_text:
            tags.update(per_tags)

    if any(m in combined_text for m in ["marine", "sea", "ocean", "reef", "seafloor"]):
        tags.add("marine")
    if any(m in combined_text for m in ["seafloor", "benthic", "bottom"]):
        tags.add("benthic")
    if any(m in combined_text for m in ["predator", "carnivore"]):
        tags.add("predator")

    # Include keyframe names as tags for easy AI matching
    for kf in keyframes:
        tags.add(kf)
        tags.add(kf.replace('_', ' '))

    # Build description
    desc_sentences = []
    if meta["description_body"]:
        # Protect abbreviations like 'F. ', 'T. ', 'sp. ', 'cf. ', 'al. '
        safe_text = re.sub(r'\b([A-Z])\.\s+', r'\1_DOT_ ', meta["description_body"])
        safe_text = re.sub(r'\b(sp|cf|al|ca|gen|no|coll)\.\s+', r'\1_DOT_ ', safe_text)
        # Split into sentences
        sentences = [
            re.sub(r'_DOT_', '.', s).strip()
            for s in re.split(r'(?<=[.!?])\s+', safe_text)
            if s.strip()
        ]
        # Clean up known typos in raw text
        cleaned_sentences = []
        for s in sentences:
            s_clean = s.replace("wordlwide", "worldwide")
            cleaned_sentences.append(s_clean)
        desc_sentences = cleaned_sentences[:2]
    else:
        # Fallback synthesis
        h = meta.get("horizon", "")
        sz = meta.get("size", "")
        desc = f"{title}"
        if sz: desc += f" (~{sz})"
        if h: desc += f" from {h}"
        desc += "."
        desc_sentences.append(desc)

    description = " ".join(desc_sentences)

    return {
        "id": item_id,
        "filename": filename,
        "title": title,
        "credit": "Nobu Tamura",
        "license": "CC BY-SA 4.0",
        "description": description,
        "tags": sorted(list(tags)),
        "keyframes": sorted(list(keyframes))
    }

def process_url(url: str) -> dict:
    """Download image and return entry dict for image-library.json."""
    print(f"\nProcessing: {url}")
    page_html = fetch_url(url)
    post_id = get_post_id(page_html)

    if not post_id:
        raise ValueError(f"Could not extract Blogger postId from {url}")

    feed_url = f"https://spinops.blogspot.com/feeds/posts/default/{post_id}?alt=json"
    feed_json = json.loads(fetch_url(feed_url))
    entry = feed_json.get('entry', {})

    meta = extract_metadata(entry, page_html)
    record = derive_classification(meta)

    # Download image
    img_url = meta.get("image_url")
    if not img_url:
        raise ValueError(f"No image found for {url}")

    dest_file = IMAGES_DIR / record["filename"]
    print(f"Downloading image from: {img_url}")
    req = urllib.request.Request(img_url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest_file, "wb") as f:
        f.write(resp.read())

    print(f"Saved image to: {dest_file} ({dest_file.stat().st_size:,} bytes)")
    return record

def update_image_library(new_entries: list[dict]):
    """Insert or update entries in data/image-library.json."""
    if not IMAGE_LIB_PATH.exists():
        data = {"images": []}
    else:
        with open(IMAGE_LIB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

    existing_images = data.get("images", [])
    id_map = {item["id"]: i for i, item in enumerate(existing_images)}

    for entry in new_entries:
        if entry["id"] in id_map:
            idx = id_map[entry["id"]]
            print(f"Updating existing entry: {entry['id']}")
            existing_images[idx] = entry
        else:
            print(f"Adding new entry: {entry['id']}")
            existing_images.append(entry)

    data["images"] = existing_images

    with open(IMAGE_LIB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nSuccessfully updated {IMAGE_LIB_PATH} (total entries: {len(existing_images)})")

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_spinops_image.py <URL1> [URL2 ...]")
        print("   or: python scripts/import_spinops_image.py --file urls.txt")
        sys.exit(1)

    urls = []
    if sys.argv[1] == "--file":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        urls = [arg.strip() for arg in sys.argv[1:] if arg.strip()]

    new_entries = []
    for u in urls:
        try:
            entry = process_url(u)
            new_entries.append(entry)
        except Exception as e:
            print(f"Error processing {u}: {e}")

    if new_entries:
        update_image_library(new_entries)

if __name__ == "__main__":
    main()
