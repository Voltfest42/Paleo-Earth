"""
colorize_paleodem.py — Colorize Scotese & Wright PaleoDEMs to WebGL textures.

Generates equirectangular texture maps for Paleo Earth:
  - Diffuse   ({index}_earth_diffuse_{ma}.jpg) — required for globe
  - Normal    ({index}_earth_normal_{ma}.jpg)  — optional normal map
  - Roughness ({index}_earth_rough_{ma}.jpg)   — optional roughness map

Geological Color Regimes:
  1. Vegetated Earth (0 to 435 Ma):
     Lush coastal/lowland greens, olive canopy, upland browns, mountain rock.
  2. First Land Colonization Transition (440 Ma):
     Early moss/bryophyte green confined to moist low-lying coastlines (<90m elev,
     within coastal perimeter), with interior continents remaining barren brown/tan.
  3. Primordial Barren Earth (445 to 540 Ma):
     Pre-vegetation land. Warm sands, alluvial ochre, arid clay, sandstone,
     and rocky highlands. Zero plant green on land.

Normal Map Strength:
  Default --nzfactor is 0.4 (1/10th the strength of the original 4.0),
  producing gentle, smooth relief without harsh or dark normal saturation.

Usage Examples:
  # Render all 109 frames to 8-bit WebGL JPEGs in textures_temp/:
  python scripts/colorize_paleodem.py

  # Render a single keyframe by Ma (e.g. 440 Ma transition frame):
  python scripts/colorize_paleodem.py --frame 440

  # Render a single keyframe by sequence index (e.g. frame 89):
  python scripts/colorize_paleodem.py --frame 89

  # Render by keyframe name:
  python scripts/colorize_paleodem.py --frame early_silurian

  # Render a comma-separated list or range:
  python scripts/colorize_paleodem.py --frame 435,440,445
  python scripts/colorize_paleodem.py --frame 0-25

  # Dry-run inspection:
  python scripts/colorize_paleodem.py --frame all --dry-run
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
# Keyframe ID to Ma mapping for convenience
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

# ---------------------------------------------------------------------------
# Color ramps (elevation in metres → float RGB [0, 1])
# ---------------------------------------------------------------------------

# Ocean shelf & deep ocean shared across all ramps
# Deep abyssal navy -> cyan coastal shelf -> surf
OCEAN_STOPS: list[tuple[float, tuple[float, float, float]]] = [
    (-11000.0, (0.020, 0.071, 0.176)),  # abyssal plain
    (  -200.0, (0.020, 0.071, 0.176)),  # continental slope base
    (   -80.0, (0.047, 0.188, 0.345)),  # outer continental shelf
    (   -20.0, (0.110, 0.314, 0.471)),  # inner shelf / nearshore
    (    -1.0, (0.149, 0.412, 0.580)),  # surf zone
    (     0.0, (0.149, 0.412, 0.580)),  # sea level (prevents green fringe in water)
]

# Regime 1: Modern / Vegetated Earth (0 to 435 Ma)
RAMP_MODERN: list[tuple[float, tuple[float, float, float]]] = [
    *OCEAN_STOPS,
    (   0.5, (0.176, 0.373, 0.216)),   # lush coastal lowlands
    ( 150.0, (0.255, 0.451, 0.176)),   # lowland plains / forests
    ( 500.0, (0.373, 0.451, 0.196)),   # mid-elevation woodlands / savanna
    (1000.0, (0.510, 0.424, 0.227)),   # upland plateau / semi-arid tan
    (2000.0, (0.580, 0.424, 0.267)),   # highland brown
    (3500.0, (0.635, 0.529, 0.392)),   # high mountains
    (5500.0, (0.753, 0.714, 0.635)),   # very high / rocky plateau
    (8900.0, (0.855, 0.843, 0.824)),   # summit rock / snow
]

# Regime 3: Primordial Barren Continents (445 to 540 Ma)
# Pure warm earthen, sandy, clay, and rocky tones — zero green on land
RAMP_BARREN: list[tuple[float, tuple[float, float, float]]] = [
    *OCEAN_STOPS,
    (   0.5, (0.560, 0.465, 0.335)),   # coastal warm sand / silt
    (  50.0, (0.535, 0.435, 0.305)),   # lowland alluvial plain
    ( 200.0, (0.515, 0.410, 0.285)),   # interior plains (warm clay/tan)
    ( 500.0, (0.520, 0.400, 0.265)),   # mid-elevation desert / plateau
    (1000.0, (0.530, 0.410, 0.255)),   # upland arid brown
    (2000.0, (0.580, 0.424, 0.267)),   # highland brown
    (3500.0, (0.635, 0.529, 0.392)),   # high mountains
    (5500.0, (0.753, 0.714, 0.635)),   # very high / rocky plateau
    (8900.0, (0.855, 0.843, 0.824)),   # summit rock
]

# Regime 2: Transition (440 Ma) Coastal Pioneer Target Ramp
# Provides lush, vivid bryophyte/moss pioneer greens along coastal plains and estuaries
RAMP_TRANSITION_440: list[tuple[float, tuple[float, float, float]]] = [
    *OCEAN_STOPS,
    (   0.5, (0.130, 0.430, 0.140)),   # vivid coastal pioneer green
    (  80.0, (0.180, 0.440, 0.160)),   # coastal wetlands & estuaries
    ( 200.0, (0.260, 0.430, 0.180)),   # lowland moss/bryophyte plains
    ( 350.0, (0.390, 0.420, 0.230)),   # transition green-tan
    ( 500.0, (0.490, 0.410, 0.260)),   # arid tan
    ( 750.0, (0.525, 0.405, 0.260)),   # barren interior
    (1000.0, (0.530, 0.410, 0.255)),   # upland arid brown
    (2000.0, (0.580, 0.424, 0.267)),   # highland brown
    (3500.0, (0.635, 0.529, 0.392)),   # high mountains
    (5500.0, (0.753, 0.714, 0.635)),   # plateau
    (8900.0, (0.855, 0.843, 0.824)),   # summit rock
]

# Roughness lookup (elevation in metres → roughness 0.0–1.0)
ROUGH_RAMP: list[tuple[float, float]] = [
    (-11000.0, 0.03),   # deep ocean – very smooth
    (  -200.0, 0.03),   # open ocean
    (   -80.0, 0.12),   # outer shelf
    (   -20.0, 0.20),   # nearshore
    (     0.0, 0.20),
    (     0.5, 0.62),   # coastal lowland
    (   200.0, 0.72),   # plains
    (   800.0, 0.80),   # upland
    (  2000.0, 0.85),   # mountains
    (  4000.0, 0.78),   # very high
    (  6000.0, 0.45),   # glacier / ice
    (  8900.0, 0.30),   # summit snowfields
]

ELEV_MAX = 8900.0

# ---------------------------------------------------------------------------
# Vectorised Ramp Interpolation
# ---------------------------------------------------------------------------

def _lerp_ramp(
    z: np.ndarray,
    stops_z: np.ndarray,
    stops_v: np.ndarray,
) -> np.ndarray:
    """Vectorised linear interpolation through an arbitrary ramp."""
    z = np.clip(z, stops_z[0], stops_z[-1])
    idx = np.searchsorted(stops_z, z, side="right") - 1
    idx = np.clip(idx, 0, len(stops_z) - 2)
    z0 = stops_z[idx]
    z1 = stops_z[idx + 1]
    t = np.where(z1 > z0, (z - z0) / (z1 - z0), 0.0)
    if stops_v.ndim == 2:
        t = t[..., None]
    return (stops_v[idx] * (1.0 - t) + stops_v[idx + 1] * t).astype(np.float32)


def lerp_color_ramp(z: np.ndarray, ramp: list[tuple[float, tuple[float, float, float]]]) -> np.ndarray:
    stops_z = np.array([s[0] for s in ramp], dtype=np.float32)
    stops_c = np.array([s[1] for s in ramp], dtype=np.float32)
    return _lerp_ramp(z.astype(np.float32), stops_z, stops_c)


def lerp_roughness(z: np.ndarray) -> np.ndarray:
    stops_z = np.array([r[0] for r in ROUGH_RAMP], dtype=np.float32)
    stops_v = np.array([r[1] for r in ROUGH_RAMP], dtype=np.float32)
    return _lerp_ramp(z.astype(np.float32), stops_z, stops_v)


# ---------------------------------------------------------------------------
# Geological Colorization (Three Regimes)
# ---------------------------------------------------------------------------

def colorize_dem(grid: np.ndarray, ma: float) -> np.ndarray:
    """
    Select and apply color ramp according to age (Ma):
      - ma <= 435: RAMP_MODERN (vegetation greens)
      - ma == 440: Transition (mossy coastal strip, barren interior)
      - ma >= 445: RAMP_BARREN (pure brownish/earthy continents, zero green)
    """
    if ma <= 435.0:
        return lerp_color_ramp(grid, RAMP_MODERN)

    elif abs(ma - 440.0) < 1.0:
        # 440 Ma Transition: Early Silurian
        # Inland continents are barren brown/tan; coastal lowlands (<350m elevation,
        # within 20 pixels / ~200 km of ocean) display a prominent pioneer moss/bryophyte green belt.
        c_barren = lerp_color_ramp(grid, RAMP_BARREN)
        c_green  = lerp_color_ramp(grid, RAMP_TRANSITION_440)

        # Detect ocean adjacency by 20-pixel morphological dilation (~200 km coastal belt)
        is_ocean = (grid < 0.0)
        near_coast = np.copy(is_ocean)
        for _ in range(20):
            near_coast = (
                near_coast
                | np.roll(near_coast, 1, axis=0)
                | np.roll(near_coast, -1, axis=0)
                | np.roll(near_coast, 1, axis=1)
                | np.roll(near_coast, -1, axis=1)
            )

        # Low coastal land (<350m elevation)
        max_elev = 350.0
        is_coastal_lowland = near_coast & (grid >= 0.0) & (grid < max_elev)
        clamped_elev = np.clip(grid, 0.0, max_elev)
        elev_weight = (1.0 - (clamped_elev / max_elev))[..., None]
        mask = is_coastal_lowland[..., None].astype(np.float32) * (elev_weight ** 0.8)

        # Blend on land, keep ocean unchanged
        land = (grid >= 0.0)[..., None]
        blended = (1.0 - mask) * c_barren + mask * c_green
        return np.where(land, blended, c_barren)

    else:
        # 445 Ma to 540 Ma: Primordial barren continents
        return lerp_color_ramp(grid, RAMP_BARREN)


# ---------------------------------------------------------------------------
# Gradients & Hillshading
# ---------------------------------------------------------------------------

def _gradients(
    grid: np.ndarray,
    lat_array: np.ndarray | None,
    z_factor: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (dx_east, dy_north) gradients scaled by z_factor, with
    latitude correction on the east-west component.
    """
    g = grid.astype(np.float32) * z_factor
    dy_south, dx_east = np.gradient(g)
    dy_north = -dy_south

    if lat_array is not None:
        cos_lat = np.cos(np.radians(lat_array))[:, None]
        cos_lat = np.clip(cos_lat, 0.01, 1.0)
        dx_east = dx_east / cos_lat

    return dx_east.astype(np.float32), dy_north.astype(np.float32)


def hillshade(
    grid: np.ndarray,
    altitude_deg: float,
    azimuth_deg: float,
    z_factor: float,
    lat_array: np.ndarray | None = None,
) -> np.ndarray:
    """Lambertian hillshade. Returns float32 (H, W) in [0, 1]."""
    dx, dy = _gradients(grid, lat_array, z_factor)
    alt = np.radians(altitude_deg)
    az  = np.radians(azimuth_deg)
    slope  = np.pi / 2.0 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    shade  = (
        np.sin(alt) * np.sin(slope)
        + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    )
    return np.clip(shade, 0.0, 1.0).astype(np.float32)


def apply_hillshade(
    colour: np.ndarray,
    grid: np.ndarray,
    strength: float,
    z_factor: float,
    altitude: float,
    azimuth: float,
    lat_array: np.ndarray | None = None,
) -> np.ndarray:
    """
    Overlay-blend hillshade onto the float colour map.
    Ocean remains flat blue; land receives shaded relief.
    """
    if strength <= 0.0:
        return colour

    shade = hillshade(grid, altitude, azimuth, z_factor, lat_array)
    shade = 0.15 + 0.85 * shade  # ambient floor

    s = shade[..., None]
    overlay = np.where(
        colour < 0.5,
        2.0 * colour * s,
        1.0 - 2.0 * (1.0 - colour) * (1.0 - s),
    )
    mixed = (1.0 - strength) * colour + strength * overlay

    land = (grid >= 0.0)[..., None]
    result = np.where(land, mixed, colour)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Normal Map Generation
# ---------------------------------------------------------------------------

def make_normal_map(
    grid: np.ndarray,
    z_factor: float = 0.4,
    lat_array: np.ndarray | None = None,
) -> np.ndarray:
    """
    Tangent-space normal map, OpenGL / Three.js convention.
    Default z_factor is 0.4 (1/10th the strength of the original 4.0),
    providing clean, gentle relief without harsh dark normal saturation.

    Encoding:
      R = X  (0.5 = neutral, >0.5 = east-facing slope)
      G = Y  (0.5 = neutral, >0.5 = north-facing slope)
      B = Z  (>= 0.5; flat surface → 1.0)
    Ocean is forced to perfectly flat (0.5, 0.5, 1.0) -> RGB (128, 128, 255).
    """
    dx_east, dy_north = _gradients(grid, lat_array, z_factor)

    nx = -dx_east
    ny = -dy_north
    nz = np.ones_like(nx)

    mag = np.maximum(np.sqrt(nx ** 2 + ny ** 2 + nz ** 2), 1e-8)
    nx /= mag
    ny /= mag
    nz /= mag

    r = nx * 0.5 + 0.5
    g = ny * 0.5 + 0.5
    b = nz * 0.5 + 0.5

    normal = np.stack([r, g, b], axis=-1).astype(np.float32)
    flat = np.array([0.5, 0.5, 1.0], dtype=np.float32)
    ocean = (grid < 0.0)[..., None]
    normal = np.where(ocean, flat, normal)

    return np.clip(normal, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Roughness Map Generation
# ---------------------------------------------------------------------------

def make_roughness_map(grid: np.ndarray) -> np.ndarray:
    """
    Grayscale roughness map derived from elevation.
    Returns float32 (H, W) in [0, 1].

    0.0 = perfectly smooth (specular) -> deep ocean
    1.0 = fully rough (diffuse)       -> bare rock / mountains
    """
    return np.clip(lerp_roughness(grid), 0.0, 1.0)


# ---------------------------------------------------------------------------
# Data Loading (netCDF4 & CSV)
# ---------------------------------------------------------------------------

def load_nc(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Load a Scotese & Wright PaleoDEM netCDF.
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

    # Ensure (lat, lon)
    h, w = arr.shape
    if h > w and h // w == 2:
        arr = arr.T

    # Trim duplicate wrap-around row/column
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

    arr = np.clip(arr, -11000.0, ELEV_MAX)
    return arr, lat_arr


def load_csv(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
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
    suffix = path.suffix.lower()
    if suffix == ".nc":
        return load_nc(path)
    if suffix in {".csv", ".txt", ".dat"}:
        return load_csv(path)
    raise SystemExit(f"Unsupported file type: {path}")


# ---------------------------------------------------------------------------
# Metadata & Filename Helpers
# ---------------------------------------------------------------------------

def parse_paleodem_filename(path: Path) -> tuple[int, int]:
    """
    Extract (sequence_index, ma) from a paleodem filename.
    Supports both:
      Standard format: '{index}_paleodem_{ma}.nc' -> (index, ma)
      Legacy format:   'Map*_..._{ma}Ma.nc'       -> ((ma // 5) + 1, ma)
    """
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


def parse_frame_selector(selector: str, all_files: list[tuple[int, int, Path]]) -> list[tuple[int, int, Path]]:
    """
    Parse a user --frame argument.
    Accepts:
      - 'all'
      - single Ma or index (e.g. '440', '89')
      - keyframe name (e.g. 'early_silurian', 'kpg_extinction')
      - comma list (e.g. '435,440,445')
      - range (e.g. '0-25' in Ma)
    """
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
            end_ma   = float(parts[1])
            return [f for f in all_files if start_ma <= f[1] <= end_ma]
        except ValueError:
            pass

    # Comma-separated list
    tokens = [t.strip() for t in sel.split(",") if t.strip()]
    selected: list[tuple[int, int, Path]] = []
    seen = set()

    for tok in tokens:
        # Check if tok is keyframe name
        if tok in KEYFRAME_MA_MAP:
            target_ma = round(KEYFRAME_MA_MAP[tok] / 5.0) * 5
            for f in all_files:
                if f[1] == target_ma and f[2] not in seen:
                    selected.append(f)
                    seen.add(f[2])
            continue

        try:
            val = float(tok)
            # Check matching Ma first
            matches = [f for f in all_files if abs(f[1] - val) < 0.1]
            if not matches:
                # If not matched by Ma, check matching sequence index (1-109)
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
# Image Saving & Resizing
# ---------------------------------------------------------------------------

def parse_resolution(
    res_str: str | None,
    width: int | None,
    height: int | None,
) -> tuple[int, int]:
    """
    Resolve output (width, height) with automatic 2:1 aspect ratio enforcement.
    Supports:
      - Presets: '8k'/'full' (7200x3600), '4k' (4096x2048), '2k' (2048x1024), '1k' (1024x512)
      - Exact dimensions: '4096x2048', '2048x1024'
      - Single width dimension: '4096' (height auto-computes to width // 2)
      - Explicit --width and/or --height arguments
    """
    PRESETS = {
        "8k": (7200, 3600),
        "7.2k": (7200, 3600),
        "full": (7200, 3600),
        "4k": (4096, 2048),
        "2k": (2048, 1024),
        "1k": (1024, 512),
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
                f"Invalid resolution format: '{res_str}'. Use '4k', '2k', '1k', '4096x2048', or '4096'."
            )

    if width is not None and height is not None:
        return width, height
    if width is not None and height is None:
        return width, width // 2
    if height is not None and width is None:
        return height * 2, height

    # Default full resolution
    return 7200, 3600


def save_image(
    data: np.ndarray,
    out_path: Path,
    width: int,
    height: int,
    fmt: str = "jpg",
    quality: int = 92,
    mode: str = "RGB",
    depth: int = 8,
) -> None:
    """Save float32 array in [0, 1] to 8-bit JPEG or PNG."""
    u8 = (data * 255.0).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(u8, mode=mode)

    if (img.width, img.height) != (width, height):
        img = img.resize((width, height), Image.Resampling.LANCZOS)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt.lower() in {"jpg", "jpeg"}:
        if img.mode not in {"RGB", "L"}:
            img = img.convert("RGB")
        img.save(out_path, format="JPEG", quality=quality, optimize=True)
    else:
        img.save(out_path, format="PNG")


# ---------------------------------------------------------------------------
# Main CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Render Scotese & Wright PaleoDEMs to WebGL textures with geological color ramps.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("paleodems"),
        help="Input paleodems directory or specific .nc file",
    )
    p.add_argument(
        "--frame", "-f",
        type=str,
        default="all",
        help="Which frame(s) to render: 'all', Ma value (e.g. '440'), index (e.g. '89'), keyframe name ('early_silurian'), or range ('0-30')",
    )
    p.add_argument(
        "--outdir", "-o",
        type=Path,
        default=Path("textures_temp"),
        help="Output directory for generated texture files",
    )
    p.add_argument(
        "--res", "--resolution",
        type=str,
        default=None,
        help="Output resolution preset ('8k', '4k', '2k', '1k') or dimensions ('4096x2048' or '4096')",
    )
    p.add_argument(
        "--width",
        type=int,
        default=None,
        help="Explicit output texture width in pixels (height auto-computes to width // 2 if omitted)",
    )
    p.add_argument(
        "--height",
        type=int,
        default=None,
        help="Explicit output texture height in pixels (width auto-computes to height * 2 if omitted)",
    )
    p.add_argument(
        "--format",
        choices=["jpg", "png"],
        default="jpg",
        help="Texture format (jpg for 8-bit WebGL textures, png for lossless)",
    )
    p.add_argument(
        "--quality",
        type=int,
        default=92,
        help="JPEG quality (1-100) when --format is jpg",
    )
    p.add_argument(
        "--depth",
        type=int,
        choices=[8, 16],
        default=8,
        help="Bit depth. 8-bit for web application textures.",
    )

    # Shading and relief knobs
    p.add_argument(
        "--shade",
        type=float,
        default=0.10,
        help="Hillshade overlay strength on diffuse map (0 = off, 1.0 = maximum)",
    )
    p.add_argument(
        "--zfactor",
        type=float,
        default=6.0,
        help="Relief exaggeration for diffuse hillshade",
    )
    p.add_argument(
        "--altitude",
        type=float,
        default=45.0,
        help="Sun elevation angle in degrees for hillshade",
    )
    p.add_argument(
        "--azimuth",
        type=float,
        default=315.0,
        help="Sun azimuth direction in degrees (315 = NW)",
    )

    # Normal map knob
    p.add_argument(
        "--nzfactor",
        type=float,
        default=0.4,
        help="Relief exaggeration for normal map (0.4 is 1/10th original strength)",
    )

    # Texture channel toggles
    p.add_argument(
        "--normal",
        dest="normal",
        action="store_true",
        default=True,
        help="Generate normal maps ({index}_earth_normal_{ma}.jpg)",
    )
    p.add_argument(
        "--no-normal",
        dest="normal",
        action="store_false",
        help="Skip normal map generation",
    )
    p.add_argument(
        "--roughness",
        dest="roughness",
        action="store_true",
        default=True,
        help="Generate roughness maps ({index}_earth_rough_{ma}.jpg)",
    )
    p.add_argument(
        "--no-roughness",
        dest="roughness",
        action="store_false",
        help="Skip roughness map generation",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching frames and output paths without rendering",
    )

    args = p.parse_args()

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

    # Parse index and Ma for all discovered files
    indexed_files: list[tuple[int, int, Path]] = []
    for f in raw_files:
        try:
            idx, ma = parse_paleodem_filename(f)
            indexed_files.append((idx, ma, f))
        except ValueError as err:
            print(f"Skipping {f.name}: {err}")

    indexed_files.sort(key=lambda x: x[1])  # sort by Ma (0 -> 540)

    # Filter according to --frame argument
    target_files = parse_frame_selector(args.frame, indexed_files)

    ext = args.format.lower()
    out_width, out_height = parse_resolution(args.res, args.width, args.height)
    is_downscaled = (out_width, out_height) != (7200, 3600)
    res_label = f"{out_width}x{out_height}" + (" (Lanczos downscaled)" if is_downscaled else " (Full source 7.2k)")

    print("=" * 72)
    print("Paleo Earth — PaleoDEM Texture Generator")
    print("=" * 72)
    print(f"  Input:         {args.input} ({len(target_files)} / {len(indexed_files)} frames selected)")
    print(f"  Output Dir:    {args.outdir}/")
    print(f"  Resolution:    {res_label} ({args.depth}-bit {ext.upper()})")
    print(f"  Color Ramps:   Modern (0-435 Ma) | 440 Ma Transition | Barren (445-540 Ma)")
    print(f"  Normal Map:    {'Enabled (nzfactor=' + str(args.nzfactor) + ')' if args.normal else 'Disabled'}")
    print(f"  Roughness Map: {'Enabled' if args.roughness else 'Disabled'}")
    print("=" * 72)

    if args.dry_run:
        print("\n[DRY RUN] Would process the following frames:")
        for idx, ma, f in target_files:
            diff_out = args.outdir / f"{idx}_earth_diffuse_{ma}.{ext}"
            norm_out = args.outdir / f"{idx}_earth_normal_{ma}.{ext}" if args.normal else "off"
            rgh_out  = args.outdir / f"{idx}_earth_rough_{ma}.{ext}" if args.roughness else "off"
            print(f"  [{idx:3d}] {ma:3d} Ma: {f.name} -> {diff_out.name} | normal: {norm_out.name if args.normal else 'off'} | rough: {rgh_out.name if args.roughness else 'off'}")
        return

    t_start = time.time()
    for count, (idx, ma, f) in enumerate(target_files, 1):
        t0 = time.time()
        print(f"\n[{count}/{len(target_files)}] Processing Frame {idx}: {ma} Ma ({f.name})")

        grid, lat_arr = load_dem(f)
        regime = "Modern (Vegetated)" if ma <= 435 else ("Transition (Coastal Green)" if ma == 440 else "Barren (Pre-Plant)")
        print(f"  Elevation: {grid.min():.0f}m .. {grid.max():.0f}m | Regime: {regime}")

        # 1. Diffuse Colorization & Hillshade
        col = colorize_dem(grid, ma)
        col = apply_hillshade(
            col, grid,
            strength=args.shade,
            z_factor=args.zfactor,
            altitude=args.altitude,
            azimuth=args.azimuth,
            lat_array=lat_arr,
        )
        out_diffuse = args.outdir / f"{idx}_earth_diffuse_{ma}.{ext}"
        save_image(col, out_diffuse, out_width, out_height, fmt=ext, quality=args.quality, mode="RGB", depth=args.depth)
        print(f"  -> Diffuse:   {out_diffuse} ({os.path.getsize(out_diffuse) / 1024:.1f} KB)")

        # 2. Normal Map (if enabled)
        if args.normal:
            nrm = make_normal_map(grid, z_factor=args.nzfactor, lat_array=lat_arr)
            out_normal = args.outdir / f"{idx}_earth_normal_{ma}.{ext}"
            save_image(nrm, out_normal, out_width, out_height, fmt=ext, quality=args.quality, mode="RGB", depth=args.depth)
            print(f"  -> Normal:    {out_normal} ({os.path.getsize(out_normal) / 1024:.1f} KB)")

        # 3. Roughness Map (if enabled)
        if args.roughness:
            rgh = make_roughness_map(grid)
            out_rough = args.outdir / f"{idx}_earth_rough_{ma}.{ext}"
            save_image(rgh, out_rough, out_width, out_height, fmt=ext, quality=args.quality, mode="L", depth=args.depth)
            print(f"  -> Roughness: {out_rough} ({os.path.getsize(out_rough) / 1024:.1f} KB)")

        dt = time.time() - t0
        print(f"  Completed in {dt:.2f}s")

    total_time = time.time() - t_start
    print("\n" + "=" * 72)
    print(f"Batch completed! Processed {len(target_files)} frame(s) in {total_time:.1f}s ({total_time / len(target_files):.2f}s per frame)")
    print("=" * 72)


if __name__ == "__main__":
    main()