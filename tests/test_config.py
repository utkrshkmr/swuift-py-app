"""Tests for config.py derived constants."""

import math

import numpy as np
import pytest

from swuift.config import SWUIFTConfig


def _default_cfg(**overrides):
    defaults = dict(
        grid_size=10,
        t_step_min=5.0,
        fb_mass=0.5,
        aes=9.0,
        ee=0.9,
        er=0.9,
        sconst=5.67e-8,
        rad_energy_ig=12500.0,
        rad_rf=0.9,
        fb_wind_coef=6.0,
        fb_wind_sd=0.8,
        fb_wind_sd_transverse=5.0,
        fb_dist_mu=0.0,
        fb_dist_sd=1.0,
        veg_included=True,
        tmpr=np.zeros(37),
    )
    defaults.update(overrides)
    return SWUIFTConfig(**defaults)


class TestDerivedConstants:
    def test_fstep(self):
        cfg = _default_cfg(t_step_min=5.0)
        assert cfg.fstep == int(22 / 5) + 1  # 5

    def test_lstep(self):
        cfg = _default_cfg(t_step_min=5.0)
        assert cfg.lstep == int(177 / 5) + 1  # 36

    def test_fb_str_ig(self):
        cfg = _default_cfg(fb_mass=0.5)
        assert cfg.fb_str_ig == math.ceil(24 / 0.5)  # 48

    def test_fb_veg_gen(self):
        cfg = _default_cfg(grid_size=10, fb_mass=0.5)
        expected = math.ceil((100 / (2.25 * math.pi / 4)) * (87 / 0.5))
        assert cfg.fb_veg_gen == expected

    def test_fb_veg_ig(self):
        cfg = _default_cfg(fb_mass=0.5)
        assert cfg.fb_veg_ig == 64 * math.ceil(3.5 / 0.5) + 1

    def test_limrad(self):
        cfg = _default_cfg(hardening_level_rad=70.0)
        assert cfg.limrad == pytest.approx(0.3)

    def test_limspo(self):
        cfg = _default_cfg(hardening_level_spo=70.0)
        assert cfg.limspo == pytest.approx(0.3)
