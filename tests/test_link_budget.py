"""Tests for RF link budget calculations: FSPL, Friis, and aperture limits."""

import math

import pytest

from physbound.engines.link_budget import (
    compute_link_budget,
    free_space_path_loss_db,
    max_aperture_gain_dbi,
    validate_antenna_gain,
)
from physbound.errors import PhysicalViolationError

DB_TOL = 0.1


class TestFreeSpacePathLoss:
    def test_1ghz_1km(self):
        """FSPL at 1 GHz, 1 km ≈ 92.45 dB (standard reference)."""
        fspl = free_space_path_loss_db(1e9, 1000)
        assert abs(fspl - 92.45) < DB_TOL

    def test_2_4ghz_100m(self):
        """FSPL at 2.4 GHz, 100 m ≈ 80.0 dB (Wi-Fi reference)."""
        fspl = free_space_path_loss_db(2.4e9, 100)
        assert abs(fspl - 80.0) < DB_TOL

    def test_5ghz_10m(self):
        """FSPL at 5 GHz, 10 m ≈ 66.4 dB."""
        fspl = free_space_path_loss_db(5e9, 10)
        # Manual: 20*log10(10) + 20*log10(5e9) + 20*log10(4*pi/c)
        #       = 20 + 194.0 + (-147.55) = 66.4
        expected = (
            20 * math.log10(10) + 20 * math.log10(5e9) + 20 * math.log10(4 * math.pi / 299792458)
        )
        assert abs(fspl - expected) < 0.001

    def test_fspl_doubles_with_frequency(self):
        """Doubling frequency adds ~6 dB to FSPL."""
        fspl1 = free_space_path_loss_db(1e9, 1000)
        fspl2 = free_space_path_loss_db(2e9, 1000)
        assert abs((fspl2 - fspl1) - 6.02) < DB_TOL

    def test_fspl_doubles_with_distance(self):
        """Doubling distance adds ~6 dB to FSPL."""
        fspl1 = free_space_path_loss_db(1e9, 500)
        fspl2 = free_space_path_loss_db(1e9, 1000)
        assert abs((fspl2 - fspl1) - 6.02) < DB_TOL

    def test_zero_frequency_rejects(self):
        with pytest.raises(PhysicalViolationError):
            free_space_path_loss_db(0, 1000)

    def test_negative_distance_rejects(self):
        with pytest.raises(PhysicalViolationError):
            free_space_path_loss_db(1e9, -100)


class TestApertureGain:
    def test_1m_dish_at_10ghz(self):
        """1m dish at 10 GHz, eta=0.55: G_max ≈ 37.6 dBi."""
        c = 299792458
        wavelength = c / 10e9
        g_linear = 0.55 * (math.pi * 1.0 / wavelength) ** 2
        expected = 10 * math.log10(g_linear)
        g = max_aperture_gain_dbi(1.0, 10e9)
        assert abs(g - expected) < DB_TOL

    def test_small_dish_low_freq(self):
        """0.3m dish at 1 GHz: G_max ≈ 7.3 dBi (small dish, low freq)."""
        g = max_aperture_gain_dbi(0.3, 1e9)
        # lambda = 0.3 m, so D/lambda = 1, G = 0.55 * pi^2 = 5.43 -> 7.35 dBi
        expected = 10 * math.log10(0.55 * math.pi**2)
        assert abs(g - expected) < DB_TOL

    def test_gain_validation_passes(self):
        """Claiming 7 dBi on a 0.3m dish at 1 GHz should pass."""
        g_max = validate_antenna_gain(7.0, 0.3, 1e9, "test")
        assert g_max > 7.0

    def test_gain_validation_rejects(self):
        """Claiming 45 dBi on a 0.3m dish at 1 GHz must fail."""
        with pytest.raises(PhysicalViolationError, match="Aperture") as exc_info:
            validate_antenna_gain(45.0, 0.3, 1e9, "test")
        assert exc_info.value.computed_limit < 45.0
        assert exc_info.value.claimed_value == 45.0


class TestLinkBudget:
    def test_basic_link_budget(self):
        """P_rx = P_tx + G_tx + G_rx - FSPL."""
        result = compute_link_budget(
            tx_power_dbm=20.0,
            tx_antenna_gain_dbi=10.0,
            rx_antenna_gain_dbi=3.0,
            frequency_hz=2.4e9,
            distance_m=100.0,
        )
        fspl = free_space_path_loss_db(2.4e9, 100.0)
        expected_prx = 20.0 + 10.0 + 3.0 - fspl
        assert abs(result["received_power_dbm"] - expected_prx) < 0.001
        assert abs(result["fspl_db"] - fspl) < 0.001

    def test_with_losses(self):
        """Losses reduce received power."""
        no_loss = compute_link_budget(20, 10, 3, 2.4e9, 100)
        with_loss = compute_link_budget(20, 10, 3, 2.4e9, 100, tx_losses_db=2, rx_losses_db=1)
        assert abs(no_loss["received_power_dbm"] - with_loss["received_power_dbm"] - 3.0) < 0.001

    def test_aperture_rejection(self):
        """Impossible antenna gain triggers PhysicalViolationError."""
        with pytest.raises(PhysicalViolationError, match="Aperture"):
            compute_link_budget(
                tx_power_dbm=20,
                tx_antenna_gain_dbi=45,
                rx_antenna_gain_dbi=0,
                frequency_hz=1e9,
                distance_m=1000,
                tx_antenna_diameter_m=0.3,
            )

    def test_high_frequency_warning(self):
        """Frequencies above 300 GHz should produce a warning."""
        result = compute_link_budget(20, 10, 3, 400e9, 10)
        assert any("300 GHz" in w for w in result["warnings"])

    def test_output_has_required_keys(self):
        """Output dict must contain all expected keys."""
        result = compute_link_budget(20, 10, 3, 2.4e9, 100)
        required = [
            "fspl_db",
            "received_power_dbm",
            "wavelength_m",
            "warnings",
            "human_readable",
            "latex",
        ]
        for key in required:
            assert key in result

    def test_human_readable_present(self):
        result = compute_link_budget(20, 10, 3, 2.4e9, 100)
        assert "Link Budget" in result["human_readable"]
        assert "dBm" in result["human_readable"]

    def test_latex_present(self):
        result = compute_link_budget(20, 10, 3, 2.4e9, 100)
        assert "P_{" in result["latex"]
        assert "FSPL" in result["latex"]
