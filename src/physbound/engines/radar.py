"""Monostatic radar range equation and SNR computation.

Formulas:
    R_max = [P_t * G^2 * lambda^2 * sigma / ((4*pi)^3 * S_min * L)]^(1/4)
    SNR = P_t * G^2 * lambda^2 * sigma / ((4*pi)^3 * k_B * T_s * B_n * R^4 * L)
    S_min = k_B * T_s * B_n * SNR_min / N_pulses
"""

import math

from physbound.engines.constants import BOLTZMANN, SPEED_OF_LIGHT
from physbound.engines.units import db_to_linear
from physbound.errors import PhysicalViolationError
from physbound.validators import (
    validate_positive_bandwidth,
    validate_positive_frequency,
    validate_positive_power,
    validate_positive_rcs,
    validate_temperature,
)


def compute_radar_range(
    peak_power_w: float,
    antenna_gain_dbi: float,
    frequency_hz: float,
    rcs_m2: float,
    system_noise_temp_k: float = 290.0,
    noise_bandwidth_hz: float = 1e6,
    min_snr_db: float = 13.0,
    claimed_range_m: float | None = None,
    num_pulses: int = 1,
    losses_db: float = 0.0,
) -> dict:
    """Compute maximum monostatic radar detection range.

    Args:
        peak_power_w: Peak transmit power in watts.
        antenna_gain_dbi: Antenna gain in dBi (monostatic: same for TX/RX).
        frequency_hz: Operating frequency in Hz.
        rcs_m2: Radar cross section in m^2.
        system_noise_temp_k: System noise temperature in Kelvin.
        noise_bandwidth_hz: Receiver noise bandwidth in Hz.
        min_snr_db: Minimum required SNR in dB for detection.
        claimed_range_m: Optional claimed detection range to validate.
        num_pulses: Number of coherently integrated pulses.
        losses_db: Total system losses in dB.

    Returns:
        Dict with max_range_m, max_range_km, wavelength_m,
        min_detectable_power_w/dbm, human_readable, latex, warnings.

    Raises:
        PhysicalViolationError: If inputs violate physics or claimed range
            exceeds R_max.
    """
    # Validate inputs
    validate_positive_power(peak_power_w)
    validate_positive_frequency(frequency_hz)
    validate_positive_rcs(rcs_m2)
    validate_temperature(system_noise_temp_k)
    validate_positive_bandwidth(noise_bandwidth_hz)

    if num_pulses < 1:
        raise PhysicalViolationError(
            message=f"Number of pulses must be >= 1, got {num_pulses}",
            law_violated="Radar Signal Processing",
            latex_explanation=r"$N_{\text{pulses}} \geq 1$ required",
            claimed_value=float(num_pulses),
        )
    if losses_db < 0:
        raise PhysicalViolationError(
            message=f"System losses must be >= 0 dB, got {losses_db} dB",
            law_violated="Conservation of Energy",
            latex_explanation=r"$L \geq 0\,\text{dB}$; negative loss implies free energy gain",
            claimed_value=losses_db,
            unit="dB",
        )

    # Derived quantities
    c = SPEED_OF_LIGHT.magnitude
    k_b = BOLTZMANN.magnitude
    wavelength_m = c / frequency_hz
    gain_linear = db_to_linear(antenna_gain_dbi)
    snr_min_linear = db_to_linear(min_snr_db)
    losses_linear = db_to_linear(losses_db)
    integration_gain = num_pulses

    # Minimum detectable signal power
    s_min_w = (k_b * system_noise_temp_k * noise_bandwidth_hz * snr_min_linear) / integration_gain
    s_min_dbm = 10.0 * math.log10(s_min_w / 1e-3)

    # Radar range equation: R_max
    numerator = peak_power_w * gain_linear**2 * wavelength_m**2 * rcs_m2
    denominator = (4.0 * math.pi) ** 3 * s_min_w * losses_linear
    r_max_m = (numerator / denominator) ** 0.25

    # Warnings
    warnings: list[str] = []
    if frequency_hz > 3e11:
        warnings.append(
            "Frequency > 300 GHz: atmospheric absorption may significantly "
            "reduce effective range beyond the free-space model."
        )
    if num_pulses > 1:
        warnings.append(
            f"Coherent integration of {num_pulses} pulses assumed "
            f"(gain = N). Non-coherent integration yields gain = sqrt(N)."
        )
    if rcs_m2 > 100:
        warnings.append(
            "RCS > 100 m^2 is typical only for very large targets (ships, large aircraft)."
        )
    if rcs_m2 < 1e-4:
        warnings.append("RCS < 0.0001 m^2 is at the limit of detectability for most radar systems.")

    # Validate claimed range
    if claimed_range_m is not None and claimed_range_m > r_max_m:
        excess_pct = ((claimed_range_m - r_max_m) / r_max_m) * 100.0
        raise PhysicalViolationError(
            message=(
                f"Claimed detection range {claimed_range_m:.1f} m "
                f"({claimed_range_m / 1000:.1f} km) exceeds radar range "
                f"equation limit of {r_max_m:.1f} m "
                f"({r_max_m / 1000:.1f} km) by {excess_pct:.1f}%"
            ),
            law_violated="Radar Range Equation",
            latex_explanation=(
                rf"$R_{{\max}} = \left[\frac{{P_t G^2 \lambda^2 \sigma}}"
                rf"{{(4\pi)^3 S_{{\min}} L}}\right]^{{1/4}} = "
                rf"{r_max_m:.1f}\,\text{{m}}$. "
                rf"Claimed ${claimed_range_m:.1f}\,\text{{m}}$ exceeds "
                rf"this limit by ${excess_pct:.1f}\%$."
            ),
            computed_limit=r_max_m,
            claimed_value=claimed_range_m,
            unit="m",
        )

    # Human-readable output
    power_dbm = 10.0 * math.log10(peak_power_w / 1e-3)
    human_readable = (
        f"Radar Range Equation (Monostatic):\n"
        f"  Peak Power:     {peak_power_w:.1f} W ({power_dbm:.1f} dBm)\n"
        f"  Antenna Gain:   {antenna_gain_dbi:.1f} dBi\n"
        f"  Frequency:      {frequency_hz / 1e9:.3f} GHz "
        f"(lambda = {wavelength_m:.4f} m)\n"
        f"  RCS:            {rcs_m2:.4f} m^2\n"
        f"  System Temp:    {system_noise_temp_k:.1f} K\n"
        f"  Noise BW:       {noise_bandwidth_hz / 1e6:.3f} MHz\n"
        f"  Min SNR:        {min_snr_db:.1f} dB\n"
        f"  Losses:         {losses_db:.1f} dB\n"
        f"  Pulses:         {num_pulses}\n"
        f"  S_min:          {s_min_dbm:.2f} dBm ({s_min_w:.3e} W)\n"
        f"  Max Range:      {r_max_m:.1f} m ({r_max_m / 1000:.2f} km)"
    )

    # LaTeX output
    latex = (
        rf"$R_{{\max}} = \left[\frac{{P_t G^2 \lambda^2 \sigma}}"
        rf"{{(4\pi)^3 S_{{\min}} L}}\right]^{{1/4}} = "
        rf"\left[\frac{{{peak_power_w:.1f} \times {gain_linear:.2f}^2 \times "
        rf"{wavelength_m:.4f}^2 \times {rcs_m2:.4f}}}"
        rf"{{(4\pi)^3 \times {s_min_w:.3e} \times {losses_linear:.2f}}}"
        rf"\right]^{{1/4}} = {r_max_m:.1f}\,\text{{m}}$"
    )

    return {
        "max_range_m": r_max_m,
        "max_range_km": r_max_m / 1000.0,
        "wavelength_m": wavelength_m,
        "min_detectable_power_w": s_min_w,
        "min_detectable_power_dbm": s_min_dbm,
        "antenna_gain_linear": gain_linear,
        "snr_min_linear": snr_min_linear,
        "integration_gain": integration_gain,
        "losses_linear": losses_linear,
        "warnings": warnings,
        "human_readable": human_readable,
        "latex": latex,
    }
