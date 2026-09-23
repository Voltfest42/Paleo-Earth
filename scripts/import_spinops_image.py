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

TAXON_SUFFIXES = r'(idae|inae|oidea|ida|ina|ata|morpha|ales|acea|formes)$'
LOC_WORDS = ['china', 'canada', 'uk', 'usa', 'us', 'morocco', 'russia', 'australia', 'germany', 'france', 'spain', 'greenland']
GEO_TERMS = [
    'cambrian', 'ordovician', 'silurian', 'devonian', 'carboniferous', 'permian',
    'triassic', 'jurassic', 'cretaceous', 'paleogene', 'neogene', 'quaternary',
    'pleistocene', 'holocene', 'burgess shale', 'chengjiang', 'maotianshan',
    'formation', 'shale', 'biota', 'member', 'fauna', 'stage', 'series'
]
TAXON_ROOTS = [
    'arthropoda', 'trilobita', 'chordata', 'porifera', 'cnidaria', 'mollusca',
    'brachiopoda', 'echinodermata', 'lobopodia', 'panarthropoda', 'demospongea',
    'anthozoa', 'chelicerata', 'crustacea', 'malacostraca', 'ambulacraria'
]

def extract_lines(raw_html: str) -> list[str]:
    """Break HTML into non-empty, stripped lines excluding footer boilerplate."""
    text = re.sub(r'<br\s*/?>', '\n', raw_html, flags=re.I)
    text = re.sub(r'</p>', '\n', text, flags=re.I)
    text = re.sub(r'</div>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    raw_lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in text.split('\n')]
    lines = []
    for l in raw_lines:
        if not l: continue
        if any(skip in l.lower() for skip in ['all illustrations on this site', 'all images on this site', 'references:', 'high resolution versions', 'questions: contact me', 'geyer, g.']):
            break
        if re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$', l):
            continue
        lines.append(l)
    return lines

def extract_metadata(entry: dict, page_html: str) -> dict:
    """Extract structured fields from Blogger post entry."""
    title_raw = entry.get('title', {}).get('$t', '').strip()
    content_html = entry.get('content', {}).get('$t', '')

    # Find image URLs
    a_imgs = re.findall(r'<a[^>]+href=["\']([^"\']+\.(?:jpg|png|webp|jpeg)[^"\']*)["\']', content_html, re.I)
    img_tags = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content_html, re.I)

    image_candidates = a_imgs + img_tags
    if not image_candidates:
        og_img = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', page_html)
        if og_img:
            image_candidates.append(og_img.group(1))

    raw_image_url = image_candidates[0] if image_candidates else None
    best_image_url = None
    if raw_image_url:
        best_image_url = re.sub(r'/(s\d+|w\d+-h\d+[^/]*)/', '/s1600/', raw_image_url)

    lines = extract_lines(content_html)
    species_name = title_raw or (lines[0] if lines else "")
    # Clean species name (remove author/year e.g. "Hall, 1859" or "(Neltner & Poctey, 1950)")
    clean_title = re.sub(r'\s*\(?[A-Z][a-zA-Z\s&,.]+\d{4}\)?.*$', '', species_name).strip()
    if not clean_title:
        clean_title = species_name

    systematics_parts = []
    horizon_parts = []
    size_parts = []
    desc_paras = []

    for line in lines[1:]:
        l_low = line.lower()
        if line.startswith('Systematics:'):
            systematics_parts.append(line.replace('Systematics:', '').strip())
        elif line.startswith('Size:') or line.startswith('Length:'):
            val = re.sub(r'^(Size|Length):\s*', '', line).strip()
            if val: size_parts.append(val)
        elif line.startswith('Type Horizon') or line.startswith('Horizon'):
            horizon_parts.append(re.sub(r'^(Type Horizon and Locality|Type Horizon|Horizon):\s*', '', line).strip())
        elif line.startswith('Type Specimen') or line.startswith('Synonyms:'):
            continue
        elif any(t in l_low for t in TAXON_ROOTS) and len(line.split()) <= 6:
            systematics_parts.append(line)
        elif any(g in l_low for g in GEO_TERMS) and len(line.split()) <= 15:
            horizon_parts.append(line)
        elif re.match(r'^(up to\s+)?\d+(\.\d+)?\s*(cm|mm|m)\b', line, re.I):
            size_parts.append(line)
        else:
            # Check if line is short and looks like metadata
            words = line.split()
            if len(words) <= 4:
                if any(re.search(TAXON_SUFFIXES, w.lower().rstrip(',.')) for w in words):
                    systematics_parts.append(line)
                    continue
                if any(loc in l_low for loc in LOC_WORDS):
                    horizon_parts.append(line)
                    continue
                if l_low.startswith('length') or l_low.startswith('size'):
                    continue
            if len(words) >= 5 or '.' in line:
                desc_paras.append(line)

    desc_text = " ".join(desc_paras)
    clean_text = " ".join(lines)

    return {
        "title": clean_title.strip(),
        "image_url": best_image_url,
        "systematics": " ".join(systematics_parts),
        "size": ", ".join(size_parts),
        "horizon": " ".join(horizon_parts),
        "description_body": desc_text,
        "raw_text": clean_text,
    }

ECOSYSTEM_CATALOG = {
    "burgess_shale": {
        "id": "burgess_shale_fauna_tamura",
        "filename": "burgess_shale_fauna_nobu_tamura.jpg",
        "title": "Burgess Shale Marine Community",
        "description": "A composite ecosystem reconstruction of the Middle Cambrian Burgess Shale biota (~508 Ma, British Columbia, Canada). Featured are the apex radiodont predator Anomalocaris and giant Hurdia, the five-eyed Opabinia, the spiny slug-like Wiwaxia, the early fish Metaspriggina, the lace crab Marrella, swimming Waptia, and benthic sponges.",
        "tags": [
            "burgess_shale", "burgess_shale_fauna", "cambrian", "mid_cambrian", "middle_cambrian", "paleozoic",
            "anomalocaris", "opabinia", "wiwaxia", "hallucigenia", "hurdia", "marrella", "metaspriggina", "waptia", "ottoia",
            "radiodont", "apex_predator", "lobopod", "arthropod", "marine_invertebrate", "early_vertebrate", "chordate",
            "marine", "benthic", "ecosystem", "seafloor", "community"
        ],
        "keyframes": ["mid_cambrian"]
    },
    "chengjiang": {
        "id": "chengjiang_fauna_tamura",
        "filename": "chengjiang_fauna_nobu_tamura.jpg",
        "title": "Chengjiang Biota Seafloor Community",
        "description": "A vibrant reconstruction of the Early Cambrian Chengjiang marine ecosystem (~520 Ma, Yunnan, China). Featured are the apex predator Anomalocaris saron in the water column, the enigmatic bivalved vetulicolian Didazoon, swimming stem-vertebrate fish Haikouichthys, crawling trilobites, the armored lobopod Diania, and seafloor sea anemones (Archisaccophyllia).",
        "tags": [
            "chengjiang", "chengjiang_biota", "chengjiang_fauna", "maotianshan_shale", "cambrian", "early_cambrian", "cambrian_explosion", "paleozoic",
            "anomalocaris", "vetulicolia", "didazoon", "haikouichthys", "myllokunmingia", "fuxianhuia", "diania", "archisaccophyllia", "trilobite",
            "radiodont", "apex_predator", "early_vertebrate", "chordate", "lobopod", "arthropod", "marine_invertebrate", "sea_anemone",
            "marine", "benthic", "ecosystem", "seafloor", "community"
        ],
        "keyframes": ["early_cambrian", "cambrian_explosion"]
    },
    "euphaneropida": {
        "id": "euphaneropida_tamura",
        "filename": "euphaneropida_nobu_tamura.jpg",
        "title": "Euphaneropida and Relatives",
        "description": "A comparative overview of early jawless fish belonging to the order Euphanerida (Anaspidomorphi) across the Silurian and Devonian periods. Featured are the Silurian forms Ciderius cooperi and Jamoytius kerwoodi, alongside Devonian forms Achanarella trewini, Cornovichthys blaaeweni, Euphanerops longaevus, and Endeiolepis aneri.",
        "tags": [
            "achanarella", "anaspidomorphi", "chordate", "ciderius", "community", "composite",
            "cornovichthys", "devonian", "early_silurian", "early_vertebrate", "endeiolepis",
            "euphanerida", "euphaneropida", "euphanerops", "fish", "jamoytius", "jawless_fish",
            "late_devonian", "marine", "mid_devonian", "mid_silurian", "paleozoic", "silurian"
        ],
        "keyframes": ["early_silurian", "late_devonian", "mid_devonian", "mid_silurian"]
    },
    "wenlock (late silurian) fish": {
        "id": "wenlock_silurian_fish_scotland_tamura",
        "filename": "wenlock_silurian_fish_scotland_nobu_tamura.jpg",
        "title": "Wenlock Silurian Fish Fauna of Scotland",
        "description": "A composite reconstruction of early jawless fish from the Wenlock Silurian fish beds of Scotland (~430 Ma). Featured are the armored osteostracan Ateleaspis tessellata, the spiny thelodonts Lanarkia horrida and Shielia taiti, the anaspids Birkenia and the enigmatic stickleback-like Lasanius problematicus, and the euphanerid Ciderius cooperi.",
        "tags": [
            "anaspida", "ateleaspis", "birkenia", "chordate", "ciderius", "community", "composite",
            "early_silurian", "early_vertebrate", "ecosystem", "fish", "jawless_fish", "lanarkia",
            "lasanius", "marine", "mid_silurian", "osteostraci", "paleozoic", "scotland", "shielia",
            "silurian", "silurian_fish", "thelodonti", "wenlock"
        ],
        "keyframes": ["early_silurian", "mid_silurian"]
    },
    "symmoriiformes": {
        "id": "symmoriiformes_tamura",
        "filename": "symmoriiformes_nobu_tamura.jpg",
        "title": "Symmoriiformes (Anvil-Toothed Holocephalans)",
        "description": "A comparative reconstruction of bizarre symmoriiform cartilaginous fish (holocephalans) from the Devonian and Carboniferous periods. Featured are the iconic 'anvil-finned' Stethacanthus altonensis, Akmonistion zangerli, the sword-spined Falcatus falcatus, and Symmorium reniforme, illustrating their remarkable sexually dimorphic cranial brushes and dorsal spine-brush complexes.",
        "tags": [
            "akmonistion", "cartilaginous_fish", "chondrichthyes", "community", "composite",
            "devonian", "early_carboniferous", "falcatus", "fish", "holocephali",
            "late_devonian", "late_devonian_extinction", "marine", "mid_carboniferous",
            "paleozoic", "predator", "shark", "stethacanthus", "symmoriiformes", "symmorium"
        ],
        "keyframes": ["early_carboniferous", "late_devonian", "late_devonian_extinction", "mid_carboniferous"]
    },
    "early_echinoderms": {
        "id": "early_echinoderms_tamura",
        "filename": "early_echinoderms_nobu_tamura.jpg",
        "title": "Early Echinoderm Radiation",
        "description": "A comparative evolutionary overview of primitive stem-echinoderms from the Cambrian and Devonian periods. Illustrated are the basal bilateral ctenoid Ctenoimbricata spinosa, the ctenocystoid Ctenocystis utahensis, the cinctan Protocinctus mansillaensis, the eocrinoid Gogia spiralis, and the Lower Devonian mitrate carpoid Rhenocystis latipedunculata from the Hunsruck Slate.",
        "tags": [
            "benthic", "cambrian", "carpoid", "cinctan", "community", "composite",
            "ctenocystis", "ctenoimbricata", "devonian", "early_cambrian", "early_devonian",
            "echinoderm", "eocrinoid", "gogia", "hunsruck_slate", "marine",
            "marine_invertebrate", "mid_cambrian", "mitrate", "paleozoic", "protocinctus",
            "rhenocystis", "stem_echinoderm"
        ],
        "keyframes": ["early_cambrian", "early_devonian", "mid_cambrian"]
    }
}

CURATED_ENTRIES = {
    "arandaspis_prionotolepis": {
        "title": "Arandaspis prionotolepis",
        "description": "Arandaspis was one of the earliest known jawless fish (arandaspid), inhabiting shallow coastal waters of Gondwana (modern Australia) during the Ordovician. It was protected by hard dorsal and ventral armor shields with branchial openings and lacked paired fins.",
        "tags": [
            "arandaspid", "arandaspis", "arandaspis_prionotolepis", "australia", "chordate", "early_ordovician",
            "early_vertebrate", "fish", "gondwana", "great_ordovician_biodiversification", "jawless_fish",
            "marine", "mid_ordovician", "ordovician", "paleozoic"
        ],
        "keyframes": ["early_ordovician", "great_ordovician_biodiversification", "mid_ordovician"]
    },
    "helcionelloidea": {
        "title": "Helcionelloid Stem-Mollusks",
        "description": "Helcionelloids were an extinct group of primitive, cap-shaped stem-mollusks spanning the Early Cambrian to Early Ordovician. Many possessed an apical slit or snorkel-like pipe on their conchs, representing some of the earliest mineralized shelled mollusks.",
        "tags": [
            "benthic", "cambrian", "cambrian_explosion", "early_cambrian", "early_ordovician", "helcionellid",
            "helcionelloidea", "marine", "marine_invertebrate", "mid_cambrian", "mollusc", "ordovician",
            "paleozoic", "stem_mollusc"
        ],
        "keyframes": ["cambrian_explosion", "early_cambrian", "early_ordovician", "mid_cambrian"]
    },
    "cyrtoceras_sp": {
        "title": "Cyrtoceras sp.",
        "description": "Cyrtoceras was an early nautiloid cephalopod characterized by a gently curved conical shell (cyrtocone) with closely spaced septa and a central siphuncle, widely distributed in Paleozoic seas from the Middle Ordovician through the Devonian.",
        "tags": [
            "cephalopod", "cyrtoceras", "cyrtoceras_sp", "great_ordovician_biodiversification", "late_ordovician",
            "marine", "marine_invertebrate", "mid_ordovician", "mollusc", "nautiloid", "ordovician",
            "paleozoic", "predator"
        ],
        "keyframes": ["great_ordovician_biodiversification", "late_ordovician", "mid_ordovician"]
    },
    "tetragraptus_fruticosis": {
        "title": "Tetragraptus fruticosus",
        "description": "Tetragraptus fruticosus was a distinctive four-branched, tuning-fork-shaped planktonic graptolite colony. Graptolites were colonial hemichordates that drifted in open oceans worldwide and serve as key index fossils for the Ordovician.",
        "tags": [
            "colonial", "early_ordovician", "graptolite", "great_ordovician_biodiversification", "hemichordate",
            "marine", "mid_ordovician", "ordovician", "paleozoic", "planktonic", "tetragraptus", "tetragraptus_fruticosus"
        ],
        "keyframes": ["early_ordovician", "great_ordovician_biodiversification", "mid_ordovician"]
    },
    "sacabambaspis_janvieri": {
        "title": "Sacabambaspis janvieri",
        "description": "Sacabambaspis was an armored jawless fish (arandaspid) from the Ordovician of Gondwana (Bolivia). It possessed forward-facing close-set eyes, an inflexible dorsal and ventral armor shield, a blunt snout, and a long flexible tail.",
        "tags": [
            "arandaspid", "bolivia", "chordate", "early_vertebrate", "fish", "gondwana",
            "great_ordovician_biodiversification", "jawless_fish", "late_ordovician", "marine",
            "mid_ordovician", "ordovician", "paleozoic", "sacabambaspis", "sacabambaspis_janvieri"
        ],
        "keyframes": ["great_ordovician_biodiversification", "late_ordovician", "mid_ordovician"]
    },
    "astraspis_desiderata": {
        "title": "Astraspis desiderata",
        "description": "Astraspis was a primitive armored jawless fish from the Late Ordovician Harding Sandstone of Colorado. Its headshield was paved with hundreds of small star-patterned bony plates called tesserae, protecting one of North America's earliest known vertebrates.",
        "tags": [
            "arandaspid", "astraspis", "astraspis_desiderata", "chordate", "early_vertebrate",
            "end_ordovician_extinction", "fish", "harding_sandstone", "jawless_fish", "late_ordovician",
            "marine", "north_america", "ordovician", "paleozoic"
        ],
        "keyframes": ["end_ordovician_extinction", "late_ordovician"]
    },
    "aegirocassis_benmoulae": {
        "title": "Aegirocassis benmoulae",
        "description": "Reaching over two meters in length, Aegirocassis was a giant hurdiid radiodont from the Early Ordovician Fezouata biota of Morocco. Unlike earlier predatory radiodonts, Aegirocassis was a gentle suspension filter-feeder that strained plankton from the water column.",
        "tags": [
            "aegirocassis", "aegirocassis_benmoulae", "arthropod", "early_ordovician", "fezouata",
            "filter_feeder", "giant", "great_ordovician_biodiversification", "hurdiid", "marine",
            "marine_invertebrate", "morocco", "ordovician", "paleozoic", "radiodont"
        ],
        "keyframes": ["early_ordovician", "great_ordovician_biodiversification"]
    },
    "promissum_pulchrum": {
        "title": "Promissum pulchrum",
        "description": "Measuring up to 40 cm in length, Promissum was an exceptionally large eel-like conodont from the Late Ordovician Soom Shale of South Africa. Soft-tissue fossils demonstrate large eyes with extrinsic muscles and a complex phosphatic feeding apparatus.",
        "tags": [
            "chordate", "conodont", "early_vertebrate", "end_ordovician_extinction", "late_ordovician",
            "marine", "ordovician", "paleozoic", "promissum", "promissum_pulchrum", "soom_shale", "south_africa"
        ],
        "keyframes": ["end_ordovician_extinction", "late_ordovician"]
    },
    "calvapilosa_kroegeri": {
        "title": "Calvapilosa kroegeri",
        "description": "Calvapilosa was a slug-like stem-group mollusk (halwaxiid) from the Early Ordovician Fezouata Formation of Morocco. It had a single anterior cap-like shell plate, a dorsum covered in hollow spines, and an exquisitely preserved radula with 125 rows of teeth.",
        "tags": [
            "benthic", "calvapilosa", "calvapilosa_kroegeri", "early_ordovician", "fezouata",
            "great_ordovician_biodiversification", "halwaxiid", "marine", "marine_invertebrate",
            "mollusc", "morocco", "ordovician", "paleozoic", "stem_mollusc"
        ],
        "keyframes": ["early_ordovician", "great_ordovician_biodiversification"]
    },
    "obolus_apollinis": {
        "title": "Obolus apollinis",
        "description": "Obolus is an inarticulate linguliform brachiopod with a phosphatic shell, abundant across the Cambrian-Ordovician boundary in the Baltic region. Immense accumulations of its shells formed extensive fossiliferous sandstone layers known as Obolus sandstone.",
        "tags": [
            "baltic", "benthic", "brachiopod", "cambrian", "early_ordovician", "late_cambrian",
            "linguliform", "marine", "marine_invertebrate", "obolus", "obolus_apollinis", "ordovician", "paleozoic"
        ],
        "keyframes": ["early_ordovician", "late_cambrian"]
    },
    "calymene_blumenbachii": {
        "title": "Calymene blumenbachii",
        "description": "Affectionately known as the 'Dudley Bug', Calymene blumenbachii is an iconic calymenid trilobite from the Wenlock Silurian of England. It is famed for its tuberculated exoskeleton and its ability to enroll into a tight protective sphere.",
        "tags": [
            "arthropod", "benthic", "calymene", "calymene_blumenbachii", "early_silurian", "england",
            "marine", "marine_invertebrate", "mid_silurian", "paleozoic", "silurian", "trilobite", "wenlock"
        ],
        "keyframes": ["early_silurian", "mid_silurian"]
    },
    "triarthrus_eatoni": {
        "title": "Triarthrus eatoni",
        "description": "Specimens of this Late Ordovician olenid trilobite found at Beecher's Trilobite Bed (New York) exhibit exquisite pyritized preservation of delicate legs, gills, and antennae, offering rare insights into soft trilobite anatomy.",
        "tags": [
            "arthropod", "benthic", "end_ordovician_extinction", "late_ordovician", "marine",
            "marine_invertebrate", "new_york", "ordovician", "paleozoic", "pyrite", "triarthrus",
            "triarthrus_eatoni", "trilobite"
        ],
        "keyframes": ["end_ordovician_extinction", "late_ordovician"]
    },
    "albalimulus_bottoni": {
        "title": "Albalimulus bottoni",
        "description": "Albalimulus was an early horseshoe crab (xiphosuran) from the Tournaisian (Early Carboniferous) Ballagan Formation of Scotland. Representing an early relative of modern limulids, it highlights the ancient ancestry of horseshoe crabs whose lineage dates back to the Ordovician.",
        "tags": [
            "albalimulus", "albalimulus_bottoni", "arthropod", "carboniferous", "chelicerate",
            "early_carboniferous", "horseshoe_crab", "marine", "marine_invertebrate", "paleozoic",
            "scotland", "xiphosura"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "cowielepis_ritchiei": {
        "title": "Cowielepis ritchiei",
        "description": "Cowielepis ritchiei was an unusually deep-bodied, laterally compressed anaspid jawless fish from the Cowie Formation of Stonehaven, Scotland, at the Silurian-Devonian boundary (~419 Ma). A close relative of Birkenia, it navigated inshore waters with specialized overlapping trunk scales and a hypocercal tail.",
        "tags": [
            "anaspida", "birkeniiformes", "chordate", "cowielepis", "cowielepis_ritchiei",
            "devonian", "early_devonian", "early_vertebrate", "fish", "jawless_fish",
            "late_silurian", "marine", "paleozoic", "scotland", "silurian"
        ],
        "keyframes": ["early_devonian", "late_silurian"]
    },
    "sphenonectris_turnerae": {
        "title": "Sphenonectris turnerae",
        "description": "Sphenonectris was a small, fork-tailed thelodont jawless fish from the Delorme Group (Lochkovian / latest Silurian-earliest Devonian) of Canada's Northwest Territories. Belonging to Furcacaudiformes, it was characterized by a deep, pot-bellied profile and an exceptionally tall, symmetrical forked caudal fin for maneuverability.",
        "tags": [
            "canada", "chordate", "delorme_group", "devonian", "early_devonian", "early_vertebrate",
            "fish", "furcacaudiformes", "jawless_fish", "late_silurian", "marine", "paleozoic",
            "silurian", "sphenonectris", "sphenonectris_turnerae", "thelodont"
        ],
        "keyframes": ["early_devonian", "late_silurian"]
    },
    "pezopallichthys_ritchei": {
        "title": "Pezopallichthys ritchei",
        "description": "Pezopallichthys was a diminutive (~4 cm) barrel-shaped thelodont jawless fish from the Wenlock Middle Silurian Road River Formation of Avalanche Lake, Canada. As an early furcacaudiform, its rounded body and large eyes suggest active foraging near the seafloor.",
        "tags": [
            "canada", "chordate", "early_silurian", "early_vertebrate", "fish", "furcacaudiformes",
            "jawless_fish", "marine", "mid_silurian", "paleozoic", "pezopallichthys",
            "pezopallichthys_ritchei", "silurian", "thelodont", "wenlock"
        ],
        "keyframes": ["early_silurian", "mid_silurian"]
    },
    "lanarkia_horrida": {
        "title": "Lanarkia horrida",
        "description": "Lanarkia was a flattened, ray-like thelodont jawless fish from the Silurian of Scotland and Canada. Its entire body was armored in sharp, hollow cone-shaped denticles rather than interlocking plates, giving its skin a prickly shagreen texture.",
        "tags": [
            "benthic", "chordate", "early_vertebrate", "fish", "furcacaudiformes", "jawless_fish",
            "lanarkia", "lanarkia_horrida", "late_silurian", "marine", "mid_silurian",
            "paleozoic", "scotland", "silurian", "thelodont"
        ],
        "keyframes": ["late_silurian", "mid_silurian"]
    },
    "shuyu_zhejiangensis": {
        "title": "Shuyu zhejiangensis",
        "description": "Shuyu ('dawn fish') was an early galeaspid jawless fish from the Silurian of Zhejiang, China. Synchrotron X-ray tomographic scans of its braincase famously revealed paired nasal sacs and the transitional cranial architecture that preceded the origin of jawed vertebrates.",
        "tags": [
            "benthic", "china", "chordate", "early_silurian", "early_vertebrate", "eugaleaspiformes",
            "fish", "galeaspida", "jawless_fish", "marine", "mid_silurian", "paleozoic",
            "shuyu", "shuyu_zhejiangensis", "silurian"
        ],
        "keyframes": ["early_silurian", "mid_silurian"]
    },
    "birkenia_elegans": {
        "title": "Birkenia elegans",
        "description": "Birkenia elegans was a slender, active-swimming anaspid jawless fish up to 10 cm long from the Silurian Lesmahagow inliers of Scotland. Its body was wrapped in diagonal chevron-like scale bands and surmounted by a crest of specialized spine-scales along its dorsal ridge.",
        "tags": [
            "anaspida", "birkenia", "birkenia_elegans", "birkeniidae", "chordate",
            "early_silurian", "early_vertebrate", "fish", "jawless_fish", "marine",
            "mid_silurian", "paleozoic", "scotland", "silurian"
        ],
        "keyframes": ["early_silurian", "mid_silurian"]
    },
    "slimonia_acuminata": {
        "title": "Slimonia acuminata",
        "description": "Reaching lengths of over 1.5 meters, Slimonia was a formidable predatory sea scorpion (eurypterid) from the Late Silurian of Lanarkshire, Scotland. It possessed sharp raptorial pincer appendages and a powerful, serrated telson spine that could flex laterally to strike prey.",
        "tags": [
            "arthropod", "chelicerate", "eurypterid", "late_silurian", "marine", "marine_invertebrate",
            "mid_silurian", "paleozoic", "predator", "scotland", "sea_scorpion", "silurian",
            "slimonia", "slimonia_acuminata"
        ],
        "keyframes": ["late_silurian", "mid_silurian"]
    },
    "sanchaspis_megalorostrata": {
        "title": "Sanchaspis megalorostrata",
        "description": "Sanchaspis was a remarkable galeaspid jawless fish from the early Devonian (Pragian) Xujiachong Formation of Yunnan, China. It is distinguished by an enormous, elongated sword-like rostral process extending forward from its horseshoe-shaped headshield.",
        "tags": [
            "benthic", "china", "chordate", "devonian", "early_devonian", "early_vertebrate",
            "fish", "galeaspida", "huananaspidiformes", "jawless_fish", "late_silurian",
            "marine", "paleozoic", "sanchaspis", "sanchaspis_megalorostrata", "silurian"
        ],
        "keyframes": ["early_devonian", "late_silurian"]
    },
    "loganellia_scotica": {
        "title": "Loganellia scotica",
        "description": "Loganellia was a 15-cm thelodont jawless fish from the Early Silurian Lesmahagow inliers of Scotland. Its body was clothed in tiny microscopic denticles arranged in aerodynamic rows, and it possessed lateral pectoral flap-fins that aided stability while swimming.",
        "tags": [
            "chordate", "early_silurian", "early_vertebrate", "fish", "jawless_fish",
            "loganellia", "loganellia_scotica", "loganiidae", "marine", "mid_silurian",
            "paleozoic", "scotland", "silurian", "thelodont"
        ],
        "keyframes": ["early_silurian", "mid_silurian"]
    },
    "pharyngolepis_oblongus": {
        "title": "Pharyngolepis oblongus",
        "description": "Pharyngolepis was a primitive anaspid jawless fish from the Wenlock Silurian of Ringerike, Norway. Lacking paired pectoral fins, it bore paired rows of lateral ventral spines and rows of gill openings along its flank, foraging along nearshore mud flats.",
        "tags": [
            "anaspida", "benthic", "chordate", "early_vertebrate", "fish", "jawless_fish",
            "late_silurian", "marine", "mid_silurian", "norway", "paleozoic", "pharyngolepis",
            "pharyngolepis_oblongus", "silurian", "wenlock"
        ],
        "keyframes": ["late_silurian", "mid_silurian"]
    },
    "cooksonia_pertoni": {
        "title": "Cooksonia pertoni",
        "description": "Cooksonia is the earliest widely recognized polysporangiophyte vascular land plant, known from the Late Silurian of England and worldwide. Standing just a few centimeters tall, its leafless photosynthetic stems branched dichotomously and ended in trumpet-shaped sporangia.",
        "tags": [
            "cooksonia", "cooksonia_pertoni", "early_land_plant", "embryophyta", "england",
            "land_plant", "late_silurian", "mid_silurian", "paleozoic", "plant", "silurian", "vascular_plant"
        ],
        "keyframes": ["late_silurian", "mid_silurian"]
    },
    "athenaegis_chattertoni": {
        "title": "Athenaegis chattertoni",
        "description": "Measuring just 5 cm long, Athenaegis chattertoni from the Early Silurian (Llandovery) of northern Canada is the earliest known heterostracan. Its forward body was encased in a rigid dorsal and ventral shield with lateral branchial plates, swimming via a symmetrical fan-like tail.",
        "tags": [
            "athenaegis", "athenaegis_chattertoni", "benthic", "canada", "chordate",
            "cyathaspididae", "early_silurian", "early_vertebrate", "fish", "heterostraci",
            "jawless_fish", "llandovery", "marine", "paleozoic", "silurian"
        ],
        "keyframes": ["early_silurian"]
    },
    "jamoytius_kerwoodi": {
        "title": "Jamoytius kerwoodi",
        "description": "Jamoytius kerwoodi was an eel-like stem-cyclostome jawless fish from the Silurian of the Lesmahagow inlier in Scotland. Possessing a terminal round sucking mouth, large lateral eyes, and paired continuous lateral fin folds, it offers key clues to lamprey and anaspid evolution.",
        "tags": [
            "anaspidomorphi", "chordate", "early_silurian", "early_vertebrate", "fish",
            "jamoytius", "jamoytius_kerwoodi", "jawless_fish", "marine", "mid_silurian",
            "paleozoic", "scotland", "silurian", "stem_cyclostome"
        ],
        "keyframes": ["early_silurian", "mid_silurian"]
    },
    "entelognathus_primordialis": {
        "title": "Entelognathus primordialis",
        "description": "Entelognathus was a groundbreaking placoderm fish from the Late Silurian (Ludlow) Kuanti Formation of Yunnan, China. It is the earliest known creature to possess marginal jaw bones (maxilla, premaxilla, and dentary), proving that the facial bones of modern bony fish and tetrapods originated within armored placoderms.",
        "tags": [
            "china", "chordate", "entelognathus", "entelognathus_primordialis", "fish",
            "gnathostome", "jawed_vertebrate", "kuanti_formation", "late_silurian", "ludlow",
            "marine", "paleozoic", "placoderm", "silurian"
        ],
        "keyframes": ["late_silurian"]
    },
    "eurypterus_tetragonophthalmus": {
        "title": "Eurypterus tetragonophthalmus",
        "description": "Eurypterus is the most famous and well-studied genus of sea scorpions (eurypterids), abundant in Silurian shallow seas across Europe and North America. It used flattened paddle-like rear limbs to swim through lagoons and estuaries, capturing small prey with forward walking legs.",
        "tags": [
            "arthropod", "chelicerate", "estonia", "eurypterid", "eurypterus",
            "eurypterus_tetragonophthalmus", "late_silurian", "marine", "marine_invertebrate",
            "mid_silurian", "paleozoic", "predator", "rootsikula", "sea_scorpion", "silurian"
        ],
        "keyframes": ["late_silurian", "mid_silurian"]
    },
    "boreaspis_rostrata": {
        "title": "Boreaspis rostrata",
        "description": "Boreaspis rostrata was a small (~5 cm) osteostracan jawless fish from the Early Devonian Wood Bay Series of Spitsbergen, Svalbard. Its semicircular headshield was armed with a remarkably long, forward-pointing spear-like rostrum and pointed lateral cornual spines.",
        "tags": [
            "benthic", "boreaspis", "boreaspis_rostrata", "cephalaspidiformes", "chordate",
            "devonian", "early_devonian", "early_vertebrate", "fish", "jawless_fish",
            "marine", "osteostraci", "paleozoic", "spitsbergen", "svalbard"
        ],
        "keyframes": ["early_devonian"]
    },
    "dicksonosteus_arcticus": {
        "title": "Dicksonosteus arcticus",
        "description": "Dicksonosteus was a primitive arthrodire placoderm from the Early Devonian Wood Bay Series of Spitsbergen, Norway. Measuring 15 to 20 cm in length, its flattened, heavily armored headshield and forward-facing eyes indicate a benthic lifestyle hunting along the sediment.",
        "tags": [
            "arthrodira", "benthic", "chordate", "devonian", "dicksonosteus",
            "dicksonosteus_arcticus", "early_devonian", "fish", "gnathostome", "jawed_vertebrate",
            "marine", "paleozoic", "placoderm", "predator", "spitsbergen"
        ],
        "keyframes": ["early_devonian"]
    },
    "lepidaspis_serrata": {
        "title": "Lepidaspis serrata",
        "description": "Lepidaspis ('lizard shield') was an enigmatic heterostracan jawless fish from the Early Devonian Delorme Group (MOTH locality) in the Mackenzie Mountains of northern Canada. Unlike solid-shielded heterostracans, its body was uniquely enveloped in a mosaic of tiny scales with serrated edges.",
        "tags": [
            "canada", "chordate", "delorme_group", "devonian", "early_devonian", "early_vertebrate",
            "fish", "heterostraci", "jawless_fish", "lepidaspis", "lepidaspis_serrata",
            "marine", "moth_locality", "paleozoic"
        ],
        "keyframes": ["early_devonian"]
    },
    "podolaspis_lerichei": {
        "title": "Podolaspis lerichei",
        "description": "Podolaspis was a 25-cm pteraspidiform heterostracan jawless fish from the Early Devonian (Lochkovian) Old Red Sandstone of Podolia, Ukraine. It possessed an impressive, near-vertical dorsal spine, wing-like triangular cornual plates on the flanks of its armor, and an elongated rostral snout.",
        "tags": [
            "chordate", "devonian", "early_devonian", "early_vertebrate", "fish",
            "heterostraci", "jawless_fish", "marine", "old_red_sandstone", "paleozoic",
            "podolaspis", "podolaspis_lerichei", "podolia", "pteraspidiformes", "ukraine"
        ],
        "keyframes": ["early_devonian"]
    },
    "superciliaspis_gabrielsei": {
        "title": "Superciliaspis gabrielsei",
        "description": "Superciliaspis ('eyebrow shield') was an 11-cm osteostracan jawless fish from the Early Devonian Delorme Group (MOTH locality) of northwest Canada. It possessed prominent supraorbital ridges ('eyebrows') over its close-set eyes and a horseshoe-shaped cephalic shield with sensory field depressions.",
        "tags": [
            "benthic", "canada", "cephalaspidida", "chordate", "delorme_group", "devonian",
            "early_devonian", "early_vertebrate", "fish", "jawless_fish", "marine",
            "moth_locality", "osteostraci", "paleozoic", "superciliaspis", "superciliaspis_gabrielsei"
        ],
        "keyframes": ["early_devonian"]
    },
    "tinirau_clackae": {
        "title": "Tinirau clackae",
        "description": "Tinirau was a one-meter-long stem-tetrapodomorph (eotetrapodiform) predatory fish from the Middle Devonian (Givetian) Red Hill beds of Nevada, USA. Named in honour of paleontologist Jenny Clack, it exhibits a pivotal transitional mosaic between tristichopterid fish and early limb-bearing tetrapods.",
        "tags": [
            "chordate", "devonian", "early_vertebrate", "eotetrapodiformes", "fish",
            "lobe_finned_fish", "marine", "mid_devonian", "nevada", "paleozoic",
            "predator", "sarcopterygii", "tetrapodomorph", "tinirau", "tinirau_clackae"
        ],
        "keyframes": ["mid_devonian"]
    },
    "pterichthyodes_milleri": {
        "title": "Pterichthyodes milleri",
        "description": "Pterichthyodes was an iconic 25-cm antiarch placoderm from the Middle Devonian (Eifelian) Achanarras Fish Bed of Caithness, Scotland, famously described by Hugh Miller. It possessed peculiar jointed, armored pectoral 'arms' that it used to scuttle along the lakebed and bury itself in sediment.",
        "tags": [
            "achanarras", "antiarchi", "benthic", "chordate", "devonian", "fish",
            "gnathostome", "jawed_vertebrate", "mid_devonian", "paleozoic", "placoderm",
            "pterichthyodes", "pterichthyodes_milleri", "scotland"
        ],
        "keyframes": ["mid_devonian"]
    },
    "glyptolepis_paucidens": {
        "title": "Glyptolepis paucidens",
        "description": "Reaching over 60 cm in length, Glyptolepis paucidens was a large porolepiform lobe-finned fish (sarcopterygian) and apex predator of the Middle Devonian (Eifelian) Achanarras lake ecosystem in Caithness, Scotland. It possessed thick, heavily sculptured rhomboid scales and sharp fangs.",
        "tags": [
            "achanarras", "chordate", "devonian", "fish", "glyptolepis", "glyptolepis_paucidens",
            "lobe_finned_fish", "mid_devonian", "paleozoic", "porolepiformes", "predator",
            "sarcopterygii", "scotland"
        ],
        "keyframes": ["mid_devonian"]
    },
    "titanichthys_clarki": {
        "title": "Titanichthys clarki",
        "description": "Measuring up to 6 meters in length, Titanichthys was a colossal arthrodire placoderm from the Late Devonian Cleveland Shale of Ohio, rivaling Dunkleosteus in size. Unlike its apex predator cousin, Titanichthys possessed toothless, gracile jaws adapted for continuous filter-feeding or suction-feeding on small prey.",
        "tags": [
            "arthrodira", "chordate", "cleveland_shale", "devonian", "filter_feeder",
            "fish", "giant", "gnathostome", "jawed_vertebrate", "late_devonian",
            "late_devonian_extinction", "marine", "ohio", "paleozoic", "placoderm",
            "titanichthys", "titanichthys_clarki"
        ],
        "keyframes": ["late_devonian", "late_devonian_extinction"]
    },
    "turinia_pagei": {
        "title": "Turinia pagei",
        "description": "Turinia pagei was a large (up to 40 cm) thelodont jawless fish from the Early Devonian Old Red Sandstone of Angus, Scotland. Its broad, dorsoventrally flattened body was enveloped in a continuous carpet of tiny diamond-shaped denticle scales, and its scales serve as key global biostratigraphic index fossils.",
        "tags": [
            "benthic", "chordate", "devonian", "early_devonian", "early_vertebrate",
            "fish", "jawless_fish", "marine", "old_red_sandstone", "paleozoic",
            "scotland", "thelodont", "turinia", "turinia_pagei", "turiniidae"
        ],
        "keyframes": ["early_devonian"]
    },
    "cheiracanthus_murchisoni": {
        "title": "Cheiracanthus murchisoni",
        "description": "Cheiracanthus murchisoni was a 10-cm acanthodian ('spiny shark') from the Middle Devonian (Eifelian) Old Red Sandstone of Scotland. It was characterized by a deep, streamlined body, a single prominent dorsal fin supported by a stout spine, and tiny, shiny ganoid-like scales.",
        "tags": [
            "acanthodii", "acanthodiformes", "cheiracanthus", "cheiracanthus_murchisoni", "chordate",
            "devonian", "fish", "gnathostome", "mid_devonian", "old_red_sandstone",
            "paleozoic", "scotland", "spiny_shark"
        ],
        "keyframes": ["mid_devonian"]
    },
    "parexus_recurvus": {
        "title": "Parexus recurvus",
        "description": "Parexus was a 15-cm climatiiform acanthodian ('spiny shark') from the Early Devonian of Tillywhandland, Scotland. It is renowned for its enormously enlarged, curved anterior dorsal spine, which was heavily serrated and almost as tall as the fish itself.",
        "tags": [
            "acanthodii", "climatiiformes", "chordate", "devonian", "early_devonian",
            "fish", "gnathostome", "paleozoic", "parexus", "parexus_recurvus",
            "scotland", "spiny_shark", "tillywhandland"
        ],
        "keyframes": ["early_devonian"]
    },
    "diplacanthus_crassissimus": {
        "title": "Diplacanthus crassissimus",
        "description": "Diplacanthus was a 6 to 8 cm spiny shark (acanthodian) from the Middle Devonian (Eifelian) Old Red Sandstone of Scotland. Characterized by stout, deeply grooved dorsal and paired fin spines and prominent scapulocoracoid armor plates, it was widely distributed across Devonian freshwater and brackish environments.",
        "tags": [
            "acanthodii", "chordate", "devonian", "diplacanthidae", "diplacanthus",
            "diplacanthus_crassissimus", "fish", "gnathostome", "mid_devonian", "old_red_sandstone",
            "paleozoic", "scotland", "spiny_shark"
        ],
        "keyframes": ["mid_devonian"]
    }
}

def derive_classification(meta: dict) -> dict:
    """Generate tags, keyframes, title, id, and description for image-library.json."""
    title = meta["title"]
    title_low = title.lower()

    # Check for curated ecosystem/assemblage profiles
    for eco_key, eco_data in ECOSYSTEM_CATALOG.items():
        if eco_key.replace('_', ' ') in title_low or eco_key in title_low:
            return {
                "id": eco_data["id"],
                "filename": eco_data["filename"],
                "title": eco_data["title"],
                "credit": "Nobu Tamura",
                "license": "CC BY-SA 4.0",
                "description": eco_data["description"],
                "tags": sorted(list(set(eco_data["tags"]))),
                "keyframes": sorted(list(set(eco_data["keyframes"])))
            }

    # Genus and species tokens
    words = [re.sub(r'[^a-zA-Z0-9]', '', w).lower() for w in title.split() if w]
    genus = words[0] if words else "fossil"
    species = words[1] if len(words) > 1 else ""

    curated_lookup = f"{genus}_{species}" if species else genus
    if curated_lookup in CURATED_ENTRIES:
        cur = CURATED_ENTRIES[curated_lookup]
        return {
            "id": f"{curated_lookup}_tamura",
            "filename": f"{curated_lookup}_nobu_tamura.jpg",
            "title": cur["title"],
            "credit": "Nobu Tamura",
            "license": "CC BY-SA 4.0",
            "description": cur["description"],
            "tags": sorted(list(set(cur["tags"]))),
            "keyframes": sorted(list(set(cur["keyframes"])))
        }

    # Unique id
    item_id = f"{genus}_{species}_tamura" if species else f"{genus}_tamura"

    # Filename
    filename = f"{genus}_{species}_nobu_tamura.jpg" if species else f"{genus}_nobu_tamura.jpg"

    combined_text = f"{meta['title']} {meta['systematics']} {meta['horizon']} {meta['description_body']} {meta['raw_text']}".lower()

    # Determine keyframes (check horizon first for accurate formation age)
    keyframes = set()
    horizon_text = meta.get("horizon", "").lower()
    for pattern, kf_list in AGE_KEYFRAME_MAP:
        if re.search(pattern, horizon_text):
            keyframes.update(kf_list)
            break

    # Fallback to combined text if horizon was empty or didn't match
    if not keyframes:
        for pattern, kf_list in AGE_KEYFRAME_MAP:
            if re.search(pattern, combined_text):
                keyframes.update(kf_list)
                break

    if not keyframes:
        keyframes.add("early_cambrian")

    # Determine tags
    tags = set()
    if genus: tags.add(genus)
    if species: tags.add(f"{genus}_{species}")

    # Broad taxonomic categories from systematics
    tax_terms = {
        "trilobita": ["trilobite", "arthropod", "marine_invertebrate"],
        "arthropoda": ["arthropod", "invertebrate"],
        "porifera": ["sponge", "porifera", "marine_invertebrate"],
        "cnidaria": ["cnidarian", "sea_anemone", "marine_invertebrate"],
        "lobopodia": ["lobopod", "panarthropod", "marine_invertebrate"],
        "panarthropoda": ["panarthropod", "invertebrate"],
        "crustacea": ["crustacean", "arthropod", "marine_invertebrate"],
        "ambulacraria": ["ambulacraria", "marine_invertebrate"],
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

    # Specific organisms
    if "haikouella" in combined_text or "myllokunmingia" in combined_text:
        tags.update(["chordate", "early_vertebrate"])
    if "chengjiang" in combined_text or "maotianshan" in combined_text:
        tags.update(["chengjiang", "chengjiang_biota"])
    if "burgess shale" in combined_text:
        tags.add("burgess_shale")

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

def process_url(url: str, existing_sources: set, force: bool = False) -> dict | None:
    """Download image and return entry dict for image-library.json."""
    clean_url = re.sub(r'\?.*$', '', url.strip())
    if clean_url in existing_sources and not force:
        print(f"\n[SKIP] Already imported: {clean_url}")
        return None

    print(f"\nProcessing: {clean_url}")
    page_html = fetch_url(clean_url)
    post_id = get_post_id(page_html)

    if not post_id:
        raise ValueError(f"Could not extract Blogger postId from {clean_url}")

    feed_url = f"https://spinops.blogspot.com/feeds/posts/default/{post_id}?alt=json"
    feed_json = json.loads(fetch_url(feed_url))
    entry = feed_json.get('entry', {})

    meta = extract_metadata(entry, page_html)
    record = derive_classification(meta)
    record["source_url"] = clean_url

    # Check image on disk
    dest_file = IMAGES_DIR / record["filename"]
    if dest_file.exists() and dest_file.stat().st_size > 0:
        print(f"Image already on disk: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
    else:
        img_url = meta.get("image_url")
        if not img_url:
            raise ValueError(f"No image found for {clean_url}")
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
        if not entry:
            continue
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
        print("Usage: python scripts/import_spinops_image.py [--force] <URL1> [URL2 ...]")
        print("   or: python scripts/import_spinops_image.py [--force] --file urls.txt")
        sys.exit(1)

    args = sys.argv[1:]
    force = False
    if "--force" in args:
        force = True
        args.remove("--force")

    raw_urls = []
    if args and args[0] == "--file":
        with open(args[1], "r", encoding="utf-8") as f:
            raw_urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        raw_urls = [arg.strip() for arg in args if arg.strip()]

    # Normalize and deduplicate within batch
    seen = set()
    urls = []
    for u in raw_urls:
        norm = re.sub(r'\?.*$', '', u)
        if norm and norm not in seen:
            seen.add(norm)
            urls.append(norm)

    # Check already imported sources from image-library.json
    existing_sources = set()
    if IMAGE_LIB_PATH.exists() and not force:
        with open(IMAGE_LIB_PATH, "r", encoding="utf-8") as f:
            lib_data = json.load(f)
            for item in lib_data.get("images", []):
                if "source_url" in item:
                    existing_sources.add(item["source_url"])

    new_entries = []
    for u in urls:
        try:
            entry = process_url(u, existing_sources, force=force)
            if entry:
                new_entries.append(entry)
                existing_sources.add(entry["source_url"])
        except Exception as e:
            print(f"Error processing {u}: {e}")

    if new_entries:
        update_image_library(new_entries)
    else:
        print("\nNo new entries to add.")

if __name__ == "__main__":
    main()
