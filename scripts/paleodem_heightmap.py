"""
paleodem_heightmap.py — Generate Normalized Height, Depth, Mask, Soft Mask, and Shadow Maps for Blender.

Produces up to five equirectangular maps per geological keyframe from Scotese & Wright PaleoDEMs:
  1. Hard Sea Level Mask (8-bit PNG):
     earth_sealevel_mask_{index}.png
     Binary mask where ocean (<= 0m) is pure black (0) and land (> 0m) is pure white (255).
     Acts as a hard mixer factor for ocean vs land shaders/materials in Blender.

  2. Soft Sea Level Mask (8-bit PNG):
     earth_sealevel_soft_mask_{index}.png
     Smooth coastal transition mask for compositing. Black (0) at -20m elevation,
     white (255) at +20m elevation, with a smooth linear gradient in between.
     Sea level (0m) sits at exactly 50% neutral gray (128).

  3. Land Height Map (32-bit Float OpenEXR, ZIP compressed):
     earth_height_{index}.exr
     Grayscale elevation for land. Sea level (0m) is black (0.0). Highest elevation
     is white (1.0), normalized across the global dataset (up to 10,500m) or per-frame.
     Ocean is clamped to 0.0.

  4. Ocean Depth Map (32-bit Float OpenEXR, ZIP compressed):
     earth_depth_{index}.exr
     Grayscale depth for continental shelves and coastal bathymetry.
     Sea level (0m) is black (0.0). Inverted so deeper water is brighter:
     e.g., -150m becomes +150m (0.3). Clamped at 500m depth (1.0).
     Abyssal plains and depths > 500m clamp to 1.0, preserving clean open ocean.
     Land is clamped to 0.0.

  5. Relief Shadows Map (8-bit PNG or 32-bit EXR):
     earth_shadows_{index}.png  (or .exr via --shadow-format exr)
     Cartographic hillshade shadow map designed for Darken or Multiply blending in Blender.
     Sunlit slopes, flat plains, and ocean are pure white (1.0 / 255 = no shadow).
     Shadowed slopes facing away from the sun are darker values down to black.

Usage Examples:
  # Render all 109 frames at 8K (8192x4096, default) into working_files/textures_temp/:
  python scripts/paleodem_heightmap.py

  # Render modern Earth (Frame 1, 0 Ma) at 8K:
  python scripts/paleodem_heightmap.py --frame 1

  # Render a specific keyframe by Ma (e.g. 440 Ma Early Silurian):
  python scripts/paleodem_heightmap.py --frame 440

  # Render a keyframe by name:
  python scripts/paleodem_heightmap.py --frame kpg_extinction

  # Render at native Scotese 7.2K resolution (7200x3600):
  python scripts/paleodem_heightmap.py --frame 1 --res native

  # Render at 4K resolution:
  python scripts/paleodem_heightmap.py --frame 1 --res 4k

  # Preview frames without generating files (dry run):
  python scripts/paleodem_heightmap.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Check / Import EXR encoding backend (imagecodecs)
# ---------------------------------------------------------------------------
try:
    import imagecodecs
except ImportError:
    print(
        "\n[ERROR] The 'imagecodecs' package is required to write 32-bit float OpenEXR files.\n"
        "Please install it with:\n"
        "    pip install imagecodecs\n",
        file=sys.stderr,
    )
    sys.exit(1)

# Optional fast resizing / saving via OpenCV if available
try:
    import cv2  # type: ignore
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


# ---------------------------------------------------------------------------
# Keyframe ID to Ma mapping
# ---------------------------------------------------------------------------
KEYFRAME_MA_MAP: dict[str, int] = {
    "holocene": 0,
    "mid_pleistocene": 1,
    "early_quaternary": 2,
    "late_neogene": 5,
    "mid_neogene": 15,
    "early_neogene": 20,
    "late_paleogene": 35,
    "mid_paleogene": 50,
    "early_paleogene": 60,
    "late_cretaceous": 75,
    "mid_cretaceous": 100,
    "early_cretaceous": 130,
    "late_jurassic": 150,
    "mid_jurassic": 165,
    "early_jurassic": 195,
    "late_triassic": 215,
    "mid_triassic": 235,
    "early_triassic": 245,
    "late_permian": 260,
    "mid_permian": 275,
    "early_permian": 290,
    "late_carboniferous": 305,
    "mid_carboniferous": 320,
    "early_carboniferous": 345,
    "late_devonian": 370,
    "mid_devonian": 390,
    "early_devonian": 410,
    "late_silurian": 420,
    "mid_silurian": 430,
    "early_silurian": 440,
    "late_ordovician": 450,
    "mid_ordovician": 465,
    "early_ordovician": 480,
    "late_cambrian": 495,
    "mid_cambrian": 510,
    "early_cambrian": 530,
    "cambrian_explosion": 538,
    "great_ordovician_biodiversification": 470,
    "end_ordovician_extinction": 443,
    "late_devonian_extinction": 374,
    "carboniferous_rainforest_collapse": 307,
    "permian_triassic_extinction": 252,
    "triassic_jurassic_extinction": 201,
    "jurassic_marine_revolution": 155,
    "kpg_extinction": 65,
    "petm": 56,
    "eocene_oligocene_transition": 34,
}

# Global dataset limits
DEFAULT_GLOBAL_MAX_LAND_ELEV: float = 10500.0  # Mount Everest peak in Scotese dataset
DEFAULT_MAX_OCEAN_DEPTH: float = 500.0        # Shelf bathymetry ceiling (metres)


# ---------------------------------------------------------------------------
# Data Loading (netCDF4 & CSV)
# ---------------------------------------------------------------------------

def load_nc(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Load a Scotese & Wright PaleoDEM netCDF file.
    Returns (elevation_grid, lat_array), north-up, west-left.
    """
    from netCDF4 import Dataset  # type: ignore

    ds = Dataset(path)
    lat_arr: np.ndarray | None = None
    for name in ("latitude", "lat", "y"):
        if name in ds.variables and ds.variables[name].ndim == 1:
            lat_arr = np.array(ds.variables[name][:], dtype=np.float64)
            break

    preferred = ("z", "elev", "elevation", "topo", "topography", "Band1", "height")
    elev_name = None
    for key in preferred:
        if key in ds.variables and ds.variables[key].ndim >= 2:
            elev_name = key
            break
    if elev_name is None:
        candidates = [k for k, v in ds.variables.items() if v.ndim >= 2]
        if not candidates:
            raise SystemExit(f"No 2-D elevation variable found in {path}")
        elev_name = candidates[0]

    arr = np.array(ds.variables[elev_name][:], dtype=np.float32)
    ds.close()

    while arr.ndim > 2:
        arr = arr[0]

    # Ensure (lat, lon) orientation
    h, w = arr.shape
    if h > w and h // w == 2:
        arr = arr.T

    # Trim duplicate wrap-around boundary row/column (e.g. 1801x3601 -> 1800x3600)
    if arr.shape[0] % 2 == 1:
        arr = arr[:-1, :]
    if arr.shape[1] % 2 == 1:
        arr = arr[:, :-1]

    if lat_arr is not None and len(lat_arr) == arr.shape[0] + 1:
        lat_arr = lat_arr[:-1]

    # Ensure north-up
    if lat_arr is not None and lat_arr[0] < lat_arr[-1]:
        arr = np.flipud(arr)
        lat_arr = lat_arr[::-1]

    return arr, lat_arr


def load_csv(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """Load gridded CSV elevation data."""
    raw = np.loadtxt(path, delimiter=",")
    if raw.ndim != 2 or raw.shape[1] < 3:
        raw = np.loadtxt(path)
    lon, lat, elev = raw[:, 0], raw[:, 1], raw[:, 2]
    lon_i = np.rint(lon).astype(int)
    lat_i = np.rint(lat).astype(int)
    grid = np.full((180, 360), 0.0, dtype=np.float32)
    grid[lat_i + 90, (lon_i + 180) % 360] = elev
    grid = np.flipud(grid)
    lat_arr = np.linspace(90.0, -90.0, 180, endpoint=False)
    return grid, lat_arr


def load_dem(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """Unified entry point for loading DEM files."""
    suffix = path.suffix.lower()
    if suffix == ".nc":
        return load_nc(path)
    if suffix in {".csv", ".txt", ".dat"}:
        return load_csv(path)
    raise SystemExit(f"Unsupported DEM file type: {path}")


# ---------------------------------------------------------------------------
# Metadata & Filename Helpers
# ---------------------------------------------------------------------------

def parse_paleodem_filename(path: Path) -> tuple[int, int]:
    """Extract (sequence_index, ma) from a paleodem filename."""
    name = path.name
    # Standard format: 1_paleodem_0.nc, 89_paleodem_440.nc
    m = re.match(r"^(\d+)_paleodem_(\d+(?:\.\d+)?)\.nc$", name, re.IGNORECASE)
    if m:
        idx = int(m.group(1))
        ma = int(round(float(m.group(2))))
        return idx, ma

    # Legacy format: e.g. Map76_PALEOMAP_6min_Early_Silurian_440Ma.nc
    m = re.search(r"(\d+(?:\.\d+)?)Ma", name, re.IGNORECASE)
    if m:
        ma = int(round(float(m.group(1))))
        idx = (ma // 5) + 1
        return idx, ma

    raise ValueError(f"Cannot parse index/Ma from filename: {name}")


def parse_frame_selector(
    selector: str,
    all_files: list[tuple[int, int, Path]],
) -> list[tuple[int, int, Path]]:
    """Parse user --frame argument."""
    sel = selector.strip().lower()
    if sel == "all":
        return all_files

    # Keyframe name lookup
    if sel in KEYFRAME_MA_MAP:
        target_ma = round(KEYFRAME_MA_MAP[sel] / 5.0) * 5
        matched = [f for f in all_files if f[1] == target_ma]
        if not matched:
            raise SystemExit(f"No paleodem found for keyframe '{sel}' (snapped {target_ma} Ma)")
        return matched

    # Range format: e.g. "0-50"
    if "-" in sel and not sel.startswith("-"):
        parts = sel.split("-", 1)
        try:
            start_ma = float(parts[0])
            end_ma = float(parts[1])
            return [f for f in all_files if start_ma <= f[1] <= end_ma]
        except ValueError:
            pass

    # Comma-separated list
    tokens = [t.strip() for t in sel.split(",") if t.strip()]
    selected: list[tuple[int, int, Path]] = []
    seen = set()

    for tok in tokens:
        if tok in KEYFRAME_MA_MAP:
            target_ma = round(KEYFRAME_MA_MAP[tok] / 5.0) * 5
            for f in all_files:
                if f[1] == target_ma and f[2] not in seen:
                    selected.append(f)
                    seen.add(f[2])
            continue

        try:
            val = float(tok)
            # Match by Ma first
            matches = [f for f in all_files if abs(f[1] - val) < 0.1]
            if not matches:
                # Match by index (1 to 109)
                matches = [f for f in all_files if f[0] == int(val)]

            for m in matches:
                if m[2] not in seen:
                    selected.append(m)
                    seen.add(m[2])
        except ValueError:
            print(f"Warning: Unrecognized frame identifier '{tok}', skipping.")

    if not selected:
        raise SystemExit(f"No frames matched selector '{selector}'. Available 0 to 540 Ma or 'all'.")

    return selected


# ---------------------------------------------------------------------------
# Resolution & Resampling
# ---------------------------------------------------------------------------

def parse_resolution(res_str: str | None, width: int | None, height: int | None) -> tuple[int, int]:
    """Resolve output (width, height) with standard presets."""
    PRESETS: dict[str, tuple[int, int]] = {
        "8k": (8192, 4096),
        "8192": (8192, 4096),
        "native": (7200, 3600),
        "7.2k": (7200, 3600),
        "7200": (7200, 3600),
        "4k": (4096, 2048),
        "4096": (4096, 2048),
        "2k": (2048, 1024),
        "2048": (2048, 1024),
        "1k": (1024, 512),
        "1024": (1024, 512),
    }

    if res_str:
        s = str(res_str).strip().lower()
        if s in PRESETS:
            return PRESETS[s]
        if "x" in s:
            parts = s.split("x")
            return int(parts[0]), int(parts[1])
        try:
            w = int(s)
            return w, w // 2
        except ValueError:
            raise SystemExit(
                f"Invalid resolution format: '{res_str}'. Use '8k', 'native', '4k', '2k', '1k', or '8192x4096'."
            )

    if width is not None and height is not None:
        return width, height
    if width is not None and height is None:
        return width, width // 2
    if height is not None and width is None:
        return height * 2, height

    # Default to 8K (8192x4096)
    return 8192, 4096


def resize_grid(grid: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """Resize elevation grid (H, W) to (out_h, out_w) with bilinear interpolation."""
    in_h, in_w = grid.shape
    if (in_w, in_h) == (out_w, out_h):
        return grid

    if HAS_CV2:
        return cv2.resize(grid, (out_w, out_h), interpolation=cv2.INTER_LINEAR)

    # Fallback to PIL Image mode='F' (32-bit float)
    img = Image.fromarray(grid, mode="F")
    resized = img.resize((out_w, out_h), resample=Image.Resampling.BILINEAR)
    return np.array(resized, dtype=np.float32)


# ---------------------------------------------------------------------------
# Map Generation Math
# ---------------------------------------------------------------------------

def generate_sealevel_mask(grid: np.ndarray, sealevel: float = 0.0) -> np.ndarray:
    """
    Generate harsh sea level mask.
    - Elevation > sealevel (land)   -> 255 (pure white)
    - Elevation <= sealevel (ocean) -> 0   (pure black)
    
    Using strict > sealevel ensures that 0.0m shallow continental shelves
    (English Channel, North Sea, Florida keys & Bahamas) remain ocean black.
    Returns uint8 (H, W) array.
    """
    return (grid > sealevel).astype(np.uint8) * 255


def generate_sealevel_soft_mask(
    grid: np.ndarray,
    low: float = -20.0,
    high: float = 20.0,
) -> np.ndarray:
    """
    Generate soft sea level mask with linear gradient across coastal boundary.
    - Elevation <= low (-20m)   -> 0   (pure black)
    - Elevation >= high (+20m)  -> 255 (pure white)
    - Between low and high      -> linear gradient [0, 255]
    (At 0.0m sea level, value is exactly 128 / 50% neutral gray).
    Returns uint8 (H, W) array.
    """
    span = max(high - low, 1e-6)
    t = np.clip((grid - low) / span, 0.0, 1.0)
    return (t * 255.0).clip(0, 255).astype(np.uint8)


def generate_land_height(
    grid: np.ndarray,
    max_land: float,
    scale_mode: str = "global",
    sealevel: float = 0.0,
) -> tuple[np.ndarray, float]:
    """
    Generate normalized land height map.
    - Sea level (sealevel) is black (0.0).
    - Peak elevation is white (1.0).
    - Ocean (<= sealevel) is clamped to 0.0.
    Returns (float32 array in [0.0, 1.0], effective_max_elev).
    """
    eff_max = max_land
    if scale_mode == "per-frame":
        peak = float(np.max(grid))
        eff_max = peak if peak > sealevel else (sealevel + 1.0)

    # Land: (elevation - sealevel) / span clamped to [0.0, 1.0]; ocean clamped to 0.0
    span = max(eff_max - sealevel, 1e-6)
    land = np.where(grid > sealevel, np.clip((grid - sealevel) / span, 0.0, 1.0), 0.0).astype(np.float32)
    return land, eff_max


def generate_ocean_depth(
    grid: np.ndarray,
    max_depth: float = DEFAULT_MAX_OCEAN_DEPTH,
    sealevel: float = 0.0,
) -> np.ndarray:
    """
    Generate normalized ocean depth map.
    - Water elevation below sealevel becomes positive depth (sealevel - elevation).
    - Sea level (sealevel) is black (0.0).
    - Deeper water gets brighter up to max_depth (e.g. 500m -> 1.0).
    - Anything deeper than max_depth (depth > max_depth) clamps to 1.0.
    - Land (>= sealevel) is clamped to 0.0.
    Returns float32 array in [0.0, 1.0].
    """
    # Depth = sealevel - elevation for ocean; 0.0 for land
    depth_m = np.where(grid < sealevel, sealevel - grid, 0.0)
    # Clamped to [0.0, 1.0] across max_depth
    depth_norm = np.clip(depth_m / max_depth, 0.0, 1.0).astype(np.float32)
    return depth_norm


def generate_shadows(
    grid: np.ndarray,
    z_factor: float = 1.0,
    altitude_deg: float = 45.0,
    azimuth_deg: float = 315.0,
    ambient: float = 0.0,
    sealevel: float = 0.0,
    lat_array: np.ndarray | None = None,
) -> np.ndarray:
    """
    Generate cartographic relief shadow map for Darken/Multiply blending.
    - Flat plains, sunlit slopes, and ocean -> 1.0 (pure white = no shadow)
    - Slopes angled away from the sun       -> darker values (< 1.0 down to ambient)
    Returns float32 array in [ambient, 1.0].
    """
    g = grid.astype(np.float32) * z_factor
    dy_south, dx_east = np.gradient(g)
    dy_north = -dy_south

    if lat_array is not None:
        cos_lat = np.clip(np.cos(np.radians(lat_array))[:, None], 0.01, 1.0)
        dx_east = dx_east / cos_lat

    alt = np.radians(altitude_deg)
    az = np.radians(azimuth_deg)
    slope = np.pi / 2.0 - np.arctan(np.hypot(dx_east, dy_north))
    aspect = np.arctan2(-dx_east, dy_north)
    shade = np.clip(
        np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect),
        0.0,
        1.0,
    )

    # Flat horizontal terrain shade value
    flat_shade = max(float(np.sin(alt)), 1e-4)

    # Normalized shadow: flat or sunlit slopes are 1.0; shadowed slopes are < 1.0
    shadow = np.clip(shade / flat_shade, 0.0, 1.0)

    # Apply ambient floor if specified
    if ambient > 0.0:
        shadow = ambient + (1.0 - ambient) * shadow

    # Force ocean to 1.0 (no terrain shadows cast onto water)
    is_land = grid > sealevel
    shadow = np.where(is_land, shadow, 1.0).astype(np.float32)
    return shadow


# ---------------------------------------------------------------------------
# File Writers
# ---------------------------------------------------------------------------

def save_png_grayscale(arr_u8: np.ndarray, path: Path) -> None:
    """Save 8-bit grayscale PNG using fast backend."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if HAS_CV2:
        cv2.imwrite(str(path), arr_u8)
    else:
        img = Image.fromarray(arr_u8, mode="L")
        img.save(path, format="PNG")


def save_exr_float32(
    arr: np.ndarray,
    path: Path,
    compression: int = imagecodecs.EXR.COMPRESSION.ZIP,
) -> None:
    """Save single-channel 32-bit float OpenEXR with lossless ZIP compression."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = imagecodecs.exr_encode(
        arr.astype(np.float32),
        compression=compression,
    )
    with open(path, "wb") as f:
        f.write(encoded)


# ---------------------------------------------------------------------------
# CLI Argument Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate normalized 32-bit float EXR height/depth maps, 8-bit PNG sea level masks, soft masks, and shadow maps for Blender.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("working_files/paleodems") if Path("working_files/paleodems").exists() else Path("paleodems"),
        help="Input paleodems directory or specific .nc file",
    )
    p.add_argument(
        "--frame", "-f",
        type=str,
        default="all",
        help="Which frame(s) to process: 'all', sequence index (e.g. '1'), Ma (e.g. '440'), keyframe name ('kpg_extinction'), or range ('0-65')",
    )
    p.add_argument(
        "--outdir", "-o",
        type=Path,
        default=Path("working_files/textures_temp") if Path("working_files").exists() else Path("textures_temp"),
        help="Output directory for generated texture maps",
    )
    p.add_argument(
        "--res", "--resolution",
        type=str,
        default="8k",
        help="Output resolution preset: '8k' (8192x4096, default), 'native' (7200x3600), '4k' (4096x2048), '2k', '1k', or 'WIDTHxHEIGHT'",
    )
    p.add_argument(
        "--width",
        type=int,
        default=None,
        help="Explicit output width in pixels (height auto-computes to width // 2)",
    )
    p.add_argument(
        "--height",
        type=int,
        default=None,
        help="Explicit output height in pixels (width auto-computes to height * 2)",
    )
    p.add_argument(
        "--height-name",
        choices=["height", "hight"],
        default="height",
        help="File naming for land height: 'height' (earth_height_{idx}.exr, default) or 'hight' (earth_hight_{idx}.exr)",
    )
    p.add_argument(
        "--scale",
        choices=["global", "per-frame"],
        default="global",
        help="Land normalization scale: 'global' (consistent scale across all geological frames) or 'per-frame' (normalizes each frame to its own peak)",
    )
    p.add_argument(
        "--max-land",
        type=float,
        default=DEFAULT_GLOBAL_MAX_LAND_ELEV,
        help="Maximum land elevation in metres for global normalization (1.0 = this value). Clamps higher peaks.",
    )
    p.add_argument(
        "--max-depth",
        type=float,
        default=DEFAULT_MAX_OCEAN_DEPTH,
        help="Maximum ocean depth in metres for shelf normalization (1.0 = this value). Deeper ocean is clamped at 1.0.",
    )
    p.add_argument(
        "--sealevel",
        type=float,
        default=0.0,
        help="Sea level elevation threshold in metres (default 0.0m). Values strictly above this threshold are classified as land (white 255), and values at or below are classified as ocean (black 0).",
    )
    p.add_argument(
        "--soft-low",
        type=float,
        default=-20.0,
        help="Soft sea level mask lower elevation bound in metres (gradient starts at 0/black here).",
    )
    p.add_argument(
        "--soft-high",
        type=float,
        default=20.0,
        help="Soft sea level mask upper elevation bound in metres (gradient ends at 255/white here).",
    )
    p.add_argument(
        "--zfactor",
        type=float,
        default=1.0,
        help="Relief exaggeration factor for shadow map.",
    )
    p.add_argument(
        "--altitude",
        type=float,
        default=45.0,
        help="Sun elevation angle in degrees for shadow map (45 = mid-afternoon).",
    )
    p.add_argument(
        "--azimuth",
        type=float,
        default=315.0,
        help="Sun azimuth direction in degrees for shadow map (315 = NW).",
    )
    p.add_argument(
        "--ambient",
        type=float,
        default=0.0,
        help="Ambient light floor for shadows (0.0 = full shadow to black, 0.2 = soft shadows).",
    )
    p.add_argument(
        "--shadow-format",
        choices=["png", "exr"],
        default="png",
        help="File format for shadow map: 'png' (8-bit PNG, default) or 'exr' (32-bit Float EXR).",
    )
    p.add_argument(
        "--pad",
        type=int,
        default=0,
        help="Zero-padding width for frame index in filename (0 = unpadded: earth_height_1.exr; 4 = earth_height_0001.exr)",
    )
    p.add_argument(
        "--no-mask",
        action="store_true",
        help="Skip generating hard sea level mask (earth_sealevel_mask_{idx}.png)",
    )
    p.add_argument(
        "--no-soft-mask",
        action="store_true",
        help="Skip generating soft sea level mask (earth_sealevel_soft_mask_{idx}.png)",
    )
    p.add_argument(
        "--no-height",
        action="store_true",
        help="Skip generating land height map (earth_height_{idx}.exr)",
    )
    p.add_argument(
        "--no-depth",
        action="store_true",
        help="Skip generating ocean depth map (earth_depth_{idx}.exr)",
    )
    p.add_argument(
        "--no-shadows",
        action="store_true",
        help="Skip generating shadow relief map (earth_shadows_{idx}.png)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview selected frames and target filenames without writing files",
    )
    return p


# ---------------------------------------------------------------------------
# Main Execution Loop
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Discover input files
    raw_files: list[Path] = []
    if args.input.is_dir():
        raw_files = sorted(
            [f for f in args.input.glob("*.nc")]
            + [f for f in args.input.glob("*.csv")]
        )
    elif args.input.is_file():
        raw_files = [args.input]
    else:
        raise SystemExit(f"Input path not found: {args.input}")

    if not raw_files:
        raise SystemExit(f"No .nc or .csv files found in {args.input}")

    # Parse index and Ma for discovered files
    indexed_files: list[tuple[int, int, Path]] = []
    for f in raw_files:
        try:
            idx, ma = parse_paleodem_filename(f)
            indexed_files.append((idx, ma, f))
        except ValueError as err:
            print(f"Skipping {f.name}: {err}")

    indexed_files.sort(key=lambda x: x[1])  # sort chronological 0 -> 540 Ma

    # Filter target frames
    target_files = parse_frame_selector(args.frame, indexed_files)

    out_width, out_height = parse_resolution(args.res, args.width, args.height)
    if (out_width, out_height) == (8192, 4096):
        res_label = "8192x4096 (Standard 8K)"
    elif (out_width, out_height) == (7200, 3600):
        res_label = "7200x3600 (Native Scotese 7.2K)"
    elif (out_width, out_height) == (4096, 2048):
        res_label = "4096x2048 (4K UHD)"
    elif (out_width, out_height) == (2048, 1024):
        res_label = "2048x1024 (2K)"
    elif (out_width, out_height) == (1024, 512):
        res_label = "1024x512 (1K Preview)"
    else:
        res_label = f"{out_width}x{out_height} (Custom)"

    sh_ext = "exr" if args.shadow_format == "exr" else "png"

    print("=" * 76)
    print("Paleo Earth — Blender Height, Depth, Mask & Shadow Texture Generator")
    print("=" * 76)
    print(f"  Input:            {args.input} ({len(target_files)} / {len(indexed_files)} frames selected)")
    print(f"  Output Dir:       {args.outdir}/")
    print(f"  Resolution:       {res_label}")
    print(f"  Hard Mask:        {'Enabled (8-bit PNG, sealevel > ' + str(args.sealevel) + 'm)' if not args.no_mask else 'Disabled'}")
    print(f"  Soft Mask:        {'Enabled (8-bit PNG, gradient ' + str(args.soft_low) + 'm to ' + str(args.soft_high) + 'm)' if not args.no_soft_mask else 'Disabled'}")
    print(f"  Land Height Map:  {'Enabled (32-bit Float EXR, ZIP)' if not args.no_height else 'Disabled'}")
    print(f"    - Naming:       earth_{args.height_name}_{{index}}.exr")
    print(f"    - Scale:        {args.scale.upper()} (Max land = {args.max_land:.0f}m)")
    print(f"  Ocean Depth Map:  {'Enabled (32-bit Float EXR, ZIP)' if not args.no_depth else 'Disabled'}")
    print(f"    - Bathymetry:   0m (shore) to {args.max_depth:.0f}m (deep shelf) -> 0.0 to 1.0")
    print(f"  Shadow Relief:    {'Enabled (' + sh_ext.upper() + ', sun azimuth ' + str(args.azimuth) + '°, alt ' + str(args.altitude) + '°)' if not args.no_shadows else 'Disabled'}")
    print(f"  Fast Resampling:  {'OpenCV (bilinear)' if HAS_CV2 else 'Pillow (bilinear)'}")
    print("=" * 76)

    def get_filenames(idx: int) -> dict[str, str]:
        idx_str = f"{idx:0{args.pad}d}" if args.pad > 0 else str(idx)
        return {
            "mask": f"earth_sealevel_mask_{idx_str}.png",
            "soft_mask": f"earth_sealevel_soft_mask_{idx_str}.png",
            "height": f"earth_{args.height_name}_{idx_str}.exr",
            "depth": f"earth_depth_{idx_str}.exr",
            "shadows": f"earth_shadows_{idx_str}.{sh_ext}",
        }

    if args.dry_run:
        print("\n[DRY RUN] Planned texture outputs:")
        for idx, ma, f in target_files:
            fn = get_filenames(idx)
            print(f"  [Index {idx:3d}] {ma:3d} Ma ({f.name}):")
            if not args.no_mask:
                print(f"    -> Hard Mask: {args.outdir / fn['mask']}")
            if not args.no_soft_mask:
                print(f"    -> Soft Mask: {args.outdir / fn['soft_mask']}")
            if not args.no_height:
                print(f"    -> Height:    {args.outdir / fn['height']}")
            if not args.no_depth:
                print(f"    -> Depth:     {args.outdir / fn['depth']}")
            if not args.no_shadows:
                print(f"    -> Shadows:   {args.outdir / fn['shadows']}")
        return

    t_start = time.time()
    for count, (idx, ma, f) in enumerate(target_files, 1):
        t0 = time.time()
        print(f"\n[{count}/{len(target_files)}] Processing Frame {idx}: {ma} Ma ({f.name})")

        fn = get_filenames(idx)

        # 1. Load elevation grid
        raw_grid, lat_arr = load_dem(f)
        orig_min, orig_max = float(raw_grid.min()), float(raw_grid.max())
        print(f"  Raw elevation: {orig_min:+.0f}m .. {orig_max:+.0f}m (shape {raw_grid.shape[1]}x{raw_grid.shape[0]})")

        # 2. Resample grid to target resolution
        grid = resize_grid(raw_grid, out_width, out_height)
        lat_target = np.linspace(90.0, -90.0, out_height, endpoint=False)

        # 3. Hard Sea Level Mask
        if not args.no_mask:
            mask = generate_sealevel_mask(grid, sealevel=args.sealevel)
            out_mask = args.outdir / fn["mask"]
            save_png_grayscale(mask, out_mask)
            mask_size_kb = os.path.getsize(out_mask) / 1024
            print(f"  -> Hard Mask:     {out_mask.name:<32} ({mask_size_kb:6.1f} KB)")

        # 4. Soft Sea Level Mask
        if not args.no_soft_mask:
            soft_mask = generate_sealevel_soft_mask(grid, low=args.soft_low, high=args.soft_high)
            out_soft = args.outdir / fn["soft_mask"]
            save_png_grayscale(soft_mask, out_soft)
            soft_size_kb = os.path.getsize(out_soft) / 1024
            print(f"  -> Soft Mask:     {out_soft.name:<32} ({soft_size_kb:6.1f} KB, gradient {args.soft_low:+.0f}m..{args.soft_high:+.0f}m)")

        # 5. Land Height Map (32-bit Float EXR)
        if not args.no_height:
            land_arr, eff_max = generate_land_height(
                grid,
                args.max_land,
                scale_mode=args.scale,
                sealevel=args.sealevel,
            )
            out_height_file = args.outdir / fn["height"]
            save_exr_float32(land_arr, out_height_file)
            h_size_mb = os.path.getsize(out_height_file) / (1024 * 1024)
            print(f"  -> Land Height:   {out_height_file.name:<32} ({h_size_mb:6.2f} MB, peak={orig_max:.0f}m / {eff_max:.0f}m)")

        # 6. Ocean Depth Map (32-bit Float EXR)
        if not args.no_depth:
            depth_arr = generate_ocean_depth(
                grid,
                max_depth=args.max_depth,
                sealevel=args.sealevel,
            )
            out_depth_file = args.outdir / fn["depth"]
            save_exr_float32(depth_arr, out_depth_file)
            d_size_mb = os.path.getsize(out_depth_file) / (1024 * 1024)
            print(f"  -> Ocean Depth:   {out_depth_file.name:<32} ({d_size_mb:6.2f} MB, shelf <= {args.max_depth:.0f}m)")

        # 7. Relief Shadows Map
        if not args.no_shadows:
            shadows_arr = generate_shadows(
                grid,
                z_factor=args.zfactor,
                altitude_deg=args.altitude,
                azimuth_deg=args.azimuth,
                ambient=args.ambient,
                sealevel=args.sealevel,
                lat_array=lat_target,
            )
            out_shadows_file = args.outdir / fn["shadows"]
            if args.shadow_format == "exr":
                save_exr_float32(shadows_arr, out_shadows_file)
                sh_size_str = f"{os.path.getsize(out_shadows_file) / (1024 * 1024):6.2f} MB"
            else:
                sh_u8 = (shadows_arr * 255.0).clip(0, 255).astype(np.uint8)
                save_png_grayscale(sh_u8, out_shadows_file)
                sh_size_str = f"{os.path.getsize(out_shadows_file) / (1024 * 1024):6.2f} MB"
            print(f"  -> Relief Shadows:{out_shadows_file.name:<32} ({sh_size_str}, zfactor={args.zfactor})")

        dt = time.time() - t0
        print(f"  Frame {idx} completed in {dt:.2f}s")

    total_time = time.time() - t_start
    print("\n" + "=" * 76)
    print(f"Batch completed! Processed {len(target_files)} frame(s) in {total_time:.1f}s ({total_time / len(target_files):.2f}s per frame)")
    print("=" * 76)


if __name__ == "__main__":
    main()
