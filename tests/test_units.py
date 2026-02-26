"""Tests for unit conversion and dimensional analysis helpers."""

import pytest

from physbound.engines.constants import Q_, ureg
from physbound.engines.units import (
    db_to_linear,
    dbm_to_watts,
    frequency_to_wavelength,
    linear_to_db,
    validate_dimensions,
    watts_to_dbm,
)
from physbound.errors import PhysicalViolationError


class TestWattsToDbm:
    def test_one_watt(self):
        """1 W = 30 dBm."""
        assert abs(watts_to_dbm(Q_(1.0, "watt")) - 30.0) < 0.001

    def test_one_milliwatt(self):
        """1 mW = 0 dBm."""
        assert abs(watts_to_dbm(Q_(1e-3, "watt")) - 0.0) < 0.001

    def test_one_microwatt(self):
        """1 µW = -30 dBm."""
        assert abs(watts_to_dbm(Q_(1e-6, "watt")) - (-30.0)) < 0.001

    def test_milliwatt_unit(self):
        """Works with milliwatt input units."""
        assert abs(watts_to_dbm(Q_(1.0, "milliwatt")) - 0.0) < 0.001

    def test_negative_power_rejects(self):
        with pytest.raises(PhysicalViolationError, match="positive"):
            watts_to_dbm(Q_(-1.0, "watt"))

    def test_wrong_dimensions_rejects(self):
        with pytest.raises(PhysicalViolationError, match="Dimensional"):
            watts_to_dbm(Q_(1.0, "meter"))


class TestDbmToWatts:
    def test_zero_dbm(self):
        """0 dBm = 1 mW."""
        result = dbm_to_watts(0.0)
        assert abs(result.to(ureg.milliwatt).magnitude - 1.0) < 1e-10

    def test_30_dbm(self):
        """30 dBm = 1 W."""
        result = dbm_to_watts(30.0)
        assert abs(result.to(ureg.watt).magnitude - 1.0) < 1e-6

    def test_roundtrip(self):
        """dBm -> W -> dBm should be identity."""
        for dbm in [-30, -10, 0, 10, 30]:
            assert abs(watts_to_dbm(dbm_to_watts(dbm)) - dbm) < 1e-10


class TestFrequencyToWavelength:
    def test_1ghz(self):
        """1 GHz -> ~0.2998 m."""
        lam = frequency_to_wavelength(Q_(1e9, "Hz"))
        assert abs(lam.magnitude - 0.299792458) < 1e-6

    def test_2_4ghz(self):
        """2.4 GHz -> ~0.125 m (Wi-Fi)."""
        lam = frequency_to_wavelength(Q_(2.4e9, "Hz"))
        assert abs(lam.magnitude - 0.12491) < 0.001

    def test_negative_frequency_rejects(self):
        with pytest.raises(PhysicalViolationError):
            frequency_to_wavelength(Q_(-1e9, "Hz"))

    def test_wrong_dimensions_rejects(self):
        with pytest.raises(PhysicalViolationError, match="Dimensional"):
            frequency_to_wavelength(Q_(1.0, "meter"))


class TestDbConversions:
    def test_db_to_linear_0db(self):
        assert abs(db_to_linear(0.0) - 1.0) < 1e-10

    def test_db_to_linear_10db(self):
        assert abs(db_to_linear(10.0) - 10.0) < 1e-10

    def test_db_to_linear_3db(self):
        assert abs(db_to_linear(3.0) - 2.0) < 0.01

    def test_linear_to_db_roundtrip(self):
        for db in [-20, -3, 0, 3, 10, 20]:
            assert abs(linear_to_db(db_to_linear(db)) - db) < 1e-10

    def test_linear_to_db_zero_rejects(self):
        with pytest.raises(PhysicalViolationError):
            linear_to_db(0.0)

    def test_linear_to_db_negative_rejects(self):
        with pytest.raises(PhysicalViolationError):
            linear_to_db(-1.0)


class TestValidateDimensions:
    def test_correct_dimensions_pass(self):
        validate_dimensions(Q_(1.0, "meter"), "[length]", "distance")

    def test_wrong_dimensions_raise(self):
        with pytest.raises(PhysicalViolationError, match="Dimensional"):
            validate_dimensions(Q_(1.0, "meter"), "1 / [time]", "frequency")
