"""Tests for hard-limit guard functions."""

import pytest

from physbound.errors import PhysicalViolationError
from physbound.validators import (
    validate_positive_bandwidth,
    validate_positive_distance,
    validate_positive_frequency,
    validate_positive_power,
    validate_positive_rcs,
    validate_positive_snr,
    validate_temperature,
)


class TestPositiveFrequency:
    def test_valid(self):
        validate_positive_frequency(1e9)

    def test_zero_rejects(self):
        with pytest.raises(PhysicalViolationError, match="positive"):
            validate_positive_frequency(0)

    def test_negative_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_frequency(-1e9)


class TestPositiveDistance:
    def test_valid(self):
        validate_positive_distance(1000)

    def test_zero_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_distance(0)

    def test_negative_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_distance(-100)


class TestPositiveBandwidth:
    def test_valid(self):
        validate_positive_bandwidth(20e6)

    def test_zero_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_bandwidth(0)


class TestTemperature:
    def test_valid_290k(self):
        validate_temperature(290)

    def test_zero_k_valid(self):
        validate_temperature(0)

    def test_negative_rejects(self):
        with pytest.raises(PhysicalViolationError, match="Third Law"):
            validate_temperature(-1)


class TestPositiveSNR:
    def test_valid(self):
        validate_positive_snr(10.0)

    def test_zero_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_snr(0)

    def test_negative_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_snr(-1.0)


class TestPositivePower:
    def test_valid(self):
        validate_positive_power(1000.0)

    def test_zero_rejects(self):
        with pytest.raises(PhysicalViolationError, match="positive"):
            validate_positive_power(0)

    def test_negative_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_power(-100.0)


class TestPositiveRCS:
    def test_valid(self):
        validate_positive_rcs(1.0)

    def test_zero_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_rcs(0)

    def test_negative_rejects(self):
        with pytest.raises(PhysicalViolationError):
            validate_positive_rcs(-0.5)


class TestErrorSerialization:
    def test_to_dict_structure(self):
        err = PhysicalViolationError(
            message="Test violation",
            law_violated="Test Law",
            latex_explanation=r"$E = mc^2$",
            computed_limit=100.0,
            claimed_value=200.0,
            unit="dBm",
        )
        d = err.to_dict()
        assert d["error"] is True
        assert d["violation_type"] == "PhysicalViolationError"
        assert d["law_violated"] == "Test Law"
        assert d["latex"] == r"$E = mc^2$"
        assert d["computed_limit"] == 100.0
        assert d["claimed_value"] == 200.0
        assert d["unit"] == "dBm"
