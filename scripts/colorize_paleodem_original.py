"""
Colorize Scotese & Wright PaleoDEMs (netCDF or CSV) to equirectangular PNGs.
Generates up to three texture types per file:
  - Diffuse  (colour map, always generated)
  - Normal   (tangent-space, Three.js/OpenGL convention, --no-normal to skip)
  - Roughness (grayscale, --no-roughness to skip)

Install dependencies:
    python -m pip install numpy pillow netCDF4 imageio

Basic usage (single file, all three maps, 16-bit output):
    python scripts/colorize_paleodem.py paleodems/Map01_PALEOMAP_6min_Holocene_0Ma.nc

Batch (whole folder):
    python scripts/colorize_paleodem.py paleodems/ --outdir textures_temp/

8-bit output for final WebGL textures:
    python scripts/colorize_paleodem.py paleodems/ --outdir textures/ --depth 8

Diffuse hillshade knobs:
    --shade 0.10     :: 0 = off, 1 = full overlay  (default 0.10)
    --zfactor 6.0    :: relief exaggeration for hillshade  (default 6.0)
    --azimuth 315    :: light direction, 315 = NW  (default)
    --altitude 45    :: sun elevation in degrees  (default 45)

Normal map knob:
    --nzfactor 4.0   :: relief exaggeration baked into the normal map (default 4.0)
                        Lower = flatter normals, gentler in-engine lighting.

Output size:
    --width 7200 --height 3600   (default; full source resolution)
    --width 4096 --height 2048   (good WebGL balance)
    --width 2048 --height 1024   (lightweight WebGL)

Output files (example for 0Ma, outdir = textures_temp/, 16-bit):
    textures_temp/earth_0Ma_diffuse.png   (RGB  16-bit)
    textures_temp/earth_0Ma_normal.png    (RGB  16-bit)
    textures_temp/earth_0Ma_rough.png     (Gray 16-bit)

Three.js usage (8-bit finals):
    const mat = new THREE.MeshStandardMaterial({
        map:          new THREE.TextureLoader().load('textures/earth_0Ma_diffuse.png'),
        normalMap:    new THREE.TextureLoader().load('textures/earth_0Ma_normal.png'),
        normalMapType: THREE.TangentSpaceNormalMap,
        normalScale:  new THREE.Vector2(1, 1),   // tune in-engine
        roughnessMap: new THREE.TextureLoader().load('textures/earth_0Ma_rough.png'),
        roughness:    1.0,
        metalness:    0.0,
    })
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Color ramp  (elevation in metres → float RGB [0, 1])
# ---------------------------------------------------------------------------
# Ocean: deep navy → lighter blue only in very shallow water.
# Underwater features collapse to the same deep navy (no ridges visible).
# Land: coastal green → lowland → tan interior → upland brown → high grey.
# ---------------------------------------------------------------------------
RAMP: list[tuple[float, tuple[float, float, float]]] = [
    (-11000, (0.020, 0.071, 0.176)),   # abyssal / deep ocean (flat)
    (  -200, (0.020, 0.071, 0.176)),   # deep ocean
    (   -80, (0.047, 0.188, 0.345)),   # outer shelf
    (   -20, (0.110, 0.314, 0.471)),   # inner shelf / nearshore
    (    -1, (0.149, 0.412, 0.580)),   # surf zone
    (     0, (0.149, 0.412, 0.580)),   # sea level (prevents green fringe)
    (   0.5, (0.176, 0.373, 0.216)),   # low coastal land
    (   150, (0.255, 0.451, 0.176)),   # lowland plains / jungle
    (   500, (0.373, 0.451, 0.196)),   # mid elevation
    (  1000, (0.510, 0.424, 0.227)),   # upland / savanna
    (  2000, (0.580, 0.424, 0.267)),   # highland brown
    (  3500, (0.635, 0.529, 0.392)),   # high mountains
    (  5500, (0.753, 0.714, 0.635)),   # very high / plateau
    (  8900, (0.855, 0.843, 0.824)),   # summit ice-free rock
]

# Clamp unrealistic spikes (0Ma file has a ~10 500 m artefact).
ELEV_MAX = 8900.0


# ---------------------------------------------------------------------------
# Roughness lookup (elevation in metres → roughness 0.0–1.0)
# ---------------------------------------------------------------------------
# 0.0 = perfectly smooth (mirror/specular) → deep ocean
# 1.0 = fully rough (diffuse, no specular) → bare mountain rock
# ---------------------------------------------------------------------------
ROUGH_RAMP: list[tuple[float, float]] = [
    (-11000, 0.03),   # deep ocean – very smooth
    (  -200, 0.03),   # open ocean
    (   -80, 0.12),   # outer shelf
    (   -20, 0.20),   # nearshore
    (     0, 0.20),
    (   0.5, 0.62),   # coastal lowland
    (   200, 0.72),   # plains
    (   800, 0.80),   # upland
    (  2000, 0.85),   # mountains
    (  4000, 0.78),   # very high – ice begins
    (  6000, 0.45),   # heavy snow / glacier – more reflective
    (  8900, 0.30),   # summit snowfields
]


# ---------------------------------------------------------------------------
# Generic ramp interpolation  (returns float32)
# ---------------------------------------------------------------------------

def _lerp_ramp(
    z: np.ndarray,
    stops_z: np.ndarray,
    stops_v: np.ndarray,
) -> np.ndarray:
    """
    Vectorised linear interpolation through an arbitrary ramp.
    stops_v shape: (N,) for scalar output, (N, C) for vector output.
    Returns float32 array with last axis matching stops_v.
    """
    z = np.clip(z, stops_z[0], stops_z[-1])
    idx = np.searchsorted(stops_z, z, side="right") - 1
    idx = np.clip(idx, 0, len(stops_z) - 2)
    z0 = stops_z[idx]
    z1 = stops_z[idx + 1]
    t = np.where(z1 > z0, (z - z0) / (z1 - z0), 0.0)
    if stops_v.ndim == 2:
        t = t[..., None]
    return (stops_v[idx] * (1 - t) + stops_v[idx + 1] * t).astype(np.float32)


def lerp_color(z: np.ndarray) -> np.ndarray:
    """Colour ramp interpolation. Returns float32 (H, W, 3) in [0, 1]."""
    stops_z = np.array([s[0] for s in RAMP], dtype=np.float32)
    stops_c = np.array([s[1] for s in RAMP], dtype=np.float32)
    return _lerp_ramp(z.astype(np.float32), stops_z, stops_c)


def lerp_roughness(z: np.ndarray) -> np.ndarray:
    """Roughness ramp interpolation. Returns float32 (H, W) in [0, 1]."""
    stops_z = np.array([r[0] for r in ROUGH_RAMP], dtype=np.float32)
    stops_v = np.array([r[1] for r in ROUGH_RAMP], dtype=np.float32)
    return _lerp_ramp(z.astype(np.float32), stops_z, stops_v)


# ---------------------------------------------------------------------------
# Shared gradient helper (latitude-corrected)
# ---------------------------------------------------------------------------

def _gradients(
    grid: np.ndarray,
    lat_array: np.ndarray | None,
    z_factor: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (dx_east, dy_north) gradients scaled by z_factor, with
    latitude correction on the east-west component.

    grid     : (H, W) float32, north-up, metres
    dy_north : positive when terrain rises going north
    dx_east  : positive when terrain rises going east
    """
    g = grid.astype(np.float32) * z_factor
    # np.gradient axis 0 → rows → southward; axis 1 → columns → eastward
    dy_south, dx_east = np.gradient(g)
    dy_north = -dy_south   # flip: positive = uphill northward

    if lat_array is not None:
        cos_lat = np.cos(np.radians(lat_array))[:, None]
        cos_lat = np.clip(cos_lat, 0.01, 1.0)
        dx_east = dx_east / cos_lat

    return dx_east.astype(np.float32), dy_north.astype(np.float32)


# ---------------------------------------------------------------------------
# Diffuse: hillshading
# ---------------------------------------------------------------------------

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
    Inputs and output are float32 (H, W, 3) in [0, 1].
    Ocean remains flat; shadows have a 15% ambient floor.
    """
    if strength <= 0:
        return colour

    shade = hillshade(grid, altitude, azimuth, z_factor, lat_array)

    # Ambient fill: shadows bottom out at 15%.
    shade = 0.15 + 0.85 * shade

    s = shade[..., None]   # broadcast over colour channels

    # Overlay blend: more saturated than multiply.
    overlay = np.where(
        colour < 0.5,
        2.0 * colour * s,
        1.0 - 2.0 * (1.0 - colour) * (1.0 - s),
    )

    mixed = (1.0 - strength) * colour + strength * overlay

    # Ocean: shading disabled (keeps sea perfectly flat).
    land   = (grid >= 0)[..., None]
    result = np.where(land, mixed, colour)

    return np.clip(result, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Normal map
# ---------------------------------------------------------------------------

def make_normal_map(
    grid: np.ndarray,
    z_factor: float,
    lat_array: np.ndarray | None = None,
) -> np.ndarray:
    """
    Tangent-space normal map, OpenGL / Three.js convention.

    Encoding:  value = (component * 0.5 + 0.5)
      R = X  (0.5 = neutral, >0.5 = east-facing slope)
      G = Y  (0.5 = neutral, >0.5 = north-facing slope)
      B = Z  (always >= 0.5; flat surface → 1.0)

    Flat surface encodes as (0.5, 0.5, 1.0) → (128, 128, 255) in 8-bit.
    Ocean is forced to perfectly flat (0.5, 0.5, 1.0).

    Returns float32 (H, W, 3) in [0, 1].
    """
    dx_east, dy_north = _gradients(grid, lat_array, z_factor)

    # N = normalize(-dx, -dy, 1)
    nx = -dx_east
    ny = -dy_north
    nz = np.ones_like(nx)

    mag = np.maximum(np.sqrt(nx ** 2 + ny ** 2 + nz ** 2), 1e-8)
    nx /= mag
    ny /= mag
    nz /= mag

    # Encode: component → [0, 1]
    r = nx * 0.5 + 0.5
    g = ny * 0.5 + 0.5
    b = nz * 0.5 + 0.5

    normal = np.stack([r, g, b], axis=-1).astype(np.float32)

    # Ocean: flat normal.
    flat  = np.array([0.5, 0.5, 1.0], dtype=np.float32)
    ocean = (grid < 0)[..., None]
    normal = np.where(ocean, flat, normal)

    return np.clip(normal, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Roughness map
# ---------------------------------------------------------------------------

def make_roughness_map(grid: np.ndarray) -> np.ndarray:
    """
    Grayscale roughness map derived from elevation.
    Returns float32 (H, W) in [0, 1].

    0.0 = perfectly smooth (specular) → deep ocean
    1.0 = fully rough (diffuse)       → bare rock / mountains

    Three.js: set material.roughness = 1.0 so roughnessMap drives
    the full 0-1 range without an additional global scalar.
    """
    return np.clip(lerp_roughness(grid), 0.0, 1.0)


# ---------------------------------------------------------------------------
# Image saving  (8-bit via Pillow, 16-bit via imageio)
# ---------------------------------------------------------------------------

def _save(
    data: np.ndarray,
    path: Path,
    depth: int,
    mode: str,
) -> None:
    """
    Save a float32 array [0, 1] as a PNG.

    depth : 8  → uint8  via Pillow (0–255   per channel)
            16 → uint16 via pypng  (0–65535 per channel)
    mode  : 'RGB' or 'L'
    """
    if depth == 8:
        arr8 = (data * 255.0).clip(0, 255).astype(np.uint8)
        Image.fromarray(arr8, mode=mode).save(path)
    else:
        # pypng writes genuine 16-bit PNG for both RGB and grayscale.
        try:
            import png  # type: ignore  (pypng)
        except ImportError:
            raise SystemExit(
                "16-bit output requires pypng.\n"
                "Install it with:  python -m pip install pypng"
            )
        arr16 = (data * 65535.0).clip(0, 65535).astype(np.uint16)
        if mode == "RGB":
            h, w, _ = arr16.shape
            # pypng expects each row as a flat sequence: R0 G0 B0 R1 G1 B1 …
            rows = arr16.reshape(h, w * 3).tolist()
            with open(path, "wb") as fh:
                png.Writer(width=w, height=h, bitdepth=16, greyscale=False).write(fh, rows)
        else:  # 'L'
            h, w = arr16.shape
            rows = arr16.tolist()
            with open(path, "wb") as fh:
                png.Writer(width=w, height=h, bitdepth=16, greyscale=True).write(fh, rows)


# ---------------------------------------------------------------------------
# Resize helper
# ---------------------------------------------------------------------------

def _resize_float(
    arr: np.ndarray,
    width: int,
    height: int,
    mode: str,
) -> np.ndarray:
    """Resize a float32 array via Pillow LANCZOS and return float32."""
    if arr.shape[1] == width and arr.shape[0] == height:
        return arr
    if mode == "RGB":
        tmp = Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8), mode="RGB")
        tmp = tmp.resize((width, height), Image.Resampling.LANCZOS)
        return np.array(tmp, dtype=np.float32) / 255.0
    else:  # 'L'
        tmp = Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8), mode="L")
        tmp = tmp.resize((width, height), Image.Resampling.LANCZOS)
        return np.array(tmp, dtype=np.float32) / 255.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_nc(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Load a Scotese & Wright PaleoDEM netCDF.
    Returns (elevation_grid, lat_array), north-up, west-left.
    Duplicate wrap-around rows/columns are trimmed automatically.
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
            raise SystemExit(f"No 2-D variable in {path}. Variables: {list(ds.variables)}")
        elev_name = candidates[0]
        print(f"  using variable '{elev_name}'")

    arr = np.array(ds.variables[elev_name][:], dtype=np.float32)
    ds.close()

    while arr.ndim > 2:
        arr = arr[0]

    # Ensure (lat, lon): latitude axis is shorter for 2:1 grids.
    h, w = arr.shape
    if h > w and h // w == 2:
        arr = arr.T
        if lat_arr is not None:
            lat_arr = lat_arr  # already lat

    # Trim duplicate wrap-around row/column (Scotese files: 1801x3601).
    if arr.shape[0] % 2 == 1:
        arr = arr[:-1, :]
    if arr.shape[1] % 2 == 1:
        arr = arr[:, :-1]
    if lat_arr is not None and len(lat_arr) == arr.shape[0] + 1:
        lat_arr = lat_arr[:-1]

    # Ensure north-up.
    if lat_arr is not None and lat_arr[0] < lat_arr[-1]:
        arr     = np.flipud(arr)
        lat_arr = lat_arr[::-1]

    arr = np.clip(arr, -11000.0, ELEV_MAX)
    return arr, lat_arr


def load_csv(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    """Load a lon/lat/elev CSV into a north-up elevation grid."""
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
# Filename helper
# ---------------------------------------------------------------------------

def ma_from_filename(stem: str) -> str:
    """Extract age label, e.g. '...0Ma' → '0Ma'."""
    m = re.search(r"_(\d+(?:\.\d+)?)Ma", stem, re.IGNORECASE)
    return f"{m.group(1)}Ma" if m else stem


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Generate diffuse / normal / roughness textures from PaleoDEM .nc files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("input", type=Path,
                   help=".nc file, or directory of .nc files")
    p.add_argument("--outdir", type=Path, default=Path("textures_temp"),
                   help="Output directory")
    p.add_argument("--width",  type=int, default=4096)
    p.add_argument("--height", type=int, default=2048)
    p.add_argument("--depth",  type=int, default=16, choices=[8, 16],
                   help="Output bit depth. Use 16 for intermediate work, 8 for final WebGL textures.")

    # Diffuse hillshade
    p.add_argument("--shade",    type=float, default=0.10,
                   help="Hillshade overlay strength 0-1 (0 = off)")
    p.add_argument("--zfactor",  type=float, default=6.0,
                   help="Relief exaggeration for diffuse hillshade")
    p.add_argument("--altitude", type=float, default=45.0,
                   help="Sun altitude in degrees above horizon")
    p.add_argument("--azimuth",  type=float, default=315.0,
                   help="Sun azimuth in degrees (315 = NW)")

    # Normal map
    p.add_argument("--nzfactor", type=float, default=4.0,
                   help="Relief exaggeration baked into the normal map")

    # Toggles
    p.add_argument("--no-normal",    dest="normal",    action="store_false",
                   help="Skip normal map generation")
    p.add_argument("--no-roughness", dest="roughness", action="store_false",
                   help="Skip roughness map generation")
    p.set_defaults(normal=True, roughness=True)

    args = p.parse_args()

    files: list[Path]
    if args.input.is_dir():
        files = sorted([
            *args.input.glob("*.nc"),
            *args.input.glob("*.csv"),
            *args.input.glob("*.txt"),
        ])
    else:
        files = [args.input]
    if not files:
        raise SystemExit(f"No .nc/.csv files found in {args.input}")

    args.outdir.mkdir(parents=True, exist_ok=True)

    bits = args.depth
    print(f"Output: {args.width}x{args.height}  {bits}-bit  -> {args.outdir}/\n")

    for f in files:
        age = ma_from_filename(f.stem)
        print(f"[{age}]  {f.name}")

        grid, lat_arr = load_dem(f)
        print(f"  grid {grid.shape[1]}x{grid.shape[0]}  "
              f"elev {grid.min():.0f}..{grid.max():.0f} m")

        # --- Diffuse ---
        colour = lerp_color(grid)
        colour = apply_hillshade(colour, grid, args.shade, args.zfactor,
                                 args.altitude, args.azimuth, lat_array=lat_arr)
        colour = _resize_float(colour, args.width, args.height, "RGB")
        out_d  = args.outdir / f"earth_{age}_diffuse.png"
        _save(colour, out_d, bits, "RGB")
        print(f"  diffuse   -> {out_d}")

        # --- Normal map ---
        if args.normal:
            nrm = make_normal_map(grid, args.nzfactor, lat_array=lat_arr)
            nrm = _resize_float(nrm, args.width, args.height, "RGB")
            out_n = args.outdir / f"earth_{age}_normal.png"
            _save(nrm, out_n, bits, "RGB")
            print(f"  normal    -> {out_n}")

        # --- Roughness map ---
        if args.roughness:
            rgh = make_roughness_map(grid)
            rgh = _resize_float(rgh, args.width, args.height, "L")
            out_r = args.outdir / f"earth_{age}_rough.png"
            _save(rgh, out_r, bits, "L")
            print(f"  roughness -> {out_r}")

        print()


if __name__ == "__main__":
    main()