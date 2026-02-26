"""Shannon-Hartley channel capacity theorem implementation.

Formulas:
    C = B * log2(1 + SNR)                  (channel capacity in bps)
    eta = C / B = log2(1 + SNR)            (spectral efficiency in bps/Hz)
    SNR_linear = 10^(SNR_dB / 10)          (dB to linear conversion)
"""

import math

from physbound.engines.units import db_to_linear
from physbound.errors import PhysicalViolationError
from physbound.validators import validate_positive_bandwidth, validate_positive_snr


def channel_capacity_bps(bandwidth_hz: float, snr_linear: float) -> float:
    """Compute Shannon-Hartley channel capacity: C = B * log2(1 + SNR).

    Args:
        bandwidth_hz: Channel bandwidth in Hz.
        snr_linear: Signal-to-noise ratio (linear, not dB).

    Returns:
        Maximum channel capacity in bits per second.
    """
    validate_positive_bandwidth(bandwidth_hz)
    validate_positive_snr(snr_linear)
    return bandwidth_hz * math.log2(1.0 + snr_linear)


def spectral_efficiency(snr_linear: float) -> float:
    """Compute spectral efficiency: eta = log2(1 + SNR) in bps/Hz.

    Args:
        snr_linear: Signal-to-noise ratio (linear, not dB).

    Returns:
        Spectral efficiency in bits/sec/Hz.
    """
    validate_positive_snr(snr_linear)
    return math.log2(1.0 + snr_linear)


def snr_db_to_linear(snr_db: float) -> float:
    """Convert SNR from dB to linear: SNR_linear = 10^(SNR_dB / 10)."""
    return db_to_linear(snr_db)


def validate_throughput_claim(
    bandwidth_hz: float,
    snr_linear: float,
    claimed_throughput_bps: float,
) -> dict:
    """Validate a throughput claim against the Shannon-Hartley limit.

    Args:
        bandwidth_hz: Channel bandwidth in Hz.
        snr_linear: Signal-to-noise ratio (linear, not dB).
        claimed_throughput_bps: Claimed throughput to validate in bps.

    Returns:
        Dict with capacity, claim validity, and excess percentage.

    Raises:
        PhysicalViolationError: If claimed throughput exceeds Shannon limit.
    """
    capacity = channel_capacity_bps(bandwidth_hz, snr_linear)
    eta = spectral_efficiency(snr_linear)

    if claimed_throughput_bps > capacity:
        excess_pct = ((claimed_throughput_bps - capacity) / capacity) * 100.0
        raise PhysicalViolationError(
            message=(
                f"Claimed throughput {claimed_throughput_bps:.1f} bps exceeds "
                f"Shannon limit of {capacity:.1f} bps by {excess_pct:.1f}%"
            ),
            law_violated="Shannon-Hartley Theorem",
            latex_explanation=(
                rf"$C = B \log_2(1 + \text{{SNR}}) = "
                rf"{bandwidth_hz:.0f} \times \log_2(1 + {snr_linear:.2f}) = "
                rf"{capacity:.1f}\,\text{{bps}}$. "
                rf"Claimed ${claimed_throughput_bps:.1f}\,\text{{bps}}$ exceeds "
                rf"the Shannon limit by ${excess_pct:.1f}\%$."
            ),
            computed_limit=capacity,
            claimed_value=claimed_throughput_bps,
            unit="bps",
        )

    # Warn if spectral efficiency is unusually high (> 20 bps/Hz)
    warnings = []
    claimed_eta = claimed_throughput_bps / bandwidth_hz
    if claimed_eta > 20:
        warnings.append(
            f"Claimed spectral efficiency {claimed_eta:.1f} bps/Hz exceeds "
            "20 bps/Hz; possible but unusual in practical systems"
        )

    return {
        "capacity_bps": capacity,
        "spectral_efficiency_bps_hz": eta,
        "claim_is_valid": True,
        "excess_percentage": 0.0,
        "warnings": warnings,
    }
