"""Radiation and brand-transport kernels."""

from __future__ import annotations

import math

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════
# Radiation kernel
# ═══════════════════════════════════════════════════════════════════════════

def _angle_deg(dx: int, dy: int) -> float:
    """Source-to-target angle in degrees, matching the wind-direction filter.

    ``dx``, ``dy`` are integer cell offsets.  The returned angle lies in
    the range used by the wind-direction cutoff (``wd - 90 .. wd + 90``).
    For the (0, 0) cell a sentinel of ``-9999`` is returned so the
    caller can skip it.
    """
    if dx == 0 and dy == 0:
        return -9999.0

    if dx < 0:
        ac = 180.0
    elif dy <= 0:
        ac = 0.0
    else:
        ac = 360.0

    if dx != 0:
        angle = -math.degrees(math.atan(float(dy) / float(dx)))
    else:
        if dy > 0:
            angle = -90.0
        elif dy < 0:
            angle = 90.0
        else:
            angle = 0.0

    return angle + ac


def radiation_kernel(
    source_rows: np.ndarray,
    source_cols: np.ndarray,
    fire_vals: np.ndarray,
    wind_dirs: np.ndarray,
    rows: int,
    cols: int,
    grid_size: float,
    radtotal: np.ndarray,
    tmpr: np.ndarray,
    rad_rf: float,
    aes: float,
    emissivity: float,
    sconst: float,
) -> np.ndarray:
    """Accumulate Stefan-Boltzmann point-source radiation onto ``radtotal``.

    For each active burning source, iterate over every cell of the grid,
    compute the angle and squared distance to that cell, apply the
    wind-direction cosine cutoff (``|angle - wind_dir| <= 90 deg``) and
    add the point-source flux

        q = (aes / (pi * r^2)) * emissivity * sconst * (T_s^4 - T_inf^4)

    When ``rad_rf != 1`` a sequential recurrence is used: before adding
    each source's contribution the whole ``radtotal`` matrix is
    multiplied by ``rad_rf``.
    """
    pi = math.pi
    ambient_T4 = 293.15 ** 4
    n_sources = source_rows.shape[0]
    if n_sources == 0:
        return radtotal

    grid_size_f = float(grid_size)

    for s in range(n_sources):
        si = int(source_rows[s])
        sj = int(source_cols[s])
        temp_idx = int(fire_vals[s])
        if temp_idx < 1 or temp_idx > tmpr.shape[0]:
            if rad_rf != 1.0:
                radtotal *= rad_rf
            continue

        temp_K = float(tmpr[temp_idx - 1]) + 273.15
        radiant = emissivity * sconst * (temp_K ** 4 - ambient_T4)

        wd = float(wind_dirs[s])
        wd_lo = wd - 90.0
        wd_hi = wd + 90.0

        if rad_rf != 1.0:
            radtotal *= rad_rf

        for ii in range(rows):
            dy = ii - si
            for jj in range(cols):
                dx = jj - sj
                if dx == 0 and dy == 0:
                    continue

                rangle = _angle_deg(dx, dy)
                if rangle < wd_lo or rangle > wd_hi:
                    continue

                r2 = (grid_size_f * float(dx)) ** 2 + (grid_size_f * float(dy)) ** 2
                if r2 == 0.0:
                    continue

                val = (aes / (pi * r2)) * radiant
                if math.isnan(val) or math.isinf(val):
                    continue

                radtotal[ii, jj] += val

    return radtotal


# ═══════════════════════════════════════════════════════════════════════════
# Brand transport kernel
# ═══════════════════════════════════════════════════════════════════════════

def brand_transport_kernel(
    source_rows: np.ndarray,
    source_cols: np.ndarray,
    brand_counts: np.ndarray,
    rows: int,
    cols: int,
    grid_size: float,
    wind_s_2d: np.ndarray,
    wind_d_2d: np.ndarray,
    fb_wind_coef: float,
    fb_wind_sd: float,
    fb_wind_sd_transverse: float,
    rng: np.random.RandomState,
) -> np.ndarray:
    """Transport firebrands from every active source and tally landings.

    For each active source cell, draw ``nb`` brands, apply a Himoto
    lognormal forward displacement and a Gaussian lateral displacement,
    rotate by the local wind direction, round to the grid, and
    accumulate deposits.  Every non-zero landing cell is returned; any
    brand-count thresholding is applied by the caller.

    Returns an ``(N, 2) int64`` array whose columns are the flat
    linear index of the landing cell and the number of brands that
    landed there.
    """
    deg2rad = math.pi / 180.0
    grid_size_f = float(grid_size)

    total_counts = np.zeros(rows * cols, dtype=np.int64)

    for s in range(source_rows.shape[0]):
        si = int(source_rows[s])
        sj = int(source_cols[s])
        nb = int(brand_counts[s])
        if nb <= 0:
            continue

        ws = float(wind_s_2d[si, sj])
        wdeg = float(wind_d_2d[si, sj])
        wd_sin = math.sin(wdeg * deg2rad)
        wd_cos = math.cos(wdeg * deg2rad)
        mu_ln = math.log(fb_wind_coef * ws) if ws > 0 else -30.0

        for _ in range(nb):
            dforward = math.exp(mu_ln + fb_wind_sd * rng.randn())
            dlateral = fb_wind_sd_transverse * rng.randn()

            dispy = -dforward * wd_sin + dlateral * wd_cos
            dispx = dforward * wd_cos + dlateral * wd_sin

            s_dispy = 1.0 if dispy > 0 else (-1.0 if dispy < 0 else 0.0)
            s_dispx = 1.0 if dispx > 0 else (-1.0 if dispx < 0 else 0.0)
            ynum = int(dispy / grid_size_f + s_dispy)
            xnum = int(dispx / grid_size_f + s_dispx)

            dy = ynum + si
            dx = xnum + sj
            if dy < 0 or dy >= rows or dx < 0 or dx >= cols:
                continue

            total_counts[dy * cols + dx] += 1

    nz = np.flatnonzero(total_counts)
    if nz.size == 0:
        return np.empty((0, 2), dtype=np.int64)

    out = np.empty((nz.size, 2), dtype=np.int64)
    out[:, 0] = nz
    out[:, 1] = total_counts[nz]
    return out
