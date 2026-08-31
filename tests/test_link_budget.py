"""Tests for RF link budget calculations: FSPL, Friis, and aperture limits."""

import math

import pytest

from physbound.engines.link_budget import (
    compute_link_budget,
    free_space_path_loss_db,
    harrington_gain_limit_dbi,
    max_aperture_gain_dbi,
    physical_aperture_gain_limit_dbi,
    physical_gain_limit_dbi,
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

    def test_aperture_limit_is_eta_one(self):
        """G_ap = (pi D / lambda)^2: 0.3 m at 1 GHz (lambda = 0.2998 m) -> 9.95 dBi."""
        g_ap = physical_aperture_gain_limit_dbi(0.3, 1e9)
        expected = 10 * math.log10((math.pi * 0.3 / (299792458 / 1e9)) ** 2)
        assert abs(g_ap - expected) < 1e-9
        assert abs(g_ap - 9.95) < DB_TOL
        # typical limit is exactly 10*log10(0.55) = -2.60 dB below the eta = 1 aperture value
        g_typ = max_aperture_gain_dbi(0.3, 1e9)
        assert abs((g_ap - g_typ) - (-10 * math.log10(0.55))) < 1e-9

    def test_harrington_limit_reference_values(self):
        """D_max = (ka)^2 + 2ka, a = D/2: 0.1 m @ 900 MHz -> 4.43 dBi; 0.3 m @ 1 GHz -> 12.09."""
        c = 299792458
        ka = math.pi * 0.1 * 900e6 / c  # 0.943
        expected = 10 * math.log10(ka**2 + 2 * ka)
        assert abs(harrington_gain_limit_dbi(0.1, 900e6) - expected) < 1e-9
        assert abs(harrington_gain_limit_dbi(0.1, 900e6) - 4.43) < 0.01
        assert abs(harrington_gain_limit_dbi(0.3, 1e9) - 12.09) < 0.01

    def test_physical_limit_is_max_of_aperture_and_harrington(self):
        """The hard limit is max(G_ap, D_max); since D_max = (ka)^2 + 2ka > (ka)^2 it is D_max."""
        for d, f in [(0.1, 900e6), (0.3, 1e9), (1.0, 10e9), (30.0, 1e9)]:
            g_ap = physical_aperture_gain_limit_dbi(d, f)
            g_h = harrington_gain_limit_dbi(d, f)
            g_phys = physical_gain_limit_dbi(d, f)
            assert g_phys == max(g_ap, g_h) == g_h
            assert g_h > g_ap

    def test_large_dish_limit_converges_to_aperture_value(self):
        """For D >> lambda the 2ka term is negligible: 1 m @ 10 GHz differs by 0.08 dB,
        a 30 m dish at 1 GHz by 0.03 dB, so large dishes are effectively unchanged."""
        assert (
            abs(physical_gain_limit_dbi(1.0, 10e9) - physical_aperture_gain_limit_dbi(1.0, 10e9))
            < 0.09
        )
        assert (
            abs(physical_gain_limit_dbi(30.0, 1e9) - physical_aperture_gain_limit_dbi(30.0, 1e9))
            < 0.03
        )
        # electrically small: the correction is decisive (> 2 dB)
        assert (
            physical_gain_limit_dbi(0.1, 900e6) - physical_aperture_gain_limit_dbi(0.1, 900e6) > 4.9
        )

    def test_efficiency_above_one_rejects(self):
        """eta > 1 means A_e > A_phys, which is impossible."""
        with pytest.raises(PhysicalViolationError, match="efficiency"):
            max_aperture_gain_dbi(0.3, 1e9, efficiency=1.2)

    def test_efficiency_non_positive_rejects(self):
        with pytest.raises(PhysicalViolationError, match="efficiency"):
            max_aperture_gain_dbi(0.3, 1e9, efficiency=0.0)

    def test_gain_validation_passes(self):
        """Claiming 7 dBi on a 0.3m dish at 1 GHz passes with no efficiency warning."""
        check = validate_antenna_gain(7.0, 0.3, 1e9, "test")
        assert (
            check["physical_limit_dbi"] > check["aperture_limit_dbi"] > check["typical_limit_dbi"]
        )
        assert check["typical_limit_dbi"] > 7.0
        assert check["implied_efficiency"] < 0.55
        assert check["warnings"] == []

    def test_gain_between_typical_and_physical_warns(self):
        """1 m dish at 10 GHz: eta=0.55 -> 37.8 dBi, eta=1 -> 40.4 dBi.

        A 39 dBi claim needs eta = 10^((39 - 40.4)/10) = 0.72: allowed, but flagged.
        """
        check = validate_antenna_gain(39.0, 1.0, 10e9, "test")
        assert check["typical_limit_dbi"] < 39.0 < check["aperture_limit_dbi"]
        assert check["limiting_bound"] == "aperture"
        assert (
            abs(check["implied_efficiency"] - 10 ** ((39.0 - check["aperture_limit_dbi"]) / 10))
            < 1e-12
        )
        assert 0.55 < check["implied_efficiency"] < 1.0
        assert any("typical-efficiency" in w for w in check["warnings"])
        assert any("eta = 0.72" in w for w in check["warnings"])

    def test_gain_validation_rejects_above_physical(self):
        """Claiming 45 dBi on a 0.3m dish at 1 GHz must fail against the Harrington bound (12.1)."""
        with pytest.raises(PhysicalViolationError, match="Aperture") as exc_info:
            validate_antenna_gain(45.0, 0.3, 1e9, "test")
        assert abs(exc_info.value.computed_limit - physical_gain_limit_dbi(0.3, 1e9)) < 1e-12
        assert abs(exc_info.value.computed_limit - 12.09) < 0.01
        assert exc_info.value.claimed_value == 45.0
        assert "Harrington" in exc_info.value.message
        assert "eta = 1" in exc_info.value.message
        assert "(ka)^2 + 2ka" in exc_info.value.latex_explanation

    def test_gain_just_above_physical_rejects(self):
        """A claim 0.1 dB over the hard bound is rejected even though eta=0.55 is far below."""
        g_phys = physical_gain_limit_dbi(1.0, 10e9)
        with pytest.raises(PhysicalViolationError, match="Aperture"):
            validate_antenna_gain(g_phys + 0.1, 1.0, 10e9, "test")
        # exactly at the bound passes
        check = validate_antenna_gain(g_phys, 1.0, 10e9, "test")
        assert check["physical_limit_dbi"] == g_phys
        # a 1 m dish at 10 GHz: the Harrington bound sits 0.08 dB above the eta = 1 aperture value
        assert 1.0 < check["implied_efficiency"] < 1.02

    def test_between_aperture_and_harrington_warns_not_raises(self):
        """A claim between (pi D/lambda)^2 and (ka)^2 + 2ka is valid but flagged as non-planar."""
        g_ap = physical_aperture_gain_limit_dbi(0.3, 1e9)  # 9.95 dBi
        check = validate_antenna_gain(11.0, 0.3, 1e9, "test")
        assert g_ap < 11.0 < check["physical_limit_dbi"]
        assert check["implied_efficiency"] > 1.0
        assert any("Harrington" in w and "planar-aperture" in w for w in check["warnings"])
        assert not any("typical-efficiency" in w for w in check["warnings"])

    def test_custom_efficiency_threshold(self):
        """The warning threshold follows the efficiency parameter."""
        # 39 dBi on 1 m @ 10 GHz needs eta = 0.72: warns at 0.55, not at 0.8
        assert any(
            "typical-efficiency" in w
            for w in validate_antenna_gain(39.0, 1.0, 10e9, efficiency=0.55)["warnings"]
        )
        assert not any(
            "typical-efficiency" in w
            for w in validate_antenna_gain(39.0, 1.0, 10e9, efficiency=0.8)["warnings"]
        )

    def test_limiting_bound_regime_label(self):
        """D < lambda reports 'harrington'; D >= lambda reports 'aperture'."""
        check = validate_antenna_gain(-4.0, 0.1, 900e6, "test")  # below typical -3.1 dBi
        assert check["limiting_bound"] == "harrington"
        assert check["warnings"] == []
        check_big = validate_antenna_gain(30.0, 1.0, 10e9, "test")
        assert check_big["limiting_bound"] == "aperture"
        assert check_big["warnings"] == []
        # exactly D = lambda is the aperture regime
        lam = 299792458 / 1e9
        assert validate_antenna_gain(0.0, lam, 1e9, "test")["limiting_bound"] == "aperture"

    def test_half_wave_dipole_in_small_footprint_is_valid(self):
        """A 2.15 dBi half-wave dipole fits a 0.1 m footprint at 900 MHz (lambda = 0.333 m).

        The eta = 1 aperture value is -0.5 dBi, which would falsely reject it; the
        Harrington bound (ka)^2 + 2ka = 4.4 dBi admits it.
        """
        check = validate_antenna_gain(2.15, 0.1, 900e6, "dipole")
        assert abs(check["aperture_limit_dbi"] - (-0.51)) < 0.01
        assert abs(check["harrington_limit_dbi"] - 4.43) < 0.01
        assert check["physical_limit_dbi"] == check["harrington_limit_dbi"]
        assert check["limiting_bound"] == "harrington"
        assert abs(check["implied_efficiency"] - 1.84) < 0.01
        assert any("Harrington" in w for w in check["warnings"])
        # and in a full link budget
        result = compute_link_budget(
            tx_power_dbm=20,
            tx_antenna_gain_dbi=2.15,
            rx_antenna_gain_dbi=2.15,
            frequency_hz=900e6,
            distance_m=1000,
            tx_antenna_diameter_m=0.1,
            rx_antenna_diameter_m=0.1,
        )
        assert result["tx_limiting_bound"] == result["rx_limiting_bound"] == "harrington"
        assert abs(result["tx_physical_limit_dbi"] - 4.43) < 0.01
        assert abs(result["tx_aperture_limit_dbi"] - (-0.51)) < 0.01
        # 5 dBi still fails: above the Harrington bound
        with pytest.raises(PhysicalViolationError, match="Aperture"):
            compute_link_budget(20, 5.0, 0, 900e6, 1000, tx_antenna_diameter_m=0.1)


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

    def test_negative_tx_loss_rejects(self):
        """Negative loss is free energy: rejected like radar.py's losses_db."""
        with pytest.raises(PhysicalViolationError, match="Conservation of Energy"):
            compute_link_budget(20, 10, 3, 2.4e9, 100, tx_losses_db=-1.0)

    def test_negative_rx_loss_rejects(self):
        with pytest.raises(PhysicalViolationError, match="Conservation of Energy"):
            compute_link_budget(20, 10, 3, 2.4e9, 100, rx_losses_db=-0.5)

    def test_zero_losses_allowed(self):
        result = compute_link_budget(20, 10, 3, 2.4e9, 100, tx_losses_db=0.0, rx_losses_db=0.0)
        assert "received_power_dbm" in result

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

    def test_aperture_limits_reported(self):
        """The hard limit, the eta=1 aperture value and the eta=0.55 gain are returned per dish."""
        result = compute_link_budget(
            tx_power_dbm=20,
            tx_antenna_gain_dbi=35,
            rx_antenna_gain_dbi=35,
            frequency_hz=10e9,
            distance_m=50_000,
            tx_antenna_diameter_m=1.0,
            rx_antenna_diameter_m=1.0,
        )
        g_ap = physical_aperture_gain_limit_dbi(1.0, 10e9)
        g_phys = physical_gain_limit_dbi(1.0, 10e9)
        g_typ = max_aperture_gain_dbi(1.0, 10e9)
        assert abs(result["tx_physical_limit_dbi"] - g_phys) < 1e-9
        assert abs(result["rx_physical_limit_dbi"] - g_phys) < 1e-9
        assert abs(result["tx_aperture_limit_dbi"] - g_ap) < 1e-9
        assert abs(result["rx_aperture_limit_dbi"] - g_ap) < 1e-9
        assert abs(result["tx_typical_aperture_gain_dbi"] - g_typ) < 1e-9
        assert abs(result["rx_typical_aperture_gain_dbi"] - g_typ) < 1e-9
        assert result["tx_limiting_bound"] == result["rx_limiting_bound"] == "aperture"
        assert result["aperture_efficiency"] == 0.55
        assert result["warnings"] == []

    def test_limit_fields_none_without_diameters(self):
        result = compute_link_budget(20, 10, 3, 2.4e9, 100)
        for key in (
            "tx_physical_limit_dbi",
            "rx_physical_limit_dbi",
            "tx_aperture_limit_dbi",
            "rx_aperture_limit_dbi",
            "tx_limiting_bound",
            "rx_limiting_bound",
        ):
            assert result[key] is None

    def test_aperture_typical_efficiency_warning_in_budget(self):
        """39 dBi on a 1 m dish at 10 GHz is allowed (eta=0.76) but warned."""
        result = compute_link_budget(
            tx_power_dbm=20,
            tx_antenna_gain_dbi=39,
            rx_antenna_gain_dbi=0,
            frequency_hz=10e9,
            distance_m=50_000,
            tx_antenna_diameter_m=1.0,
        )
        assert any("TX antenna" in w and "typical-efficiency" in w for w in result["warnings"])

    def test_rx_aperture_rejection(self):
        with pytest.raises(PhysicalViolationError, match="RX antenna"):
            compute_link_budget(20, 0, 45, 1e9, 1000, rx_antenna_diameter_m=0.3)

    def test_near_field_warning(self):
        """Friis assumes d > 2 D^2 / lambda; warn when inside the Fraunhofer distance."""
        # 1 m dish at 10 GHz: 2 D^2 / lambda = 2 / 0.03 = 66.7 m
        result = compute_link_budget(20, 30, 0, 10e9, 10.0, tx_antenna_diameter_m=1.0)
        assert any("Fraunhofer" in w for w in result["warnings"])
        far = compute_link_budget(20, 30, 0, 10e9, 1000.0, tx_antenna_diameter_m=1.0)
        assert not any("Fraunhofer" in w for w in far["warnings"])

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
