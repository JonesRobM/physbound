"""Standalone antenna aperture gain calculator and claim validator.

Formulas:
    lambda = c / f                                            (wavelength)
    A_phys = pi * D^2 / 4                                     (circular aperture area)
    D      = sqrt(4 * A_phys / pi)                            (equivalent diameter)
    D_0    = 4*pi*A_phys / lambda^2 = (pi*D/lambda)^2          (planar-aperture directivity)
    D_max  = (ka)^2 + 2ka,  k = 2*pi/lambda,  a = D/2            (Harrington bound, >= D_0)
    G      = eta * D_0 = 4*pi*A_e / lambda^2,  A_e = eta*A_phys (gain at efficiency eta)
    HPBW   ~ 70 * lambda / D  degrees                         (tapered reflector rule of thumb)
    HPBW   ~ 58.4 * lambda / D degrees                        (uniformly illuminated circle)
    R_ff   = 2 * D^2 / lambda                                 (far-field / Fraunhofer distance)

Sources:
    Balanis, "Antenna Theory: Analysis and Design", Sec. 2.16 (aperture-directivity
    relation G = 4*pi*A_e/lambda^2), Sec. 12.5 (uniform circular aperture:
    HPBW = 29.2 deg * lambda/a with a = D/2, i.e. 58.4 deg * lambda/D), Sec. 15.4
    (parabolic reflectors, HPBW ~ 70 deg * lambda/D for typical edge taper),
    Sec. 2.2.4 (far-field region begins at R = 2 D^2 / lambda).
    Skolnik, "Radar Handbook", Ch. 9: typical parabolic-dish aperture efficiency
    eta ~ 0.55.
    Harrington, "Effect of antenna size on gain, bandwidth, and efficiency",
    J. Res. NBS 64D (1960): D_max = (ka)^2 + 2ka for electrically small antennas.

Gain limit semantics are shared with ``physbound.engines.link_budget``: the
hard limit is max(eta = 1 aperture value, Harrington bound) — numerically the
Harrington value, which converges to the aperture value for D >> lambda; a
claim between the typical-efficiency gain and the hard limit is a warning; a
claim above the hard limit is a ``PhysicalViolationError`` (raised by
``validate_antenna_gain``).
"""

import math

from physbound.engines.constants import SPEED_OF_LIGHT
from physbound.engines.link_budget import (
    DEFAULT_APERTURE_EFFICIENCY,
    PHYSICAL_APERTURE_EFFICIENCY,
    harrington_gain_limit_dbi,
    limiting_bound_for,
    max_aperture_gain_dbi,
    physical_aperture_gain_limit_dbi,
    validate_antenna_gain,
)
from physbound.engines.units import db_to_linear
from physbound.errors import PhysicalViolationError

# Half-power beamwidth coefficients (degrees * D / lambda), Balanis Sec. 12.5 / 15.4
HPBW_COEFF_UNIFORM_DEG = 58.4  # uniformly illuminated circular aperture
HPBW_COEFF_TAPERED_DEG = 70.0  # typical tapered parabolic reflector (rule of thumb)


def diameter_from_area_m(aperture_area_m2: float) -> float:
    """Equivalent circular diameter for a given physical aperture area.

    D = sqrt(4 * A / pi)

    Raises:
        PhysicalViolationError: If the area is not positive.
    """
    if aperture_area_m2 <= 0:
        raise PhysicalViolationError(
            message=f"Aperture area must be positive, got {aperture_area_m2} m^2",
            law_violated="Antenna Theory",
            latex_explanation=r"$A_{\text{phys}} > 0$ required for a physical antenna aperture",
            claimed_value=aperture_area_m2,
            unit="m^2",
        )
    return math.sqrt(4.0 * aperture_area_m2 / math.pi)


def half_power_beamwidth_deg(
    diameter_m: float, wavelength_m: float, coefficient: float = HPBW_COEFF_TAPERED_DEG
) -> float:
    """Approximate half-power beamwidth in degrees: HPBW ~ k * lambda / D.

    Args:
        diameter_m: Aperture diameter in meters.
        wavelength_m: Wavelength in meters.
        coefficient: 70 (tapered reflector, default) or 58.4 (uniform circular aperture).
    """
    return coefficient * wavelength_m / diameter_m


def far_field_distance_m(diameter_m: float, wavelength_m: float) -> float:
    """Fraunhofer (far-field) distance R = 2 D^2 / lambda (Balanis Sec. 2.2.4)."""
    return 2.0 * diameter_m**2 / wavelength_m


def compute_antenna_gain(
    frequency_hz: float,
    diameter_m: float | None = None,
    aperture_area_m2: float | None = None,
    claimed_gain_dbi: float | None = None,
    aperture_efficiency: float = DEFAULT_APERTURE_EFFICIENCY,
) -> dict:
    """Compute aperture gain limits, beamwidth and far-field distance for an antenna.

    Exactly one of ``diameter_m`` or ``aperture_area_m2`` must be given; an area
    is converted to the equivalent circular diameter.

    Args:
        frequency_hz: Operating frequency in Hz (must be > 0).
        diameter_m: Circular aperture diameter in meters.
        aperture_area_m2: Physical aperture area in m^2 (alternative to diameter).
        claimed_gain_dbi: Optional gain claim to validate in dBi.
        aperture_efficiency: Efficiency for the typical-gain value / warning
            threshold, 0 < eta <= 1 (default 0.55). The hard limit is
            max(eta = 1 aperture value, Harrington bound).

    Returns:
        Dict matching ``AntennaGainOutput`` fields.

    Raises:
        PhysicalViolationError: If inputs are non-physical or the claimed gain
            exceeds the physical limit.
    """
    if (diameter_m is None) == (aperture_area_m2 is None):
        raise ValueError("Exactly one of diameter_m or aperture_area_m2 must be provided")
    if diameter_m is None:
        assert aperture_area_m2 is not None
        diameter_m = diameter_from_area_m(aperture_area_m2)

    # max_aperture_gain_dbi validates frequency, diameter and efficiency
    typical_gain_dbi = max_aperture_gain_dbi(diameter_m, frequency_hz, aperture_efficiency)
    aperture_limit_dbi = physical_aperture_gain_limit_dbi(diameter_m, frequency_hz)
    harrington_limit_dbi = harrington_gain_limit_dbi(diameter_m, frequency_hz)
    physical_limit_dbi = max(aperture_limit_dbi, harrington_limit_dbi)

    c = SPEED_OF_LIGHT.magnitude
    wavelength = c / frequency_hz
    limiting_bound = limiting_bound_for(diameter_m, wavelength)
    physical_area = math.pi * diameter_m**2 / 4.0
    effective_area = aperture_efficiency * physical_area
    directivity_linear = db_to_linear(aperture_limit_dbi)  # D_0 = (pi D / lambda)^2

    hpbw_tapered = half_power_beamwidth_deg(diameter_m, wavelength, HPBW_COEFF_TAPERED_DEG)
    hpbw_uniform = half_power_beamwidth_deg(diameter_m, wavelength, HPBW_COEFF_UNIFORM_DEG)
    r_ff = far_field_distance_m(diameter_m, wavelength)

    warnings: list[str] = []
    implied_efficiency: float | None = None
    claim_is_valid: bool | None = None

    if claimed_gain_dbi is not None:
        check = validate_antenna_gain(
            claimed_gain_dbi, diameter_m, frequency_hz, "Antenna", aperture_efficiency
        )
        implied_efficiency = check["implied_efficiency"]
        claim_is_valid = True  # validate_antenna_gain raised otherwise
        warnings.extend(check["warnings"])

    warnings.append(
        f"Half-power beamwidth {hpbw_tapered:.2f} deg uses the 70*lambda/D rule of thumb "
        f"for a tapered parabolic reflector; a uniformly illuminated circular aperture "
        f"gives 58.4*lambda/D = {hpbw_uniform:.2f} deg (Balanis, Antenna Theory, Sec. 12.5)"
    )
    if aperture_efficiency >= PHYSICAL_APERTURE_EFFICIENCY:
        warnings.append(
            "aperture_efficiency = 1 assumes a lossless, uniformly illuminated aperture; "
            "the typical gain equals the physical limit and no efficiency margin is reported"
        )

    human_readable = (
        f"Antenna Aperture Gain at {frequency_hz / 1e9:.3f} GHz (lambda = {wavelength:.4f} m):\n"
        f"  Diameter:            {diameter_m:.3f} m (area {physical_area:.4f} m^2)\n"
        f"  Physical limit:      {physical_limit_dbi:.2f} dBi "
        f"(Harrington (ka)^2 + 2ka; regime: {limiting_bound})\n"
        f"  Aperture (eta = 1):  {aperture_limit_dbi:.2f} dBi\n"
        f"  Typical gain:        {typical_gain_dbi:.2f} dBi (eta = {aperture_efficiency})\n"
        f"  Effective aperture:  {effective_area:.4f} m^2\n"
        f"  HPBW (~70 lambda/D): {hpbw_tapered:.2f} deg\n"
        f"  Far-field distance:  {r_ff:.2f} m (2D^2/lambda)"
    )
    if claimed_gain_dbi is not None:
        assert implied_efficiency is not None
        human_readable += (
            f"\n  Claimed gain:        {claimed_gain_dbi:.2f} dBi "
            f"(implied eta = {implied_efficiency:.3f}) -> VALID"
        )

    latex = (
        rf"$G = \eta \left(\frac{{\pi D}}{{\lambda}}\right)^2 = "
        rf"\eta \frac{{4\pi A_{{\text{{phys}}}}}}{{\lambda^2}}$: "
        rf"$D_0 = \left(\frac{{\pi \times {diameter_m:.3f}}}{{{wavelength:.4f}}}\right)^2 = "
        rf"{aperture_limit_dbi:.2f}\,\text{{dBi}}$ at $\eta = 1$; "
        rf"$D_{{\max}} = (ka)^2 + 2ka = {physical_limit_dbi:.2f}\,\text{{dBi}}$ (Harrington); "
        rf"$G = {typical_gain_dbi:.2f}\,\text{{dBi}}$ at $\eta = {aperture_efficiency}$; "
        rf"$\theta_{{3\,\text{{dB}}}} \approx 70\lambda/D = {hpbw_tapered:.2f}^\circ$; "
        rf"$R_{{\text{{ff}}}} = 2D^2/\lambda = {r_ff:.2f}\,\text{{m}}$"
    )

    return {
        "frequency_hz": frequency_hz,
        "wavelength_m": wavelength,
        "diameter_m": diameter_m,
        "physical_aperture_m2": physical_area,
        "effective_aperture_m2": effective_area,
        "aperture_efficiency": aperture_efficiency,
        "physical_limit_dbi": physical_limit_dbi,
        "aperture_limit_dbi": aperture_limit_dbi,
        "harrington_limit_dbi": harrington_limit_dbi,
        "limiting_bound": limiting_bound,
        "typical_gain_dbi": typical_gain_dbi,
        "directivity_linear": directivity_linear,
        "half_power_beamwidth_deg": hpbw_tapered,
        "half_power_beamwidth_uniform_deg": hpbw_uniform,
        "far_field_distance_m": r_ff,
        "claimed_gain_dbi": claimed_gain_dbi,
        "implied_efficiency": implied_efficiency,
        "claim_is_valid": claim_is_valid,
        "warnings": warnings,
        "human_readable": human_readable,
        "latex": latex,
    }
