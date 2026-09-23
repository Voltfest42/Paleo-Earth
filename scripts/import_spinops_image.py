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
    },
    "colosteidae": {
        "id": "colosteidae_tamura",
        "filename": "colosteidae_nobu_tamura.jpg",
        "title": "Colosteidae (Early Aquatic Stem-Tetrapods)",
        "description": "A comparative reconstruction of the enigmatic Carboniferous stem-tetrapod family Colosteidae. Featured are the flattened-skulled Colosteus scutellatus from Ohio, the serpentine predator Greererpeton burkemorani from West Virginia, and the basal Pholidogaster pisciformis from Scotland, showcasing their elongated eel-like bodies and secondarily aquatic adaptations.",
        "tags": [
            "amphibian", "aquatic", "carboniferous", "carboniferous_rainforest_collapse",
            "chordate", "colosteidae", "colosteus", "community", "composite",
            "early_carboniferous", "early_tetrapod", "greererpeton", "late_carboniferous",
            "mid_carboniferous", "paleozoic", "pholidogaster", "predator", "stegocephalia"
        ],
        "keyframes": ["carboniferous_rainforest_collapse", "early_carboniferous", "late_carboniferous", "mid_carboniferous"]
    },
    "diadectomorpha": {
        "id": "diadectomorpha_tamura",
        "filename": "diadectomorpha_nobu_tamura.jpg",
        "title": "Diadectomorpha Evolution and Diversity",
        "description": "A comparative phylogenetic overview of Diadectomorpha, the pivotal clade of advanced reptiliomorph tetrapods near the origin of amniotes. Illustrated are the Early Permian taxa Tseajaia campi (Utah), the heavy-bodied herbivore Diadectes sideropelicus (Texas), and the well-studied locomotion models Orobates pabsti and Silvadectes absitus from the Bromacker quarry of Germany.",
        "tags": [
            "carboniferous", "chordate", "community", "composite", "diadectes", "diadectomorpha",
            "early_permian", "herbivore", "land_vertebrate", "orobates", "paleozoic", "permian",
            "reptiliomorpha", "silvadectes", "stem_amniote", "tetrapod", "tseajaia"
        ],
        "keyframes": ["early_permian", "late_carboniferous"]
    },
    "amphibamiformes": {
        "id": "amphibamiformes_tamura",
        "filename": "amphibamiformes_nobu_tamura.jpg",
        "title": "Amphibamiformes (Ancestors of Modern Amphibians)",
        "description": "A comparative evolutionary reconstruction of amphibamiform dissorophoid temnospondyls, the ancestral lineage leading directly to modern frogs, salamanders, and caecilians (Lissamphibia). Featured are the famous 'frogamander' Gerobatrachus hottoni, Doleserpeton annectens, the gilled branchiosaurid Apateon, Branchiosaurus, Leptorophus, and the Triassic survivor Micropholis stowi.",
        "tags": [
            "amphibamiformes", "amphibian", "apateon", "branchiosaurus", "carboniferous", "chordate",
            "community", "composite", "doleserpeton", "early_permian", "early_triassic", "frogamander",
            "gerobatrachus", "lissamphibia", "micropholis", "paleozoic", "permian", "temnospondyli", "triassic"
        ],
        "keyframes": ["early_permian", "early_triassic", "late_carboniferous", "mid_permian"]
    },
    "diplocaulidae": {
        "id": "diplocaulidae_tamura",
        "filename": "diplocaulidae_nobu_tamura.jpg",
        "title": "Diplocaulidae (Boomerang-Headed Amphibians)",
        "description": "A comparative reconstruction of the iconic boomerang-headed lepospondyl amphibians (Diplocaulidae). Featured are Diplocaulus magnicornis from the Early Permian red beds of Texas and its relative Diploceraspis burkei from West Virginia, highlighting their hydrodynamic horned skull 'wings' used for underwater lift and defense against predators.",
        "tags": [
            "amphibian", "aquatic", "boomerang_head", "chordate", "community", "composite",
            "diplocaulidae", "diplocaulus", "diploceraspis", "early_permian", "lepospondyli",
            "nectridea", "paleozoic", "permian", "texas"
        ],
        "keyframes": ["early_permian", "late_carboniferous"]
    },
    "kupferschiefer": {
        "id": "kupferschiefer_vertebrates_tamura",
        "filename": "kupferschiefer_vertebrates_nobu_tamura.jpg",
        "title": "Kupferschiefer Late Permian Vertebrate Fauna",
        "description": "An ecosystem reconstruction of fossil vertebrates from the Late Permian (Wuchiapingian) Kupferschiefer of Germany (Zechstein Basin, ~258 Ma). Featured is the specialized gliding reptile Glaurung schneideri (Weigeltisauridae) alongside ancient ray-finned palaeonisciforms and marine fish that populated the semi-enclosed inland Zechstein Sea.",
        "tags": [
            "actinopterygii", "community", "composite", "ecosystem", "fish", "germany",
            "glaurung", "gliding_reptile", "kupferschiefer", "late_permian", "marine",
            "paleozoic", "permian", "permian_triassic_extinction", "reptile", "weigeltisaurus", "zechstein"
        ],
        "keyframes": ["late_permian", "permian_triassic_extinction"]
    },
    "caseasauria": {
        "id": "caseasauria_tamura",
        "filename": "caseasauria_nobu_tamura.jpg",
        "title": "Caseasauria (Early Synapsid Radiation)",
        "description": "A comparative evolutionary overview of Caseasauria, an ancient basal branch of synapsids spanning the Late Carboniferous through Middle Permian. Features the small, large-canined insectivorous eothyridids alongside the colossal, barrel-bodied herbivorous caseids (such as Cotylorhynchus and Casea) with tiny heads, leaf-shaped teeth, and massive ribcages adapted for fermenting plant matter.",
        "tags": [
            "barrel_bodied", "carboniferous", "casea", "caseasauria", "caseidae", "chordate",
            "community", "composite", "cotylorhynchus", "early_permian", "eothyrididae", "eothyris",
            "herbivore", "land_vertebrate", "mid_permian", "paleozoic", "pelycosaur", "permian", "synapsid"
        ],
        "keyframes": ["early_permian", "late_carboniferous", "mid_permian"]
    },
    "nanlinghu": {
        "id": "nanlinghu_formation_tamura",
        "filename": "nanlinghu_formation_nobu_tamura.jpg",
        "title": "Nanlinghu Formation Marine Reptile Fauna",
        "description": "An ecosystem reconstruction of the Early Triassic (Olenekian, ~248 Ma) marine reptile community from the Nanlinghu Formation of Chaohu, Anhui Province, China. Featured are the suction-feeding ichthyosauromorph Sclerocormus, the short-snouted basal ichthyosaur Chaohusaurus, the seal-like Cartorhynchus, the sauropterygian Majiashanosaurus, the predatory bony fish Saurichthys, coelacanth Chaohuichthys, and the thylacocephalan arthropod Ankitokazocaris.",
        "tags": [
            "anhui", "ankitokazocaris", "cartorhynchus", "chaohu", "chaohuichthys", "chaohusaurus",
            "china", "chordate", "coelacanth", "community", "composite", "early_triassic",
            "ecosystem", "ichthyosaur", "ichthyosauromorpha", "majiashanosaurus", "marine",
            "marine_reptile", "mesozoic", "nanlinghu_formation", "permian_triassic_extinction",
            "saurichthys", "sauropterygia", "sclerocormus", "thylacocephala", "triassic"
        ],
        "keyframes": ["early_triassic", "permian_triassic_extinction"]
    },
    "madygen": {
        "id": "madygen_formation_tamura",
        "filename": "madygen_formation_nobu_tamura.jpg",
        "title": "Madygen Formation Fossil Vertebrates",
        "description": "An ecosystem reconstruction of the Middle to Late Triassic (Ladinian-Carnian) inland lake basin biota from the Madygen Formation of southwestern Kyrgyzstan. Featured are bizarre specialized reptiles including Longisquama insignis with its elongated dorsal appendages, the delta-winged hindlimb glider Sharovipteryx mirabilis, the chameleon-like drepanosaur Kyrgyzsaurus, the armored crocodile-like chroniosuchian Madygenerpeton, the tiny cynodont Madysaurus, and the early stem-salamander Triassurus.",
        "tags": [
            "armored_reptile", "central_asia", "chordate", "chroniosuchian", "community",
            "composite", "cynodont", "drepanosaur", "ecosystem", "gliding_reptile",
            "kyrgyzstan", "kyrgyzsaurus", "lake_basin", "late_triassic", "longisquama",
            "madygen_formation", "madygenerpeton", "madysaurus", "mesozoic", "mid_triassic",
            "reptile", "sharovipteryx", "stem_salamander", "triassic", "triassurus"
        ],
        "keyframes": ["late_triassic", "mid_triassic"]
    },
    "lower_maleri": {
        "id": "lower_maleri_formation_tamura",
        "filename": "lower_maleri_formation_nobu_tamura.jpg",
        "title": "Lower Maleri Formation Fossil Vertebrates",
        "description": "A terrestrial and riverine ecosystem reconstruction of the Late Triassic (Carnian, ~230 Ma) Lower Maleri Formation of the Pranhita-Godavari Basin in India. Illustrated are the apex predatory crocodile-mimic phytosaur Parasuchus hislopi, the large herbivorous traversodontid cynodont Exaeretodon statisticae, the beaked rhynchosaur Hyperodapedon huxleyi, the slender protorosaur Malerisaurus robinsonae, and the basal saurischian dinosaur Alwalkeria maleriensis.",
        "tags": [
            "alwalkeria", "archosaur", "chordate", "community", "composite", "cynodont",
            "dinosaur", "early_dinosaur", "ecosystem", "exaeretodon", "gondwana",
            "hyperodapedon", "india", "land_vertebrate", "late_triassic",
            "lower_maleri_formation", "malerisaurus", "mesozoic", "parasuchus",
            "phytosaur", "reptile", "rhynchosaur", "synapsid", "traversodontidae", "triassic"
        ],
        "keyframes": ["late_triassic"]
    },
    "prida": {
        "id": "prida_formation_tamura",
        "filename": "prida_formation_nobu_tamura.jpg",
        "title": "Prida Formation Middle Triassic Marine Fauna",
        "description": "A Middle Triassic (Anisian, ~245 Ma) open-marine ecosystem reconstruction from the Fossil Hill Member of the Prida Formation in Nevada, USA. Illustrated are the giant nine-meter apex predatory ichthyosaur Cymbospondylus piscosus, the specialized shell-crushing button-toothed marine reptiles Omphalosaurus nevadanus and O. nettarhynchus, the fast-swimming mixosaurid Phalarodon fraasi, and the primitive hybodont shark Acrodus alexandrae.",
        "tags": [
            "acrodus", "apex_predator", "chondrichthyes", "chordate", "community",
            "composite", "cymbospondylus", "durophagous", "ecosystem", "fish",
            "fossil_hill", "hybodont", "ichthyosaur", "ichthyosauria", "marine",
            "marine_reptile", "mesozoic", "mid_triassic", "nevada", "omphalosaurus",
            "phalarodon", "prida_formation", "reptile", "shark", "triassic", "usa"
        ],
        "keyframes": ["mid_triassic"]
    },
    "blue_lias": {
        "id": "blue_lias_formation_tamura",
        "filename": "blue_lias_formation_nobu_tamura.jpg",
        "title": "Blue Lias Formation Marine Fauna",
        "description": "An ecosystem reconstruction of the earliest Jurassic (Hettangian, ~200 Ma) marine community from the Blue Lias Formation of Lyme Regis and Somerset, England. Featured are the large ammonite Psiloceras planorbis, the nautiloid Cenoceras, giant clam Plagiostoma, early ichthyosaurs Protoichthyosaurus and long-snouted Leptonectes, the plesiosaurs Thalassiodracon and Atychodracon, and the early coastal pterosaur Dimorphodon macronyx.",
        "tags": [
            "ammonite", "atychodracon", "blue_lias", "cenoceras", "cephalopod", "chordate",
            "community", "composite", "dimorphodon", "early_jurassic", "ecosystem", "england",
            "ichthyosaur", "jurassic", "jurassic_coast", "leptonectes", "marine", "marine_reptile",
            "mesozoic", "mollusc", "plagiostoma", "plesiosaur", "protoichthyosaurus", "psiloceras",
            "pterosaur", "thalassiodracon", "triassic_jurassic_extinction", "uk"
        ],
        "keyframes": ["early_jurassic", "triassic_jurassic_extinction"]
    },
    "charmouth_mudstone": {
        "id": "charmouth_mudstone_formation_tamura",
        "filename": "charmouth_mudstone_formation_nobu_tamura.jpg",
        "title": "Charmouth Mudstone Formation Vertebrate Fauna",
        "description": "A marine and coastal vertebrate ecosystem reconstruction from the Early Jurassic (Sinemurian-Pliensbachian, ~195 Ma) Charmouth Mudstone Formation of Lyme Regis, Dorset, England. Featured are the iconic long-necked Plesiosaurus dolichodeirus, the rhomaleosaurid Archaeonectrus, Sir David Attenborough's namesake pliosaur Attenborosaurus conybeari, Mary Anning's Ichthyosaurus anningae, the bizarre holocephalan chimaera Myriacanthus paradoxus, and the armored coastal dinosaur Scelidosaurus harrisonii.",
        "tags": [
            "archaeonectrus", "attenborosaurus", "chimaera", "chordate", "community",
            "composite", "dinosaur", "dorset", "early_jurassic", "ecosystem", "england",
            "ichthyosaur", "ichthyosaurus", "jurassic", "jurassic_coast", "marine",
            "marine_reptile", "mesozoic", "myriacanthus", "plesiosaur", "plesiosaurus",
            "reptile", "scelidosaurus", "uk"
        ],
        "keyframes": ["early_jurassic"]
    },
    "2018_in_paleontology": {
        "id": "paleontology_2018_discoveries_tamura",
        "filename": "2018_in_paleontology_nobu_tamura.jpg",
        "title": "2018 in Paleontology: New Species Discoveries",
        "description": "A composite retrospective illustration highlighting eight extraordinary fossil species described in the year 2018. Featured are the piranha-toothed Late Jurassic pycnodont fish Piranhamesodon pinnatomus, the tail-bearing Cretaceous stem-spider Chimerarachne yingi, the Late Triassic desert pterosaur Caelestiventus hanseni, the enantiornithine bird Mirarce eatoni, the toothless stem-baleen whale Maiabalaena nesbittae, the shell-less stem-turtle Eorhynchochelys sinensis, the giant burrowing bat Vulcanops jennyworthyae, and the Ediacaran organism Obamus coronatus.",
        "tags": [
            "caelestiventus", "chimerarachne", "chordate", "community", "composite",
            "discovery", "eorhynchochelys", "fish", "jurassic", "late_jurassic",
            "maiabalaena", "mammal", "mesozoic", "mirarce", "obamus", "piranhamesodon",
            "pterosaur", "retrospective", "spider", "stem_turtle", "vulcanops"
        ],
        "keyframes": ["early_cretaceous", "late_jurassic", "late_triassic"]
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
    },
    "rainerichthys_zangerli": {
        "title": "Rainerichthys zangerli",
        "description": "Rainerichthys zangerli was a small (15 cm) bizarre iniopterygian cartilaginous fish (holocephalan) from the Early Carboniferous (Namurian) Bear Gulch Limestone of Montana. Characterized by enormous, wing-like pectoral fins set high on its back, it may have 'flown' or glided through ancient waters like a modern flying fish.",
        "tags": [
            "bear_gulch", "carboniferous", "cartilaginous_fish", "chondrichthyes", "chordate",
            "early_carboniferous", "fish", "holocephali", "iniopterygiformes", "marine",
            "montana", "paleozoic", "rainerichthys", "rainerichthys_zangerli"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "allenypterus_montanus": {
        "title": "Allenypterus montanus",
        "description": "Allenypterus was a peculiar deep-bodied, hump-backed coelacanth (actinistian) from the Early Carboniferous (Namurian) Bear Gulch Limestone of Montana. Measuring 12 cm long, its tear-drop shape, continuous dorsal-to-tail fin margin, and lack of typical coelacanth lobed fins reflect a specialized reef-dwelling niche.",
        "tags": [
            "actinistia", "allenypterus", "allenypterus_montanus", "bear_gulch", "carboniferous",
            "chordate", "coelacanth", "early_carboniferous", "fish", "lobe_finned_fish",
            "marine", "montana", "paleozoic", "sarcopterygii"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "cervifurca_nasuta": {
        "title": "Cervifurca nasuta",
        "description": "Cervifurca nasuta was a 25-cm iniopterygian holocephalan from the Late Carboniferous (Westphalian D) Excello Shale of Indiana. Like its relative Rainerichthys, it bore huge wing-like dorsal pectoral fins, accompanied by a prominent forked snout horn reminiscent of stag antlers.",
        "tags": [
            "carboniferous", "carboniferous_rainforest_collapse", "cartilaginous_fish", "cervifurca",
            "cervifurca_nasuta", "chondrichthyes", "chordate", "excello_shale", "fish",
            "holocephali", "indiana", "iniopterygiformes", "late_carboniferous", "marine", "paleozoic"
        ],
        "keyframes": ["carboniferous_rainforest_collapse", "late_carboniferous"]
    },
    "megalichthys_hibberti": {
        "title": "Megalichthys hibberti",
        "description": "Reaching over 1.5 meters in length, Megalichthys hibberti was a colossal predatory megalichthyid lobe-finned fish (tetrapodomorph) from the Early Carboniferous (Visean) Coal Measures of Yorkshire, England. Its cylindrical body was armored in shiny cosmine-coated rhomboid scales, and its powerful jaws were studded with dagger-like fangs.",
        "tags": [
            "carboniferous", "coal_measures", "early_carboniferous", "england", "fish",
            "lobe_finned_fish", "megalichthyidae", "megalichthys", "megalichthys_hibberti",
            "mid_carboniferous", "paleozoic", "predator", "sarcopterygii", "tetrapodomorpha"
        ],
        "keyframes": ["early_carboniferous", "mid_carboniferous"]
    },
    "whatcheeria_deltae": {
        "title": "Whatcheeria deltae",
        "description": "Whatcheeria was a 2-meter apex predatory early stem-tetrapod from the Early Carboniferous (Visean-Serpukhovian) of Keokuk County, Iowa. Equipped with robust limbs, a heavy skull, and formidable dagger teeth, Whatcheeria demonstrates that early tetrapods evolved large body size and terrestrial-capable limbs far earlier than once thought.",
        "tags": [
            "amphibian", "carboniferous", "chordate", "early_carboniferous", "early_tetrapod",
            "iowa", "paleozoic", "predator", "tetrapodomorpha", "whatcheeria",
            "whatcheeria_deltae", "whatcheeridae"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "tanyrhinichthys_mcallisteri": {
        "title": "Tanyrhinichthys mcallisteri",
        "description": "Tanyrhinichthys was a 15-cm ray-finned fish (actinopterygian) from the Upper Pennsylvanian (Missourian) Atrasado Formation of New Mexico. It evolved an elongated, sensory-pitted rostrum and ventral mouth convergent with modern sturgeons, allowing it to forage along bottom sediments for hidden invertebrates.",
        "tags": [
            "actinopterygii", "benthic", "carboniferous", "carboniferous_rainforest_collapse",
            "chordate", "fish", "late_carboniferous", "new_mexico", "paleozoic",
            "pennsylvanian", "ray_finned_fish", "tanyrhinichthys", "tanyrhinichthys_mcallisteri"
        ],
        "keyframes": ["carboniferous_rainforest_collapse", "late_carboniferous"]
    },
    "chimerarachne_yingi": {
        "title": "Chimerarachne yingi",
        "description": "Chimerarachne yingi is an extraordinary stem-spider preserved in Mid-Cretaceous (~100 Ma) Burmese amber from Myanmar. Measuring just a few millimeters long, it combined true spider traits (chelicerae, pedipalps, and spinnerets) with an ancient, jointed whip-like tail (telson) inherited from Paleozoic arachnid ancestors.",
        "tags": [
            "arachnid", "arthropod", "burmese_amber", "chelicerate", "chimerarachne",
            "chimerarachne_yingi", "cretaceous", "early_cretaceous", "invertebrate",
            "mesozoic", "mid_cretaceous", "myanmar", "spider", "stem_spider"
        ],
        "keyframes": ["early_cretaceous", "mid_cretaceous"]
    },
    "morganucodon_watsoni": {
        "title": "Morganucodon watsoni",
        "description": "Morganucodon was a tiny (10 cm) shrew-like early mammaliaform from the latest Triassic to Early Jurassic (Hettangian), discovered in fissure fills of Glamorgan, Wales. Possessing a transitional double jaw joint, differentiated teeth, and an enlarged brain, it stands as one of the pivotal transitional fossils in mammal evolution.",
        "tags": [
            "chordate", "cynodont", "early_jurassic", "early_mammal", "jurassic",
            "land_vertebrate", "late_triassic", "mammal", "mammaliaformes", "mesozoic",
            "morganucodon", "morganucodon_watsoni", "synapsid", "triassic", "triassic_jurassic_extinction", "wales"
        ],
        "keyframes": ["early_jurassic", "late_triassic", "triassic_jurassic_extinction"]
    },
    "limnoscelis_paludis": {
        "title": "Limnoscelis paludis",
        "description": "Limnoscelis was a heavy-set, 1.5-meter predatory reptiliomorph (diadectomorph) from the Late Carboniferous (Gzhelian) Lower Cutler Formation of New Mexico. With strong sprawling limbs, conical teeth, and prominent maxillary fangs, it was an ambush predator hunting near swamp waters.",
        "tags": [
            "carboniferous", "carboniferous_rainforest_collapse", "diadectomorpha", "land_vertebrate",
            "late_carboniferous", "limnoscelis", "limnoscelis_paludis", "new_mexico", "paleozoic",
            "predator", "reptiliomorpha", "stem_amniote", "tetrapod"
        ],
        "keyframes": ["carboniferous_rainforest_collapse", "late_carboniferous"]
    },
    "edaphosaurus_pogonias": {
        "title": "Edaphosaurus pogonias",
        "description": "Edaphosaurus was a 3.2-meter sail-backed herbivorous synapsid from the Late Carboniferous to Early Permian (Kungurian) of Texas. Supported by tall vertebral spines bearing cross-bars, its distinctive dorsal sail aided thermoregulation while its deep palate and peg-like teeth ground tough plant matter.",
        "tags": [
            "carboniferous", "carboniferous_rainforest_collapse", "chordate", "early_permian",
            "edaphosauridae", "edaphosaurus", "edaphosaurus_pogonias", "herbivore", "land_vertebrate",
            "late_carboniferous", "paleozoic", "pelycosaur", "sail_backed", "synapsid", "texas"
        ],
        "keyframes": ["carboniferous_rainforest_collapse", "early_permian", "late_carboniferous"]
    },
    "tristychius_arcuatus": {
        "title": "Tristychius arcuatus",
        "description": "Tristychius was a 60-cm primitive hybodont-like shark from the Early Carboniferous (Visean) East Kirkton Limestone of Scotland. Resembling modern dogfish, it bore stout, recurved spines at the front of both dorsal fins and inhabited nearshore brackish lagoons.",
        "tags": [
            "carboniferous", "cartilaginous_fish", "chondrichthyes", "chordate", "early_carboniferous",
            "east_kirkton", "elasmobranchii", "fish", "hybodontiformes", "paleozoic",
            "scotland", "shark", "tristychius", "tristychius_arcuatus"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "squatinactis_caudispinatus": {
        "title": "Squatinactis caudispinatus",
        "description": "Squatinactis was a one-meter-long, ray-like elasmobranch from the Early Carboniferous (Serpukhovian) Bear Gulch Limestone of Montana. With broadly expanded wing-like pectoral fins, a dorsoventrally flattened body, and a whip-like tail bearing a spine, it represents an astonishing Paleozoic convergence with modern rays.",
        "tags": [
            "bear_gulch", "benthic", "carboniferous", "cartilaginous_fish", "chondrichthyes",
            "chordate", "early_carboniferous", "elasmobranchii", "fish", "marine",
            "montana", "paleozoic", "ray", "squatinactis", "squatinactis_caudispinatus", "squatinactiformes"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "akmonistion_zangerli": {
        "title": "Akmonistion zangerli",
        "description": "Akmonistion was a 50-cm stethacanthid holocephalan from the Early Carboniferous (Visean) Manse Burn Formation of Scotland. Male specimens are famed for their bizarre, anvil-shaped dorsal spine-brush complex and cranial thorn spine patch, used in courtship display or defense.",
        "tags": [
            "akmonistion", "akmonistion_zangerli", "carboniferous", "cartilaginous_fish", "chondrichthyes",
            "chordate", "early_carboniferous", "fish", "holocephali", "marine",
            "paleozoic", "predator", "scotland", "shark", "stethacanthidae", "symmoriida"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "eucritta_melanolimnetes": {
        "title": "Eucritta melanolimnetes",
        "description": "Named the 'creature from the black lagoon', Eucritta melanolimnetes was a 25-cm stem-tetrapod (baphetid) from the Early Carboniferous (Visean) East Kirkton quarry of Scotland. It possessed characteristic keyhole-shaped eye orbits and a mosaic of cranial features bridging anthracosaurs, temnospondyls, and baphetids.",
        "tags": [
            "amphibian", "baphetidae", "baphetoidea", "carboniferous", "chordate",
            "early_carboniferous", "early_tetrapod", "east_kirkton", "eucritta", "eucritta_melanolimnetes",
            "paleozoic", "scotland", "tetrapod"
        ],
        "keyframes": ["early_carboniferous"]
    },
    "arthropleura_armata": {
        "title": "Arthropleura armata",
        "description": "Reaching lengths of over 2.5 meters, Arthropleura was the largest land invertebrate of all time, roaming the dense equatorial coal swamps of the Carboniferous. Armored in dozens of overlapping tergite plates, this colossal millipede relative fed on lycopod spores and decaying forest vegetation in the oxygen-rich atmosphere.",
        "tags": [
            "arthropleura", "arthropleura_armata", "arthropod", "carboniferous", "carboniferous_rainforest_collapse",
            "coal_swamp", "germany", "giant", "herbivore", "invertebrate",
            "late_carboniferous", "mid_carboniferous", "millipede", "myriapod", "paleozoic", "rainforest"
        ],
        "keyframes": ["carboniferous_rainforest_collapse", "late_carboniferous", "mid_carboniferous"]
    },
    "archaeothyris_florensis": {
        "title": "Archaeothyris florensis",
        "description": "Archaeothyris florensis was a 50-cm ophiacodontid from the Late Carboniferous (Moscovian / Westphalian C) Morien Group of Joggins, Nova Scotia. It is celebrated as the oldest undisputed synapsid known, marking the evolutionary split of the mammal lineage from reptiles.",
        "tags": [
            "archaeothyris", "archaeothyris_florensis", "canada", "carboniferous", "carboniferous_rainforest_collapse",
            "chordate", "joggins", "land_vertebrate", "late_carboniferous", "nova_scotia",
            "ophiacodontidae", "paleozoic", "pelycosaur", "stem_mammal", "synapsid", "tetrapod"
        ],
        "keyframes": ["carboniferous_rainforest_collapse", "late_carboniferous"]
    },
    "proburnetia_viatkensis": {
        "title": "Proburnetia viatkensis",
        "description": "Proburnetia was a 1.5-meter carnivorous biarmosuchian therapsid from the Late Permian (Severodvinian) of Vologda, Russia. Its skull was ornamented with bizarre bulbous bony horns and ridges above its eyes, snout, and occiput, likely used for species recognition and head-butting.",
        "tags": [
            "biarmosuchia", "burnetiamorpha", "chordate", "land_vertebrate", "late_permian",
            "paleozoic", "permian", "predator", "proburnetia", "proburnetia_viatkensis",
            "russia", "synapsid", "therapsid"
        ],
        "keyframes": ["late_permian"]
    },
    "lemurosaurus_pricei": {
        "title": "Lemurosaurus pricei",
        "description": "Lemurosaurus ('lemur lizard') was a small, one-meter basal burnetiamorph biarmosuchian therapsid from the Late Permian (Wuchiapingian) Cistecephalus zone of South Africa's Karoo Basin. Possessing large orbits and modest cranial bosses, it was an agile predator.",
        "tags": [
            "biarmosuchia", "burnetiamorpha", "chordate", "karoo", "land_vertebrate",
            "late_permian", "lemurosaurus", "lemurosaurus_pricei", "paleozoic", "permian",
            "predator", "south_africa", "synapsid", "therapsid"
        ],
        "keyframes": ["late_permian"]
    },
    "tapinocaninus_pamelae": {
        "title": "Tapinocaninus pamelae",
        "description": "Reaching up to 3 meters in length and over a ton in weight, Tapinocaninus was one of the earliest and most massive tapinocephalian dinocephalian therapsids from the Middle Permian (Wordian) of South Africa. As a bulky herbivore, its robust skeleton supported a massive gut for processing tough vegetation.",
        "tags": [
            "chordate", "dinocephalia", "giant", "herbivore", "karoo", "land_vertebrate",
            "mid_permian", "paleozoic", "permian", "south_africa", "synapsid",
            "tapinocaninus", "tapinocaninus_pamelae", "tapinocephalidae", "therapsid"
        ],
        "keyframes": ["mid_permian"]
    },
    "cacops_aspidephorus": {
        "title": "Cacops aspidephorus",
        "description": "Cacops was a 40-cm armored dissorophid temnospondyl amphibian from the Early Permian (Kungurian) Clear Fork Group of Texas. Highly adapted for terrestrial life, it possessed strong walking limbs, an ear drum (tympanum) housed in large otic notches for hearing airborne sound, and a defensive armor row of osteoderms down its spine.",
        "tags": [
            "amphibian", "cacops", "cacops_aspidephorus", "chordate", "clear_fork",
            "dissorophidae", "early_permian", "early_tetrapod", "land_vertebrate", "paleozoic",
            "permian", "predator", "temnospondyli", "texas"
        ],
        "keyframes": ["early_permian"]
    },
    "archegosaurus_decheni": {
        "title": "Archegosaurus decheni",
        "description": "Archegosaurus was a 1.5-meter crocodile-like aquatic temnospondyl amphibian from the Early Permian (Asselian) Lower Rotliegend of Germany. With an elongated, slender snout lined with sharp conical teeth convergent with modern gharials, it was an agile fish-eating predator of ancient lakes and rivers.",
        "tags": [
            "amphibian", "aquatic", "archegosauridae", "archegosauroidea", "archegosaurus",
            "archegosaurus_decheni", "chordate", "early_permian", "germany", "paleozoic",
            "permian", "predator", "rotliegend", "temnospondyli"
        ],
        "keyframes": ["early_permian"]
    },
    "trimerorhachis_insignis": {
        "title": "Trimerorhachis insignis",
        "description": "Trimerorhachis was a flattened, one-meter-long dvinosaurian temnospondyl amphibian from the Early Permian (Artinskian) Wichita Group of Texas. Entirely aquatic, it retained bushy external gills and a sensory lateral-line system into adulthood, lurking on murky lake bottoms much like modern giant salamanders.",
        "tags": [
            "amphibian", "aquatic", "chordate", "dvinosauria", "early_permian",
            "paleozoic", "permian", "temnospondyli", "texas", "trimerorhachidae",
            "trimerorhachis", "trimerorhachis_insignis"
        ],
        "keyframes": ["early_permian"]
    },
    "abdalodon_diastematicus": {
        "title": "Abdalodon diastematicus",
        "description": "Abdalodon was a small (~30 cm) basal charassognathid cynodont from the Late Permian (Wuchiapingian) Tropidostoma zone of South Africa's Beaufort Group. Closely related to Charassognathus, it represents one of the earliest stages in the evolutionary emergence of cynodonts and the mammal stem.",
        "tags": [
            "abdalodon", "abdalodon_diastematicus", "charassognathidae", "chordate", "cynodontia",
            "karoo", "land_vertebrate", "late_permian", "paleozoic", "permian",
            "south_africa", "stem_mammal", "synapsid", "therapsid"
        ],
        "keyframes": ["late_permian"]
    },
    "dvinia_prima": {
        "title": "Dvinia prima",
        "description": "Dvinia prima was a 50-cm basal cynodont from the Late Permian (Wuchiapingian) of northern Russia (Salarevo Formation). It possessed complex multicusped cheek teeth and an expanded zygomatic arch for powerful chewing muscles, representing an omnivorous pioneer among pre-mammalian therapsids.",
        "tags": [
            "chordate", "cynodontia", "dvinia", "dvinia_prima", "dviniidae",
            "land_vertebrate", "late_permian", "omnivore", "paleozoic", "permian",
            "russia", "stem_mammal", "synapsid", "therapsid"
        ],
        "keyframes": ["late_permian"]
    },
    "procynosuchus_delaharpeae": {
        "title": "Procynosuchus delaharpeae",
        "description": "Procynosuchus was a 60-cm semi-aquatic cynodont from the Late Permian (Wuchiapingian) of South Africa and Germany. Equipped with flattened paddle-like feet, a flexible spine, and sharp teeth, it was an agile swimmer hunting fish in rivers and lakes, functioning ecologically much like a modern otter.",
        "tags": [
            "chordate", "cynodontia", "karoo", "late_permian", "paleozoic",
            "permian", "predator", "procynosuchidae", "procynosuchus", "procynosuchus_delaharpeae",
            "semi_aquatic", "south_africa", "stem_mammal", "synapsid", "therapsid"
        ],
        "keyframes": ["late_permian"]
    },
    "eunotosaurus_africanus": {
        "title": "Eunotosaurus africanus",
        "description": "Eunotosaurus was a 30-cm pivotal stem-turtle (pantestudine) from the Middle Permian (Capitanian) Karoo Basin of South Africa. It possessed broad, T-shaped ribs that widened and overlapped to form a rigid proto-shell, adapted primarily for powerful burrowing before being co-opted as defensive turtle armor.",
        "tags": [
            "chordate", "eunotosaurus", "eunotosaurus_africanus", "fossorial", "karoo",
            "land_vertebrate", "mid_permian", "paleozoic", "pantestudines", "permian",
            "reptile", "south_africa", "stem_turtle"
        ],
        "keyframes": ["late_permian", "mid_permian"]
    },
    "bolosaurus_striatus": {
        "title": "Bolosaurus striatus",
        "description": "Bolosaurus striatus was a small (15 cm) parareptile from the Early Permian (Artinskian) Wichita Group of Texas. Possessing bulbous, cusped grinding teeth set in deep jaws, Bolosaurus was among the earliest known reptiles to evolve an herbivorous diet.",
        "tags": [
            "bolosauridae", "bolosaurus", "bolosaurus_striatus", "chordate", "early_permian",
            "herbivore", "land_vertebrate", "paleozoic", "parareptilia", "permian",
            "procolophonomorpha", "reptile", "texas"
        ],
        "keyframes": ["early_permian"]
    },
    "moschops_capensis": {
        "title": "Moschops capensis",
        "description": "Moschops was a massive, 2.5- to 3-meter tapinocephalid dinocephalian therapsid weighing over a ton, roaming the Middle to Late Permian (Capitanian) Karoo of South Africa. Its heavy skull featured dense, thickened bone (pachyostosis) up to 10 cm thick, adapted for head-butting contests for social dominance.",
        "tags": [
            "chordate", "dinocephalia", "giant", "head_butting", "herbivore",
            "karoo", "land_vertebrate", "late_permian", "mid_permian", "moschops",
            "moschops_capensis", "paleozoic", "permian", "south_africa", "synapsid",
            "tapinocephalidae", "therapsid"
        ],
        "keyframes": ["late_permian", "mid_permian"]
    },
    "charassognathus_gracilis": {
        "title": "Charassognathus gracilis",
        "description": "Charassognathus ('notched jaw') was a slender, 50-cm predatory cynodont from the Late Permian (Wuchiapingian) Teekloof Formation of South Africa. As one of the earliest and most basal cynodonts known, it provides a crucial snapshot of the early anatomical innovations on the road to mammals.",
        "tags": [
            "charassognathidae", "charassognathus", "charassognathus_gracilis", "chordate", "cynodontia",
            "karoo", "land_vertebrate", "late_permian", "paleozoic", "permian",
            "predator", "south_africa", "stem_mammal", "synapsid", "therapsid"
        ],
        "keyframes": ["late_permian"]
    },
    "haplophrentis_carinatus": {
        "title": "Haplophrentis carinatus",
        "description": "Haplophrentis was a small (2.5 cm) conical-shelled hyolith from the Middle Cambrian Burgess Shale of British Columbia. Exceptional soft-tissue fossils revealed a horseshoe-shaped tentacled lophophore, a pair of curved stabilizer spines (helens), and an opercular lid, confirming hyoliths as stem-lophophorates related to brachiopods.",
        "tags": [
            "benthic", "burgess_shale", "cambrian", "canada", "haplophrentis",
            "haplophrentis_carinatus", "hyolith", "hyolitha", "invertebrate", "lophophorata",
            "marine", "marine_invertebrate", "mid_cambrian", "paleozoic"
        ],
        "keyframes": ["mid_cambrian"]
    },
    "eotitanosuchus_olsoni": {
        "title": "Eotitanosuchus olsoni",
        "description": "Measuring over 2.5 meters in length, Eotitanosuchus was the apex predatory therapsid of the Middle to Late Permian Ezhovo fauna in Perm, Russia. Bearing huge saber-like canine teeth and a massive deep skull, this formidable biarmosuchian preyed on large dinocephalians and anapsids.",
        "tags": [
            "apex_predator", "biarmosuchia", "carnivore", "chordate", "eotitanosuchidae",
            "eotitanosuchus", "eotitanosuchus_olsoni", "land_vertebrate", "late_permian", "mid_permian",
            "paleozoic", "permian", "predator", "russia", "synapsid", "therapsid"
        ],
        "keyframes": ["late_permian", "mid_permian"]
    },
    "dimetrodon_gigashomegenes": {
        "title": "Dimetrodon gigas",
        "description": "Dimetrodon was an iconic 3.3-meter sail-backed predatory synapsid from the Early Permian (Kungurian) Clear Fork Group of Texas. Re-examination of well-preserved neural spines reveals that the skin webbing of its dorsal sail may have ended below the tips, leaving bare bone spines protruding above the sail.",
        "tags": [
            "apex_predator", "carnivore", "chordate", "clear_fork", "dimetrodon",
            "dimetrodon_gigas", "early_permian", "land_vertebrate", "paleozoic", "pelycosaur",
            "permian", "predator", "sail_backed", "sphenacodontidae", "synapsid", "texas"
        ],
        "keyframes": ["early_permian"]
    },
    "sclerocormus_parviceps": {
        "title": "Sclerocormus parviceps",
        "description": "Sclerocormus was a 1.6-meter basal ichthyosauromorph from the Early Triassic (Olenekian) Nanlinghu Formation of Chaohu, Anhui, China. Featuring a heavily built, toothless snout, a stocky body, and a disproportionately long whip-like tail, it was an early suction-feeder evolving rapidly in the aftermath of the Permian-Triassic extinction.",
        "tags": [
            "china", "chordate", "early_triassic", "ichthyosaur", "ichthyosauromorpha",
            "marine", "marine_reptile", "mesozoic", "nasorostra", "permian_triassic_extinction",
            "sclerocormus", "sclerocormus_parviceps", "triassic"
        ],
        "keyframes": ["early_triassic", "permian_triassic_extinction"]
    },
    "ankitokazocaris_chaohuensis": {
        "title": "Ankitokazocaris chaohuensis",
        "description": "Ankitokazocaris was a 6-cm thylacocephalan arthropod from the Early Triassic (Olenekian) Nanlinghu Formation of Chaohu, China. Characterized by a bivalved carapace enclosing the body, huge compound eyes, and three pairs of raptorial limbs, it was an agile predator in recovering post-Permian marine ecosystems.",
        "tags": [
            "ankitokazocaris", "ankitokazocaris_chaohuensis", "arthropod", "china", "early_triassic",
            "invertebrate", "marine", "marine_invertebrate", "mesozoic", "nanlinghu_formation",
            "raptorial", "thylacocephala", "triassic"
        ],
        "keyframes": ["early_triassic"]
    },
    "protoichthyosaurus_prostaxalis": {
        "title": "Protoichthyosaurus prostaxalis",
        "description": "Protoichthyosaurus was a 3.5-meter early ichthyosaur from the Early Jurassic (Hettangian) Blue Lias Formation of England. Resurrected as a distinct genus based on unique forefin osteology, it represents the rapid post-Triassic-extinction adaptive radiation of parvipelvian marine reptiles.",
        "tags": [
            "blue_lias", "chordate", "early_jurassic", "england", "ichthyosaur",
            "ichthyosauria", "marine", "marine_reptile", "mesozoic", "protoichthyosaurus",
            "protoichthyosaurus_prostaxalis", "reptile", "triassic_jurassic_extinction", "uk"
        ],
        "keyframes": ["early_jurassic", "triassic_jurassic_extinction"]
    },
    "psephochelys_polyosteoderma": {
        "title": "Psephochelys polyosteoderma",
        "description": "Psephochelys was a 2.5-meter armored marine placodont from the Late Triassic (Carnian) Xiaowa Formation of Guizhou, China. Possessing a turtle-like carapace composed of fused polygonal osteoderms and massive, flattened crushing tooth plates, it fed primarily on thick-shelled benthic mollusks.",
        "tags": [
            "armored", "china", "chordate", "durophagous", "guizhou", "late_triassic",
            "marine", "marine_reptile", "mesozoic", "placodont", "placodontia",
            "psephochelys", "psephochelys_polyosteoderma", "reptile", "sauropterygia",
            "triassic", "xiaowa_formation"
        ],
        "keyframes": ["late_triassic"]
    },
    "paludidraco_multidentatus": {
        "title": "Paludidraco multidentatus",
        "description": "Paludidraco ('marsh dragon') was a 2.5-meter simosaurid nothosaur from the Late Triassic (Carnian-Norian boundary) of Guadalajara, Spain. Equipped with comb-like rows of hundreds of tiny interlocking teeth and heavily pachyostotic ribs for neutral buoyancy, it likely specialized in filter-feeding small invertebrates.",
        "tags": [
            "chordate", "filter_feeder", "keuper", "late_triassic", "marine", "marine_reptile",
            "mesozoic", "nothosaur", "pachyostosis", "paludidraco", "paludidraco_multidentatus",
            "reptile", "sauropterygia", "simosauridae", "spain", "triassic"
        ],
        "keyframes": ["late_triassic"]
    },
    "eretmorhipis_carrolldongi": {
        "title": "Eretmorhipis carrolldongi",
        "description": "Eretmorhipis was an 80-cm hupehsuchian marine reptile from the Early Triassic Jialingjiang Formation of Hubei, China. Possessing an oddly tiny platypus-like head with reduced eyes, thick dermal ossicles along its spine, and large fan-like paddle limbs, it used tactile senses to probe muddy seafloors for prey.",
        "tags": [
            "armored", "china", "chordate", "early_triassic", "eretmorhipis",
            "eretmorhipis_carrolldongi", "hupehsuchia", "ichthyosauromorpha", "marine",
            "marine_reptile", "mesozoic", "paddle_limbs", "permian_triassic_extinction",
            "reptile", "tactile_feeder", "triassic"
        ],
        "keyframes": ["early_triassic", "permian_triassic_extinction"]
    },
    "tanytrachelos_ahynis": {
        "title": "Tanytrachelos ahynis",
        "description": "Tanytrachelos was a 20-cm long-necked tanystropheid archosauromorph from the Late Triassic (Norian) Cow Branch Formation of North Carolina and Virginia. Abundantly preserved along lake deposits, this agile quadruped scurried along freshwater margins and produced distinctive fossil trackways.",
        "tags": [
            "archosauromorpha", "chordate", "cow_branch", "lake_fauna", "land_vertebrate",
            "late_triassic", "mesozoic", "north_america", "reptile", "tanystropheidae",
            "tanytrachelos", "tanytrachelos_ahynis", "triassic", "usa"
        ],
        "keyframes": ["late_triassic"]
    },
    "fodonyx_spenceri": {
        "title": "Fodonyx spenceri",
        "description": "Fodonyx ('digging claw') was a 50-cm rhynchosaur from the Middle Triassic (Anisian) Otter Sandstone Formation of Devon, England. Characterized by a downcurved parrot-like beak, complex tooth-grinding plates, and robust digging claws, it grubbed for roots and tubers in semi-arid river floodplains.",
        "tags": [
            "archosauromorpha", "beaked", "chordate", "england", "fodonyx", "fodonyx_spenceri",
            "herbivore", "land_vertebrate", "mesozoic", "mid_triassic", "otter_sandstone",
            "reptile", "rhynchosaur", "rhynchosauria", "triassic", "uk"
        ],
        "keyframes": ["mid_triassic"]
    },
    "teraterpeton_hrynewichorum": {
        "title": "Teraterpeton hrynewichorum",
        "description": "Teraterpeton ('wonderful creeping creature') was a 1.2-meter allokotosaurian archosauromorph from the Late Triassic (Carnian) Wolfville Formation of Nova Scotia, Canada. It possessed a bizarre, elongated toothless beak, upwardly projecting brow ridges, and retracted nostrils adapted for a specialized herbivorous diet.",
        "tags": [
            "allokotosauria", "archosauromorpha", "canada", "chordate", "land_vertebrate",
            "late_triassic", "mesozoic", "nova_scotia", "reptile", "teraterpeton",
            "teraterpeton_hrynewichorum", "trilophosauria", "triassic", "wolfville_formation"
        ],
        "keyframes": ["late_triassic"]
    },
    "bauria_cynops": {
        "title": "Bauria cynops",
        "description": "Bauria was a 60-cm therocephalian therapsid from the Middle Triassic (Anisian) Burgersdorp Formation of South Africa. As one of the latest-surviving therocephalians, it exhibited mammal-like adaptations including a secondary palate and multicusped cheek teeth suited for masticating plant and animal matter.",
        "tags": [
            "beaufort_group", "chordate", "karoo", "land_vertebrate", "mammal_like_reptile",
            "mesozoic", "mid_triassic", "omnivore", "south_africa", "stem_mammal",
            "synapsid", "therapsid", "therocephalia", "triassic"
        ],
        "keyframes": ["mid_triassic"]
    },
    "bergamodactylus_wildi": {
        "title": "Bergamodactylus wildi",
        "description": "Bergamodactylus was a diminutive early pterosaur with a wingspan of only 50 centimeters from the Late Triassic (Norian) Zorzino Limestone Formation of northern Italy. Possessing multicusped teeth and agile wings, it flitted along the subtropical Tethyan archipelago snatching insects and small fish.",
        "tags": [
            "bergamodactylus", "bergamodactylus_wildi", "campylognathoididae", "chordate",
            "flying_reptile", "italy", "late_triassic", "mesozoic", "pterosaur",
            "pterosauria", "reptile", "triassic", "zorzino_limestone"
        ],
        "keyframes": ["late_triassic"]
    },
    "psephoderma_alpinum": {
        "title": "Psephoderma alpinum",
        "description": "Psephoderma was a 1.8-meter placodont from the latest Triassic (Rhaetian) of Alpine Europe and England. Exhibiting a bipartite armored carapace covering its back and hips, a narrow toothless rostrum, and broad crushing pavement teeth, it survived up to the Triassic-Jurassic boundary extinction.",
        "tags": [
            "armored", "chordate", "durophagous", "germany", "koessen_formation",
            "late_triassic", "marine", "marine_reptile", "mesozoic", "placodont",
            "placodontia", "psephoderma", "psephoderma_alpinum", "reptile",
            "sauropterygia", "triassic", "triassic_jurassic_extinction"
        ],
        "keyframes": ["late_triassic", "triassic_jurassic_extinction"]
    },
    "mystriosuchus_planirostris": {
        "title": "Mystriosuchus planirostris",
        "description": "Mystriosuchus was a 4-meter, slender-snouted phytosaur from the Late Triassic (Norian) Löwenstein Formation of Germany. Convergent on modern gharials with its elongated jaws and upward-directed nostrils positioned near the eyes, it was among the most thoroughly aquatic archosaurs of the Triassic.",
        "tags": [
            "archosauriform", "carnivore", "chordate", "germany", "gharial_snout",
            "late_triassic", "loewenstein_formation", "mesozoic", "mystriosuchus",
            "mystriosuchus_planirostris", "phytosaur", "phytosauria", "piscivore",
            "reptile", "semi_aquatic", "triassic"
        ],
        "keyframes": ["late_triassic"]
    },
    "riojasaurus_incertus": {
        "title": "Riojasaurus incertus",
        "description": "Riojasaurus was a massive 4- to 6-meter early sauropodomorph dinosaur from the Late Triassic (Norian) Los Colorados Formation of Argentina. Possessing dense limb bones and a small skull with serrated leaf-shaped teeth, it was among the largest terrestrial herbivores of the Triassic.",
        "tags": [
            "argentina", "chordate", "dinosaur", "dinosauria", "early_dinosaur",
            "herbivore", "land_vertebrate", "late_triassic", "los_colorados", "mesozoic",
            "reptile", "riojasauridae", "riojasaurus", "riojasaurus_incertus",
            "saurischia", "sauropodomorph", "triassic"
        ],
        "keyframes": ["late_triassic"]
    },
    "phalarodon_fraasi": {
        "title": "Phalarodon fraasi",
        "description": "Phalarodon was a 1.2-meter mixosaurid ichthyosaur from the Middle Triassic (Anisian) Prida Formation of Nevada and the Guanling Formation of China. Distinguished by a prominent sagittal cranial crest and bulbous button-like rear teeth, it was an agile predator crushing ammonoids and belemnoid cephalopods.",
        "tags": [
            "chordate", "ichthyosaur", "ichthyosauria", "marine", "marine_reptile",
            "mesozoic", "mid_triassic", "mixosauridae", "nevada", "phalarodon",
            "phalarodon_fraasi", "prida_formation", "reptile", "triassic", "usa"
        ],
        "keyframes": ["mid_triassic"]
    },
    "batrachosuchus_browni": {
        "title": "Batrachosuchus browni",
        "description": "Batrachosuchus was a 1.5- to 2-meter aquatic brachyopid temnospondyl amphibian from the Middle Triassic (Anisian) Burgersdorp Formation of South Africa. With a broad, flattened parabolic skull and upward-directed eyes, it lay concealed in murky riverbeds to ambush passing fish and tetrapods.",
        "tags": [
            "amphibian", "aquatic", "beaufort_group", "brachyopidae", "chordate",
            "karoo", "mesozoic", "mid_triassic", "predator", "south_africa",
            "stereospondyli", "temnospondyli", "triassic"
        ],
        "keyframes": ["mid_triassic"]
    },
    "diademodon_tetragonus": {
        "title": "Diademodon tetragonus",
        "description": "Diademodon was a 2-meter herbivorous-to-omnivorous cynodont from the Middle Triassic (Anisian) Burgersdorp Formation of South Africa. Widespread across southern Gondwana, it possessed characteristic crown-shaped expanded cheek teeth used to crush tough vegetation and invertebrates.",
        "tags": [
            "beaufort_group", "chordate", "cynodont", "cynodontia", "diademodon",
            "diademodon_tetragonus", "diademodontidae", "karoo", "land_vertebrate",
            "mammal_like_reptile", "mesozoic", "mid_triassic", "omnivore", "south_africa",
            "stem_mammal", "synapsid", "therapsid", "triassic"
        ],
        "keyframes": ["mid_triassic"]
    },
    "archaeonectrus_rostratus": {
        "title": "Archaeonectrus rostratus",
        "description": "Archaeonectrus was a 4-meter, short-necked predatory plesiosaur (rhomaleosaurid) from the Early Jurassic (Sinemurian) Charmouth Mudstone Formation of Dorset, England. Armed with a long, robust snout and sharp interlocking teeth, it was a dominant carnivore patrolling the early Jurassic seas.",
        "tags": [
            "archaeonectrus", "archaeonectrus_rostratus", "charmouth_mudstone", "chordate",
            "dorset", "early_jurassic", "england", "jurassic", "jurassic_coast", "marine",
            "marine_reptile", "mesozoic", "plesiosaur", "plesiosauria", "reptile",
            "rhomaleosauridae", "uk"
        ],
        "keyframes": ["early_jurassic"]
    },
    "caelestiventus_hanseni": {
        "title": "Caelestiventus hanseni",
        "description": "Caelestiventus was a large early pterosaur with a 1.5-meter wingspan from the Late Triassic (Norian) Nugget Sandstone of Utah, USA. Inhabiting desert dune oasis environments, it preserved delicate pneumatic bone cavities and prominent anterior canine-like teeth, providing crucial evidence of early pterosaur diversity.",
        "tags": [
            "caelestiventus", "caelestiventus_hanseni", "chordate", "desert",
            "dimorphodontidae", "flying_reptile", "late_triassic", "mesozoic",
            "nugget_sandstone", "pneumatic_bones", "pterosaur", "pterosauria",
            "reptile", "triassic", "usa", "utah"
        ],
        "keyframes": ["late_triassic"]
    },
    "barracudasauroides_panxiensis": {
        "title": "Barracudasauroides panxiensis",
        "description": "Barracudasauroides was a 75-cm mixosaurid ichthyosaur from the Middle Triassic (Anisian) Guanling Formation of Guizhou, China. Featuring a slender, barracuda-like body form, large eyes, and sharp grasping teeth, it pursued small fish and cephalopods in the warm shallow coastal margins of eastern Tethys.",
        "tags": [
            "barracudasauroides", "barracudasauroides_panxiensis", "china", "chordate",
            "guanling_formation", "guizhou", "ichthyosaur", "ichthyosauria", "marine",
            "marine_reptile", "mesozoic", "mid_triassic", "mixosauria", "mixosauridae",
            "piscivore", "reptile", "triassic"
        ],
        "keyframes": ["mid_triassic"]
    },
    "guaibasaurus_candeleriensis": {
        "title": "Guaibasaurus candeleriensis",
        "description": "Guaibasaurus was a 1.8-meter basal saurischian dinosaur from the Late Triassic (Norian) Caturrita Formation of Rio Grande do Sul, Brazil. Exhibiting an anatomical mosaic linking early theropods with ancestral sauropodomorphs, it offers crucial insights into early dinosaur radiation in South America.",
        "tags": [
            "basal_dinosaur", "brazil", "caturrita_formation", "chordate", "dinosaur",
            "dinosauria", "early_dinosaur", "guaibasauridae", "guaibasaurus",
            "guaibasaurus_candeleriensis", "land_vertebrate", "late_triassic",
            "mesozoic", "reptile", "saurischia", "south_america", "triassic"
        ],
        "keyframes": ["late_triassic"]
    },
    "monjurosuchus_splendens": {
        "title": "Monjurosuchus splendens",
        "description": "Monjurosuchus was a 40-cm semi-aquatic choristodere from the Early Cretaceous (Aptian) Yixian Formation of Liaoning, China. Possessing webbed feet, small granular scales, and dorsal rows of protective scutes, this lizard-like freshwater predator survived as a relict of the Jurassic choristoderan radiation.",
        "tags": [
            "china", "chordate", "choristodera", "early_cretaceous", "freshwater", "jehol",
            "mesozoic", "monjurosuchus", "monjurosuchus_splendens", "predator", "reptile",
            "semi_aquatic", "yixian_formation"
        ],
        "keyframes": ["early_cretaceous"]
    },
    "coeruleodraco_jurassicus": {
        "title": "Coeruleodraco jurassicus",
        "description": "Coeruleodraco ('blue dragon') was a 40-cm freshwater choristoderan reptile from the Late Jurassic (Oxfordian) Tiaojishan Formation of Hebei, China. As the most complete Jurassic choristodere known, it possessed slender jaws with sharp conical teeth suited for hunting fish and aquatic invertebrates in volcanic caldera lakes.",
        "tags": [
            "china", "chordate", "choristodera", "coeruleodraco", "coeruleodraco_jurassicus",
            "freshwater", "hebei", "jurassic", "late_jurassic", "mesozoic", "mid_jurassic",
            "predator", "reptile", "semi_aquatic", "tiaojishan_formation"
        ],
        "keyframes": ["late_jurassic", "mid_jurassic"]
    },
    "scutellosaurus_lawleri": {
        "title": "Scutellosaurus lawleri",
        "description": "Scutellosaurus was a 1.2-meter basal armored ornithischian dinosaur (thyreophoran) from the Early Jurassic (Sinemurian) Kayenta Formation of Arizona, USA. Featuring an exceptionally long balancing tail and hundreds of small keeled dermal scutes across its back, it represents one of the earliest ancestors of stegosaurs and ankylosaurs.",
        "tags": [
            "arizona", "armored_dinosaur", "chordate", "dinosaur", "dinosauria",
            "early_jurassic", "herbivore", "jurassic", "kayenta_formation", "land_vertebrate",
            "mesozoic", "ornithischia", "reptile", "scutellosaurus", "scutellosaurus_lawleri",
            "thyreophora", "usa"
        ],
        "keyframes": ["early_jurassic"]
    },
    "plesiosaurus_dolichodeirus": {
        "title": "Plesiosaurus dolichodeirus",
        "description": "Plesiosaurus was a 3.5-meter marine reptile discovered by Mary Anning in 1823 in the Early Jurassic (Sinemurian) Charmouth Mudstone of Lyme Regis, Dorset, England. With its compact body, four powerful paddle fins, small head, and extraordinarily long neck, it serves as the archetypal representative of the Plesiosauria.",
        "tags": [
            "charmouth_mudstone", "chordate", "dorset", "early_jurassic", "england",
            "jurassic", "jurassic_coast", "marine", "marine_reptile", "mary_anning",
            "mesozoic", "piscivore", "plesiosaur", "plesiosauria", "plesiosauridae",
            "plesiosaurus", "plesiosaurus_dolichodeirus", "reptile", "uk"
        ],
        "keyframes": ["early_jurassic"]
    },
    "docofossor_brachydactylus": {
        "title": "Docofossor brachydactylus",
        "description": "Docofossor was a tiny 9-cm subterranean mammaliaform (docodont) from the Late Jurassic (Oxfordian) Tiaojishan Formation of Hebei, China. Displaying remarkable anatomical convergence with modern golden moles, it evolved spade-like shovel forepaws, short robust digits, and widened clavicles for digging underground tunnels.",
        "tags": [
            "china", "chordate", "docodonta", "docodontidae", "docofossor",
            "docofossor_brachydactylus", "early_mammal", "fossorial", "hebei", "jurassic",
            "land_vertebrate", "late_jurassic", "mammaliaformes", "mesozoic", "synapsid",
            "tiaojishan_formation"
        ],
        "keyframes": ["late_jurassic"]
    },
    "kayentatherium_wellesi": {
        "title": "Kayentatherium wellesi",
        "description": "Kayentatherium was a 1-meter herbivorous tritylodontid cynodont from the Early Jurassic (Sinemurian) Kayenta Formation of Arizona, USA. Closely related to the ancestors of mammals, it possessed multicusped molar teeth for grinding foliage and strong limbs; exceptionally preserved clutches show it produced litters of up to 38 tiny offspring.",
        "tags": [
            "arizona", "chordate", "cynodont", "cynodontia", "early_jurassic",
            "herbivore", "jurassic", "kayenta_formation", "kayentatherium",
            "kayentatherium_wellesi", "land_vertebrate", "mammal_like_reptile",
            "mesozoic", "stem_mammal", "synapsid", "therapsid", "tritylodontidae", "usa"
        ],
        "keyframes": ["early_jurassic"]
    },
    "lindwurmia_thiuda": {
        "title": "Lindwurmia thiuda",
        "description": "Lindwurmia was a 2.5-meter basal plesiosaur from the earliest Jurassic (Lower Hettangian) of Halberstadt, Germany. Discovered in strata immediately overlying the Triassic-Jurassic boundary, it is one of the oldest known plesiosaurs, named after the mythical German dragon Lindwurm.",
        "tags": [
            "chordate", "early_jurassic", "germany", "jurassic", "lindwurmia",
            "lindwurmia_thiuda", "marine", "marine_reptile", "mesozoic", "plesiosaur",
            "plesiosauria", "predator", "reptile", "rhomaleosauridae", "sauropterygia",
            "triassic_jurassic_extinction"
        ],
        "keyframes": ["early_jurassic", "triassic_jurassic_extinction"]
    },
    "ledumahadi_mafube": {
        "title": "Ledumahadi mafube",
        "description": "Ledumahadi ('giant thunderclap' in Sesotho) was a colossal 10-meter, 12-tonne lessemsaurid sauropodomorph dinosaur from the Early Jurassic (Hettangian) Upper Elliot Formation of South Africa. As one of the earliest dinosaurs to achieve massive multi-tonne bulk, it walked obligately on all fours and foreshadowed the gigantism of Late Jurassic sauropods.",
        "tags": [
            "chordate", "dinosaur", "dinosauria", "early_jurassic", "giant",
            "herbivore", "jurassic", "land_vertebrate", "ledumahadi", "ledumahadi_mafube",
            "lessemsauridae", "mesozoic", "quadrupedal", "reptile", "saurischia",
            "sauropod", "sauropodomorpha", "south_africa"
        ],
        "keyframes": ["early_jurassic", "triassic_jurassic_extinction"]
    },
    "kimmerosaurus_langhami": {
        "title": "Kimmerosaurus langhami",
        "description": "Kimmerosaurus was a 6-meter cryptoclidid plesiosaur from the Late Jurassic (Tithonian) Kimmeridge Clay Formation of Dorset, England. Characterized by a lightly built skull with recurved, densely packed needle-like teeth, it swept through open marine waters filter-feeding or catching small soft-bodied cephalopods and fish.",
        "tags": [
            "chordate", "cryptoclididae", "dorset", "england", "jurassic",
            "kimmeridge_clay", "kimmerosaurus", "kimmerosaurus_langhami", "late_jurassic",
            "marine", "marine_reptile", "mesozoic", "piscivore", "plesiosaur",
            "plesiosauria", "reptile", "sauropterygia", "uk"
        ],
        "keyframes": ["late_jurassic"]
    },
    "maiopatagium_furculiferum": {
        "title": "Maiopatagium furculiferum",
        "description": "Maiopatagium was a 25-cm gliding mammaliaform (euharamiyidan) from the Late Jurassic (Oxfordian) Tiaojishan Formation of Liaoning, China. Preserving extensive wing membranes (patagia) stretched between its limbs and fur impressions, it proves that mammals developed tree-gliding locomotion over 160 million years ago alongside dinosaurs.",
        "tags": [
            "arboreal", "china", "chordate", "early_mammal", "euharamiyida",
            "gliding_mammal", "haramiyida", "jurassic", "late_jurassic", "liaoning",
            "maiopatagium", "maiopatagium_furculiferum", "mammaliaformes", "mesozoic",
            "patagium", "synapsid", "tiaojishan_formation"
        ],
        "keyframes": ["late_jurassic"]
    },
    "allosaurus_fragilis": {
        "title": "Allosaurus fragilis",
        "description": "Allosaurus was an iconic 8.5- to 10-meter theropod dinosaur and the apex predator of the Late Jurassic (Kimmeridgian-Tithonian) Morrison Formation of western North America. Armed with sharp serrated teeth, powerful clawed three-fingered forelimbs, and a flexible skull designed to slash into prey, it hunted massive sauropods and stegosaurs.",
        "tags": [
            "allosauridae", "allosauroidea", "allosaurus", "allosaurus_fragilis",
            "apex_predator", "carnivore", "carnosauria", "chordate", "dinosaur",
            "dinosauria", "jurassic", "land_vertebrate", "late_jurassic", "mesozoic",
            "morrison_formation", "predator", "reptile", "saurischia", "theropod", "usa"
        ],
        "keyframes": ["late_jurassic"]
    },
    "attenborosaurus_conybeari": {
        "title": "Attenborosaurus conybeari",
        "description": "Attenborosaurus was a 5-meter pliosaurid plesiosaur from the Early Jurassic (Sinemurian) Charmouth Mudstone of Dorset, England, named in honor of naturalist Sir David Attenborough. Possessing a proportionally large skull, sharp grasping teeth, and a moderately short neck, it was an agile predator of pelagic Jurassic fish and squids.",
        "tags": [
            "attenborosaurus", "attenborosaurus_conybeari", "charmouth_mudstone", "chordate",
            "david_attenborough", "dorset", "early_jurassic", "england", "jurassic",
            "jurassic_coast", "marine", "marine_reptile", "mesozoic", "piscivore",
            "plesiosaur", "plesiosauria", "pliosauridae", "reptile", "uk"
        ],
        "keyframes": ["early_jurassic"]
    },
    "vouivria_damparisensis": {
        "title": "Vouivria damparisensis",
        "description": "Vouivria was a 15-meter brachiosaurid sauropod dinosaur from the Late Jurassic (Oxfordian) Calcaires de Clerval of Franche-Comté, France. Identified as one of the oldest known true brachiosaurids, it possessed elevated forequarters, an elongated neck, and chisel-like teeth suited for high-canopy browsing.",
        "tags": [
            "brachiosauridae", "chordate", "dinosaur", "dinosauria", "france",
            "herbivore", "jurassic", "land_vertebrate", "late_jurassic", "macronaria",
            "mesozoic", "neosauropoda", "reptile", "saurischia", "sauropod",
            "sauropodomorpha", "vouivria", "vouivria_damparisensis"
        ],
        "keyframes": ["late_jurassic"]
    },
    "gavialinum_rhodani": {
        "title": "Gavialinum rhodani",
        "description": "Gavialinum was a 3-meter teleosaurid marine crocodylomorph from the Middle Jurassic (Bathonian) limestone quarries of Ain, France. Equipped with a very slender elongated rostrum and needle-like teeth convergent with modern gharials, it was fully adapted to nearshore marine life hunting schools of fish and squid.",
        "tags": [
            "chordate", "crocodylomorph", "france", "gavialinum", "gavialinum_rhodani",
            "gharial_snout", "jurassic", "marine", "marine_crocodile", "marine_reptile",
            "mesoeucrocodylia", "mesozoic", "mid_jurassic", "piscivore", "reptile",
            "teleosauridae", "thalattosuchia"
        ],
        "keyframes": ["mid_jurassic"]
    },
    "isaberrysaura_mollensis": {
        "title": "Isaberrysaura mollensis",
        "description": "Isaberrysaura was a 4.5-meter basal neornithischian dinosaur from the Early to Middle Jurassic (Toarcian-Bajocian) Los Molles Formation of Neuquén, Argentina. Exceptional fossilized gut contents revealed that it fed on large cycad seeds, providing rare and direct evidence of seed-dispersal mutualism between dinosaurs and Mesozoic plants.",
        "tags": [
            "argentina", "chordate", "cycad_feeder", "dinosaur", "dinosauria",
            "early_jurassic", "herbivore", "isaberrysaura", "isaberrysaura_mollensis",
            "jurassic", "land_vertebrate", "los_molles", "mesozoic", "mid_jurassic",
            "neornithischia", "ornithischia", "reptile", "south_america"
        ],
        "keyframes": ["early_jurassic", "mid_jurassic"]
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
