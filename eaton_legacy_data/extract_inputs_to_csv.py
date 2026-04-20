#!/usr/bin/env python3
"""
Extract SWUIFT input data from the Eaton legacy bundle into CSV files.

Requires: numpy, scipy; h5py for wind (``wind_eaton.mat`` is HDF5/v7.3).

Run from the project root using your virtual environment, e.g.::

    .venv/bin/python eaton_legacy_data/extract_inputs_to_csv.py

Output name mapping:
  fire_prog           -> wildland_fire_matrix.csv
  domains_mat         -> domain_matrix.csv
  binary_cover        -> binary_cover_landcover.csv
  homes_mat           -> homes_matrix.csv
  lati, long          -> latitude.csv, longitude.csv
  hardening_mat_rad   -> radiation_matrix.csv
  hardening_mat_spo   -> spotting_matrix.csv
  water               -> water_matrix.csv
  wind_s, wind_d      -> wind.csv (columns: timestep, row, col, wind_speed, wind_direction)

Usage:
  python extract_inputs_to_csv.py [--out-dir DIR] [--wind-max-steps N]
  Default output directory: ../eaton_sample_csv (sibling of this script)
  Use --wind-max-steps N only to limit wind rows for testing (default: all timesteps).
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import scipy.io as sio

# Optional: use project venv's h5py for wind_eaton.mat (v7.3 / HDF5)
try:
    import h5py
except ImportError:
    h5py = None


# ---------------------------------------------------------------------------
# Output names (new names) and source mapping
# ---------------------------------------------------------------------------

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.abspath(os.path.join(DATA_DIR, "..", "eaton_sample_csv"))

# 2D grids: (source_file, variable_name) -> output_csv_name
SPATIAL_2D = [
    ("fire_prog.mat", "fire_prog", "wildland_fire_matrix.csv"),           # fire progression
    ("domains_mat.mat", "domains_mat", "domain_matrix.csv"),             # domain matrix
    ("eaton_inputs_all.mat", "binary_cover", "binary_cover_landcover.csv"),
    ("eaton_inputs_all.mat", "homes_mat", "homes_matrix.csv"),
    ("eaton_inputs_all.mat", "water", "water_matrix.csv"),
    ("eaton_inputs_all.mat", "hardening_mat_rad", "radiation_matrix.csv"),
    ("eaton_inputs_all.mat", "hardening_mat_spo", "spotting_matrix.csv"),
]

# 1D from eaton: variable -> output name
SPATIAL_1D = [
    ("eaton_inputs_all.mat", "lati", "latitude.csv"),
    ("eaton_inputs_all.mat", "long", "longitude.csv"),
]


def load_mat_v5(path: str) -> dict:
    """Load a ``.mat`` v5 file."""
    return sio.loadmat(path, squeeze_me=False)


def save_2d_csv(arr: np.ndarray, out_path: str) -> None:
    """Save 2D array as CSV (no header; comma-separated)."""
    np.savetxt(out_path, arr, delimiter=",", fmt="%g")


def save_1d_csv(arr: np.ndarray, out_path: str) -> None:
    """Save 1D array as CSV (one column)."""
    a = np.asarray(arr).ravel()
    np.savetxt(out_path, a.reshape(-1, 1), delimiter=",", fmt="%g")


def extract_spatial_mat_files(out_dir: str) -> None:
    """Extract 2D and 1D variables from fire_prog, domains_mat, eaton_inputs_all."""
    os.makedirs(out_dir, exist_ok=True)
    cache: dict[str, dict] = {}

    for item in SPATIAL_2D + SPATIAL_1D:
        src_file, var_name, csv_name = item
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
        out_path = os.path.join(out_dir, csv_name)
        if arr.ndim == 2:
            save_2d_csv(arr, out_path)
        else:
            save_1d_csv(arr, out_path)
        print(f"Wrote {csv_name} ({arr.shape})")


def extract_wind(out_dir: str, wind_max_steps: int | None) -> None:
    """Extract wind speed and direction from wind_eaton.mat (HDF5) to a single wind.csv."""
    if h5py is None:
        print("Skip wind: h5py not installed.", file=sys.stderr)
        return
    path = os.path.join(DATA_DIR, "wind_eaton.mat")
    if not os.path.isfile(path):
        print(f"Skip wind: not found {path}", file=sys.stderr)
        return
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "wind.csv")
    with h5py.File(path, "r") as h:
        wind_s = h["wind_s"]
        wind_d = h["wind_d"]
        n_t = wind_s.shape[0]
        n_lim = n_t if wind_max_steps is None else min(wind_max_steps, n_t)
        n_rows, n_cols = wind_s.shape[1], wind_s.shape[2]
        # HDF5 order: (timesteps, rows, cols) or (timesteps, cols, rows); transpose so (row, col)
        with open(out_path, "w") as f:
            f.write("timestep,row,col,wind_speed,wind_direction\n")
            rows_idx, cols_idx = np.meshgrid(np.arange(n_rows), np.arange(n_cols), indexing="ij")
            rows_flat = rows_idx.ravel()
            cols_flat = cols_idx.ravel()
            for t in range(n_lim):
                ws = np.asarray(wind_s[t, :, :]).T  # (rows, cols)
                wd = np.asarray(wind_d[t, :, :]).T
                block = np.column_stack([
                    np.full_like(rows_flat, t, dtype=np.int32),
                    rows_flat,
                    cols_flat,
                    ws.ravel(),
                    wd.ravel(),
                ])
                np.savetxt(f, block, delimiter=",", fmt=["%d", "%d", "%d", "%.6g", "%.6g"])
        print(f"Wrote wind.csv (timestep,row,col,wind_speed,wind_direction) with {n_lim} timesteps, {n_rows}x{n_cols} grid")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract SWUIFT .mat inputs to CSV with new names.")
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT,
        help=f"Output directory for CSV files (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--wind-max-steps",
        type=int,
        default=None,
        metavar="N",
        help="Limit wind to first N timesteps (default: all)",
    )
    args = parser.parse_args()
    out_dir = os.path.abspath(args.out_dir)
    print(f"Output directory: {out_dir}")
    extract_spatial_mat_files(out_dir)
    extract_wind(out_dir, args.wind_max_steps)
    print("Done.")


if __name__ == "__main__":
    main()
