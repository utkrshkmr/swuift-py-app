#!/usr/bin/env python3
"""
Extract SWUIFT input data from the Eaton legacy bundle into the
per-variable ``.mat`` layout that the GUI consumes.

Requires: numpy, scipy.

Run from the project root using your virtual environment, e.g.::

    .venv/bin/python eaton_legacy_data/extract_inputs_to_mat.py

Source file -> output file mapping:

    fire_prog.mat           -> wildland_fire_matrix.mat   (var: wildland_fire_matrix)
    domains_mat.mat         -> domain_matrix.mat          (var: domains_mat)
    eaton_inputs_all.mat ->
        binary_cover        -> binary_cover_landcover.mat (var: binary_cover)
        homes_mat           -> homes_matrix.mat           (var: homes_mat)
        water               -> water_matrix.mat           (var: water)
        lati                -> latitude.mat               (var: lati)
        long                -> longitude.mat              (var: long)
        hardening_mat_rad   -> radiation_matrix.mat       (var: hardening_mat_rad)
        hardening_mat_spo   -> spotting_matrix.mat        (var: hardening_mat_spo)
    wind_eaton.mat          -> wind.mat                   (copied as-is; HDF5 v7.3)

Usage:
    python extract_inputs_to_mat.py [--out-dir DIR]
    Default output directory: ../eaton_sample_data (sibling of this script)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

import numpy as np
import scipy.io as sio


# ---------------------------------------------------------------------------
# Paths and mappings
# ---------------------------------------------------------------------------

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.abspath(os.path.join(DATA_DIR, "..", "eaton_sample_data"))

# (source_file, variable_name, output_filename, variable_name_in_output_mat)
EXTRACTIONS = [
    ("fire_prog.mat", "fire_prog", "wildland_fire_matrix.mat", "wildland_fire_matrix"),
    ("domains_mat.mat", "domains_mat", "domain_matrix.mat", "domains_mat"),
    ("eaton_inputs_all.mat", "binary_cover", "binary_cover_landcover.mat", "binary_cover"),
    ("eaton_inputs_all.mat", "homes_mat", "homes_matrix.mat", "homes_mat"),
    ("eaton_inputs_all.mat", "water", "water_matrix.mat", "water"),
    ("eaton_inputs_all.mat", "lati", "latitude.mat", "lati"),
    ("eaton_inputs_all.mat", "long", "longitude.mat", "long"),
    ("eaton_inputs_all.mat", "hardening_mat_rad", "radiation_matrix.mat", "hardening_mat_rad"),
    ("eaton_inputs_all.mat", "hardening_mat_spo", "spotting_matrix.mat", "hardening_mat_spo"),
]

WIND_SOURCE = "wind_eaton.mat"
WIND_OUTPUT = "wind.mat"


def load_mat_v5(path: str) -> dict:
    """Load a ``.mat`` v5 file."""
    return sio.loadmat(path, squeeze_me=False)


def extract_spatial_mat_files(out_dir: str) -> None:
    """Extract each required variable from the legacy bundle to its own ``.mat``."""
    os.makedirs(out_dir, exist_ok=True)
    cache: dict[str, dict] = {}

    for src_file, var_name, out_filename, mat_var_name in EXTRACTIONS:
        path = os.path.join(DATA_DIR, src_file)
        if not os.path.isfile(path):
            print(f"Skip (missing): {path}", file=sys.stderr)
            continue
        if src_file not in cache:
            cache[src_file] = load_mat_v5(path)
        data = cache[src_file]
        if var_name not in data:
            print(f"Skip (no var '{var_name}'): {path}", file=sys.stderr)
            continue
        arr = np.asarray(data[var_name], dtype=np.float64)
        if arr.ndim == 2 and arr.shape[1] == 1:
            arr = arr.ravel()
        out_path = os.path.join(out_dir, out_filename)
        sio.savemat(out_path, {mat_var_name: arr}, format="5", do_compression=False)
        print(f"Wrote {out_filename} ({arr.shape})")


def copy_wind(out_dir: str) -> None:
    """Copy the large wind time-series to the output dir (no conversion)."""
    src = os.path.join(DATA_DIR, WIND_SOURCE)
    if not os.path.isfile(src):
        print(f"Skip wind: not found {src}", file=sys.stderr)
        return
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, WIND_OUTPUT)
    shutil.copy2(src, dst)
    print(f"Copied {WIND_SOURCE} -> {WIND_OUTPUT}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the Eaton legacy bundle into per-variable .mat files."
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT,
        help=f"Output directory for .mat files (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()
    out_dir = os.path.abspath(args.out_dir)
    print(f"Output directory: {out_dir}")
    extract_spatial_mat_files(out_dir)
    copy_wind(out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
