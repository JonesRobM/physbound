"""RF Link Budget calculator using Friis transmission equation.

Formulas:
    FSPL = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)    (free-space path loss)
    P_rx = P_tx + G_tx + G_rx - FSPL - L_tx - L_rx          (Friis transmission)
    G_max = eta * (pi*D/lambda)^2                             (aperture limit)
"""

import math

from physbound.engines.constants import SPEED_OF_LIGHT
from physbound.engines.units import linear_to_db
from physbound.errors import PhysicalViolationError
from physbound.validators import validate_positive_distance, validate_positive_frequency

# Default aperture efficiency for parabolic dish antennas
DEFAULT_APERTURE_EFFICIENCY = 0.55


def free_space_path_loss_db(frequency_hz: float, distance_m: float) -> float:
    """Compute free-space path loss in dB.

    FSPL(dB) = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)

    Args:
        frequency_hz: Carrier frequency in Hz.
        distance_m: Link distance in meters.

    Returns:
        FSPL in dB (positive value; a loss).
    """
    validate_positive_frequency(frequency_hz)
    validate_positive_distance(distance_m)

    c = SPEED_OF_LIGHT.magnitude  # m/s
    fspl = (
        20.0 * math.log10(distance_m)
        + 20.0 * math.log10(frequency_hz)
        + 20.0 * math.log10(4.0 * math.pi / c)
    )
    return fspl


def max_aperture_gain_dbi(
    diameter_m: float,
    frequency_hz: float,
    efficiency: float = DEFAULT_APERTURE_EFFICIENCY,
) -> float:
    """Compute maximum antenna gain for a circular aperture.

    G_max = eta * (pi * D / lambda)^2

    Args:
        diameter_m: Antenna diameter in meters.
        frequency_hz: Operating frequency in Hz.
        efficiency: Aperture efficiency (default: 0.55 for parabolic dish).

    Returns:
        Maximum gain in dBi.
    """
    validate_positive_frequency(frequency_hz)
    if diameter_m <= 0:
        raise PhysicalViolationError(
            message=f"Antenna diameter must be positive, got {diameter_m} m",
            law_violated="Antenna Theory",
            latex_explanation=r"$D > 0$ required for a physical antenna aperture",
            claimed_value=diameter_m,
            unit="m",
        )

    c = SPEED_OF_LIGHT.magnitude
    wavelength = c / frequency_hz
    g_linear = efficiency * (math.pi * diameter_m / wavelength) ** 2
    return linear_to_db(g_linear)


def validate_antenna_gain(
    claimed_gain_dbi: float,
    diameter_m: float,
    frequency_hz: float,
    label: str = "antenna",
    efficiency: float = DEFAULT_APERTURE_EFFICIENCY,
) -> float:
    """Validate that claimed antenna gain doesn't exceed the aperture limit.

    Args:
        claimed_gain_dbi: Claimed antenna gain in dBi.
        diameter_m: Antenna diameter in meters.
        frequency_hz: Operating frequency in Hz.
        label: Human label for error messages (e.g., "TX antenna").
        efficiency: Aperture efficiency (default: 0.55).

    Returns:
        The computed G_max in dBi.

    Raises:
        PhysicalViolationError: If claimed gain exceeds G_max.
    """
    g_max = max_aperture_gain_dbi(diameter_m, frequency_hz, efficiency)

    if claimed_gain_dbi > g_max:
        c = SPEED_OF_LIGHT.magnitude
        wavelength = c / frequency_hz
        raise PhysicalViolationError(
            message=(
                f"{label} claimed gain {claimed_gain_dbi:.1f} dBi exceeds "
                f"aperture limit {g_max:.1f} dBi for {diameter_m} m dish at "
                f"{frequency_hz / 1e9:.3f} GHz"
            ),
            law_violated="Antenna Aperture Limit",
            latex_explanation=(
                rf"$G_{{\max}} = \eta \left(\frac{{\pi D}}{{\lambda}}\right)^2 = "
                rf"{efficiency} \times \left(\frac{{\pi \times {diameter_m}}}"
                rf"{{{wavelength:.4f}}}\right)^2 = {g_max:.1f}\,\text{{dBi}}$. "
                rf"Claimed ${claimed_gain_dbi:.1f}\,\text{{dBi}}$ exceeds this limit."
            ),
            computed_limit=g_max,
            claimed_value=claimed_gain_dbi,
            unit="dBi",
        )

    return g_max


def compute_link_budget(
    tx_power_dbm: float,
    tx_antenna_gain_dbi: float,
    rx_antenna_gain_dbi: float,
    frequency_hz: float,
    distance_m: float,
    tx_losses_db: float = 0.0,
    rx_losses_db: float = 0.0,
    tx_antenna_diameter_m: float | None = None,
    rx_antenna_diameter_m: float | None = None,
) -> dict:
    """Compute a full RF link budget using the Friis transmission equation.

    P_rx = P_tx + G_tx + G_rx - FSPL - L_tx - L_rx

    Args:
        tx_power_dbm: Transmit power in dBm.
        tx_antenna_gain_dbi: Transmit antenna gain in dBi.
        rx_antenna_gain_dbi: Receive antenna gain in dBi.
        frequency_hz: Carrier frequency in Hz.
        distance_m: Link distance in meters.
        tx_losses_db: TX-side miscellaneous losses in dB.
        rx_losses_db: RX-side miscellaneous losses in dB.
        tx_antenna_diameter_m: Optional TX antenna diameter for aperture check.
        rx_antenna_diameter_m: Optional RX antenna diameter for aperture check.

    Returns:
        Dict with FSPL, received power, warnings, human-readable, and LaTeX.

    Raises:
        PhysicalViolationError: If antenna gains exceed aperture limits.
    """
    warnings = []
    tx_aperture_limit_dbi = None
    rx_aperture_limit_dbi = None

    # Validate antenna gains against aperture limits if diameters provided
    if tx_antenna_diameter_m is not None:
        tx_aperture_limit_dbi = validate_antenna_gain(
            tx_antenna_gain_dbi, tx_antenna_diameter_m, frequency_hz, "TX antenna"
        )

    if rx_antenna_diameter_m is not None:
        rx_aperture_limit_dbi = validate_antenna_gain(
            rx_antenna_gain_dbi, rx_antenna_diameter_m, frequency_hz, "RX antenna"
        )

    # Friis model applicability warning above 300 GHz
    if frequency_hz > 3e11:
        warnings.append(
            f"Frequency {frequency_hz / 1e9:.1f} GHz exceeds 300 GHz; "
            "Friis free-space model may not be accurate due to atmospheric absorption"
        )

    # Compute FSPL and received power
    fspl = free_space_path_loss_db(frequency_hz, distance_m)
    received_power_dbm = (
        tx_power_dbm
        + tx_antenna_gain_dbi
        + rx_antenna_gain_dbi
        - fspl
        - tx_losses_db
        - rx_losses_db
    )

    c = SPEED_OF_LIGHT.magnitude
    wavelength = c / frequency_hz

    human_readable = (
        f"Link Budget at {frequency_hz / 1e9:.3f} GHz, {distance_m:.1f} m:\n"
        f"  TX Power:      {tx_power_dbm:.1f} dBm\n"
        f"  TX Gain:       {tx_antenna_gain_dbi:.1f} dBi\n"
        f"  RX Gain:       {rx_antenna_gain_dbi:.1f} dBi\n"
        f"  FSPL:          {fspl:.2f} dB\n"
        f"  TX Losses:     {tx_losses_db:.1f} dB\n"
        f"  RX Losses:     {rx_losses_db:.1f} dB\n"
        f"  Received Power: {received_power_dbm:.2f} dBm"
    )

    latex = (
        rf"$P_{{\text{{rx}}}} = P_{{\text{{tx}}}} + G_{{\text{{tx}}}} + G_{{\text{{rx}}}} "
        rf"- \text{{FSPL}} - L_{{\text{{tx}}}} - L_{{\text{{rx}}}} = "
        rf"{tx_power_dbm:.1f} + {tx_antenna_gain_dbi:.1f} + {rx_antenna_gain_dbi:.1f} "
        rf"- {fspl:.2f} - {tx_losses_db:.1f} - {rx_losses_db:.1f} = "
        rf"{received_power_dbm:.2f}\,\text{{dBm}}$"
    )

    return {
        "fspl_db": fspl,
        "received_power_dbm": received_power_dbm,
        "wavelength_m": wavelength,
        "tx_aperture_limit_dbi": tx_aperture_limit_dbi,
        "rx_aperture_limit_dbi": rx_aperture_limit_dbi,
        "warnings": warnings,
        "human_readable": human_readable,
        "latex": latex,
    }
