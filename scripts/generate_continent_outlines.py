#!/usr/bin/env python3
"""
Paleo Earth - Continent Outlines Generator
==========================================
Takes a directory of Color ID maps and generates matching transparent PNGs 
containing the colored outlines (borders) of each distinct continent region.
White areas (unassigned islands) and Black areas (oceans) are ignored.
"""

import argparse
import os
from pathlib import Path
import cv2
import numpy as np

def generate_outlines(input_path: Path, output_path: Path, thickness: int = 2):
    print(f"Processing: {input_path.name}")
    
    # Read image (BGR in OpenCV)
    img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if img is None:
        print(f"Failed to read {input_path}")
        return False
        
    img_rgb_32 = (img[:,:,2].astype(np.int32) << 16) | (img[:,:,1].astype(np.int32) << 8) | img[:,:,0].astype(np.int32)
    unique_colors = np.unique(img_rgb_32)
    
    out_rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
    kernel = np.ones((thickness, thickness), np.uint8)
    
    for color_val in unique_colors:
        if color_val == 0x000000 or color_val == 0xFFFFFF:
            continue
            
        r = (color_val >> 16) & 0xFF
        g = (color_val >> 8) & 0xFF
        b = color_val & 0xFF
        
        continent_mask = (img_rgb_32 == color_val)
        mask_8u = (continent_mask * 255).astype(np.uint8)
        
        gradient = cv2.morphologyEx(mask_8u, cv2.MORPH_GRADIENT, kernel)
        
        if thickness > 1:
            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thickness, thickness))
            gradient = cv2.dilate(gradient, dilate_kernel)
            
        edge_pixels = gradient > 0
        
        out_rgba[edge_pixels, 0] = b
        out_rgba[edge_pixels, 1] = g
        out_rgba[edge_pixels, 2] = r
        out_rgba[edge_pixels, 3] = 255 
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), out_rgba)
    return True

def main():
    parser = argparse.ArgumentParser(description="Generate transparent, colored continent outlines from Color ID maps.")
    parser.add_argument("--input", "-i", default="textures/continents_color_id", help="Input directory")
    parser.add_argument("--output", "-o", default="textures/continents_outlines", help="Output directory")
    parser.add_argument("--thickness", "-t", type=int, default=3, help="Line thickness in pixels")
    parser.add_argument("--frame", "-f", default="all", help="Frames to process: 'all', '15', or '10-40'")
    
    args = parser.parse_args()
    
    in_dir = Path(args.input)
    out_dir = Path(args.output)
    
    if not in_dir.exists():
        print(f"Error: Input directory {in_dir} does not exist.")
        return
        
    target_frames = set()
    process_all = False
    
    if args.frame.lower() == 'all':
        process_all = True
    elif '-' in args.frame:
        try:
            start, end = map(int, args.frame.split('-'))
            target_frames = set(range(start, end + 1))
        except ValueError:
            print("Invalid frame range. Use format like '10-40'.")
            return
    else:
        try:
            target_frames.add(int(args.frame))
        except ValueError:
            print("Invalid frame number. Use an integer or 'all'.")
            return
            
    processed_count = 0
    for img_path in in_dir.glob("earth_continent_id_2k_*.png"):
        try:
            frame_idx = int(img_path.stem.split('_')[-1])
        except ValueError:
            continue
            
        if not process_all and frame_idx not in target_frames:
            continue
            
        out_name = img_path.name.replace("_id_", "_outline_")
        if generate_outlines(img_path, out_dir / out_name, args.thickness):
            processed_count += 1
            
    print(f"\\nFinished processing {processed_count} files.")

if __name__ == "__main__":
    main()
