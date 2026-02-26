"""Tests for monostatic radar range equation calculations."""

import math

import pytest

from physbound.engines.constants import BOLTZMANN, SPEED_OF_LIGHT
from physbound.engines.radar import compute_radar_range
from physbound.engines.units import db_to_linear
from physbound.errors import PhysicalViolationError

DB_TOL = 0.1
RANGE_REL_TOL = 1e-6


class TestRadarRangeBasic:
    """Core radar range equation correctness tests."""

    def test_known_reference_case(self):
        """Verify R_max for manually computed reference parameters.

        1 kW, 30 dBi, 10 GHz, sigma=1 m^2, 290K, 1 MHz BW, 13 dB min SNR.
        """
        result = compute_radar_range(
            peak_power_w=1000.0,
            antenna_gain_dbi=30.0,
            frequency_hz=10e9,
            rcs_m2=1.0,
        )
        # Manually verify: compute expected R_max
        c = SPEED_OF_LIGHT.magnitude
        k_b = BOLTZMANN.magnitude
        lam = c / 10e9
        g = db_to_linear(30.0)
        snr_min = db_to_linear(13.0)
        s_min = k_b * 290.0 * 1e6 * snr_min
        num = 1000.0 * g**2 * lam**2 * 1.0
        den = (4.0 * math.pi) ** 3 * s_min
        expected_r = (num / den) ** 0.25

        assert math.isclose(result["max_range_m"], expected_r, rel_tol=RANGE_REL_TOL)
        assert math.isclose(result["max_range_km"], expected_r / 1000.0, rel_tol=RANGE_REL_TOL)

    def test_fourth_root_power_scaling(self):
        """Doubling power increases range by 2^(1/4) = 1.189, NOT 2x."""
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        r2 = compute_radar_range(2000.0, 30.0, 10e9, 1.0)
        ratio = r2["max_range_m"] / r1["max_range_m"]
        assert math.isclose(ratio, 2**0.25, rel_tol=1e-9)

    def test_gain_scaling(self):
        """6 dB more gain → range increases by 10^(3/10).

        R ~ G^(1/2), and +6 dB = 10^(6/10) linear gain ratio,
        so range ratio = (10^(6/10))^(1/2) = 10^(3/10) = 1.9953.
        """
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        r2 = compute_radar_range(1000.0, 36.0, 10e9, 1.0)
        ratio = r2["max_range_m"] / r1["max_range_m"]
        expected = 10 ** (3 / 10)  # exact: (10^(6/10))^(1/2)
        assert math.isclose(ratio, expected, rel_tol=1e-9)

    def test_rcs_scaling(self):
        """10x RCS → 10^(1/4) = 1.778x range increase."""
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        r2 = compute_radar_range(1000.0, 30.0, 10e9, 10.0)
        ratio = r2["max_range_m"] / r1["max_range_m"]
        assert math.isclose(ratio, 10**0.25, rel_tol=1e-6)

    def test_noise_temp_effect(self):
        """Doubling T_s decreases R_max by 2^(1/4).

        S_min ~ T_s, so R_max ~ T_s^(-1/4).
        """
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, system_noise_temp_k=290.0)
        r2 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, system_noise_temp_k=580.0)
        ratio = r1["max_range_m"] / r2["max_range_m"]
        assert math.isclose(ratio, 2**0.25, rel_tol=1e-9)

    def test_wavelength_computed_correctly(self):
        """wavelength_m = c / frequency_hz."""
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        expected = SPEED_OF_LIGHT.magnitude / 10e9
        assert math.isclose(result["wavelength_m"], expected, rel_tol=1e-12)

    def test_s_min_matches_ktb_snr(self):
        """S_min = k_B * T * B * SNR_min / N_pulses."""
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        k_b = BOLTZMANN.magnitude
        expected = k_b * 290.0 * 1e6 * db_to_linear(13.0)
        assert math.isclose(result["min_detectable_power_w"], expected, rel_tol=1e-9)

    def test_output_has_required_keys(self):
        """All expected keys are present in the output dict."""
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        required = [
            "max_range_m",
            "max_range_km",
            "wavelength_m",
            "min_detectable_power_w",
            "min_detectable_power_dbm",
            "antenna_gain_linear",
            "snr_min_linear",
            "integration_gain",
            "losses_linear",
            "warnings",
            "human_readable",
            "latex",
        ]
        for key in required:
            assert key in result

    def test_human_readable_content(self):
        """Human-readable output contains key information."""
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        assert "Radar Range" in result["human_readable"]
        assert "Max Range" in result["human_readable"]

    def test_latex_content(self):
        """LaTeX output contains the radar range equation."""
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        assert "R_{" in result["latex"]
        assert "4\\pi" in result["latex"]


class TestRadarRangeValidation:
    """Claimed range validation and input rejection tests."""

    def test_claimed_range_below_max_passes(self):
        """Claimed range at 50% of R_max does not raise."""
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        half_max = result["max_range_m"] * 0.5
        result2 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, claimed_range_m=half_max)
        assert "max_range_m" in result2

    def test_claimed_range_above_max_raises(self):
        """Claimed range at 2x R_max raises PhysicalViolationError."""
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0)
        double_max = result["max_range_m"] * 2.0
        with pytest.raises(PhysicalViolationError, match="Radar Range"):
            compute_radar_range(1000.0, 30.0, 10e9, 1.0, claimed_range_m=double_max)

    def test_zero_power_rejects(self):
        with pytest.raises(PhysicalViolationError, match="positive"):
            compute_radar_range(0.0, 30.0, 10e9, 1.0)

    def test_negative_rcs_rejects(self):
        with pytest.raises(PhysicalViolationError):
            compute_radar_range(1000.0, 30.0, 10e9, -1.0)

    def test_zero_frequency_rejects(self):
        with pytest.raises(PhysicalViolationError):
            compute_radar_range(1000.0, 30.0, 0.0, 1.0)

    def test_negative_temperature_rejects(self):
        with pytest.raises(PhysicalViolationError):
            compute_radar_range(1000.0, 30.0, 10e9, 1.0, system_noise_temp_k=-1.0)

    def test_zero_bandwidth_rejects(self):
        with pytest.raises(PhysicalViolationError):
            compute_radar_range(1000.0, 30.0, 10e9, 1.0, noise_bandwidth_hz=0.0)

    def test_zero_pulses_rejects(self):
        with pytest.raises(PhysicalViolationError, match="pulses"):
            compute_radar_range(1000.0, 30.0, 10e9, 1.0, num_pulses=0)

    def test_negative_losses_rejects(self):
        with pytest.raises(PhysicalViolationError, match="losses"):
            compute_radar_range(1000.0, 30.0, 10e9, 1.0, losses_db=-1.0)


class TestRadarRangeWarnings:
    """Warning generation tests."""

    def test_high_frequency_warning(self):
        result = compute_radar_range(1000.0, 30.0, 400e9, 1.0)
        assert any("300 GHz" in w for w in result["warnings"])

    def test_large_rcs_warning(self):
        result = compute_radar_range(1000.0, 30.0, 10e9, 150.0)
        assert any("100 m^2" in w for w in result["warnings"])

    def test_small_rcs_warning(self):
        result = compute_radar_range(1000.0, 30.0, 10e9, 1e-5)
        assert any("0.0001" in w for w in result["warnings"])

    def test_multi_pulse_warning(self):
        result = compute_radar_range(1000.0, 30.0, 10e9, 1.0, num_pulses=10)
        assert any("Coherent" in w for w in result["warnings"])


class TestRadarRangePulseIntegration:
    """Pulse integration gain tests."""

    def test_integration_increases_range(self):
        """N pulses increases range by N^(1/4)."""
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, num_pulses=1)
        r16 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, num_pulses=16)
        ratio = r16["max_range_m"] / r1["max_range_m"]
        assert math.isclose(ratio, 16**0.25, rel_tol=1e-9)


class TestRadarRangeLosses:
    """System loss effect tests."""

    def test_losses_decrease_range(self):
        r_no_loss = compute_radar_range(1000.0, 30.0, 10e9, 1.0, losses_db=0.0)
        r_loss = compute_radar_range(1000.0, 30.0, 10e9, 1.0, losses_db=3.0)
        assert r_loss["max_range_m"] < r_no_loss["max_range_m"]

    def test_3db_loss_effect(self):
        """3 dB loss halves effective power, reducing range by 2^(-1/4) = 0.841."""
        r1 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, losses_db=0.0)
        r2 = compute_radar_range(1000.0, 30.0, 10e9, 1.0, losses_db=3.0)
        ratio = r2["max_range_m"] / r1["max_range_m"]
        assert math.isclose(ratio, 2 ** (-0.25), rel_tol=1e-3)
