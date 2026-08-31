"""Pydantic models for the pulse-Doppler radar ambiguity tool."""

from pydantic import BaseModel, Field

from physbound.models.common import PhysBoundResult


class RadarAmbiguityInput(BaseModel):
    """Input parameters for pulse-Doppler unambiguous range/velocity calculation."""

    frequency_hz: float = Field(gt=0, description="Carrier frequency in Hz")
    prf_hz: float = Field(gt=0, description="Pulse repetition frequency in Hz")
    pulse_width_s: float | None = Field(
        default=None, gt=0, description="Transmitted pulse width tau in seconds"
    )
    target_velocity_m_s: float | None = Field(
        default=None, description="Target radial velocity in m/s (closing positive)"
    )
    bandwidth_hz: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Transmitted (compressed) bandwidth in Hz. When given, the range-resolution "
            "limit is c/(2B) instead of c*tau/2 for an unmodulated pulse"
        ),
    )
    claimed_unambiguous_range_m: float | None = Field(
        default=None, gt=0, description="Optional claimed unambiguous range to validate (m)"
    )
    claimed_unambiguous_velocity_m_s: float | None = Field(
        default=None,
        description="Optional claimed unambiguous radial velocity to validate (m/s, magnitude)",
    )
    claimed_range_resolution_m: float | None = Field(
        default=None, gt=0, description="Optional claimed range resolution to validate (m)"
    )


class RadarAmbiguityOutput(PhysBoundResult):
    """Output of pulse-Doppler radar ambiguity calculation."""

    wavelength_m: float
    pulse_repetition_interval_s: float
    max_unambiguous_range_m: float
    max_unambiguous_range_km: float
    first_blind_speed_m_s: float
    max_unambiguous_velocity_m_s: float
    max_unambiguous_doppler_hz: float
    range_velocity_product_m2_s: float
    doppler_shift_hz: float | None = None
    doppler_aliased: bool | None = None
    apparent_velocity_m_s: float | None = None
    range_resolution_m: float | None = None
    minimum_range_m: float | None = None
    duty_cycle: float | None = None
