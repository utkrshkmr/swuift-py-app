# SWUIFT — Simulating Wildfire-Urban Interface Fire Transmission

Desktop application for the SWUIFT fire-spread model.  SWUIFT simulates
how wildfire radiation and wind-borne firebrands propagate through a
mixed wildland-urban landscape, ignite structures, and damage a
neighbourhood over time.

The application is a PySide6 desktop GUI: configure a simulation across
six tabs, queue one or more runs, and watch per-step progress, frames,
and summary plots appear in the output folder.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Data Preparation](#2-data-preparation)
   1. [Directory layout](#21-directory-layout)
   2. [Eaton legacy data — what each file contains](#22-eaton-legacy-data)
   3. [Extracting the Eaton sample data](#23-extracting-the-eaton-sample-data)
   4. [Downloading the pre-extracted sample dataset](#24-downloading-the-pre-extracted-sample-dataset)
3. [Launching the App](#3-launching-the-app)
4. [UI Reference — every tab, every field](#4-ui-reference)
   1. [Tab 1 — Data Inputs](#41-tab-1--data-inputs)
   2. [Tab 2 — Grid & Time](#42-tab-2--grid--time)
   3. [Tab 3 — Radiation](#43-tab-3--radiation)
   4. [Tab 4 — Firebrands](#44-tab-4--firebrands)
   5. [Tab 5 — Hardening & Seeds](#45-tab-5--hardening--seeds)
   6. [Tab 6 — Output Settings](#46-tab-6--output-settings)
   7. [Job Queue panel](#47-job-queue-panel)
5. [Platform-specific first-launch warnings](#5-platform-specific-warnings)
   1. [macOS — Gatekeeper / Privacy & Security](#51-macos)
   2. [Windows — SmartScreen / admin elevation](#52-windows)
   3. [Linux — executable bit](#53-linux)
6. [Outputs produced by a run](#6-outputs)

---

## 1. Installation

### Prerequisites

- Python 3.11 or 3.12 (CI targets 3.12).
- `pip` and `venv` (or any equivalent environment manager).
- An input dataset of ten `.mat` files — see
  [§2 Data Preparation](#2-data-preparation).

### From source

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate.bat     # Windows cmd
pip install -r requirements_app.txt
```

`requirements_app.txt` contains everything needed for the GUI, tests,
and PyInstaller packaging.

### Pre-built installers

GitHub Actions builds binaries for every push (see
`.github/workflows/build.yml`):

| Platform            | Artifact                       |
| ------------------- | ------------------------------ |
| macOS Apple Silicon | `SWUIFT-macos-arm64.dmg`       |
| macOS Intel         | `SWUIFT-macos-x86_64.dmg`      |
| Windows x64         | `SWUIFT-windows-x64-setup.exe` |
| Windows ARM64       | `SWUIFT-windows-arm64.zip`     |

Download an artifact, then see
[§5 Platform-specific warnings](#5-platform-specific-warnings) for how
to bypass the first-launch security prompts.

---

## 2. Data Preparation

The SWUIFT GUI consumes **ten per-variable `.mat` files**, one variable
per file.  The reference dataset is the *Eaton* scenario: a wildfire
scenario over a real wildland-urban neighbourhood at 10 m resolution.
The repository ships two closely related folders for working with that
dataset — a *legacy bundle* and the *extracted sample dataset* the
application actually loads.

### 2.1 Directory layout

```text
PROTOTYPE_APP/
├── eaton_legacy_data/          # Original Eaton MATLAB bundle + extractors
│   ├── default_values.mat      # Baseline parameter values and the tmpr curve
│   ├── domains_mat.mat         # Domain classification raster
│   ├── eaton_inputs_all.mat    # Bundled spatial inputs (see §2.2)
│   ├── fire_prog.mat           # Known wildfire ignition progression
│   ├── wind_eaton.mat          # Wind time-series (HDF5 v7.3, ~6.8 GB)
│   ├── extract_inputs_to_mat.py    # → produces eaton_sample_data/*.mat
│   └── extract_inputs_to_csv.py    # → produces eaton_sample_csv/*.csv
│
├── eaton_sample_data/          # Per-variable .mat files (app reads these)
│   ├── binary_cover_landcover.mat
│   ├── domain_matrix.mat
│   ├── homes_matrix.mat
│   ├── latitude.mat
│   ├── longitude.mat
│   ├── radiation_matrix.mat
│   ├── spotting_matrix.mat
│   ├── water_matrix.mat
│   ├── wildland_fire_matrix.mat
│   └── wind.mat                # copied verbatim from wind_eaton.mat
│
├── swuift/                     # Model source
├── gui/                        # PySide6 GUI
├── scripts/                    # Sample-data helpers (fetch / publish)
├── swuift_app.py               # GUI entry point
└── README.md
```

Only the contents of `eaton_sample_data/` are loaded by the GUI.  The
legacy bundle in `eaton_legacy_data/` is kept so the extraction is
reproducible — if upstream data changes you can regenerate the sample
dataset by re-running the extractors.

Neither `.mat` payload is tracked in git (see `.gitignore`): the legacy
bundle lives on the maintainer's machine, and the sample dataset is
published as a GitHub Release (§2.4).

### 2.2 Eaton legacy data

The files inside `eaton_legacy_data/` are the original MATLAB assets
produced upstream.  Variables are packed together inside a small number
of `.mat` files:

| File                  | Type      | Variables it contains                       | Description                                                                                                                |
| --------------------- | --------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `default_values.mat`  | MATLAB v5 | default run parameters + `tmpr` curve       | Baseline numerical constants used by the model when no GUI override is supplied (grid size, emissivity, tmpr array, …).    |
| `domains_mat.mat`     | MATLAB v5 | `domains_mat` *(row × col int raster)*      | Domain classification: integer codes for roads, water, buildable structures, non-combustible, etc.                         |
| `eaton_inputs_all.mat`| MATLAB v5 | `binary_cover`, `homes_mat`, `water`, `lati`, `long`, `hardening_mat_rad`, `hardening_mat_spo` | Bundled spatial inputs for the Eaton scenario — the landcover raster, building IDs, water mask, lat/long vectors, and both hardening masks. |
| `fire_prog.mat`       | MATLAB v5 | `fire_prog` *(row × col × time int raster)* | Known wildfire ignition progression used as the boundary condition that seeds the urban-area simulation.                   |
| `wind_eaton.mat`      | HDF5 v7.3 | `wind_s`, `wind_d` *(time × row × col)*     | Full wind time-series — speed (m/s) and direction (deg) per cell per timestep.  ~6.8 GB uncompressed.                      |

Everything has a consistent grid resolution (10 m) and shares the same
`(rows, cols)` extent.  Latitude/longitude are 1-D vectors whose lengths
match the number of rows and columns respectively.

### 2.3 Extracting the Eaton sample data

The GUI loads one raster per `.mat` file, with stable file names and
variable names.  Two helper scripts unpack the legacy bundle into that
layout:

```text
eaton_legacy_data/extract_inputs_to_mat.py   → writes eaton_sample_data/*.mat
eaton_legacy_data/extract_inputs_to_csv.py   → writes eaton_sample_csv/*.csv
```

The `.mat` extractor is what the application expects.  From the
repository root:

```bash
python eaton_legacy_data/extract_inputs_to_mat.py
```

This reads the bundle, writes per-variable files to
`eaton_sample_data/`, and copies `wind_eaton.mat` verbatim to
`eaton_sample_data/wind.mat`.

Output mapping:

| Legacy source                 | Variable read       | Output file in `eaton_sample_data/` | Variable name inside output |
| ----------------------------- | ------------------- | ----------------------------------- | --------------------------- |
| `fire_prog.mat`               | `fire_prog`         | `wildland_fire_matrix.mat`          | `wildland_fire_matrix`      |
| `domains_mat.mat`             | `domains_mat`       | `domain_matrix.mat`                 | `domains_mat`               |
| `eaton_inputs_all.mat`        | `binary_cover`      | `binary_cover_landcover.mat`        | `binary_cover`              |
| `eaton_inputs_all.mat`        | `homes_mat`         | `homes_matrix.mat`                  | `homes_mat`                 |
| `eaton_inputs_all.mat`        | `water`             | `water_matrix.mat`                  | `water`                     |
| `eaton_inputs_all.mat`        | `lati`              | `latitude.mat`                      | `lati`                      |
| `eaton_inputs_all.mat`        | `long`              | `longitude.mat`                     | `long`                      |
| `eaton_inputs_all.mat`        | `hardening_mat_rad` | `radiation_matrix.mat`              | `hardening_mat_rad`         |
| `eaton_inputs_all.mat`        | `hardening_mat_spo` | `spotting_matrix.mat`               | `hardening_mat_spo`         |
| `wind_eaton.mat` *(HDF5 v7.3)*| `wind_s`, `wind_d`  | `wind.mat`                          | `wind_s`, `wind_d`          |

Override the destination if you'd rather write elsewhere:

```bash
python eaton_legacy_data/extract_inputs_to_mat.py --out-dir /tmp/swuift-inputs
```

A companion script `extract_inputs_to_csv.py` writes each raster as CSV
into `eaton_sample_csv/` (useful for eyeballing the data in Excel /
Pandas).  The GUI does **not** read CSV inputs.

### 2.4 Downloading the pre-extracted sample dataset

If you don't have access to `wind_eaton.mat` you can skip the extraction
step entirely and fetch the pre-extracted sample dataset from the
project's GitHub Release:

```bash
./scripts/fetch_sample_data.sh
```

This downloads each asset, verifies SHA-256 checksums, reassembles the
split `wind.mat` chunks, and leaves everything under
`eaton_sample_data/`.  Total download is ~7 GB.

See [`SAMPLE_DATA.md`](SAMPLE_DATA.md) for release asset details, manual
download instructions, and the maintainer workflow for publishing a new
dataset.

---

## 3. Launching the App

```bash
python swuift_app.py
```

A PySide6 window opens with six configuration tabs, a live simulation
log, and a job queue.  Fill in each tab (point Tab 1 at the ten files in
`eaton_sample_data/`), click **Add to Queue**, repeat for as many
parameter sweeps as you want, then click **Run All**.

The **File** menu provides *Save Settings as JSON* (Ctrl+S) and
*Load Settings from JSON* (Ctrl+O) to persist every tab's values
between sessions.

---

## 4. UI Reference

The main window is split into three regions:

```
┌──────────────────────────────────────────────────────────┐
│  [Tabs:  Data Inputs │ Grid & Time │ Radiation │ … ]     │
│                                                          │
│  (current tab content)                                   │
├──────────────────────────────────────────────────────────┤
│  Simulation Log          (live stdout / phase updates)   │
├──────────────────────────────────────────────────────────┤
│  Job Queue  [Add] [Run All] [Cancel] [Remove] [Dup] …    │
│  id │ state │ progress │ started │ elapsed │ out-dir     │
└──────────────────────────────────────────────────────────┘
```

### 4.1 Tab 1 — Data Inputs

Ten file pickers.  Each must point to a real `.mat` file on disk (all
are required).  The defaults match the layout produced by §2.3.

| Field                | What to select                                                                                                         |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Wildland Fire Matrix | `wildland_fire_matrix.mat` — known wildfire ignition progression (`wildland_fire_matrix`, row × col × time).           |
| Domain Matrix        | `domain_matrix.mat` — domain classification raster (`domains_mat`).  Integer codes for roads, water, buildable, etc.   |
| Binary Cover         | `binary_cover_landcover.mat` — `binary_cover` raster.  `+1` = structure, `−1` = burnable vegetation, `0` = non-burnable. |
| Homes Matrix         | `homes_matrix.mat` — `homes_mat`, per-cell integer building ID (`0` = not a home).                                      |
| Latitude             | `latitude.mat` — 1-D latitude vector, length = number of rows.                                                         |
| Longitude            | `longitude.mat` — 1-D longitude vector, length = number of columns.                                                    |
| Radiation Matrix     | `radiation_matrix.mat` — `hardening_mat_rad`, per-cell radiation hardening flag (`1` = already hardened).              |
| Spotting Matrix      | `spotting_matrix.mat` — `hardening_mat_spo`, per-cell spotting hardening flag.                                         |
| Water Matrix         | `water_matrix.mat` — mask of non-burnable water cells.                                                                  |
| Wind File            | `wind.mat` — HDF5 / v7.3 file containing `wind_s` (speed) and `wind_d` (direction) arrays, one slice per timestep.     |

Clicking *Reset to Defaults* clears all ten paths.  Paths you type are
stored via `QSettings` between sessions.

**Hidden but physical.** A handful of constants live in
`swuift/config.py` and are not editable from the GUI:

- `grid_size = 10` m (cell size)
- `aes = 9.0`, `ee = er = 0.9`, `sconst = 5.67e-8` (radiation emissivities & Stefan-Boltzmann)
- `fb_mass = 0.5 g` (brand mass), `fb_dist_mu = 0.0`, `fb_dist_sd = 1.0` (lognormal transport)
- `tmpr` — 37-point temperature curve used by the radiation kernel

### 4.2 Tab 2 — Grid & Time

Simulation start / end time.  The number of timesteps is derived
automatically (`(t_end − t_start) / 5 min + 1`) and shown live.

| Field            | What to fill                  | Default           |
| ---------------- | ----------------------------- | ----------------- |
| Simulation Start | Date and time the sim begins. | 2025-01-07 18:20  |
| Simulation End   | Date and time the sim ends.   | 2025-01-08 14:20  |

A status line below the pickers shows the calculated step count
(e.g. `Calculated steps: 241 (20.0 h · 5-min timestep · grid = 10 m)`).
If the end is before the start a red warning appears and the run cannot
be queued.

### 4.3 Tab 3 — Radiation

Controls the Stefan-Boltzmann structure-ignition test.

| Field                      | What it represents                                                                              | Default  | Range       |
| -------------------------- | ----------------------------------------------------------------------------------------------- | -------- | ----------- |
| Ignition Threshold (W/m²)  | Minimum radiant flux a cell must receive to ignite.  Lower → structures ignite more easily.    | 14 000.0 | 0 – 100 000 |
| Radiation Reduction Factor | Multiplicative damping of accumulated flux (0–1).  `1.0` = no reduction; `0.0` = radiation off. | 1.0      | 0.0 – 1.0   |

### 4.4 Tab 4 — Firebrands

Controls wind-driven brand transport statistics.  Brands are drawn from
a lognormal distribution (`fb_dist_mu`, `fb_dist_sd` in config) and
displaced by a wind-parallel drift (`fb_wind_coef`) plus longitudinal
and transverse scatter.

| Field                       | What it represents                                                                    | Default |
| --------------------------- | ------------------------------------------------------------------------------------- | ------- |
| Wind Coefficient            | Scales downwind drift of each brand.  Higher → brands land farther downwind.         | 30.0    |
| Wind Std Dev (longitudinal) | σ of along-wind scatter added to each landing.  Larger → more spread along wind axis. | 0.3     |
| Wind Std Dev (transverse)   | σ of cross-wind scatter.  Larger → more lateral spread of brand landings.             | 4.85    |

### 4.5 Tab 5 — Hardening & Seeds

Hardening defines the fraction of structures that **resist** ignition;
the two RNG seeds make a run reproducible.

| Field                         | What it represents                                                                                              | Default |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------- | ------- |
| Radiation Hardening Level (%) | Target % of homes that resist radiation ignition.  100 = all homes immune to radiation.                         | 70.0    |
| Spotting Hardening Level (%)  | Target % of homes that resist firebrand ignition.                                                               | 70.0    |
| Seed — Hardening RNG          | Seed used to draw the uniform(0,1) hardening criterion for each home.  Same seed → same set of hardened homes. | 123456  |
| Seed — Spread RNG             | Seed for all firebrand-transport and stochastic-ignition draws.  Same seed → same run.                          | 10      |

### 4.6 Tab 6 — Output Settings

| Field                             | Type      | What it does                                                                                                         | Default    |
| --------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------- | ---------- |
| Output Folder                     | Folder    | Parent directory — every run creates a new timestamped subfolder `run_YYYYMMDD_HHMMSS` inside it.                     | `outputs/` |
| Generate Video / GIF              | Checkbox  | After the run, assemble all PNG frames into `simulation.mp4` + `simulation.gif`.  Requires bundled `ffmpeg`.          | On         |
| Frame DPI                         | Integer   | Resolution of rendered PNG frames and the resulting video.                                                            | 600        |
| Dump Interval (0 = off)           | Integer   | Save per-step `fire / ignition / radtotal / out_fire / zvector` arrays every N steps.  `0` disables per-step dumps.   | 0          |
| Dump as CSV                       | Checkbox  | When dumps are enabled, write `.csv` (portable) instead of `.npy` (compact).                                          | Off        |
| Lazy Wind (low-RAM mode)          | Checkbox  | Read wind slices on demand from the HDF5 file instead of preloading.  Saves RAM but is slower per step.               | Off        |
| Export radiation flux CSV / frame | Checkbox  | Write `radtotal` (W/m²) to `radiation_csv/step_XXX.csv` for every frame.                                              | Off        |
| Export spotting CSV / frame       | Checkbox  | Write the firebrand-deposit matrix to `spotting_csv/step_XXX.csv` for every frame.                                    | Off        |

### 4.7 Job Queue panel

The bottom dock lets you queue several runs with different parameter
sets.  Columns are:

- **id** — integer run id.
- **state** — `Pending`, `Running`, `Done`, `Cancelled`, `Error`.
- **progress** — `step N / total`.
- **started** — wall-clock time when the job started.
- **elapsed / ETA** — live-updating once the job is running.
- **out-dir** — the timestamped subfolder this job is writing to.

Buttons:

- **Add to Queue** — snapshot current tab values, validate, and append a pending job.
- **Run All** — start the first pending job; subsequent ones run sequentially.
- **Cancel** — ask the running job to stop at the next step boundary.
- **Remove Selected** — delete a pending job.
- **Duplicate Selected** — append a pending copy of any job (handy for parameter sweeps).
- **Clear Queue** — wipe everything (running job is cancelled first).

Double-click any row to open a job-detail dialog.  Right-click gives
the same actions as the buttons.

---

## 5. Platform-specific Warnings

Because the binary is not signed with a paid Apple or Microsoft
developer certificate, each OS warns on first launch.  Here is how to
bypass each warning as the machine's administrator or owner.

### 5.1 macOS

#### A. "SWUIFT can't be opened because Apple cannot check it for malicious software."

1. Leave the dialog and open **System Settings → Privacy & Security**.
2. Scroll to the **Security** section.  You will see
   "SWUIFT was blocked from use because it is not from an identified developer."
3. Click **Open Anyway**, enter your admin password, and answer
   **Open** in the confirmation dialog that follows.

#### B. Shortcut via Finder (no Settings panel)

Right-click (or Ctrl-click) `SWUIFT.app` → **Open** → **Open** in the
warning dialog.  macOS caches the grant; subsequent launches work as
normal double-clicks.

#### C. Quarantine attribute (from Terminal)

If macOS insists the app is "damaged" (this happens when the `.dmg` was
downloaded via `curl` / `scp` and loses its `com.apple.quarantine`
metadata), strip the attribute:

```bash
xattr -dr com.apple.quarantine /Applications/SWUIFT.app
```

### 5.2 Windows

#### A. SmartScreen: "Windows protected your PC"

1. Click **More info** on the SmartScreen dialog.
2. A new button **Run anyway** appears — click it.
3. If you launched the **Inno Setup installer** Windows may additionally
   ask for **UAC elevation**; click **Yes** to allow the installer to
   write to `Program Files`.

#### B. Installing per-user (no admin password)

Run the installer and on the first page choose **"Install for me
only"**, which writes to `%LocalAppData%\Programs\SWUIFT` and needs no
admin rights.

#### C. Running from source

- Open **PowerShell** (not admin is fine).
- If `Set-ExecutionPolicy` blocks `.venv\Scripts\activate.ps1`, run it
  once per user:

    ```powershell
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
    ```

- If Defender quarantines `python.exe` inside the venv, add the folder
  under **Windows Security → Virus & Threat Protection → Manage Settings
  → Add or remove exclusions**.

#### D. Launching as administrator (only if writing to protected dirs)

Right-click `SWUIFT.exe` → **Run as administrator**.  You should **not**
need admin for normal operation — SWUIFT writes only to the Output
Folder you select, never to `Program Files` at runtime.

### 5.3 Linux

No code-signing scheme is enforced; the bundle is a plain directory.

```bash
chmod +x SWUIFT/SWUIFT     # make the launcher executable
./SWUIFT/SWUIFT            # run
```

If SELinux / AppArmor blocks the binary, run with `sudo setenforce 0`
temporarily or add a permissive policy for the install path.

---

## 6. Outputs

Each run creates a new timestamped folder inside your chosen Output
Folder, e.g. `outputs/run_20260420_142812/`:

```
outputs/run_20260420_142812/
├── frames/                 # per-timestep high-res PNG snapshots
├── simulation.mp4          # assembled video (if "Generate Video" is on)
├── simulation.gif          # animated GIF
├── frames_csv/             # per-timestep "fire matrix" CSVs
├── timesteps/              # per-step .npy / .csv dumps (if enabled)
├── radiation_csv/          # per-cell radiation flux CSVs (if enabled)
├── spotting_csv/           # per-cell firebrand counts (if enabled)
├── ig_pixel.png            # cumulative pixel-ignition plot
├── ig_structure.png        # cumulative structure-ignition plot
├── fire_prog.csv           # final fire-time-of-arrival raster
├── zvector.csv             # per-building ignition log
├── run_metadata.txt        # full metadata (same text as the console log)
└── run_log.txt             # parameter log + per-step diagnostics
```
