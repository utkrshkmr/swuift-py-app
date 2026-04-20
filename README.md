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
2. [Launching the App](#2-launching-the-app)
3. [UI Reference — every tab, every field](#3-ui-reference)
   1. [Tab 1 — Data Inputs](#31-tab-1--data-inputs)
   2. [Tab 2 — Grid & Time](#32-tab-2--grid--time)
   3. [Tab 3 — Radiation](#33-tab-3--radiation)
   4. [Tab 4 — Firebrands](#34-tab-4--firebrands)
   5. [Tab 5 — Hardening & Seeds](#35-tab-5--hardening--seeds)
   6. [Tab 6 — Output Settings](#36-tab-6--output-settings)
   7. [Job Queue panel](#37-job-queue-panel)
4. [Platform-specific first-launch warnings](#4-platform-specific-warnings)
   1. [macOS — Gatekeeper / Privacy & Security](#41-macos)
   2. [Windows — SmartScreen / admin elevation](#42-windows)
   3. [Linux — executable bit](#43-linux)
5. [Outputs produced by a run](#5-outputs)

---

## 1. Installation

### Prerequisites

- Python 3.11 or 3.12 (CI targets 3.12).
- `pip` and `venv` (or any equivalent environment manager).
- An input dataset consisting of ten `.mat` files (see
  [Tab 1 — Data Inputs](#31-tab-1--data-inputs)).  A ready-to-use sample
  dataset is available via `./scripts/fetch_sample_data.sh` — see
  [`SAMPLE_DATA.md`](SAMPLE_DATA.md) for details.

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
[§4 Platform-specific warnings](#4-platform-specific-warnings) for how
to bypass the first-launch security prompts.

---

## 2. Launching the App

```bash
python swuift_app.py
```

A PySide6 window opens with six configuration tabs, a live simulation
log, and a job queue.  Fill in each tab, click **Add to Queue**, repeat
for as many parameter sweeps as you want, then click **Run All**.

The **File** menu provides *Save Settings as JSON* (Ctrl+S) and
*Load Settings from JSON* (Ctrl+O) to persist every tab's values
between sessions.

---

## 3. UI Reference

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

### 3.1 Tab 1 — Data Inputs

Ten file pickers.  Each must point to a real `.mat` file on disk (all
are required).

| Field                | What to select                                                                                                         |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Wildland Fire Matrix | `wildland_fire_matrix.mat` — known wildfire ignition progression (`knownig_mat`, row × col × time).                    |
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

### 3.2 Tab 2 — Grid & Time

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

### 3.3 Tab 3 — Radiation

Controls the Stefan-Boltzmann structure-ignition test.

| Field                      | What it represents                                                                              | Default  | Range       |
| -------------------------- | ----------------------------------------------------------------------------------------------- | -------- | ----------- |
| Ignition Threshold (W/m²)  | Minimum radiant flux a cell must receive to ignite.  Lower → structures ignite more easily.    | 14 000.0 | 0 – 100 000 |
| Radiation Reduction Factor | Multiplicative damping of accumulated flux (0–1).  `1.0` = no reduction; `0.0` = radiation off. | 1.0      | 0.0 – 1.0   |

### 3.4 Tab 4 — Firebrands

Controls wind-driven brand transport statistics.  Brands are drawn from
a lognormal distribution (`fb_dist_mu`, `fb_dist_sd` in config) and
displaced by a wind-parallel drift (`fb_wind_coef`) plus longitudinal
and transverse scatter.

| Field                       | What it represents                                                                    | Default |
| --------------------------- | ------------------------------------------------------------------------------------- | ------- |
| Wind Coefficient            | Scales downwind drift of each brand.  Higher → brands land farther downwind.         | 30.0    |
| Wind Std Dev (longitudinal) | σ of along-wind scatter added to each landing.  Larger → more spread along wind axis. | 0.3     |
| Wind Std Dev (transverse)   | σ of cross-wind scatter.  Larger → more lateral spread of brand landings.             | 4.85    |

### 3.5 Tab 5 — Hardening & Seeds

Hardening defines the fraction of structures that **resist** ignition;
the two RNG seeds make a run reproducible.

| Field                         | What it represents                                                                                              | Default |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------- | ------- |
| Radiation Hardening Level (%) | Target % of homes that resist radiation ignition.  100 = all homes immune to radiation.                         | 70.0    |
| Spotting Hardening Level (%)  | Target % of homes that resist firebrand ignition.                                                               | 70.0    |
| Seed — Hardening RNG          | Seed used to draw the uniform(0,1) hardening criterion for each home.  Same seed → same set of hardened homes. | 123456  |
| Seed — Spread RNG             | Seed for all firebrand-transport and stochastic-ignition draws.  Same seed → same run.                          | 10      |

### 3.6 Tab 6 — Output Settings

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

### 3.7 Job Queue panel

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

## 4. Platform-specific Warnings

Because the binary is not signed with a paid Apple or Microsoft
developer certificate, each OS warns on first launch.  Here is how to
bypass each warning as the machine's administrator or owner.

### 4.1 macOS

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

### 4.2 Windows

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

### 4.3 Linux

No code-signing scheme is enforced; the bundle is a plain directory.

```bash
chmod +x SWUIFT/SWUIFT     # make the launcher executable
./SWUIFT/SWUIFT            # run
```

If SELinux / AppArmor blocks the binary, run with `sudo setenforce 0`
temporarily or add a permissive policy for the install path.

---

## 5. Outputs

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
