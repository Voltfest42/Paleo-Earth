#!/usr/bin/env python3
"""
update_keyframe_images.py
=========================
Helper script to manage, optimize, and catalog keyframe hero mood illustrations
in `images/keyframe_images/` and update `data/keyframe-images.json`.

Usage:
    python scripts/update_keyframe_images.py
    python scripts/update_keyframe_images.py --sync-s3
"""

import os
import sys
import json
import glob
import shutil
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KEYFRAME_IMG_DIR = PROJECT_ROOT / "images" / "keyframe_images"
KEYFRAME_JSON_PATH = PROJECT_ROOT / "data" / "keyframes.json"
OUTPUT_JSON_PATH = PROJECT_ROOT / "data" / "keyframe-images.json"

# Common alias/naming variants to official keyframe IDs in keyframes.json
KNOWN_ALIASES = {
    "permian-triassic_great_dying": "permian_triassic_extinction",
    "permian_triassic_great_dying": "permian_triassic_extinction",
    "triassic–jurassic_mass_extinction": "triassic_jurassic_extinction",
    "triassic-jurassic_mass_extinction": "triassic_jurassic_extinction",
    "triassic_jurassic_mass_extinction": "triassic_jurassic_extinction",
    "mesozoic_marine_revolution": "jurassic_marine_revolution",
    "k-pg_mass_extinction": "kpg_extinction",
    "kpg_mass_extinction": "kpg_extinction",
    "k_pg_mass_extinction": "kpg_extinction",
}

def main():
    sync_s3 = "--sync-s3" in sys.argv

    if not KEYFRAME_JSON_PATH.exists():
        print(f"Error: {KEYFRAME_JSON_PATH} not found.")
        sys.exit(1)

    with open(KEYFRAME_JSON_PATH, "r", encoding="utf-8") as f:
        keyframes = json.load(f)
    kf_by_id = {k["id"]: k for k in keyframes}

    if not KEYFRAME_IMG_DIR.exists():
        print(f"Creating directory {KEYFRAME_IMG_DIR}...")
        KEYFRAME_IMG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Clean filename copies (normalize unicode en-dashes to standard hyphens)
    for p in KEYFRAME_IMG_DIR.iterdir():
        if "–" in p.name:
            clean_name = p.name.replace("–", "-")
            clean_path = p.parent / clean_name
            if not clean_path.exists():
                shutil.copy2(p, clean_path)
                print(f"Created ASCII hyphen copy: {clean_name}")

    # 2. Process all PNG/JPG images to WebP if missing or older
    all_source_files = list(KEYFRAME_IMG_DIR.glob("*.png")) + list(KEYFRAME_IMG_DIR.glob("*.jpg"))
    for src in all_source_files:
        webp_path = src.with_suffix(".webp")
        if not webp_path.exists() or src.stat().st_mtime > webp_path.stat().st_mtime:
            print(f"Optimizing {src.name} -> {webp_path.name}...")
            with Image.open(src) as im:
                im_res = im.copy()
                im_res.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
                im_res.save(webp_path, "WEBP", quality=85, method=6)

    # 3. Build registry
    registry = {}
    if OUTPUT_JSON_PATH.exists():
        try:
            with open(OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception:
            registry = {}

    # Scan webp/png files
    found_files = sorted(list(KEYFRAME_IMG_DIR.glob("*.webp")))
    for webp in found_files:
        if "–" in webp.name:
            continue  # prefer ASCII hyphen filename
        base_stem = webp.stem
        # Map to keyframe ID
        kf_id = None
        if base_stem in kf_by_id:
            kf_id = base_stem
        elif base_stem.replace("-", "_") in kf_by_id:
            kf_id = base_stem.replace("-", "_")
        elif base_stem in KNOWN_ALIASES:
            kf_id = KNOWN_ALIASES[base_stem]
        elif base_stem.replace("–", "-") in KNOWN_ALIASES:
            kf_id = KNOWN_ALIASES[base_stem.replace("–", "-")]

        if kf_id:
            png_fallback = webp.with_suffix(".png")
            jpg_fallback = webp.with_suffix(".jpg")
            fallback_name = png_fallback.name if png_fallback.exists() else (jpg_fallback.name if jpg_fallback.exists() else webp.name)

            registry[kf_id] = {
                "filename": webp.name,
                "fallback": fallback_name,
                "label": kf_by_id[kf_id]["label"]
            }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n[OK] Updated {OUTPUT_JSON_PATH} ({len(registry)} keyframes with hero illustrations):")
    for kf_id, info in sorted(registry.items()):
        print(f"  - {kf_id:<32} -> {info['filename']} ({info['label']})")

    if sync_s3:
        print("\nSyncing keyframe images to S3...")
        os.system(f'aws s3 sync "{KEYFRAME_IMG_DIR}" s3://paleo-earth-236501162611/images/keyframe_images --no-progress')
        print("Syncing keyframe-images.json to S3...")
        os.system(f'aws s3 cp "{OUTPUT_JSON_PATH}" s3://paleo-earth-236501162611/data/keyframe-images.json')
        print("[OK] S3 sync complete.")

if __name__ == "__main__":
    main()
