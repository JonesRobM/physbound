"""Tests for Shannon-Hartley channel capacity and throughput validation."""

import math

import pytest

from physbound.engines.shannon import (
    channel_capacity_bps,
    snr_db_to_linear,
    spectral_efficiency,
    validate_throughput_claim,
)
from physbound.errors import PhysicalViolationError

DB_TOL = 0.01


class TestChannelCapacity:
    def test_snr_0db(self):
        """C(B=1MHz, SNR=0dB=1 linear) = 1MHz * log2(2) = 1 Mbps."""
        c = channel_capacity_bps(1e6, 1.0)  # SNR=1 linear = 0 dB
        assert abs(c - 1e6) < 1.0

    def test_wifi_like_scenario(self):
        """C(B=20MHz, SNR=30dB) ≈ 199.3 Mbps."""
        snr_linear = snr_db_to_linear(30.0)  # 1000 linear
        c = channel_capacity_bps(20e6, snr_linear)
        expected = 20e6 * math.log2(1001)  # ≈ 199.3 Mbps
        assert abs(c - expected) < 1.0

    def test_high_snr(self):
        """At very high SNR, capacity scales linearly with bandwidth."""
        snr = snr_db_to_linear(60.0)
        c1 = channel_capacity_bps(1e6, snr)
        c2 = channel_capacity_bps(2e6, snr)
        assert abs(c2 / c1 - 2.0) < 0.001

    def test_zero_bandwidth_rejects(self):
        with pytest.raises(PhysicalViolationError):
            channel_capacity_bps(0, 10.0)

    def test_zero_snr_rejects(self):
        with pytest.raises(PhysicalViolationError):
            channel_capacity_bps(1e6, 0)


class TestSpectralEfficiency:
    def test_snr_0db(self):
        """eta at SNR=1 linear (0dB) = log2(2) = 1 bps/Hz."""
        eta = spectral_efficiency(1.0)
        assert abs(eta - 1.0) < 1e-10

    def test_snr_10db(self):
        """eta at SNR=10 linear (10dB) = log2(11) ≈ 3.459 bps/Hz."""
        eta = spectral_efficiency(10.0)
        assert abs(eta - math.log2(11)) < 1e-10


class TestSnrConversion:
    def test_0db(self):
        assert abs(snr_db_to_linear(0) - 1.0) < 1e-10

    def test_10db(self):
        assert abs(snr_db_to_linear(10) - 10.0) < 1e-10

    def test_30db(self):
        assert abs(snr_db_to_linear(30) - 1000.0) < 1e-6


class TestThroughputValidation:
    def test_valid_claim_below_limit(self):
        """A claim below Shannon limit should pass."""
        snr = snr_db_to_linear(15.0)
        capacity = channel_capacity_bps(20e6, snr)
        result = validate_throughput_claim(20e6, snr, capacity * 0.5)
        assert result["claim_is_valid"] is True
        assert result["excess_percentage"] == 0.0

    def test_valid_claim_at_limit(self):
        """A claim exactly at Shannon limit should pass."""
        snr = snr_db_to_linear(15.0)
        capacity = channel_capacity_bps(20e6, snr)
        result = validate_throughput_claim(20e6, snr, capacity)
        assert result["claim_is_valid"] is True

    def test_impossible_claim_above_limit(self):
        """A claim exceeding Shannon limit must raise PhysicalViolationError."""
        snr = snr_db_to_linear(15.0)
        capacity = channel_capacity_bps(20e6, snr)
        with pytest.raises(PhysicalViolationError, match="Shannon-Hartley") as exc_info:
            validate_throughput_claim(20e6, snr, capacity * 1.5)
        assert exc_info.value.computed_limit == pytest.approx(capacity)
        assert "exceeds" in exc_info.value.latex_explanation

    def test_wifi_hallucination(self):
        """Classic hallucination: 500 Mbps on 20 MHz, 15 dB SNR."""
        snr = snr_db_to_linear(15.0)
        with pytest.raises(PhysicalViolationError) as exc_info:
            validate_throughput_claim(20e6, snr, 500e6)
        err = exc_info.value
        assert err.claimed_value == 500e6
        assert err.computed_limit < 500e6

    def test_high_spectral_efficiency_warning(self):
        """Claims with eta > 20 bps/Hz should produce a warning."""
        snr = snr_db_to_linear(70.0)  # extremely high SNR
        capacity = channel_capacity_bps(1e6, snr)
        # Claim just under the limit but with very high eta
        result = validate_throughput_claim(1e6, snr, capacity * 0.99)
        claimed_eta = (capacity * 0.99) / 1e6
        if claimed_eta > 20:
            assert len(result["warnings"]) > 0
