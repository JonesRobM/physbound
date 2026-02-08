"""Hard-limit guard functions enforcing physical laws.

These validators are called by engine modules before computation to reject
inputs that would violate fundamental physics. Each raises PhysicalViolationError
with a LaTeX explanation on failure.
"""

from physbound.errors import PhysicalViolationError


def validate_positive_frequency(frequency_hz: float) -> None:
    """Reject non-positive frequencies."""
    if frequency_hz <= 0:
        raise PhysicalViolationError(
            message=f"Frequency must be positive, got {frequency_hz} Hz",
            law_violated="Electromagnetic Theory",
            latex_explanation=r"$f > 0$ required; negative or zero frequency is non-physical",
            claimed_value=frequency_hz,
            unit="Hz",
        )


def validate_positive_distance(distance_m: float) -> None:
    """Reject non-positive distances."""
    if distance_m <= 0:
        raise PhysicalViolationError(
            message=f"Distance must be positive, got {distance_m} m",
            law_violated="Euclidean Geometry",
            latex_explanation=r"$d > 0$ required for physical separation between TX and RX",
            claimed_value=distance_m,
            unit="m",
        )


def validate_positive_bandwidth(bandwidth_hz: float) -> None:
    """Reject non-positive bandwidths."""
    if bandwidth_hz <= 0:
        raise PhysicalViolationError(
            message=f"Bandwidth must be positive, got {bandwidth_hz} Hz",
            law_violated="Signal Processing",
            latex_explanation=r"$B > 0$ required; zero or negative bandwidth is non-physical",
            claimed_value=bandwidth_hz,
            unit="Hz",
        )


def validate_temperature(temperature_k: float) -> None:
    """Reject negative absolute temperatures."""
    if temperature_k < 0:
        raise PhysicalViolationError(
            message=f"Temperature must be >= 0 K, got {temperature_k} K",
            law_violated="Third Law of Thermodynamics",
            latex_explanation=(
                r"$T \geq 0\,\text{K}$ required by the third law of thermodynamics; "
                r"negative absolute temperature is non-physical in this context"
            ),
            claimed_value=temperature_k,
            unit="K",
        )


def validate_positive_snr(snr_linear: float) -> None:
    """Reject non-positive linear SNR values."""
    if snr_linear <= 0:
        raise PhysicalViolationError(
            message=f"SNR (linear) must be positive, got {snr_linear}",
            law_violated="Information Theory",
            latex_explanation=r"$\text{SNR} > 0$ required; signal power cannot be non-positive",
            claimed_value=snr_linear,
        )
