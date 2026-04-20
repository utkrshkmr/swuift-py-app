"""Configuration dataclass and derived constants for SWUIFT simulation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Canonical physical / numerical constants
# ---------------------------------------------------------------------------

# Grid and time
GRID_SIZE: int = 10
T_STEP_MIN: float = 5.0  # minutes
T_START_DEFAULT: datetime = datetime(2025, 1, 7, 18, 20, 0)
T_END_DEFAULT: datetime = datetime(2025, 1, 8, 14, 20, 0)

# Radiation geometry and constants
AES: float = 60.0
EE: float = 0.7
ER: float = 0.7
SCONST: float = 5.67e-8

# Radiation ignition defaults (match default_values.mat / ALL_EMBERS)
RAD_ENERGY_IG_DEFAULT: float = 14000.0
RAD_RF_DEFAULT: float = 1.0

# Firebrand model defaults
FB_MASS: float = 0.5
FB_DIST_MU: float = 0.01
FB_DIST_SD: float = 0.5
FB_WIND_COEF_DEFAULT: float = 30.0
FB_WIND_SD_DEFAULT: float = 0.3
FB_WIND_SD_TRANSVERSE_DEFAULT: float = 4.85

# Hardening and seeds
HARDENING_RAD_DEFAULT: float = 70.0
HARDENING_SPO_DEFAULT: float = 70.0
SEED_HARDENING_DEFAULT: int = 123456
SEED_SPREAD_DEFAULT: int = 10

# Temperature curve: 37 fire-stage surface temperatures (degC).  Used as
# a fallback when the input bundle does not provide ``tmpr``.
_TMPR_VALUES: tuple[float, ...] = (
    28.62, 178.171, 192.151, 306.514, 484.043, 677.377, 680.536, 682.559,
    684.021, 685.132, 686.011, 686.728, 687.327, 687.837, 688.278, 688.665,
    689.008, 689.314, 689.59, 689.84, 690.068, 690.278, 690.471, 690.649,
    690.815, 690.969, 691.113, 691.248, 691.374, 691.493, 691.604, 691.709,
    691.808, 691.902, 691.99, 692.074, 678.551,
)
TMPR_DEFAULT: np.ndarray = np.array(_TMPR_VALUES, dtype=np.float64)


@dataclass(frozen=True)
class SWUIFTConfig:
    """All scalar / vector parameters needed by the simulation."""

    # Grid
    grid_size: int = GRID_SIZE

    # Time
    t_start: datetime = field(default_factory=lambda: T_START_DEFAULT)
    t_end: datetime = field(default_factory=lambda: T_END_DEFAULT)
    t_step_min: float = T_STEP_MIN
    # If set, number of timesteps to run. None = derive from t_start..t_end.
    maxstep: Optional[int] = None

    # Radiation
    aes: float = AES
    ee: float = EE
    er: float = ER
    sconst: float = SCONST
    rad_energy_ig: float = RAD_ENERGY_IG_DEFAULT
    rad_rf: float = RAD_RF_DEFAULT

    # Firebrands
    fb_mass: float = FB_MASS
    fb_wind_coef: float = FB_WIND_COEF_DEFAULT
    fb_wind_sd: float = FB_WIND_SD_DEFAULT
    fb_wind_sd_transverse: float = FB_WIND_SD_TRANSVERSE_DEFAULT
    fb_dist_mu: float = FB_DIST_MU
    fb_dist_sd: float = FB_DIST_SD

    # Vegetation
    veg_included: bool = True

    # Temperature curve (indexed by fire-stage)
    tmpr: np.ndarray = field(default_factory=lambda: TMPR_DEFAULT.copy())

    # Hardening
    hardening_level_rad: float = HARDENING_RAD_DEFAULT
    hardening_level_spo: float = HARDENING_SPO_DEFAULT

    # RNG seeds
    seed_hardening: int = SEED_HARDENING_DEFAULT
    seed_spread: int = SEED_SPREAD_DEFAULT

    # ---- derived constants (computed from the above) ----

    @property
    def fstep(self) -> int:
        """First fully-developed timestep (OZone: 22 min)."""
        return int(22 / self.t_step_min) + 1

    @property
    def lstep(self) -> int:
        """Last fully-developed timestep (OZone: 177 min)."""
        return int(177 / self.t_step_min) + 1

    @property
    def fb_str_ig(self) -> int:
        """Brand count criterion for structure ignition (Santamaria)."""
        return math.ceil(24 / self.fb_mass)

    @property
    def fb_veg_gen(self) -> int:
        """Number of brands generated from a vegetation cell (Wickramasinghe)."""
        return math.ceil(
            (self.grid_size ** 2 / (2.25 * math.pi / 4)) * (87 / self.fb_mass)
        )

    @property
    def fb_veg_ig(self) -> int:
        """Brand count criterion for vegetation ignition (Suzuki 2020)."""
        return 64 * math.ceil(3.5 / self.fb_mass) + 1

    @property
    def limrad(self) -> float:
        return 1.0 - self.hardening_level_rad / 100.0

    @property
    def limspo(self) -> float:
        return 1.0 - self.hardening_level_spo / 100.0

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


def build_config(
    defaults: Optional[dict],
    *,
    grid_size: Optional[int] = None,
    t_start: Optional[datetime] = None,
    t_end: Optional[datetime] = None,
    maxstep: Optional[int] = None,
    hardening_rad: Optional[float] = None,
    hardening_spo: Optional[float] = None,
    rad_energy_ig: Optional[float] = None,
    rad_rf: Optional[float] = None,
    fb_wind_coef: Optional[float] = None,
    fb_wind_sd: Optional[float] = None,
    fb_wind_sd_transverse: Optional[float] = None,
    seed_hardening: Optional[int] = None,
    seed_spread: Optional[int] = None,
) -> SWUIFTConfig:
    """Construct a :class:`SWUIFTConfig` from an optional defaults dict and
    explicit overrides.

    Precedence for each field:
        1. Explicit kwarg override.
        2. Value from ``defaults`` (if provided).
        3. Module-level constant.
    """

    def _scalar_from_defaults(key: str, fallback: float) -> float:
        if defaults is not None and key in defaults:
            v = defaults[key]
            if hasattr(v, "item"):
                return float(v.item())
            return float(v)
        return float(fallback)

    def _vec_from_defaults(key: str, fallback: np.ndarray) -> np.ndarray:
        if defaults is not None and key in defaults:
            v = defaults[key]
            return np.asarray(v, dtype=np.float64).ravel()
        return np.asarray(fallback, dtype=np.float64).ravel()

    # Time step comes from defaults when available, otherwise module constant.
    t_step_min = _scalar_from_defaults("t_step_min", T_STEP_MIN)

    # Time range: fixed module defaults, ignoring any t_start_vec /
    # t_end_vec in ``defaults``.  Explicit overrides take precedence.
    if t_start is None:
        t_start = T_START_DEFAULT
    if t_end is None:
        t_end = T_END_DEFAULT

    # Scalars with override → defaults → constant precedence.
    aes = _scalar_from_defaults("aes", AES)
    ee = _scalar_from_defaults("ee", EE)
    er = _scalar_from_defaults("er", ER)
    sconst = _scalar_from_defaults("sconst", SCONST)

    rad_energy_ig_val = (
        float(rad_energy_ig)
        if rad_energy_ig is not None
        else _scalar_from_defaults("rad_energy_ig", RAD_ENERGY_IG_DEFAULT)
    )
    rad_rf_val = (
        float(rad_rf)
        if rad_rf is not None
        else _scalar_from_defaults("rad_rf", RAD_RF_DEFAULT)
    )

    fb_mass = _scalar_from_defaults("fb_mass", FB_MASS)
    fb_wind_coef_val = (
        float(fb_wind_coef)
        if fb_wind_coef is not None
        else _scalar_from_defaults("fb_wind_coef", FB_WIND_COEF_DEFAULT)
    )
    fb_wind_sd_val = (
        float(fb_wind_sd)
        if fb_wind_sd is not None
        else _scalar_from_defaults("fb_wind_sd", FB_WIND_SD_DEFAULT)
    )
    fb_wind_sd_transverse_val = (
        float(fb_wind_sd_transverse)
        if fb_wind_sd_transverse is not None
        else _scalar_from_defaults(
            "fb_wind_sd_transverse", FB_WIND_SD_TRANSVERSE_DEFAULT
        )
    )

    fb_dist_mu = _scalar_from_defaults("fb_dist_mu", FB_DIST_MU)
    fb_dist_sd = _scalar_from_defaults("fb_dist_sd", FB_DIST_SD)

    veg_included = True
    if defaults is not None and "veg_included" in defaults:
        veg_included = bool(_scalar_from_defaults("veg_included", 1.0))

    tmpr_vec = _vec_from_defaults("tmpr", TMPR_DEFAULT)

    # Hardening levels: override → defaults (if present) → constants.
    hardening_level_rad = (
        float(hardening_rad)
        if hardening_rad is not None
        else _scalar_from_defaults("hardening_level_rad", HARDENING_RAD_DEFAULT)
    )
    hardening_level_spo = (
        float(hardening_spo)
        if hardening_spo is not None
        else _scalar_from_defaults("hardening_level_spo", HARDENING_SPO_DEFAULT)
    )

    seed_h = (
        int(seed_hardening)
        if seed_hardening is not None
        else int(SEED_HARDENING_DEFAULT)
    )
    seed_s = int(seed_spread) if seed_spread is not None else int(SEED_SPREAD_DEFAULT)

    return SWUIFTConfig(
        grid_size=grid_size if grid_size is not None else GRID_SIZE,
        t_start=t_start,
        t_end=t_end,
        t_step_min=t_step_min,
        maxstep=maxstep,
        aes=aes,
        ee=ee,
        er=er,
        sconst=sconst,
        rad_energy_ig=rad_energy_ig_val,
        rad_rf=rad_rf_val,
        fb_mass=fb_mass,
        fb_wind_coef=fb_wind_coef_val,
        fb_wind_sd=fb_wind_sd_val,
        fb_wind_sd_transverse=fb_wind_sd_transverse_val,
        fb_dist_mu=fb_dist_mu,
        fb_dist_sd=fb_dist_sd,
        veg_included=veg_included,
        tmpr=tmpr_vec,
        hardening_level_rad=hardening_level_rad,
        hardening_level_spo=hardening_level_spo,
        seed_hardening=seed_h,
        seed_spread=seed_s,
    )
