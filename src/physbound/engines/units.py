"""Unit conversion helpers for RF engineering calculations.

All functions operate on Pint quantities and enforce dimensional correctness.
"""

import math

import pint

from physbound.engines.constants import Q_, SPEED_OF_LIGHT, ureg
from physbound.errors import PhysicalViolationError


def validate_dimensions(quantity: pint.Quantity, expected: str, name: str = "value") -> None:
    """Raise PhysicalViolationError if quantity dimensions don't match expected.

    Args:
        quantity: The Pint quantity to check.
        expected: Pint dimensionality string, e.g. '[length]', '[power]'.
        name: Human-readable name for error messages.
    """
    if not quantity.check(expected):
        raise PhysicalViolationError(
            message=f"{name} has dimensions {quantity.dimensionality}, expected {expected}",
            law_violated="Dimensional Analysis",
            latex_explanation=(
                rf"$\text{{{name}}}$ has dimensions "
                rf"$\left[{quantity.dimensionality}\right]$, "
                rf"expected $\left[{expected}\right]$"
            ),
        )


def watts_to_dbm(power: pint.Quantity) -> float:
    """Convert a Pint power quantity to dBm (dimensionless float).

    Args:
        power: Power as a Pint quantity with dimensions of [power].

    Returns:
        Power in dBm as a plain float.
    """
    validate_dimensions(power, "[length] ** 2 * [mass] / [time] ** 3", "power")
    power_watts = power.to(ureg.watt).magnitude
    if power_watts <= 0:
        raise PhysicalViolationError(
            message=f"Power must be positive, got {power_watts} W",
            law_violated="Conservation of Energy",
            latex_explanation=r"$P > 0$ required; negative power is non-physical",
            claimed_value=power_watts,
            unit="W",
        )
    return 10.0 * math.log10(power_watts / 1e-3)


def dbm_to_watts(power_dbm: float) -> pint.Quantity:
    """Convert dBm float to Pint watts quantity.

    Args:
        power_dbm: Power in dBm.

    Returns:
        Power as a Pint Quantity in watts.
    """
    return Q_(1e-3 * 10.0 ** (power_dbm / 10.0), "watt")


def frequency_to_wavelength(freq: pint.Quantity) -> pint.Quantity:
    """Compute wavelength from frequency: lambda = c / f.

    Args:
        freq: Frequency as a Pint quantity with dimensions of [time]^-1.

    Returns:
        Wavelength as a Pint Quantity in meters.
    """
    validate_dimensions(freq, "1 / [time]", "frequency")
    if freq.magnitude <= 0:
        raise PhysicalViolationError(
            message=f"Frequency must be positive, got {freq}",
            law_violated="Electromagnetic Theory",
            latex_explanation=r"$f > 0$ required for physical electromagnetic radiation",
            claimed_value=freq.magnitude,
            unit=str(freq.units),
        )
    return (SPEED_OF_LIGHT / freq).to(ureg.meter)


def db_to_linear(db: float) -> float:
    """Convert a dB value to linear ratio: 10^(dB/10)."""
    return 10.0 ** (db / 10.0)


def linear_to_db(linear: float) -> float:
    """Convert a linear ratio to dB: 10*log10(linear)."""
    if linear <= 0:
        raise PhysicalViolationError(
            message=f"Linear value must be positive for dB conversion, got {linear}",
            law_violated="Mathematical Constraint",
            latex_explanation=r"$\text{dB} = 10 \log_{10}(x)$ requires $x > 0$",
            claimed_value=linear,
        )
    return 10.0 * math.log10(linear)
