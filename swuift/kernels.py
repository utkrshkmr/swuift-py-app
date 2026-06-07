from __future__ import annotations
import math
import os
from typing import TYPE_CHECKING
import numpy as np
if TYPE_CHECKING:
    pass
_KERNEL_BACKEND = os.environ.get('SWUIFT_APP_KERNEL_BACKEND', 'numba').strip().lower()

def kernel_backend() -> str:
    return 'numba' if _use_numba() else 'python'

def _use_numba() -> bool:
    if _KERNEL_BACKEND == 'python':
        return False
    return _NUMBA_AVAILABLE

def _angle_deg_py(dx: int, dy: int) -> float:
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
    elif dy > 0:
        angle = -90.0
    elif dy < 0:
        angle = 90.0
    else:
        angle = 0.0
    return angle + ac

def radiation_kernel_py(source_rows: np.ndarray, source_cols: np.ndarray, fire_vals: np.ndarray, wind_dirs: np.ndarray, rows: int, cols: int, grid_size: float, radtotal: np.ndarray, tmpr: np.ndarray, rad_rf: float, aes: float, emissivity: float, sconst: float) -> np.ndarray:
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
                rangle = _angle_deg_py(dx, dy)
                if rangle < wd_lo or rangle > wd_hi:
                    continue
                r2 = (grid_size_f * float(dx)) ** 2 + (grid_size_f * float(dy)) ** 2
                if r2 == 0.0:
                    continue
                val = aes / (pi * r2) * radiant
                if math.isnan(val) or math.isinf(val):
                    continue
                radtotal[ii, jj] += val
    return radtotal

def brand_transport_kernel_py(source_rows: np.ndarray, source_cols: np.ndarray, brand_counts: np.ndarray, rows: int, cols: int, grid_size: float, wind_s_2d: np.ndarray, wind_d_2d: np.ndarray, fb_wind_coef: float, fb_wind_sd: float, fb_wind_sd_transverse: float, rng: np.random.RandomState) -> np.ndarray:
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
            s_dispy = 1.0 if dispy > 0 else -1.0 if dispy < 0 else 0.0
            s_dispx = 1.0 if dispx > 0 else -1.0 if dispx < 0 else 0.0
            ynum = int(dispy / grid_size_f + s_dispy)
            xnum = int(dispx / grid_size_f + s_dispx)
            dy = ynum + si
            dx = xnum + sj
            if dy < 0 or dy >= rows or dx < 0 or (dx >= cols):
                continue
            total_counts[dy * cols + dx] += 1
    nz = np.flatnonzero(total_counts)
    if nz.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    out = np.empty((nz.size, 2), dtype=np.int64)
    out[:, 0] = nz
    out[:, 1] = total_counts[nz]
    return out

def max_brands_in_circle_py(points: np.ndarray, radius: float) -> int:
    n = points.shape[0]
    if n == 0:
        return 0
    r2 = radius * radius
    best = 0
    for i in range(n):
        xi = points[i, 0]
        yi = points[i, 1]
        cnt = 0
        for j in range(n):
            dx = points[j, 0] - xi
            dy = points[j, 1] - yi
            if dx * dx + dy * dy <= r2:
                cnt += 1
        if cnt > best:
            best = cnt
    return best
_NUMBA_AVAILABLE = False
try:
    import numba

    @numba.njit(cache=True)
    def _angle_deg_numba(dx: int, dy: int) -> float:
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
        elif dy > 0:
            angle = -90.0
        elif dy < 0:
            angle = 90.0
        else:
            angle = 0.0
        return angle + ac

    @numba.njit(cache=True)
    def radiation_kernel_numba(source_rows: np.ndarray, source_cols: np.ndarray, fire_vals: np.ndarray, wind_dirs: np.ndarray, rows: int, cols: int, grid_size: float, radtotal: np.ndarray, tmpr: np.ndarray, rad_rf: float, aes: float, emissivity: float, sconst: float) -> np.ndarray:
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
                    rangle = _angle_deg_numba(dx, dy)
                    if rangle < wd_lo or rangle > wd_hi:
                        continue
                    r2 = (grid_size_f * float(dx)) ** 2 + (grid_size_f * float(dy)) ** 2
                    if r2 == 0.0:
                        continue
                    val = aes / (pi * r2) * radiant
                    if math.isnan(val) or math.isinf(val):
                        continue
                    radtotal[ii, jj] += val
        return radtotal

    @numba.njit(cache=True)
    def brand_transport_kernel_numba(source_rows: np.ndarray, source_cols: np.ndarray, brand_counts: np.ndarray, rows: int, cols: int, grid_size: float, wind_s_2d: np.ndarray, wind_d_2d: np.ndarray, fb_wind_coef: float, fb_wind_sd: float, fb_wind_sd_transverse: float, randn_vec: np.ndarray) -> np.ndarray:
        deg2rad = math.pi / 180.0
        grid_size_f = float(grid_size)
        total_counts = np.zeros(rows * cols, dtype=np.int64)
        rand_idx = 0
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
                dforward = math.exp(mu_ln + fb_wind_sd * randn_vec[rand_idx])
                dlateral = fb_wind_sd_transverse * randn_vec[rand_idx + 1]
                rand_idx += 2
                dispy = -dforward * wd_sin + dlateral * wd_cos
                dispx = dforward * wd_cos + dlateral * wd_sin
                s_dispy = 1.0 if dispy > 0 else -1.0 if dispy < 0 else 0.0
                s_dispx = 1.0 if dispx > 0 else -1.0 if dispx < 0 else 0.0
                ynum = int(dispy / grid_size_f + s_dispy)
                xnum = int(dispx / grid_size_f + s_dispx)
                dy = ynum + si
                dx = xnum + sj
                if dy < 0 or dy >= rows or dx < 0 or (dx >= cols):
                    continue
                total_counts[dy * cols + dx] += 1
        nz_count = 0
        for k in range(rows * cols):
            if total_counts[k] != 0:
                nz_count += 1
        if nz_count == 0:
            return np.empty((0, 2), dtype=np.int64)
        out = np.empty((nz_count, 2), dtype=np.int64)
        out_idx = 0
        for k in range(rows * cols):
            if total_counts[k] != 0:
                out[out_idx, 0] = k
                out[out_idx, 1] = total_counts[k]
                out_idx += 1
        return out

    @numba.njit(cache=True)
    def max_brands_in_circle_numba(points: np.ndarray, radius: float) -> int:
        n = points.shape[0]
        if n == 0:
            return 0
        r2 = radius * radius
        best = 0
        for i in range(n):
            xi = points[i, 0]
            yi = points[i, 1]
            cnt = 0
            for j in range(n):
                dx = points[j, 0] - xi
                dy = points[j, 1] - yi
                if dx * dx + dy * dy <= r2:
                    cnt += 1
            if cnt > best:
                best = cnt
        return best
    _NUMBA_AVAILABLE = True
except ImportError:
    pass

def radiation_kernel(source_rows: np.ndarray, source_cols: np.ndarray, fire_vals: np.ndarray, wind_dirs: np.ndarray, rows: int, cols: int, grid_size: float, radtotal: np.ndarray, tmpr: np.ndarray, rad_rf: float, aes: float, emissivity: float, sconst: float) -> np.ndarray:
    if _use_numba():
        return radiation_kernel_numba(source_rows, source_cols, fire_vals, wind_dirs, rows, cols, grid_size, radtotal, tmpr, rad_rf, aes, emissivity, sconst)
    return radiation_kernel_py(source_rows, source_cols, fire_vals, wind_dirs, rows, cols, grid_size, radtotal, tmpr, rad_rf, aes, emissivity, sconst)

def brand_transport_kernel(source_rows: np.ndarray, source_cols: np.ndarray, brand_counts: np.ndarray, rows: int, cols: int, grid_size: float, wind_s_2d: np.ndarray, wind_d_2d: np.ndarray, fb_wind_coef: float, fb_wind_sd: float, fb_wind_sd_transverse: float, rng: np.random.RandomState) -> np.ndarray:
    if _use_numba():
        total_brands = int(np.sum(brand_counts))
        if total_brands <= 0:
            return np.empty((0, 2), dtype=np.int64)
        randn_vec = np.ascontiguousarray(rng.randn(total_brands * 2), dtype=np.float64)
        return brand_transport_kernel_numba(source_rows, source_cols, brand_counts, rows, cols, grid_size, wind_s_2d, wind_d_2d, fb_wind_coef, fb_wind_sd, fb_wind_sd_transverse, randn_vec)
    return brand_transport_kernel_py(source_rows, source_cols, brand_counts, rows, cols, grid_size, wind_s_2d, wind_d_2d, fb_wind_coef, fb_wind_sd, fb_wind_sd_transverse, rng)

def max_brands_in_circle(points: np.ndarray, radius: float) -> int:
    if points.size == 0:
        return 0
    pts = np.ascontiguousarray(points, dtype=np.float64)
    if _use_numba():
        return max_brands_in_circle_numba(pts, radius)
    return max_brands_in_circle_py(pts, radius)
