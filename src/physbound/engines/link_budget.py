"""RF Link Budget calculator using Friis transmission equation.

Formulas:
    FSPL = 20*log10(d) + 20*log10(f) + 20*log10(4*pi/c)    (free-space path loss)
    P_rx = P_tx + G_tx + G_rx - FSPL - L_tx - L_rx          (Friis transmission)
    G = eta * (pi*D/lambda)^2                                 (circular aperture gain)
    D_max = (ka)^2 + 2ka,  k = 2*pi/lambda,  a = D/2          (Harrington bound)

Gain limit semantics:
    The gain of a circular aperture of diameter D is G = eta * (pi*D/lambda)^2
    where eta is the aperture efficiency, 0 < eta <= 1 (Balanis, "Antenna
    Theory", Sec. 12.x; Pozar, "Microwave Engineering", Ch. 14). Since eta
    cannot exceed 1, the eta = 1 value G_ap = (pi*D/lambda)^2 (from
    G = 4*pi*A_e/lambda^2 with A_e <= A_phys = pi*D^2/4) bounds the gain of a
    *planar aperture*. It is not a rigorous bound for an arbitrary antenna
    fitting in a D-metre footprint: a half-wave dipole (2.15 dBi) in a 0.1 m
    footprint at 900 MHz exceeds G_ap = -0.5 dBi. The rigorous bound on the
    directivity of any antenna enclosed in a sphere of radius a = D/2 is
    Harrington's D_max = (ka)^2 + 2ka (Harrington, J. Res. NBS 64D, 1960;
    Balanis Sec. 11.x). Since (ka)^2 = (pi*D/lambda)^2, Harrington's bound is
    the aperture value plus the 2ka term, so the hard physical limit
    G_phys = max(G_ap, D_max) = D_max for every D; the two coincide to within
    10*log10(1 + 2/(ka)) dB, negligible for D >> lambda (0.08 dB for a 1 m
    dish at 10 GHz) but decisive for electrically small antennas (D < lambda,
    where it is at least 2.1 dB). A claimed gain above G_phys is a hard
    violation. A claimed gain above the *typical-efficiency* value (eta ~ 0.55
    for a parabolic reflector, Skolnik "Radar Handbook" Ch. 9) but below G_phys
    is achievable only with an unusually efficient (or non-planar,
    electrically small) antenna, so it is reported as a warning.
"""

import math

from physbound.engines.constants import SPEED_OF_LIGHT
from physbound.engines.units import linear_to_db
from physbound.errors import PhysicalViolationError
from physbound.validators import validate_positive_distance, validate_positive_frequency

# Typical aperture efficiency for parabolic dish antennas (warning threshold)
DEFAULT_APERTURE_EFFICIENCY = 0.55

# Physical upper bound on aperture efficiency (planar-aperture bound)
PHYSICAL_APERTURE_EFFICIENCY = 1.0

# Values of the ``limiting_bound`` field returned by ``validate_antenna_gain``
LIMITING_BOUND_APERTURE = "aperture"
LIMITING_BOUND_HARRINGTON = "harrington"


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


def _validate_aperture_inputs(diameter_m: float, frequency_hz: float, efficiency: float) -> None:
    validate_positive_frequency(frequency_hz)
    if diameter_m <= 0:
        raise PhysicalViolationError(
            message=f"Antenna diameter must be positive, got {diameter_m} m",
            law_violated="Antenna Theory",
            latex_explanation=r"$D > 0$ required for a physical antenna aperture",
            claimed_value=diameter_m,
            unit="m",
        )
    if not (0.0 < efficiency <= PHYSICAL_APERTURE_EFFICIENCY):
        raise PhysicalViolationError(
            message=(
                f"Aperture efficiency must satisfy 0 < eta <= 1, got {efficiency}; "
                "effective area cannot exceed physical area"
            ),
            law_violated="Antenna Aperture Limit",
            latex_explanation=(
                r"$0 < \eta = A_e / A_{\text{phys}} \leq 1$; "
                r"the effective aperture cannot exceed the physical aperture"
            ),
            claimed_value=efficiency,
        )


def max_aperture_gain_dbi(
    diameter_m: float,
    frequency_hz: float,
    efficiency: float = DEFAULT_APERTURE_EFFICIENCY,
) -> float:
    """Compute antenna gain for a circular aperture at a given efficiency.

    G = eta * (pi * D / lambda)^2

    With efficiency=1.0 this is the physical upper bound on gain; with the
    default efficiency=0.55 it is the gain of a typical parabolic reflector.

    Args:
        diameter_m: Antenna diameter in meters.
        frequency_hz: Operating frequency in Hz.
        efficiency: Aperture efficiency, 0 < eta <= 1 (default: 0.55).

    Returns:
        Gain in dBi.
    """
    _validate_aperture_inputs(diameter_m, frequency_hz, efficiency)

    c = SPEED_OF_LIGHT.magnitude
    wavelength = c / frequency_hz
    g_linear = efficiency * (math.pi * diameter_m / wavelength) ** 2
    return linear_to_db(g_linear)


def physical_aperture_gain_limit_dbi(diameter_m: float, frequency_hz: float) -> float:
    """eta = 1 upper bound on planar circular-aperture gain in dBi.

    G_ap = (pi * D / lambda)^2, from G = 4*pi*A_e/lambda^2 with A_e <= pi*D^2/4.
    This is the bound for a planar aperture; the hard limit for an arbitrary
    antenna in the same footprint is ``physical_gain_limit_dbi``.
    """
    return max_aperture_gain_dbi(diameter_m, frequency_hz, PHYSICAL_APERTURE_EFFICIENCY)


def harrington_gain_limit_dbi(diameter_m: float, frequency_hz: float) -> float:
    """Harrington bound on directivity for an antenna enclosed in a sphere of diameter D.

    D_max = (ka)^2 + 2ka with k = 2*pi/lambda and a = D/2 (Harrington 1960,
    "Effect of antenna size on gain, bandwidth, and efficiency"; Balanis).
    Since ka = pi*D/lambda this exceeds the eta = 1 aperture value (ka)^2 by 2ka.
    """
    _validate_aperture_inputs(diameter_m, frequency_hz, PHYSICAL_APERTURE_EFFICIENCY)
    c = SPEED_OF_LIGHT.magnitude
    ka = math.pi * diameter_m * frequency_hz / c  # k * a = (2 pi / lambda) * (D / 2)
    return linear_to_db(ka**2 + 2.0 * ka)


def physical_gain_limit_dbi(diameter_m: float, frequency_hz: float) -> float:
    """Hard physical gain limit: max(eta = 1 aperture value, Harrington bound), dBi.

    Because D_max = (ka)^2 + 2ka >= (ka)^2 = (pi*D/lambda)^2 for all D, this is
    the Harrington value; it converges to the aperture value for D >> lambda.
    """
    return max(
        physical_aperture_gain_limit_dbi(diameter_m, frequency_hz),
        harrington_gain_limit_dbi(diameter_m, frequency_hz),
    )


def limiting_bound_for(diameter_m: float, wavelength_m: float) -> str:
    """Which regime sets the hard limit.

    ``"harrington"`` when D < lambda (electrically small: the planar-aperture
    formula understates the bound by >= 2.1 dB); ``"aperture"`` when D >= lambda
    (electrically large: the Harrington and eta = 1 aperture values agree to
    within 10*log10(1 + 2 lambda / (pi D)) dB, vanishing as D / lambda grows).
    """
    return LIMITING_BOUND_HARRINGTON if diameter_m < wavelength_m else LIMITING_BOUND_APERTURE


def validate_antenna_gain(
    claimed_gain_dbi: float,
    diameter_m: float,
    frequency_hz: float,
    label: str = "antenna",
    efficiency: float = DEFAULT_APERTURE_EFFICIENCY,
) -> dict:
    """Validate a claimed antenna gain against the physical gain limit.

    Hard-fails (PhysicalViolationError) if the claim exceeds the physical bound
    max(eta = 1 aperture value, Harrington bound) — numerically the Harrington
    value (ka)^2 + 2ka. Emits a warning if the claim is above the
    typical-efficiency value ``efficiency * (pi D / lambda)^2`` (default 0.55, a
    typical parabolic dish); if it is also above the eta = 1 planar-aperture
    value the warning notes that only a non-planar / electrically small
    radiator can reach it.

    Args:
        claimed_gain_dbi: Claimed antenna gain in dBi.
        diameter_m: Antenna diameter (enclosing-sphere diameter) in meters.
        frequency_hz: Operating frequency in Hz.
        label: Human label for messages (e.g., "TX antenna").
        efficiency: Aperture efficiency used for the warning threshold.

    Returns:
        Dict with keys ``physical_limit_dbi`` (hard limit), ``aperture_limit_dbi``
        (eta = 1 planar aperture), ``harrington_limit_dbi``, ``limiting_bound``
        (``"aperture"`` for D >= lambda, ``"harrington"`` for D < lambda),
        ``typical_limit_dbi`` (eta = ``efficiency``), ``implied_efficiency``
        (G_claim / G_ap, the aperture efficiency needed to reach the claim; may
        exceed 1 for a valid electrically small antenna) and ``warnings``.

    Raises:
        PhysicalViolationError: If claimed gain exceeds the physical limit.
    """
    g_ap = physical_aperture_gain_limit_dbi(diameter_m, frequency_hz)
    g_harr = harrington_gain_limit_dbi(diameter_m, frequency_hz)
    g_phys = max(g_ap, g_harr)
    g_typ = max_aperture_gain_dbi(diameter_m, frequency_hz, efficiency)

    c = SPEED_OF_LIGHT.magnitude
    wavelength = c / frequency_hz
    ka = math.pi * diameter_m / wavelength
    bound = limiting_bound_for(diameter_m, wavelength)
    # eta required to achieve the claim with a planar aperture: G_claim / (pi D / lambda)^2
    implied_eta = 10.0 ** ((claimed_gain_dbi - g_ap) / 10.0)

    if claimed_gain_dbi > g_phys:
        raise PhysicalViolationError(
            message=(
                f"{label} claimed gain {claimed_gain_dbi:.1f} dBi exceeds the physical limit "
                f"{g_phys:.1f} dBi for a {diameter_m} m antenna at {frequency_hz / 1e9:.3f} GHz "
                f"(Harrington bound (ka)^2 + 2ka with ka = {ka:.3f}; eta = 1 aperture value "
                f"{g_ap:.1f} dBi); it would require aperture efficiency "
                f"eta = {implied_eta:.2f} > 1 (typical eta = {efficiency} gives {g_typ:.1f} dBi)"
            ),
            law_violated="Antenna Aperture Limit",
            latex_explanation=(
                rf"$G_{{\max}} = (ka)^2 + 2ka = {ka:.3f}^2 + 2 \times {ka:.3f} = "
                rf"{g_phys:.1f}\,\text{{dBi}}$ with $ka = \pi D / \lambda = "
                rf"\pi \times {diameter_m} / {wavelength:.4f}$ (Harrington); "
                rf"the $\eta = 1$ aperture value $(\pi D/\lambda)^2 = {g_ap:.1f}\,\text{{dBi}}$ "
                r"(since $A_e \leq A_{\text{phys}}$). "
                rf"Claimed ${claimed_gain_dbi:.1f}\,\text{{dBi}}$ requires "
                rf"$\eta = {implied_eta:.2f} > 1$."
            ),
            computed_limit=g_phys,
            claimed_value=claimed_gain_dbi,
            unit="dBi",
        )

    warnings: list[str] = []
    if claimed_gain_dbi > g_ap:
        warnings.append(
            f"{label} claimed gain {claimed_gain_dbi:.1f} dBi exceeds the eta = 1 planar-aperture "
            f"value {g_ap:.1f} dBi (implied eta = {implied_eta:.2f} > 1) for a {diameter_m} m "
            f"footprint at {frequency_hz / 1e9:.3f} GHz, but is within the Harrington bound "
            f"{g_harr:.1f} dBi for an antenna enclosed in a sphere of that diameter; this gain "
            "is achievable only by a non-planar or electrically small radiator, not by a "
            "planar aperture"
        )
    elif claimed_gain_dbi > g_typ:
        warnings.append(
            f"{label} claimed gain {claimed_gain_dbi:.1f} dBi exceeds the typical-efficiency "
            f"aperture gain {g_typ:.1f} dBi (eta = {efficiency}) for a {diameter_m} m aperture "
            f"at {frequency_hz / 1e9:.3f} GHz; it requires aperture efficiency "
            f"eta = {implied_eta:.2f}, which is physically allowed (<= 1) but unusually high"
        )

    return {
        "physical_limit_dbi": g_phys,
        "aperture_limit_dbi": g_ap,
        "harrington_limit_dbi": g_harr,
        "limiting_bound": bound,
        "typical_limit_dbi": g_typ,
        "implied_efficiency": implied_eta,
        "warnings": warnings,
    }


def _validate_non_negative_loss(loss_db: float, label: str) -> None:
    if loss_db < 0:
        raise PhysicalViolationError(
            message=f"{label} must be >= 0 dB, got {loss_db} dB",
            law_violated="Conservation of Energy",
            latex_explanation=r"$L \geq 0\,\text{dB}$; negative loss implies free energy gain",
            claimed_value=loss_db,
            unit="dB",
        )


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
    aperture_efficiency: float = DEFAULT_APERTURE_EFFICIENCY,
) -> dict:
    """Compute a full RF link budget using the Friis transmission equation.

    P_rx = P_tx + G_tx + G_rx - FSPL - L_tx - L_rx

    Args:
        tx_power_dbm: Transmit power in dBm.
        tx_antenna_gain_dbi: Transmit antenna gain in dBi.
        rx_antenna_gain_dbi: Receive antenna gain in dBi.
        frequency_hz: Carrier frequency in Hz.
        distance_m: Link distance in meters.
        tx_losses_db: TX-side miscellaneous losses in dB (must be >= 0).
        rx_losses_db: RX-side miscellaneous losses in dB (must be >= 0).
        tx_antenna_diameter_m: Optional TX antenna diameter for aperture check.
        rx_antenna_diameter_m: Optional RX antenna diameter for aperture check.
        aperture_efficiency: Efficiency for the typical-gain warning threshold.

    Returns:
        Dict with FSPL, received power, per-antenna gain limits (hard physical
        limit, eta = 1 aperture value, typical-efficiency gain and which bound
        regime applies), warnings, human-readable, and LaTeX.

    Raises:
        PhysicalViolationError: If antenna gains exceed the physical limit
            max(eta = 1 aperture value, Harrington bound), or losses are negative.
    """
    _validate_non_negative_loss(tx_losses_db, "TX losses")
    _validate_non_negative_loss(rx_losses_db, "RX losses")

    warnings: list[str] = []
    tx_physical_limit_dbi = None
    rx_physical_limit_dbi = None
    tx_aperture_limit_dbi = None
    rx_aperture_limit_dbi = None
    tx_typical_aperture_gain_dbi = None
    rx_typical_aperture_gain_dbi = None
    tx_limiting_bound = None
    rx_limiting_bound = None

    # Validate antenna gains against the physical gain limits if diameters provided
    if tx_antenna_diameter_m is not None:
        tx_check = validate_antenna_gain(
            tx_antenna_gain_dbi,
            tx_antenna_diameter_m,
            frequency_hz,
            "TX antenna",
            aperture_efficiency,
        )
        tx_physical_limit_dbi = tx_check["physical_limit_dbi"]
        tx_aperture_limit_dbi = tx_check["aperture_limit_dbi"]
        tx_typical_aperture_gain_dbi = tx_check["typical_limit_dbi"]
        tx_limiting_bound = tx_check["limiting_bound"]
        warnings.extend(tx_check["warnings"])

    if rx_antenna_diameter_m is not None:
        rx_check = validate_antenna_gain(
            rx_antenna_gain_dbi,
            rx_antenna_diameter_m,
            frequency_hz,
            "RX antenna",
            aperture_efficiency,
        )
        rx_physical_limit_dbi = rx_check["physical_limit_dbi"]
        rx_aperture_limit_dbi = rx_check["aperture_limit_dbi"]
        rx_typical_aperture_gain_dbi = rx_check["typical_limit_dbi"]
        rx_limiting_bound = rx_check["limiting_bound"]
        warnings.extend(rx_check["warnings"])

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

    # Far-field (Fraunhofer) check: Friis assumes d >> 2D^2/lambda for both antennas
    largest_d = max(d for d in (tx_antenna_diameter_m, rx_antenna_diameter_m, 0.0) if d is not None)
    if largest_d > 0:
        fraunhofer_m = 2.0 * largest_d**2 / wavelength
        if distance_m < fraunhofer_m:
            warnings.append(
                f"Distance {distance_m:.1f} m is inside the far-field (Fraunhofer) distance "
                f"2D^2/lambda = {fraunhofer_m:.1f} m for a {largest_d} m aperture; "
                "the Friis equation assumes far-field propagation"
            )

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
        "tx_physical_limit_dbi": tx_physical_limit_dbi,
        "rx_physical_limit_dbi": rx_physical_limit_dbi,
        "tx_aperture_limit_dbi": tx_aperture_limit_dbi,
        "rx_aperture_limit_dbi": rx_aperture_limit_dbi,
        "tx_typical_aperture_gain_dbi": tx_typical_aperture_gain_dbi,
        "rx_typical_aperture_gain_dbi": rx_typical_aperture_gain_dbi,
        "tx_limiting_bound": tx_limiting_bound,
        "rx_limiting_bound": rx_limiting_bound,
        "aperture_efficiency": aperture_efficiency,
        "warnings": warnings,
        "human_readable": human_readable,
        "latex": latex,
    }
