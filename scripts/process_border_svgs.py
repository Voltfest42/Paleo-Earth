#!/usr/bin/env python3
"""
Paleo Earth - Political Borders SVG to PNG Batch Processor & Cropper
====================================================================
Automates the Adobe Illustrator & Photoshop manual workflow:
1. Parses GPlates vector border SVGs across geological time (0 - 540 Ma).
2. Increases vector border stroke thickness (default: 6.0 px, replacing manual Illustrator step).
3. Automatically eliminates the transparent margin/padding artifact exported by GPlates,
   cropping to the exact equirectangular map bounds (7656 x 3828 or custom resolution).
4. Renders crisp, anti-aliased white borders on pure black background using the high-performance
   Rust-based vector engine (resvg-py) with multi-threaded parallel execution.

Usage examples:
    # Process all frames with default settings (6px stroke, native 7656x3828 cropped resolution):
    python scripts/process_border_svgs.py

    # Process all frames into standard 8K (8192x4096):
    python scripts/process_border_svgs.py --res 8k

    # Process all frames formatted for Blender sequence (earth_borders_1.png .. earth_borders_109.png):
    python scripts/process_border_svgs.py --naming blender

    # Test run on a single frame and verify against reference:
    python scripts/process_border_svgs.py --file working_files/borders_temp/snapshot_0.00Ma.svg --verify
"""

import argparse
import concurrent.futures
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import resvg_py
    HAS_RESVG = True
except ImportError:
    HAS_RESVG = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# Native equirectangular bounds inside GPlates SVG
NATIVE_OFFSET_X = 151.0
NATIVE_OFFSET_Y = 235.0
NATIVE_WIDTH = 7656
NATIVE_HEIGHT = 3828

PRESETS = {
    "native": (7656, 3828),
    "8k": (8192, 4096),
    "4k": (4096, 2048),
    "2k": (2048, 1024),
}


def parse_ma_from_filename(filename: str) -> Optional[float]:
    """Extract Ma (million years ago) value from filename e.g. snapshot_0.00Ma.svg."""
    m = re.search(r"snapshot_([\d\.]+)Ma", filename, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def calculate_frame_index(ma: float) -> int:
    """Calculate 1-based chronological index matching paleodem_heightmap.py (0 Ma -> 1, 540 Ma -> 109)."""
    return int(round(ma / 5.0)) + 1


def prepare_svg_markup(
    svg_path: Path,
    stroke_width: float = 6.0,
    crop: bool = True,
    width: int = NATIVE_WIDTH,
    height: int = NATIVE_HEIGHT,
) -> str:
    """
    Parse and clean raw GPlates SVG markup identically across all frames:
    - Set stroke-width to requested size across all stroked elements.
    - Remove embedded raster image (transparent background margin artifact).
    - Set equirectangular viewBox to crop out transparent GPlates margins.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}
    ET.register_namespace("", "http://www.w3.org/2000/svg")

    # 1. Remove embedded transparent base64 image
    for parent in root.iter():
        for img in list(parent.findall("svg:image", ns)):
            parent.remove(img)

    # 2. Update stroke-width across all elements and groups
    stroke_w_str = f"{stroke_width:g}"
    for el in root.iter():
        if "stroke-width" in el.attrib:
            el.attrib["stroke-width"] = stroke_w_str

    # 3. Configure viewBox and dimensions
    if crop:
        root.attrib["viewBox"] = f"{NATIVE_OFFSET_X:g} {NATIVE_OFFSET_Y:g} {NATIVE_WIDTH} {NATIVE_HEIGHT}"
    else:
        if "viewBox" not in root.attrib:
            root.attrib["viewBox"] = "0 0 8192 4092"

    root.attrib["width"] = str(width)
    root.attrib["height"] = str(height)

    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def render_svg_to_png(
    svg_path: Path,
    output_path: Path,
    stroke_width: float = 6.0,
    crop: bool = True,
    width: int = NATIVE_WIDTH,
    height: int = NATIVE_HEIGHT,
) -> Tuple[bool, str]:
    """Render SVG to PNG using resvg-py (or fallback)."""
    try:
        svg_str = prepare_svg_markup(
            svg_path=svg_path,
            stroke_width=stroke_width,
            crop=crop,
            width=width,
            height=height,
        )

        if HAS_RESVG:
            png_bytes = resvg_py.svg_to_bytes(
                svg_string=svg_str,
                width=width,
                height=height,
                background="#000000",
                shape_rendering="geometric_precision",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(png_bytes)
            return True, f"Success ({len(png_bytes) / 1024:.1f} KB)"
        elif HAS_CV2:
            return _render_opencv_fallback(svg_path, output_path, stroke_width, crop, width, height)
        else:
            return False, "Neither resvg-py nor opencv-python available for rendering."
    except Exception as e:
        return False, str(e)


def _render_opencv_fallback(
    svg_path: Path,
    output_path: Path,
    stroke_width: float,
    crop: bool,
    width: int,
    height: int,
) -> Tuple[bool, str]:
    """Fallback rasterizer using OpenCV polylines."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}

    scale_x = width / float(NATIVE_WIDTH if crop else 8192)
    scale_y = height / float(NATIVE_HEIGHT if crop else 4092)
    off_x = NATIVE_OFFSET_X if crop else 0.0
    off_y = NATIVE_OFFSET_Y if crop else 0.0

    canvas = np.zeros((height, width), dtype=np.uint8)
    shift = 4
    sub_scale = 1 << shift

    thick = max(1, int(round(stroke_width * ((scale_x + scale_y) / 2.0))))

    for g in root.findall(".//svg:g", ns):
        opacity = g.attrib.get("stroke-opacity", "1")
        stroke = g.attrib.get("stroke", "")
        if opacity == "0" or stroke == "none":
            continue

        for p in g.findall("svg:polyline", ns):
            pts = [pair.split(",") for pair in p.attrib["points"].strip().split(" ")]
            pts_subpixel = np.array(
                [
                    [
                        int(round(((float(pt[0]) - off_x) * scale_x) * sub_scale)),
                        int(round(((float(pt[1]) - off_y) * scale_y) * sub_scale)),
                    ]
                    for pt in pts
                ],
                dtype=np.int32,
            ).reshape((-1, 1, 2))
            cv2.polylines(canvas, [pts_subpixel], isClosed=False, color=255, thickness=thick, lineType=cv2.LINE_AA, shift=shift)

        for l in g.findall("svg:line", ns):
            pt1 = (
                int(round(((float(l.attrib["x1"]) - off_x) * scale_x) * sub_scale)),
                int(round(((float(l.attrib["y1"]) - off_y) * scale_y) * sub_scale)),
            )
            pt2 = (
                int(round(((float(l.attrib["x2"]) - off_x) * scale_x) * sub_scale)),
                int(round(((float(l.attrib["y2"]) - off_y) * scale_y) * sub_scale)),
            )
            cv2.line(canvas, pt1, pt2, color=255, thickness=thick, lineType=cv2.LINE_AA, shift=shift)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)
    return True, f"Success via OpenCV ({os.path.getsize(output_path) / 1024:.1f} KB)"


def determine_output_filename(
    svg_path: Path,
    naming_scheme: str,
    res_suffix: str,
    pad_width: int = 0,
) -> str:
    """Generate target filename according to requested scheme."""
    stem = svg_path.stem
    ma = parse_ma_from_filename(svg_path.name)

    if naming_scheme == "cropped":
        # Matches snapshot_0.00Ma_cropped.png
        return f"{stem}_cropped.png"
    elif naming_scheme == "standard":
        # Matches snapshot_0.00Ma.png
        return f"{stem}.png"
    elif naming_scheme in ("blender", "sequence"):
        if ma is not None:
            idx = calculate_frame_index(ma)
            idx_str = f"{idx:0{pad_width}d}" if pad_width > 0 else str(idx)
            return f"earth_borders_{res_suffix}_{idx_str}.png"
        else:
            return f"{stem}.png"
    elif naming_scheme == "ma":
        if ma is not None:
            return f"earth_borders_{ma:.2f}Ma.png"
        return f"{stem}.png"
    else:
        return f"{stem}_cropped.png"


def run_batch_processing(args):
    """Execute batch rendering with parallel threading."""
    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    # Resolution
    if args.res in PRESETS:
        out_w, out_h = PRESETS[args.res]
    elif args.width and args.height:
        out_w, out_h = args.width, args.height
    else:
        out_w, out_h = NATIVE_WIDTH, NATIVE_HEIGHT

    # Determine resolution suffix for filenames
    res_suffix = "8k"
    if args.res and args.res.lower() in {"8k", "4k", "2k", "1k"}:
        res_suffix = args.res.lower()
    else:
        res_suffix = f"{out_w}x{out_h}"

    # Find SVGs
    if args.file:
        svg_files = [Path(args.file)]
        if not svg_files[0].exists():
            print(f"Error: Specified file '{args.file}' does not exist.")
            sys.exit(1)
    else:
        svg_files = sorted(
            list(input_dir.glob("snapshot_*.svg")) or list(input_dir.glob("*.svg")),
            key=lambda p: (
                parse_ma_from_filename(p.name) if parse_ma_from_filename(p.name) is not None else 9999.0,
                p.name,
            ),
        )

    if not svg_files:
        print(f"No SVG files found in '{input_dir}'.")
        sys.exit(1)

    out_dir = Path(args.outdir)

    print("=" * 76)
    print("Paleo Earth - Political Borders SVG to PNG Processor & Cropper")
    print("=" * 76)
    print(f"  Input Directory:  {input_dir} ({len(svg_files)} files)")
    print(f"  Output Directory: {out_dir}")
    print(f"  Stroke Width:     {args.stroke_width} px (replacing Illustrator manual step)")
    print(f"  Crop Margins:     {'Enabled (7656x3828 equirectangular)' if not args.no_crop else 'Disabled'}")
    print(f"  Output Dimensions:{out_w} x {out_h} ({args.res.upper() if args.res in PRESETS else 'Custom'})")
    print(f"  Naming Scheme:    {args.naming}")
    print(f"  Rendering Engine: {'resvg-py (Rust vector rasterizer)' if HAS_RESVG else 'OpenCV fallback'}")
    print(f"  Workers:          {args.workers}")
    print("=" * 76)

    # Prepare job list
    jobs = []
    for svg_p in svg_files:
        out_name = determine_output_filename(svg_p, args.naming, res_suffix, args.pad)
        out_p = out_dir / out_name
        jobs.append((svg_p, out_p))

    if args.dry_run:
        print("\n[DRY RUN] Planned outputs:")
        for svg_p, out_p in jobs[:10]:
            print(f"  {svg_p.name:<28} -> {out_p.name}")
        if len(jobs) > 10:
            print(f"  ... and {len(jobs) - 10} more files.")
        print("\nDry run complete. No files written.")
        return

    # Process jobs
    t_start = time.time()
    success_count = 0
    fail_count = 0

    def _worker(job):
        src, dst = job
        ok, msg = render_svg_to_png(
            svg_path=src,
            output_path=dst,
            stroke_width=args.stroke_width,
            crop=not args.no_crop,
            width=out_w,
            height=out_h,
        )
        return src.name, dst.name, ok, msg

    print(f"\nProcessing {len(jobs)} files...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_worker, job): job for job in jobs}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            src_name, dst_name, ok, msg = future.result()
            if ok:
                success_count += 1
                status_icon = "[OK]  "
            else:
                fail_count += 1
                status_icon = "[FAIL]"
            print(f"[{i:3d}/{len(jobs):3d}] {status_icon} {src_name:<28} -> {dst_name:<32} {msg}")

    elapsed = time.time() - t_start
    print("=" * 76)
    print(f"Completed {success_count} / {len(jobs)} files in {elapsed:.2f}s ({elapsed / len(jobs):.2f}s per frame).")
    if fail_count > 0:
        print(f"WARNING: {fail_count} files encountered errors.")
    print(f"Output files saved to: {out_dir.resolve()}")

    # Verification against reference if requested
    if args.verify:
        ref_file = input_dir / "snapshot_0.00Ma_cropped.png"
        test_file = out_dir / determine_output_filename(Path("snapshot_0.00Ma.svg"), args.naming, res_suffix, args.pad)
        if ref_file.exists() and test_file.exists() and HAS_CV2:
            print("\n--- Verifying Output Against Manual Reference ---")
            ref_img = cv2.imread(str(ref_file), cv2.IMREAD_GRAYSCALE)
            test_img = cv2.imread(str(test_file), cv2.IMREAD_GRAYSCALE)
            if ref_img.shape == test_img.shape:
                bin_ref = ref_img > 100
                bin_test = test_img > 100
                iou = np.logical_and(bin_ref, bin_test).sum() / np.logical_or(bin_ref, bin_test).sum()
                mae = np.mean(np.abs(test_img.astype(float) - ref_img.astype(float)))
                print(f"  Reference File: {ref_file.name} ({ref_img.shape[1]}x{ref_img.shape[0]})")
                print(f"  Generated File: {test_file.name} ({test_img.shape[1]}x{test_img.shape[0]})")
                print(f"  Shape Match:    YES")
                print(f"  Vector IoU:     {iou * 100:.2f}% overlap with manual Photoshop/Illustrator result")
                print(f"  Pixel MAE:      {mae:.4f} (out of 255)")
            else:
                print(f"  Dimension mismatch: Ref {ref_img.shape} vs Gen {test_img.shape} (due to custom resolution preset)")


def main():
    parser = argparse.ArgumentParser(
        description="Automate Illustrator stroke-width expansion and Photoshop margin cropping for Paleo Earth borders."
    )
    parser.add_argument(
        "--input",
        "-i",
        default="working_files/borders_temp" if Path("working_files/borders_temp").exists() else "borders_temp",
        help="Input directory containing SVG files (default: working_files/borders_temp)",
    )
    parser.add_argument(
        "--outdir",
        "-o",
        default="working_files/textures_temp" if Path("working_files").exists() else "textures_temp",
        help="Output directory for PNG files (default: working_files/borders_temp/cropped)",
    )
    parser.add_argument(
        "--file",
        "-f",
        default=None,
        help="Process a single SVG file instead of the entire directory",
    )
    parser.add_argument(
        "--stroke-width",
        "-s",
        type=float,
        default=6.0,
        help="Stroke width in pixels for border lines (default: 6.0, matching Illustrator setting)",
    )
    parser.add_argument(
        "--no-crop",
        action="store_true",
        help="Disable automatic margin cropping (keeps GPlates transparent outer borders)",
    )
    parser.add_argument(
        "--res",
        choices=["native", "8k", "4k", "2k"],
        default="native",
        help="Resolution preset: 'native' (7656x3828, default), '8k' (8192x4096), '4k' (4096x2048), '2k' (2048x1024)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Custom output width in pixels (overrides --res)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Custom output height in pixels (overrides --res)",
    )
    parser.add_argument(
        "--naming",
        choices=["blender", "cropped", "standard", "ma"],
        default="blender",
        help="Output filename pattern: 'blender' (earth_borders_{index}.png, default), 'cropped' (snapshot_0.00Ma_cropped.png), 'standard' (snapshot_0.00Ma.png), 'ma' (earth_borders_{ma}Ma.png)",
    )
    parser.add_argument(
        "--pad",
        type=int,
        default=0,
        help="Zero-padding for Blender index numbering (e.g. 0 = earth_borders_1.png, 4 = earth_borders_0001.png)",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=min(os.cpu_count() or 4, 16),
        help=f"Number of parallel rendering threads (default: {min(os.cpu_count() or 4, 16)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run and print output file list without writing",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Compare rendered frame against reference snapshot_0.00Ma_cropped.png if present",
    )

    args = parser.parse_args()
    run_batch_processing(args)


if __name__ == "__main__":
    main()
