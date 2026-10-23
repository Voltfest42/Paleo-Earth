import os
import json
import shutil

# Paths
source_dir = os.path.join("images", "paleo_art")
target_dir = os.path.join("images", "paleo_art_sorted")
json_path = os.path.join("data", "image-library.json")

# Create target dir if it doesn't exist
os.makedirs(target_dir, exist_ok=True)

# Load JSON
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Known modifiers
modifiers = ["early_", "mid_", "middle_", "late_"]

copied_count = 0

for item in data.get("images", []):
    filename = item.get("filename")
    if not filename: continue
    
    # Path to original image
    src_path = os.path.join(source_dir, filename)
    if not os.path.exists(src_path):
        continue
        
    keyframes = item.get("keyframes", [])
    for kf in keyframes:
        # Reformat keyframe name
        folder_name = kf
        for mod in modifiers:
            if kf.startswith(mod):
                base_period = kf[len(mod):]
                mod_clean = mod.rstrip("_")
                folder_name = f"{base_period}_{mod_clean}"
                break
                
        # Create subfolder
        subfolder_path = os.path.join(target_dir, folder_name)
        os.makedirs(subfolder_path, exist_ok=True)
        
        # Copy file
        dest_path = os.path.join(subfolder_path, filename)
        if not os.path.exists(dest_path):
            shutil.copy2(src_path, dest_path)
            copied_count += 1

print(f"Done! Copied {copied_count} files into {target_dir}")
