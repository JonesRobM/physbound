"""Thermal noise floor, Friis noise figure cascading, and receiver sensitivity.

Formulas:
    N = k_B * T * B                         (thermal noise power)
    F_total = F_1 + (F_2-1)/G_1 + ...      (Friis noise cascade)
    S_min = N_floor + NF + SNR_req          (receiver sensitivity)
"""

import math

from physbound.engines.constants import BOLTZMANN, T_REF
from physbound.engines.units import db_to_linear, linear_to_db
from physbound.errors import PhysicalViolationError
from physbound.validators import validate_positive_bandwidth, validate_temperature


def thermal_noise_power_dbm(bandwidth_hz: float, temperature_k: float = 290.0) -> float:
    """Compute thermal noise power N = k_B * T * B in dBm.

    Args:
        bandwidth_hz: Receiver bandwidth in Hz.
        temperature_k: System noise temperature in Kelvin (default: 290K).

    Returns:
        Thermal noise power in dBm.
    """
    validate_positive_bandwidth(bandwidth_hz)
    validate_temperature(temperature_k)

    if temperature_k == 0:
        return float("-inf")

    k_b = BOLTZMANN.magnitude  # J/K
    n_watts = k_b * temperature_k * bandwidth_hz
    n_dbm = 10.0 * math.log10(n_watts / 1e-3)
    return n_dbm


def thermal_noise_power_watts(bandwidth_hz: float, temperature_k: float = 290.0) -> float:
    """Compute thermal noise power N = k_B * T * B in watts.

    Args:
        bandwidth_hz: Receiver bandwidth in Hz.
        temperature_k: System noise temperature in Kelvin (default: 290K).

    Returns:
        Thermal noise power in watts.
    """
    validate_positive_bandwidth(bandwidth_hz)
    validate_temperature(temperature_k)

    k_b = BOLTZMANN.magnitude
    return k_b * temperature_k * bandwidth_hz


def friis_noise_cascade(
    stages: list[tuple[float, float]],
) -> float:
    """Compute cascaded noise figure using the Friis formula.

    F_total = F_1 + (F_2 - 1)/G_1 + (F_3 - 1)/(G_1*G_2) + ...

    Args:
        stages: List of (gain_db, noise_figure_db) tuples for each stage.

    Returns:
        Total cascaded noise figure in dB.

    Raises:
        PhysicalViolationError: If noise figure is negative (below quantum limit).
    """
    if not stages:
        raise PhysicalViolationError(
            message="At least one stage is required for noise cascade",
            law_violated="Friis Noise Formula",
            latex_explanation=r"$F_\text{total}$ requires at least one stage",
        )

    for i, (gain_db, nf_db) in enumerate(stages):
        if nf_db < 0:
            raise PhysicalViolationError(
                message=f"Stage {i + 1} noise figure is {nf_db} dB (negative); "
                "this implies a noiseless amplifier below the quantum limit",
                law_violated="Quantum Noise Limit",
                latex_explanation=(
                    rf"$NF_{{{i + 1}}} = {nf_db}\,\text{{dB}} < 0$; "
                    r"violates the quantum noise limit $NF \geq 0\,\text{dB}$"
                ),
                claimed_value=nf_db,
                unit="dB",
            )

    # Convert to linear
    gains_linear = [db_to_linear(g) for g, _ in stages]
    nf_linear = [db_to_linear(nf) for _, nf in stages]

    # Friis formula
    f_total = nf_linear[0]
    cumulative_gain = 1.0
    for i in range(1, len(stages)):
        cumulative_gain *= gains_linear[i - 1]
        f_total += (nf_linear[i] - 1.0) / cumulative_gain

    return linear_to_db(f_total)


def receiver_sensitivity_dbm(
    bandwidth_hz: float,
    noise_figure_db: float,
    required_snr_db: float,
    temperature_k: float = 290.0,
) -> float:
    """Compute minimum receiver sensitivity: S_min = N_floor + NF + SNR_req.

    Args:
        bandwidth_hz: Receiver bandwidth in Hz.
        noise_figure_db: System noise figure in dB.
        required_snr_db: Required SNR at the detector in dB.
        temperature_k: Reference temperature in Kelvin (default: 290K).

    Returns:
        Minimum detectable signal power in dBm.
    """
    n_floor = thermal_noise_power_dbm(bandwidth_hz, temperature_k)
    return n_floor + noise_figure_db + required_snr_db
