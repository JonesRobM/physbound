"""Tests for physical constants and their Pint representations."""

import math

from physbound.engines.constants import (
    BOLTZMANN,
    PLANCK,
    SPEED_OF_LIGHT,
    T_REF,
    THERMAL_NOISE_FLOOR_DBM_PER_HZ,
    ureg,
)


def test_speed_of_light_exact():
    """c must be exactly 299,792,458 m/s (SI definition)."""
    assert SPEED_OF_LIGHT.magnitude == 299_792_458
    assert SPEED_OF_LIGHT.units == ureg.meter / ureg.second


def test_boltzmann_exact():
    """k_B must be exactly 1.380649e-23 J/K (SI definition since 2019)."""
    assert BOLTZMANN.magnitude == 1.380649e-23
    assert BOLTZMANN.check("[energy] / [temperature]")


def test_planck_exact():
    """h must be exactly 6.62607015e-34 J·s (SI definition since 2019)."""
    assert PLANCK.magnitude == 6.62607015e-34
    assert PLANCK.check("[energy] * [time]")


def test_reference_temperature():
    """IEEE standard reference temperature is 290 K."""
    assert T_REF.magnitude == 290
    assert T_REF.units == ureg.kelvin


def test_thermal_noise_floor_derivation():
    """Verify -174 dBm/Hz matches k_B * T_REF computation."""
    # N = k_B * T in watts per Hz
    n_watts_per_hz = BOLTZMANN.magnitude * T_REF.magnitude
    n_dbm_per_hz = 10.0 * math.log10(n_watts_per_hz / 1e-3)
    # Should be approximately -174 dBm/Hz
    assert abs(n_dbm_per_hz - THERMAL_NOISE_FLOOR_DBM_PER_HZ) < 0.03
    # Exact value is -173.977... which rounds to -174
    assert THERMAL_NOISE_FLOOR_DBM_PER_HZ == -174.0
