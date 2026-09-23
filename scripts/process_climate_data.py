#!/usr/bin/env python3
"""
process_climate_data.py
=======================
Processes raw paleoclimate datasets into production JSON data for Paleo Earth:
  1. Oxygen (%): Mills et al. (2023) AREPS median O2 curve (1 Ma resolution).
  2. Temperature (°C): Scotese et al. (2021/2023) Phanerozoic GMST via
     cosine-of-latitude area-weighted integration of 181x361 global temperature grids.
  3. CO2 (ppm): Broad scientific consensus composite (Foster et al. 2017 Nature Comms,
     CenCO2PIP 2023 Science, GEOCARB III / Berner).

Outputs:
  - data/keyframes.json: updates climateData for all 47 keyframes
  - data/climate.json: continuous 0–540 Ma climate series at 1 Ma resolution
"""

import os
import glob
import json
import math
import zipfile
import xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "climate_data_raw")
TEMP_DIR = os.path.join(RAW_DIR, "Temperature, gmst_scotese02a_v21321_csv-grid")
O2_FILE = os.path.join(RAW_DIR, "Oxygen, Mills_etal_2023_AREPS_O2", "Mills_etal_2023_AREPS_O2.xlsx")
KEYFRAMES_FILE = os.path.join(BASE_DIR, "data", "keyframes.json")
CLIMATE_FILE = os.path.join(BASE_DIR, "data", "climate.json")


# ─── 1. Calculate Area-Weighted Global Mean Surface Temperature (GMST) ────────
def process_temperatures():
    print("Processing Scotese paleotemperature grids...")
    files = sorted(glob.glob(os.path.join(TEMP_DIR, "*_temp.csv")))
    if not files:
        raise FileNotFoundError(f"No temp CSV files found in {TEMP_DIR}")

    # Area weights for 181 latitude rows (+90 to -90 degrees)
    # Surface area of 1-degree band at latitude phi is proportional to cos(phi)
    lat_weights = [math.cos(math.radians(90.0 - r)) for r in range(181)]
    sum_weights = sum(lat_weights)

    temp_by_ma = {}
    for f in files:
        ma = int(os.path.basename(f).split("_")[0])
        with open(f, "r", encoding="utf-8") as fp:
            grid = [[float(val) for val in line.strip().split(",")] for line in fp if line.strip()]

        if len(grid) != 181:
            print(f"Warning: {f} has {len(grid)} rows instead of 181")

        weighted_temp_sum = sum(
            (sum(row) / len(row)) * lat_weights[r]
            for r, row in enumerate(grid)
        )
        gmst = weighted_temp_sum / sum_weights
        temp_by_ma[ma] = round(gmst, 2)

    print(f"Calculated GMST for {len(temp_by_ma)} discrete time slices.")

    # Fill in any missing 1 Ma intervals between 0 and 540 by linear interpolation
    full_temp = {}
    known_mas = sorted(temp_by_ma.keys())
    for ma in range(541):
        if ma in temp_by_ma:
            full_temp[ma] = temp_by_ma[ma]
        else:
            # Find surrounding known points
            prev_ma = max(k for k in known_mas if k < ma)
            next_ma = min(k for k in known_mas if k > ma)
            frac = (ma - prev_ma) / (next_ma - prev_ma)
            interpolated = temp_by_ma[prev_ma] + frac * (temp_by_ma[next_ma] - temp_by_ma[prev_ma])
            full_temp[ma] = round(interpolated, 2)

    return full_temp, temp_by_ma


# ─── 2. Extract Oxygen Curve (Mills et al. 2023) ──────────────────────────────
def process_oxygen():
    print("Processing Mills et al. (2023) O2 dataset...")
    if not os.path.exists(O2_FILE):
        raise FileNotFoundError(f"Oxygen Excel file not found: {O2_FILE}")

    with zipfile.ZipFile(O2_FILE, "r") as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    o2_by_ma = {}
    for row_el in sheet.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")[1:]:
        vals = [
            c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v").text
            for c in row_el.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
            if c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v") is not None
        ]
        if len(vals) >= 2:
            time_ma = abs(float(vals[0]))
            mid_val = float(vals[1])
            int_ma = int(round(time_ma))
            if 0 <= int_ma <= 540:
                o2_by_ma[int_ma] = round(mid_val, 2)

    # Ensure complete coverage 0 to 540 Ma
    full_o2 = {}
    known_mas = sorted(o2_by_ma.keys())
    for ma in range(541):
        if ma in o2_by_ma:
            full_o2[ma] = o2_by_ma[ma]
        else:
            prev_ma = max(k for k in known_mas if k < ma)
            next_ma = min(k for k in known_mas if k > ma)
            frac = (ma - prev_ma) / (next_ma - prev_ma)
            full_o2[ma] = round(o2_by_ma[prev_ma] + frac * (o2_by_ma[next_ma] - o2_by_ma[prev_ma]), 2)

    print(f"Extracted O2 for {len(full_o2)} intervals (0 to 540 Ma).")
    return full_o2


# ─── 3. Consensus CO2 Curve (Foster et al. / CenCO2PIP / GEOCARB III) ──────────
def generate_consensus_co2():
    """
    Authoritative consensus Phanerozoic atmospheric CO2 trajectory (ppm).
    Tie points derived from Foster et al. (2017 Nature Communications),
    CenCO2PIP (2023 Science) for Cenozoic, and GEOCARB III / COPSE synthesis.
    """
    co2_tie_points = [
        # (Ma, CO2 ppm)
        (0,   420),   # Modern anthropogenic (280 pre-industrial)
        (1,   220),   # Middle Pleistocene glacial cycles (180-280)
        (2,   280),   # Early Quaternary / Pleistocene onset
        (3,   380),   # Late Pliocene
        (5,   410),   # Early Pliocene
        (15,  520),   # Middle Miocene Climatic Optimum
        (20,  460),   # Early Miocene
        (25,  420),   # Late Oligocene
        (34,  600),   # Eocene-Oligocene Transition (drop to Antarctic glaciation)
        (40,  950),   # Middle Eocene
        (50,  1400),  # Early Eocene Climatic Optimum (EECO)
        (56,  2000),  # Paleocene-Eocene Thermal Maximum (PETM spike)
        (60,  850),   # Middle Paleocene
        (65,  1100),  # K-Pg Mass Extinction / Deccan Traps
        (75,  900),   # Late Cretaceous (Campanian/Maastrichtian)
        (90,  1600),  # Turonian / Cenomanian thermal high
        (100, 1850),  # Mid-Cretaceous Thermal Maximum
        (120, 1500),  # Aptian
        (130, 1400),  # Early Cretaceous (Barremian)
        (145, 1700),  # Jurassic-Cretaceous boundary
        (150, 1900),  # Late Jurassic (Morrison / Kimmeridgian)
        (165, 1800),  # Middle Jurassic
        (180, 2000),  # Early Jurassic (Toarcian Oceanic Anoxic Event spike)
        (195, 2100),  # Early Jurassic
        (201, 2600),  # Triassic-Jurassic Extinction (CAMP volcanism spike)
        (215, 1800),  # Late Triassic (Norian)
        (235, 1600),  # Middle Triassic (Carnian Pluvial Episode)
        (245, 2000),  # Early Triassic recovery
        (252, 3200),  # Permian-Triassic Extinction (Siberian Traps greenhouse spike)
        (260, 1200),  # Late Permian (Capitanian)
        (275,  750),  # Middle Permian (Roadian)
        (290,  450),  # Early Permian (Asselian)
        (300,  300),  # Late Carboniferous (Gzhelian coal forest icehouse minimum)
        (307,  350),  # Carboniferous Rainforest Collapse
        (320,  550),  # Serpukhovian / Bashkirian
        (345,  900),  # Early Carboniferous (Tournaisian)
        (360, 1100),  # Devonian-Carboniferous boundary
        (374, 1400),  # Late Devonian Kellwasser Extinction
        (390, 2200),  # Middle Devonian (forest expansion accelerating weathering)
        (410, 2900),  # Early Devonian
        (420, 3200),  # Late Silurian (Pridoli)
        (430, 3600),  # Middle Silurian (Wenlock)
        (440, 3400),  # Early Silurian (Llandovery)
        (443, 2100),  # End-Ordovician Hirnantian Glaciation minimum
        (450, 3800),  # Late Ordovician (Caradoc)
        (465, 4100),  # Middle Ordovician
        (470, 4200),  # Great Ordovician Biodiversification Event (GOBE)
        (480, 4300),  # Early Ordovician (Tremadocian)
        (495, 4500),  # Late Cambrian (Furongian)
        (510, 4600),  # Middle Cambrian (Miaolingian)
        (530, 4700),  # Early Cambrian
        (538, 4800),  # Cambrian Explosion
        (540, 4850),  # Precambrian-Cambrian boundary
    ]

    co2_by_ma = {}
    for i in range(len(co2_tie_points) - 1):
        m1, c1 = co2_tie_points[i]
        m2, c2 = co2_tie_points[i + 1]
        for m in range(m1, m2 + 1):
            frac = (m - m1) / (m2 - m1) if m2 > m1 else 0
            # Smooth cosine interpolation between tie points
            smooth_frac = 0.5 * (1.0 - math.cos(frac * math.pi))
            interpolated = c1 + smooth_frac * (c2 - c1)
            co2_by_ma[m] = int(round(interpolated))

    return co2_by_ma


# ─── 4. Build Combined Datasets & Update Keyframes ─────────────────────────────
def main():
    full_temp, raw_temp = process_temperatures()
    full_o2 = process_oxygen()
    full_co2 = generate_consensus_co2()

    # Build continuous 0-540 Ma climate dictionary
    climate_continuous = {}
    for ma in range(541):
        climate_continuous[str(ma)] = {
            "o2Percent": full_o2[ma],
            "co2Ppm":    full_co2[ma],
            "tempC":     full_temp[ma],
        }

    with open(CLIMATE_FILE, "w", encoding="utf-8") as f:
        json.dump(climate_continuous, f, indent=2)
    print(f"Saved continuous climate dataset -> {CLIMATE_FILE}")

    # Update data/keyframes.json
    with open(KEYFRAMES_FILE, "r", encoding="utf-8") as f:
        keyframes = json.load(f)

    updated_count = 0
    for kf in keyframes:
        ma = int(round(kf["ma"]))
        # Clamp to 0-540
        lookup_ma = max(0, min(540, ma))
        kf["climateData"] = {
            "o2Percent": full_o2[lookup_ma],
            "co2Ppm":    full_co2[lookup_ma],
            "tempC":     full_temp[lookup_ma],
        }
        updated_count += 1

    with open(KEYFRAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(keyframes, f, indent=2)
    print(f"Updated climateData for all {updated_count} keyframes in {KEYFRAMES_FILE}")

    # Print validation table for key eras
    print("\n" + "=" * 65)
    print(f"{'Era / Event':<26} {'Ma':>4} {'O2 (%)':>8} {'CO2 (ppm)':>10} {'Temp (°C)':>10}")
    print("=" * 65)
    test_ids = [
        "holocene", "mid_pleistocene", "late_neogene", "mid_paleogene",
        "kpg_extinction", "late_cretaceous", "mid_cretaceous", "late_jurassic",
        "permian_triassic_extinction", "late_carboniferous", "mid_devonian",
        "end_ordovician_extinction", "cambrian_explosion", "early_cambrian"
    ]
    for kf in keyframes:
        if kf["id"] in test_ids:
            cd = kf["climateData"]
            print(f"{kf['label']:<26} {kf['ma']:>4} {cd['o2Percent']:>7.1f}% {cd['co2Ppm']:>9} {cd['tempC']:>9.1f}°")
    print("=" * 65)


if __name__ == "__main__":
    main()
