"""Thermal noise floor, Friis noise figure cascading, and receiver sensitivity.

Formulas:
    N = k_B * T * B                         (thermal noise power)
    F_total = F_1 + (F_2-1)/G_1 + ...      (Friis noise cascade)
    T_e = T_0 * (F - 1), T_0 = 290 K        (effective input noise temperature)
    S_min = k_B * (T_A + T_e) * B * SNR_req (receiver sensitivity)
                = N_floor + NF + SNR_req    when T_A = T_0 = 290 K

Noise figure is defined by IEEE at a source temperature T_0 = 290 K
(Pozar, "Microwave Engineering", Sec. 10.1). The receiver's own noise is
therefore fixed at T_e = T_0 (F - 1) regardless of the antenna/source
temperature T_A actually presented to it.
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

    for i, (_gain_db, nf_db) in enumerate(stages):
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


def effective_noise_temperature_k(noise_figure_db: float) -> float:
    """Effective input noise temperature T_e = T_0 * (F - 1) with T_0 = 290 K.

    Noise figure is defined at the IEEE reference temperature T_0 = 290 K, so
    T_e depends only on F, not on the temperature of the source actually
    connected to the receiver.

    Args:
        noise_figure_db: Noise figure in dB (must be >= 0).

    Returns:
        Effective input noise temperature in Kelvin.
    """
    if noise_figure_db < 0:
        raise PhysicalViolationError(
            message=f"Noise figure {noise_figure_db} dB is negative (below the quantum limit)",
            law_violated="Quantum Noise Limit",
            latex_explanation=r"$NF \geq 0\,\text{dB}$ required",
            claimed_value=noise_figure_db,
            unit="dB",
        )
    return T_REF.magnitude * (db_to_linear(noise_figure_db) - 1.0)


def receiver_sensitivity_dbm(
    bandwidth_hz: float,
    noise_figure_db: float,
    required_snr_db: float,
    temperature_k: float = 290.0,
) -> float:
    """Compute minimum receiver sensitivity.

    S_min = k_B * (T_A + T_e) * B * SNR_req,  T_e = T_0 * (F - 1),  T_0 = 290 K

    When the source (antenna) temperature T_A equals T_0 this reduces to the
    familiar S_min(dBm) = N_floor + NF + SNR_req. For T_A != 290 K the
    receiver's own noise contribution T_e is still referenced to 290 K
    because that is how NF is defined (IEEE; Pozar Sec. 10.1).

    Args:
        bandwidth_hz: Receiver bandwidth in Hz.
        noise_figure_db: System noise figure in dB.
        required_snr_db: Required SNR at the detector in dB.
        temperature_k: Source/antenna noise temperature T_A in Kelvin (default: 290K).

    Returns:
        Minimum detectable signal power in dBm.
    """
    validate_positive_bandwidth(bandwidth_hz)
    validate_temperature(temperature_k)
    t_e = effective_noise_temperature_k(noise_figure_db)
    t_total = temperature_k + t_e
    if t_total == 0:
        return float("-inf")
    n_total_dbm = thermal_noise_power_dbm(bandwidth_hz, t_total)
    return n_total_dbm + required_snr_db
