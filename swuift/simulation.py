"""SWUIFT simulation loop.

Runs the fire-spread model for one parameter set over a sequence of
timesteps, writing PNG frames, summary plots, and optional per-step
CSV / NPY dumps to the output directory.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import numpy as np
from tqdm import tqdm

from .config import SWUIFTConfig
from .data_loader import SWUIFTData
from .hardening import apply_hardening
from .plotting import (
    assemble_video,
    plot_pixel_ignitions,
    plot_structure_ignitions,
    save_frame_csv,
    save_snapshot,
)
from .spread import brand_gen, brand_ig, radiation_gen, radiation_ig


# ── helpers ──────────────────────────────────────────────────────────────

def _time_vector(t_start: datetime, t_end: datetime, t_step_min: float):
    dt = timedelta(minutes=t_step_min)
    times = []
    t = t_start
    while t <= t_end:
        times.append(t)
        t += dt
    return times


def _write_log(fh, msg: str):
    fh.write(msg)
    fh.flush()


def _dump_step_binary(step_dir: str, fire, ignition, radtotal, out_fire, zvector):
    """Save per-step arrays as ``.npy`` (synchronous)."""
    os.makedirs(step_dir, exist_ok=True)
    np.save(os.path.join(step_dir, "fire.npy"), fire)
    np.save(os.path.join(step_dir, "ignition.npy"), ignition)
    np.save(os.path.join(step_dir, "radtotal.npy"), radtotal)
    np.save(os.path.join(step_dir, "out_fire.npy"), out_fire)
    np.save(os.path.join(step_dir, "zvector.npy"), zvector)


def _dump_step_csv(step_dir: str, fire, ignition, radtotal, out_fire, zvector):
    """Save per-step arrays as ``.csv`` (synchronous)."""
    os.makedirs(step_dir, exist_ok=True)
    np.savetxt(os.path.join(step_dir, "fire.csv"), fire, delimiter=",")
    np.savetxt(os.path.join(step_dir, "ignition.csv"), ignition, delimiter=",")
    np.savetxt(os.path.join(step_dir, "radtotal.csv"), radtotal, delimiter=",")
    np.savetxt(os.path.join(step_dir, "out_fire.csv"), out_fire, delimiter=",")
    np.savetxt(os.path.join(step_dir, "zvector.csv"), zvector, delimiter=",")


def _ignited_home_ids(ignition: np.ndarray, homes_mat: np.ndarray) -> set:
    """Return the set of home IDs that currently contain an ignited pixel."""
    mask = (ignition == 1) & (homes_mat > 0)
    if not np.any(mask):
        return set()
    hids = np.unique(homes_mat[mask].astype(int))
    return {int(h) for h in hids if h > 0}


# ── main entry point ─────────────────────────────────────────────────────

def run_simulation(
    cfg: SWUIFTConfig,
    data: SWUIFTData,
    output_dir: str,
    dpi: int = 150,
    dpi_hires: int = 600,
    make_video: bool = True,
    dump_interval: int = 1,
    dump_csv: bool = True,
    dump_radiation_csv: bool = False,
    dump_spotting_csv: bool = False,
    phase_callback=None,
) -> None:
    """Run the SWUIFT simulation.

    ``dump_interval=1`` and ``dump_csv=True`` write a directory of CSV
    files at every time step.  Pass ``dump_interval=0`` to disable
    per-step dumps.
    """

    # ── hardening ──────────────────────────────────────────────────────
    hard = apply_hardening(
        cfg,
        data.binary_cover,
        data.homes_mat,
        data.hardening_mat_rad,
        data.hardening_mat_spo,
        data.knownig_mat,
        data.lati,
        data.long,
    )
    knownig_mat = hard.knownig_mat
    criteria_rad = hard.criteria_rad
    criteria_spo = hard.criteria_spo

    # ── zvector ────────────────────────────────────────────────────────
    n_homes = int(data.homes_mat.max())
    zvector = np.zeros((n_homes, 5))
    zvector[:, 0] = np.arange(1, n_homes + 1)

    # ── RNG for spread ────────────────────────────────────────────────
    rng = np.random.RandomState(cfg.seed_spread)

    # ── time vector & maxstep ─────────────────────────────────────────
    t_num_vec = _time_vector(cfg.t_start, cfg.t_end, cfg.t_step_min)
    if cfg.maxstep is not None:
        maxstep = min(cfg.maxstep, len(t_num_vec))
        t_num_vec = t_num_vec[:maxstep]
    else:
        maxstep = len(t_num_vec)

    fstep = cfg.fstep
    lstep = cfg.lstep

    # ── state matrices ────────────────────────────────────────────────
    rows, cols = data.rows, data.cols
    ignition = np.zeros((rows, cols))
    fire = np.zeros((rows, cols))
    radtotal = np.zeros((rows, cols))
    out_fire = np.zeros((rows, cols))

    ig_known = np.zeros(maxstep)
    ig_dev = np.zeros(maxstep)
    ig_rad = np.zeros(maxstep)
    ig_brand = np.zeros(maxstep)
    ig_total = np.zeros(maxstep)

    house_ig_known = np.zeros(maxstep)
    house_ig_rad = np.zeros(maxstep)
    house_ig_brand = np.zeros(maxstep)
    house_ig_total = np.zeros(maxstep)

    brands_on_structures_cumsum = 0

    # ── output dirs ────────────────────────────────────────────────────
    frames_dir = os.path.join(output_dir, "frames")
    frame_csvs_dir = os.path.join(output_dir, "frame_csvs")
    timesteps_dir = os.path.join(output_dir, "timesteps")
    radiation_csv_dir = os.path.join(output_dir, "radiation_csv")
    spotting_csv_dir = os.path.join(output_dir, "spotting_csv")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(frame_csvs_dir, exist_ok=True)
    if dump_interval > 0:
        os.makedirs(timesteps_dir, exist_ok=True)
    if dump_radiation_csv:
        os.makedirs(radiation_csv_dir, exist_ok=True)
    if dump_spotting_csv:
        os.makedirs(spotting_csv_dir, exist_ok=True)

    # ── log ───────────────────────────────────────────────────────────
    log_path = os.path.join(output_dir, "run_log.txt")
    fh = open(log_path, "w")
    wall_start = time.time()
    _write_log(fh, f"Spread loop begins at: {datetime.now()}\n")
    _write_log(fh, "################################\n")
    _write_log(fh, f"grid cell size = {cfg.grid_size} m\n")
    _write_log(fh, f"start time = {cfg.t_start.strftime('%Y/%m/%d %H:%M')}\n")
    _write_log(fh, f"end time = {cfg.t_end.strftime('%Y/%m/%d %H:%M')}\n")
    _write_log(fh, f"time step = {cfg.t_step_min} minutes\n")
    _write_log(fh, f"Fully developed phase between steps {fstep} and {lstep}\n")
    _write_log(fh, f"threshold for ignition due to radiation = {cfg.rad_energy_ig}\n")
    _write_log(fh, f"emissivity receiving = {cfg.er}\n")
    _write_log(fh, f"emissivity emitting = {cfg.ee}\n")
    _write_log(fh, f"area for radiating surface = {cfg.aes} m2\n")
    _write_log(fh, f"radiation reduction factor = {cfg.rad_rf}\n")
    _write_log(fh, f"mass of each firebrand = {cfg.fb_mass} g\n")
    _write_log(fh, f"brands for Santamaria condition = {cfg.fb_str_ig}\n")
    _write_log(fh, f"brands for igniting vegetation = {cfg.fb_veg_ig}\n")
    _write_log(fh, f"brands generated from vegetation = {cfg.fb_veg_gen}\n")
    _write_log(fh, "################################\n\n")

    # ── main loop ─────────────────────────────────────────────────────
    for tstep in tqdm(range(1, maxstep + 1), desc="Time steps", unit="step"):
        sim_time = t_num_vec[tstep - 1]
        _write_log(fh, f"Step {tstep}: {sim_time.strftime('%Y/%m/%d %H:%M')}\n")

        # 1. increment burning stages
        fire[fire > 0] += 1

        # 2. known ignitions from wildfire (only outside urban domain)
        ignition[(knownig_mat == tstep) & (data.domains_mat >= 8)] = 1

        ig_known_mask = (
            (data.homes_mat > 0)
            & (knownig_mat == tstep)
            & (data.domains_mat >= 8)
        )
        ig_known[tstep - 1] = ignition[ig_known_mask].sum()

        # house_ig_known: how many of these homes were NOT yet ignited
        # before this step?  We have to compute "ignited homes before
        # this step"; rebuild from scratch.
        ignited_homes_before = _ignited_home_ids(ignition, data.homes_mat)
        if np.any(ig_known_mask):
            new_known_ids = set(
                int(h) for h in data.homes_mat[ig_known_mask].astype(int) if h > 0
            )
            house_ig_known[tstep - 1] = len(new_known_ids - ignited_homes_before)

        str_pixels_ignited = int(ignition[data.homes_mat > 0].sum())
        ignited_homes_now = _ignited_home_ids(ignition, data.homes_mat)
        house_ig_tmp = len(ignited_homes_now)

        _write_log(fh, "- Known ignitions registered.\n")
        _write_log(fh, f"    Structure pixels ignited so far: {str_pixels_ignited}\n")
        _write_log(fh, f"    Structures ignited so far: {house_ig_tmp}\n")

        # 3. full-house propagation — pixels of each active home are
        #    found on demand with np.where.
        _write_log(fh, "- Propagating full-house ignition.\n")
        ind_mask = (ignition == 1) & (data.binary_cover > 0)
        active_hids = np.unique(data.homes_mat[ind_mask].astype(int))
        for hid in active_hids:
            hid_i = int(hid)
            if hid_i <= 0:
                continue
            hr, hc = np.where(data.homes_mat == hid_i)
            if hr.size == 0:
                continue
            if np.any(fire[hr, hc] >= fstep):
                ignition[hr, hc] = 1

        new_str_pix = int(ignition[data.homes_mat > 0].sum())
        ig_dev[tstep - 1] = new_str_pix - str_pixels_ignited
        str_pixels_ignited = new_str_pix
        _write_log(fh, f"    Structure pixels ignited so far: {str_pixels_ignited}\n")

        # 4. wind slice (clamp index)
        wind_ix = min(tstep - 1, data.wind.n_timesteps - 1)
        wind_s_2d, wind_d_2d = data.wind.get_slice(wind_ix)

        # 5. brand generation & transport
        brands, brand_gen_mat = brand_gen(
            cfg, rows, cols,
            data.binary_cover, fire,
            fstep, lstep,
            wind_s_2d, wind_d_2d,
            cfg.fb_veg_gen, cfg.fb_str_ig,
            cfg.veg_included, tstep,
            data.domains_mat, rng,
        )
        _write_log(fh, "- Brands generated and transported.\n")

        # 5c. per-frame spotting CSV (synchronous)
        if dump_spotting_csv:
            _spo_path = os.path.join(spotting_csv_dir, f"{tstep:04d}.csv")
            np.savetxt(_spo_path, brand_gen_mat, delimiter=",", fmt="%.6g")

        # 5b. ember statistics on structures
        step_brands_on_structures = 0
        if brands.shape[1] > 0:
            brand_indices = brands[0, :].astype(np.intp)
            brand_counts = brands[1, :].astype(np.int64)
            total_counts = np.zeros(rows * cols, dtype=np.int64)
            for k in range(brand_indices.size):
                total_counts[brand_indices[k]] += int(brand_counts[k])
            total_counts_2d = total_counts.reshape(rows, cols)
            step_brands_on_structures = int(
                total_counts_2d[data.binary_cover > 0].sum()
            )
        brands_on_structures_cumsum += step_brands_on_structures
        _write_log(
            fh,
            f"    Brands on structures this step: {step_brands_on_structures}\n",
        )
        _write_log(
            fh,
            f"    Brands on structures cumulative: {brands_on_structures_cumsum}\n",
        )

        # 6. radiation
        radtotal = radiation_gen(
            cfg, rows, cols,
            data.binary_cover, fire, cfg.tmpr, radtotal,
            fstep, lstep, cfg.rad_rf,
            wind_d_2d, cfg.aes, cfg.ee, cfg.er, cfg.sconst,
        )
        _write_log(fh, "- Radiation fluxes evaluated.\n")

        # 6b. per-frame radiation CSV (synchronous)
        if dump_radiation_csv:
            _rad_path = os.path.join(radiation_csv_dir, f"{tstep:04d}.csv")
            np.savetxt(_rad_path, radtotal, delimiter=",", fmt="%.6g")

        # 7. radiation ignition
        ig_before_rad = str_pixels_ignited
        homes_before_rad_set = _ignited_home_ids(ignition, data.homes_mat)
        homes_before_rad = len(homes_before_rad_set)
        ignition = radiation_ig(
            ignition, data.binary_cover, radtotal,
            cfg.rad_energy_ig, criteria_rad, cfg.limrad,
        )

        # zvector update for radiation-caused ignitions
        _update_zvector(
            ignition=ignition,
            homes_mat=data.homes_mat,
            binary_cover=data.binary_cover,
            zvector=zvector,
            tstep=tstep,
            previously_ignited=homes_before_rad_set,
            cause_column=2,   # radiation
        )

        str_pixels_ignited = int(ignition[data.homes_mat > 0].sum())
        ignited_homes_now = _ignited_home_ids(ignition, data.homes_mat)
        ig_rad[tstep - 1] = str_pixels_ignited - ig_before_rad
        house_ig_rad[tstep - 1] = len(ignited_homes_now) - homes_before_rad
        _write_log(fh, "- Radiation ignitions registered.\n")
        _write_log(fh, f"    Structure pixels ignited so far: {str_pixels_ignited}\n")
        _write_log(fh, f"    Structures ignited so far: {len(ignited_homes_now)}\n")

        # 8. brand ignition
        ig_before_brand = str_pixels_ignited
        homes_before_brand_set = _ignited_home_ids(ignition, data.homes_mat)
        homes_before_brand = len(homes_before_brand_set)
        brand_log: list[str] = []
        ignition = brand_ig(
            cfg, rows, cols,
            data.binary_cover, ignition,
            brand_log, brands,
            cfg.fb_str_ig, cfg.fb_veg_ig,
            cfg.fb_dist_mu, cfg.fb_dist_sd,
            cfg.veg_included, data.domains_mat,
            criteria_spo, cfg.limspo, rng,
        )
        for line in brand_log:
            _write_log(fh, f"    {line}\n")

        _update_zvector(
            ignition=ignition,
            homes_mat=data.homes_mat,
            binary_cover=data.binary_cover,
            zvector=zvector,
            tstep=tstep,
            previously_ignited=homes_before_brand_set,
            cause_column=3,   # branding
        )

        str_pixels_ignited = int(ignition[data.homes_mat > 0].sum())
        ignited_homes_now = _ignited_home_ids(ignition, data.homes_mat)
        ig_brand[tstep - 1] = str_pixels_ignited - ig_before_brand
        house_ig_brand[tstep - 1] = len(ignited_homes_now) - homes_before_brand
        _write_log(fh, "- Branding ignitions registered.\n")
        _write_log(fh, f"    Structure pixels ignited so far: {str_pixels_ignited}\n")
        _write_log(fh, f"    Structures ignited so far: {len(ignited_homes_now)}\n")
        _write_log(fh, f"    Wall time: {datetime.now()}\n")

        # 9. register new fires
        new_fire_mask = (fire == 0) & (ignition == 1)
        fire[new_fire_mask] = 0.11

        ig_total[tstep - 1] = ignition[data.homes_mat > 0].sum()
        house_ig_total[tstep - 1] = len(ignited_homes_now)

        # 10. track earliest fire time
        newly_on_fire = (fire != 0) & (out_fire == 0)
        out_fire[newly_on_fire] = (tstep - 1) * cfg.t_step_min

        # 11. save frame (synchronous)
        save_snapshot(
            rows, cols,
            data.binary_cover, ignition.copy(), fire.copy(),
            data.long, data.lati,
            sim_time, tstep,
            fstep, lstep,
            data.water,
            frames_dir,
            dpi_hires,
        )

        # 11b. per-frame CSV (synchronous)
        save_frame_csv(
            rows, cols,
            data.binary_cover, ignition.copy(), fire.copy(),
            fstep, lstep,
            data.water, tstep, frame_csvs_dir,
        )

        # 12. per-step dump (synchronous)
        if dump_interval > 0 and tstep % dump_interval == 0:
            step_dir = os.path.join(timesteps_dir, f"t{tstep:06d}")
            dumper = _dump_step_csv if dump_csv else _dump_step_binary
            dumper(
                step_dir,
                fire.copy(), ignition.copy(),
                radtotal.copy(), out_fire.copy(), zvector.copy(),
            )

    # ── post-loop: clean out_fire ──────────────────────────────────────
    out_fire[(out_fire == 0) & (knownig_mat == 0)] = np.nan

    wall_end = time.time()
    runtime_min = (wall_end - wall_start) / 60
    _write_log(fh, "\n################################\n")
    _write_log(fh, f"Runtime: {runtime_min:.1f} minutes.\n")
    _write_log(fh, f"rad_energy_ig: {cfg.rad_energy_ig}\n")
    _write_log(fh, f"fb_wind_coef: {cfg.fb_wind_coef}\n")
    _write_log(fh, f"fb_wind_sd: {cfg.fb_wind_sd}\n")
    _write_log(fh, f"fb_wind_sd_transverse: {cfg.fb_wind_sd_transverse}\n")
    _write_log(fh, f"fb_mass: {cfg.fb_mass}\n")
    _write_log(fh, f"fb_dist_mu: {cfg.fb_dist_mu}\n")
    _write_log(fh, f"fb_dist_sd: {cfg.fb_dist_sd}\n")
    fh.close()

    # ── video / GIF ────────────────────────────────────────────────────
    if make_video:
        if phase_callback is not None:
            phase_callback("Generating video")
        print("Assembling video and GIF …")
        assemble_video(frames_dir, output_dir, tag="")

    # ── summary plots ─────────────────────────────────────────────────
    step_size = max(1, maxstep // 6)
    tick_positions = list(range(1, maxstep + 1, step_size))
    time_labels = [t_num_vec[k - 1].strftime("%H:%M") for k in tick_positions]

    plot_pixel_ignitions(
        output_dir, maxstep, time_labels, tick_positions,
        ig_known, ig_dev, ig_rad, ig_brand, ig_total,
    )
    plot_structure_ignitions(
        output_dir, maxstep, time_labels, tick_positions,
        house_ig_known, house_ig_rad, house_ig_brand, house_ig_total,
    )

    # ── CSV exports ───────────────────────────────────────────────────
    np.savetxt(os.path.join(output_dir, "fire_prog.csv"), out_fire, delimiter=",")
    np.savetxt(os.path.join(output_dir, "zvector.csv"), zvector, delimiter=",")

    print(f"Simulation complete.  Outputs in {output_dir}")


# ── helpers ──────────────────────────────────────────────────────────────

def _update_zvector(
    ignition: np.ndarray,
    homes_mat: np.ndarray,
    binary_cover: np.ndarray,
    zvector: np.ndarray,
    tstep: int,
    previously_ignited: set,
    cause_column: int,
) -> None:
    """Mark newly-ignited homes in ``zvector``.

    Columns:
        0 — home id
        1 — "any cause" flag
        2 — radiation flag
        3 — branding flag
        4 — first-ignition timestep

    ``previously_ignited`` is the set of home IDs that were already on
    fire before the current sub-step; only homes not in that set get
    flagged with ``cause_column`` and a step number.
    """
    mask = (ignition == 1) & (binary_cover > 0) & (homes_mat > 0)
    if not np.any(mask):
        return
    hids = np.unique(homes_mat[mask].astype(int))
    for hid in hids:
        hid_i = int(hid)
        if hid_i <= 0:
            continue
        if hid_i in previously_ignited:
            continue
        if zvector[hid_i - 1, 1] == 0:
            zvector[hid_i - 1, 1] = 1
            zvector[hid_i - 1, cause_column] = 1
            zvector[hid_i - 1, 4] = tstep
