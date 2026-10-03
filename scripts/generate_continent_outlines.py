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
        
    # Convert to a 2D array of 32-bit integers representing the RGB color to easily isolate pixels
    # OpenCV uses BGR natively, but we can just pack it as BGR or RGB, as long as we are consistent.
    # Let's pack as RGB for easier debugging/hex matching: (R<<16) | (G<<8) | B
    img_rgb_32 = (img[:,:,2].astype(np.int32) << 16) | (img[:,:,1].astype(np.int32) << 8) | img[:,:,0].astype(np.int32)
    
    # Find all unique colors in the image
    unique_colors = np.unique(img_rgb_32)
    
    # Create the final RGBA image (transparent background)
    out_rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
    
    kernel = np.ones((thickness, thickness), np.uint8)
    
    for color_val in unique_colors:
        # Skip Black (Ocean) and White (Unassigned landmasses/islands)
        if color_val == 0x000000 or color_val == 0xFFFFFF:
            continue
            
        # Extract RGB components for the output color
        r = (color_val >> 16) & 0xFF
        g = (color_val >> 8) & 0xFF
        b = color_val & 0xFF
        
        # In the future, if you want different output colors, you can map (r, g, b) to a new color here.
        out_r, out_g, out_b = r, g, b
        
        # Create a binary mask for JUST this specific continent/color
        continent_mask = (img_rgb_32 == color_val)
        mask_8u = (continent_mask * 255).astype(np.uint8)
        
        # Morphological gradient extracts the perimeter/edge of the mask
        gradient = cv2.morphologyEx(mask_8u, cv2.MORPH_GRADIENT, kernel)
        
        # If thickness > 1, we might want to ensure the lines are fully solid
        if thickness > 1:
            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thickness, thickness))
            gradient = cv2.dilate(gradient, dilate_kernel)
            
        # Apply this continent's edge to the output image with its specific color
        edge_pixels = gradient > 0
        
        # We assign B, G, R, A (OpenCV uses BGRA for 4-channel images)
        out_rgba[edge_pixels, 0] = out_b
        out_rgba[edge_pixels, 1] = out_g
        out_rgba[edge_pixels, 2] = out_r
        out_rgba[edge_pixels, 3] = 255  # Fully opaque
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), out_rgba)
    print(f"Saved outline to: {output_path.name}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Generate transparent, colored continent outlines from Color ID maps.")
    parser.add_argument("--input", "-i", default="textures/continents_color_id", help="Input directory")
    parser.add_argument("--output", "-o", default="textures/continents_outlines", help="Output directory")
    parser.add_argument("--thickness", "-t", type=int, default=3, help="Line thickness in pixels")
    
    args = parser.parse_args()
    
    in_dir = Path(args.input)
    out_dir = Path(args.output)
    
    if not in_dir.exists():
        print(f"Error: Input directory {in_dir} does not exist.")
        return
        
    for img_path in in_dir.glob("*.png"):
        out_name = img_path.name.replace("_id_", "_outline_")
        generate_outlines(img_path, out_dir / out_name, args.thickness)

if __name__ == "__main__":
    main()
