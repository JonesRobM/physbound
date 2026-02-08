"""Tests for thermal noise, Friis noise cascade, and receiver sensitivity."""

import math

import pytest

from physbound.engines.noise import (
    friis_noise_cascade,
    receiver_sensitivity_dbm,
    thermal_noise_power_dbm,
    thermal_noise_power_watts,
)
from physbound.errors import PhysicalViolationError

DB_TOL = 0.01


class TestThermalNoisePower:
    def test_anchor_point_290k_1hz(self):
        """kTB at 290K, 1Hz = -174 dBm/Hz (the RF anchor point)."""
        n = thermal_noise_power_dbm(1.0, 290.0)
        assert abs(n - (-174.0)) < 0.03  # -173.977...

    def test_290k_1mhz(self):
        """kTB at 290K, 1MHz = -114 dBm."""
        n = thermal_noise_power_dbm(1e6, 290.0)
        expected = -174.0 + 10.0 * math.log10(1e6)  # -174 + 60 = -114
        assert abs(n - expected) < 0.03

    def test_290k_20mhz(self):
        """kTB at 290K, 20MHz = -101 dBm."""
        n = thermal_noise_power_dbm(20e6, 290.0)
        expected = -174.0 + 10.0 * math.log10(20e6)  # -174 + 73.01 = -100.99
        assert abs(n - expected) < 0.03

    def test_watts_consistency(self):
        """Watts and dBm computations must agree."""
        bw = 1e6
        n_watts = thermal_noise_power_watts(bw, 290.0)
        n_dbm = thermal_noise_power_dbm(bw, 290.0)
        n_dbm_from_watts = 10.0 * math.log10(n_watts / 1e-3)
        assert abs(n_dbm - n_dbm_from_watts) < 1e-10

    def test_zero_temperature(self):
        """0K should produce -inf noise (no thermal energy)."""
        n = thermal_noise_power_dbm(1e6, 0.0)
        assert n == float("-inf")

    def test_negative_temperature_rejects(self):
        with pytest.raises(PhysicalViolationError, match="Third Law"):
            thermal_noise_power_dbm(1e6, -1.0)

    def test_zero_bandwidth_rejects(self):
        with pytest.raises(PhysicalViolationError):
            thermal_noise_power_dbm(0, 290.0)


class TestFriisNoiseCascade:
    def test_single_stage(self):
        """Single stage: cascaded NF = stage NF."""
        nf = friis_noise_cascade([(20.0, 3.0)])
        assert abs(nf - 3.0) < DB_TOL

    def test_two_stage_lna_first(self):
        """LNA (NF=1dB, G=20dB) -> mixer (NF=10dB, G=0dB).
        F_total = F_1 + (F_2-1)/G_1
        F_1 = 10^(1/10) = 1.2589
        F_2 = 10^(10/10) = 10.0
        G_1 = 10^(20/10) = 100.0
        F_total = 1.2589 + (10 - 1)/100 = 1.2589 + 0.09 = 1.3489
        NF_total = 10*log10(1.3489) = 1.299 dB
        """
        nf = friis_noise_cascade([(20.0, 1.0), (0.0, 10.0)])
        expected = 10.0 * math.log10(1.2589 + 9.0 / 100.0)
        assert abs(nf - expected) < DB_TOL

    def test_order_matters(self):
        """Swapping LNA and mixer should give worse NF."""
        nf_good = friis_noise_cascade([(20.0, 1.0), (0.0, 10.0)])
        nf_bad = friis_noise_cascade([(0.0, 10.0), (20.0, 1.0)])
        assert nf_bad > nf_good  # bad order has much higher NF

    def test_three_stages(self):
        """Three-stage cascade manual verification."""
        stages = [(20.0, 2.0), (10.0, 6.0), (15.0, 8.0)]
        nf = friis_noise_cascade(stages)
        # Manual: F1=1.585, F2=3.981, F3=6.310, G1=100, G2=10
        # F_total = 1.585 + (3.981-1)/100 + (6.310-1)/(100*10)
        #         = 1.585 + 0.02981 + 0.005310 = 1.6201
        # NF = 10*log10(1.6201) = 2.097 dB
        f1 = 10 ** (2.0 / 10)
        f2 = 10 ** (6.0 / 10)
        f3 = 10 ** (8.0 / 10)
        g1 = 10 ** (20.0 / 10)
        g2 = 10 ** (10.0 / 10)
        expected = 10.0 * math.log10(f1 + (f2 - 1) / g1 + (f3 - 1) / (g1 * g2))
        assert abs(nf - expected) < DB_TOL

    def test_empty_stages_rejects(self):
        with pytest.raises(PhysicalViolationError, match="At least one"):
            friis_noise_cascade([])

    def test_negative_nf_rejects(self):
        with pytest.raises(PhysicalViolationError, match="quantum"):
            friis_noise_cascade([(20.0, -1.0)])


class TestReceiverSensitivity:
    def test_basic_sensitivity(self):
        """S_min = N_floor + NF + SNR_req."""
        # At 290K, 1MHz: N_floor ≈ -114 dBm
        # NF = 6 dB, SNR_req = 10 dB
        # S_min ≈ -114 + 6 + 10 = -98 dBm
        s = receiver_sensitivity_dbm(1e6, 6.0, 10.0)
        expected = thermal_noise_power_dbm(1e6, 290.0) + 6.0 + 10.0
        assert abs(s - expected) < 1e-10
